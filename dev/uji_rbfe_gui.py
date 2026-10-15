"""Uji GUI dialog Energi bebas relatif (F9): susun jaringan, periksa kejujuran status, tangkap layar.

Status mesin kini datang dari OpenFE di WSL (core/rbfe_openfe.py), bukan dari paket Python Windows; yang diuji
adalah dialog mengatakan keadaan sebenarnya, baik saat OpenFE ada maupun tidak.

Keluaran: dev/uji/rbfe/dialog_rbfe_{terang,gelap}.png
"""
from pathlib import Path
import sys

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from PySide6.QtWidgets import QApplication, QWidget      # noqa: E402
from rdkit import RDLogger                               # noqa: E402

from virmolab.core import rbfe, rbfe_openfe              # noqa: E402
from virmolab.ui import theme                            # noqa: E402
from virmolab.ui.dialog_rbfe import DialogRbfe           # noqa: E402

RDLogger.DisableLog("rdApp.*")
KELUAR = AKAR / "dev" / "uji" / "rbfe"
SERI = [{"nama": "toluena", "smiles": "Cc1ccccc1"},
        {"nama": "etilbenzena", "smiles": "CCc1ccccc1"},
        {"nama": "klorobenzena", "smiles": "Clc1ccccc1"},
        {"nama": "bromobenzena", "smiles": "Brc1ccccc1"}]
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


class JendelaPalsu(QWidget):
    proyek = None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    KELUAR.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)

    from virmolab.ui import kit
    kit.ligan_proyek = lambda jw, **k: SERI

    st = rbfe_openfe.status()
    for tema in ("terang", "gelap"):
        app.setPalette(theme.palet(tema))
        app.setStyleSheet(theme.qss(tema))
        d = DialogRbfe(JendelaPalsu())
        d.resize(1080, 680)
        d.show()
        for _ in range(10):
            app.processEvents()
        cek(d.daftar.count() == 4, f"seri senyawa terdaftar ({tema})")

        for _ in range(40):          # status WSL diperiksa di thread latar
            app.processEvents()
        teks_dialog = " ".join(w.text() for w in d.findChildren(type(d.l_status)) if w.text())
        if st["ada"]:
            cek("siap di WSL" in teks_dialog or "openfe" in teks_dialog.lower(),
                f"OpenFE yang terpasang dinyatakan siap ({tema}): {d.l_mesin.text()[:70]}")
        else:
            cek("belum terpasang" in teks_dialog or "tidak dapat dijalankan" in teks_dialog,
                f"ketidaktersediaan mesin dinyatakan terus terang ({tema}): {d.l_mesin.text()[:70]}")
        cek("Eksperimental" in teks_dialog, f"label eksperimental tampil ({tema})")

        # Susun langsung tanpa thread supaya uji deterministik
        pasangan = rbfe.pasangan_dari_mmp([(s["nama"], s["smiles"]) for s in SERI])
        d._selesai((rbfe.jaringan(pasangan, "mst"), pasangan))
        for _ in range(8):
            app.processEvents()
        cek(d.tabel.rowCount() > 0, f"tabel tepi terisi ({tema}, {d.tabel.rowCount()} baris)")
        cek("ns simulasi" in d.l_beban.text(), f"perkiraan beban ditampilkan ({tema})")
        cek("belum dapat diperkirakan" in d.l_beban.text() or "hari" in d.l_beban.text(),
            f"lama perhitungan dinyatakan jujur ({tema})")

        p = KELUAR / f"dialog_rbfe_{tema}.png"
        d.grab().save(str(p))
        cek(p.exists() and p.stat().st_size > 5000, f"tangkapan layar {tema} ({p.name})")
        d.close()

    print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
    sys.exit(1 if gagal else 0)


if __name__ == "__main__":
    main()
