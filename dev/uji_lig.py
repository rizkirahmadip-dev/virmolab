import time
from virmodock.core import prep_ligan as L, molekul
lig=[o for o in molekul.baca_teks_struktur(open("dev/uji/1HSG.pdb").read(),"1HSG") if o.jenis=="ligan"][0]
d=[(lig.nama,lig.teks,"pdb"),("aspirin","CC(=O)Oc1ccccc1C(=O)O","smiles"),("salah","C1CC(","smiles"),
   ("cast", open("dev/uji/cast.sdf").read() if False else "COc1cc(O)c2c(c1)oc(-c1ccc(OC)c(O)c1)c(OC)c2=O","smiles"),
   ("garam","CC(=O)[O-].[Na+]","smiles"),("peptida_panjang","CC(C)C[C@H](NC(=O)"*12+"C)"+"C(=O)O)"*0,"smiles")]
t=time.time(); h=L.siapkan_banyak(d)
for x in h: print(x.nama,x.status,x.torsi,x.atom,x.rumus,x.tipe,"|",x.alasan)
print(round(time.time()-t,1),"s")
open("dev/uji/MK1.pdbqt","w").write(h[0].pdbqt); open("dev/uji/MK1.sdf","w").write(h[0].sdf)
open("dev/uji/aspirin.pdbqt","w").write(h[1].pdbqt)
