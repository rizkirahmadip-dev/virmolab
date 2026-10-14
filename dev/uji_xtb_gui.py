"""Uji GUI dialog Sifat elektronik (xTB): buka dialog, hitung satu ligan, tangkap layar kedua tema.

Keluaran: dev/uji/xtb/dialog_xtb_{terang,gelap}.png
"""
from pathlib import Path
import sys

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from PySide6.QtTest import QTest                               # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget            # noqa: E402
from rdkit import Chem                                         # noqa: E402
from rdkit.Chem import AllChem                                 # noqa: E402

from virmolab.core import xtb                                  # noqa: E402
from virmolab.ui import theme                                  # noqa: E402
from virmolab.ui.dialog_xtb import DialogXtb                   # noqa: E402

KELUAR = AKAR / "dev" / "uji" / "xtb"
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


def mol3d(smi, nama):
    m = Chem.AddHs(Chem.MolFromSmiles(smi))
    AllChem.EmbedMolecule(m, randomSeed=42)
    AllChem.MMFFOptimizeMolecule(m)
    m.SetProp("_Name", nama)
    return m


class JendelaPalsu(QWidget):
    """Jendela utama palsu: hanya menyediakan ligan proyek dan proyek kosong."""

    proyek = None

    def minta_simpan(self):
        pass


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    info = xtb.tersedia()
    if not info["ada"]:
        print(f"LEWAT: {info['pesan']}")
        return
    KELUAR.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)

    ligan = [{"nama": "benzena", "mol": mol3d("c1ccccc1", "benzena")},
             {"nama": "anilin", "mol": mol3d("Nc1ccccc1", "anilin")}]
    from virmolab.ui import kit
    kit.ligan_proyek = lambda jw, **k: ligan          # dialog hanya butuh daftar ini

    for tema in ("terang", "gelap"):
        app.setPalette(theme.palet(tema))
        app.setStyleSheet(theme.qss(tema))
        d = DialogXtb(JendelaPalsu())
        d.resize(1200, 720)
        d.show()
        for _ in range(10):
            app.processEvents()
        cek(d.daftar.count() == 2, f"dua ligan terdaftar ({tema})")
        cek("xtb" in d.l_status_xtb.text().lower(), f"status xtb tampil ({tema})")

        # Hitung langsung (tanpa thread) supaya uji tetap deterministik
        hasil = xtb.hitung_banyak([(l["mol"], l["nama"]) for l in ligan], esp=False, n_proses=1)
        d._selesai(hasil)
        for _ in range(10):
            app.processEvents()
        cek(d.tabel.rowCount() == 2, f"tabel terisi dua baris ({tema})")

        nilai_benzena = {d.tabel.item(r, 0).text(): r for r in range(d.tabel.rowCount())}
        cek("benzena" in nilai_benzena and "anilin" in nilai_benzena, f"nama ligan di tabel ({tema})")
        d.tabel.selectRow(nilai_benzena["anilin"])
        for _ in range(8):
            app.processEvents()
        cek(bool(d.l_legenda.text()), f"legenda pewarnaan terisi ({tema})")
        teks_dialog = " ".join(w.text() for w in d.findChildren(type(d.l_status_xtb)) if w.text())
        cek("Bukan DFT" in teks_dialog, f"peringatan metode tampil di dialog ({tema})")

        d.cb_mode.setCurrentIndex(2)      # muatan parsial
        for _ in range(8):
            app.processEvents()
        cek("Muatan" in d.l_legenda.text(), f"mode muatan parsial aktif ({tema})")

        QTest.qWait(3500)      # beri waktu WebGL penampil merender molekul
        cek(not d.l_legenda.text().startswith("Nilai untuk mode"),
            f"nilai per atom tersedia untuk pewarnaan ({tema})")
        p = KELUAR / f"dialog_xtb_{tema}.png"
        d.grab().save(str(p))
        cek(p.exists() and p.stat().st_size > 5000, f"tangkapan layar {tema} ({p.name})")
        d.close()

    print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
    sys.exit(1 if gagal else 0)


if __name__ == "__main__":
    main()
