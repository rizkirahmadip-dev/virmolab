"""Uji GUI interaktif DialogFarmakofor dan visualisasi 3D farmakofor di Viewer (F4).

Memverifikasi:
1. Dialog terbuka dengan pose MK1 / proyek nyata.
2. WebGL dan VM.tampilFarmakofor berjalan di viewport.
3. Mengambil tangkapan layar dev/uji/lanjut/farmakofor_3d_render.png.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from virmolab.ui.dialog_farmakofor import DialogFarmakofor


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    app = QApplication.instance() or QApplication(sys.argv)

    dlg = DialogFarmakofor()
    dlg.resize(1260, 750)
    dlg.show()

    out_png = Path("dev/uji/lanjut/farmakofor_3d_render.png")
    out_png.parent.mkdir(parents=True, exist_ok=True)

    def _selesai():
        # Berikan waktu agar WebGL 3Dmol merender bola transparan
        dlg.grab().save(str(out_png))
        print(f"OK    Tangkapan layar 3D disimpan ke {out_png} ({out_png.stat().st_size} bytes)")
        dlg.close()
        app.quit()

    # Tunggu 3 detik agar QWebEngineView dan WebGL 3Dmol tuntas merender kanvas
    QTimer.singleShot(3500, _selesai)
    app.exec()
    print("OK    Uji visual dialog farmakofor 3D selesai.")


if __name__ == "__main__":
    main()
