"""Uji antarmuka bahasa Inggris: bahasa=en, buka proyek docs, tangkap jendela utama, menu, tab, dan dialog;
cetak teks UI yang masih berbahasa Indonesia (kata kunci umum). Bahasa dikembalikan ke 'id' di akhir.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_bahasa.py
Keluaran: dev/uji/bahasa/*.png
"""
import re
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

SUMBER = Path(str(sorted(Path("dev/uji/kerja_docs").glob("*.vmd"))[-1])).resolve()
sys.argv = [sys.argv[0]]
KERJA = Path("dev/uji/bahasa").resolve()
shutil.rmtree(KERJA, ignore_errors=True)
shutil.copytree(SUMBER, KERJA / SUMBER.name)
st = QSettings("VirmoDock", "VirmoDock")
for k in ("sesi_terbuka", "proyek_terakhir", "layout_v2"):
    st.remove(k)
st.setValue("wizard_selesai", True)
st.setValue("bahasa", sys.argv[1] if len(sys.argv) > 1 else "en")

import virmodock.app as A
from virmodock import i18n
from PySide6.QtWidgets import QApplication, QMessageBox

QMessageBox.information = staticmethod(lambda *a, **k: None)
INDO = re.compile(r"\b(dan|yang|untuk|dari|atau|tidak|belum|dengan|pada|Simpan|Buka|Tampilkan|Siapkan|Jalankan|"
                  r"Pilih|Hapus|Ligan|Langkah|Berkas|Analisis|Alat|Bantuan|Hasil|Sifat|Statistik|Uji|Grafik)\b")
sisa = set()

asli = i18n.pasang


def pasang(app):
    asli(app)
    from virmodock.ui import mainwindow

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(1500, 920)
            s._galat = lambda t: print("GALAT", t, flush=True)
            QTimer.singleShot(2500, s.l1)
            QTimer.singleShot(120000, lambda: (print("TIMEOUT"), QApplication.quit()))

        def l1(s):
            s.buka_proyek(str(KERJA / SUMBER.name))
            QTimer.singleShot(4000, s.l2)

        def periksa(s, w, nama):
            from PySide6.QtWidgets import QAbstractButton, QComboBox, QGroupBox, QLabel, QWidget
            for x in [w] + w.findChildren(QWidget):
                teks = []
                if isinstance(x, (QLabel, QAbstractButton)):
                    teks.append(x.text())
                if isinstance(x, QGroupBox):
                    teks.append(x.title())
                if isinstance(x, QComboBox):
                    teks += [x.itemText(i) for i in range(x.count())]
                teks.append(x.toolTip())
                for tt in teks:
                    if tt and INDO.search(re.sub("<[^>]+>", " ", tt)):
                        sisa.add((nama, tt[:90]))

        def l2(s):
            s.grab().save(str(KERJA / "utama.png"))
            s.periksa(s, "utama")
            for a in s.menuBar().actions():
                m = a.menu()
                for x in m.actions():
                    if x.text() and INDO.search(x.text()):
                        sisa.add(("menu " + a.text(), x.text()))
            print("menu:", [a.text() for a in s.menuBar().actions()], flush=True)
            s.atur_ruang("analisis")
            for w, n in ((s.hasil, "hasil"), (s.statistik, "statistik"), (s.sifat, "sifat"), (s.uji, "uji")):
                s.tab_tengah.setCurrentWidget(w)
                QApplication.processEvents()
                s.grab().save(str(KERJA / f"tab_{n}.png"))
                s.periksa(w, "tab " + n)
            from virmodock.ui.dialog_reseptor import DialogReseptor
            prot = [o for o in s.objek.values() if o.jenis == "protein"]
            d = DialogReseptor(prot, {}, s, teks_sumber=s._teks_sumber_reseptor)
            d.show()
            for i in range(4):
                d.l_langkah.setCurrentRow(i)
                QApplication.processEvents()
                d.grab().save(str(KERJA / f"reseptor_{i + 1}.png"))
                s.periksa(d, "reseptor")
            d.reject()
            from virmodock.ui.dialog_kemiripan import DialogKemiripan
            d = DialogKemiripan(s)
            d.show()
            QApplication.processEvents()
            d.grab().save(str(KERJA / "kemiripan.png"))
            s.periksa(d, "kemiripan")
            d.close()
            for nama, tt in sorted(sisa)[:80]:
                print("  ID:", nama, "|", tt, flush=True)
            print("jumlah teks Indonesia tersisa:", len(sisa), flush=True)
            QTimer.singleShot(300, QApplication.quit)

    mainwindow.JendelaUtama = U


i18n.pasang = pasang
try:
    A.main()
finally:
    QSettings("VirmoDock", "VirmoDock").setValue("bahasa", "id")
