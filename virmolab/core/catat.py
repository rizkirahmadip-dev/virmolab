"""Log aplikasi ke berkas (rotasi 10 berkas × 1 MB) untuk dilampirkan saat melapor masalah."""
import logging
import platform
import sys
import traceback
from logging.handlers import RotatingFileHandler

from . import paths

log = logging.getLogger("virmolab")
BERKAS = paths.LOG / "virmolab.log"


def mulai(versi=""):
    if log.handlers:
        return
    h = RotatingFileHandler(BERKAS, maxBytes=1_000_000, backupCount=9, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(h)
    log.setLevel(logging.INFO)
    log.info("=" * 60)
    log.info(f"VirmoLab {versi} mulai · Python {platform.python_version()} · {platform.platform()}"
             + (" · portable" if paths.PORTABLE else ""))
    lama = sys.excepthook

    def tangkap(t, v, tb):
        log.error("Galat tak tertangani:\n" + "".join(traceback.format_exception(t, v, tb)))
        lama(t, v, tb)
    sys.excepthook = tangkap


def ekor(n=80):
    try:
        return "\n".join(BERKAS.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
    except OSError:
        return ""
