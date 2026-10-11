"""Uji alat penelitian 0.9.6 (tanpa GUI, tanpa GPU).

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv\\Scripts\\python.exe dev\\uji_penelitian.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rdkit import Chem
from rdkit.Chem import AllChem

from virmodock.core import (air, energi_residu, kampanye, konservasi, kovalen, mutasi, naskah, senyawa, syarat)

gagal = []


def cek(nama, fn):
    try:
        fn()
        print("OK   ", nama, flush=True)
    except Exception as e:
        gagal.append(nama)
        print("GAGAL", nama, type(e).__name__, e, flush=True)


def atom(nomor, nama, resn, rantai, resi, x, y, z, tipe):
    return (f"ATOM  {nomor:5d}  {nama:<4}{resn:>3} {rantai}{resi:4d}    {x:8.3f}{y:8.3f}{z:8.3f}"
            f"  1.00  0.00    +0.000 {tipe}")


def t_konservasi():
    skor = konservasi.skor("ACD", [("h", "ACD"), ("h2", "ACE")])
    assert skor[0]["identitas"] == 1.0
    assert skor[2]["identitas"] == 0.5
    pdb = "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n"
    out = konservasi.terapkan_bfaktor(pdb, "A", [{"identitas": 0.5, "n": 2, "aa": "A"}])
    assert "50.00" in out


def t_senyawa():
    m = Chem.AddHs(Chem.MolFromSmiles("CC(=O)O"))
    AllChem.EmbedMolecule(m, AllChem.ETKDGv3())
    AllChem.MMFFOptimizeMolecule(m, maxIters=200)
    assert senyawa.regangan(m) < 5
    assert senyawa.bentuk(m, Chem.Mol(m)) > 0.9
    assert senyawa.ada_makrosiklus(Chem.MolFromSmiles("C1CCCCCC1"))
    assert not senyawa.ada_makrosiklus(Chem.MolFromSmiles("c1ccccc1"))
    gugus = senyawa.enumerasi_gugus("*c1ccccc1", ["Cl"])
    assert gugus[0][1] and "Cl" in gugus[0][1]
    bio = dict(senyawa.bioisoster(Chem.MolFromSmiles("CC(=O)O")))
    assert bio
    tau = senyawa.tautomer(Chem.MolFromSmiles("CC(=O)C"))
    assert tau
    umpan = senyawa.umpan(["CC(=O)Oc1ccccc1C(=O)O"], 5, seed=1)
    assert umpan


def t_kovalen():
    m = Chem.MolFromSmiles("CN=C=S")
    d = kovalen.deteksi(m, "CYS")
    assert any(x[0] == "isotiosianat" for x in d)
    assert kovalen.catatan_warhead("isotiosianat")


def t_energi():
    rec = "\n".join([
        atom(1, "CA", "ALA", "A", 1, 0, 0, 0, "C"),
        atom(2, "CB", "ALA", "A", 1, 1.5, 0, 0, "C"),
        atom(3, "CG", "ASP", "A", 2, 3.2, 0.4, 0, "C"),
        atom(4, "OD1", "ASP", "A", 2, 3.6, 1.5, 0, "OA"),
    ]) + "\n"
    lig = atom(1, "C1", "UNL", " ", 1, 5.2, 1.2, 0, "C") + "\n"
    residu, total = energi_residu.per_residu(rec, lig)
    assert residu and isinstance(total, float)
    ala = energi_residu.alanin(rec, lig, maks=4)
    assert isinstance(ala, list)


def t_air():
    pdb = "\n".join([
        "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N",
        "ATOM      2  CA  ALA A   1       1.400   0.000   0.000  1.00  0.00           C",
        "HETATM    3  C1  LIG B   1       6.000   0.000   0.000  1.00  0.00           C",
        "HETATM    4  C2  LIG B   1       7.200   0.800   0.000  1.00  0.00           C",
        "HETATM    5  O   HOH C   1       3.000   0.200   0.000  1.00  0.00           O",
        "HETATM    6  FE  HEM D   1      12.000   0.000   0.000  1.00  0.00          FE",
        "HETATM    7  CHA HEM D   1      13.400   0.000   0.000  1.00  0.00           C",
        "END",
    ])
    h = air.telaah(pdb)
    assert h["jembatan"], h
    assert any(k["resn"] == "HEM" for k in h["kofaktor"])


def t_lain():
    ok, gagal_s = syarat.periksa([{"jenis": "hbond", "residu": "ASP 25 A"}], ["ASP 25 A hbond", "HIS 41 A"])
    assert not ok and gagal_s == ["HIS 41 A"]
    baris = [{"ligan": "A", "reseptor": "R1", "energi": -8, "kovalen": False, "warhead": ""},
             {"ligan": "A", "reseptor": "R2", "energi": -6, "kovalen": True, "warhead": "nitril"}]
    assert kampanye.ensemble(baris)[0]["energi"] == -8
    assert kampanye.banding_kovalen(baris)
    assert naskah.periksa_figur(72, 85, 5, ["#ff0000", "#00ff00"])
    draf = naskah.draf_skripsi({"nama": "Uji", "baris": [("X", "-7.00", "")]})
    assert "Bab III" in draf and "CNNaffinity" in draf and "pK" in draf
    assert "@misc" in naskah.bibtex()
    pdb = "ATOM      1  CB  LYS A  12       1.500   0.000   0.000  1.00  0.00           C\n" \
          "ATOM      2  CG  LYS A  12       2.800   0.500   0.000  1.00  0.00           C\nEND\n"
    ala, _ = mutasi.mutasi(pdb, "A", "12", "A")
    assert "ALA" in ala and "CG" not in ala
    from virmodock.core import lanjutan
    assert lanjutan.ringkas_gnina("Affinity: -1.0\nCNNscore: 0.20\nlain") == "Affinity: -1.0\nCNNscore: 0.20"
    import openmm as mm
    from openmm import app, unit
    import tempfile
    top = app.Topology()
    chain = top.addChain()
    res = top.addResidue("ALA", chain)
    a0 = top.addAtom("N", app.Element.getBySymbol("N"), res)
    a1 = top.addAtom("CA", app.Element.getBySymbol("C"), res)
    top.addBond(a0, a1)
    sistem = mm.System()
    sistem.addParticle(14.0)
    sistem.addParticle(12.0)
    ikatan = mm.HarmonicBondForce()
    ikatan.addBond(0, 1, 0.145, 200000.0)
    sistem.addForce(ikatan)
    gb = mm.GBSAOBCForce()
    gb.addParticle(0.0, 0.17, 0.8)
    gb.addParticle(0.0, 0.17, 0.8)
    sistem.addForce(gb)
    pos = unit.Quantity([[0, 0, 0], [0.145, 0, 0]], unit.nanometer)
    folder = Path(tempfile.mkdtemp())
    catatan = lanjutan.tulis_topologi_gromacs(sistem, top, pos, folder)
    assert (folder / "kompleks.gro").exists()
    assert (folder / "kompleks.top").exists()
    assert "tidak ikut" in catatan
    assert "bonds" in (folder / "kompleks.top").read_text(encoding="utf-8").lower()


def t_baru():
    from virmodock.core import asisten, lanjutan, lokal
    xml = """<BlastOutput><BlastOutput_iterations><Iteration><Iteration_hits>
      <Hit><Hit_def>sp|P00000|TES</Hit_def><Hit_hsps><Hsp><Hsp_hseq>AC-DE</Hsp_hseq></Hsp></Hit_hsps></Hit>
    </Iteration_hits></Iteration></BlastOutput_iterations></BlastOutput>"""
    assert konservasi.urai_blast_xml(xml) == [("sp|P00000|TES", "ACDE")]
    assert "2 Å" in asisten.jawab_aturan("kapan redocking dianggap valid")
    assert lokal.baca_afinitas("   1       -7.50      0.000      0.000") == -7.5
    mol = Chem.MolFromSmiles("c1ccccc1")
    AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    assert "ATOM" in lokal.pdbqt_pose(mol)
    y = lanjutan._yaml_boltz([("A", "ACDEFGHIK")], "CCO")
    assert "empty" in y
    assert "empty" not in lanjutan._yaml_boltz([("A", "ACDEFGHIK")], "CCO", msa_kosong=False)
    import virmodock.ui.dialog_asisten
    import virmodock.ui.dialog_penelitian


if __name__ == "__main__":
    uji = [("konservasi", t_konservasi), ("senyawa", t_senyawa), ("kovalen warhead", t_kovalen),
           ("energi residu", t_energi), ("air", t_air), ("syarat kampanye naskah mutasi", t_lain),
           ("blast asisten lokal boltz", t_baru)]
    for nama, fn in uji:
        cek(nama, fn)
    print(f"\n{len(uji) - len(gagal)}/{len(uji)} lulus" if not gagal else f"\nGAGAL: {gagal}")
    sys.exit(1 if gagal else 0)
