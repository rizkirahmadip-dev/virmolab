import time
from concurrent.futures import ThreadPoolExecutor
from virmolab.app import siapkan_kimia; siapkan_kimia()
from virmolab.core import molekul, prep_ligan as L
nama = "quercetin kaempferol luteolin apigenin naringenin hesperetin curcumin resveratrol caffeine ibuprofen aspirin paracetamol oseltamivir remdesivir lopinavir ritonavir nelfinavir saquinavir indinavir darunavir".split()
t = time.time()
with ThreadPoolExecutor(6) as ex:
    objs = list(ex.map(lambda n: molekul.unduh_pubchem(n)[0], nama))
t1 = time.time() - t
h = L.siapkan_banyak([(o.nama, o.teks, "sdf") for o in objs])
print(f"unduh {t1:.1f}s, preparasi {time.time()-t-t1:.1f}s")
for x in h: print(f"{x.nama:12s} {x.status:10s} torsi {x.torsi:2d} q {x.muatan:+d} {x.alasan[:70]}")
