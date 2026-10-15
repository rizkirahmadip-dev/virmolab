"""EKSPERIMEN (tidak dipakai aplikasi): docking induced fit dengan relaksasi kantong.

Hasil validasinya negatif - lihat dev/dokumen/INDUCED_FIT_EKSPERIMEN.md. Modul ini disimpan di
dev/ supaya tidak ikut terpasang, dan dijalankan oleh dev/uji_induced_fit.py.

Docking induced fit: kantong dibiarkan menyesuaikan diri dengan ligan, bukan dianggap kaku.

Protokolnya mengikuti alur Induced Fit Docking Glide/Prime (Sherman W, Day T, Jacobson MP, Friesner RA, Farid R.
J Med Chem. 2006;49(2):534-553), dengan program bebas:

  1. Docking lunak    - rantai samping besar di kantong dipangkas menjadi alanina (CB saja), sehingga ligan dapat
                        masuk ke bentuk kantong yang berbeda dari kristal.
  2. Relaksasi        - beberapa pose terbaik dibawa terus: rantai samping dikembalikan utuh, lalu kompleks
                        protein-ligan diminimisasi dengan
                        OpenMM (medan gaya Amber14 + ligan OpenFF/NAGL, pelarut implisit OBC2). Hanya rantai samping
                        di sekitar ligan yang bebas bergerak; tulang punggung dan sisa protein dikekang.
  3. Docking ulang    - ligan didocking ulang pada reseptor hasil relaksasi (kaku), dan pose terbaiknya dilaporkan.

Yang dihasilkan: pose ligan, reseptor yang sudah menyesuaikan diri (PDB + PDBQT), skor docking lunak dan skor akhir,
serta RMSD pergeseran rantai samping. Skor akhir tetap skor docking biasa (Vina/AD-GPU), bukan energi bebas ikatan;
dua struktur reseptor yang berbeda tidak dibandingkan langsung lewat skornya.
"""
import io
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from virmolab.core import mesin as M

NOWIN = 0x08000000
# Rantai samping yang dipangkas saat docking lunak (Gly/Ala/Pro tidak punya rantai samping yang berguna untuk
# dipangkas; Ser/Cys/Thr terlalu kecil untuk mengubah bentuk kantong).
DIPANGKAS = {"ARG", "LYS", "GLU", "GLN", "MET", "LEU", "ILE", "PHE", "TYR", "TRP", "HIS", "ASP", "ASN", "VAL"}
INTI = {"N", "CA", "C", "O", "CB", "OXT"}
SITASI = ("Sherman W, Day T, Jacobson MP, Friesner RA, Farid R. Novel procedure for modeling ligand/receptor induced "
          "fit effects. J Med Chem. 2006;49(2):534-553. doi:10.1021/jm050540c")


class GalatIF(Exception):
    pass


@dataclass
class OpsiIF:
    radius: float = 5.0            # rantai samping dalam radius ini dari pose awal ikut dipangkas & direlaksasi
    maks_residu: int = 20          # batas jumlah rantai samping yang dipangkas (residu terdekat didahulukan)
    kekang: float = 2.0            # kekangan harmonik atom berat tulang punggung (kkal/mol/Å²)
    kekang_ligan: float = 5.0      # kekangan atom ligan selama relaksasi (pose dipertahankan)
    ps_anil: float = 20.0          # anil singkat 300->75 K supaya rantai samping bisa berpindah rotamer (0 = mati)
    suhu_anil: float = 300.0       # suhu awal anil (K)
    iterasi: int = 2000            # langkah minimisasi OpenMM
    n_pose: int = 3                # pose awal per sumber yang direlaksasi lalu didocking ulang (Sherman dkk.: 20)
    jendela: float = 3.0           # hanya pose dalam jendela ini (kkal/mol) dari pose terbaik sumbernya
    pakai_kaku: bool = True        # pose docking reseptor utuh ikut jadi titik awal (kantong yang hanya sesak)
    pakai_lunak: bool = True       # pose docking kantong terpangkas ikut jadi titik awal (kantong yang tertutup)
    exhaustiveness: int = 16       # Vina untuk docking lunak dan docking ulang
    num_modes: int = 9
    seed: int = 42
    platform: str = "auto"


@dataclass
class HasilIF:
    pose_pdbqt: str = ""           # pose ligan terbaik pada reseptor yang sudah menyesuaikan diri
    pose_lunak_pdbqt: str = ""     # pose pada reseptor terpangkas (hanya untuk telaah)
    energi: float = None           # skor docking ulang (kkal/mol)
    energi_lunak: float = None     # skor docking lunak (reseptor dipangkas) - tidak sebanding dengan energi
    energi_kaku: float = None      # skor docking biasa pada reseptor asli, bila dihitung (pembanding)
    reseptor_pdb: str = ""         # reseptor hasil relaksasi (PDB, dengan hidrogen)
    reseptor_pdbqt: str = ""       # reseptor hasil relaksasi untuk docking lanjutan
    residu: list = field(default_factory=list)      # [{id, resn, rmsd_sisi, dipangkas}]
    rmsd_sisi: float = None        # RMSD atom berat rantai samping yang direlaksasi (reseptor awal -> akhir)
    rmsd_pose: float = None        # RMSD pose awal -> pose akhir
    n_pose_relaks: int = 0         # pose awal yang berhasil direlaksasi dan didocking ulang
    asal_pose: str = ""            # titik awal pose terbaik: "reseptor utuh" | "kantong terpangkas"
    detik: float = 0.0
    catatan: list = field(default_factory=list)

    def ke_dict(self):
        return {"energi": self.energi, "energi_lunak": self.energi_lunak, "energi_kaku": self.energi_kaku,
                "residu": self.residu, "rmsd_sisi": self.rmsd_sisi, "rmsd_pose": self.rmsd_pose,
                "n_pose_relaks": self.n_pose_relaks, "asal_pose": self.asal_pose, "detik": self.detik,
                "catatan": self.catatan}


# ------------------------------------------------------------------ geometri PDB
def _atom(b):
    return {"nama": b[12:16].strip(), "resn": b[17:20].strip(), "rantai": b[21], "resi": b[22:27].strip(),
            "x": float(b[30:38]), "y": float(b[38:46]), "z": float(b[46:54]), "baris": b}


def _baca_pdb(teks):
    return [_atom(b) for b in teks.splitlines() if b.startswith(("ATOM", "HETATM")) and len(b) >= 54]


def _pusat_pose(pose_pdbqt):
    xyz = [(float(b[30:38]), float(b[38:46]), float(b[46:54])) for b in pose_pdbqt.splitlines()
           if b.startswith(("ATOM", "HETATM"))]
    if not xyz:
        raise GalatIF("Pose ligan kosong.")
    return np.array(xyz)


def residu_sekitar(teks_pdb, acuan, radius=5.0, maks=20):
    """Residu protein yang rantai sampingnya dekat dengan acuan, terdekat lebih dulu.

    acuan: blok pose/ligan PDBQT (jarak ke atom ligan) atau mesin.Kotak (jarak ke dinding kotak: atom di dalam
    kotak berjarak 0). Kotak dipakai saat belum ada pose yang bisa dipercaya - pose docking kaku pada kantong
    yang tertutup sering mendarat di cekungan lain, dan residu yang dipangkas pun ikut salah.
    -> [(id 'A:123', resn, jarak terdekat)]"""
    if hasattr(acuan, "pusat"):
        pusat, ukuran = np.array(acuan.pusat, float), np.array(acuan.ukuran, float)

        def jarak_ke(p):
            return float(np.linalg.norm(np.maximum(np.abs(p - pusat) - ukuran / 2, 0.0)))
    else:
        lig = _pusat_pose(acuan)

        def jarak_ke(p):
            return float(np.sqrt(((lig - p) ** 2).sum(axis=1)).min())
    jarak = {}
    for a in _baca_pdb(teks_pdb):
        if a["resn"] not in DIPANGKAS or a["nama"] in INTI or a["nama"].startswith("H"):
            continue
        d = jarak_ke(np.array([a["x"], a["y"], a["z"]]))
        rid = f"{a['rantai']}:{a['resi']}"
        if d < jarak.get(rid, (1e9, ""))[0]:
            jarak[rid] = (d, a["resn"])
    dekat = sorted(((d, rid, resn) for rid, (d, resn) in jarak.items() if d <= radius))
    return [(rid, resn, round(d, 2)) for d, rid, resn in dekat[:maks]]


def pangkas(teks_pdb, residu):
    """Hapus atom rantai samping di luar N/CA/C/O/CB (residu jadi 'alanina'), kembalikan PDB terpangkas."""
    pilih = {r[0] if isinstance(r, (tuple, list)) else r for r in residu}
    keluar = []
    for b in teks_pdb.splitlines():
        if b.startswith(("ATOM", "HETATM")) and len(b) >= 54:
            a = _atom(b)
            if f"{a['rantai']}:{a['resi']}" in pilih and a["nama"] not in INTI and not a["nama"].startswith("H"):
                continue
        keluar.append(b)
    return "\n".join(keluar) + "\n"


def rmsd_rantai_samping(pdb_a, pdb_b, residu):
    """RMSD atom berat rantai samping (per residu dan keseluruhan) antara dua struktur dengan penomoran sama."""
    pilih = {r[0] if isinstance(r, (tuple, list)) else r for r in residu}

    def peta(teks):
        d = {}
        for a in _baca_pdb(teks):
            rid = f"{a['rantai']}:{a['resi']}"
            if rid in pilih and a["nama"] not in INTI and not a["nama"].startswith("H"):
                d.setdefault(rid, {})[a["nama"]] = (a["x"], a["y"], a["z"])
        return d
    A, B = peta(pdb_a), peta(pdb_b)
    per_residu, semua = {}, []
    for rid in sorted(set(A) & set(B)):
        nama = sorted(set(A[rid]) & set(B[rid]))
        if not nama:
            continue
        d2 = [sum((A[rid][n][i] - B[rid][n][i]) ** 2 for i in range(3)) for n in nama]
        per_residu[rid] = round(float(np.sqrt(np.mean(d2))), 2)
        semua += d2
    return per_residu, (round(float(np.sqrt(np.mean(semua))), 2) if semua else None)


# ------------------------------------------------------------------ docking satu ligan (Vina)
def _vina(rec_pdbqt, lig_pdbqt, kotak, opsi, kerja):
    """Docking satu ligan dengan Vina di folder kerja -> (daftar Pose, teks keluaran)."""
    kerja = Path(kerja)
    kerja.mkdir(parents=True, exist_ok=True)
    r = kerja / "rec.pdbqt"
    l = kerja / "lig.pdbqt"
    o = kerja / "out.pdbqt"
    r.write_text(rec_pdbqt, encoding="utf-8")
    l.write_text(lig_pdbqt, encoding="utf-8")
    p = M.Parameter(mesin="vina", perangkat="cpu", exhaustiveness=opsi.exhaustiveness, num_modes=opsi.num_modes,
                    seed=opsi.seed)
    cmd = M.perintah_vina(r, l, o, kotak, p)
    h = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=3600, creationflags=NOWIN)
    if not o.exists():
        raise GalatIF("Vina gagal: " + M.ringkas_galat((h.stderr or h.stdout or "").strip()))
    return M.baca_hasil("vina", o), h.stdout


# ------------------------------------------------------------------ relaksasi OpenMM
def _pdbqt_ke_pdb_protein(pdbqt):
    """PDBQT reseptor -> PDB (kolom muatan/tipe dibuang). Hidrogen dipertahankan."""
    keluar = []
    for b in pdbqt.splitlines():
        if b.startswith(("ATOM", "HETATM")):
            keluar.append(b[:66].rstrip())
        elif b.startswith("TER"):
            keluar.append("TER")
    return "\n".join(keluar) + "\nEND\n"


def relaksasi(teks_pdb, pose_mol, residu, opsi, lapor=None):
    """Minimisasi kompleks protein-ligan: rantai samping residu terpilih bebas, sisanya dikekang.
    -> (PDB reseptor hasil relaksasi, Mol ligan hasil relaksasi, info)"""
    import openmm as mm
    from openmm import app, unit
    from virmolab.core import md
    log = lapor or (lambda s: None)
    t0 = time.time()
    ff, modeller, info = md.siapkan_kompleks(teks_pdb, "", pose_mol, lapor=lapor)
    platform = md.platform_terbaik(opsi.platform)
    s = md.sistem_implisit(ff, modeller.topology, grup=False)
    pos = np.asarray(modeller.positions.value_in_unit(unit.nanometer))
    bebas = {r[0] if isinstance(r, (tuple, list)) else r for r in residu}
    lig = set(info["idx_ligan"])
    n_bebas = 0
    k = mm.CustomExternalForce("0.5*kk*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
    k.addGlobalParameter("kk", opsi.kekang * md.KKAL * 100.0)        # kkal/mol/Å² -> kJ/mol/nm²
    for nm in ("x0", "y0", "z0"):
        k.addPerParticleParameter(nm)
    for a in modeller.topology.atoms():
        if a.index in lig or a.element is None or a.element.symbol == "H":
            continue
        rid = f"{a.residue.chain.id}:{str(a.residue.id).strip()}"
        if rid in bebas and a.name not in INTI:      # rantai samping kantong: bebas bergerak
            n_bebas += 1
            continue
        k.addParticle(a.index, pos[a.index].tolist())
    s.addForce(k)
    # Ligan ditahan di tempatnya selama anil supaya pose tidak melayang; rantai samping bebas mencari rotamer baru.
    kl = mm.CustomExternalForce("0.5*kl*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
    kl.addGlobalParameter("kl", opsi.kekang_ligan * md.KKAL * 100.0)
    for nm in ("x0", "y0", "z0"):
        kl.addPerParticleParameter(nm)
    for i in sorted(lig):
        kl.addParticle(i, pos[i].tolist())
    s.addForce(kl)
    integrator = mm.LangevinMiddleIntegrator(opsi.suhu_anil * unit.kelvin, 1.0 / unit.picosecond,
                                             0.002 * unit.picosecond)
    c = mm.Context(s, integrator, platform[1], platform[2])
    c.setPositions(pos)
    e0 = c.getState(getEnergy=True).getPotentialEnergy()._value / md.KKAL
    mm.LocalEnergyMinimizer.minimize(c, 10.0, opsi.iterasi)       # bentrok awal dihilangkan dulu
    if opsi.ps_anil > 0:
        # Anil singkat: minimisasi saja tidak bisa melewati penghalang rotamer, padahal perubahan rantai samping
        # pada induced fit justru sering berupa lompatan rotamer (mis. Gln/Arg yang berputar).
        c.setVelocitiesToTemperature(opsi.suhu_anil * unit.kelvin)
        integrator.step(int(opsi.ps_anil * 500))                  # 2 fs/langkah
        for suhu in (0.75, 0.5, 0.25):                            # didinginkan bertahap
            integrator.setTemperature(opsi.suhu_anil * suhu * unit.kelvin)
            integrator.step(int(opsi.ps_anil * 125))
        mm.LocalEnergyMinimizer.minimize(c, 10.0, opsi.iterasi)
    pos1 = c.getState(getPositions=True).getPositions(asNumpy=True).value_in_unit(unit.nanometer)
    e1 = c.getState(getEnergy=True).getPotentialEnergy()._value / md.KKAL
    log(f"Relaksasi {n_bebas} atom rantai samping bebas, {len(lig)} atom ligan"
        + (f", anil {opsi.ps_anil:g} ps pada {opsi.suhu_anil:g} K" if opsi.ps_anil > 0 else "")
        + f": {e0:,.0f} -> {e1:,.0f} kkal/mol ({platform[0]}, {time.time() - t0:.0f} s)")
    # tulis kembali: protein (tanpa ligan) sebagai PDB, ligan sebagai Mol baru
    buf = io.StringIO()
    app.PDBFile.writeFile(modeller.topology, (pos1 * 10).tolist() * unit.angstrom, buf, keepIds=True)
    pdb_semua = buf.getvalue()
    pdb_protein = "\n".join(b for b in pdb_semua.splitlines()
                            if not (b.startswith(("ATOM", "HETATM")) and b[17:20].strip() in ("UNL", "UNK", "LIG")))
    mol = _mol_dari_pos(pose_mol, np.asarray(pos1)[sorted(lig)] * 10.0)
    return pdb_protein, mol, {"energi_awal": e0, "energi_akhir": e1, "atom_bebas": n_bebas,
                              "platform": platform[0], "detik": round(time.time() - t0, 1)}


def _mol_dari_pos(mol, xyz_angstrom):
    from rdkit.Chem import Mol
    from rdkit.Geometry import Point3D
    baru = Mol(mol)
    conf = baru.GetConformer()
    for i in range(baru.GetNumAtoms()):
        x, y, z = xyz_angstrom[i]
        conf.SetAtomPosition(i, Point3D(float(x), float(y), float(z)))
    return baru


# ------------------------------------------------------------------ reseptor -> PDBQT
def _pdbqt_reseptor(pdb, opsi_reseptor=None):
    from virmolab.core import prep_reseptor
    o = opsi_reseptor or prep_reseptor.OpsiReseptor()
    try:
        rigid, dibuang, _log = prep_reseptor._meeko(pdb, o)
        return rigid, dibuang
    except Exception as e:
        raise GalatIF(f"Reseptor hasil relaksasi gagal dijadikan PDBQT: {str(e).splitlines()[0][:150]}")


def _mol_ke_pdbqt(mol):
    from meeko import MoleculePreparation, PDBQTWriterLegacy
    prep = MoleculePreparation()
    siap = prep.prepare(mol)
    teks, ok, pesan = PDBQTWriterLegacy.write_string(siap[0])
    if not ok:
        raise GalatIF(f"Ligan gagal ditulis sebagai PDBQT: {pesan}")
    return teks


# ------------------------------------------------------------------ protokol lengkap
def jalankan(teks_pdb_reseptor, pdbqt_reseptor, pdbqt_ligan, kotak, pose_awal=None, opsi=None, lapor=None,
             banding_kaku=True):
    """Protokol induced fit lengkap untuk satu ligan.

    teks_pdb_reseptor: PDB reseptor bersih (hasil preparasi, 'untuk_meeko.pdb'/'bersih.pdb').
    pdbqt_reseptor   : PDBQT reseptor kaku (docking lunak dan pembanding).
    pdbqt_ligan      : PDBQT ligan siap docking (REMARK SMILES dari Meeko).
    kotak            : kotak docking (mesin.Kotak) - sekaligus penentu rantai samping yang dipangkas.
    pose_awal        : pose docking kaku yang sudah ada; hanya dicatat sebagai pembanding, tidak mengubah protokol.
    """
    opsi = opsi or OpsiIF()
    log = (lambda s: lapor.log.emit(s)) if hasattr(lapor, "log") else (lapor or (lambda s: None))
    maju = (lambda i, n, t: lapor.progres.emit(i, n, t)) if hasattr(lapor, "progres") else (lambda *_a: None)
    t0 = time.time()
    h = HasilIF()
    from virmolab.core import analisis
    with tempfile.TemporaryDirectory(prefix="virmolab_if_") as tmp:
        tmp = Path(tmp)
        # Residu kantong dipilih dari kotak docking, bukan dari pose: pada kantong yang tertutup pose docking
        # sering mendarat di cekungan lain, sehingga rantai samping yang dipangkas/direlaksasi pun ikut salah.
        residu = residu_sekitar(teks_pdb_reseptor, kotak, opsi.radius, opsi.maks_residu)
        if not residu:
            raise GalatIF("Tidak ada rantai samping besar di sekitar kotak docking; docking induced fit tidak ada "
                          "gunanya untuk kantong ini.")
        log(f"Rantai samping kantong ({len(residu)}): "
            + ", ".join(f"{resn}{rid.split(':')[1]}{rid.split(':')[0]}" for rid, resn, _d in residu))

        def _ambil(rec_pdbqt, label, folder):
            p, _o = _vina(rec_pdbqt, pdbqt_ligan, kotak, opsi, tmp / folder)
            if not p:
                return []
            pilih = [x for x in p[:opsi.n_pose] if x.energi - p[0].energi <= opsi.jendela]
            log(f"Docking {label}: {p[0].energi:.2f} kkal/mol, {len(pilih)} pose dibawa ke relaksasi")
            return [(label, x) for x in pilih]

        # --- 1a. docking pada reseptor utuh: cukup untuk kantong yang hanya sesak, dan sekaligus pembanding
        awal = []
        if opsi.pakai_kaku or banding_kaku:
            kaku = _ambil(pdbqt_reseptor, "reseptor utuh", "kaku")
            if not kaku and not opsi.pakai_lunak:
                raise GalatIF("Docking awal tidak menghasilkan pose.")
            if kaku:
                h.energi_kaku = kaku[0][1].energi
            if opsi.pakai_kaku:
                awal += kaku
        # --- 1b. docking lunak: rantai samping kantong dipangkas jadi alanina, untuk kantong yang tertutup
        if opsi.pakai_lunak:
            pdb_pangkas = pangkas(teks_pdb_reseptor, residu)
            pdbqt_pangkas, dibuang = _pdbqt_reseptor(pdb_pangkas)
            if dibuang:
                h.catatan.append(f"{len(dibuang)} residu tidak dikenali Meeko pada reseptor terpangkas dan dibuang.")
            lunak = _ambil(pdbqt_pangkas, "kantong terpangkas", "lunak")
            if lunak:
                h.energi_lunak = lunak[0][1].energi
                h.pose_lunak_pdbqt = lunak[0][1].pdbqt
            awal += lunak
        if not awal:
            raise GalatIF("Tidak ada pose awal yang bisa direlaksasi.")

        # --- 2 & 3. tiap pose awal: relaksasi kompleks (rantai samping utuh) lalu docking ulang
        kandidat = []
        for i, (asal, p) in enumerate(awal, 1):
            maju(i, len(awal) + 1, f"Relaksasi & docking ulang pose {i}/{len(awal)}")
            try:
                mol_pose = analisis.pose_mol(pdbqt_ligan, p.pdbqt)
                pdb_relaks, _mol, info = relaksasi(teks_pdb_reseptor, mol_pose, residu, opsi, log)
                rec_pdbqt, dibuang2 = _pdbqt_reseptor(pdb_relaks)
                ulang, _o = _vina(rec_pdbqt, pdbqt_ligan, kotak, opsi, tmp / f"ulang{i}")
            except Exception as e:
                log(f"Pose {i} ({asal}) gagal: {str(e).splitlines()[0][:150]}")
                h.catatan.append(f"Pose awal {i} ({asal}) gagal direlaksasi/didocking ulang: "
                                 f"{str(e).splitlines()[0][:150]}")
                continue
            if not ulang:
                continue
            log(f"Pose {i} ({asal}): {p.energi:.2f} -> docking ulang {ulang[0].energi:.2f} kkal/mol")
            kandidat.append({"pose": ulang[0], "pdb": pdb_relaks, "pdbqt": rec_pdbqt, "mol_awal": mol_pose,
                             "dibuang": dibuang2, "energi_awal": p.energi, "asal": asal, "minimisasi": info})
        if not kandidat:
            raise GalatIF("Tidak ada pose yang berhasil melewati relaksasi dan docking ulang. Lihat catatan.")
        terbaik = min(kandidat, key=lambda k: k["pose"].energi)
        h.pose_pdbqt, h.energi = terbaik["pose"].pdbqt, terbaik["pose"].energi
        h.reseptor_pdb, h.reseptor_pdbqt = terbaik["pdb"], terbaik["pdbqt"]
        h.n_pose_relaks = len(kandidat)
        info = terbaik["minimisasi"]
        h.catatan.append(f"Minimisasi {info['platform']}: {info['energi_awal']:,.0f} -> {info['energi_akhir']:,.0f} "
                         f"kkal/mol".replace(",", "."))
        h.asal_pose = terbaik["asal"]
        log(f"Pose terbaik: {h.energi:.2f} kkal/mol dari {len(kandidat)} pose yang direlaksasi "
            f"(titik awal: {terbaik['asal']})")

        per_residu, h.rmsd_sisi = rmsd_rantai_samping(teks_pdb_reseptor, h.reseptor_pdb, residu)
        h.residu = [{"id": rid, "resn": resn, "jarak": d, "rmsd_sisi": per_residu.get(rid)} for rid, resn, d in residu]
        try:
            h.rmsd_pose = round(analisis.rmsd_simetri(analisis.pose_mol(pdbqt_ligan, h.pose_pdbqt),
                                                      terbaik["mol_awal"]), 2)
        except Exception:
            h.rmsd_pose = None
        h.detik = round(time.time() - t0, 1)
        if terbaik["dibuang"]:
            h.catatan.append(f"{len(terbaik['dibuang'])} residu dibuang saat reseptor hasil relaksasi "
                             f"dijadikan PDBQT.")
    return h


def teks_metode(h, opsi=None, en=False):
    """Paragraf metode untuk naskah."""
    opsi = opsi or OpsiIF()
    n = len(h.residu)
    if en:
        return (f"Induced-fit docking followed the Glide/Prime protocol of Sherman et al. (2006) implemented with open "
                f"tools: side chains of the {n} residues within {opsi.radius:g} Å of the initially docked ligand were "
                f"truncated to alanine and the ligand was redocked into this softened pocket with AutoDock Vina "
                f"(exhaustiveness {opsi.exhaustiveness}); the full side chains were then restored and the "
                f"protein-ligand complex was energy-minimised with OpenMM (Amber14 protein force field, OpenFF/NAGL "
                f"ligand parameters, OBC2 implicit solvent), with the pocket side chains free and all other heavy "
                f"atoms harmonically restrained ({opsi.kekang:g} kcal/mol/Å²); finally the ligand was redocked into "
                f"the relaxed, rigid receptor. Reported scores are docking scores, not binding free energies, and "
                f"scores obtained on different receptor conformations are not directly comparable.")
    return (f"Docking induced fit mengikuti protokol Glide/Prime Sherman dkk. (2006) dengan program bebas: rantai "
            f"samping {n} residu dalam radius {opsi.radius:g} Å dari pose awal dipangkas menjadi alanina, lalu ligan "
            f"didocking ulang pada kantong yang dilunakkan itu dengan AutoDock Vina (exhaustiveness "
            f"{opsi.exhaustiveness}); rantai samping dikembalikan utuh dan kompleks protein-ligan diminimisasi dengan "
            f"OpenMM (medan gaya protein Amber14, parameter ligan OpenFF/NAGL, pelarut implisit OBC2) dengan rantai "
            f"samping kantong bebas bergerak dan atom berat lain dikekang harmonik ({opsi.kekang:g} kkal/mol/Å²); "
            f"terakhir ligan didocking ulang pada reseptor hasil relaksasi yang dibuat kaku. Skor yang dilaporkan "
            f"adalah skor docking, bukan energi bebas ikatan, dan skor pada konformasi reseptor yang berbeda tidak "
            f"dibandingkan langsung.")
