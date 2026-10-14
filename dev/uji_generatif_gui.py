"""Uji GUI dialog Desain generatif (F8): buka dialog, bangun analog, tangkap layar kedua tema.

Keluaran: dev/uji/generatif/dialog_generatif_{terang,gelap}.png
"""
from pathlib import Path
import sys

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from PySide6.QtWidgets import QApplication, QWidget        # noqa: E402
from rdkit import RDLogger                                 # noqa: E402

from virmolab.core import generatif                        # noqa: E402
from virmolab.ui import theme                              # noqa: E402
from virmolab.ui.dialog_generatif import DialogGeneratif   # noqa: E402

RDLogger.DisableLog("rdApp.*")
KELUAR = AKAR / "dev" / "uji" / "generatif"
MK1 = "CC(C)(C)NC(=O)[C@@H]1CN(Cc2cccnc2)CCN1C[C@@H](O)C[C@@H](Cc1ccccc1)C(=O)N[C@H]1c2ccccc2C[C@H]1O"
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


class JendelaPalsu(QWidget):
    proyek = None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    info = generatif.tersedia()
    if not info["ada"]:
        print(f"LEWAT: {info['pesan']}")
        return
    KELUAR.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)

    from virmolab.ui import kit
    kit.ligan_proyek = lambda jw, **k: [{"nama": "MK1 (indinavir)", "smiles": MK1}]

    for tema in ("terang", "gelap"):
        app.setPalette(theme.palet(tema))
        app.setStyleSheet(theme.qss(tema))
        d = DialogGeneratif(JendelaPalsu())
        d.resize(1140, 700)
        d.show()
        for _ in range(10):
            app.processEvents()
        cek(d.t_smiles.text() == MK1, f"SMILES induk terisi dari ligan proyek ({tema})")
        cek(d.b_jalan.isEnabled(), f"tombol bangun aktif ({tema})")

        # Jalankan langsung tanpa thread supaya uji deterministik
        d.s_maks.setValue(150)
        hasil = generatif.siklus(MK1, dock=None, n_generasi=1, maks=150,
                                 sa_maks=d.s_sa.value(), qed_min=d.s_qed.value(), relatif_induk=True)
        d._selesai(hasil)
        for _ in range(8):
            app.processEvents()
        cek(d.tabel.rowCount() > 0, f"tabel kandidat terisi ({tema}, {d.tabel.rowCount()} baris)")
        cek("ditolak" in d.l_ringkas.text(), f"ringkasan menyebut jumlah yang ditolak ({tema})")
        cek("ΔG masih kosong" in d.l_ringkas.text(), f"status ΔG dinyatakan jujur ({tema})")

        teks = generatif.paragraf_metode(hasil)
        cek("CReM" in teks and "usulan komputasi" in teks, f"paragraf metode menyebut batasan ({tema})")

        p = KELUAR / f"dialog_generatif_{tema}.png"
        d.grab().save(str(p))
        cek(p.exists() and p.stat().st_size > 5000, f"tangkapan layar {tema} ({p.name})")
        d.close()

    print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
    sys.exit(1 if gagal else 0)


if __name__ == "__main__":
    main()
