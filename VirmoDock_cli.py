"""Titik masuk VirmoDock-cli.exe (konsol) untuk PyInstaller — lihat virmodock/cli.py."""
import sys

from virmodock.cli import main

if __name__ == "__main__":
    sys.exit(main())
