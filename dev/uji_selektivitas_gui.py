"""Uji integrasi dialog selektivitas multi-target VirmoLab."""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

from virmolab.core.proyek import Proyek
from virmolab.ui.dialog_selektivitas import DialogSelektivitas


def main():
    app = QApplication.instance() or QApplication(sys.argv)

    p1_path = AKAR / "dev" / "uji" / "kerja_docs" / "Docs_1HSG.vmd"
    p2_path = AKAR / "dev" / "uji" / "admet" / "7AEH_20261011_2151.vmd"

    if not p1_path.exists() or not p2_path.exists():
        print("LEWAT: berkas proyek uji tidak ditemukan.")
        return 0

    p1 = Proyek.buka(p1_path)
    p2 = Proyek.buka(p2_path)

    class DummyJW:
        proyek = p1

    jw = DummyJW()
    d = DialogSelektivitas(jw)
    d.daftar_proyek.append(("SARS-CoV-2 Mpro", p2))
    d._perbarui_daftar_target_ui()
    d._hitung_dan_tampilkan()

    assert len(d.label_target) == 2, f"Target harus 2, dapat {len(d.label_target)}"
    assert len(d.label_ligan) > 0, "Ligan harus > 0"
    assert d.tabel_selektivitas.rowCount() > 0, "Tabel harus terisi baris"
    print(f"OK   DialogSelektivitas berhasil memuat {len(d.label_ligan)} ligan pada {len(d.label_target)} target.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
