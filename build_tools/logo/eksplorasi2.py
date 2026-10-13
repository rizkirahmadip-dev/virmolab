import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from buat_logo import NAVY, BIRU, BIRU_MUDA, lockup_svg, tanda_svg
from eksplorasi import lembar
item = []
for lab, geo in (("K1 g.16 t.62 atas1.3", {}), ("K2 t.80", {"t": 0.80}), ("K3 t.50", {"t": 0.50}),
                 ("K4 g.24", {"g": 0.24}), ("K5 atas1.0", {"atas": 1.0}), ("K6 atas1.7", {"atas": 1.7}),
                 ("K7 ujung datar", {"ujung": 0.25}), ("K8 t.70 atas1.15", {"t": 0.70, "atas": 1.15})):
    s, _ = tanda_svg(ukuran=300, **geo)
    item.append((lab, s, None))
s, _ = tanda_svg(warna_v="#ffffff", warna_h=BIRU_MUDA, ukuran=300, latar=NAVY, rx=64, pad=0.2)
item.append(("ikon gelap", s, None))
s, _ = tanda_svg(warna_v=NAVY, warna_h=NAVY, ukuran=300)
item.append(("mono", s, None))
lembar(item, 5, 300, 300, "eksplorasi_kantong.png")
wm = [("Bahnschrift 600", lockup_svg({"keluarga": "Bahnschrift", "berat": 600})),
      ("Bahnschrift 300/600", lockup_svg({"keluarga": "Bahnschrift", "potong": [("Virmo", 300), ("Dock", 600)]})),
      ("BAHNSCHRIFT KAPITAL 500 +tagline", lockup_svg({"keluarga": "Bahnschrift", "berat": 500, "spasi": 0.08,
                                              "potong": [("VIRMOLAB", 500)]}, tagline="MOLECULAR DOCKING")),
      ("Bahnschrift 600 + tagline", lockup_svg({"keluarga": "Bahnschrift", "berat": 600},
                                               tagline="MOLECULAR DOCKING"))]
lembar([(a, b, None) for a, b in wm], 2, 760, 240, "eksplorasi_lockup.png")
