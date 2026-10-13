from pathlib import Path
from virmolab.app import siapkan_kimia; siapkan_kimia()
from virmolab.core import analisis as A, mesin as M, ekspor as E, proyek as P, prep_reseptor
pr = P.Proyek.buka(sorted(Path("dev/uji/kerja").glob("*.vmd"))[-1])
b = E.baris_hasil(pr)
print(len(b), "baris;", b[0]["ligan"], b[0]["energi"], b[0]["le"], b[0]["rmsd_kristal"], b[0]["hbond"])
open("dev/uji/hasil.csv", "w", encoding="utf-8", newline="").write(E.csv_teks(b))
E.simpan_xlsx("dev/uji/hasil.xlsx", pr, b, {}, {"Proyek": pr.nama})
j = pr.job[0]; l = j["ligan"][0]
ps = M.baca_hasil(j["mesin"], pr.p(l["keluaran"]))
m = A.pose_mol(pr.p(l["pdbqt"]).read_text(), ps[0].pdbqt)
rec = prep_reseptor.pdbqt_ke_pdb(pr.p("reseptor/reseptor.pdbqt").read_text())
t = E.kompleks_pdb(rec, m, ["MK1 pose 1 dG -12.3"])
open("dev/uji/kompleks.pdb", "w").write(t)
import gemmi; st = gemmi.read_pdb_string(t); print("kompleks rantai", [c.name for c in st[0]], st[0].count_atom_sites())
open("dev/uji/pose.sdf", "w").write(E.sdf_bertag([(m, "MK1", {"dG_kcal_mol": ps[0].energi, "Ki": ps[0].ki})]))
from rdkit import Chem
mm = next(Chem.SDMolSupplier("dev/uji/pose.sdf", removeHs=False)); print("sdf tag", mm.GetPropsAsDict())
import openpyxl; wb = openpyxl.load_workbook("dev/uji/hasil.xlsx"); print(wb.sheetnames, wb["Ringkasan"].max_row)
print(open("dev/uji/hasil.csv", encoding="utf-8-sig").read()[:300])
