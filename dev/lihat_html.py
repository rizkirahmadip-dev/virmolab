"""Tangkap tampilan berkas HTML (mis. laporan interaktif) dengan QtWebEngine.
  .venv/Scripts/python.exe dev/lihat_html.py BERKAS.html KELUAR.png [js-sebelum-tangkap]
"""
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv[:1] + ["--ignore-gpu-blocklist"])
v = QWebEngineView()
v.resize(1500, 950)
v.show()
v.page().javaScriptConsoleMessage = lambda *a: print("js:", a[1], flush=True)
v.load(QUrl.fromLocalFile(str(Path(sys.argv[1]).resolve())))
js = sys.argv[3] if len(sys.argv) > 3 else ""
QTimer.singleShot(5000, lambda: v.page().runJavaScript(js) if js else None)
QTimer.singleShot(8000, lambda: (v.grab().save(sys.argv[2]), app.quit()))
app.exec()
