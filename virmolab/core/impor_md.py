"""Impor trajektori dinamika molekul dari program lain dan analisis dengan pipa MD VirmoLab.

Topologi : PDB, GRO (GROMACS), PRMTOP/PARM7 (AMBER), PSF (CHARMM/NAMD), CIF.
Trajektori: XTC dan TRR (GROMACS), DCD (NAMD, CHARMM, OpenMM, ACEMD), NetCDF dan MDCRD (AMBER),
            serta PDB multi-MODEL dan GRO multi-frame.

Trajektori dibaca bertahap (frame terpilih saja, atom zat terlarut saja) supaya berkas berukuran puluhan GB tetap
muat di memori. Molekul yang terpotong batas kotak periodik diutuhkan lalu lompatan antarframe dihapus (setara
`gmx trjconv -pbc mol` + `-pbc nojump`), kemudian semua frame disejajarkan pada Cα frame pertama.

Hasilnya ditulis dalam format yang sama dengan MD internal (topologi.pdb, trajektori_terlarut.dcd, hasil.json),
sehingga RMSD, RMSF, Rg, SASA, ikatan H, okupansi interaksi, barcode, PCA, FEL, klaster, dan ekspor memakai kode
yang sama. MM/GBSA tidak dihitung ulang karena parameter medan gaya program asal tidak dibawa.
"""
import json
import math
import os
import re
import struct
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import catat

EKSTENSI_TOPOLOGI = (".pdb", ".ent", ".gro", ".prmtop", ".parm7", ".psf", ".cif", ".mmcif")
EKSTENSI_TRAJEKTORI = (".xtc", ".trr", ".dcd", ".nc", ".ncdf", ".netcdf", ".mdcrd", ".crd", ".x")
EKSTENSI_TRAJEKTORI_TEKS = (".pdb", ".gro")       # multi-frame, juga sah sebagai trajektori

AA = {"ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE", "LEU", "LYS", "MET", "PHE", "PRO",
      "SER", "THR", "TRP", "TYR", "VAL"}
PROTEIN = AA | {"HID", "HIE", "HIP", "HSD", "HSE", "HSP", "CYX", "CYM", "ASH", "GLH", "LYN", "ACE", "NME", "NMA",
                "NHE", "NH2", "MSE", "SEC", "PYL", "HYP", "CYZ", "CSO", "SEP", "TPO", "PTR", "HISD", "HISE",
                "HISH", "LSN", "ASPP", "GLUP"}
NUKLEAT = {"DA", "DT", "DG", "DC", "DU", "A", "U", "G", "C", "RA", "RU", "RG", "RC", "DA5", "DA3", "DT5", "DT3",
           "DG5", "DG3", "DC5", "DC3", "RA5", "RA3", "RU5", "RU3", "RG5", "RG3", "RC5", "RC3", "ADE", "THY", "GUA",
           "CYT", "URA"}
AIR = {"HOH", "WAT", "SOL", "TIP", "TIP3", "TIP4", "TIP5", "T3P", "T4P", "T5P", "SPC", "SPCE", "TP3", "H2O", "DOD",
       "TIP3P", "OPC", "OPC3", "HO4", "TP4", "TP5", "SWM4"}
ION_LAWAN = {"NA", "CL", "K", "SOD", "CLA", "POT", "NA+", "CL-", "K+", "CES", "CS", "LIT", "LI", "LI+", "CS+", "IP",
             "IM", "RB", "BR-", "IOD", "F-", "NIO", "CIO", "KIO"}
LIPID = {"POPC", "POPE", "POPG", "POPS", "POPA", "DPPC", "DMPC", "DOPC", "DOPE", "DOPS", "DLPC", "DLPE", "DSPC",
         "SDPC", "CHL1", "CHOL", "CHL", "PA", "PC", "OL", "PE", "PGR", "PS", "ST", "LA", "MY", "SA", "PLPC", "PSM",
         "SSM", "CER", "DPSM", "POP2", "PIP2", "SAPI", "DPPE", "DPPG", "DMPG"}
ION_UNSUR = {"NA": "Na", "SOD": "Na", "NA+": "Na", "CL": "Cl", "CLA": "Cl", "CL-": "Cl", "K": "K", "POT": "K",
             "K+": "K", "MG": "Mg", "MG2": "Mg", "MG+2": "Mg", "CA": "Ca", "CAL": "Ca", "CA2": "Ca", "ZN": "Zn",
             "ZN2": "Zn", "ZN+2": "Zn", "FE": "Fe", "FE2": "Fe", "FE3": "Fe", "MN": "Mn", "CU": "Cu", "CU1": "Cu",
             "CO": "Co", "NI": "Ni", "CD": "Cd", "HG": "Hg", "LI": "Li", "LIT": "Li", "CS": "Cs", "CES": "Cs",
             "RB": "Rb", "SR": "Sr", "BA": "Ba", "BR": "Br", "IOD": "I", "F": "F"}
_DUA_HURUF = {"CL", "BR", "NA", "MG", "ZN", "FE", "MN", "CU", "CO", "NI", "LI", "CS", "RB", "SR", "BA", "CD", "HG",
              "AL", "SI", "SE", "AU", "AG", "PT", "PB"}
AKMA_PS = 0.04888821       # satuan waktu CHARMM/NAMD (AKMA) dalam ps


class GalatImporMD(Exception):
    pass


# ------------------------------------------------------------------ topologi
@dataclass
class Topologi:
    """Topologi OpenMM + posisi awal (nm, bila berkas membawanya) + nama berkas asal."""
    top: object
    posisi: np.ndarray | None = None
    kotak: np.ndarray | None = None          # 3x3 nm
    sumber: str = ""
    catatan: list = field(default_factory=list)

    @property
    def n_atom(self):
        return self.top.getNumAtoms()


def _kelas_residu(resn, n_atom=0):
    r = resn.upper().strip()
    if r in AIR:
        return "air"
    if r in PROTEIN or (len(r) == 4 and r[0] in "NC" and r[1:] in PROTEIN):
        return "protein"
    if r in NUKLEAT:
        return "nukleat"
    if r in LIPID:
        return "lipid"
    if r in ION_LAWAN and n_atom <= 1:
        return "ion_lawan"
    if n_atom == 1 or (r.rstrip("+-0123456789") in ION_UNSUR and n_atom <= 1):
        return "ion"
    return "lain"


def _tebak_unsur(nama, resn, n_atom_residu, kelas):
    from openmm.app import element as E
    n = re.sub(r"[^A-Za-z]", "", nama).upper()
    if kelas in ("ion", "ion_lawan"):
        for c in (resn.upper().strip(), resn.upper().strip().rstrip("+-0123456789"), n):
            if c in ION_UNSUR:
                return E.get_by_symbol(ION_UNSUR[c])
        c = n[:2].capitalize() if n[:2] in _DUA_HURUF else n[:1]
    elif kelas in ("protein", "nukleat", "air", "lipid"):
        c = n[:1] if n else "C"
    else:   # ligan: Cl/Br dll. hanya bila nama diawali dua huruf itu (CL1, BR2), bukan C1/L
        c = n[:2].capitalize() if n[:2] in ("CL", "BR") else n[:1]
    try:
        return E.get_by_symbol(c or "C")
    except KeyError:
        return E.get_by_symbol("C")


def _bangun(baris_atom, beri_rantai=True, kotak=None):
    """[(nama, resn, resi, rantai, unsur|None, xyz_nm)] -> (Topology, posisi nm). Rantai kosong diberi huruf
    berdasarkan putus kerangka protein (jarak C(i-1)–N(i) > 2 Å) supaya label residu tetap unik."""
    from openmm import app
    from openmm.app import element as E
    n = len(baris_atom)
    xyz = np.array([b[5] for b in baris_atom], dtype=float).reshape(n, 3)
    # kelompokkan residu berurutan
    residu, cur, kunci_lama = [], [], None
    for i, b in enumerate(baris_atom):
        k = (b[1], b[2], b[3])
        if k != kunci_lama and cur:
            residu.append(cur)
            cur = []
        cur.append(i)
        kunci_lama = k
    if cur:
        residu.append(cur)
    kelas = [_kelas_residu(baris_atom[r[0]][1], len(r)) for r in residu]
    rantai_res = [baris_atom[r[0]][3].strip() for r in residu]
    if beri_rantai and not any(rantai_res):
        huruf, k_huruf, prev_c = "ABCDEFGHIJKLMNOPQRSTUVWXYZ", -1, None
        for j, r in enumerate(residu):
            if kelas[j] == "protein" or kelas[j] == "nukleat":
                nama = {baris_atom[i][0]: i for i in r}
                n_at = nama.get("N", nama.get("P"))
                if prev_c is None or n_at is None:
                    putus = True
                else:   # koordinat GRO/PDB sering terbungkus kotak periodik: ukur ke citra terdekat
                    d = xyz[n_at] - xyz[prev_c]
                    if kotak is not None and np.linalg.det(kotak) > 1e-6:
                        d = _citra_minimum(d, kotak, np.linalg.inv(kotak))
                    putus = np.linalg.norm(d) > 0.20
                if putus:
                    k_huruf += 1
                rantai_res[j] = huruf[k_huruf % 26]
                prev_c = nama.get("C", nama.get("O3'"))
            else:
                prev_c = None
                rantai_res[j] = ""
    top = app.Topology()
    rantai = {}
    ch_lama = None
    for j, r in enumerate(residu):
        cid = rantai_res[j]
        # rantai baru bila id berubah (residu non-polimer berurutan berbagi satu rantai)
        if cid != ch_lama or cid not in rantai:
            rantai[cid] = top.addChain(cid)
            ch_lama = cid
        b0 = baris_atom[r[0]]
        res = top.addResidue(b0[1], rantai[cid], id=str(b0[2]))
        for i in r:
            nama, resn = baris_atom[i][0], baris_atom[i][1]
            el = baris_atom[i][4]
            if el:
                try:
                    el = E.get_by_symbol(el.strip().capitalize())
                except KeyError:
                    el = None
            top.addAtom(nama, el or _tebak_unsur(nama, resn, len(r), kelas[j]), res)
    return top, xyz


def _baca_pdb_topologi(path):
    """Model pertama PDB, urutan atom persis seperti di berkas (gemmi bisa menata ulang residu)."""
    baris, kotak = [], None
    with open(path, encoding="utf-8", errors="replace") as f:
        for b in f:
            if b.startswith("CRYST1") and kotak is None:
                try:
                    a, bb, c, al, be, ga = (float(b[6:15]), float(b[15:24]), float(b[24:33]), float(b[33:40]),
                                            float(b[40:47]), float(b[47:54]))
                    if a > 2 and bb > 2 and c > 2:
                        kotak = kotak_dari_parameter(a / 10, bb / 10, c / 10, al, be, ga)
                except ValueError:
                    pass
            elif b.startswith(("ATOM", "HETATM")):
                try:
                    xyz = (float(b[30:38]) / 10, float(b[38:46]) / 10, float(b[46:54]) / 10)
                except ValueError:
                    continue
                resi = b[22:27].strip() or "0"
                el = b[76:78].strip() if len(b) >= 78 else ""
                baris.append((b[12:16].strip(), b[17:21].strip(), resi, b[21].strip(), el, xyz))
            elif b.startswith("ENDMDL") and baris:
                break
    if not baris:
        raise GalatImporMD("Tidak ada atom di berkas PDB topologi.")
    top, xyz = _bangun(baris, kotak=kotak)
    return Topologi(top, xyz, kotak, str(path))


def _baca_gro_frame(f, n_atom=None):
    """Satu frame GRO dari objek berkas -> (judul, baris atom, kotak 3x3 nm) atau None di akhir berkas."""
    judul = f.readline()
    if not judul:
        return None
    n = int(f.readline().strip())
    if n_atom is not None and n != n_atom:
        raise GalatImporMD(f"Frame GRO berisi {n} atom, topologi {n_atom}.")
    atom = [f.readline() for _ in range(n)]
    kotak = [float(x) for x in f.readline().split()]
    if len(kotak) == 3:
        B = np.diag(kotak)
    elif len(kotak) == 9:   # v1(x) v2(y) v3(z) v1(y) v1(z) v2(x) v2(z) v3(x) v3(y)
        B = np.array([[kotak[0], kotak[3], kotak[4]], [kotak[5], kotak[1], kotak[6]], [kotak[7], kotak[8], kotak[2]]])
    else:
        B = None
    return judul, atom, B


def _koordinat_gro(baris):
    """Kolom koordinat GRO berlebar tetap; presisi bisa lebih dari 3 desimal (lebar dari jarak titik desimal)."""
    b0 = baris[0]
    t1 = b0.find(".", 20)
    t2 = b0.find(".", t1 + 1)
    lebar = (t2 - t1) if t1 > 0 and t2 > 0 else 8
    xyz = np.empty((len(baris), 3))
    for i, b in enumerate(baris):
        xyz[i] = (float(b[20:20 + lebar]), float(b[20 + lebar:20 + 2 * lebar]), float(b[20 + 2 * lebar:20 + 3 * lebar]))
    return xyz


def _baca_gro_topologi(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        fr = _baca_gro_frame(f)
    if fr is None:
        raise GalatImporMD("Berkas GRO kosong.")
    _, atom, B = fr
    xyz = _koordinat_gro(atom)
    baris = [(b[10:15].strip(), b[5:10].strip(), b[0:5].strip(), "", "", tuple(p)) for b, p in zip(atom, xyz)]
    top, xyz = _bangun(baris, kotak=B)
    return Topologi(top, xyz, B, str(path))


def baca_topologi(path):
    """Berkas topologi -> Topologi. GRO/PDB membawa koordinat; PRMTOP/PSF hanya topologi."""
    p = Path(path)
    ext = p.suffix.lower()
    try:
        if ext in (".pdb", ".ent"):
            return _baca_pdb_topologi(p)
        if ext == ".gro":
            return _baca_gro_topologi(p)
        if ext in (".prmtop", ".parm7"):
            from openmm import app
            t = app.AmberPrmtopFile(str(p)).topology
            return Topologi(t, None, None, str(p))
        if ext == ".psf":
            from openmm import app
            t = app.CharmmPsfFile(str(p)).topology
            return Topologi(t, None, None, str(p))
        if ext in (".cif", ".mmcif"):
            from openmm import app
            c = app.PDBxFile(str(p))
            pos = np.array(c.getPositions(asNumpy=True)._value, dtype=float)
            return Topologi(c.topology, pos, None, str(p))
    except GalatImporMD:
        raise
    except Exception as e:
        raise GalatImporMD(f"Topologi {p.name} tidak terbaca: {e}")
    if ext == ".tpr":
        raise GalatImporMD("Berkas .tpr adalah biner GROMACS. Tulis koordinat acuan dulu, misalnya "
                           "`gmx editconf -f md.tpr -o ref.gro`, lalu pakai ref.gro sebagai topologi.")
    if ext == ".top":
        raise GalatImporMD("Topologi GROMACS .top tidak memuat koordinat atau nama atom per indeks secara langsung. "
                           "Pakai berkas .gro (mis. md.gro atau npt.gro) dari simulasi yang sama.")
    raise GalatImporMD(f"Format topologi {ext} belum didukung.")


def kotak_dari_parameter(a, b, c, alfa, beta, gama):
    """Panjang (nm) dan sudut (derajat) sel -> matriks kotak 3x3 (baris = vektor)."""
    al, be, ga = (math.radians(x) for x in (alfa, beta, gama))
    va = [a, 0.0, 0.0]
    vb = [b * math.cos(ga), b * math.sin(ga), 0.0]
    cx = c * math.cos(be)
    cy = c * (math.cos(al) - math.cos(be) * math.cos(ga)) / max(1e-9, math.sin(ga))
    cz = math.sqrt(max(0.0, c * c - cx * cx - cy * cy))
    return np.array([va, vb, [cx, cy, cz]], dtype=float)


# ------------------------------------------------------------------ pemilihan atom
def kelas_atom(top):
    """List kelas per atom (protein, nukleat, air, ion, ion_lawan, lipid, lain)."""
    out = []
    for r in top.residues():
        k = _kelas_residu(r.name, len(list(r.atoms())))
        out += [k] * len(list(r.atoms()))
    return out


def calon_ligan(top, kelas=None):
    """Residu bukan polimer/pelarut berisi ≥ 5 atom berat: [{kunci, label, atom, berat}] (terbesar dulu)."""
    kelas = kelas or kelas_atom(top)
    out = []
    i = 0
    for r in top.residues():
        atom = list(r.atoms())
        if kelas[atom[0].index] == "lain":
            berat = sum(1 for a in atom if a.element is not None and a.element.symbol != "H")
            if berat >= 5:
                kunci = f"{r.chain.id}|{r.name}|{r.id}"
                out.append({"kunci": kunci, "label": f"{r.name} {r.id}" + (f" {r.chain.id}" if r.chain.id else ""),
                            "atom": len(atom), "berat": berat, "indeks": [a.index for a in atom]})
        i += len(atom)
    out.sort(key=lambda x: -x["berat"])
    return out


def pilih_atom(top, ligan=None, ion_logam=True, lipid=False, kelas=None):
    """Indeks atom zat terlarut yang disimpan: polimer + ligan terpilih (+ ion logam, lipid)."""
    kelas = kelas or kelas_atom(top)
    lig = set()
    for c in calon_ligan(top, kelas):
        if c["kunci"] == ligan:
            lig = set(c["indeks"])
    sel = [a.index for a in top.atoms() if kelas[a.index] in ("protein", "nukleat") or a.index in lig
           or (kelas[a.index] == "ion" and ion_logam) or (kelas[a.index] == "lipid" and lipid)]
    return sel, sorted(lig)


def sub_topologi(top, indeks):
    """Topologi OpenMM berisi atom terpilih saja (urutan dipertahankan, ikatan internal disalin)."""
    from openmm import app
    pilih = set(indeks)
    baru = app.Topology()
    peta, rantai, residu = {}, {}, {}
    for a in top.atoms():
        if a.index not in pilih:
            continue
        r = a.residue
        if r.chain not in rantai:
            rantai[r.chain] = baru.addChain(r.chain.id)
        if r not in residu:
            residu[r] = baru.addResidue(r.name, rantai[r.chain], id=r.id, insertionCode=getattr(r, "insertionCode", ""))
        peta[a] = baru.addAtom(a.name, a.element, residu[r], id=a.id)
    for b in top.bonds():
        if b[0] in peta and b[1] in peta:
            baru.addBond(peta[b[0]], peta[b[1]])
    return baru


# ------------------------------------------------------------------ pembaca trajektori
class Pembaca:
    """Antarmuka: n_atom, n_frame, waktu (ps, array atau None), dt_ps (dari kepala berkas, bisa None),
    baca(indeks_frame_terurut, indeks_atom) -> iterator (indeks_frame, xyz_nm float32, kotak_nm 3x3|None)."""
    n_atom = 0
    n_frame = 0
    waktu = None
    dt_ps = None
    nama = ""

    def tutup(self):
        pass


class PembacaXTC(Pembaca):
    """XTC GROMACS. Offset tiap frame dipindai dari kepala (tanpa dekompresi); frame terpilih disalin ke berkas
    sementara per potongan lalu didekompresi dengan pembaca C bawaan OpenMM."""
    nama = "XTC"

    def __init__(self, path):
        self.path = str(path)
        self.offset, waktu = [], []
        ukuran = os.path.getsize(self.path)
        with open(self.path, "rb") as f:
            pos = 0
            while pos + 56 <= ukuran:
                f.seek(pos)
                h = f.read(96)
                magic, natom = struct.unpack(">ii", h[:8])
                if magic not in (1995, 2023):
                    if not self.offset:
                        raise GalatImporMD("Bukan berkas XTC (magic number tidak cocok).")
                    catat.log.warning(f"XTC {Path(path).name}: frame rusak di byte {pos}, sisanya diabaikan.")
                    break
                t = struct.unpack(">f", h[12:16])[0]
                if natom <= 9:
                    panjang = 56 + 12 * natom
                elif magic == 1995:
                    nb = struct.unpack(">i", h[88:92])[0]
                    panjang = 92 + (nb + 3) // 4 * 4
                else:
                    nb = struct.unpack(">q", h[88:96])[0]
                    panjang = 96 + (nb + 3) // 4 * 4
                if pos + panjang > ukuran:      # frame terakhir terpotong (simulasi terhenti)
                    break
                self.offset.append((pos, panjang))
                waktu.append(t)
                self.n_atom = natom
                pos += panjang
        if not self.offset:
            raise GalatImporMD("Berkas XTC tidak berisi frame utuh.")
        self.n_frame = len(self.offset)
        self.waktu = np.array(waktu, dtype=float)

    def baca(self, indeks, atom):
        from openmm.app.internal.xtc_utils import read_xtc
        atom = np.asarray(atom)
        per_potong = max(1, int(1.5e8 // max(1, self.n_atom * 12)))
        with open(self.path, "rb") as f, tempfile.TemporaryDirectory(prefix="vmd_xtc_") as d:
            tmp = Path(d, "potong.xtc")
            for a in range(0, len(indeks), per_potong):
                bagian = indeks[a:a + per_potong]
                with open(tmp, "wb") as g:
                    for i in bagian:
                        f.seek(self.offset[i][0])
                        g.write(f.read(self.offset[i][1]))
                xyz, kotak, _, _ = read_xtc(str(tmp).encode("utf-8"))
                for k, i in enumerate(bagian):
                    yield i, np.ascontiguousarray(xyz[atom, :, k], dtype=np.float32), np.asarray(kotak[:, :, k])


class PembacaTRR(Pembaca):
    """TRR GROMACS (presisi tunggal/ganda). Frame tanpa koordinat (hanya kecepatan/gaya) dilewati."""
    nama = "TRR"

    def __init__(self, path):
        self.path = str(path)
        self.frame = []      # (offset x, nyata, offset kotak|None)
        waktu = []
        ukuran = os.path.getsize(self.path)
        with open(self.path, "rb") as f:
            pos = 0
            while pos + 24 < ukuran:
                f.seek(pos)
                try:
                    magic, _slen, n_str = struct.unpack(">iii", f.read(12))
                except struct.error:
                    break
                if magic != 1993:
                    if not self.frame:
                        raise GalatImporMD("Bukan berkas TRR (magic number tidak cocok).")
                    break
                f.read((n_str + 3) // 4 * 4)
                (ir, e, box, vir, pres, top, sym, x, v, fz, natom, _step, _nre) = struct.unpack(">13i", f.read(52))
                if box:
                    nyata = box // 9
                elif x:
                    nyata = x // (natom * 3)
                elif v:
                    nyata = v // (natom * 3)
                else:
                    nyata = fz // (natom * 3) if fz else 4
                fmt = ">2d" if nyata == 8 else ">2f"
                t, _lam = struct.unpack(fmt, f.read(2 * nyata))
                awal = f.tell()
                off_box = awal + ir + e if box else None
                off_x = awal + ir + e + box + vir + pres + top + sym
                total = ir + e + box + vir + pres + top + sym + x + v + fz
                if awal + total > ukuran:
                    break
                if x:
                    self.frame.append((off_x, nyata, off_box))
                    waktu.append(t)
                    self.n_atom = natom
                pos = awal + total
        if not self.frame:
            raise GalatImporMD("Berkas TRR tidak berisi frame koordinat.")
        self.n_frame = len(self.frame)
        self.waktu = np.array(waktu, dtype=float)

    def baca(self, indeks, atom):
        atom = np.asarray(atom)
        with open(self.path, "rb") as f:
            for i in indeks:
                off_x, nyata, off_box = self.frame[i]
                dt = np.dtype(">f8" if nyata == 8 else ">f4")
                kotak = None
                if off_box is not None:
                    f.seek(off_box)
                    kotak = np.frombuffer(f.read(9 * nyata), dtype=dt).astype(float).reshape(3, 3)
                f.seek(off_x)
                xyz = np.frombuffer(f.read(3 * self.n_atom * nyata), dtype=dt).reshape(self.n_atom, 3)
                yield i, xyz[atom].astype(np.float32), kotak


class PembacaDCD(Pembaca):
    """DCD CHARMM/NAMD/OpenMM/ACEMD: little/big endian, sel satuan, atom tetap (NAMNF), dimensi ke-4."""
    nama = "DCD"

    def __init__(self, path):
        self.path = str(path)
        with open(self.path, "rb") as f:
            kepala = f.read(4)
            for e in ("<", ">"):
                if struct.unpack(e + "i", kepala)[0] == 84:
                    self.e = e
                    break
            else:
                raise GalatImporMD("Bukan berkas DCD (rekaman kepala tidak dikenal).")
            e = self.e
            blok = f.read(84)
            if blok[:4] != b"CORD":
                raise GalatImporMD("Bukan berkas DCD (tanda CORD tidak ada).")
            icntrl = struct.unpack(e + "20i", blok[4:84])
            versi_charmm = icntrl[19]
            n_set, nsavc = icntrl[0], icntrl[2]
            self.namnf = icntrl[8]
            delta = struct.unpack(e + "f", blok[40:44])[0] if versi_charmm else struct.unpack(e + "d", blok[40:48])[0]
            self.sel = bool(icntrl[10]) if versi_charmm else False
            self.empat_d = bool(icntrl[11]) if versi_charmm else False
            f.read(4)
            n_judul_rek = struct.unpack(e + "i", f.read(4))[0]
            f.read(n_judul_rek + 4)
            f.read(4)
            self.n_atom = struct.unpack(e + "i", f.read(4))[0]
            f.read(4)
            self.bebas = None
            if self.namnf:
                n_bebas = self.n_atom - self.namnf
                r = struct.unpack(e + "i", f.read(4))[0]
                self.bebas = np.frombuffer(f.read(r), dtype=e + "i4").astype(int) - 1
                f.read(4)
                if len(self.bebas) != n_bebas:
                    raise GalatImporMD("Daftar atom bebas DCD tidak konsisten.")
            self.awal_data = f.tell()
            ukuran = os.path.getsize(self.path)
        def rek(n):
            return 4 * n + 8
        self.panjang_pertama = (56 if self.sel else 0) + 3 * rek(self.n_atom) + (rek(self.n_atom) if self.empat_d else 0)
        n_lain = self.n_atom - self.namnf if self.namnf else self.n_atom
        self.panjang_lain = (56 if self.sel else 0) + 3 * rek(n_lain) + (rek(n_lain) if self.empat_d else 0)
        sisa = ukuran - self.awal_data
        n_dari_ukuran = 0 if sisa < self.panjang_pertama else 1 + (sisa - self.panjang_pertama) // self.panjang_lain
        # NSET sering 0 atau basi pada trajektori yang dihentikan paksa: percayai ukuran berkas
        self.n_frame = int(n_dari_ukuran if (n_set <= 0 or n_set > n_dari_ukuran) else n_set)
        if self.n_frame <= 0:
            raise GalatImporMD("Berkas DCD tidak berisi frame.")
        self.dt_ps = abs(delta) * max(1, nsavc) * AKMA_PS if delta else None
        self.waktu = None

    def _offset(self, i):
        return self.awal_data if i == 0 else self.awal_data + self.panjang_pertama + (i - 1) * self.panjang_lain

    def _sel(self, f):
        e = self.e
        f.read(4)
        v = struct.unpack(e + "6d", f.read(48))
        f.read(4)
        a, gama, b, beta, alfa, c = v           # urutan NAMD/CHARMM: A, gamma, B, beta, alpha, C
        # CHARMM baru menyimpan kosinus sudut, NAMD/OpenMM menyimpan derajat
        sudut = [math.degrees(math.acos(x)) if abs(x) <= 1.0 else x for x in (alfa, beta, gama)]
        if not (a > 0 and b > 0 and c > 0):
            return None
        return kotak_dari_parameter(a / 10, b / 10, c / 10, *sudut)

    def baca(self, indeks, atom):
        atom = np.asarray(atom)
        penuh = None
        with open(self.path, "rb") as f:
            if self.namnf:      # frame pertama memuat semua atom; frame berikut hanya atom bebas
                f.seek(self._offset(0))
                kotak0 = self._sel(f) if self.sel else None
                penuh = self._xyz(f, self.n_atom)
            for i in indeks:
                f.seek(self._offset(i))
                kotak = self._sel(f) if self.sel else None
                if self.namnf and i > 0:
                    x = penuh.copy()
                    x[self.bebas] = self._xyz(f, len(self.bebas))
                elif self.namnf:
                    x = penuh
                    kotak = kotak0
                else:
                    x = self._xyz(f, self.n_atom)
                yield i, (x[atom] / 10.0).astype(np.float32), kotak

    def _xyz(self, f, n):
        e = self.e
        kol = []
        for _ in range(3):
            r = struct.unpack(e + "i", f.read(4))[0]
            kol.append(np.frombuffer(f.read(r), dtype=e + "f4"))
            f.read(4)
        if len(kol[0]) != n:
            raise GalatImporMD("Jumlah atom frame DCD tidak cocok dengan kepala berkas.")
        return np.stack(kol, axis=1).astype(np.float64)


class PembacaNetCDF(Pembaca):
    """NetCDF trajektori AMBER (klasik/64-bit offset) lewat scipy; NetCDF4/HDF5 tidak didukung scipy."""
    nama = "NetCDF"

    def __init__(self, path):
        from scipy.io import netcdf_file
        self.path = str(path)
        try:
            self.nc = netcdf_file(self.path, "r", mmap=True)
        except Exception as e:
            with open(self.path, "rb") as f:
                sig = f.read(8)
            if sig.startswith(b"\x89HDF"):
                raise GalatImporMD("NetCDF4 (HDF5) belum didukung. Simpan ulang sebagai NetCDF klasik, misalnya "
                                   "cpptraj: `trajout md_klasik.nc netcdf`, atau ekspor ke DCD/XTC.")
            raise GalatImporMD(f"NetCDF tidak terbaca: {e}")
        v = self.nc.variables
        if "coordinates" not in v:
            self.nc.close()
            raise GalatImporMD("Berkas NetCDF tidak memuat variabel 'coordinates' (bukan trajektori AMBER).")
        self.n_frame, self.n_atom = v["coordinates"].shape[:2]
        self.waktu = np.array(v["time"][:], dtype=float) if "time" in v else None

    def baca(self, indeks, atom):
        v = self.nc.variables
        atom = np.asarray(atom)
        ada_sel = "cell_lengths" in v and "cell_angles" in v
        for i in indeks:
            xyz = np.array(v["coordinates"][i][atom], dtype=np.float32) / 10.0
            kotak = None
            if ada_sel:
                L = np.array(v["cell_lengths"][i], dtype=float) / 10.0
                A = np.array(v["cell_angles"][i], dtype=float)
                if (L > 0).all():
                    kotak = kotak_dari_parameter(*L, *A)
            yield i, xyz, kotak

    def tutup(self):
        try:
            self.nc.close()
        except Exception:
            pass


class PembacaMDCRD(Pembaca):
    """MDCRD ASCII AMBER (10F8.3 per baris, opsional baris kotak 3 angka tiap frame). Butuh jumlah atom topologi."""
    nama = "MDCRD"

    def __init__(self, path, n_atom):
        self.path = str(path)
        self.n_atom = n_atom
        n_baris = math.ceil(3 * n_atom / 10)
        self.offset = []
        with open(self.path, "rb") as f:
            f.readline()                     # judul
            pos = f.tell()
            baris = f.readlines()
        # baris kotak = baris setelah frame pertama yang lebarnya tepat 3 kolom F8.3 (baris koordinat penuh 10
        # kolom; baris pertama frame berikutnya selalu > 3 kolom kecuali sistem satu atom)
        self.kotak = len(baris) > n_baris and n_atom > 1 and len(baris[n_baris].rstrip()) // 8 == 3
        per = n_baris + (1 if self.kotak else 0)
        for k in range(0, len(baris) - n_baris + 1, per):
            if len(baris) - k < n_baris:
                break
            self.offset.append(pos)
            pos += sum(len(b) for b in baris[k:k + per])
        self.n_frame = len(self.offset)
        if not self.n_frame:
            raise GalatImporMD("MDCRD tidak berisi frame lengkap (jumlah atom topologi cocok?).")

    def baca(self, indeks, atom):
        atom = np.asarray(atom)
        n_baris = math.ceil(3 * self.n_atom / 10)
        with open(self.path, "rb") as f:
            for i in indeks:
                f.seek(self.offset[i])
                teks = b"".join(f.readline() for _ in range(n_baris))
                nilai = [float(teks[k:k + 8]) for b in teks.splitlines() for k in range(0, len(b.rstrip()), 8)]
                xyz = np.array(nilai[:3 * self.n_atom], dtype=float).reshape(self.n_atom, 3)
                kotak = None
                if self.kotak:
                    L = [float(x) for x in f.readline().split()]
                    kotak = np.diag(np.array(L) / 10.0) if len(L) == 3 else None
                yield i, (xyz[atom] / 10.0).astype(np.float32), kotak


class PembacaPDB(Pembaca):
    """PDB multi-MODEL sebagai trajektori."""
    nama = "PDB"

    def __init__(self, path):
        self.path = str(path)
        self.offset = []
        n, pos = 0, 0
        with open(self.path, "rb") as f:
            for b in f:
                if b.startswith(b"MODEL"):
                    self.offset.append(pos)
                    n = 0
                elif b.startswith((b"ATOM", b"HETATM")):
                    n += 1
                pos += len(b)
        if not self.offset:
            self.offset = [0]
        with open(self.path, "rb") as f:
            f.seek(self.offset[0])
            n = 0
            for b in f:
                if b.startswith((b"ATOM", b"HETATM")):
                    n += 1
                elif b.startswith(b"ENDMDL") and n:
                    break
        self.n_atom, self.n_frame = n, len(self.offset)

    def baca(self, indeks, atom):
        atom = np.asarray(atom)
        with open(self.path, "rb") as f:
            for i in indeks:
                f.seek(self.offset[i])
                xyz, kotak = [], None
                for b in f:
                    if b.startswith(b"CRYST1"):
                        try:
                            kotak = kotak_dari_parameter(*(float(b[s:e]) / (10 if k < 3 else 1) for k, (s, e) in
                                                           enumerate(((6, 15), (15, 24), (24, 33), (33, 40),
                                                                      (40, 47), (47, 54)))))
                        except ValueError:
                            kotak = None
                    elif b.startswith((b"ATOM", b"HETATM")):
                        xyz.append((float(b[30:38]), float(b[38:46]), float(b[46:54])))
                    elif b.startswith((b"ENDMDL", b"END")) and xyz:
                        break
                if len(xyz) != self.n_atom:
                    raise GalatImporMD(f"MODEL {i + 1} berisi {len(xyz)} atom, model pertama {self.n_atom}.")
                yield i, (np.array(xyz)[atom] / 10.0).astype(np.float32), kotak


class PembacaGRO(Pembaca):
    """GRO multi-frame (keluaran `gmx trjconv -o *.gro`). Waktu dibaca dari 't=' di judul bila ada."""
    nama = "GRO"

    def __init__(self, path):
        self.path = str(path)
        self.offset, waktu = [], []
        with open(self.path, "rb") as f:
            while True:
                pos = f.tell()
                judul = f.readline()
                if not judul.strip():
                    break
                try:
                    n = int(f.readline().strip())
                except ValueError:
                    break
                for _ in range(n + 1):
                    f.readline()
                self.offset.append(pos)
                m = re.search(rb"t=\s*([-+0-9.eE]+)", judul)
                waktu.append(float(m.group(1)) if m else np.nan)
                self.n_atom = n
        if not self.offset:
            raise GalatImporMD("Berkas GRO kosong.")
        self.n_frame = len(self.offset)
        w = np.array(waktu, dtype=float)
        self.waktu = None if np.isnan(w).any() else w

    def baca(self, indeks, atom):
        atom = np.asarray(atom)
        with open(self.path, encoding="utf-8", errors="replace") as f:
            for i in indeks:
                f.seek(self.offset[i])
                _, baris, B = _baca_gro_frame(f, self.n_atom)
                yield i, _koordinat_gro(baris)[atom].astype(np.float32), B


def buka_trajektori(path, n_atom_topologi=None):
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".xtc":
        return PembacaXTC(p)
    if ext == ".trr":
        return PembacaTRR(p)
    if ext == ".dcd":
        return PembacaDCD(p)
    if ext in (".nc", ".ncdf", ".netcdf"):
        return PembacaNetCDF(p)
    if ext in (".mdcrd", ".crd", ".x"):
        if not n_atom_topologi:
            raise GalatImporMD("MDCRD butuh topologi untuk mengetahui jumlah atom.")
        return PembacaMDCRD(p, n_atom_topologi)
    if ext in (".pdb", ".ent"):
        return PembacaPDB(p)
    if ext == ".gro":
        return PembacaGRO(p)
    raise GalatImporMD(f"Format trajektori {ext} belum didukung.")


def info_trajektori(path, n_atom_topologi=None):
    """Ringkasan cepat untuk dialog: atom, frame, waktu awal/akhir (ps), dt (ps)."""
    r = buka_trajektori(path, n_atom_topologi)
    try:
        w = r.waktu
        dt = None
        if w is not None and len(w) > 1:
            d = np.diff(w)
            d = d[d > 0]
            dt = float(np.median(d)) if len(d) else None
        dt = dt or r.dt_ps
        t0 = float(w[0]) if w is not None and len(w) else 0.0
        t1 = float(w[-1]) if w is not None and len(w) else (t0 + (r.n_frame - 1) * dt if dt else None)
        return {"format": r.nama, "atom": r.n_atom, "frame": r.n_frame, "t0": t0, "t1": t1, "dt": dt,
                "waktu_ada": w is not None}
    finally:
        r.tutup()


# ------------------------------------------------------------------ PBC & penyejajaran
def _citra_minimum(d, B, Binv):
    """Vektor selisih d (…,3) ke citra terdekat untuk kotak B (baris = vektor kotak)."""
    s = d @ Binv
    s -= np.round(s)
    return s @ B


def utuhkan_frame(x, B, residu, rantai, ligan_res):
    """Frame pertama: utuhkan tiap residu, sambung residu berurutan dalam rantai, dekatkan rantai lain dan ligan ke
    rantai pertama. x: (n,3) nm, diubah di tempat."""
    Binv = np.linalg.inv(B)
    for r in residu:
        if len(r) > 1:
            x[r[1:]] = x[r[0]] + _citra_minimum(x[r[1:]] - x[r[0]], B, Binv)
    pusat_rantai = []
    for ch in rantai:
        sebelum = None
        for r in ch:
            c = x[r].mean(0)
            if sebelum is not None:
                geser = sebelum + _citra_minimum(c - sebelum, B, Binv) - c
                x[r] += geser
                c = c + geser
            sebelum = c
        pusat_rantai.append(np.concatenate(ch))
    if pusat_rantai:
        acuan = x[pusat_rantai[0]].mean(0)
        for idx in pusat_rantai[1:] + list(ligan_res):
            c = x[idx].mean(0)
            x[idx] += acuan + _citra_minimum(c - acuan, B, Binv) - c
    return x


def tanpa_lompatan(sebelum, x, B):
    """Hilangkan lompatan citra periodik per atom terhadap frame sebelumnya yang sudah utuh."""
    Binv = np.linalg.inv(B)
    return sebelum + _citra_minimum(x - sebelum, B, Binv)


def kabsch(P, Q):
    """Rotasi R dan pusat (cp, cq) agar (P-cp)@R + cq menempel ke Q."""
    cp, cq = P.mean(0), Q.mean(0)
    H = (P - cp).T @ (Q - cq)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(U @ Vt))
    D = np.diag([1.0, 1.0, d])
    return U @ D @ Vt, cp, cq


# ------------------------------------------------------------------ molekul ligan
def mol_ligan(top, indeks, xyz_nm, smiles=None, muatan=None):
    """Ligan dari trajektori -> RDKit Mol ber-H dengan orde ikatan, urutan atom = urutan `indeks`.

    Konektivitas dari topologi (PRMTOP/PSF/CONECT) bila lengkap, selain itu dari jarak. Orde ikatan dari templat
    SMILES bila diberikan, selain itu ditentukan dari geometri dengan atom H eksplisit (rdDetermineBonds) untuk
    muatan total 0, ±1, ±2. Kembalikan (mol, catatan) — mol None bila gagal (interaksi polar tidak dinilai)."""
    from rdkit import Chem, rdBase
    from rdkit.Chem import AllChem, rdDetermineBonds
    atoms = list(top.atoms())
    pos = {i: k for k, i in enumerate(indeks)}
    rw = Chem.RWMol()
    for i in indeks:
        el = atoms[i].element
        a = Chem.Atom(el.symbol if el is not None else "C")
        a.SetNoImplicit(True)
        rw.AddAtom(a)
    ikatan = [(pos[b[0].index], pos[b[1].index]) for b in top.bonds() if b[0].index in pos and b[1].index in pos]
    conf = Chem.Conformer(len(indeks))
    for k, i in enumerate(indeks):
        conf.SetAtomPosition(k, (np.asarray(xyz_nm[k], dtype=float) * 10.0).tolist())
    rw.AddConformer(conf, assignId=True)
    catatan = []
    with rdBase.BlockLogs():
        if len(ikatan) >= len(indeks) - 1:
            for a, b in ikatan:
                rw.AddBond(a, b, Chem.BondType.SINGLE)
            mol = rw.GetMol()
        else:
            mol = rw.GetMol()
            try:
                rdDetermineBonds.DetermineConnectivity(mol)
            except Exception as e:
                return None, f"konektivitas ligan tidak bisa ditentukan: {e}"
        punya_h = any(a.GetAtomicNum() == 1 for a in mol.GetAtoms())
        if smiles:
            try:
                templ = Chem.MolFromSmiles(smiles)
                berat = Chem.RemoveHs(mol, sanitize=False)
                hasil = AllChem.AssignBondOrdersFromTemplate(templ, berat)
                if hasil is not None:
                    # pindahkan orde ikatan ke mol ber-H (atom berat sama urutan relatifnya)
                    peta = [a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum() != 1]
                    m2 = Chem.RWMol(mol)
                    for b in hasil.GetBonds():
                        bb = m2.GetBondBetweenAtoms(peta[b.GetBeginAtomIdx()], peta[b.GetEndAtomIdx()])
                        if bb is not None:
                            bb.SetBondType(b.GetBondType())
                    for a in hasil.GetAtoms():
                        m2.GetAtomWithIdx(peta[a.GetIdx()]).SetFormalCharge(a.GetFormalCharge())
                    m = m2.GetMol()
                    for a in m.GetAtoms():
                        a.SetNoImplicit(True)
                    Chem.SanitizeMol(m)
                    return m, "orde ikatan dari templat SMILES"
            except Exception as e:
                catatan.append(f"templat SMILES tidak cocok ({e})")
        if punya_h:
            urut = [muatan] if muatan is not None else [0, 1, -1, 2, -2]
            for q in urut:
                try:
                    m = Chem.Mol(mol)
                    rdDetermineBonds.DetermineBondOrders(m, charge=q, embedChiral=False)
                    Chem.SanitizeMol(m)
                    return m, f"orde ikatan dari geometri (muatan {q:+d})"
                except Exception:
                    continue
            catatan.append("orde ikatan tidak bisa ditentukan dari geometri")
        else:
            catatan.append("ligan tanpa atom H")
        try:     # cadangan: ikatan tunggal saja; kontak hidrofobik tetap terhitung
            m = Chem.Mol(mol)
            m.UpdatePropertyCache(strict=False)
            Chem.FastFindRings(m)
            return m, "; ".join(catatan + ["ikatan tunggal saja: ikatan H dan π mungkin tidak terdeteksi"])
        except Exception:
            return None, "; ".join(catatan)


# ------------------------------------------------------------------ proses utama
@dataclass
class OpsiImpor:
    nama: str = "Trajektori"
    mode: str = "sambung"           # sambung (bagian-bagian satu simulasi) | replika (tiap berkas satu replika)
    ligan: str | None = "auto"      # kunci calon_ligan, "auto" (terbesar), atau None (protein saja)
    mulai_ps: float | None = None
    akhir_ps: float | None = None
    stride: int = 0                 # 0 = otomatis dari maks_frame
    maks_frame: int = 1000
    dt_ps: float | None = None      # paksa jarak waktu antarframe bila berkas tidak menyimpan waktu
    pbc: bool = True
    ion_logam: bool = True
    lipid: bool = False
    smiles: str = ""                # templat orde ikatan ligan (opsional)


def _waktu_gabungan(pembaca, dt_paksa):
    """[(i_berkas, i_frame, t_ps)] semua frame berurutan waktu.

    Waktu dari berkas dipakai bila naik monoton; selain itu (DCD, MDCRD) dibuat dari dt kepala berkas atau dt
    paksaan. Bagian lanjutan yang mengulang frame terakhir bagian sebelumnya (gmx mdrun -noappend) dilewati;
    bagian yang mulai lagi dari nol disambung setelah bagian sebelumnya."""
    out, t_akhir = [], None
    for b, r in enumerate(pembaca):
        w = r.waktu
        if dt_paksa or w is None or (len(w) > 1 and not np.all(np.diff(w) > 0)):
            dt = dt_paksa or r.dt_ps or 1.0
            awal = (t_akhir if t_akhir is not None else 0.0) + dt
            w = awal + np.arange(r.n_frame, dtype=float) * dt
        else:
            w = np.asarray(w, dtype=float)
            if t_akhir is not None and w[0] <= 1e-6 < t_akhir:
                dt = float(np.median(np.diff(w))) if len(w) > 1 else (r.dt_ps or 1.0)
                w = w + t_akhir + dt - w[0]
        for i, t in enumerate(w):
            if t_akhir is not None and t <= t_akhir + 1e-6:
                continue
            out.append((b, i, float(t)))
            t_akhir = float(t)
    return out


def _pilih_frame(semua, opsi):
    pilih = [x for x in semua if (opsi.mulai_ps is None or x[2] >= opsi.mulai_ps - 1e-6)
             and (opsi.akhir_ps is None or x[2] <= opsi.akhir_ps + 1e-6)]
    if not pilih:
        raise GalatImporMD("Tidak ada frame di rentang waktu yang dipilih.")
    stride = opsi.stride if opsi.stride and opsi.stride > 0 else max(1, math.ceil(len(pilih) / max(10, opsi.maks_frame)))
    return pilih[::stride], stride


def _baca_frame(pembaca, pilihan, atom, lapor=None, label=""):
    """Baca frame terpilih (atom terpilih) dari banyak berkas -> (frames nm (n,a,3), kotak list)."""
    frames = np.empty((len(pilihan), len(atom), 3), dtype=np.float32)
    kotak = [None] * len(pilihan)
    k = 0
    for b, r in enumerate(pembaca):
        idx = [i for bb, i, _ in pilihan if bb == b]
        for i, xyz, B in r.baca(idx, atom):
            frames[k] = xyz
            kotak[k] = B
            k += 1
            if lapor and k % 25 == 0:
                lapor.progres.emit(int(10 + 45 * k / len(pilihan)), 100, f"{label}membaca frame {k}/{len(pilihan)}")
    if k != len(pilihan):
        raise GalatImporMD(f"Hanya {k} dari {len(pilihan)} frame terbaca.")
    return frames, kotak


def _struktur_residu(top_sub):
    """(residu [indeks], rantai polimer [[indeks residu]], kelompok non-polimer [indeks]) untuk utuhkan_frame."""
    residu, rantai, lain = [], [], []
    for ch in top_sub.chains():
        poli = []
        for r in ch.residues():
            idx = [a.index for a in r.atoms()]
            residu.append(np.array(idx))
            if _kelas_residu(r.name, len(idx)) in ("protein", "nukleat"):
                poli.append(np.array(idx))
            else:
                lain.append(np.array(idx))
        if poli:
            rantai.append(poli)
    return residu, rantai, lain


def _rapikan(frames, kotak, top_sub, pbc, lapor=None):
    """PBC (utuhkan + tanpa lompatan) lalu sejajarkan semua frame ke Cα frame pertama. Di tempat."""
    atoms = list(top_sub.atoms())
    catatan = []
    ada_kotak = pbc and all(B is not None and np.linalg.det(B) > 1e-6 for B in kotak)
    if pbc and not ada_kotak:
        catatan.append("informasi kotak periodik tidak ada di trajektori; perbaikan PBC dilewati")
    if ada_kotak:
        residu, rantai, lain = _struktur_residu(top_sub)
        x0 = frames[0].astype(np.float64)
        utuhkan_frame(x0, np.asarray(kotak[0], float), residu, rantai, lain)
        frames[0] = x0
        sebelum = x0
        for k in range(1, len(frames)):
            x = tanpa_lompatan(sebelum, frames[k].astype(np.float64), np.asarray(kotak[k], float))
            frames[k] = x
            sebelum = x
        catatan.append("molekul diutuhkan dan lompatan antarframe periodik dihapus")
    ca = [a.index for a in atoms if a.name == "CA" and a.element is not None and a.element.symbol == "C"]
    acuan_idx = ca if len(ca) >= 3 else [a.index for a in atoms if a.element is not None and a.element.symbol != "H"]
    ref = frames[0][acuan_idx].astype(np.float64)
    for k in range(len(frames)):
        x = frames[k].astype(np.float64)
        R, cp, cq = kabsch(x[acuan_idx], ref)
        frames[k] = ((x - cp) @ R + cq).astype(np.float32)
    catatan.append("frame disejajarkan pada " + ("Cα" if len(ca) >= 3 else "atom berat") + " frame pertama")
    return catatan


def _analisis_trajektori(top_sub, idx_lig, frames):
    """RMSD Cα & ligan (atom berat) terhadap frame pertama dan RMSF Cα; frame sudah disejajarkan."""
    atoms = list(top_sub.atoms())
    ca = [a.index for a in atoms if a.name == "CA" and a.element is not None and a.element.symbol == "C"]
    lig = [i for i in idx_lig if atoms[i].element is not None and atoms[i].element.symbol != "H"]
    x = frames.astype(np.float64) * 10.0
    out = {}
    if ca:
        d = x[:, ca] - x[0, ca]
        out["rmsd_ca"] = np.sqrt((d ** 2).sum(2).mean(1)).round(4).tolist()
        rata = x[:, ca].mean(0)
        out["rmsf"] = np.sqrt(((x[:, ca] - rata) ** 2).sum(2).mean(0)).round(4).tolist()
        out["residu"] = [f"{atoms[i].residue.name}{atoms[i].residue.id} {atoms[i].residue.chain.id}".strip()
                         for i in ca]
    if lig:
        d = x[:, lig] - x[0, lig]
        out["rmsd_ligan"] = np.sqrt((d ** 2).sum(2).mean(1)).round(4).tolist()
        # jarak pusat massa ligan ke pusat kantong (residu ≤ 6 Å dari ligan di frame pertama)
        kantong = sorted({a.index for a in atoms if a.element is not None and a.element.symbol != "H"
                          and a.index not in set(idx_lig)
                          and np.min(np.linalg.norm(x[0, lig] - x[0, a.index], axis=1)) <= 6.0})
        if kantong:
            out["jarak_kantong"] = np.linalg.norm(x[:, lig].mean(1) - x[:, kantong].mean(1), axis=1).round(3).tolist()
    return out


def tulis_pdb(top, xyz_nm, f):
    from openmm import app, unit
    with open(f, "w", encoding="utf-8") as h:
        app.PDBFile.writeFile(top, unit.Quantity(np.asarray(xyz_nm, dtype=float), unit.nanometer), h, keepIds=True)


def tulis_dcd(top, frames, f, dt_ps):
    from openmm import app, unit
    with open(f, "wb") as h:
        d = app.DCDFile(h, top, max(dt_ps, 1e-6) * unit.picoseconds)
        for x in frames:
            d.writeModel(unit.Quantity(np.asarray(x, dtype=float), unit.nanometer))


def _aman(nama):
    return re.sub(r"[^\w.\-]+", "_", nama).strip("._")[:60] or "trajektori"


def _satu_replika(tp, berkas, opsi, folder, lapor, label=""):
    """Baca, rapikan, tulis, dan analisis satu simulasi (satu atau beberapa bagian berkas)."""
    from . import md_analisis
    pembaca = []
    try:
        for f in berkas:
            pembaca.append(buka_trajektori(f, tp.n_atom))
        n_traj = {r.n_atom for r in pembaca}
        if len(n_traj) > 1:
            raise GalatImporMD("Bagian trajektori berisi jumlah atom berbeda: " + ", ".join(map(str, n_traj)))
        n_traj = n_traj.pop()
        kelas = kelas_atom(tp.top)
        calon = calon_ligan(tp.top, kelas)
        kunci_lig = calon[0]["kunci"] if opsi.ligan == "auto" and calon else (
            None if opsi.ligan == "auto" else opsi.ligan)
        sel, lig_global = pilih_atom(tp.top, kunci_lig, opsi.ion_logam, opsi.lipid, kelas)
        catatan = []
        if n_traj != tp.n_atom:
            # trajektori sering ditulis hanya untuk grup awal (mis. Protein_LIG, tanpa air): cocokkan atom awal
            if n_traj < tp.n_atom and all(i < n_traj for i in sel):
                catatan.append(f"trajektori berisi {n_traj} atom pertama dari {tp.n_atom} atom topologi")
            else:
                raise GalatImporMD(
                    f"Jumlah atom trajektori ({n_traj}) tidak sama dengan topologi ({tp.n_atom}). Pakai topologi dari "
                    "grup keluaran yang sama, misalnya `gmx trjconv -s md.tpr -f md.xtc -o ref.pdb -dump 0` dengan "
                    "pilihan grup yang sama seperti saat menulis trajektori.")
        if not sel:
            raise GalatImporMD("Tidak ada atom protein, asam nukleat, atau ligan di topologi.")
        semua = _waktu_gabungan(pembaca, opsi.dt_ps)
        pilihan, stride = _pilih_frame(semua, opsi)
        if lapor:
            lapor.progres.emit(8, 100, f"{label}{len(pilihan)} frame dari {len(semua)} (tiap {stride})")
        frames, kotak = _baca_frame(pembaca, pilihan, sel, lapor, label)
    finally:
        for r in pembaca:
            r.tutup()
    top_sub = sub_topologi(tp.top, sel)
    peta = {g: k for k, g in enumerate(sel)}
    idx_lig = [peta[i] for i in lig_global]
    if lapor:
        lapor.progres.emit(58, 100, f"{label}memperbaiki PBC dan menyejajarkan frame")
    catatan += _rapikan(frames, kotak, top_sub, opsi.pbc)
    waktu = np.array([t for _, _, t in pilihan], dtype=float)
    dt_ef = float(np.median(np.diff(waktu))) if len(waktu) > 1 else (opsi.dt_ps or 1.0)
    folder.mkdir(parents=True, exist_ok=True)
    tulis_pdb(top_sub, frames[0], folder / "topologi.pdb")
    tulis_dcd(top_sub, frames, folder / "trajektori_terlarut.dcd", dt_ef)
    mol, ket_mol = (None, "")
    if idx_lig:
        mol, ket_mol = mol_ligan(top_sub, idx_lig, frames[0][idx_lig], opsi.smiles or None)
        if mol is not None:
            from rdkit import Chem
            Chem.MolToMolFile(mol, str(folder / "ligan.mol"))
        catatan.append(f"ligan: {ket_mol}")
    if lapor:
        lapor.progres.emit(64, 100, f"{label}RMSD, RMSF, Rg, SASA, interaksi, PCA, FEL, klaster")
    traj = _analisis_trajektori(top_sub, idx_lig, frames)
    traj["waktu_ns"] = (waktu / 1000.0).round(6).tolist()

    class _Modeller:
        def __init__(self, t):
            self.topology = t
    an = md_analisis.analisis_lengkap(_Modeller(top_sub), {"idx_ligan": idx_lig}, frames, mol, dt_ps=dt_ef)
    if idx_lig and mol is None:
        an.setdefault("peringatan", []).append("Orde ikatan ligan tidak bisa ditentukan: ikatan hidrogen dan "
                                               "interaksi polar tidak dinilai; hanya kontak hidrofobik.")
    lig_info = next((c for c in calon_ligan(tp.top) if c["kunci"] == kunci_lig), None) if kunci_lig else None
    return {"folder": folder.name, "trajektori": traj, "analisis": an,
            "interaksi_frek": an.get("interaksi_frek", {}),
            "md": {"pelarut": "-", "ns": round(float(waktu[-1] - waktu[0]) / 1000.0, 4), "atom": tp.n_atom,
                   "suhu": None, "seed": None},
            "impor": {"berkas": [str(b) for b in berkas], "frame_asli": len(semua), "frame": len(pilihan),
                      "stride": stride, "t_awal_ps": float(waktu[0]), "t_akhir_ps": float(waktu[-1]),
                      "dt_ps": dt_ef, "atom_disimpan": len(sel), "ligan": lig_info["label"] if lig_info else None,
                      "catatan": catatan}}


def proses(topologi, trajektori, folder, opsi=None, lapor=None):
    """Topologi + berkas trajektori -> folder hasil (format MD VirmoLab) dan dict hasil.json.

    trajektori: list berkas. Mode 'sambung' = bagian berurutan satu simulasi; 'replika' = tiap berkas satu replika
    independen (topologi sama)."""
    opsi = opsi or OpsiImpor()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    mulai = time.time()
    if lapor:
        lapor.progres.emit(1, 100, "Membaca topologi")
    tp = baca_topologi(topologi)
    trajektori = [str(t) for t in trajektori] or [str(topologi)]
    sub = folder / f"{_aman(opsi.nama)}_1"
    kelompok = [[t] for t in trajektori] if opsi.mode == "replika" and len(trajektori) > 1 else [trajektori]
    replika = []
    for r, berkas in enumerate(kelompok, 1):
        label = f"Replika {r}/{len(kelompok)}: " if len(kelompok) > 1 else ""
        tujuan = sub / f"replika_{r}" if len(kelompok) > 1 else sub
        item = _satu_replika(tp, berkas, opsi, tujuan, lapor, label)
        item["replika"] = r
        item["seed"] = "-"
        if len(kelompok) > 1:
            item["folder"] = f"{sub.name}/{tujuan.name}"
        replika.append(item)
    utama = replika[0]
    d = {"nama": opsi.nama, "lid": None, "job": None, "peringkat": 1, "energi_docking": None, "selesai": True,
         "folder": sub.name, "trajektori": utama["trajektori"], "analisis": utama["analisis"],
         "interaksi_frek": utama["interaksi_frek"], "md": utama["md"], "replika": replika, "impor": utama["impor"]}
    if len(replika) > 1:
        def rerata(nilai):
            v = [x for x in nilai if x is not None]
            return [float(np.mean(v)), float(np.std(v, ddof=1)) if len(v) > 1 else 0.0] if v else [0.0, 0.0]
        d["replika_agregat"] = {
            "rmsd_ligan": rerata([np.mean(x["trajektori"]["rmsd_ligan"]) if x["trajektori"].get("rmsd_ligan")
                                  else None for x in replika]),
            "rmsd_ca": rerata([np.mean(x["trajektori"]["rmsd_ca"]) if x["trajektori"].get("rmsd_ca") else None
                               for x in replika]),
            "rg": rerata([np.mean(x["analisis"]["rg"]) if x["analisis"].get("rg") else None for x in replika]),
            "mmgbsa_dG": [0.0, 0.0]}
    hasil = {"mode": "md", "impor": True, "versi": {"VirmoLab impor": "1"},
             "opsi": {"interval_ps": utama["impor"]["dt_ps"], "pelarut": "-", "ns": utama["md"]["ns"],
                      "replika": len(replika)},
             "sumber": {"topologi": str(topologi), "trajektori": trajektori, "mode": opsi.mode,
                        "pbc": opsi.pbc, "ligan": opsi.ligan, "smiles": opsi.smiles},
             "ligan": [d], "mulai": time.strftime("%Y-%m-%d %H:%M:%S"),
             "selesai": time.strftime("%Y-%m-%d %H:%M:%S"), "detik": round(time.time() - mulai, 1)}
    (folder / "hasil.json").write_text(json.dumps(hasil, indent=1, ensure_ascii=False), encoding="utf-8")
    if lapor:
        lapor.progres.emit(100, 100, "Selesai")
    return hasil


def film_pdb(folder_sub, maks=150, hanya_kantong=False):
    """topologi.pdb + trajektori_terlarut.dcd -> (PDB multi-MODEL tanpa H non-polar, waktu ns per bingkai)."""
    import io
    from openmm import app, unit
    folder_sub = Path(folder_sub)
    top = app.PDBFile(str(folder_sub / "topologi.pdb")).topology
    r = PembacaDCD(folder_sub / "trajektori_terlarut.dcd")
    idx = sorted({int(round(i)) for i in np.linspace(0, r.n_frame - 1, min(maks, r.n_frame))})
    atom = list(top.atoms())
    simpan = [a.index for a in atom if not (a.element is not None and a.element.symbol == "H"
                                            and a.residue.name.upper() in PROTEIN)]
    sub = sub_topologi(top, simpan)
    potong = []
    for k, (_, xyz, _) in enumerate(r.baca(idx, simpan), 1):
        buf = io.StringIO()
        app.PDBFile.writeFile(sub, unit.Quantity(xyz.astype(float), unit.nanometer), buf, keepIds=True)
        isi = "\n".join(b for b in buf.getvalue().splitlines() if b.startswith(("ATOM", "HETATM")))
        potong.append(f"MODEL     {k:4d}\n{isi}\nENDMDL")
    return "\n".join(potong) + "\nEND\n", idx


def jalankan_tugas(f_tugas):
    """Pekerja (python -m virmolab --impor-md tugas.json): cetak 'PROGRES p teks', tulis hasil.json.
    Galat ditulis sebagai baris 'GALAT pesan' dan galat.txt; kode keluar 0 = berhasil."""
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except (AttributeError, ValueError):
        pass
    t = json.loads(Path(f_tugas).read_text(encoding="utf-8"))
    folder = Path(t["folder"])

    class _Sinyal:
        def emit(self, a, b=100, teks=""):
            print(f"PROGRES {100.0 * a / max(1, b):.1f} {teks}", flush=True)

    class _Lapor:
        progres = _Sinyal()

    try:
        opsi = OpsiImpor(**{k: v for k, v in (t.get("opsi") or {}).items() if k in OpsiImpor.__dataclass_fields__})
        proses(t["topologi"], t["trajektori"], folder, opsi, _Lapor())
        return 0
    except Exception as e:
        pesan = (str(e).strip().splitlines() or [type(e).__name__])[0]
        if not isinstance(e, GalatImporMD):
            import traceback
            catat.log.error("Impor MD gagal:\n" + traceback.format_exc())
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "galat.txt").write_text(pesan, encoding="utf-8")
        print("GALAT " + pesan, flush=True)
        return 1


def jumlah_atom_topologi(path):
    """Jumlah atom berkas topologi tanpa membangun topologi penuh (untuk mencocokkan trajektori). None bila gagal."""
    p = Path(path)
    ext = p.suffix.lower()
    try:
        if ext == ".gro":
            with open(p, encoding="utf-8", errors="replace") as f:
                f.readline()
                return int(f.readline().strip())
        if ext in (".pdb", ".ent"):
            n = 0
            with open(p, "rb") as f:
                for b in f:
                    if b.startswith((b"ATOM", b"HETATM")):
                        n += 1
                    elif b.startswith(b"ENDMDL") and n:
                        break
            return n or None
        if ext in (".prmtop", ".parm7"):
            teks = p.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"%FLAG POINTERS\s*\n%FORMAT\([^)]*\)\s*\n\s*(\d+)", teks)
            return int(m.group(1)) if m else None
        if ext == ".psf":
            with open(p, encoding="utf-8", errors="replace") as f:
                for b in f:
                    if "!NATOM" in b:
                        return int(b.split()[0])
    except (OSError, ValueError):
        return None
    return None


def cari_topologi(path_traj, n_atom=None):
    """Topologi di folder trajektori yang jumlah atomnya cocok: nama dasar sama dulu, lalu nama GROMACS/AMBER
    lazim (md, npt, nvt, em, complex, system, step*), lalu berkas topologi lain."""
    p = Path(path_traj)
    calon = [x for x in p.parent.iterdir() if x.is_file() and x.suffix.lower() in EKSTENSI_TOPOLOGI and x != p]
    lazim = ("md", "npt", "nvt", "em", "complex", "kompleks", "system", "sistem", "solv_ions", "conf", "start",
             "step5_input", "step4.1_equilibration", "ionized", "prod", "production")

    def urutan(x):
        stem = x.stem.lower()
        return (0 if stem == p.stem.lower() else 1 if stem in lazim or stem.startswith(lazim) else 2,
                {".prmtop": 0, ".parm7": 0, ".psf": 1, ".gro": 2, ".pdb": 3}.get(x.suffix.lower(), 4), stem)
    for x in sorted(calon, key=urutan):
        n = jumlah_atom_topologi(x)
        if n and (n_atom is None or n == n_atom):
            return str(x)
    return None
