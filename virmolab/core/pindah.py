"""Pindah laptop: ekspor/impor pengaturan (+ proyek opsional) dalam satu berkas .vmdbackup (zip)."""
import base64
import json
import zipfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray

from . import paths

LEWATI = {"sesi_terbuka"}          # khusus laptop ini
JALUR = {"folder_kerja", "dir_terakhir", "proyek_terakhir"}


def _ke_json(v):
    if isinstance(v, (QByteArray, bytes, bytearray)):
        return {"__bytes__": base64.b64encode(bytes(v)).decode()}
    return v


def _dari_json(v):
    if isinstance(v, dict) and "__bytes__" in v:
        return QByteArray(base64.b64decode(v["__bytes__"]))
    return v


def ekspor(path, st, proyek=(), versi="", lapor=None):
    """st: QSettings; proyek: daftar folder .vmd yang ikut dikemas."""
    data = {k: _ke_json(st.value(k)) for k in st.allKeys() if k not in LEWATI}
    meta = {"aplikasi": "VirmoLab", "versi": versi, "dibuat": datetime.now().isoformat(timespec="seconds"),
            "proyek": [Path(p).name for p in proyek]}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=1))
        z.writestr("pengaturan.json", json.dumps(data, ensure_ascii=False, indent=1, default=str))
        for p in proyek:
            p = Path(p)
            for f in p.rglob("*"):
                if f.is_file() and ".cadangan" not in f.parts:
                    z.write(f, f"proyek/{p.name}/{f.relative_to(p).as_posix()}")
            if lapor:
                lapor.log.emit(f"Dikemas: {p.name}")
    return meta


def baca_meta(path):
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read("meta.json"))


def impor(path, st, folder_proyek, lapor=None):
    """Pulihkan pengaturan; jalur yang tidak ada di laptop ini diabaikan. Proyek diekstrak ke folder_proyek.

    Mengembalikan (jumlah kunci, [folder proyek hasil ekstrak], [catatan])."""
    catatan, hasil = [], []
    with zipfile.ZipFile(path) as z:
        meta = json.loads(z.read("meta.json"))
        if meta.get("aplikasi") not in ("VirmoLab", paths.NAMA_LAMA):     # cadangan buatan versi lama tetap diterima
            raise ValueError("Berkas bukan cadangan VirmoLab.")
        data = json.loads(z.read("pengaturan.json"))
        n = 0
        for k, v in data.items():
            v = _dari_json(v)
            if k in JALUR and isinstance(v, str) and v and not Path(v).exists():
                catatan.append(f"Jalur '{k}' tidak ada di laptop ini ({v}); dipakai bawaan.")
                continue
            if k == "eksternal" and isinstance(v, dict):
                v = {nama: j for nama, j in v.items() if Path(j).exists()}
            st.setValue(k, v)
            n += 1
        folder_proyek = Path(folder_proyek)
        folder_proyek.mkdir(parents=True, exist_ok=True)
        nama = sorted({Path(i).parts[1] for i in z.namelist() if i.startswith("proyek/") and len(Path(i).parts) > 2})
        for nm in nama:
            tujuan = folder_proyek / nm
            k = 2
            while tujuan.exists():
                tujuan = folder_proyek / f"{Path(nm).stem}_{k}.vmd"
                k += 1
            for i in z.namelist():
                if i.startswith(f"proyek/{nm}/") and not i.endswith("/"):
                    f = tujuan / i[len(f"proyek/{nm}/"):]
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_bytes(z.read(i))
            hasil.append(str(tujuan))
            if lapor:
                lapor.log.emit(f"Proyek dipulihkan: {tujuan}")
    st.sync()
    return n, hasil, catatan
