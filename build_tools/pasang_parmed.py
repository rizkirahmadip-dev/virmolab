"""Pasang ParmEd 4.3.1 tanpa ekstensi C++ _rdparm.

Sumber resmi butuh Visual C++ untuk parser prmtop cepat. VirmoDock hanya memakai
penulis topologi GROMACS, yang berjalan di Python murni. Berkas Python ParmEd tidak diubah.
"""
import tarfile
from pathlib import Path

VERSI = "4.3.1"
AKAR = Path(__file__).resolve().parents[1]
TUJUAN = AKAR / "vendor" / "_unduh" / "parmed"
ARSIP = TUJUAN / f"parmed-{VERSI}.tar.gz"
SUMBER = TUJUAN / f"parmed-{VERSI}"


def main():
    import subprocess
    import sys
    TUJUAN.mkdir(parents=True, exist_ok=True)
    py = AKAR / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = Path(sys.executable)
    if not ARSIP.exists():
        subprocess.check_call([str(py), "-m", "pip", "download", f"parmed=={VERSI}",
                               "-d", str(TUJUAN), "--no-binary", ":all:"])
    if not (SUMBER / "setup.py").exists():
        with tarfile.open(ARSIP) as arsip:
            arsip.extractall(TUJUAN)
    setup = (SUMBER / "setup.py").read_text(encoding="utf-8")
    setup = setup.replace("ext_modules=extensions,", "ext_modules=[],")
    (SUMBER / "setup.py").write_text(setup, encoding="utf-8")
    subprocess.check_call([str(py), "-m", "pip", "install", "--no-build-isolation", str(SUMBER)])


if __name__ == "__main__":
    main()
