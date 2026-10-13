#!/usr/bin/env python3
"""Uji kolom 'pIC50 prediksi' di panel Hasil: nilai, interval, penanda luar domain, dan baris tanpa prediksi."""
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from virmolab.ui import panel_hasil  # noqa: E402


def cek(k, pesan):
    if not k:
        print(f"GAGAL: {pesan}")
        sys.exit(1)
    print(f"OK: {pesan}")


app = QApplication([])
p = panel_hasil.PanelHasil()
baris = [{"peringkat": i + 1, "ligan": nama, "energi": -8.0 + i, "ki": "", "le": 0.3, "klaster": 1,
          "rmsd_kristal": None, "rmsd": None, "hbond": 2, "hidrofobik": 1, "pi": 0, "pikation": 0, "garam": 0,
          "halogen": 0, "logam": 0, "mesin": "vina", "job": "J1", "lid": f"L{i}", "ifp_sim": None, "mmgbsa": None,
          "gnina": None, "cnnscore": None, "cnnaffinity": None, "syarat_jarak": None, "qc": None, "kovalen": False,
          "pose": []}
         for i, nama in enumerate(["ligan A", "ligan B", "ligan C"])]
p.muat(baris)
cek(p.pohon.topLevelItemCount() == 3, "tiga baris hasil dimuat")

p.set_qsar({
    "ligan A": {"pic50": 7.25, "bawah": 6.25, "atas": 8.25, "dalam_domain": True, "tanimoto": 0.8},
    "ligan B": {"pic50": 5.5, "bawah": 4.0, "atas": 7.0, "dalam_domain": False, "tanimoto": 0.2},
})
teks = {p.pohon.topLevelItem(i).text(1): p.pohon.topLevelItem(i).text(panel_hasil.K_QSAR) for i in range(3)}
cek("7,25" in teks["ligan A"] and "± 1,00" in teks["ligan A"], f"nilai dan setengah lebar interval: {teks['ligan A']!r}")
cek(teks["ligan B"].startswith("⚠"), f"senyawa di luar domain diberi tanda: {teks['ligan B']!r}")
cek(teks["ligan C"] == "", "ligan tanpa prediksi dibiarkan kosong, bukan diisi angka")
tip = {p.pohon.topLevelItem(i).text(1): p.pohon.topLevelItem(i).toolTip(panel_hasil.K_QSAR) for i in range(3)}
cek("luar domain" in tip["ligan B"] and "0,20" in tip["ligan B"], "tooltip menjelaskan domain dan kemiripan")
cek(p.pohon.topLevelItem(0).data(panel_hasil.K_QSAR, Qt.UserRole) == 7.25, "nilai numerik tersimpan untuk pengurutan")

p.set_qsar({"ligan A": {"kelas": 1, "peluang_aktif": 0.82, "dalam_domain": True, "tanimoto": 0.9}}, klasifikasi=True)
t = p.pohon.topLevelItem(0).text(panel_hasil.K_QSAR)
cek("aktif" in t and "0,82" in t, f"mode klasifikasi menampilkan kelas dan peluang: {t!r}")

p.muat(baris)      # muat ulang: prediksi harus tetap menempel pada ligan yang sama
cek(p.pohon.topLevelItem(0).text(panel_hasil.K_QSAR).startswith("aktif"), "prediksi bertahan setelah tabel dimuat ulang")
print("SEMUA UJI LULUS")
