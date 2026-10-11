"""Unduh bobot Boltz-2 dan kamus komponen kimia ke ~/.boltz di WSL."""
from pathlib import Path

from boltz.main import download_boltz2

download_boltz2(Path.home() / ".boltz")
print("BOBOT_SELESAI")
