r"""Ikon aplikasi kini dibuat dari logo resmi: jalankan build_tools/logo/produksi.py lalu salin ke virmodock/aset.

  .venv\Scripts\python.exe dev\buat_ikon.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

AKAR = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(AKAR / "build_tools" / "logo" / "produksi.py")], check=True)
B, A = AKAR / "branding", AKAR / "virmodock" / "aset"
shutil.copy(B / "virmodock.ico", A / "virmodock.ico")
shutil.copy(B / "virmodock_ikon.svg", A / "virmodock.svg")
im = Image.open(B / "virmodock_ikon.png")
im.resize((512, 512), Image.LANCZOS).save(A / "virmodock_512.png")
im.resize((256, 256), Image.LANCZOS).save(A / "virmodock_256.png")
shutil.copy(B / "virmodock_logo_horizontal_tanpa_tagline.svg", A / "logo_horizontal.svg")
shutil.copy(B / "virmodock_logo_horizontal_tanpa_tagline_putih.svg", A / "logo_horizontal_putih.svg")
subprocess.run([sys.executable, str(AKAR / "build_tools" / "logo" / "installer_gambar.py")], check=True)
print("ikon, logo aplikasi & gambar installer diperbarui dari branding/")
