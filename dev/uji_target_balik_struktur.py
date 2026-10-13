#!/usr/bin/env python3
"""Uji terpadu jalur struktur: ibuprofen x panel (kelas dari argv, bawaan antiinflamasi) lewat antrean Pelaksana sungguhan
(Vina CPU), lalu z-skor dan Borda dari hasil docking nyata. Hasil dilaporkan apa adanya (tidak ada ambang lulus biologis)."""
import sys
import tempfile
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

from virmolab.core import antrean, prep_ligan, target_balik as tb  # noqa: E402
from virmolab.core.proyek import Proyek  # noqa: E402

kelas = sys.argv[1] if len(sys.argv) > 1 else "antiinflamasi"
app = QCoreApplication([])
tmp = tempfile.mkdtemp(prefix="vmd_tb_")
pr = Proyek(Path(tmp) / "uji")
pr.siapkan_folder()
h = prep_ligan.siapkan_satu("ibuprofen", "CC(C)Cc1ccc(cc1)C(C)C(=O)O", "smiles", prep_ligan.OpsiLigan())
assert h.pdbqt, h.alasan
pr.p("ligan", "pdbqt", "L1.pdbqt").write_text(h.pdbqt, encoding="utf-8")
lig = {"id": "L1", "nama": "ibuprofen", "pdbqt": "ligan/pdbqt/L1.pdbqt", "status": "siap"}
pr.ligan.append(lig)

pel = antrean.Pelaksana()
pel.atur_proyek(pr)
jobs = tb.jalur_struktur(pr, lig, kelas, daftarkan=pel.tambah)
print(f"{len(jobs)} job dibuat untuk kelas {kelas}", flush=True)
sisa = {j["id"] for j in jobs}
pel.jobSelesai.connect(lambda jid: (sisa.discard(jid), print("selesai", jid, len(sisa), "sisa", flush=True), None if sisa else app.quit()))
QTimer.singleShot(1500000, app.quit)
app.exec()

hasil = tb.kumpulkan(pr, kelas, ligan_id="L1")
print("\ngen        PDB   status     energi   z_rata  z_sd    z")
for x in hasil:
    print(f"{x['gen']:<10} {x['pdb']}  {x['status']:<9} {x['energi']}  {x['z_rata']}  {x['z_sd']}  {x['z_skor']}")
g = tb.gabung([], hasil)
print("\nUrutan struktur (z terkecil dulu):", [(e["gen"], e["r_struktur"]) for e in g if e["r_struktur"]])
