import subprocess, pathlib
from virmodock.app import siapkan_kimia; siapkan_kimia()
from virmodock.core import prep_ligan as L, analisis as A, mesin as M, molekul
lig = [o for o in molekul.baca_teks_struktur(open("dev/uji/1HSG.pdb").read(), "1HSG") if o.jenis == "ligan"][0]
kr = A.mol_kristal(lig.teks)
d = pathlib.Path("dev/uji/run")
for nama, op in (("ph74", L.OpsiLigan()), ("netral", L.OpsiLigan(protonasi=False)), ("netral_tanpa_min", L.OpsiLigan(protonasi=False, minimisasi=False))):
    h = L.siapkan_satu("MK1", lig.teks, "pdb", op)
    f = d / f"p_{nama}.pdbqt"; f.write_text(h.pdbqt)
    hasil = []
    for seed in (1, 2, 3):
        p = M.Parameter(nrun=50, seed=seed)
        subprocess.run(M.perintah_adgpu(d / "reseptor.maps.fld", f, d / f"p_{nama}_{seed}", p), capture_output=True)
        ps = M.baca_hasil("adgpu", d / f"p_{nama}_{seed}.dlg")
        r = [round(A.rmsd_simetri(A.pose_mol(h.pdbqt, x.pdbqt), kr), 2) for x in ps[:5]]
        hasil.append((ps[0].energi, r[0], min(r)))
    print(nama, "muatan", h.muatan, "torsi", h.torsi, "| (dG, RMSD pose1, RMSD min top5) per seed:", hasil)
