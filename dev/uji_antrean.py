import sys, shutil
from PySide6.QtCore import QCoreApplication, QTimer
from virmolab.core import proyek as P, antrean as A, mesin as M
app=QCoreApplication([])
pr=P.Proyek.baru("dev/uji/proj","Uji 1HSG")
shutil.copy("dev/uji/1HSG_rec.pdbqt", pr.p("reseptor","reseptor.pdbqt"))
pr.reseptor={"nama":"1HSG","pdbqt":"reseptor/reseptor.pdbqt"}
for n in ("MK1","aspirin"):
    shutil.copy(f"dev/uji/{n}.pdbqt", pr.p("ligan","pdbqt",f"{n}.pdbqt"))
    pr.ligan.append({"id":n,"nama":n,"status":"siap","pdbqt":f"ligan/pdbqt/{n}.pdbqt"})
k={"pusat":[13.07,22.47,5.56],"ukuran":[22.5]*3,"spasi":0.375}
pl=A.Pelaksana(); pl.atur_proyek(pr)
pl.log.connect(print); pl.pesan.connect(lambda s: print("PESAN",s)); pl.perluSimpan.connect(pr.simpan)
selesai=[]
def js(jid):
    selesai.append(jid); j=pl.cari(jid); print("JOB",jid,j["status"],[(l["nama"],l["status"],l["energi"],l["rmsd_ref"]) for l in j["ligan"]])
    if len(selesai)==2: app.quit()
pl.jobSelesai.connect(js)
pl.tambah(A.job_baru(pr, pr.ligan, "adgpu","gpu",{"nrun":10},k))
import time; time.sleep(1)
pl.tambah(A.job_baru(pr, pr.ligan, "vina","cpu",{"exhaustiveness":4},k))
QTimer.singleShot(300000, app.quit)
app.exec()
pr2=P.Proyek.buka(pr.folder); print("dibuka ulang:",len(pr2.job),"job", [j["status"] for j in pr2.job])
