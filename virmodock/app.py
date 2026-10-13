"""Titik masuk aplikasi VirmoLab.

Argumen:
  berkas...                 buka struktur (PDB/PDBQT/CIF/SDF/MOL2/SMILES), folder proyek .vmd, atau cadangan .vmdbackup
  --disable-gpu             viewport 3D memakai rendering perangkat lunak (driver grafis bermasalah)
  --uji-mandiri HASIL.json  jalankan uji komponen tanpa jendela, tulis hasil, keluar (kode 0 = semua lulus)
  --qc-pekerja ALAMAT KUNCI (internal) proses pekerja PoseBusters, tersambung lewat named pipe
  --admet MASUK KELUAR      (internal) prediksi ADMET-AI di proses terpisah (JSON masuk/keluar)
  --md TUGAS.json           (internal) MD / MM-GBSA OpenMM di proses terpisah (core/md.py)
"""
import os
import sys


def siapkan_kimia():
    """Senyapkan log RDKit (Open Babel dipanggil sebagai program terpisah, lihat core/obabel.py)."""
    try:
        from rdkit import RDLogger
        RDLogger.DisableLog("rdApp.*")
    except ImportError:
        pass


def main():
    arg = sys.argv[1:]
    if arg[:1] == ["--qc-pekerja"]:      # proses pekerja PoseBusters (core/qc.py), tanpa jendela
        siapkan_kimia()
        from .core import qc
        qc.layani(arg[1], arg[2])
        return
    if arg[:1] == ["--admet"]:           # proses prediksi ADMET-AI (core/admet.py), tanpa jendela
        from .core import admet
        sys.exit(admet.jalankan_cli(arg[1], arg[2]))
    if arg[:1] == ["--md"]:              # proses MD / MM/GBSA OpenMM (core/md.py), tanpa jendela
        siapkan_kimia()
        from .core import md
        sys.exit(md.jalankan_tugas(arg[1]))
    siapkan_kimia()
    if "--uji-mandiri" in arg:
        i = arg.index("--uji-mandiri")
        keluar = arg[i + 1] if i + 1 < len(arg) else "uji_mandiri.json"
        from .core import ujimandiri
        sys.exit(0 if ujimandiri.tulis(keluar) else 1)
    flag = "--ignore-gpu-blocklist"  # WebGL tetap jalan di laptop dengan driver GPU lama
    if "--disable-gpu" in arg:
        flag = "--disable-gpu"
        arg.remove("--disable-gpu")
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", flag)
    from . import __version__
    from .core import catat
    catat.mulai(__version__)
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtWidgets import QApplication

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication([sys.argv[0]] + arg)
    app.setApplicationName("VirmoDock")
    app.setOrganizationName("VirmoDock")
    app.setStyle("Fusion")
    from .core import paths
    ikon = paths.PAKET / "aset" / "virmodock.ico"
    if ikon.exists():
        app.setWindowIcon(QIcon(str(ikon)))
    from . import i18n
    i18n.pasang(app)          # bahasa antarmuka (sebelum modul UI diimpor)
    from .ui.mainwindow import JendelaUtama
    w = JendelaUtama()
    w.showMaximized()
    # buka dari Explorer ("Open with" / asosiasi berkas)
    berkas = [a for a in arg if os.path.exists(a)]
    for a in [a for a in berkas if a.lower().endswith(".vmdbackup")]:
        berkas.remove(a)
        w.impor_cadangan(a)
    for a in [a for a in berkas if os.path.isdir(a) and os.path.exists(os.path.join(a, "proyek.json"))]:
        berkas.remove(a)
        w.buka_proyek(a)
    if berkas:
        w.impor(berkas)
    if os.environ.get("VD_TANGKAP"):  # uji build: simpan gambar jendela VirmoLab sendiri (bukan layar), lalu keluar
        from PySide6.QtCore import QTimer
        QTimer.singleShot(int(os.environ.get("VD_TANGKAP_MS", "15000")),
                          lambda: (w.grab().save(os.environ["VD_TANGKAP"]), w.close(), app.quit()))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
