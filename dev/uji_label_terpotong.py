"""Audit teks terpotong di semua dialog: label berbungkus yang lebih pendek dari teksnya, label/tombol satu baris
yang lebih sempit dari teksnya.

Tiap dialog dibuka dari jendela utama pada proyek nyata, lalu diperiksa pada ukuran bawaan dan ukuran minimumnya,
di setiap tab (QTabWidget) dan halaman wizard (QStackedWidget). Yang diukur:
  - QLabel berbungkus: tinggi < heightForWidth(lebar) - 2 (baris terpotong atas/bawah)
  - QLabel satu baris dan QAbstractButton: lebar < sizeHint().width() - 4 (teks terpotong mendatar)
Label di dalam area gulir (QScrollArea) tetap diperiksa: area gulir tidak memotong label, hanya menggesernya.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_label_terpotong.py [--en] [nama ...]
Keluaran: dev/uji/label_terpotong/<bahasa>.txt dan tangkapan dialog yang bermasalah.
"""
import json
import re
import shutil
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtCore import QSettings, QTimer                       # noqa: E402

BAHASA = "en" if "--en" in sys.argv else "id"
PILIH = [a for a in sys.argv[1:] if not a.startswith("--")]
sys.argv = [sys.argv[0]]
st = QSettings("VirmoLab", "VirmoLab")
st.setValue("tema", "terang")
st.setValue("bahasa", BAHASA)
st.remove("layout")
st.remove("sesi_terbuka")
st.setValue("mode_pengguna", "ahli")
st.setValue("wizard_selesai", True)
OUT = Path("dev/uji/label_terpotong").resolve()
OUT.mkdir(parents=True, exist_ok=True)
KERJA = OUT / f"kerja_{BAHASA}"
shutil.rmtree(KERJA, ignore_errors=True)
KERJA.mkdir()


def _n_job(d):
    try:
        return len(json.loads((d / "proyek.json").read_text(encoding="utf-8")).get("job", []))
    except Exception:                                               # noqa: BLE001
        return 0


CALON = [c for d in ("dev/uji/kerja", "dev/uji/proj", "dev/uji/kerja_docs") for c in sorted(Path(d).glob("*.vmd"))]
CALON = [c for c in CALON if _n_job(c)]
if not CALON:
    print("LEWAT: belum ada proyek .vmd berisi hasil docking (jalankan dev/siapkan_contoh.py)")
    raise SystemExit(0)
SUMBER = max(CALON, key=_n_job).resolve()
PROYEK = KERJA / SUMBER.name
shutil.copytree(SUMBER, PROYEK)
st.setValue("folder_kerja", str(KERJA))

import virmolab.app as A                                            # noqa: E402
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QFileDialog, QLabel,  # noqa: E402
                               QMessageBox, QStackedWidget, QTabWidget, QWidget)

# Kotak pesan dan dialog berkas modal menghentikan audit sampai batas waktu; semuanya dijawab otomatis.
for _n in ("information", "warning", "critical"):
    setattr(QMessageBox, _n, staticmethod(lambda *a, **k: QMessageBox.Ok))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.No)
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: "")
QMessageBox.exec = lambda self, *a, **k: QMessageBox.Ok
# Beberapa dialog dibuka modal (exec), misalnya Konsensus; di audit ditampilkan non-modal agar bisa diukur lalu ditutup.
QDialog.exec = lambda self, *a, **k: (self.show(), 0)[1]
galat, temuan = [], []


def _tangkap(t, v, tb):
    print("Traceback (galat GUI):\n" + "".join(traceback.format_exception(t, v, tb)), flush=True)
    galat.append(f"{t.__name__}: {v}")


sys.excepthook = _tangkap

DIALOG = ["admet", "mpo", "labplanner", "penapisan", "mmp", "selektivitas", "interpretasi", "ppi", "kantong", "fbdd",
          "skrip_publikasi", "diagnostik", "terowongan", "kinetika", "protac", "metabolisme", "rescore_ml", "tanaman",
          "validasi_protokol", "target_balik", "qsar", "farmakofor", "peptida", "xtb", "generatif", "rbfe",
          "konsensus", "md", "pembelajaran_aktif", "sunting3d", "glikosida"]
if PILIH:
    DIALOG = [d for d in DIALOG if d in PILIH]


def _terlihat_sungguh(w, d):
    """Widget tampil dan tidak berada di dalam tab/halaman yang tersembunyi."""
    return w.isVisibleTo(d) and w.width() > 0


def ukur(nama, d, ukuran):
    hasil = []
    for w in d.findChildren(QWidget):
        if not _terlihat_sungguh(w, d):
            continue
        if isinstance(w, QLabel):
            teks = w.text()
            if not teks.strip() or w.pixmap() is not None and not w.pixmap().isNull():
                continue
            polos = re.sub(r"<[^>]+>", "", teks).strip()
            if w.wordWrap():
                perlu = w.heightForWidth(w.width())
                if perlu > 0 and w.height() + 2 < perlu:
                    hasil.append(("label tinggi", w.height(), perlu, polos))
            elif "\n" not in teks and w.width() + 4 < w.sizeHint().width():
                hasil.append(("label lebar", w.width(), w.sizeHint().width(), polos))
        elif isinstance(w, QAbstractButton) and w.text().strip():
            if w.width() + 4 < w.sizeHint().width():
                hasil.append(("tombol lebar", w.width(), w.sizeHint().width(), w.text().strip()))
    for jenis, ada, perlu, teks in hasil:
        temuan.append((nama, ukuran, jenis, ada, perlu, teks[:110].replace("\n", " ")))
    return bool(hasil)


def halaman(d):
    """Generator: kunjungi tiap tab dan halaman wizard, hasilkan labelnya."""
    yield "utama"
    for tw in d.findChildren(QTabWidget):
        if not tw.isVisibleTo(d):
            continue
        for i in range(tw.count()):
            tw.setCurrentIndex(i)
            yield f"tab {tw.tabText(i)}"
    for sw in d.findChildren(QStackedWidget):
        if sw.count() < 2 or isinstance(sw.parent(), QTabWidget) or not sw.isVisibleTo(d):
            continue
        for i in range(sw.count()):
            sw.setCurrentIndex(i)
            yield f"halaman {i + 1}"


def hook():
    from virmolab.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(900000, lambda: (print("TIMEOUT"), QApplication.quit()))

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
            for nama in DIALOG:
                sebelum = set(QApplication.topLevelWidgets())
                try:
                    getattr(s, "buka_" + nama)()
                except Exception:                                   # noqa: BLE001
                    _tangkap(*sys.exc_info())
                for _ in range(20):
                    QApplication.processEvents()
                baru = [w for w in QApplication.topLevelWidgets() if w not in sebelum and isinstance(w, QDialog)
                        and w.isVisible()]
                if not baru:
                    print(f"  {nama}: dialog tidak muncul", flush=True)
                    continue
                d = baru[0]
                bawaan = d.size()
                minimum = d.minimumSize() if d.minimumSize().width() > 0 else d.minimumSizeHint()
                n_awal = len(temuan)
                for label_ukuran, uk in (("bawaan", bawaan), ("minimum", minimum)):
                    d.resize(uk)
                    for hal in halaman(d):
                        for _ in range(6):
                            QApplication.processEvents()
                        teks_uk = f"{label_ukuran} {d.width()}x{d.height()} · {hal}"
                        if ukur(nama, d, teks_uk):
                            aman = re.sub(r"[^\w]+", "_", f"{nama}_{label_ukuran}_{hal}")[:80]
                            d.grab().save(str(OUT / f"{BAHASA}_{aman}.png"))
                print(f"  {nama}: {len(temuan) - n_awal} temuan", flush=True)
                d.close()
                QApplication.processEvents()
            baris = [f"{n} | {u} | {j} | {a} < {p} | {t}" for n, u, j, a, p, t in temuan]
            (OUT / f"{BAHASA}.txt").write_text("\n".join(baris), encoding="utf-8")
            print("\n".join(baris[:300]), flush=True)
            print(f"\nTOTAL {len(temuan)} temuan, {len(galat)} galat ({BAHASA})", flush=True)
            QApplication.quit()

    mainwindow.JendelaUtama = Uji


from virmolab import i18n                                           # noqa: E402
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
