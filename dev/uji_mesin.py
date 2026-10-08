import subprocess, time, sys
from pathlib import Path
from virmodock.core import mesin as M
d=Path("dev/uji/run"); d.mkdir(exist_ok=True)
rec=open("dev/uji/1HSG_rec.pdbqt").read(); lig=open("dev/uji/MK1.pdbqt").read()
(d/"reseptor.pdbqt").write_text(rec); (d/"MK1.pdbqt").write_text(lig)
xs=[(float(b[30:38]),float(b[38:46]),float(b[46:54])) for b in lig.splitlines() if b.startswith(("ATOM","HETATM"))]
k=M.Kotak(pusat=[sum(x[i] for x in xs)/len(xs) for i in range(3)], ukuran=[22.5]*3)
gpf=M.tulis_gpf(rec, M.tipe_atom(lig), k); (d/"reseptor.gpf").write_text(gpf)
t=time.time(); cmd,cwd=M.perintah_autogrid(d); r=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True); print("autogrid",r.returncode,round(time.time()-t,1),"s", M.grid_siap(d,gpf))
p=M.Parameter(nrun=20)
for mes in sys.argv[1:]:
    t=time.time(); pr=M.PembacaProgres(mes,p); last=[]
    if mes=="adgpu": cmd=M.perintah_adgpu(d/"reseptor.maps.fld", d/"MK1.pdbqt", d/"MK1_gpu", p); out=d/"MK1_gpu.dlg"
    elif mes=="vina": cmd=M.perintah_vina(d/"reseptor.pdbqt", d/"MK1.pdbqt", d/"MK1_out.pdbqt", k, p); out=d/"MK1_out.pdbqt"
    else:
        (d/"MK1.dpf").write_text(M.tulis_dpf(lig,"MK1.pdbqt",".",M.Parameter(nrun=3,nev=250000))); cmd=M.perintah_ad4("MK1.dpf","MK1_ad4.dlg"); out=d/"MK1_ad4.dlg"
    pp=subprocess.Popen(cmd,cwd=str(d) if mes=="ad4" else None,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    allout=""
    while True:
        ch=pp.stdout.read(64)
        if not ch: break
        allout+=ch
        for line in ch.split("\n"):
            v=pr.baca(line)
            if v is not None: last.append(v)
    pp.wait()
    print(mes, pp.returncode, round(time.time()-t,1),"s", "progres:",last[:3],"...",last[-3:])
    if pp.returncode: print(allout[-1500:])
    hs=M.baca_hasil(mes,out)
    for h in hs[:4]: print(" ",h.peringkat,h.energi,h.rmsd_lb,h.rmsd_ub,h.rmsd_ref,h.klaster,h.ki, len(h.pdbqt.splitlines()))
    open(f"dev/uji/{mes}_out.txt","w").write(allout)
