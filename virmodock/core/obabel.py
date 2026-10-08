"""Open Babel sebagai PROGRAM TERPISAH (obabel.exe lewat subprocess).

Open Babel berlisensi GPL-2.0; dipanggil sebagai proses terpisah (agregasi),
bukan di-import ke proses Python yang juga memuat Qt (LGPL-3). Lihat
RENCANA_LENGKAP.md Lampiran B2.
"""
import os
import subprocess

from . import paths

NOWIN = 0x08000000 if os.name == "nt" else 0


class GalatObabel(Exception):
    pass


def folder():
    return paths.BIN / "openbabel"


def tersedia():
    return (folder() / "obabel.exe").exists()


def konversi(teks, dari, ke, opsi=(), timeout=120):
    """Konversi teks molekul format `dari` -> `ke` (mis. "pdb" -> "mol"). opsi: argumen tambahan obabel."""
    d = folder()
    exe = d / "obabel.exe"
    if not exe.exists():
        raise GalatObabel("obabel.exe tidak ditemukan di folder bin/openbabel. Pasang ulang VirmoDock.")
    env = dict(os.environ, BABEL_LIBDIR=str(d), BABEL_DATADIR=str(d / "data"))
    cmd = [str(exe), f"-i{dari}", f"-o{ke}", *opsi]
    try:
        p = subprocess.run(cmd, input=teks.encode("utf-8"), capture_output=True, timeout=timeout, env=env,
                           cwd=str(d), creationflags=NOWIN)
    except subprocess.TimeoutExpired:
        raise GalatObabel("Open Babel melebihi batas waktu.")
    keluar = p.stdout.decode("utf-8", "replace")
    if not keluar.strip():
        pesan = p.stderr.decode("utf-8", "replace").strip().splitlines()
        raise GalatObabel("Open Babel gagal: " + (pesan[-1] if pesan else f"kode {p.returncode}"))
    return keluar
