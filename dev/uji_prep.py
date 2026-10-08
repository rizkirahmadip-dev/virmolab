import sys, time
from virmodock.core import prep_reseptor as P
for k in sys.argv[1:]:
    t=time.time()
    h=P.siapkan(open(f"dev/uji/{k}.pdb").read())
    open(f"dev/uji/{k}_rec.pdbqt","w").write(h.pdbqt)
    print(k, round(time.time()-t,1),"s"); print(h.laporan)
