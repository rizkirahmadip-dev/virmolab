"""Uji GUI dialog Sunting di kantong (3D): pilih titik tumbuh, nilai usulan dengan Vina lokal, tangkap layar.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_sunting3d_gui.py
Keluaran: dev/uji/sunting3d/dialog_{terang,gelap}.png
"""
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))
sys.argv = [sys.argv[0]]

from PySide6.QtWidgets import QApplication, QWidget          # noqa: E402
from rdkit import Chem, RDLogger                             # noqa: E402

from virmolab.core import molekul, sunting3d as S            # noqa: E402
from virmolab.ui import theme                                # noqa: E402
from virmolab.ui.dialog_sunting3d import DialogSunting3D     # noqa: E402

RDLogger.DisableLog("rdApp.*")
KELUAR = AKAR / "dev" / "uji" / "sunting3d"
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


class ProyekPalsu:
    def __init__(self):
        self.reseptor = {"nama": "1HSG", "pdbqt": "1HSG_rec.pdbqt", "bersih": "1HSG.pdb"}
        self.ligan = []
        self.job = []

    def p(self, *bag):
        return AKAR / "dev" / "uji" / Path(*bag)

    def smiles_ligan(self, l):
        return ""


class JendelaPalsu(QWidget):
    def __init__(self):
        super().__init__()
        self.proyek = ProyekPalsu()
        mol = Chem.MolFromMolFile(str(AKAR / "dev" / "uji" / "MK1.sdf"), removeHs=False)
        o = molekul.Objek(nama="MK1 (pose docking)", jenis="pose", teks=Chem.MolToMolBlock(mol), fmt="sdf",
                          sumber="uji")
        self.objek = {o.id: o}
        self._aktif_inter = {"oid": o.id}
        self.ditambah = []
        self.ligan_baru = []

    def tambah_objek(self, daftar, fokus=False):
        self.ditambah += daftar

    def _ligan_siap(self, daftar):
        self.ligan_baru += daftar

    def _reseptor_objek(self):
        return None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    KELUAR.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    hasil_akhir = None
    for tema in ("terang", "gelap"):
        app.setPalette(theme.palet(tema))
        app.setStyleSheet(theme.qss(tema))
        jw = JendelaPalsu()
        d = DialogSunting3D(jw)
        d.resize(1200, 760)
        d.show()
        for _ in range(10):
            app.processEvents()
        cek(d.cb_ligan.count() == 1, f"pose induk terbaca dari viewer ({tema})")
        cek(d.cb_atom.count() > 10, f"titik tumbuh terdaftar: {d.cb_atom.count()} ({tema})")
        cek(d.b_jalan.isEnabled(), f"tombol Nilai usulan aktif ({tema})")
        # pilih atom lewat klik diagram (sinyal yang sama dengan klik mouse)
        idx = d.cb_atom.itemData(3)
        d.peta.atomDipilih.emit(idx)
        for _ in range(4):
            app.processEvents()
        cek(d.cb_atom.currentData() == idx, f"klik diagram memilih titik tumbuh ({tema})")
        # jalankan langsung (tanpa thread) supaya uji deterministik
        pilih = [S.GUGUS[i] for i in (0, 4, 7)]
        usulan = S.usulan_tumbuh(d._mol, d._atom, pilih)
        ind = S.induk(d._mol, d._rec_pdbqt, d._rec_pdb, "Pose induk")
        hasil = S.jalankan(d._mol, usulan, d._rec_pdbqt, d._rec_pdb, energi_induk=ind.energi)
        d._selesai((ind, hasil))
        for _ in range(6):
            app.processEvents()
        hasil_akhir = (ind, hasil)
        cek(ind.status == "ok" and ind.energi is not None, f"pose induk dinilai: {ind.energi} kkal/mol ({tema})")
        cek(d.tabel.rowCount() == len(hasil), f"tabel terisi {d.tabel.rowCount()} usulan ({tema})")
        ok = [u for u in hasil if u.status == "ok"]
        cek(len(ok) == len(hasil), f"semua usulan berhasil dinilai ({len(ok)}/{len(hasil)}, {tema})")
        cek(all(u.d_energi is not None for u in ok), f"ΔΔG terhadap induk dihitung ({tema})")
        cek("kkal/mol" in d.k_induk.l_ket.text(), f"kartu ΔG induk terisi ({tema})")
        cek("usulan dinilai" in d.l_status.text(), f"status menyebut jumlah usulan ({tema})")
        d.tabel.setCurrentCell(0, 0)
        n = len(jw.ditambah)
        d._ke_viewer()
        cek(len(jw.ditambah) == n + 1, f"pose usulan dikirim ke viewer ({tema})")
        p = KELUAR / f"dialog_{tema}.png"
        d.grab().save(str(p))
        cek(p.exists() and p.stat().st_size > 5000, f"tangkapan layar {tema} ({p.name})")
        d.close()
    if hasil_akhir:
        ind, hasil = hasil_akhir
        print(f"\ninduk {ind.energi} kkal/mol, LE {ind.le}")
        for u in sorted(hasil, key=lambda x: x.energi or 0):
            print(f"  {u.nama:22s} {u.energi:7.2f} ΔΔG {u.d_energi:+5.2f}  tabrakan {u.tabrakan}  {u.detik:.1f} s")
        print(S.teks_metode(len(hasil), sum(1 for u in hasil if u.status == "ok")))
    print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
    sys.exit(1 if gagal else 0)


if __name__ == "__main__":
    main()
