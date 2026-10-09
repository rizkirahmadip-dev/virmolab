"""Uji wizard reseptor (4 langkah) + preparasi PROPKA/PDB2PQR pada 1HSG, 1ITB, 3KS3.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_wizard_reseptor.py
Keluaran: dev/uji/wizard_reseptor/ (tangkapan halaman + laporan_*.txt)
"""
import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from virmodock.app import siapkan_kimia

siapkan_kimia()
app = QApplication(sys.argv)
app.setStyle("Fusion")
from virmodock.core import molekul, periksa_protein, prep_reseptor as R
from virmodock.ui import theme

app.setPalette(theme.palet("terang"))
app.setStyleSheet(theme.qss("terang").replace("ICON_CHECK", ""))
from virmodock.ui.dialog_reseptor import DialogReseptor

OUT = Path("dev/uji/wizard_reseptor")
OUT.mkdir(parents=True, exist_ok=True)
gagal = 0
for kode in ("1HSG", "1ITB", "3KS3"):
    teks = Path(f"dev/uji/{kode}.pdb").read_text()
    objs = molekul.baca_teks_struktur(teks, kode)
    prot = [o for o in objs if o.jenis == "protein"]
    d = DialogReseptor(prot, {}, None, teks_sumber=lambda o, t=teks: t)
    d.resize(860, 620)
    d.show()
    for i in range(4):
        d.l_langkah.setCurrentRow(i)
        app.processEvents()
        d.grab().save(str(OUT / f"{kode}_langkah{i + 1}.png"))
    info = periksa_protein.periksa(teks)
    print(kode, periksa_protein.skor(info), [t for t in info["temuan"] if t[0] != "ok"][:3])
    op = d.opsi()
    d.reject()
    t0 = time.perf_counter()
    h = R.siapkan(teks, op)
    print(f"  {h.metode}: {h.atom} atom, {h.residu} residu, dibuang {len(h.dibuang)}, "
          f"{time.perf_counter() - t0:.1f} s; keadaan {[k[0] + ' ' + k[1] for k in h.protonasi.keadaan][:8] if h.protonasi else '-'}")
    (OUT / f"laporan_{kode}.txt").write_text(h.laporan, encoding="utf-8")
    if not h.protonasi or not h.atom:
        gagal += 1
    # PDBQT harus terbaca autogrid/vina: cek tipe atom dikenal
    tipe = R.tipe_atom(h.pdbqt)
    asing = tipe - {"A", "C", "N", "NA", "OA", "O", "S", "SA", "HD", "H", "Zn", "Mg", "Ca", "Mn", "Fe", "Cu", "NS", "OS"}
    if asing:
        print("  TIPE ASING:", asing)
        gagal += 1
print("GAGAL" if gagal else "LULUS", gagal)
