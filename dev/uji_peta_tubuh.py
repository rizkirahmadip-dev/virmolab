"""Uji peta tubuh ADMET: penilaian per organ, widget, animasi, dan ekspor gambar.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_peta_tubuh.py
Keluaran: dev/uji/peta_tubuh/ (peta_terang.png, peta_gelap.png, peta.svg)
"""
import shutil
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))
sys.argv = [sys.argv[0]]

from virmolab.core import peta_tubuh as PT

OUT = AKAR / "dev" / "uji" / "peta_tubuh"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


# ---------------------------------------------------------------- inti: penilaian organ
AMAN = {"BBB_Martins": 0.2, "hERG": 0.05, "DILI": 0.05, "Clearance_Hepatocyte_AZ": 12.0, "Half_Life_Obach": 6.0,
        "CYP3A4_Veith": 0.05, "CYP2D6_Veith": 0.05, "CYP2C9_Veith": 0.05, "CYP1A2_Veith": 0.05,
        "CYP2C19_Veith": 0.05, "HIA_Hou": 0.97, "Bioavailability_Ma": 0.9, "Caco2_Wang": -4.8,
        "PAMPA_NCATS": 0.9, "Solubility_AqSolDB": -2.2, "Pgp_Broccatelli": 0.1,
        "Clearance_Microsome_AZ": 6.0, "VDss_Lombardo": 0.6, "PPBR_AZ": 86.0, "Skin_Reaction": 0.05,
        "AMES": 0.05, "Carcinogens_Lagunin": 0.05, "SR-p53": 0.05, "NR-AhR": 0.05, "LD50_Zhu": 3.4,
        "ClinTox": 0.05, "Lipophilicity_AstraZeneca": 2.2}
BAHAYA = dict(AMAN, hERG=0.95, DILI=0.93, AMES=0.9, LD50_Zhu=1.6, ClinTox=0.88, Skin_Reaction=0.85)

aman = PT.nilai_organ(AMAN)
bahaya = PT.nilai_organ(BAHAYA)
pk = {o["kunci"]: o for o in aman}
pb = {o["kunci"]: o for o in bahaya}

cek(len(aman) == len(PT.ORGAN), f"{len(aman)} organ dinilai")
cek(all(o["skor"] is not None for o in aman if o["kunci"] != "otak"),
    "semua organ berendpoint menilai punya skor")
cek(pk["otak"]["info"] is not None, f"otak menampilkan nilai BBB sebagai informasi ({pk['otak']['info']})")
cek(pk["jantung"]["status"] == "baik" and pb["jantung"]["status"] == "risiko",
    f"jantung: aman={pk['jantung']['skor']} vs hERG tinggi={pb['jantung']['skor']}")
cek(pb["hati"]["skor"] < pk["hati"]["skor"], f"hati memburuk saat DILI tinggi ({pb['hati']['skor']})")
cek(pb["sel"]["status"] == "risiko", f"inti sel berisiko saat Ames tinggi ({pb['sel']['skor']})")
cek(pk["cerna"]["skor"] >= 70, f"saluran cerna baik untuk ligan terserap ({pk['cerna']['skor']})")

# endpoint netral (BBB, substrat CYP) tidak boleh ikut menilai baik/buruk
otak = pk["otak"]
cek(all(e["netral"] for e in otak["endpoint"]) and otak["skor"] is None,
    "BBB bersifat netral: otak tidak diberi nilai baik/buruk")

# satu endpoint sangat buruk tidak tersamarkan rata-rata
cek(pb["sistemik"]["skor"] <= 100 * min(e["skor"] for e in pb["sistemik"]["endpoint"] if e["skor"] is not None) + 20.1,
    f"skor organ dibatasi endpoint terburuk ({pb['sistemik']['skor']})")

kosong = PT.nilai_organ({})
cek(all(o["skor"] is None for o in kosong), "tanpa prediksi: semua organ kosong, bukan nol")
cek("Belum ada prediksi" in PT.ringkas(kosong), "ringkasan kosong jujur")
cek("jantung" in PT.ringkas(bahaya).lower() or "inti sel" in PT.ringkas(bahaya).lower(),
    f"ringkasan menunjuk organ berisiko: {PT.ringkas(bahaya)}")
cek(3.0 <= PT.waktu_alur(AMAN) <= 12.0, f"durasi animasi dari waktu paruh = {PT.waktu_alur(AMAN):.1f} detik")

# ---------------------------------------------------------------- widget
from PySide6.QtWidgets import QApplication

from virmolab.ui import theme
from virmolab.ui.peta_tubuh import PetaTubuh

app = QApplication.instance() or QApplication(sys.argv)
for mode in ("terang", "gelap"):
    app.setPalette(theme.palet(mode))
    app.setStyleSheet("")
    w = PetaTubuh()
    w.resize(640, 820)
    w.muat(BAHAYA if mode == "terang" else AMAN, "uji")
    w.show()
    app.processEvents()
    w._anim.stop()                # hentikan dulu, lalu paksa ke keadaan akhir
    w._langkah_anim(1.0)          # selesaikan animasi peralihan warna
    app.processEvents()
    warna_organ = {o["kunci"]: w._warna(o).name() for o in w.organ}
    cek(len({v for k, v in warna_organ.items() if k != "otak"}) >= 1 and
        all(v.lower() not in ("#2d333d", "#d3d9e1") for k, v in warna_organ.items() if k != "otak"),
        f"warna organ bukan abu-abu kosong ({mode}): {sorted(set(warna_organ.values()))}")
    berkas = OUT / f"peta_{mode}.png"
    cek(w.simpan_png(berkas) and berkas.exists() and berkas.stat().st_size > 5000,
        f"ekspor PNG {mode}: {berkas.stat().st_size if berkas.exists() else 0} B")
    w.grab().save(str(OUT / f"layar_{mode}.png"))
    if mode == "terang":
        # klik tepat di tengah organ jantung harus memilih organ itu
        from PySide6.QtCore import QPointF
        dipilih = []
        w.organDipilih.connect(dipilih.append)
        k, dx, dy = w._skala()
        pusat = w._kotak("jantung").center()
        titik = QPointF(pusat.x() * k + dx, pusat.y() * k + dy)
        cek(w._organ_di(titik) == "jantung", "klik di tengah kartu jantung mengenai kartu jantung")
        kotak = [w._kotak(x) for x in ("cerna", "jantung", "hati", "ginjal")]
        cek(all(a.right() < b2.left() for a, b2 in zip(kotak, kotak[1:])),
            "kartu baris perjalanan obat berurutan tanpa tumpang tindih")
        cek(w._kotak("cerna").bottom() < w._kotak("otak").top(), "baris kedua di bawah baris pertama")
        w.pilih("hati")
        cek(dipilih and dipilih[-1] == "hati", "sinyal organDipilih terkirim")
        svg = OUT / "peta.svg"
        cek(w.simpan_svg(svg) and svg.exists() and svg.stat().st_size > 2000,
            f"ekspor SVG: {svg.stat().st_size if svg.exists() else 0} B")
        w.atur_alur(False)
        app.processEvents()
        cek(not w._alur_hidup, "animasi perjalanan obat bisa dimatikan")
    w.close()

# ---------------------------------------------------------------- animasi
w = PetaTubuh()
w.resize(900, 580)
w.muat(BAHAYA, "uji animasi")
app.processEvents()
cek(w._masuk < 1.0, f"kartu mulai dari keadaan masuk ({w._masuk:.2f})")
alur_awal = w._alur
for _ in range(12):
    w._detak()
cek(w._masuk > 0.3, f"animasi masuk berjalan ({w._masuk:.2f})")
cek(w._alur != alur_awal, "partikel aliran bergerak")
w.pilih("hati")
cek(w._riak is not None and w._riak[0] == "hati", "riak muncul saat kartu dipilih")
for _ in range(20):
    w._detak()
cek(w._riak is None, "riak berhenti sendiri setelah menyebar")
w._hover = "ginjal"
w._hover_t.setdefault("ginjal", 0.0)
for _ in range(8):
    w._detak()
cek(w._hover_t.get("ginjal", 0) > 0.5, f"efek sorot naik halus ({w._hover_t.get('ginjal', 0):.2f})")
w.atur_alur(False)
diam = (w._masuk, w._riak, w._denyut_sisa, dict(w._hover_t))
for _ in range(5):
    w._detak()
cek(not w._t.isActive(), "pengatur waktu berhenti saat animasi dimatikan (hemat daya)")
cek(diam == (1.0, None, 0.0, {}), "mematikan animasi langsung menyelesaikan semua gerak")
bingkai = OUT / "animasi"
bingkai.mkdir(exist_ok=True)
w.atur_alur(True)
w.muat(BAHAYA, "uji animasi")
for i in range(4):
    for _ in range(4):
        w._detak()
    app.processEvents()
    w.grab().save(str(bingkai / f"bingkai_{i}.png"))
cek(len(list(bingkai.glob("*.png"))) == 4, "empat bingkai animasi tersimpan untuk ditinjau")
w.close()

print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
sys.exit(1 if gagal else 0)
