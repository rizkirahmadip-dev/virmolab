"""Tutorial PDF: docs/_sumber/tutorial.html -> docs/Tutorial_Docking_VirmoDock.pdf (Chromium Qt WebEngine, A4)."""
import re
import sys
from datetime import date
from pathlib import Path

from PySide6.QtCore import QMarginsF, QUrl
from PySide6.QtGui import QPageLayout, QPageSize
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEnginePage

AKAR = Path(__file__).resolve().parents[1]
versi = re.search(r'__version__ = "([^"]+)"', (AKAR / "virmodock" / "__init__.py").read_text()).group(1)
bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
         "November", "Desember"]
t = date.today()
html = (AKAR / "docs" / "_sumber" / "tutorial.html").read_text(encoding="utf-8")
html = html.replace("{{VERSI}}", versi).replace("{{TANGGAL}}", f"{t.day} {bulan[t.month - 1]} {t.year}")
cetak = AKAR / "docs" / "_sumber" / "_tutorial_cetak.html"
cetak.write_text(html, encoding="utf-8")
keluar = AKAR / "docs" / "Tutorial_Docking_VirmoDock.pdf"

app = QApplication(sys.argv)
hal = QWebEnginePage()


def dimuat(ok):
    if not ok:
        print("gagal memuat"); app.quit(); return
    tata = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(15, 16, 15, 16), QPageLayout.Millimeter)
    hal.printToPdf(str(keluar), tata)


hal.loadFinished.connect(dimuat)
hal.pdfPrintingFinished.connect(lambda f, ok: (print("PDF", f, ok), cetak.unlink(missing_ok=True), app.quit()))
hal.load(QUrl.fromLocalFile(str(cetak)))
app.exec()
