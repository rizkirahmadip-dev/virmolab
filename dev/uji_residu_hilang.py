"""Uji residu hilang (core/residu_hilang.py): hapus-loop pada 3KS3, celah nyata 1HP0, dan grup di wizard reseptor.

Butuh internet sekali (struktur RCSB + model AlphaFold DB, lalu tersimpan di cache). Hasil gambar wizard:
dev/uji/residu_hilang/wizard_<tema>.png

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_residu_hilang.py
"""
import sys
import urllib.request
from pathlib import Path

import gemmi
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from virmolab.core import molekul, prep_reseptor  # noqa: E402
from virmolab.core import residu_hilang as RH  # noqa: E402

D = Path("dev/uji/residu_hilang")
D.mkdir(parents=True, exist_ok=True)
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


def ambil(kode):
    f = D / f"{kode}.pdb"
    if not f.exists():
        req = urllib.request.Request(f"https://files.rcsb.org/download/{kode}.pdb", headers={"User-Agent": "VirmoLab"})
        f.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    return f.read_text(encoding="utf-8", errors="replace")


def tanpa(teks, rantai, lo, hi):
    return "\n".join(b for b in teks.splitlines()
                     if not (b.startswith(("ATOM", "ANISOU")) and b[21] == rantai and lo <= int(b[22:26]) <= hi))


# --- A. hapus-loop pada 3KS3 (karbonat anhidrase II, UniProt P00918), pembanding: koordinat kristal yang dihapus
teks = Path("dev/uji/3KS3.pdb").read_text(encoding="utf-8", errors="replace") if Path("dev/uji/3KS3.pdb").exists() \
    else ambil("3KS3")
sek, unp = RH.info_sekuens(teks)
cek(len(sek.get("A", [])) == 260 and unp.get("A") == "P00918", f"3KS3: SEQRES 260 residu, UniProt {unp.get('A')}")
asli = gemmi.read_pdb_string(teks)
bb = {(r.seqid.num, a.name): np.array([a.pos.x, a.pos.y, a.pos.z]) for r in asli[0]["A"] for a in r
      if a.name in ("N", "CA", "C", "O")}
for lo, hi, maks in ((230, 237, 1.0), (166, 177, 1.0), (55, 66, 1.0)):
    st = gemmi.read_pdb_string(tanpa(teks, "A", lo, hi))
    st.remove_ligands_and_waters()
    st.setup_entities()
    celah = [c for c in RH.cari_celah(st, sek) if c.jenis == "internal"]
    cek(len(celah) == 1 and celah[0].n == hi - lo + 1, f"3KS3 Δ{lo}-{hi}: celah {hi - lo + 1} residu terdeteksi dari SEQRES")
    st2, celah = RH.lengkapi(st, celah, "otomatis", unp)
    c = celah[0]
    d = [((np.array([a.pos.x, a.pos.y, a.pos.z]) - bb[(r.seqid.num, a.name)]) ** 2).sum()
         for r in st2[0]["A"] if lo <= r.seqid.num <= hi for a in r if (r.seqid.num, a.name) in bb]
    rmsd = float(np.sqrt(np.mean(d))) if d else float("nan")
    cek(c.metode.startswith("AlphaFold") and rmsd <= maks,
        f"3KS3 Δ{lo}-{hi}: {c.metode}, RMSD tulang punggung {rmsd:.2f} Å (≤ {maks}), pLDDT {c.plddt}")
    cek(all(s is not None and 1.25 <= s <= 1.45 for s in c.sambungan) and c.bentrok == 0,
        f"3KS3 Δ{lo}-{hi}: sambungan {c.sambungan} Å, bentrok {c.bentrok}")
# PDBFixer hanya untuk celah pendek pada mode otomatis
st = gemmi.read_pdb_string(tanpa(teks, "A", 230, 237))
st.remove_ligands_and_waters()
st.setup_entities()
celah = [c for c in RH.cari_celah(st, sek) if c.jenis == "internal"]
_, celah = RH.lengkapi(st, celah, "otomatis", {})          # tanpa UniProt: AlphaFold tidak bisa
cek(celah[0].metode == "dibiarkan" and "PDBFixer" in celah[0].catatan,
    f"tanpa UniProt, celah 8 residu dibiarkan: {celah[0].catatan}")

# --- B. celah nyata: 1HP0 (nukleosida hidrolase T. vivax + AD3), 8 residu hilang 4,7 Å dari ligan
teks = ambil("1HP0")
sek, unp = RH.info_sekuens(teks)
st = gemmi.read_pdb_string(teks)
st.setup_entities()
lig = [np.array([a.pos.x, a.pos.y, a.pos.z]) for ch in st[0] for r in ch if r.name == "AD3" for a in r]
celah = [c for c in RH.cari_celah(st, sek, lig) if c.jenis == "internal"]
dekat = [c for c in celah if c.jarak_kantong is not None and c.jarak_kantong <= 10]
cek(bool(dekat), "1HP0: celah dekat ligan terdeteksi: " + "; ".join(f"{c.label()} {c.jarak_kantong} Å" for c in celah))
h = prep_reseptor.siapkan(teks, prep_reseptor.OpsiReseptor(protonasi="propka", lengkapi_loop=True,
                                                           sekuens=sek, uniprot=unp))
isi = [c for c in h.loop if c["metode"].startswith("AlphaFold")]
cek(bool(isi), "1HP0: " + "; ".join(f"{c['rantai']} {c['sebelum']}–{c['sesudah']}: {c['metode']} pLDDT {c['plddt']}"
                                       for c in h.loop))
loop_xyz = [np.array([float(b[30:38]), float(b[38:46]), float(b[46:54])]) for b in h.pdb_bersih.splitlines()
            if b.startswith("ATOM") and any(f"{b[17:20]} {b[22:27].strip()}" in c["dimodelkan"] for c in isi)
            and b[21] in {c["rantai"] for c in isi}]
if loop_xyz and lig:
    jarak = float(min(np.linalg.norm(p - q) for p in loop_xyz for q in lig))
    print(f"      loop terisi ke ligan kristal AD3: {jarak:.1f} Å (< 2,5 Å berarti loop model menutup kantong)")
cek("Residu hilang:" in h.laporan and not any("dibuang oleh Meeko" in p for p in h.peringatan),
    "1HP0: laporan memuat residu hilang; tidak ada residu loop yang dibuang Meeko")

# --- C. wizard: grup Residu hilang (terang & gelap)
from PySide6.QtWidgets import QApplication  # noqa: E402
app = QApplication.instance() or QApplication([])
from virmolab.ui import theme  # noqa: E402
from virmolab.ui.dialog_reseptor import DialogReseptor  # noqa: E402
objs = molekul.baca_teks_struktur(teks, "1HP0", "pdb", "RCSB 1HP0")
prot = [o for o in objs if o.jenis == "protein"]
cek(prot and prot[0].info.get("sekuens") and prot[0].info.get("uniprot"), "objek protein menyimpan SEQRES dan UniProt")
sumber = "\n".join(b for b in teks.splitlines() if b.startswith(("ATOM", "HETATM", "TER")))
for tema in ("terang", "gelap"):
    app.setPalette(theme.palet(tema))
    app.setStyleSheet(theme.qss(tema))
    d = DialogReseptor(prot, {}, None, teks_sumber=lambda o: sumber)
    d.show()
    d.l_langkah.setCurrentRow(1)
    for _ in range(10):
        app.processEvents()
    d.grab().save(str(D / f"wizard_{tema}.png"))
    if tema == "terang":
        cek(d.c_loop.isEnabled() and d.c_loop.isChecked(), f"wizard: celah dekat kantong -> dicentang ({d.l_celah.text()[:90]})")
        op = d.opsi()
        cek(op.lengkapi_loop and op.sekuens and op.uniprot and op.kode_pdb == "1HP0", "wizard: opsi membawa SEQRES, UniProt, kode PDB")
    d.close()
print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
sys.exit(1 if gagal else 0)
