"""Titik masuk VirmoLab-cli.exe (konsol) untuk PyInstaller — lihat virmolab/cli.py."""
import sys

from virmolab.cli import main

if __name__ == "__main__":
    sys.exit(main())
