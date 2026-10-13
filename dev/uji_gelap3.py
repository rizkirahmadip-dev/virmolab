import sys
from pathlib import Path
from PySide6.QtCore import QSettings, QTimer
sys.argv = [sys.argv[0]]
st = QSettings("VirmoLab", "VirmoLab"); st.remove("sesi_terbuka"); st.setValue("tema", "gelap")
import virmolab.app as A
from PySide6.QtWidgets import QApplication
Path("dev/uji/gambar").mkdir(parents=True, exist_ok=True)  # keluaran gambar uji
P = sorted(Path("dev/uji/kerja").glob("*.vmd"))[-1].resolve()
def hook():
    from virmolab.ui import mainwindow
    from virmolab.core import ekspor
    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__(); s.resize(1600, 960)
            QTimer.singleShot(2000, lambda: s.buka_proyek(str(P)))
            QTimer.singleShot(5000, s.a)
        def a(s):
            b = ekspor.baris_hasil(s.proyek)[0]; s.buka_pose(b["job"], b["lid"], 1)
            s.tab_tengah.setCurrentWidget(s.diagram)
            QTimer.singleShot(1500, lambda: (s.grab().save("dev/uji/gambar/gelap_diagram.png"), s.tab_tengah.setCurrentWidget(s.hasil),
                                            QTimer.singleShot(800, lambda: (s.grab().save("dev/uji/gambar/gelap_hasil.png"), QApplication.quit()))))
    mainwindow.JendelaUtama = U
    A.main()
hook()
