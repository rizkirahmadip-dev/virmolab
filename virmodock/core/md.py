"""Dinamika molekul (MD) dan MM/GBSA dengan OpenMM - dijalankan di proses terpisah (lihat jalankan_tugas).

Medan gaya: protein Amber ff14SB, ion Li/Merz (amber14/tip3p.xml), ligan OpenFF Sage 2.3.0 dengan muatan
parsial OpenFF NAGL (openff-gnn-am1bcc-1.0.0, setara AM1-BCC; AmberTools tidak tersedia di Windows).
Pelarut implisit: OBC2 (Onufriev-Bashford-Case, Amber igb=5, radii mbondi2) dengan GBSAOBCForce native
(jauh lebih cepat di CPU daripada CustomGBForce). Pelarut eksplisit: TIP3P, PME, NaCl 0,15 M.

MM/GBSA satu-trajektori: ΔG = G(kompleks) − G(reseptor) − G(ligan) dari koordinat yang sama;
komponen ΔE_vdW, ΔE_elek, ΔG_GB (polar), ΔG_SA (nonpolar, ACE). Energi internal saling meniadakan;
entropi konformasi TIDAK dihitung - nilai dipakai untuk peringkat relatif, bukan ΔG absolut.
Kutip: Eastman dkk. 2024 (OpenMM 8); Boothroyd dkk. 2023 (OpenFF Sage); Maier dkk. 2015 (ff14SB);
Onufriev dkk. 2004 (OBC); Genheden & Ryde 2015 (MM/GBSA).
"""
import io
import json
import math
import sys
import time
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

SITASI = [
    "Eastman P, Galvelis R, Peláez RP, et al. OpenMM 8: molecular dynamics simulation with machine learning potentials. "
    "J Phys Chem B. 2024;128(1):109-116. doi:10.1021/acs.jpcb.3c06662",
    "Maier JA, Martinez C, Kasavajhala K, Wickstrom L, Hauser KE, Simmerling C. ff14SB: improving the accuracy of protein "
    "side chain and backbone parameters from ff99SB. J Chem Theory Comput. 2015;11(8):3696-3713. "
    "doi:10.1021/acs.jctc.5b00255",
    "Boothroyd S, Behara PK, Madin OC, et al. Development and benchmarking of Open Force Field 2.0.0: the Sage small "
    "molecule force field. J Chem Theory Comput. 2023;19(11):3251-3275. doi:10.1021/acs.jctc.3c00039",
    "Wang L, Behara PK, Thompson MW, et al. The Open Force Field Initiative: open software and open science for "
    "molecular modeling. J Phys Chem B. 2024;128(29):7043-7067. doi:10.1021/acs.jpcb.4c01558",
    "OpenFF NAGL (graph neural network partial charges), model openff-gnn-am1bcc-1.0.0. Open Force Field Initiative. "
    "https://github.com/openforcefield/openff-nagl",
    "Onufriev A, Bashford D, Case DA. Exploring protein native states and large-scale conformational changes with a "
    "modified generalized Born model. Proteins. 2004;55(2):383-394. doi:10.1002/prot.20033",
    "Genheden S, Ryde U. The MM/PBSA and MM/GBSA methods to estimate ligand-binding affinities. Expert Opin Drug Discov. "
    "2015;10(5):449-461. doi:10.1517/17460441.2015.1032936",
]
KKAL = 4.184                 # kJ -> kkal
MODEL_NAGL = "openff-gnn-am1bcc-1.0.0.pt"
OFFXML = "openff-2.3.0.offxml"
LOGAM_RESN = {"ZN", "MG", "CA", "MN", "FE", "FE2", "CU", "CU1", "CO", "NI"}
VARIAN = {"HID", "HIE", "HIP", "ASH", "GLH", "LYN", "CYX", "CYM"}


class GalatMD(Exception):
    pass


@dataclass
class OpsiMD:
    pelarut: str = "implisit"        # implisit (OBC2) | eksplisit (TIP3P/PME)
    ns: float = 1.0                  # lama produksi
    suhu: float = 300.0              # K
    langkah_fs: float = 2.0          # dengan kendala ikatan-H
    interval_ps: float = 10.0        # simpan frame tiap … ps
    ekuilibrasi_ps: float = 100.0    # NVT (+ NPT untuk eksplisit), atom berat dikekang
    padding_nm: float = 1.0
    ion_molar: float = 0.15
    platform: str = "auto"           # auto | OpenCL | CUDA | CPU
    frame_mmgbsa: int = 25           # jumlah frame (merata) untuk MM/GBSA rata-rata
    kekang: float = 5.0              # kkal/mol/Å², atom berat protein saat minimisasi MM/GBSA
    seed: int = 42
    replika: int = 1                 # jumlah replika independen (1-5, bawaan 1, saran 3)


# ------------------------------------------------------------------ alat dasar
def _diam():
    warnings.filterwarnings("ignore")
    import logging
    for n in ("openff", "openmmforcefields", "pint"):
        logging.getLogger(n).setLevel(logging.ERROR)


def tersedia():
    try:
        import openmm
        import openff.toolkit
        import openmmforcefields.generators
        _ = (openmm, openff.toolkit, openmmforcefields.generators)
        return True
    except Exception:
        return False


def _jalur_offxml():
    import openforcefields
    f = Path(openforcefields.__file__).parent / "offxml" / OFFXML
    if not f.exists():
        raise GalatMD(f"Parameter OpenFF {OFFXML} tidak ditemukan.")
    return str(f)


def _jalur_nagl():
    import openff.nagl_models as nm
    f = Path(nm.__file__).parent / "models" / "am1bcc" / MODEL_NAGL
    if not f.exists():
        raise GalatMD(f"Model muatan NAGL {MODEL_NAGL} tidak ditemukan.")
    return str(f)


def platform_terbaik(pilih="auto"):
    """(nama, Platform, properti) - CUDA → OpenCL → CPU; tiap kandidat diuji dengan konteks kecil."""
    import openmm as mm
    urut = ["CUDA", "OpenCL", "CPU"] if pilih == "auto" else [pilih, "CPU"]
    galat = []
    for nama in urut:
        try:
            p = mm.Platform.getPlatformByName(nama)
        except Exception:
            continue   # platform tidak tersedia di komputer ini (mis. tanpa CUDA): coba kandidat berikutnya
        prop = {"Precision": "mixed"} if nama in ("CUDA", "OpenCL") else {}
        try:
            s = mm.System()
            s.addParticle(1.0)
            ctx = mm.Context(s, mm.VerletIntegrator(0.001), p, prop)
            del ctx
            return nama, p, prop
        except Exception as e:
            galat.append(f"{nama}: {str(e).splitlines()[0][:120]}")
    raise GalatMD("Tidak ada platform OpenMM yang bisa dipakai: " + "; ".join(galat))


# ------------------------------------------------------------------ ligan
_cache_muatan = {}


def ligan_openff(mol):
    """RDKit Mol (dengan H, konformer pose) -> OpenFF Molecule bermuatan NAGL (cache per SMILES)."""
    _diam()
    from openff.toolkit import Molecule
    from openff.units import unit as offunit
    off = Molecule.from_rdkit(mol, allow_undefined_stereo=True, hydrogens_are_explicit=True)
    kunci = off.to_smiles(mapped=True)
    q = _cache_muatan.get(kunci)
    if q is None:
        from openff.nagl import GNNModel
        model = GNNModel.load(_jalur_nagl(), eval_mode=True)
        q = np.asarray(model.compute_property(off, check_domains=True, error_if_unsupported=True), dtype=float)
        # koreksi pembulatan kecil agar jumlah tepat = muatan formal
        q += (float(off.total_charge.m_as(offunit.elementary_charge)) - q.sum()) / len(q)
        _cache_muatan[kunci] = q
    off.partial_charges = q * offunit.elementary_charge
    off.name = "LIG"
    return off


# ------------------------------------------------------------------ reseptor & kompleks
def _baris_logam(teks_pdbqt):
    """Ion logam dari PDBQT reseptor -> baris HETATM PDB (resn/atom = simbol)."""
    out = []
    for b in teks_pdbqt.splitlines():
        if b.startswith("HETATM") and b[17:20].strip().upper() in LOGAM_RESN:
            resn = b[17:20].strip().upper()
            resn = {"FE2": "FE", "CU1": "CU"}.get(resn, resn)
            el = resn[:2].capitalize() if len(resn) > 1 else resn
            out.append(f"HETATM{len(out) + 1:5d} {resn:>3s}  {resn:>3s} M{len(out) + 1:4d}    "
                       f"{b[30:54]}  1.00  0.00          {el.upper():>2s}")
    return out


def bangun_ff(molekul_off, pelarut="implisit"):
    _diam()
    from openmm import app
    from openmmforcefields.generators import SMIRNOFFTemplateGenerator
    ff = app.ForceField("amber14-all.xml", "amber14/tip3p.xml")
    gen = SMIRNOFFTemplateGenerator(molecules=list(molekul_off), forcefield=_jalur_offxml())
    ff.registerTemplateGenerator(gen.generator)
    return ff


def _pakai_flex(baris, flex):
    """Koordinat rantai samping residu fleksibel pose -> reseptor; H residu itu dibuang agar dibangun ulang."""
    from .mesin import terapkan_flex
    res = set()
    for b in flex.splitlines():
        if b.startswith("BEGIN_RES"):
            s = b.split()
            if len(s) >= 4:
                res.add((s[2], s[3]))
    teks = terapkan_flex("\n".join(baris), flex)
    keluar = []
    for b in teks.splitlines():
        nama = b[12:16].strip()
        hidrogen = b[76:78].strip() == "H" or nama.startswith("H")
        # H rantai samping residu fleksibel dibangun ulang; H amida tulang punggung (H/HN) tetap
        if b.startswith("ATOM") and (b[21], b[22:26].strip()) in res and hidrogen and nama not in ("H", "HN"):
            continue
        keluar.append(b)
    return keluar


def siapkan_kompleks(teks_reseptor, teks_pdbqt_reseptor, mol_ligan, ph=7.4, lapor=None, flex=None):
    """Reseptor (PDB, boleh sudah ber-H dari PDB2PQR/PROPKA) + ion logam + ligan pose -> Modeller kompleks.
    flex: blok residu fleksibel pose docking (rantai samping diposisikan seperti di pose).
    Kembalikan (ff, modeller, info) dengan info = {n_reseptor, idx_ligan, logam, atom_ditambah, muatan_ligan}."""
    _diam()
    from openmm import app, unit
    from pdbfixer import PDBFixer
    log = lapor or (lambda s: None)
    baris = [b for b in teks_reseptor.splitlines() if b.startswith(("ATOM", "TER"))]
    if flex and flex.strip():
        baris = _pakai_flex(baris, flex)
    logam = _baris_logam(teks_pdbqt_reseptor or "")
    varian_nama = {}
    for b in baris:
        if b.startswith("ATOM") and b[17:20].strip() in VARIAN:
            varian_nama[(b[21], b[22:27].strip())] = b[17:20].strip()
    teks = "\n".join(baris + logam + ["END"]) + "\n"
    fx = PDBFixer(pdbfile=io.StringIO(teks))
    fx.findMissingResidues()
    fx.missingResidues = {}               # celah rantai tidak dibangun (tidak ada informasi struktur)
    fx.findNonstandardResidues()
    fx.replaceNonstandardResidues()
    fx.findMissingAtoms()
    ditambah = sum(len(v) for v in fx.missingAtoms.values())
    fx.addMissingAtoms()
    off = ligan_openff(mol_ligan)
    ff = bangun_ff([off])
    m = app.Modeller(fx.topology, fx.positions)
    var = []
    for r in m.topology.residues():
        var.append(varian_nama.get((r.chain.id, str(r.id).strip())) if r.name in ("HIS", "ASP", "GLU", "LYS", "CYS")
                   or r.name in VARIAN else None)
    # H yang sudah ada (PDB2PQR/PROPKA, posisi teroptimasi) dipertahankan; hanya yang hilang ditambahkan.
    # Varian His/Asp/Glu/Lys/Cys mengikuti keadaan protonasi preparasi reseptor docking.
    m.addHydrogens(ff, pH=ph, variants=var)
    n_rec = m.topology.getNumAtoms()
    lig_top = off.to_topology().to_openmm()
    pos = unit.Quantity(mol_ligan.GetConformer().GetPositions(), unit.angstrom)
    m.add(lig_top, pos)
    idx_lig = list(range(n_rec, m.topology.getNumAtoms()))
    log(f"Kompleks: {n_rec} atom reseptor (+{ditambah} atom berat dilengkapi), {len(idx_lig)} atom ligan, "
        f"{len(logam)} ion logam")
    return ff, m, {"n_reseptor": n_rec, "idx_ligan": idx_lig, "logam": len(logam), "atom_ditambah": ditambah,
                   "muatan_ligan": float(sum(off.partial_charges.m))}


# ------------------------------------------------------------------ sistem implisit & MM/GBSA
def sistem_implisit(ff, topologi, grup=True):
    """Sistem OBC2 native: NonbondedForce (grup 1), GB polar (grup 2), SA ACE (grup 3), lainnya grup 0."""
    import openmm as mm
    from openmm import app
    from openmm.app.internal.customgbforces import GBSAOBC2Force
    s = ff.createSystem(topologi, nonbondedMethod=app.NoCutoff, constraints=app.HBonds, rigidWater=True)
    nb = next(f for f in s.getForces() if isinstance(f, mm.NonbondedForce))
    par = GBSAOBC2Force.getStandardParameters(topologi)
    polar = mm.GBSAOBCForce()
    sa = mm.GBSAOBCForce()
    for g in (polar, sa):
        g.setSoluteDielectric(1.0)
        g.setSolventDielectric(78.5)
        g.setNonbondedMethod(mm.GBSAOBCForce.NoCutoff)
    polar.setSurfaceAreaEnergy(0.0)
    for i, (r, skala) in enumerate(par):
        q = nb.getParticleParameters(i)[0]
        polar.addParticle(q, r, skala)
        sa.addParticle(0.0, r, skala)       # muatan nol -> hanya suku permukaan (ACE)
    s.addForce(polar)
    s.addForce(sa)
    if grup:
        for f in s.getForces():
            f.setForceGroup(0)
        nb.setForceGroup(1)
        polar.setForceGroup(2)
        sa.setForceGroup(3)
    return s


def _tanpa_muatan(sistem):
    """Salinan sistem dengan muatan NonbondedForce nol (untuk memisah vdW dari elektrostatik)."""
    import openmm as mm
    s = mm.XmlSerializer.deserialize(mm.XmlSerializer.serialize(sistem))
    nb = next(f for f in s.getForces() if isinstance(f, mm.NonbondedForce))
    for i in range(nb.getNumParticles()):
        q, sg, ep = nb.getParticleParameters(i)
        nb.setParticleParameters(i, 0.0, sg, ep)
    for i in range(nb.getNumExceptions()):
        a, b, qq, sg, ep = nb.getExceptionParameters(i)
        nb.setExceptionParameters(i, a, b, 0.0, sg, ep)
    return s


class Penilai:
    """Energi komponen (kkal/mol) untuk satu bagian (kompleks/reseptor/ligan) - konteks dibuat sekali."""

    def __init__(self, ff, topologi, platform):
        import openmm as mm
        nama, p, prop = platform
        self.s = sistem_implisit(ff, topologi)
        self.c = mm.Context(self.s, mm.VerletIntegrator(0.001), p, prop)
        self.c0 = mm.Context(_tanpa_muatan(self.s), mm.VerletIntegrator(0.001), p, prop)

    def energi(self, pos_nm):
        def e(ctx, grup):
            return ctx.getState(getEnergy=True, groups={grup}).getPotentialEnergy()._value / KKAL
        self.c.setPositions(pos_nm)
        self.c0.setPositions(pos_nm)
        nb, gb, sa = e(self.c, 1), e(self.c, 2), e(self.c, 3)
        vdw = e(self.c0, 1)
        return {"vdw": vdw, "elek": nb - vdw, "gb": gb, "sa": sa, "total": nb + gb + sa + e(self.c, 0)}


def _sub_topologi(modeller, simpan):
    from openmm import app
    m = app.Modeller(modeller.topology, modeller.positions)
    m.delete([a for a in m.topology.atoms() if a.index not in simpan])
    return m.topology


class MMGBSA:
    """MM/GBSA satu-trajektori untuk satu kompleks (topologi tetap; banyak frame)."""

    def __init__(self, ff, modeller, info, platform):
        n = modeller.topology.getNumAtoms()
        lig = set(info["idx_ligan"])
        self.i_rec = np.array([i for i in range(n) if i not in lig])
        self.i_lig = np.array(sorted(lig))
        self.k = Penilai(ff, modeller.topology, platform)
        self.r = Penilai(ff, _sub_topologi(modeller, set(self.i_rec.tolist())), platform)
        self.l = Penilai(ff, _sub_topologi(modeller, lig), platform)

    def frame(self, pos_nm):
        pos_nm = np.asarray(pos_nm)
        ek, er, el = self.k.energi(pos_nm), self.r.energi(pos_nm[self.i_rec]), self.l.energi(pos_nm[self.i_lig])
        d = {k: ek[k] - er[k] - el[k] for k in ("vdw", "elek", "gb", "sa")}
        d["dG"] = d["vdw"] + d["elek"] + d["gb"] + d["sa"]
        return d


def minimisasi(ff, modeller, info, platform, kekang=5.0, iterasi=2000, toleransi=10.0):
    """Minimisasi kompleks di pelarut implisit; atom berat reseptor dikekang harmonik (kkal/mol/Å²)."""
    import openmm as mm
    from openmm import unit
    nama, p, prop = platform
    s = sistem_implisit(ff, modeller.topology, grup=False)
    pos = np.asarray(modeller.positions.value_in_unit(unit.nanometer))
    if kekang > 0:
        k = mm.CustomExternalForce("0.5*kk*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
        k.addGlobalParameter("kk", kekang * KKAL * 100.0)      # kkal/mol/Å² -> kJ/mol/nm²
        for nm in ("x0", "y0", "z0"):
            k.addPerParticleParameter(nm)
        lig = set(info["idx_ligan"])
        for a in modeller.topology.atoms():
            if a.index not in lig and a.element is not None and a.element.symbol != "H":
                k.addParticle(a.index, pos[a.index].tolist())
        s.addForce(k)
    c = mm.Context(s, mm.VerletIntegrator(0.001), p, prop)
    c.setPositions(pos)
    mm.LocalEnergyMinimizer.minimize(c, toleransi, iterasi)
    return c.getState(getPositions=True).getPositions(asNumpy=True).value_in_unit(unit.nanometer)


def mmgbsa_pose(teks_reseptor, teks_pdbqt_reseptor, mol_ligan, opsi=None, platform=None, lapor=None, flex=None):
    """Minimisasi + MM/GBSA satu pose. -> dict komponen (kkal/mol) + info."""
    opsi = opsi or OpsiMD()
    t0 = time.time()
    platform = platform or platform_terbaik(opsi.platform)
    ff, m, info = siapkan_kompleks(teks_reseptor, teks_pdbqt_reseptor, mol_ligan, lapor=lapor, flex=flex)
    pos = minimisasi(ff, m, info, platform, opsi.kekang)
    h = MMGBSA(ff, m, info, platform).frame(pos)
    h.update(platform=platform[0], detik=round(time.time() - t0, 1), atom=m.topology.getNumAtoms(),
             atom_ditambah=info["atom_ditambah"], logam=info["logam"])
    return h, (ff, m, info, pos)


# ------------------------------------------------------------------ geometri
def kabsch(p, q):
    """Rotasi+translasi yang menempatkan p (N×3) paling dekat ke q -> (R, cp, cq): p' = (p - cp) @ R + cq."""
    cp, cq = p.mean(0), q.mean(0)
    h = (p - cp).T @ (q - cq)
    u, _s, vt = np.linalg.svd(h)
    d = np.sign(np.linalg.det(u @ vt))
    dd = np.diag([1.0, 1.0, d])
    return u @ dd @ vt, cp, cq


def rmsd(a, b):
    return float(np.sqrt(((a - b) ** 2).sum(1).mean()))


# ------------------------------------------------------------------ MD
def _platform_eksplisit_ok(nama):
    return nama in ("CUDA", "OpenCL")


def siapkan_md(ff, modeller, info, opsi, lapor=None):
    """Sistem MD + indeks atom zat terlarut. Eksplisit: solvasi TIP3P + NaCl, PME, barostat."""
    import openmm as mm
    from openmm import app, unit
    log = lapor or (lambda s: None)
    n_terlarut = modeller.topology.getNumAtoms()
    if opsi.pelarut == "eksplisit":
        m = app.Modeller(modeller.topology, modeller.positions)
        m.addSolvent(ff, model="tip3p", padding=opsi.padding_nm * unit.nanometer,
                     ionicStrength=opsi.ion_molar * unit.molar, neutralize=True)
        s = ff.createSystem(m.topology, nonbondedMethod=app.PME, nonbondedCutoff=1.0 * unit.nanometer,
                            constraints=app.HBonds, rigidWater=True, ewaldErrorTolerance=5e-4)
        s.addForce(mm.MonteCarloBarostat(1.0 * unit.bar, opsi.suhu * unit.kelvin, 25))
        log(f"Solvasi: {m.topology.getNumAtoms()} atom (air TIP3P, NaCl {opsi.ion_molar} M, tepi {opsi.padding_nm} nm)")
    else:
        m = modeller
        s = sistem_implisit(ff, m.topology, grup=False)
    return s, m, n_terlarut


class _Batal(Exception):
    pass


def jalankan_md(ff, modeller, info, opsi, folder, platform=None, lapor=None, progres=None, berhenti=None,
                pos_awal=None):
    """MD: minimisasi -> ekuilibrasi (atom berat dikekang, NVT[/NPT]) -> produksi. Frame zat terlarut disimpan
    ke frames.npy; checkpoint tiap ±5 menit (lanjut otomatis bila folder berisi checkpoint & meta cocok).
    progres(persen, teks); berhenti() -> True untuk menjeda (checkpoint lalu keluar)."""
    import openmm as mm
    from openmm import app, unit
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    log = lapor or (lambda s: None)
    pg = progres or (lambda p, t: None)
    berhenti = berhenti or (lambda: False)
    platform = platform or platform_terbaik(opsi.platform)
    nama, p, prop = platform
    if pos_awal is not None:
        modeller = app.Modeller(modeller.topology, unit.Quantity(pos_awal, unit.nanometer))
    s, m, n_terlarut = siapkan_md(ff, modeller, info, opsi, lapor)
    dt = opsi.langkah_fs / 1000.0
    n_eq = int(round(opsi.ekuilibrasi_ps / dt))
    n_prod = int(round(opsi.ns * 1000.0 / dt))
    tiap = max(1, int(round(opsi.interval_ps / dt)))
    # kekang ekuilibrasi (dimatikan saat produksi lewat parameter global)
    k = mm.CustomExternalForce("0.5*kk*periodicdistance(x,y,z,x0,y0,z0)^2" if opsi.pelarut == "eksplisit"
                               else "0.5*kk*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
    k.addGlobalParameter("kk", 10.0 * KKAL * 100.0)
    for nm_ in ("x0", "y0", "z0"):
        k.addPerParticleParameter(nm_)
    pos0 = np.asarray(m.positions.value_in_unit(unit.nanometer))
    for a in m.topology.atoms():
        if a.index < n_terlarut and a.element is not None and a.element.symbol != "H":
            k.addParticle(a.index, pos0[a.index].tolist())
    s.addForce(k)
    integ = mm.LangevinMiddleIntegrator(opsi.suhu * unit.kelvin, 1.0 / unit.picosecond, dt * unit.picoseconds)
    integ.setRandomNumberSeed(opsi.seed)
    sim = app.Simulation(m.topology, s, integ, p, prop)
    meta = {"pelarut": opsi.pelarut, "ns": opsi.ns, "dt": dt, "tiap": tiap, "n_eq": n_eq, "n_prod": n_prod,
            "atom": m.topology.getNumAtoms(), "n_terlarut": n_terlarut, "suhu": opsi.suhu, "seed": opsi.seed}
    f_cp, f_meta, f_frame = folder / "checkpoint.chk", folder / "md_meta.json", folder / "frames.npy"
    frames, langkah = [], 0
    if f_cp.exists() and f_meta.exists():
        lama = json.loads(f_meta.read_text(encoding="utf-8"))
        if {k_: lama.get(k_) for k_ in meta} == meta:
            sim.loadCheckpoint(str(f_cp))
            langkah = int(lama.get("langkah", 0))
            if f_frame.exists():
                frames = list(np.load(f_frame))
            log(f"Melanjutkan dari checkpoint: langkah {langkah:,} dari {n_eq + n_prod:,}")
        else:
            log("Checkpoint lama tidak cocok dengan pengaturan sekarang; mulai dari awal.")
    if langkah == 0:
        sim.context.setPositions(m.positions)
        pg(1, "Minimisasi energi…")
        mm.LocalEnergyMinimizer.minimize(sim.context, 10.0, 2000)
        sim.context.setVelocitiesToTemperature(opsi.suhu * unit.kelvin, opsi.seed)
    total = n_eq + n_prod
    blok = max(tiap, 500)
    t_cp = time.time()
    t_mulai, l_mulai = time.time(), langkah

    def simpan_cp():
        sim.saveCheckpoint(str(f_cp))
        np.save(f_frame, np.asarray(frames, dtype=np.float32) if frames else np.zeros((0, n_terlarut, 3), np.float32))
        f_meta.write_text(json.dumps(dict(meta, langkah=langkah), indent=1), encoding="utf-8")

    while langkah < total:
        produksi = langkah >= n_eq
        sim.context.setParameter("kk", 0.0 if produksi else 10.0 * KKAL * 100.0)
        if produksi:
            n = min(tiap - ((langkah - n_eq) % tiap), total - langkah)
        else:
            n = min(blok, n_eq - langkah)
        sim.step(n)
        langkah += n
        if langkah > n_eq and (langkah - n_eq) % tiap == 0:
            st = sim.context.getState(getPositions=True, enforcePeriodicBox=False)
            frames.append(st.getPositions(asNumpy=True).value_in_unit(unit.nanometer)[:n_terlarut].astype(np.float32))
        laju = (langkah - l_mulai) / max(1e-6, time.time() - t_mulai)
        sisa = (total - langkah) / laju if laju > 0 else 0
        ns_hari = laju * dt / 1000.0 * 86400.0
        tahap = "Produksi" if langkah > n_eq else "Ekuilibrasi"
        pg(2 + 93 * langkah / total, f"{tahap}: {(langkah - n_eq) * dt / 1000 if langkah > n_eq else langkah * dt:.2f} "
           f"{'ns' if langkah > n_eq else 'ps'} · {ns_hari:.1f} ns/hari · sisa ±{_durasi(sisa)}")
        if time.time() - t_cp > 300:
            simpan_cp()
            t_cp = time.time()
        if berhenti():
            simpan_cp()
            raise _Batal()
    simpan_cp()
    akhir = sim.context.getState(getPositions=True, getEnergy=True)
    return np.asarray(frames, dtype=np.float32), meta, akhir.getPositions(asNumpy=True).value_in_unit(unit.nanometer)


def _durasi(detik):
    detik = int(max(0, detik))
    if detik < 90:
        return f"{detik} dtk"
    if detik < 5400:
        return f"{detik // 60} mnt"
    return f"{detik // 3600} j {detik % 3600 // 60} mnt"


# ------------------------------------------------------------------ analisis trajektori
def analisis_trajektori(modeller, info, frames):
    """RMSD ligan & Cα protein (setelah superposisi Cα ke frame awal), RMSF Cα per residu."""
    top = modeller.topology
    atoms = list(top.atoms())
    ca = [a.index for a in atoms if a.name == "CA" and a.residue.name not in LOGAM_RESN
          and a.element is not None and a.element.symbol == "C"]
    lig = [i for i in info["idx_ligan"] if atoms[i].element.symbol != "H"]
    if not len(frames) or not ca:
        return {}
    ref = frames[0]
    rm_ca, rm_lig, sejajar = [], [], []
    for f in frames:
        R, cp, cq = kabsch(f[ca], ref[ca])
        g = (f - cp) @ R + cq
        sejajar.append(g)
        rm_ca.append(rmsd(g[ca], ref[ca]) * 10)
        rm_lig.append(rmsd(g[lig], ref[lig]) * 10)
    sejajar = np.asarray(sejajar)
    rata = sejajar[:, ca].mean(0)
    rmsf = np.sqrt(((sejajar[:, ca] - rata) ** 2).sum(2).mean(0)) * 10
    label = [f"{atoms[i].residue.name}{atoms[i].residue.id} {atoms[i].residue.chain.id}" for i in ca]
    return {"rmsd_ca": rm_ca, "rmsd_ligan": rm_lig, "rmsf": rmsf.tolist(), "residu": label}


def tulis_pdb(topologi, pos_nm, f):
    from openmm import app, unit
    if not hasattr(pos_nm, "value_in_unit"):
        pos_nm = unit.Quantity(np.asarray(pos_nm, dtype=float), unit.nanometer)
    with open(f, "w", encoding="utf-8") as h:
        app.PDBFile.writeFile(topologi, pos_nm, h, keepIds=True)


def tulis_dcd(topologi, frames, f, dt_ps):
    from openmm import app, unit
    with open(f, "wb") as h:
        d = app.DCDFile(h, topologi, dt_ps * unit.picoseconds)
        for x in frames:
            d.writeModel(unit.Quantity(np.asarray(x, dtype=float), unit.nanometer))


# ------------------------------------------------------------------ uji kecepatan & saran (A8a)
def uji_kecepatan(ff, modeller, info, opsi, platform=None, detik=8.0):
    """Ukur ns/hari sistem pengguna sendiri (beberapa detik). Eksplisit: termasuk solvasi."""
    import openmm as mm
    from openmm import unit
    platform = platform or platform_terbaik(opsi.platform)
    nama, p, prop = platform
    s, m, _n = siapkan_md(ff, modeller, info, opsi)
    integ = mm.LangevinMiddleIntegrator(opsi.suhu * unit.kelvin, 1.0 / unit.picosecond,
                                        opsi.langkah_fs / 1000.0 * unit.picoseconds)
    c = mm.Context(s, integ, p, prop)
    c.setPositions(m.positions)
    mm.LocalEnergyMinimizer.minimize(c, 50.0, 200)
    c.setVelocitiesToTemperature(opsi.suhu * unit.kelvin, opsi.seed)
    integ.step(20)
    n, t0 = 0, time.time()
    while time.time() - t0 < detik:
        integ.step(50)
        n += 50
    c.getState(getEnergy=True)
    dt = time.time() - t0
    return {"platform": nama, "atom": m.topology.getNumAtoms(),
            "ns_hari": n * opsi.langkah_fs / 1e6 / dt * 86400.0, "pelarut": opsi.pelarut}


def saran(ns_hari, ns, n_ligan=1):
    """Status A8a dari perkiraan waktu: Disarankan (< 2 j) / Bisa (lama, 2-12 j) / Tidak disarankan (> 12 j)."""
    jam = ns * n_ligan / max(ns_hari, 1e-9) * 24.0
    status = "disarankan" if jam < 2 else "bisa" if jam <= 12 else "tidak"
    return status, jam


# ------------------------------------------------------------------ pekerja (proses terpisah)
def _mol_pose(item):
    """Pose ligan -> RDKit Mol ber-H: dari SDF (mis. *_terbaik.sdf keluaran CLI) atau PDBQT masukan + blok pose."""
    if item.get("sdf"):
        from rdkit import Chem
        mol = Chem.MolFromMolFile(str(item["sdf"]), removeHs=False)
        if mol is None:
            raise GalatMD(f"SDF pose tidak terbaca: {item['sdf']}")
        if not any(a.GetAtomicNum() == 1 for a in mol.GetAtoms()):
            mol = Chem.AddHs(mol, addCoords=True)
        return mol
    from . import analisis
    masuk = Path(item["pdbqt_masukan"]).read_text(errors="replace")
    return analisis.pose_mol(masuk, item["pose_pdbqt"])


def _interaksi_frame(modeller, info, frames, mol, stride=1):
    """Frekuensi interaksi (residu|jenis) di sepanjang trajektori - kriteria sama dengan analisis docking."""
    from rdkit import Chem
    from . import analisis
    top = modeller.topology
    atoms = list(top.atoms())
    lig = info["idx_ligan"]
    rec_idx = [i for i in range(len(atoms)) if i not in set(lig)]
    hitung, n = {}, 0
    for f in frames[::stride]:
        x = np.asarray(f, dtype=float) * 10.0
        baris = []
        for j, i in enumerate(rec_idx):
            a = atoms[i]
            el = a.element.symbol if a.element is not None else "C"
            baris.append(f"ATOM  {j + 1:5d} {a.name:<4s} {a.residue.name:>3s} {a.residue.chain.id[:1]:1s}"
                         f"{int(''.join(c for c in str(a.residue.id) if c.isdigit()) or 0):4d}    "
                         f"{x[i, 0]:8.3f}{x[i, 1]:8.3f}{x[i, 2]:8.3f}  1.00  0.00          {el:>2s}")
        rec = analisis.baca_reseptor("\n".join(baris))
        m = Chem.Mol(mol)
        conf = m.GetConformer()
        for k_, i in enumerate(lig):
            conf.SetAtomPosition(k_, x[i].tolist())
        for h in {f"{d['residu']}|{d['jenis']}" for d in analisis.interaksi(rec, m) if d["jenis"] != "vdw"}:
            hitung[h] = hitung.get(h, 0) + 1
        n += 1
    return {k: v / n for k, v in sorted(hitung.items(), key=lambda kv: -kv[1])} if n else {}


def jalankan_tugas(f_tugas):
    """Pekerja: baca tugas JSON, cetak 'PROGRES p teks' / 'LOG teks', tulis hasil.json di folder keluaran.
    tugas = {mode: mmgbsa|md|uji, folder, reseptor: {pdb, pdbqt}, ligan: [{nama, lid, job, pdbqt_masukan,
    pose_pdbqt, peringkat, energi_docking}], opsi: {…OpsiMD}}"""
    _diam()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except (AttributeError, ValueError):
        pass
    t = json.loads(Path(f_tugas).read_text(encoding="utf-8"))
    out = Path(t["folder"])
    out.mkdir(parents=True, exist_ok=True)
    opsi = OpsiMD(**{k: v for k, v in (t.get("opsi") or {}).items() if k in OpsiMD.__dataclass_fields__})
    f_stop = out / "BERHENTI"
    f_stop.unlink(missing_ok=True)

    def log(s):
        print("LOG " + s.replace("\n", " "), flush=True)

    def pg(p, s):
        print(f"PROGRES {p:.1f} {s}", flush=True)

    rec_pdb = Path(t["reseptor"]["pdb"]).read_text(errors="replace")
    rec_pdbqt = Path(t["reseptor"]["pdbqt"]).read_text(errors="replace") if t["reseptor"].get("pdbqt") else ""
    platform = platform_terbaik(opsi.platform)
    log(f"OpenMM platform: {platform[0]}")
    hasil = {"mode": t["mode"], "opsi": asdict(opsi), "platform": platform[0], "ligan": [], "versi": _versi(),
             "mulai": time.strftime("%Y-%m-%d %H:%M:%S")}
    f_hasil = out / "hasil.json"
    if t["mode"] == "md" and f_hasil.exists():       # lanjutan: pertahankan ligan yang sudah selesai
        lama = json.loads(f_hasil.read_text(encoding="utf-8"))
        # hanya bila hasil lama berasal dari tugas MD yang sama persis (mode & opsi); selain itu mulai baru
        if lama.get("mode") == "md" and lama.get("opsi") == asdict(opsi):
            hasil["ligan"] = [x for x in lama.get("ligan", []) if x.get("selesai") and x.get("trajektori") is not None]
    selesai = {(x.get("lid"), x.get("job"), x.get("peringkat")) for x in hasil["ligan"]}
    n = len(t["ligan"])
    for i, it in enumerate(t["ligan"]):
        kunci = (it.get("lid"), it.get("job"), it.get("peringkat"))
        if kunci in selesai:
            continue
        dasar = 100.0 * i / n
        rentang = 100.0 / n
        d = {k: it.get(k) for k in ("nama", "lid", "job", "peringkat", "energi_docking")}
        try:
            mol = _mol_pose(it)
            pg(dasar, f"{it['nama']}: menyiapkan kompleks (ff14SB + OpenFF Sage, muatan NAGL)…")
            ff, m, info = siapkan_kompleks(rec_pdb, rec_pdbqt, mol, lapor=log, flex=it.get("flex"))
            if t["mode"] == "uji":
                for pel in ("implisit", "eksplisit"):
                    o = OpsiMD(**dict(asdict(opsi), pelarut=pel))
                    pg(dasar + rentang * (0.2 if pel == "implisit" else 0.6), f"Uji kecepatan {pel}…")
                    d[f"uji_{pel}"] = uji_kecepatan(ff, m, info, o, platform)
                    log(f"Uji kecepatan {pel}: {d[f'uji_{pel}']['ns_hari']:.1f} ns/hari "
                        f"({d[f'uji_{pel}']['atom']} atom, {platform[0]})")
                d["selesai"] = True
                hasil["ligan"].append(d)
                continue
            pg(dasar + rentang * 0.1, f"{it['nama']}: minimisasi + MM/GBSA…")
            pos = minimisasi(ff, m, info, platform, opsi.kekang)
            nilai = MMGBSA(ff, m, info, platform)
            d["mmgbsa_min"] = nilai.frame(pos)
            d.update(atom=m.topology.getNumAtoms(), atom_ditambah=info["atom_ditambah"], logam=info["logam"])
            sub = out / f"{_aman(it['nama'])}_{it.get('peringkat', 1)}"
            sub.mkdir(exist_ok=True)
            tulis_pdb(m.topology, pos, sub / "kompleks_minimisasi.pdb")
            log(f"{it['nama']}: MM/GBSA (minimisasi) ΔG {d['mmgbsa_min']['dG']:.2f} kkal/mol")
            if t["mode"] == "md":
                from . import md_analisis
                n_rep = max(1, getattr(opsi, "replika", 1))
                daftar_rep = []

                for r_idx in range(n_rep):
                    seed_rep = opsi.seed + r_idx * 100
                    o_rep = OpsiMD(**dict(asdict(opsi), seed=seed_rep))
                    sub_target = (sub / f"replika_{r_idx + 1}") if n_rep > 1 else sub
                    sub_target.mkdir(exist_ok=True)
                    f_rep = sub_target / "replika_selesai.json"
                    if f_rep.exists():  # dilanjutkan setelah jeda: replika yang sudah tuntas tidak disimulasikan ulang
                        try:
                            daftar_rep.append(json.loads(f_rep.read_text(encoding="utf-8")))
                            log(f"{it['nama']}: replika {r_idx + 1} sudah selesai sebelumnya, dilewati.")
                            continue
                        except ValueError:
                            f_rep.unlink(missing_ok=True)

                    def pg_md(p, s, dasar=dasar, rentang=rentang, nm=it["nama"], r=r_idx + 1, n_tot=n_rep):
                        prefix_rep = f" [Rep {r}/{n_tot}]" if n_tot > 1 else ""
                        pg(dasar + rentang * (0.15 + 0.6 * (r_idx + p / 100.0) / n_tot), f"{nm}{prefix_rep}: {s}")

                    try:
                        frames, meta, akhir = jalankan_md(ff, m, info, o_rep, sub_target, platform, log, pg_md,
                                                          berhenti=f_stop.exists, pos_awal=pos)
                    except _Batal:
                        d["dijeda"] = True
                        hasil["ligan"].append(d)
                        hasil["dijeda"] = True
                        f_hasil.write_text(json.dumps(hasil, indent=1, ensure_ascii=False), encoding="utf-8")
                        log("Dijeda - checkpoint tersimpan; jalankan lagi untuk melanjutkan.")
                        return 3

                    top_t = _sub_topologi(m, set(range(meta["n_terlarut"])))
                    tulis_pdb(top_t, frames[0] if len(frames) else pos, sub_target / "topologi.pdb")
                    tulis_dcd(top_t, frames, sub_target / "trajektori_terlarut.dcd", opsi.interval_ps)

                    traj = analisis_trajektori(m, info, frames)
                    pilih = np.unique(np.linspace(0, len(frames) - 1, min(opsi.frame_mmgbsa, len(frames))).astype(int)) \
                        if len(frames) else []
                    seri = [nilai.frame(frames[j]) for j in pilih]
                    mmgbsa_fr = [dict(x, t_ns=float((j + 1) * opsi.interval_ps / 1000.0)) for x, j in zip(seri, pilih)]
                    mmgbsa_res = {}
                    if seri:
                        v = np.array([x["dG"] for x in seri])
                        mmgbsa_res = {k: float(np.mean([x[k] for x in seri])) for k in ("vdw", "elek", "gb", "sa", "dG")}
                        mmgbsa_res["sd"] = float(v.std(ddof=1)) if len(v) > 1 else 0.0
                        mmgbsa_res["sem"] = mmgbsa_res["sd"] / math.sqrt(len(v)) if len(v) > 1 else 0.0
                        mmgbsa_res["n"] = len(v)

                    # Analisis MD lanjutan lengkap versi 2 (F2)
                    analisis_v2 = md_analisis.analisis_lengkap(m, info, frames, mol, dt_ps=opsi.interval_ps)

                    rep_item = {
                        "replika": r_idx + 1,
                        "seed": seed_rep,
                        "folder": sub_target.name,
                        "trajektori": traj,
                        "mmgbsa": mmgbsa_res,
                        "mmgbsa_frame": mmgbsa_fr,
                        "analisis": analisis_v2,
                        "interaksi_frek": analisis_v2.get("interaksi_frek", {}),
                        "md": {k: meta[k] for k in ("pelarut", "ns", "atom", "suhu", "seed")},
                    }
                    daftar_rep.append(rep_item)
                    f_rep.write_text(json.dumps(rep_item, ensure_ascii=False), encoding="utf-8")
                    (sub_target / "checkpoint.chk").unlink(missing_ok=True)

                # Replika pertama sebagai hasil utama
                rep_utama = daftar_rep[0]
                d["trajektori"] = rep_utama["trajektori"]
                d["mmgbsa"] = rep_utama["mmgbsa"]
                d["mmgbsa_frame"] = rep_utama["mmgbsa_frame"]
                d["interaksi_frek"] = rep_utama["interaksi_frek"]
                d["analisis"] = rep_utama["analisis"]
                d["md"] = rep_utama["md"]
                d["replika"] = daftar_rep

                if len(daftar_rep) > 1:
                    d_rm_lig = [float(np.mean(r["trajektori"].get("rmsd_ligan") or [0.0])) for r in daftar_rep]
                    d_rm_ca = [float(np.mean(r["trajektori"].get("rmsd_ca") or [0.0])) for r in daftar_rep]
                    d_rg = [float(np.mean(r["analisis"].get("rg") or [0.0])) for r in daftar_rep]
                    d_dg = [float(r["mmgbsa"].get("dG", 0.0)) for r in daftar_rep if r.get("mmgbsa")]

                    d["replika_agregat"] = {
                        "rmsd_ligan": [float(np.mean(d_rm_lig)), float(np.std(d_rm_lig, ddof=1)) if len(d_rm_lig) > 1 else 0.0],
                        "rmsd_ca": [float(np.mean(d_rm_ca)), float(np.std(d_rm_ca, ddof=1)) if len(d_rm_ca) > 1 else 0.0],
                        "rg": [float(np.mean(d_rg)), float(np.std(d_rg, ddof=1)) if len(d_rg) > 1 else 0.0],
                        "mmgbsa_dG": [float(np.mean(d_dg)), float(np.std(d_dg, ddof=1)) if len(d_dg) > 1 else 0.0] if d_dg else [0.0, 0.0],
                    }
            d["selesai"] = True
            d["folder"] = sub.name
        except Exception as e:
            d["galat"] = (str(e).strip().splitlines() or [type(e).__name__])[0][:300]
            log(f"{it['nama']}: GAGAL - {d['galat']}")
        hasil["ligan"].append(d)
        f_hasil.write_text(json.dumps(hasil, indent=1, ensure_ascii=False), encoding="utf-8")
    hasil["selesai"] = time.strftime("%Y-%m-%d %H:%M:%S")
    hasil.pop("dijeda", None)
    f_hasil.write_text(json.dumps(hasil, indent=1, ensure_ascii=False), encoding="utf-8")
    pg(100, "Selesai")
    return 0 if any(x.get("selesai") for x in hasil["ligan"]) else 1


def _aman(nama):
    import re
    return re.sub(r"[^\w.\-]+", "_", nama).strip("._")[:60] or "ligan"


def _versi():
    out = {}
    for m, n in (("openmm", "OpenMM"), ("openff.toolkit", "OpenFF Toolkit"), ("openff.nagl", "OpenFF NAGL")):
        try:
            mod = __import__(m, fromlist=["__version__"])
            out[n] = getattr(mod, "__version__", "") or getattr(getattr(mod, "version", None), "short_version", "")
        except Exception:
            pass
    out["Sage"] = OFFXML.replace(".offxml", "")
    out["NAGL model"] = MODEL_NAGL.replace(".pt", "")
    return out
