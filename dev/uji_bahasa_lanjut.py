"""Audit mode English untuk dialog fitur 0.9.7+ (F1-F12 dan sesudahnya) pada proyek nyata.

Tiap dialog dibuka dari jendela utama, semua tab (QTabWidget) dan halaman wizard (QStackedWidget) dikunjungi,
lalu teks yang tampil (label, tombol, judul grup, isi combo, judul tab, kepala tabel, placeholder, tooltip)
diperiksa terhadap kata Indonesia umum. Tangkapan tiap halaman disimpan untuk diperiksa mata.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_bahasa_lanjut.py [nama ...]
Keluaran: dev/uji/bahasa_lanjut/<dialog>_<halaman>.png dan sisa.txt. Bahasa dikembalikan ke 'id' di akhir.
"""
import json
import os
import re
import shutil
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QSettings, QTimer

PILIH = sys.argv[1:]
sys.argv = [sys.argv[0]]
st = QSettings("VirmoLab", "VirmoLab")
st.setValue("tema", "terang")
st.setValue("bahasa", "en")
st.remove("layout")
st.remove("sesi_terbuka")
st.setValue("mode_pengguna", "ahli")
st.setValue("wizard_selesai", True)
OUT = Path("dev/uji/bahasa_lanjut").resolve()
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)


def _n_job(d):
    try:
        return len(json.loads((d / "proyek.json").read_text(encoding="utf-8")).get("job", []))
    except Exception:
        return 0


CALON = [c for d in ("dev/uji/kerja", "dev/uji/proj", "dev/uji/kerja_docs") for c in sorted(Path(d).glob("*.vmd"))]
CALON = [c for c in CALON if _n_job(c)]
if not CALON:
    print("LEWAT: belum ada proyek .vmd berisi hasil docking (jalankan dev/siapkan_contoh.py)")
    raise SystemExit(0)
SUMBER = max(CALON, key=_n_job).resolve()
if os.environ.get("VD_PROYEK"):          # audit keadaan tertentu, mis. dev/uji/kerja_al/<proyek>.vmd (kampanye sudah ada)
    SUMBER = Path(os.environ["VD_PROYEK"]).resolve()
PROYEK = OUT / SUMBER.name
shutil.copytree(SUMBER, PROYEK)
st.setValue("folder_kerja", str(OUT))

import virmolab.app as A  # noqa: E402
from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QDialog, QFileDialog,  # noqa: E402
                               QGroupBox, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QStackedWidget,
                               QTableWidget, QTabWidget, QTextEdit, QWidget)

QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
# Dialog modal (exec) dibuat tidak memblok supaya bisa ditangkap lalu ditutup seperti dialog biasa.
QDialog.exec = lambda self, *a: (self.show(), 0)[1]

# Kata fungsi dan kata benda Indonesia yang hampir tidak pernah muncul di teks Inggris.
INDO = re.compile(
    r"\b(dan|yang|untuk|dari|atau|tidak|belum|dengan|pada|ini|itu|bila|jika|akan|sudah|masih|harus|bisa|"
    r"setelah|sebelum|semua|banyak|tiap|setiap|lebih|hanya|juga|agar|supaya|karena|tanpa|antara|oleh|sebagai|"
    r"dalam|atas|bawah|baru|ulang|dulu|ligan|berkas|hasil|kantong|residu|senyawa|obat|uji|langkah|lanjut|"
    r"kembali|tutup|batal|bawaan|otomatis|bukan|terlalu|cukup|tinggi|rendah|besar|kecil|ringan|berat|"
    r"teratas|terbaik|pusat|ukuran|warna|gambar|kolom|baris|nilai|jumlah|rantai|ikatan|simpan|buka|pilih|"
    r"hapus|tampilkan|jalankan|siapkan|salin|ekspor|impor|hitung|cari|tambah|atur|gagal|selesai|berhasil|"
    r"terpasang|kosong|sedang|menunggu|di|ke|sumur|pelat|denah|jalur|kelas|panel|kueri|aktif)\b")
# Nama diri dan istilah yang sama di dua bahasa; tidak dihitung sebagai sisa.
BOLEH = re.compile(r"\b(panel|aktif)\b")


def _kosakata():
    """Kata Indonesia = kata di kunci kamus yang tidak pernah muncul di nilai Inggris mana pun.

    Daftar regex di atas hanya memuat kata umum; detektor ini menangkap istilah seperti 'Kurasi' atau
    'reduktase' yang lolos dari regex. Kata < 5 huruf diabaikan supaya singkatan tidak salah tangkap."""
    d = json.loads(Path("virmolab/i18n/en.json").read_text(encoding="utf-8"))
    kata = lambda s: set(re.findall(r"[A-Za-z]{5,}", re.sub(r"<[^>]+>|\{\d+\}", " ", s).lower()))  # noqa: E731
    en, idn = set(), set()
    for sek in ("teks", "pola"):
        for k, v in d[sek].items():
            en |= kata(v)
            idn |= kata(k)
    return idn - en


KATA_ID = _kosakata()
sisa = []
galat = []


def _tangkap(t, v, tb):
    teks = "".join(traceback.format_exception(t, v, tb))
    print("Traceback (galat GUI):\n" + teks, flush=True)
    galat.append(f"{t.__name__}: {v}")


sys.excepthook = _tangkap

DIALOG = ["admet", "mpo", "labplanner", "penapisan", "mmp", "selektivitas", "interpretasi", "ppi", "kantong", "fbdd",
          "skrip_publikasi", "diagnostik", "terowongan", "kinetika", "protac", "metabolisme", "rescore_ml", "tanaman",
          "validasi_protokol", "target_balik", "qsar", "farmakofor", "peptida", "xtb", "generatif", "rbfe",
          "konsensus", "md", "pembelajaran_aktif", "sunting3d"]
if PILIH:
    DIALOG = [d for d in DIALOG if d in PILIH]


def teks_widget(w):
    out = []
    for x in [w] + w.findChildren(QWidget):
        if not x.isVisible():
            continue
        if isinstance(x, (QLabel, QAbstractButton)):
            out.append(x.text())
        if isinstance(x, QGroupBox):
            out.append(x.title())
        if isinstance(x, QComboBox):
            out += [x.itemText(i) for i in range(x.count())]
        if isinstance(x, QLineEdit):
            out.append(x.placeholderText())
        if isinstance(x, (QTextEdit, QPlainTextEdit)):
            out.append(x.toPlainText()[:4000])
        if isinstance(x, QTabWidget):
            out += [x.tabText(i) for i in range(x.count())]
        if isinstance(x, QTableWidget):
            for c in range(x.columnCount()):
                h = x.horizontalHeaderItem(c)
                if h:
                    out.append(h.text())
                for r in range(min(x.rowCount(), 40)):
                    it = x.item(r, c)
                    if it:
                        out.append(it.text())
        out.append(x.toolTip())
    return out


def periksa(nama, w):
    for t in teks_widget(w):
        if not t:
            continue
        polos = re.sub(r"<[^>]+>", " ", t)
        kena = [k for k in INDO.findall(polos) if not BOLEH.fullmatch(k)]
        kena += [w for w in re.findall(r"[A-Za-z]{5,}", polos) if w.lower() in KATA_ID]
        if kena:
            sisa.append((nama, polos.strip()[:160].replace("\n", " ⏎ ")))


def hook():
    from virmolab.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(600000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def _galat(s, t):
            print("GALAT:", t, flush=True)

        def l1(s):
            s.buka_proyek(str(PROYEK))
            QTimer.singleShot(4000, s.l2)

        def l2(s):
            j = s.proyek.job[0]
            s.buka_pose(j["id"], j["ligan"][0]["id"], 1)
            QTimer.singleShot(3500, s.l3)

        def l3(s):
            # Halaman Uni-Dock di panel docking hanya tampil bila mesinnya dipilih; tanpa ini tidak pernah diperiksa.
            if not PILIH or "panel_unidock" in PILIH:
                s.param.atur_unidock(True)
                s.param.set_parameter({"mesin": "unidock", "perangkat": "gpu"})
                for _ in range(10):
                    QApplication.processEvents()
                periksa("panel docking/Uni-Dock", s.param)
            for nama in DIALOG:
                sebelum = set(QApplication.topLevelWidgets())
                try:
                    getattr(s, "buka_" + nama)()
                except Exception:
                    _tangkap(*sys.exc_info())
                for _ in range(20):
                    QApplication.processEvents()
                baru = [w for w in QApplication.topLevelWidgets() if w not in sebelum and isinstance(w, QDialog)
                        and w.isVisible()]
                if not baru:
                    print(f"  {nama}: dialog tidak muncul", flush=True)
                    continue
                d = baru[0]
                halaman = 0
                d.grab().save(str(OUT / f"{nama}_{halaman}.png"))
                periksa(nama, d)
                for tw in d.findChildren(QTabWidget):
                    for i in range(tw.count()):
                        tw.setCurrentIndex(i)
                        for _ in range(5):
                            QApplication.processEvents()
                        halaman += 1
                        d.grab().save(str(OUT / f"{nama}_{halaman}.png"))
                        periksa(f"{nama}/{tw.tabText(i)}", d)
                for sw in d.findChildren(QStackedWidget):
                    if sw.count() < 2 or isinstance(sw.parent(), QTabWidget):
                        continue
                    for i in range(sw.count()):
                        sw.setCurrentIndex(i)
                        for _ in range(5):
                            QApplication.processEvents()
                        halaman += 1
                        d.grab().save(str(OUT / f"{nama}_{halaman}.png"))
                        periksa(f"{nama}/halaman {i + 1}", d)
                print(f"  {nama}: {d.windowTitle()} ({halaman + 1} tangkapan)", flush=True)
                d.close()
                QApplication.processEvents()
            unik = sorted(set(sisa))
            (OUT / "sisa.txt").write_text("\n".join(f"{n} | {t}" for n, t in unik), encoding="utf-8")
            for n, t in unik[:200]:
                print("  ID:", n, "|", t, flush=True)
            print("jumlah teks Indonesia tersisa:", len(unik), "· galat:", len(galat), flush=True)
            QApplication.quit()

    mainwindow.JendelaUtama = Uji


# Modul UI baru boleh diimpor SESUDAH lapisan terjemahan terpasang, sama seperti app.main(); kalau tidak,
# kit.py memegang QTableWidgetItem asli dan sel tabel tampak tak diterjemahkan padahal di aplikasi diterjemahkan.
from virmolab import i18n  # noqa: E402
_pasang_asli = i18n.pasang


def _pasang_lalu_hook(app):
    _pasang_asli(app)
    hook()


i18n.pasang = _pasang_lalu_hook
try:
    A.main()
except SystemExit:
    pass
finally:
    QSettings("VirmoLab", "VirmoLab").setValue("bahasa", "id")
