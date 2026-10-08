import sys
from virmodock.app import siapkan_kimia; siapkan_kimia()
from virmodock.core import analisis as A, mesin as M, diagram2d
from PySide6.QtWidgets import QApplication
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtCore import QByteArray
app = QApplication(sys.argv)
rec = A.baca_reseptor(open("dev/uji/1HSG_rec.pdbqt").read())
p = M.baca_hasil("vina", "dev/uji/run/MK1_out.pdbqt")[0]
m = A.pose_mol(open("dev/uji/MK1.pdbqt").read(), p.pdbqt)
I = A.interaksi(rec, m)
for gelap, f in ((False, "dev/diagram_terang"), (True, "dev/diagram_gelap")):
    s = diagram2d.svg(m, I, judul=f"MK1 · pose 1 · {p.energi:.2f} kcal/mol (Vina)", gelap=gelap)
    open(f + ".svg", "w", encoding="utf-8").write(s)
    r = QSvgRenderer(QByteArray(s.encode()))
    print("valid", r.isValid())
    img = QImage(1920, 1440, QImage.Format_ARGB32); img.fill(QColor(0, 0, 0, 0))
    pt = QPainter(img); pt.setRenderHint(QPainter.Antialiasing); r.render(pt); pt.end(); img.save(f + ".png")
