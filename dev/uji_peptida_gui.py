"""Uji GUI dialog docking peptida (F10): buka dialog, periksa validasi langsung, tangkap layar.

Keluaran: dev/uji/peptida/dialog_peptida_{terang,gelap}.png
"""
from pathlib import Path
import sys

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from PySide6.QtWidgets import QApplication, QWidget              # noqa: E402

from virmolab.ui import theme                                    # noqa: E402
from virmolab.ui.dialog_peptida import DialogPeptida             # noqa: E402

KELUAR = AKAR / "dev" / "uji" / "peptida"
PDB_KRISTAL = AKAR / "dev" / "data" / "1YCR.pdb"
SEKUENS = "ETFSDLWKLLPEN"
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


class JendelaPalsu(QWidget):
    """Pengganti jendela utama: cukup menyediakan reseptor dan proyek yang dipakai dialog."""

    def __init__(self, teks_pdb):
        super().__init__()
        self._teks = teks_pdb
        self.proyek = None

    def _reseptor_objek(self):
        class O:
            fmt = "pdb"
        o = O()
        o.teks = self._teks
        o.nama = "1YCR"
        return o


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if not PDB_KRISTAL.exists():
        print("LEWAT: dev/data/1YCR.pdb belum ada")
        return
    KELUAR.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)

    teks = PDB_KRISTAL.read_text(encoding="utf-8")
    for tema in ("terang", "gelap"):
        app.setPalette(theme.palet(tema))
        app.setStyleSheet(theme.qss(tema))
        jw = JendelaPalsu(teks)
        d = DialogPeptida(jw)
        d.resize(1000, 660)
        d.show()
        for _ in range(12):
            app.processEvents()

        cek(len(d._rantai_reseptor) >= 1, f"rantai reseptor terbaca ({tema})")

        d.t_seq.setPlainText(SEKUENS)
        for _ in range(8):
            app.processEvents()
        cek(d.b_jalan.isEnabled(), f"sekuens sah mengaktifkan tombol Jalankan ({tema})")
        cek("13 residu" in d.l_periksa.text(), f"panjang sekuens dilaporkan ({tema})")

        d.t_seq.setPlainText("ETJSDLWK")
        for _ in range(8):
            app.processEvents()
        cek(not d.b_jalan.isEnabled(), f"sekuens salah mematikan tombol Jalankan ({tema})")
        cek("J" in d.l_periksa.text(), f"huruf tak dikenal disebut di pesan ({tema})")

        d.t_seq.setPlainText(SEKUENS)
        for _ in range(8):
            app.processEvents()
        p = KELUAR / f"dialog_peptida_{tema}.png"
        d.grab().save(str(p))
        cek(p.exists() and p.stat().st_size > 5000, f"tangkapan layar {tema} tersimpan ({p.name})")
        d.close()

    print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
    sys.exit(1 if gagal else 0)


if __name__ == "__main__":
    main()
