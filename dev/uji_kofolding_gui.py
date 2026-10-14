"""Uji visual GUI untuk PanelProperti Tab Co-folding dan DialogKonsensus (F6).

Menghasilkan tangkapan layar tema terang dan gelap:
  - dev/uji/kofolding/panel_properti_terang.png
  - dev/uji/kofolding/panel_properti_gelap.png
  - dev/uji/kofolding/dialog_konsensus_terang.png
  - dev/uji/kofolding/dialog_konsensus_gelap.png
"""

from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QSplitter

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from virmolab.ui import panels, dialog_konsensus, theme

OUT = AKAR / "dev" / "uji" / "kofolding"
OUT.mkdir(parents=True, exist_ok=True)


class MockProyek:
    def __init__(self):
        self.nama = "Proyek Uji 1HSG"
        self.reseptor = {"pdbqt": "reseptor.pdbqt", "pdb": "virmolab/aset/uji_1hsg.pdb"}
        self.job = [
            {
                "id": "job_001_vina",
                "mesin": "vina",
                "ligan": [
                    {
                        "id": "lig_01",
                        "nama": "MK1 (Indinavir)",
                        "status": "selesai",
                        "energi": -11.18,
                        "rescore": {"vina": -11.18, "vinardo": -10.2},
                        "kofolding": {
                            "tersedia": True,
                            "pesan": "Analisis konsensus selesai.",
                            "rmsd": 0.502,
                            "rmsd_ca": 0.001,
                            "n_ca": 198,
                            "ifp_tanimoto": 0.667,
                            "posebusters_docking": {"lulus": True, "gagal": []},
                            "posebusters_cofold": {"lulus": True, "gagal": []},
                            "kesepakatan": "Sepakat",
                            "kebaruan": 0.85,
                            "peringatan_kebaruan": "",
                            "afinitas_pred_value": -2.145,
                            "afinitas_probabilitas": 0.985,
                        }
                    },
                    {
                        "id": "lig_02",
                        "nama": "Kandidat 02",
                        "status": "selesai",
                        "energi": -8.45,
                        "rescore": {"vina": -8.45, "vinardo": -7.1},
                        "kofolding": {
                            "tersedia": True,
                            "pesan": "Analisis konsensus selesai.",
                            "rmsd": 3.12,
                            "rmsd_ca": 0.05,
                            "n_ca": 198,
                            "ifp_tanimoto": 0.32,
                            "posebusters_docking": {"lulus": True, "gagal": []},
                            "posebusters_cofold": {"lulus": False, "gagal": ["tabrakan"]},
                            "kesepakatan": "Bertentangan",
                            "kebaruan": 0.15,
                            "peringatan_kebaruan": "Kemiripan ligan terhadap struktur PDB rendah (< 0,30).",
                            "afinitas_pred_value": 0.45,
                            "afinitas_probabilitas": 0.12,
                        }
                    },
                    {
                        "id": "lig_03",
                        "nama": "Kandidat 03 (Sebagian)",
                        "status": "selesai",
                        "energi": -9.30,
                        "rescore": {"vina": -9.30, "vinardo": -8.8},
                        "kofolding": {
                            "tersedia": True,
                            "pesan": "Analisis konsensus selesai.",
                            "rmsd": 1.85,
                            "rmsd_ca": 0.02,
                            "n_ca": 198,
                            "ifp_tanimoto": 0.55,
                            "posebusters_docking": {"lulus": True, "gagal": []},
                            "posebusters_cofold": {"lulus": True, "gagal": []},
                            "kesepakatan": "Sebagian",
                            "kebaruan": 0.65,
                            "peringatan_kebaruan": "",
                            "afinitas_pred_value": -1.25,
                            "afinitas_probabilitas": 0.78,
                        }
                    }
                ]
            }
        ]

    def p(self, *parts):
        return AKAR.joinpath(*parts)


class MockPelaksana:
    def __init__(self, proyek):
        self.proyek = proyek

    def cari(self, jid):
        return next((j for j in self.proyek.job if j["id"] == jid), None)


class MockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.mode = "terang"
        self.proyek = MockProyek()
        self.pelaksana = MockPelaksana(self.proyek)
        self.log = type("MockLog", (), {"tulis": lambda self, *a, **k: None})()
        self.minta_simpan = lambda: None

        self.prop = panels.PanelProperti(self)
        self.setCentralWidget(self.prop)
        self.resize(420, 680)

    def terapkan_tema(self, tema):
        self.mode = tema
        app = QApplication.instance()
        app.setPalette(theme.palet(tema))
        app.setStyleSheet(theme.qss(tema))
        self.prop.update()


def main():
    app = QApplication(sys.argv)
    app.setPalette(theme.palet("terang"))
    app.setStyleSheet(theme.qss("terang"))

    win = MockWindow()
    win.show()

    # 1. Muat data ligan MK1 ke PanelProperti
    st_b = {"ada": True, "pesan": "Boltz 2.2.1 siap di WSL (GPU RTX 3060)."}
    info_pose = {"job": "job_001_vina", "lid": "lig_01", "peringkat": 1, "ligan": "MK1 (Indinavir)"}
    data_kf = win.proyek.job[0]["ligan"][0]["kofolding"]
    win.prop.muat_kofolding(data_kf, st_b, info_pose)
    win.prop.tab.setCurrentIndex(1)  # Buka tab Co-folding

    app.processEvents()

    # Tangkap layar terang PanelProperti
    win.grab().save(str(OUT / "panel_properti_terang.png"))
    print("OK    PanelProperti tema terang tertangkap")

    # Buka DialogKonsensus tema terang
    dk = dialog_konsensus.DialogKonsensus(win)
    dk.resize(1460, 760)
    dk.findChild(QSplitter).setSizes([260, 1180])
    dk.hitung()
    app.processEvents()
    dk.grab().save(str(OUT / "dialog_konsensus_terang.png"))
    print("OK    DialogKonsensus tema terang tertangkap")
    dk.close()

    # Ubah ke tema gelap
    win.terapkan_tema("gelap")
    app.processEvents()
    win.grab().save(str(OUT / "panel_properti_gelap.png"))
    print("OK    PanelProperti tema gelap tertangkap")

    # Buka DialogKonsensus tema gelap
    dk_g = dialog_konsensus.DialogKonsensus(win)
    dk_g.resize(1460, 760)
    dk_g.findChild(QSplitter).setSizes([260, 1180])
    dk_g.hitung()
    app.processEvents()
    dk_g.grab().save(str(OUT / "dialog_konsensus_gelap.png"))
    print("OK    DialogKonsensus tema gelap tertangkap")
    dk_g.close()

    win.close()
    print("Semua tangkapan layar GUI F6 berhasil disimpan di dev/uji/kofolding/")


if __name__ == "__main__":
    main()
