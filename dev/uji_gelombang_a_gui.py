"""Uji GUI MPO + rencana lab basah pada jendela utama yang sebenarnya.

Dulu memakai MockJW berisi daftar ligan buatan; mock itu tidak punya `_sumber_sifat`, `objek`, atau `box` seperti
jendela asli, sehingga lulus walau dialognya tidak bisa dibuka dari aplikasi. Kini memanggil harness bersama
dev/uji_dialog_lanjut_gui.py yang membuka dialog lewat menu jendela asli pada proyek contoh.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_gelombang_a_gui.py
"""
import subprocess
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
perintah = [sys.executable, str(AKAR / "dev" / "uji_dialog_lanjut_gui.py"), "mpo", "labplanner"]
p = subprocess.run(perintah, cwd=AKAR, capture_output=True, text=True, encoding="utf-8", errors="replace")
keluaran = (p.stdout or "") + (p.stderr or "")
print(keluaran.strip())
if "LEWAT:" in keluaran:
    raise SystemExit(0)
raise SystemExit(p.returncode or (0 if "LULUS" in keluaran else 1))
