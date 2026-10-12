"""Plugin pengguna (rencana v2.0): berkas .py di folder plugin VirmoDock, dimuat ke menu Alat › Plugin.

Format plugin (satu berkas .py):

    PLUGIN = {"nama": "Nama plugin", "versi": "1.0", "keterangan": "Apa yang dilakukan"}

    def pasang(vd):
        # vd = jendela utama VirmoDock (lihat KONTEKS di konsol: vd.proyek, vd.objek, vd.log.tulis, …)
        return [("Jalankan sesuatu", lambda: fungsi(vd))]   # daftar (label menu, fungsi)

Plugin menjalankan kode Python bebas dengan hak pengguna - pasang hanya plugin dari sumber tepercaya.
Galat saat memuat atau menjalankan plugin ditangkap dan ditulis ke Log; tidak menghentikan aplikasi.
"""
import importlib.util
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from . import paths

FOLDER = paths.APPDATA / "plugin"
CONTOH = '''"""Contoh plugin VirmoDock: ringkasan ΔG hasil docking ke panel Pesan.

Salin berkas ini dengan nama lain (tanpa awalan "_"), ubah sesukanya, lalu Alat › Plugin › Muat ulang plugin.
"""
PLUGIN = {"nama": "Ringkasan ΔG", "versi": "1.0", "keterangan": "Rerata dan rentang ΔG pose terbaik semua ligan"}


def ringkas(vd):
    from virmodock.core import ekspor
    if not vd.proyek:
        vd.pesan.tulis("Ringkasan ΔG: belum ada proyek.")
        return
    nilai = [b["energi"] for b in ekspor.baris_hasil(vd.proyek)]
    if not nilai:
        vd.pesan.tulis("Ringkasan ΔG: belum ada hasil docking.")
        return
    vd.pesan.tulis(f"Ringkasan ΔG: {len(nilai)} ligan, rerata {sum(nilai) / len(nilai):.2f}, "
                   f"terbaik {min(nilai):.2f}, terburuk {max(nilai):.2f} kcal/mol")


def pasang(vd):
    return [("Ringkasan ΔG ke Pesan", lambda: ringkas(vd))]
'''


@dataclass
class Plugin:
    berkas: Path
    nama: str
    versi: str = ""
    keterangan: str = ""
    aksi: list = field(default_factory=list)     # [(label, fungsi)]
    galat: str = ""


def siapkan_folder():
    FOLDER.mkdir(parents=True, exist_ok=True)
    c = FOLDER / "_contoh_plugin.py"
    if not c.exists():
        c.write_text(CONTOH, encoding="utf-8")
    return FOLDER


def muat(vd, log=print):
    """Muat semua plugin (*.py tanpa awalan '_') dari FOLDER. Kembalikan [Plugin]."""
    siapkan_folder()
    hasil = []
    for f in sorted(FOLDER.glob("*.py")):
        if f.name.startswith("_"):
            continue
        nama_mod = f"virmodock_plugin_{f.stem}"
        p = Plugin(berkas=f, nama=f.stem)
        try:
            spec = importlib.util.spec_from_file_location(nama_mod, f)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[nama_mod] = mod
            spec.loader.exec_module(mod)
            info = getattr(mod, "PLUGIN", {}) or {}
            p.nama = str(info.get("nama") or f.stem)
            p.versi = str(info.get("versi") or "")
            p.keterangan = str(info.get("keterangan") or "")
            if not callable(getattr(mod, "pasang", None)):
                raise ValueError("tidak punya fungsi pasang(vd)")
            aksi = mod.pasang(vd) or []
            p.aksi = [(str(t), fn) for t, fn in aksi if callable(fn)]
            log(f"Plugin dimuat: {p.nama} {p.versi} ({f.name}, {len(p.aksi)} perintah)")
        except Exception as e:
            p.galat = f"{type(e).__name__}: {e}"
            log(f"Plugin {f.name} gagal dimuat: {p.galat}\n{traceback.format_exc(limit=3)}")
        hasil.append(p)
    return hasil


def jalankan(p, label, fn, log=print):
    """Panggil perintah plugin dengan galat tertangkap."""
    try:
        fn()
    except Exception as e:
        log(f"Plugin {p.nama} › {label} gagal: {type(e).__name__}: {e}\n{traceback.format_exc(limit=4)}")
