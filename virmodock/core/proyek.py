"""Model data proyek VirmoDock (folder *.vmd).

  NamaProyek.vmd/
    proyek.json          semua metadata & parameter (ditulis atomik, 5 cadangan di .cadangan/)
    objek/               isi objek viewer (struktur asli, ligan asli, ...) agar sesi pulih persis
    reseptor/            asli.pdb, bersih.pdb, reseptor.pdbqt, laporan_prep.txt
    ligan/               sumber/*.sdf, pdbqt/*.pdbqt
    grid/                reseptor.gpf, *.map, reseptor.maps.fld (dipakai ulang bila GPF sama)
    hasil/<id_job>/      keluaran mesin per ligan + log
"""
import json
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

VERSI_FORMAT = 1


def nama_aman(t):
    t = re.sub(r"[^A-Za-z0-9_.-]+", "_", t.strip()).strip("._")
    return t[:80] or "x"


def tulis_atomik(path, teks):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(teks)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class Proyek:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.nama = self.folder.stem
        self.dibuat = datetime.now().isoformat(timespec="seconds")
        self.reseptor = None          # dict: nama, sumber, pdbqt, bersih, asli, metode, atom, residu, dibuang, logam, objek
        self.ligan = []               # list dict: id, nama, sumber, status, alasan, sdf, pdbqt, rumus, mw, torsi, atom, tipe, objek
        self.kotak = None             # dict: pusat, ukuran, spasi
        self.parameter = {}
        self.uji_grafik = {}          # data & pengaturan tab Uji & Grafik
        self.komposer = {}            # Komposer figur: {panel, opsi}; panel raster disimpan di komposer/*.png
        self.job = []                 # list dict (lihat core/antrean.py)
        self.objek = []               # list dict objek viewer
        self.catatan = ""
        self.validasi = {}            # hasil validasi redocking terakhir
        self.eksperimen = {}          # data aktivitas eksperimen (ChEMBL): target, aktivitas [{chembl, nama, smiles, inchikey, pchembl, …}]

    # ------------------------------------------------------------- jalur
    def p(self, *bag):
        return self.folder.joinpath(*bag)

    def rel(self, path):
        return Path(path).resolve().relative_to(self.folder.resolve()).as_posix()

    def siapkan_folder(self):
        for d in ("objek", "reseptor", "ligan/sumber", "ligan/pdbqt", "grid", "hasil", ".cadangan"):
            self.p(d).mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------- simpan/buka
    def ke_dict(self):
        return {"format": VERSI_FORMAT, "aplikasi": "VirmoDock", "nama": self.nama, "dibuat": self.dibuat,
                "diubah": datetime.now().isoformat(timespec="seconds"), "reseptor": self.reseptor,
                "ligan": self.ligan, "kotak": self.kotak, "parameter": self.parameter, "uji_grafik": self.uji_grafik,
                "komposer": self.komposer, "job": self.job,
                "objek": self.objek, "catatan": self.catatan, "validasi": self.validasi,
                "eksperimen": self.eksperimen}

    def simpan(self):
        self.siapkan_folder()
        f = self.p("proyek.json")
        if f.exists():  # cadangan bergilir 5 versi
            cad = sorted(self.p(".cadangan").glob("proyek_*.json"))
            for lama in cad[:-4]:
                lama.unlink(missing_ok=True)
            shutil.copy2(f, self.p(".cadangan", f"proyek_{time.strftime('%Y%m%d_%H%M%S')}.json"))
        tulis_atomik(f, json.dumps(self.ke_dict(), ensure_ascii=False, indent=1))

    @classmethod
    def buka(cls, folder):
        folder = Path(folder)
        f = folder / "proyek.json"
        if not f.exists():
            raise FileNotFoundError(f"{folder} bukan folder proyek VirmoDock (proyek.json tidak ada).")
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cad = sorted((folder / ".cadangan").glob("proyek_*.json"))
            if not cad:
                raise
            d = json.loads(cad[-1].read_text(encoding="utf-8"))
        pr = cls(folder)
        pr.nama = d.get("nama", folder.stem)
        pr.dibuat = d.get("dibuat", pr.dibuat)
        for k in ("reseptor", "kotak", "catatan"):
            setattr(pr, k, d.get(k))
        pr.catatan = pr.catatan or ""
        pr.ligan = d.get("ligan") or []
        pr.parameter = d.get("parameter") or {}
        pr.uji_grafik = d.get("uji_grafik") or {}
        pr.komposer = d.get("komposer") or {}
        pr.job = d.get("job") or []
        pr.objek = d.get("objek") or []
        pr.validasi = d.get("validasi") or {}
        pr.eksperimen = d.get("eksperimen") or {}
        # job yang terputus (aplikasi ditutup/crash) bisa dilanjutkan
        for j in pr.job:
            if j.get("status") in ("berjalan", "menunggu"):
                j["status"] = "dijeda"
                for l in j.get("ligan", []):
                    if l.get("status") == "berjalan":
                        l["status"] = "menunggu"
                        l["progres"] = 0
        return pr

    @classmethod
    def baru(cls, induk, nama):
        folder = Path(induk) / (nama_aman(nama) + ".vmd")
        n = 2
        while folder.exists():
            folder = Path(induk) / f"{nama_aman(nama)}_{n}.vmd"
            n += 1
        pr = cls(folder)
        pr.nama = nama
        pr.siapkan_folder()
        pr.simpan()
        return pr

    # -------------------------------------------------------------- objek
    def simpan_objek(self, daftar):
        """daftar: objek molekul.Objek dari sesi. Teks ditulis ke objek/<id>.<fmt>."""
        self.p("objek").mkdir(parents=True, exist_ok=True)
        hasil, dipakai = [], set()
        for o in daftar:
            nama_f = f"{o.id}.{o.fmt}"
            f = self.p("objek", nama_f)
            if not f.exists() or f.stat().st_size != len(o.teks.encode()):
                f.write_text(o.teks, encoding="utf-8")
            dipakai.add(nama_f)
            hasil.append({"id": o.id, "nama": o.nama, "jenis": o.jenis, "fmt": o.fmt, "berkas": f"objek/{nama_f}",
                          "sumber": o.sumber, "tampil": o.tampil, "rantai": o.rantai, "info": o.info, "gaya": o.gaya,
                          "induk": o.induk, "grup": getattr(o, "grup", "")})
        for f in self.p("objek").glob("*"):
            if f.name not in dipakai:
                f.unlink(missing_ok=True)
        self.objek = hasil

    def muat_objek(self):
        from . import molekul
        hasil = []
        for d in self.objek:
            f = self.p(d["berkas"])
            if not f.exists():
                continue
            o = molekul.Objek(nama=d["nama"], jenis=d["jenis"], teks=f.read_text(encoding="utf-8"), fmt=d["fmt"],
                              sumber=d.get("sumber", ""), id=molekul.id_baru(), tampil=d.get("tampil", True),
                              rantai={k: [tuple(x) for x in v] for k, v in (d.get("rantai") or {}).items()},
                              info=d.get("info") or {}, gaya=d.get("gaya") or {}, induk=d.get("induk", ""),
                              grup=d.get("grup", ""))
            o.id_lama = d["id"]
            hasil.append(o)
        # petakan id lama -> baru untuk referensi induk/reseptor/ligan
        peta = {o.id_lama: o.id for o in hasil}
        for o in hasil:
            o.induk = peta.get(o.induk, "")
        return hasil, peta

    # ------------------------------------------------------------- ligan
    def ligan_siap(self):
        return [l for l in self.ligan if l.get("status") in ("siap", "peringatan") and l.get("pdbqt")]

    def cari_ligan(self, lid):
        return next((l for l in self.ligan if l["id"] == lid), None)

    def id_ligan_baru(self, nama):
        dasar = nama_aman(nama)
        ada = {l["id"] for l in self.ligan}
        lid, n = dasar, 2
        while lid in ada:
            lid = f"{dasar}_{n}"
            n += 1
        return lid

    def job_baru_id(self):
        dasar = time.strftime("J%Y%m%d_%H%M%S")
        ada = {j["id"] for j in self.job}
        jid, n = dasar, 2
        while jid in ada:
            jid = f"{dasar}_{n}"
            n += 1
        return jid
