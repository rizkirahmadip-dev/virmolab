import time
from virmolab.app import siapkan_kimia; siapkan_kimia()
from virmolab.core import analisis as A, molekul, mesin as M
rec = A.baca_reseptor(open("dev/uji/1HSG_rec.pdbqt").read())
lig = [o for o in molekul.baca_teks_struktur(open("dev/uji/1HSG.pdb").read(), "1HSG") if o.jenis == "ligan"][0]
kr = A.mol_kristal(lig.teks)
t = time.time(); I = A.interaksi(rec, kr); print("kristal", round(time.time()-t, 3), "s", A.hitung(I))
for h in I:
    if h["jenis"] != "vdw": print(f"  {h['jenis']:10s} {h['residu']:10s} {h['atom_p']:4s} {h['jarak']:.2f} {h['sudut']} {h['sub']}")
print("  vdw:", ", ".join(h["residu"] for h in I if h["jenis"] == "vdw"))
inp = open("dev/uji/MK1.pdbqt").read()
for mes, f in (("adgpu", "dev/uji/run/MK1_gpu.dlg"), ("vina", "dev/uji/run/MK1_out.pdbqt")):
    ps = M.baca_hasil(mes, f)
    for p in ps[:3]:
        m = A.pose_mol(inp, p.pdbqt)
        t = time.time(); I = A.interaksi(rec, m)
        print(mes, p.peringkat, p.energi, "RMSD kristal", round(A.rmsd_simetri(m, kr), 2), "ref", p.rmsd_ref, A.hitung(I), round(time.time()-t, 3))
# 3KS3 Zn + aspirin vina
rz = A.baca_reseptor(open("dev/uji/zn/reseptor.pdbqt").read())
ps = M.baca_hasil("vina", "dev/uji/zn/asp_out.pdbqt")
m = A.pose_mol(open("dev/uji/aspirin.pdbqt").read(), ps[0].pdbqt)
print("3KS3 aspirin", A.hitung(A.interaksi(rz, m)))
