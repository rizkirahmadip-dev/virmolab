"""Mesin docking dengan antarmuka seragam: AutoDock-GPU (OpenCL), AutoDock Vina, AutoDock4.

Modul ini murni: hanya menyusun berkas masukan, daftar argumen program, dan
membaca keluaran. Eksekusi (QProcess, jeda, batal) ada di core/antrean.py.
"""
import hashlib
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import paths

RT = 0.001987207 * 298.15  # kcal/mol pada 298,15 K
URUT_TIPE = ["A", "C", "N", "NA", "NS", "OA", "OS", "SA", "S", "HD", "HS", "P", "F", "Cl", "Br", "I", "Si",
             "Mg", "Ca", "Mn", "Zn", "Fe", "Cu"]
ELEMEN = {"A": "C", "C": "C", "H": "H", "HD": "H", "HS": "H", "N": "N", "NA": "N", "NS": "N", "O": "O", "OA": "O",
          "OS": "O", "S": "S", "SA": "S", "P": "P", "F": "F", "I": "I", "CL": "Cl", "BR": "Br", "MG": "Mg", "ZN": "Zn",
          "FE": "Fe", "MN": "Mn", "CA": "Ca", "CU": "Cu", "NI": "Ni", "CO": "Co", "SI": "Si"}
MESIN = {"adgpu": "AutoDock-GPU", "vina": "AutoDock Vina", "ad4": "AutoDock4", "unidock": "Uni-Dock"}


def label_mesin(j):
    """Nama mesin job untuk tampilan. Job impor menyimpan pose bergaya Vina tetapi berasal dari program lain."""
    return j.get("label_mesin") or MESIN.get(j.get("mesin"), j.get("mesin") or "")
PROGRAM = {"adgpu": "autodock_gpu.exe", "vina": "vina.exe", "ad4": "autodock4.exe"}

# pesan AD-GPU yang menandakan OpenCL/GPU tidak bisa dipakai -> pindah ke Vina
RE_GALAT_OPENCL = re.compile(r"Error: cl[A-Z]\w*\(|No suitable OpenCL|Cannot allocate device memory|"
                             r"Cannot copy memory to device|does not have a suitable device|OpenCL\.dll", re.I)
# kode keluar Windows: DLL tidak ditemukan / entry point hilang (driver OpenCL rusak atau tidak ada)
KODE_GALAT_DLL = {-1073741515, 3221225781, -1073741511, 3221225785}


@dataclass
class Kotak:
    pusat: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    ukuran: list = field(default_factory=lambda: [22.5, 22.5, 22.5])
    spasi: float = 0.375

    def npts(self):
        """Titik grid per sumbu (genap, 10-126) untuk AutoGrid."""
        hasil = []
        for u in self.ukuran:
            n = int(math.ceil(float(u) / self.spasi))
            n += n % 2
            hasil.append(max(10, min(n, 126)))
        return hasil

    def terpotong(self):
        """True bila ukuran melebihi 126 titik pada spasi saat ini."""
        return any(math.ceil(float(u) / self.spasi) > 126 for u in self.ukuran)


@dataclass
class Parameter:
    mesin: str = "adgpu"           # adgpu | vina | ad4
    perangkat: str = "gpu"         # gpu | cpu
    nrun: int = 50                 # AD-GPU / AD4 ga_run
    nev: int = 2500000             # AD-GPU --nev / AD4 ga_num_evals
    heuristik: bool = True         # AD-GPU --heuristics
    exhaustiveness: int = 8        # Vina
    num_modes: int = 9             # Vina
    energy_range: float = 3.0      # Vina
    cpu: int = 0                   # Vina thread (0 = otomatis)
    pop: int = 150                 # AD4 ga_pop_size
    seed: int = 42                 # 0 = acak
    devnum: int = 0                # GPU OpenCL untuk AD-GPU (0 = bawaan/perangkat pertama)

    def ke_dict(self):
        return asdict(self)


@dataclass
class Pose:
    peringkat: int
    energi: float                  # kcal/mol (afinitas Vina / ΔG perkiraan AutoDock)
    rmsd_lb: float = 0.0           # Vina: terhadap pose terbaik; AutoDock: RMSD terhadap pusat klaster
    rmsd_ub: float = 0.0
    klaster: int = 0               # ukuran klaster (AutoDock)
    rmsd_ref: float = -1.0         # AutoDock: RMSD terhadap koordinat ligan masukan (redocking)
    pdbqt: str = ""                # koordinat pose (blok MODEL)
    flex: str = ""                 # residu fleksibel pada pose ini (BEGIN_RES…END_RES), kosong bila reseptor kaku

    @property
    def ki(self):
        return ki_terbaca(self.energi)

    def ke_dict(self, dengan_koordinat=False):
        d = asdict(self)
        if not dengan_koordinat:
            d.pop("pdbqt")
            d.pop("flex")
        return d


def ki_terbaca(dg):
    """Ki perkiraan dari ΔG (kcal/mol), satuan yang mudah dibaca."""
    try:
        ki = math.exp(dg / RT)
    except OverflowError:
        return ""
    for batas, satuan, kali in ((1e-9, "pM", 1e12), (1e-6, "nM", 1e9), (1e-3, "µM", 1e6), (1.0, "mM", 1e3)):
        if ki < batas:
            return f"{ki * kali:.2f} {satuan}"
    return f"{ki:.2f} M"


def tersedia(mesin):
    if mesin == "unidock":          # program Linux di WSL; status diperiksa di latar (core/unidock.py)
        from .unidock import tersedia as ud
        return ud()
    return paths.program(PROGRAM[mesin]) is not None


# ---------------------------------------------------------- tipe atom & grid
def tipe_atom(teks):
    t = set()
    for b in teks.splitlines():
        if b.startswith(("ATOM", "HETATM")):
            s = b[77:].split()
            if s:
                t.add(s[0])
    return t


def urut_tipe(t):
    return sorted(t, key=lambda x: (URUT_TIPE.index(x) if x in URUT_TIPE else 99, x))


def tipe_peta(tipe_ligan):
    """Tipe yang perlu peta AutoGrid: atom makrosiklik CG* -> C, G* (dummy) dilewati."""
    hasil = set()
    for t in tipe_ligan:
        if re.match(r"^G\d$", t):
            continue
        hasil.add("C" if re.match(r"^CG\d$", t) else t)
    return urut_tipe(hasil)


def tulis_gpf(teks_reseptor, tipe_ligan, kotak, nama="reseptor"):
    rt = urut_tipe(tipe_atom(teks_reseptor))
    lt = tipe_peta(tipe_ligan)
    n = kotak.npts()
    c = kotak.pusat
    baris = [f"npts {n[0]} {n[1]} {n[2]}", f"gridfld {nama}.maps.fld", f"spacing {kotak.spasi}",
             "receptor_types " + " ".join(rt), "ligand_types " + " ".join(lt), f"receptor {nama}.pdbqt",
             f"gridcenter {float(c[0]):.3f} {float(c[1]):.3f} {float(c[2]):.3f}", "smooth 0.5"]
    baris += [f"map {nama}.{t}.map" for t in lt]
    baris += [f"elecmap {nama}.e.map", f"dsolvmap {nama}.d.map", "dielectric -0.1465"]
    return "\n".join(baris) + "\n"


def grid_siap(folder, gpf):
    """Peta grid bisa dipakai ulang bila GPF identik dan semua peta ada."""
    f = Path(folder) / "reseptor.gpf"
    if not f.exists() or f.read_text() != gpf:
        return False
    peta = re.findall(r"^(?:map|elecmap|dsolvmap)\s+(\S+)", gpf, re.M)
    return (Path(folder) / "reseptor.maps.fld").exists() and all((Path(folder) / p).exists() for p in peta)


def perintah_autogrid(folder):
    return [paths.program("autogrid4.exe"), "-p", "reseptor.gpf", "-l", "reseptor.glg"], str(folder)


def hash_teks(t):
    return hashlib.sha1(t.encode()).hexdigest()[:12]


# --------------------------------------------------------------- perintah
def perintah_adgpu(fld, lig, basis, p, devnum=None, flex=None):
    devnum = devnum or getattr(p, "devnum", 0) or None
    cmd = [paths.program("autodock_gpu.exe"), "--ffile", str(fld)] + (["--lfile", str(lig)] if lig else []) + [
           "--nrun", str(p.nrun), "--resnam", str(basis), "--xmloutput", "0", "--heuristics", "1" if p.heuristik else "0"]
    if not p.heuristik:  # heuristik aktif: jumlah evaluasi ditentukan AD-GPU dari ukuran ligan
        cmd += ["--nev", str(p.nev)]
    if p.seed:
        cmd += ["--seed", str(p.seed)]
    if devnum:
        cmd += ["--devnum", str(devnum)]
    if flex:
        cmd += ["--flexres", str(flex)]
    return cmd


def perintah_vina(rec, lig, keluaran, kotak, p, flex=None):
    c, s = kotak.pusat, kotak.ukuran
    cmd = [paths.program("vina.exe"), "--receptor", str(rec), "--ligand", str(lig),
           "--center_x", f"{c[0]:.3f}", "--center_y", f"{c[1]:.3f}", "--center_z", f"{c[2]:.3f}",
           "--size_x", f"{s[0]:.2f}", "--size_y", f"{s[1]:.2f}", "--size_z", f"{s[2]:.2f}",
           "--exhaustiveness", str(p.exhaustiveness), "--num_modes", str(p.num_modes),
           "--energy_range", f"{p.energy_range:g}", "--out", str(keluaran)]
    if p.seed:
        cmd += ["--seed", str(p.seed)]
    if p.cpu:
        cmd += ["--cpu", str(p.cpu)]
    if flex:
        cmd += ["--flex", str(flex)]
    return cmd


def tulis_dpf(teks_ligan, nama_ligan, folder_grid, p):
    """DPF AutoDock4 (LGA, parameter standar ADT). Peta dirujuk dengan jalur relatif terhadap folder grid."""
    lt = urut_tipe(tipe_atom(teks_ligan))
    xs = [(float(b[30:38]), float(b[38:46]), float(b[46:54])) for b in teks_ligan.splitlines()
          if b.startswith(("ATOM", "HETATM"))]
    about = [sum(x[i] for x in xs) / len(xs) for i in range(3)] if xs else [0, 0, 0]
    m = re.search(r"TORSDOF\s+(\d+)", teks_ligan)
    g = Path(folder_grid)
    baris = ["autodock_parameter_version 4.2", "outlev 1", "intelec",
             f"seed {p.seed} {p.seed + 1}" if p.seed else "seed pid time",
             "ligand_types " + " ".join(lt), f"fld {(g / 'reseptor.maps.fld').as_posix()}"]
    baris += [f"map {(g / f'reseptor.{t}.map').as_posix()}" for t in lt]
    baris += [f"elecmap {(g / 'reseptor.e.map').as_posix()}", f"desolvmap {(g / 'reseptor.d.map').as_posix()}",
              f"move {nama_ligan}", f"about {about[0]:.4f} {about[1]:.4f} {about[2]:.4f}",
              "tran0 random", "quaternion0 random", "dihe0 random", f"torsdof {m.group(1) if m else 0}",
              "rmstol 2.0", "extnrg 1000.0", "e0max 0.0 10000", f"ga_pop_size {p.pop}", f"ga_num_evals {p.nev}",
              "ga_num_generations 27000", "ga_elitism 1", "ga_mutation_rate 0.02", "ga_crossover_rate 0.8",
              "ga_window_size 10", "ga_cauchy_alpha 0.0", "ga_cauchy_beta 1.0", "set_ga", "sw_max_its 300",
              "sw_max_succ 4", "sw_max_fail 4", "sw_rho 1.0", "sw_lb_rho 0.01", "ls_search_freq 0.06", "set_psw1",
              "unbound_model bound", f"ga_run {p.nrun}", "analysis"]
    return "\n".join(baris) + "\n"


def perintah_ad4(dpf, dlg):
    return [paths.program("autodock4.exe"), "-p", str(dpf), "-l", str(dlg)]


# --------------------------------------------------------------- progres
RE_VINA_BINTANG = re.compile(r"^\*+$")
RE_ADGPU_GEN = re.compile(r"^\s*(\d+)\s*\|\s*(\d+)\s*\|")
RE_AD4_RUN = re.compile(r"Run (\d+) of (\d+)")
RE_ADGPU_TOTAL = re.compile(r"or (\d+) evaluations")


class PembacaProgres:
    """Ubah keluaran program (stdout baris demi baris) menjadi persen 0-100."""

    def __init__(self, mesin, p):
        self.mesin, self.p = mesin, p
        self.bintang = 0
        self.total = p.nev

    def baca(self, teks):
        if self.mesin == "vina":
            # Vina mencetak 51 bintang bertahap di satu baris
            self.bintang += teks.count("*")
            if self.bintang:
                return min(99, int(self.bintang / 51 * 100))
            return None
        if self.mesin == "adgpu":
            m = RE_ADGPU_TOTAL.search(teks)
            if m:  # batas evaluasi sesungguhnya (heuristik bisa mengubah --nev)
                self.total = int(m.group(1))
                return 0
            m = RE_ADGPU_GEN.match(teks)
            if m and self.total:
                # kolom kedua = evaluasi per run (semua run berjalan paralel); AutoStop bisa selesai lebih awal
                return min(99, int(int(m.group(2)) / self.total * 100))
            return None
        m = RE_AD4_RUN.search(teks)  # AD4 menulis ke .dlg: baris dibaca dari berkas, bukan stdout
        if m:
            return min(99, int((int(m.group(1)) - 1) / max(1, int(m.group(2))) * 100))
        return None


# ----------------------------------------------------------------- hasil
RE_ENERGI = re.compile(r"Estimated Free Energy of Binding\s*=\s*([-+]?\d+\.?\d*)")
RE_RUN = re.compile(r"Run\s*=\s*(\d+)")
RE_KLASTER = re.compile(r"^\s*(\d+)\s*\|\s*([-+]?\d+\.\d+)\s*\|\s*(\d+)\s*\|\s*([-+]?\d+\.\d+)\s*\|\s*(\d+)\s*\|")
RE_RANKING = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+([-+]?\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+RANKING")


def baca_dlg(path):
    """Pose AutoDock(-GPU) dari .dlg: satu pose terbaik per klaster, urut energi.

    Ditambah RMSD terhadap pusat klaster & ukuran klaster dari tabel histogram.
    """
    pose_run, energi, run, atom, flex, di_flex = {}, None, None, [], [], False
    klaster, ranking = [], []
    with open(path, errors="replace") as f:
        for b in f:
            if b.startswith("DOCKED:"):
                isi = b[8:].rstrip("\n")
                if isi.startswith("MODEL"):
                    energi, run, atom, flex, di_flex = None, None, [], [], False
                elif isi.startswith("BEGIN_RES"):      # residu fleksibel (dipisah dari pose ligan)
                    di_flex = True
                    flex.append(isi)
                elif isi.startswith("END_RES"):
                    flex.append(isi)
                    di_flex = False
                elif isi.startswith(("ATOM", "HETATM", "ROOT", "ENDROOT", "BRANCH", "ENDBRANCH", "TORSDOF")):
                    (flex if di_flex else atom).append(isi)
                elif isi.startswith("REMARK") and di_flex:   # REMARK SMILES aduk kovalen
                    flex.append(isi)
                elif isi.startswith("ENDMDL"):
                    if energi is not None and not atom and flex:   # docking kovalen: ligan = aduk di blok flexres
                        from .kovalen import ubah_pose
                        kv = ubah_pose(flex)
                        if kv:
                            atom, flex = kv[0].splitlines(), kv[1].splitlines()
                    if energi is not None and atom:
                        pose_run[run or len(pose_run) + 1] = (energi, "\n".join(atom), "\n".join(flex))
                else:
                    m = RE_ENERGI.search(isi)
                    if m:
                        energi = float(m.group(1))
                    m = RE_RUN.search(isi)
                    if m:
                        run = int(m.group(1))
                continue
            m = RE_KLASTER.match(b)
            if m:
                klaster.append((int(m.group(1)), float(m.group(2)), int(m.group(3)), int(m.group(5))))
                continue
            m = RE_RANKING.match(b)
            if m:
                ranking.append((int(m.group(1)), int(m.group(3)), float(m.group(4)), float(m.group(5)),
                                float(m.group(6))))
    hasil = []
    if klaster and ranking:
        # pose wakil tiap klaster = run dengan energi terendah di klaster tsb (urutan pertama di ranking)
        for rank, e_terbaik, run_terbaik, n in klaster:
            anggota = [r for r in ranking if r[0] == rank]
            wakil = anggota[0] if anggota else None
            run_w = wakil[1] if wakil else run_terbaik
            if run_w in pose_run:
                e, teks, fx = pose_run[run_w]
                hasil.append(Pose(peringkat=rank, energi=wakil[2] if wakil else e,
                                  rmsd_lb=wakil[3] if wakil else 0.0, rmsd_ref=wakil[4] if wakil else -1.0,
                                  klaster=n, pdbqt=teks, flex=fx))
    if not hasil:
        for i, (e, teks, fx) in enumerate(sorted(pose_run.values(), key=lambda x: x[0]), 1):
            hasil.append(Pose(peringkat=i, energi=e, pdbqt=teks, flex=fx))
    hasil.sort(key=lambda p: p.energi)
    for i, p in enumerate(hasil, 1):
        p.peringkat = i
    return hasil


def baca_vina(path):
    hasil, teks, flex, e, lb, ub, di_flex = [], [], [], None, 0.0, 0.0, False
    with open(path, errors="replace") as f:
        for b in f:
            if b.startswith("MODEL"):
                teks, flex, e, di_flex = [], [], None, False
            elif b.startswith("BEGIN_RES"):           # residu fleksibel (Vina --flex)
                di_flex = True
                flex.append(b.rstrip("\n"))
            elif b.startswith("END_RES"):
                flex.append(b.rstrip("\n"))
                di_flex = False
            elif b.startswith("REMARK VINA RESULT:"):
                s = b.split()
                e, lb, ub = float(s[3]), float(s[4]), float(s[5])
            elif b.startswith("ENDMDL"):
                if e is not None:
                    hasil.append(Pose(peringkat=len(hasil) + 1, energi=e, rmsd_lb=lb, rmsd_ub=ub,
                                      pdbqt="\n".join(teks), flex="\n".join(flex)))
            elif not b.startswith("REMARK"):
                (flex if di_flex else teks).append(b.rstrip("\n"))
    return hasil


def baca_hasil(mesin, path):
    """Uni-Dock menulis PDBQT bergaya Vina."""
    return baca_vina(path) if mesin in ("vina", "unidock") else baca_dlg(path)


def pose_ke_pdb(pdbqt, resn="LIG"):
    """Blok pose PDBQT -> PDB (HETATM, kolom elemen) untuk viewer dan ekspor kompleks."""
    from .kovalen import atom_residu
    residu = atom_residu(pdbqt)          # pose kovalen: atom residu tampil lewat objek residu fleksibel
    baris = []
    for i, b in enumerate(x for x in pdbqt.splitlines() if x.startswith(("ATOM", "HETATM"))):
        if i in residu:
            continue
        tipe = b[77:].split()[0] if len(b) > 77 and b[77:].split() else "C"
        el = ELEMEN.get(tipe.upper(), "C" if re.match(r"^C?G\d$", tipe) else tipe[:2].capitalize())
        baris.append(("HETATM" + b[6:17] + f"{resn:>3}" + b[20:66]).ljust(76) + el.rjust(2))
    return "\n".join(baris) + "\nEND\n"


def flex_ke_pdb(flex):
    """Blok residu fleksibel PDBQT -> PDB (ATOM, nama residu asli) untuk viewer."""
    baris = []
    for b in flex.splitlines():
        if not b.startswith(("ATOM", "HETATM")):
            continue
        tipe = b[77:].split()[0] if len(b) > 77 and b[77:].split() else "C"
        el = ELEMEN.get(tipe.upper(), tipe[:2].capitalize())
        baris.append(("ATOM  " + b[6:66]).ljust(76) + el.rjust(2))
    return "\n".join(baris) + "\nEND\n"


def terapkan_flex(teks_pdb, flex):
    """Ganti koordinat atom residu fleksibel (cocok rantai/nomor/nama atom) di teks PDB reseptor dengan posisi pose."""
    pos = {}
    for b in flex.splitlines():
        if b.startswith(("ATOM", "HETATM")):
            try:
                pos[(b[21].strip(), int(b[22:26]), b[12:16].strip())] = b[30:54]
            except ValueError:
                pass
    if not pos:
        return teks_pdb
    keluar = []
    for b in teks_pdb.splitlines():
        if b.startswith(("ATOM", "HETATM")) and len(b) >= 54:
            try:
                k = (b[21].strip(), int(b[22:26]), b[12:16].strip())
            except ValueError:
                k = None
            if k in pos:
                b = b[:30] + pos[k] + b[54:]
        keluar.append(b)
    return "\n".join(keluar) + "\n"


def residu_flex(flex):
    """['THR199 A', …] dari blok flex (urut kemunculan)."""
    out = []
    for b in flex.splitlines():
        if b.startswith("BEGIN_RES"):
            s = b.split()
            if len(s) >= 4:
                out.append(f"{s[1]}{s[3]} {s[2]}")
    return out


def ringkas_galat(teks, n=600):
    """Ambil bagian akhir keluaran program yang paling informatif untuk pesan galat."""
    baris = [b for b in teks.splitlines() if b.strip()]
    penting = [b for b in baris if re.search(r"error|galat|fail|cannot|unable|invalid", b, re.I)]
    return "\n".join((penting or baris)[-8:])[-n:]
