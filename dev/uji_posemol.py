from virmolab.core import mesin as M
from meeko import PDBQTMolecule, RDKitMolCreate
from rdkit import Chem
import pathlib as _pl
_butuh = [_pl.Path("dev/uji/MK1.pdbqt"), _pl.Path("dev/uji/run/MK1_gpu.dlg"),
          _pl.Path("dev/uji/run/MK1_out.pdbqt")]
if not all(f.exists() for f in _butuh):
    print("LEWAT: butuh hasil docking contoh di dev/uji/run/ (jalankan dev/uji_mesin.py dulu)")
    raise SystemExit(0)
inp = open("dev/uji/MK1.pdbqt").read()
rem = "\n".join(b for b in inp.splitlines() if b.startswith("REMARK"))
for mes, f in (("adgpu", "dev/uji/run/MK1_gpu.dlg"), ("vina", "dev/uji/run/MK1_out.pdbqt")):
    p = M.baca_hasil(mes, f)[0]
    s = rem + "\n" + p.pdbqt + "\n"
    pm = PDBQTMolecule(s, skip_typing=True)
    mol = RDKitMolCreate.from_pdbqt_mol(pm)[0]
    print(mes, mol.GetNumAtoms(), Chem.GetFormalCharge(mol), Chem.MolToSmiles(Chem.RemoveHs(mol))[:60])
