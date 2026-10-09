import sys
from pathlib import Path
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
Path("dev/uji/gambar").mkdir(parents=True, exist_ok=True)  # keluaran gambar uji
app = QApplication(sys.argv)
v = QWebEngineView(); v.resize(1100, 1300); v.show()
hal = sys.argv[1:] or ["panduan"]
def muat(i=0):
    if i >= len(hal): app.quit(); return
    v.load(QUrl.fromLocalFile(str(Path(f"docs/{hal[i]}.html").resolve())))
    QTimer.singleShot(2500, lambda: (v.grab().save(f"dev/uji/gambar/doc_{hal[i]}.png"), muat(i + 1)))
muat()
app.exec()
