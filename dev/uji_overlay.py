import sys
from pathlib import Path
from PySide6.QtCore import QSettings, QTimer
sys.argv = [sys.argv[0]]
QSettings("VirmoLab", "VirmoLab").remove("sesi_terbuka")
import virmolab.app as A
from PySide6.QtWidgets import QApplication, QMessageBox
Path("dev/uji/gambar").mkdir(parents=True, exist_ok=True)  # keluaran gambar uji
QMessageBox.information = staticmethod(lambda *a, **k: None)
# Proyek .vmd terakhir belum tentu memuat job validasi: isi folder kerja bergantung pada uji mana yang
# terakhir berjalan, sehingga memakai [-1] membuat uji ini gagal menurut urutan regresi, bukan menurut
# kode yang diujinya. Pilih proyek terbaru yang benar-benar punya job validasi.
def _proyek_validasi():
    import json
    for p in sorted(Path("dev/uji/kerja").glob("*.vmd"), reverse=True):
        f = p / "proyek.json" if p.is_dir() else p
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        if any(j.get("validasi") for j in d.get("job", [])):
            return p.resolve()
    raise SystemExit("LEWAT: belum ada proyek dengan job validasi di dev/uji/kerja "
                     "(jalankan uji_validasi atau uji_alur lebih dulu)")


P = _proyek_validasi()
def hook():
    from virmolab.ui import mainwindow
    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__(); s.resize(1600, 960)
            QTimer.singleShot(2000, lambda: s.buka_proyek(str(P)))
            QTimer.singleShot(5000, s.a)
        def a(s):
            j = [x for x in s.proyek.job if x.get("validasi")][-1]
            s._hasil_validasi(j)
            for o in s.objek.values():
                if o.tampil and o.jenis in ("pose", "ligan"):
                    print(o.nama, o.grup, o.gaya["warna"], o.gaya["reps"])
            QTimer.singleShot(2500, lambda: (s.grab().save("dev/uji/gambar/overlay.png"), QApplication.quit()))
    mainwindow.JendelaUtama = U
    A.main()
hook()
