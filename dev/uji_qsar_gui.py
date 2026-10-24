#!/usr/bin/env python3
"""Uji GUI wizard QSAR dari luar: tekan tombol seperti pengguna, dan pastikan jendela tidak pernah membeku.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_qsar_gui.py [terang|gelap]

Responsivitas diukur dengan QTimer 50 ms: bila thread GUI terblokir, jarak antar-detak melonjak. Ambang 1,5 detik.
Keluaran: dev/uji/lanjut/qsar_<langkah>_<tema>.png
"""
import sys
import time
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from virmolab.core import qsar  # noqa: E402
from virmolab.ui import theme  # noqa: E402
from virmolab.ui.dialog_qsar import DialogQSAR  # noqa: E402

TEMA = sys.argv[1] if len(sys.argv) > 1 else "terang"
KELUAR = AKAR / "dev" / "uji" / "lanjut"
KELUAR.mkdir(parents=True, exist_ok=True)
DATA = AKAR / "dev" / "data" / "qsar_ache.csv"
AMBANG_BEKU = 1.5          # detik; lebih lama dari ini berarti thread GUI terblokir

app = QApplication([])
app.setPalette(theme.palet(TEMA))
app.setStyleSheet(theme.qss(TEMA))
d = DialogQSAR(None, proyek=None)
d.resize(1250, 820)
d.show()

galat = []
jeda_maks = [0.0, time.perf_counter()]


def detak():
    t = time.perf_counter()
    jeda_maks[0] = max(jeda_maks[0], t - jeda_maks[1])
    jeda_maks[1] = t


nadi = QTimer()
nadi.timeout.connect(detak)
nadi.start(50)


def simpan(nama):
    app.processEvents()      # biarkan tata letak dan gambar ulang grafik selesai sebelum tangkapan layar
    d.grab().save(str(KELUAR / f"qsar_{nama}_{TEMA}.png"))
    svg = getattr(d, "svg_validasi", None)
    if svg is not None and not svg.kosong() and svg.width() > 0:
        r = svg._renderer.defaultSize()
        if r.width() and abs(r.width() / max(1, r.height()) - svg.width() / max(1, svg.height())) > 0.08:
            galat.append(f"grafik {nama}: rasio SVG {r.width()}×{r.height()} tidak sepadan dengan panel "
                         f"{svg.width()}×{svg.height()}")


def tunggu(syarat, langkah_berikut, batas=600, mulai=None):
    """Panggil langkah_berikut setelah syarat() benar, tanpa memblokir loop peristiwa."""
    mulai = mulai or time.perf_counter()
    if syarat():
        langkah_berikut()
        return
    if time.perf_counter() - mulai > batas:
        galat.append(f"waktu habis menunggu: {langkah_berikut.__name__}")
        app.quit()
        return
    QTimer.singleShot(200, lambda: tunggu(syarat, langkah_berikut, batas, mulai))


def langkah_data():
    d.baris_mentah = qsar.muat_csv(DATA)
    d.sumber_data = DATA.name
    d._tampil_data()
    simpan("1data")
    print("data:", d.l_kartu.text())
    d.b_maju.click()                       # -> kurasi (asinkron)
    tunggu(lambda: bool(d.data), langkah_kurasi)


def langkah_kurasi():
    simpan("2kurasi")
    print("kurasi:", d.l_kurasi.text())
    d.b_maju.click()                       # -> model
    d.chk_yacak.setChecked(False)          # Y-randomization 50x dilewati agar uji cepat
    simpan("3model")
    d.b_latih.click()
    tunggu(lambda: bool(d.model), langkah_validasi)


def langkah_validasi():
    print("metrik acak    :", {k: round(v, 3) for k, v in d.model_lain["acak"]["eksternal"].items()})
    print("metrik kerangka:", {k: round(v, 3) for k, v in d.model_lain["kerangka"]["eksternal"].items()})
    print("peringatan     :", (d.l_peringatan_val.text()[:120] or "(tidak ada)"))
    d.b_maju.click()                       # -> validasi
    simpan("4validasi")
    d.cb_grafik.setCurrentIndex(1)         # Williams
    d.cb_grafik.setCurrentIndex(3)         # kepentingan fitur (asinkron)
    tunggu(lambda: d._penting is not None, langkah_prediksi)


def langkah_prediksi():
    print("kepentingan fitur:", len(d._penting), "fitur positif")
    simpan("4validasi_fitur")
    d.cb_grafik.setCurrentIndex(0)
    d.b_maju.click()                       # -> prediksi
    # tanpa proyek, ligan diambil dari set data sendiri + satu senyawa asing
    d._ligan_prediksi = [{"nama": f"ligan {i + 1}", "smiles": x["smiles"]} for i, x in enumerate(d.data[:8])]
    d._ligan_prediksi.append({"nama": "alkana asing", "smiles": "CCCCCCCCCCCCCCCCCCCC"})
    d._mulai_sibuk("uji prediksi")
    from virmolab.ui import kerja
    model, smiles = d.model, [lg["smiles"] for lg in d._ligan_prediksi]
    kerja.jalankan(lambda lapor=None: qsar.prediksi(model, smiles),
                   selesai=d._prediksi_selesai, galat=lambda e: galat.append(str(e)))
    tunggu(lambda: bool(d.prediksi) or galat, selesai_semua)


def selesai_semua():
    simpan("5prediksi")
    if d.prediksi:
        print("prediksi:", len(d.prediksi), "senyawa; alkana asing di luar domain:",
              not d.prediksi[-1]["dalam_domain"])
        if d.prediksi[-1]["dalam_domain"]:
            galat.append("alkana asing seharusnya ditandai di luar domain")
        if d.l_domain.isVisibleTo(d):
            galat.append("8/9 di dalam domain: peringatan domain seharusnya tersembunyi")
        bawah = d.tabel_prediksi.item(d.tabel_prediksi.rowCount() - 1, 0).text()
        if bawah != "alkana asing":
            galat.append(f"senyawa di luar domain seharusnya di baris terbawah, didapat {bawah}")
    langkah_asing()


def langkah_asing():
    """Seri bahan alam yang asing bagi model AChE (kasus Artikel 4): peringatan 'tidak cocok' harus muncul."""
    from virmolab.ui import kerja
    asing = [b.split("	")[1] for b in (Path(__file__).resolve().parent / "data" / "glikosida_pubchem.tsv")
             .read_text(encoding="utf-8").splitlines() if b and not b.startswith("#")][:10]
    d.prediksi = []
    d._ligan_prediksi = [{"nama": f"bahan alam {i + 1}", "smiles": s} for i, s in enumerate(asing)]
    d._ligan_prediksi.append({"nama": "ligan latih", "smiles": d.data[0]["smiles"]})
    d._mulai_sibuk("uji prediksi seri asing")
    model, smiles = d.model, [lg["smiles"] for lg in d._ligan_prediksi]
    kerja.jalankan(lambda lapor=None: qsar.prediksi(model, smiles),
                   selesai=d._prediksi_selesai, galat=lambda e: galat.append(str(e)))
    tunggu(lambda: bool(d.prediksi) or galat, selesai_asing)


def selesai_asing():
    for _ in range(10):
        app.processEvents()
    simpan("5prediksi_asing")
    rd = qsar.ringkas_domain(d.prediksi)
    print(f"seri asing: {rd['n_dalam']}/{rd['n']} di dalam domain, tingkat {rd['tingkat']}; peringatan:",
          d.l_domain.text()[:160])
    if rd["tingkat"] != "tidak_cocok":
        galat.append(f"seri bahan alam seharusnya tidak_cocok, didapat {rd['tingkat']}")
    if not d.l_domain.isVisibleTo(d) or "tidak cocok" not in d.l_domain.text():
        galat.append("peringatan 'tidak cocok' tidak tampil")
    if d.tabel_prediksi.item(0, 0).text() != "ligan latih":
        galat.append("senyawa di dalam domain seharusnya di baris teratas, didapat "
                     + d.tabel_prediksi.item(0, 0).text())
    luar = [float(d.tabel_prediksi.item(r, 1).text().replace(",", ".")) for r in range(1, d.tabel_prediksi.rowCount())]
    if luar != sorted(luar, reverse=True):
        galat.append(f"senyawa di luar domain seharusnya urut prediksi menurun, didapat {luar}")
    if d.l_domain.height() + 2 < d.l_domain.heightForWidth(d.l_domain.width()):
        galat.append("label peringatan domain terpotong")
    teks = qsar.susun_paragraf_metode(d.model, d.data, d.sumber_data, d.y_acak or None)
    print("paragraf:", teks[:130], "…")
    print(f"jeda GUI terlama: {jeda_maks[0]:.2f} s")
    if jeda_maks[0] > AMBANG_BEKU:
        galat.append(f"jendela membeku {jeda_maks[0]:.1f} s (ambang {AMBANG_BEKU} s)")
    app.quit()


QTimer.singleShot(100, langkah_data)
QTimer.singleShot(900000, app.quit)
app.exec()
print("GAGAL" if galat else "OK", *galat)
sys.exit(1 if galat else 0)
