"""Titik masuk VirmoLab-cli.exe (konsol) untuk PyInstaller — lihat virmolab/cli.py."""
import multiprocessing
import sys

from virmolab.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()  # pekerja ProcessPoolExecutor di build beku
    sys.exit(main())
