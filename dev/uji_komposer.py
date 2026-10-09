"""Uji Komposer figur: susun panel SVG (grafik Uji & Grafik) + raster PNG, label A/B/C, panel lebar penuh,
ekspor PDF/TIFF lewat jalur JendelaUtama. Tangkapan -> dev/uji/komposer/."""
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from virmodock.core import grafik, komposer as K  # noqa: E402
from virmodock.ui import tab_uji as T  # noqa: E402
from virmodock.ui.dialog_komposer import DialogKomposer  # noqa: E402

OUT = Path(__file__).resolve().parent / "uji" / "komposer"
OUT.mkdir(parents=True, exist_ok=True)
app = QApplication.instance() or QApplication([])
gagal = []


def cek(nama, kondisi, detail=""):
    print(("OK   " if kondisi else "GAGAL") + f" {nama} {detail}")
    if not kondisi:
        gagal.append(nama)


t = T.TabUji()
panel = []
for jenis in ("kolom", "xy", "roc", "kontingensi"):
    t.c_data.setCurrentIndex(t.c_data.findData(jenis))
    t.kosongkan()
    t.isi_contoh()
    s, (w, h) = t.svg(gelap=False)
    panel.append({"nama": jenis, "jenis": "svg", "isi": s, "w": w, "h": h})
# sebar dengan clipPath id="area" dua kali -> id harus unik setelah disusun
sb = grafik.sebar([1, 2, 3, 4], [2, 3, 5, 4], judul="Sebar")
panel.append({"nama": "sebar", "jenis": "svg", "isi": sb, "w": 760, "h": 560})
panel.append({"nama": "sebar2", "jenis": "svg", "isi": sb, "w": 760, "h": 560})
# raster: gradasi 600x300
img = QImage(600, 300, QImage.Format_ARGB32)
img.fill(QColor("#2b6fd6"))
q = QPainter(img)
q.fillRect(0, 0, 300, 300, QColor("#e69f00"))
q.end()
buf = QBuffer()
buf.open(QIODevice.WriteOnly)
img.save(buf, "PNG")
panel.append({"nama": "Struktur 3D", "jenis": "png", "isi": base64.b64encode(bytes(buf.data())).decode(),
              "w": 600, "h": 300, "penuh": True})
s, (W, H) = K.susun(panel, {"kolom": 2, "label": "A", "judul_panel": True})
cek("id unik", s.count('id="p4_area"') == 1 and s.count('id="p5_area"') == 1)
r = QSvgRenderer(QByteArray(s.encode("utf-8")))
cek("SVG valid", r.isValid(), f"{W}x{H}")
out = QImage(1400, int(1400 * H / W), QImage.Format_ARGB32)
out.fill(QColor("white"))
p = QPainter(out)
r.render(p)
p.end()
out.save(str(OUT / "figur.png"))
# piksel raster ikut tergambar (panel terakhir, setengah kiri oranye)
px = out.pixelColor(int(out.width() * 0.25), int(out.height() * 0.93))
cek("raster PNG tergambar", px.red() > 200 and px.blue() < 80, px.name())
cek("label A–G", all(f">{c}</text>" in s for c in "ABCDEFG"))
d = DialogKomposer()
d.muat({"panel": panel, "opsi": {"kolom": 3, "label": "(a)"}})
d.show()
app.processEvents()
d.grab().save(str(OUT / "dialog.png"))
cek("dialog", d.daftar.count() == len(panel) and d.daftar.item(0).text().startswith("(a)"))
d._geser(1)
cek("geser", d.panel[1]["nama"] == "kolom")
print("SEMUA LULUS" if not gagal else f"GAGAL: {gagal}")
sys.exit(1 if gagal else 0)
