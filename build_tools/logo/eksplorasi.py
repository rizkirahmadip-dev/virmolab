"""Lembar kontak eksplorasi logo (dipakai saat mendesain)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from buat_logo import NAVY, BIRU, BIRU_MUDA, OUT, lockup_svg, render, tanda_svg  # noqa: E402
from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402


def lembar(item, kol, lw, lh, nama):
    baris = (len(item) + kol - 1) // kol
    img = QImage(kol * lw, baris * (lh + 30), QImage.Format_ARGB32)
    img.fill(QColor("#ffffff"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    f = QFont("Segoe UI")
    f.setPixelSize(15)
    p.setFont(f)
    for i, (label, svg, latar) in enumerate(item):
        x, y = (i % kol) * lw, (i // kol) * (lh + 30)
        if latar:
            p.fillRect(x + 8, y + 8, lw - 16, lh - 16, QColor(latar))
        tmp = OUT / "_tmp.png"
        sub = render(svg, lw - 60, tmp)
        if sub.height() > lh - 60:
            sub = sub.scaledToHeight(lh - 60, Qt.SmoothTransformation)
        p.drawImage(x + (lw - sub.width()) // 2, y + (lh - sub.height()) // 2, sub)
        p.setPen(QColor("#7b8698"))
        p.drawText(QRectF(x, y + lh, lw, 26), Qt.AlignCenter, label)
    p.end()
    img.save(str(OUT / nama))
    (OUT / "_tmp.png").unlink(missing_ok=True)


tanda = []
for lab, geo, gaya in (("A t.92 g.30", {}, "isi"), ("B tebal t1.15", {"t": 1.15}, "isi"),
                       ("C tipis t.70", {"t": 0.70}, "isi"), ("D celah .45", {"g": 0.45}, "isi"),
                       ("E lengan tinggi", {"atas": 2.4}, "isi"), ("F lengan pendek", {"atas": 1.5}, "isi"),
                       ("G cincin", {}, "cincin"), ("H biru muda", {}, "isi")):
    s, _ = tanda_svg(warna_h=BIRU_MUDA if lab.startswith("H") else BIRU, gaya=gaya, ukuran=300, **geo)
    tanda.append((lab, s, None))
s, _ = tanda_svg(warna_v="#ffffff", warna_h=BIRU_MUDA, ukuran=300, latar=NAVY, rx=60)
tanda.append(("I ikon (gelap)", s, None))
s, _ = tanda_svg(warna_v="#ffffff", warna_h="#ffffff", ukuran=300, latar="#1f5fbf", rx=60)
tanda.append(("J ikon mono", s, None))
lembar(tanda, 5, 300, 300, "eksplorasi_tanda.png")

wm = []
for lab, d in (("Bahnschrift 600", {"keluarga": "Bahnschrift", "berat": 600}),
               ("Bahnschrift 300/600", {"keluarga": "Bahnschrift", "potong": [("Virmo", 300), ("Dock", 600)]}),
               ("Segoe UI 600", {"keluarga": "Segoe UI", "berat": 600}),
               ("Segoe UI 300/700", {"keluarga": "Segoe UI", "potong": [("Virmo", 300), ("Dock", 700)]}),
               ("Segoe UI Variable Display 600", {"keluarga": "Segoe UI Variable Display", "berat": 600,
                                                  "spasi": -0.01}),
               ("Corbel 700", {"keluarga": "Corbel", "berat": 700}),
               ("Sitka Heading 600", {"keluarga": "Sitka Heading", "berat": 600}),
               ("Georgia 400", {"keluarga": "Georgia", "berat": 400})):
    wm.append((lab, lockup_svg(d), None))
lembar(wm, 2, 760, 220, "eksplorasi_wordmark.png")
print("ok")
