"""Uji tab Uji & Grafik lanjutan: panel Format (klik elemen), patah sumbu, skala log, ROC, kontingensi,
gaya tersimpan. Tangkapan -> dev/uji/grafik_lanjut/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from virmodock.ui import tab_uji as T  # noqa: E402

OUT = Path(__file__).resolve().parent / "uji" / "grafik_lanjut"
OUT.mkdir(parents=True, exist_ok=True)
app = QApplication.instance() or QApplication([])
gagal = []


def cek(nama, kondisi, detail=""):
    print(("OK   " if kondisi else "GAGAL") + f" {nama} {detail}")
    if not kondisi:
        gagal.append(nama)


t = T.TabUji()
t.resize(1500, 860)
t.show()
app.processEvents()


def foto(nama):
    app.processEvents()
    t.grab().save(str(OUT / f"{nama}.png"))


# 1 kolom + klik elemen
t.isi_contoh()
t.e_judul.setText("Berat kering tanaman")
t.hitung()
foto("01_kolom")
kunci = {d[0] for d in t.kanvas.daerah}
cek("daerah elemen", {"judul", "sumbu_y", "label_y", "sumbu_x", "grup:0", "braket"} <= kunci, str(sorted(kunci)))
k, ox, oy = t.kanvas._geo()
d = next(x for x in t.kanvas.daerah if x[0] == "grup:1")
p = QPointF(ox + (d[1] + d[3]) / 2 * k, oy + (d[2] + d[4]) / 2 * k)
ev = QMouseEvent(QMouseEvent.MouseButtonPress, p, p, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
t.kanvas.mousePressEvent(ev)
cek("klik grup -> panel grup", t.format.c_el.currentData() == "grup" and t.format.c_grup.currentIndex() == 1)
t.format._set_warna_grup("#cc0000")
cek("warna grup tersimpan", t.gaya["warna"].get("1") == "#cc0000")
foto("02_klik_grup")
# patah sumbu + nilai ekstrem
t.isi(["Kontrol", "Dosis rendah", "Dosis tinggi"], [[4, 5, 4.5, 5.2], [5, 6, 5.5, 6.1], [48, 52, 50, 55]], "kolom")
t.gaya.update(patah_dari=8.0, patah_sampai=40.0)
t.hitung()
s, _ = t.svg()
cek("patah sumbu tergambar", s.count("<line") > 10 and t.kanvas.r.isValid())
foto("03_patah_sumbu")
t.gaya.update(patah_dari=None, patah_sampai=None, y_log=True)
t.c_grafik.setCurrentIndex(t.c_grafik.findData("titik"))
t.hitung()
foto("04_log")
t.gaya.update(y_log=False)
# ROC
t.c_data.setCurrentIndex(t.c_data.findData("roc"))
t.kosongkan()
t.isi_contoh()
cek("ROC AUC", t.hasil and 0.8 < t.hasil["auc"] <= 1.0, f"{t.hasil.get('auc'):.3f}")
foto("05_roc")
# kontingensi
t.c_data.setCurrentIndex(t.c_data.findData("kontingensi"))
t.kosongkan()
t.isi_contoh()
cek("kontingensi Fisher", t.hasil and t.hasil.get("nama_uji") == "Uji eksak Fisher" and t.hasil["p"] < 0.05,
    f"p={t.hasil.get('p'):.4f}")
foto("06_kontingensi")
# XY
t.c_data.setCurrentIndex(t.c_data.findData("xy"))
t.kosongkan()
t.isi_contoh()
cek("IC50", t.hasil and 0.5 < t.hasil["ic50"] < 10, f"{t.hasil.get('ic50'):.3f}")
foto("07_xy")
# gaya: preset presentasi
t.c_data.setCurrentIndex(t.c_data.findData("kolom"))
t.kosongkan()
t.isi_contoh()
t.format.c_preset.setCurrentIndex(t.format.c_preset.findText("Presentasi (huruf besar)"))
t.format._terapkan()
cek("preset diterapkan", t.gaya["font"] == 16)
foto("08_preset_presentasi")
# simpan/muat proyek
d = t.ke_dict()
t2 = T.TabUji()
t2.muat(d)
cek("muat ulang gaya", t2.gaya == t.gaya and t2.jenis() == "kolom")
print("SEMUA LULUS" if not gagal else f"GAGAL: {gagal}")
sys.exit(1 if gagal else 0)
