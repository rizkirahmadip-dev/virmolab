"""Uji GUI interaktif DialogLabPlanner tab Hipotesis (F12).

Memverifikasi:
1. DialogLabPlanner terbuka tanpa galat.
2. Tab 'Hipotesis' aktif dan menampilkan tabel ligan x prediksi x terukur.
3. Kartu statistik menampilkan n sampel dan evaluasi korelasi.
4. Kanvas QSvgWidget menampilkan grafik Prediksi vs Terukur.
5. Mengambil tangkapan layar dev/uji/lanjut/hipotesis_tab_terang.png & hipotesis_tab_gelap.png.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget

from virmolab.core import hipotesis
from virmolab.core.proyek import Proyek
from virmolab.ui.dialog_labplanner import DialogLabPlanner


class MockJendela(QWidget):
    def __init__(self, proyek, gelap=False):
        super().__init__()
        self.proyek = proyek
        self.gelap = gelap
        self.status = self

    def showMessage(self, msg, timeout=0):
        print(f"[STATUS] {msg}")

    def minta_simpan(self):
        print("[PROYEK] minta_simpan dipanggil")

    def buka_qsar(self):
        print("[QSAR] buka_qsar dipanggil")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    app = QApplication.instance() or QApplication(sys.argv)

    out_dir = Path("dev/uji/lanjut").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Buat proyek dummy uji dengan ligan dan docking
    pr = Proyek(out_dir / "uji_hipotesis.vmd")
    pr.ligan = [
        {"id": "LIG1", "nama": "Kandidat_1", "smiles": "CC(C)NC(=O)c1ccccc1"},
        {"id": "LIG2", "nama": "Kandidat_2", "smiles": "CC(=O)Oc1ccccc1C(=O)O"},
        {"id": "LIG3", "nama": "Kandidat_3", "smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"},
        {"id": "LIG4", "nama": "Kandidat_4", "smiles": "c1ccc(cc1)C(=O)O"},
        {"id": "LIG5", "nama": "Kandidat_5", "smiles": "c1ccccc1"},
        {"id": "LIG6", "nama": "Kandidat_6", "smiles": "CCO"},
        {"id": "LIG7", "nama": "Kandidat_7", "smiles": "CC(=O)N"},
        {"id": "LIG8", "nama": "Kandidat_8", "smiles": "CCN(CC)CC"},
    ]
    pr.job = [
        {
            "id": "job_uji",
            "mesin": "vina",
            "ligan": [
                {"id": "LIG1", "nama": "Kandidat_1", "status": "selesai", "energi": -10.5, "pose": [{"energi": -10.5}]},
                {"id": "LIG2", "nama": "Kandidat_2", "status": "selesai", "energi": -9.2, "pose": [{"energi": -9.2}]},
                {"id": "LIG3", "nama": "Kandidat_3", "status": "selesai", "energi": -8.4, "pose": [{"energi": -8.4}]},
                {"id": "LIG4", "nama": "Kandidat_4", "status": "selesai", "energi": -7.6, "pose": [{"energi": -7.6}]},
                {"id": "LIG5", "nama": "Kandidat_5", "status": "selesai", "energi": -6.8, "pose": [{"energi": -6.8}]},
                {"id": "LIG6", "nama": "Kandidat_6", "status": "selesai", "energi": -5.9, "pose": [{"energi": -5.9}]},
                {"id": "LIG7", "nama": "Kandidat_7", "status": "selesai", "energi": -5.1, "pose": [{"energi": -5.1}]},
                {"id": "LIG8", "nama": "Kandidat_8", "status": "selesai", "energi": -4.2, "pose": [{"energi": -4.2}]},
            ]
        }
    ]

    # Entri laboratorium basah terukur
    entri_lab = [
        {"id": "EXP001", "ligan_id": "LIG1", "nilai": 12.0, "satuan": "nM", "pIC50": 7.92, "status_hipotesis": "didukung", "assay": "Inhibisi Enzim"},
        {"id": "EXP002", "ligan_id": "LIG2", "nilai": 85.0, "satuan": "nM", "pIC50": 7.07, "status_hipotesis": "didukung", "assay": "Inhibisi Enzim"},
        {"id": "EXP003", "ligan_id": "LIG3", "nilai": 450.0, "satuan": "nM", "pIC50": 6.35, "status_hipotesis": "didukung", "assay": "Inhibisi Enzim"},
        {"id": "EXP004", "ligan_id": "LIG4", "nilai": 2.1, "satuan": "uM", "pIC50": 5.68, "status_hipotesis": "diuji", "assay": "Inhibisi Enzim"},
        {"id": "EXP005", "ligan_id": "LIG5", "nilai": 8.5, "satuan": "uM", "pIC50": 5.07, "status_hipotesis": "diuji", "assay": "Inhibisi Enzim"},
        {"id": "EXP006", "ligan_id": "LIG6", "nilai": 45.0, "satuan": "uM", "pIC50": 4.35, "status_hipotesis": "ditolak", "assay": "Inhibisi Enzim"},
        {"id": "EXP007", "ligan_id": "LIG7", "nilai": 120.0, "satuan": "uM", "pIC50": 3.92, "status_hipotesis": "ditolak", "assay": "Inhibisi Enzim"},
        {"id": "EXP008", "ligan_id": "LIG8", "nilai": 500.0, "satuan": "uM", "pIC50": 3.30, "status_hipotesis": "ditolak", "assay": "Inhibisi Enzim"},
    ]
    hipotesis.simpan_entri_proyek(pr, entri_lab)

    # 1. Uji tema terang
    jw_terang = MockJendela(pr, gelap=False)
    dlg_terang = DialogLabPlanner(jw_terang)
    dlg_terang.tab.setCurrentIndex(3)  # Tab Hipotesis
    dlg_terang.show()

    # 2. Uji tema gelap
    jw_gelap = MockJendela(pr, gelap=True)
    dlg_gelap = DialogLabPlanner(jw_gelap)
    dlg_gelap.tab.setCurrentIndex(3)  # Tab Hipotesis
    dlg_gelap.show()

    def simpan_dan_tutup():
        for _ in range(20):
            app.processEvents()
        path_terang = out_dir / "hipotesis_tab_terang.png"
        path_gelap = out_dir / "hipotesis_tab_gelap.png"
        dlg_terang.grab().save(str(path_terang))
        dlg_gelap.grab().save(str(path_gelap))

        print(f"OK    Screenshot terang disimpan: {path_terang} ({path_terang.stat().st_size} bytes)")
        print(f"OK    Screenshot gelap disimpan: {path_gelap} ({path_gelap.stat().st_size} bytes)")

        dlg_terang.close()
        dlg_gelap.close()
        app.quit()

    QTimer.singleShot(1500, simpan_dan_tutup)
    app.exec()


if __name__ == "__main__":
    main()
