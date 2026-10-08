"""Analisis hasil docking: molekul pose, interaksi protein–ligan, RMSD kristal, efisiensi ligan.

Kriteria interaksi (Å / derajat) — dicantumkan juga di laporan & panduan:
  Ikatan hidrogen    D···A ≤ 3.5, H···A ≤ 2.8, sudut D–H···A ≥ 110 (tanpa H: hanya D···A)
  Hidrofobik         C nonpolar ligan ↔ C nonpolar protein ≤ 4.0 (satu kontak terdekat per residu)
  π–π                pusat cincin ≤ 5.5; tumpuk: sudut bidang ≤ 30 & offset ≤ 3.0; bentuk T: sudut ≥ 60
  π–kation           pusat cincin ↔ kation ≤ 6.0 dengan offset lateral ≤ 2.0
  Jembatan garam     gugus bermuatan berlawanan ≤ 4.0
  Ikatan halogen     X···A ≤ 3.5, sudut C–X···A ≥ 140 (X = Cl, Br, I)
  Koordinasi logam   ion ↔ O/N/S ligan ≤ 2.8
  van der Waals      atom berat ≤ 4.2 (residu yang tidak punya interaksi lain; untuk diagram)
"""
import math
import os
from dataclasses import dataclass, field

import numpy as np

KRITERIA = {"hbond_da": 3.5, "hbond_ha": 2.8, "hbond_sudut": 110.0, "hidrofobik": 4.0, "pi": 5.5,
            "pi_tumpuk_sudut": 30.0, "pi_offset": 3.0, "pi_t_sudut": 60.0, "pikation": 6.0,
            "pikation_offset": 2.0, "garam": 4.0, "halogen": 3.5, "halogen_sudut": 140.0, "logam": 2.8,
            "vdw": 4.2}
NAMA_JENIS = {"hbond": "Ikatan hidrogen", "hidrofobik": "Hidrofobik", "pi": "π–π", "pikation": "π–kation",
              "garam": "Jembatan garam", "halogen": "Ikatan halogen", "logam": "Koordinasi logam",
              "vdw": "van der Waals"}
URUT_JENIS = ["hbond", "garam", "logam", "halogen", "pikation", "pi", "hidrofobik", "vdw"]
SINGKAT = {"hbond": "HB", "garam": "SB", "logam": "M", "halogen": "X", "pikation": "πC", "pi": "ππ",
           "hidrofobik": "HF", "vdw": "vdW"}

ELEMEN_AD = {"A": "C", "C": "C", "H": "H", "HD": "H", "HS": "H", "N": "N", "NA": "N", "NS": "N", "O": "O",
             "OA": "O", "OS": "O", "S": "S", "SA": "S", "P": "P", "F": "F", "I": "I", "CL": "Cl", "BR": "Br",
             "MG": "Mg", "ZN": "Zn", "FE": "Fe", "MN": "Mn", "CA": "Ca", "CU": "Cu", "NI": "Ni", "CO": "Co"}
LOGAM = {"Zn", "Mg", "Ca", "Mn", "Fe", "Cu", "Ni", "Co", "Na", "K"}

DONOR_P = {"N": None, "ARG": {"NE", "NH1", "NH2"}, "ASN": {"ND2"}, "GLN": {"NE2"}, "HIS": {"ND1", "NE2"},
           "LYS": {"NZ"}, "SER": {"OG"}, "THR": {"OG1"}, "TYR": {"OH"}, "TRP": {"NE1"}, "CYS": {"SG"}}
AKSEPTOR_P = {"ASP": {"OD1", "OD2"}, "GLU": {"OE1", "OE2"}, "ASN": {"OD1"}, "GLN": {"OE1"},
              "HIS": {"ND1", "NE2"}, "SER": {"OG"}, "THR": {"OG1"}, "TYR": {"OH"}, "MET": {"SD"}}
NEGATIF_P = {"ASP": {"OD1", "OD2"}, "GLU": {"OE1", "OE2"}}
POSITIF_P = {"LYS": {"NZ"}, "ARG": {"NE", "NH1", "NH2"}}
CINCIN_P = {"PHE": [("CG", "CD1", "CE1", "CZ", "CE2", "CD2")], "TYR": [("CG", "CD1", "CE1", "CZ", "CE2", "CD2")],
            "HIS": [("CG", "ND1", "CE1", "NE2", "CD2")],
            "TRP": [("CG", "CD1", "NE1", "CE2", "CD2"), ("CD2", "CE2", "CZ2", "CH2", "CZ3", "CE3")]}


# ------------------------------------------------------------------ reseptor
@dataclass
class Reseptor:
    nama: list
    resn: list
    rantai: list
    resi: list
    el: list
    xyz: np.ndarray
    punya_h: bool = False
    _res: dict = field(default_factory=dict)

    def label(self, i):
        return f"{self.resn[i]} {self.resi[i]}" + (f" {self.rantai[i]}" if self.rantai[i].strip() else "")

    def kunci(self, i):
        return (self.rantai[i], self.resi[i], self.resn[i])


def baca_reseptor(teks):
    """Atom reseptor dari teks PDBQT atau PDB."""
    nama, resn, rantai, resi, el, xyz = [], [], [], [], [], []
    for b in teks.splitlines():
        if not b.startswith(("ATOM", "HETATM")):
            continue
        try:
            x, y, z = float(b[30:38]), float(b[38:46]), float(b[46:54])
            r = int(b[22:26])
        except ValueError:
            continue
        tipe = b[77:].split()[0] if len(b) > 77 and b[77:].split() else ""
        e = b[76:78].strip()
        if len(b) > 79 and tipe:  # PDBQT: tipe AD di kolom 78+
            e = ELEMEN_AD.get(tipe.upper(), tipe[:2].capitalize())
        e = e.capitalize() if e else (b[12:16].strip()[:1] or "C")
        nama.append(b[12:16].strip())
        resn.append(b[17:20].strip())
        rantai.append(b[21])
        resi.append(r)
        el.append(e)
        xyz.append((x, y, z))
    rec = Reseptor(nama, resn, rantai, resi, el, np.array(xyz, dtype=float).reshape(-1, 3))
    rec.punya_h = "H" in el
    return rec


# ------------------------------------------------------------------- ligan
def pose_mol(pdbqt_ligan_masukan, pose_pdbqt):
    """Bangun RDKit Mol (dengan H, orde ikatan & muatan benar) dari blok pose memakai REMARK SMILES masukan."""
    from meeko import PDBQTMolecule, RDKitMolCreate
    rem = "\n".join(b for b in pdbqt_ligan_masukan.splitlines() if b.startswith("REMARK"))
    pm = PDBQTMolecule(rem + "\n" + pose_pdbqt + "\n", skip_typing=True)
    mols = RDKitMolCreate.from_pdbqt_mol(pm)
    if not mols or mols[0] is None:
        raise ValueError("Pose tidak bisa diubah menjadi molekul RDKit.")
    return mols[0]


def mol_dari_objek(o):
    """RDKit Mol dari objek ligan/pose di viewer (SDF atau PDB)."""
    from rdkit import Chem
    if o.fmt == "sdf":
        return Chem.MolFromMolBlock(o.teks, removeHs=False)
    from .prep_ligan import _dari_pdb
    return _dari_pdb(o.teks)


_pabrik = None


def _fitur(mol):
    global _pabrik
    from rdkit import RDConfig
    from rdkit.Chem import ChemicalFeatures
    if _pabrik is None:
        _pabrik = ChemicalFeatures.BuildFeatureFactory(os.path.join(RDConfig.RDDataDir, "BaseFeatures.fdef"))
    hasil = {}
    for f in _pabrik.GetFeaturesForMol(mol):
        hasil.setdefault(f.GetFamily(), []).append(tuple(f.GetAtomIds()))
    return hasil


def _sudut(a, b, c):
    u, v = a - b, c - b
    nu, nv = np.linalg.norm(u), np.linalg.norm(v)
    if nu == 0 or nv == 0:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(u, v) / (nu * nv))))))


def _cincin(pts):
    pts = np.asarray(pts, dtype=float)
    c = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - c)
    return c, vt[2] / np.linalg.norm(vt[2])


def _offset(c1, n1, c2):
    d = c2 - c1
    return float(np.linalg.norm(d - np.dot(d, n1) * n1))


# --------------------------------------------------------------- interaksi
def interaksi(rec, mol, radius=8.0):
    """Daftar interaksi (dict) antara Reseptor dan RDKit Mol (koordinat konformer 0)."""
    from rdkit import Chem
    if mol is None or mol.GetNumConformers() == 0:
        return []
    L = mol.GetConformer().GetPositions()
    berat_l = [a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum() > 1]
    peta_berat = {i: k for k, i in enumerate(berat_l)}   # indeks dalam molekul tanpa H (untuk diagram 2D)
    el_l = [a.GetSymbol() for a in mol.GetAtoms()]
    # reseptor: hanya atom dalam radius dari ligan
    d_all = np.linalg.norm(rec.xyz[:, None, :] - L[None, berat_l, :], axis=2)
    dekat_res = {rec.kunci(i) for i in np.where(d_all.min(axis=1) <= radius)[0]}
    idx = [i for i in range(len(rec.el)) if rec.kunci(i) in dekat_res]
    if not idx:
        return []
    P = rec.xyz[idx]
    per_res = {}
    for k, i in enumerate(idx):
        per_res.setdefault(rec.kunci(i), []).append(k)

    def nm(k):
        return rec.nama[idx[k]]

    def el(k):
        return rec.el[idx[k]]

    def tetangga_p(k):
        hasil = []
        for j in per_res[rec.kunci(idx[k])]:
            if j != k:
                lim = 1.25 if "H" in (el(k), el(j)) else 1.9
                if np.linalg.norm(P[k] - P[j]) <= lim:
                    hasil.append(j)
        return hasil

    # sambungan antar residu (C–N peptida) tidak dihitung: cukup untuk kepolaran karbon
    D = np.linalg.norm(P[:, None, :] - L[None, :, :], axis=2)
    fit = _fitur(mol)
    hasil = []

    def tambah(jenis, k, li, jarak, sudut=None, sub="", p_xyz=None, l_xyz=None, anchor=None):
        i = idx[k] if k is not None else None
        kunci = rec.kunci(i)
        hasil.append({"jenis": jenis, "sub": sub, "resn": kunci[2], "resi": kunci[1], "rantai": kunci[0].strip(),
                      "residu": rec.label(i), "atom_p": nm(k) if k is not None else "",
                      "atom_l": [int(x) for x in (li if isinstance(li, (list, tuple)) else [li])],
                      "anchor": [peta_berat[x] for x in (anchor if anchor is not None else
                                 (li if isinstance(li, (list, tuple)) else [li])) if x in peta_berat],
                      "p": [round(float(v), 3) for v in (p_xyz if p_xyz is not None else P[k])],
                      "l": [round(float(v), 3) for v in (l_xyz if l_xyz is not None else L[li])],
                      "jarak": round(float(jarak), 2), "sudut": None if sudut is None else round(float(sudut), 1)})

    # ---- ikatan hidrogen
    def donor_p(k):
        r = rec.resn[idx[k]]
        n = nm(k)
        return (n == "N" and r != "PRO") or n in DONOR_P.get(r, set())

    def akseptor_p(k):
        n = nm(k)
        return n in ("O", "OXT") or n in AKSEPTOR_P.get(rec.resn[idx[k]], set())

    don_l = {a[0] for a in fit.get("Donor", [])}
    aks_l = {a[0] for a in fit.get("Acceptor", [])}
    sudah = set()
    for k in range(len(idx)):
        if el(k) not in ("N", "O", "S"):
            continue
        if donor_p(k):  # protein donor -> ligan akseptor
            hs = [j for j in tetangga_p(k) if el(j) == "H"]
            for li in aks_l:
                d = D[k, li]
                if d > KRITERIA["hbond_da"]:
                    continue
                ok, sd = not hs and not rec.punya_h, None
                for h in hs:
                    if np.linalg.norm(P[h] - L[li]) <= KRITERIA["hbond_ha"]:
                        s = _sudut(P[k], P[h], L[li])
                        if s >= KRITERIA["hbond_sudut"]:
                            ok, sd = True, s
                if ok and (k, li) not in sudah:
                    sudah.add((k, li))
                    tambah("hbond", k, li, d, sd, "protein donor")
        if akseptor_p(k):  # ligan donor -> protein akseptor
            for li in don_l:
                d = D[k, li]
                if d > KRITERIA["hbond_da"]:
                    continue
                hs = [n.GetIdx() for n in mol.GetAtomWithIdx(li).GetNeighbors() if n.GetAtomicNum() == 1]
                ok, sd = not hs, None
                for h in hs:
                    if np.linalg.norm(L[h] - P[k]) <= KRITERIA["hbond_ha"]:
                        s = _sudut(L[li], L[h], P[k])
                        if s >= KRITERIA["hbond_sudut"]:
                            ok, sd = True, s
                if ok and (k, li) not in sudah:
                    sudah.add((k, li))
                    tambah("hbond", k, li, d, sd, "ligan donor")

    # ---- hidrofobik
    def c_nonpolar_l(a):
        if a.GetSymbol() in ("Cl", "Br", "I"):
            return True
        return a.GetSymbol() == "C" and all(n.GetSymbol() in ("C", "H") for n in a.GetNeighbors())

    hf_l = [a.GetIdx() for a in mol.GetAtoms() if c_nonpolar_l(a)]
    terbaik = {}
    for k in range(len(idx)):
        if el(k) != "C" or nm(k) in ("C", "CA"):
            continue
        if any(el(j) not in ("C", "H") for j in tetangga_p(k)):
            continue
        for li in hf_l:
            d = D[k, li]
            if d <= KRITERIA["hidrofobik"]:
                kk = rec.kunci(idx[k])
                if kk not in terbaik or d < terbaik[kk][2]:
                    terbaik[kk] = (k, li, d)
    for k, li, d in terbaik.values():
        tambah("hidrofobik", k, li, d)

    # ---- cincin
    ring_l = []
    for r in mol.GetRingInfo().AtomRings():
        if all(mol.GetAtomWithIdx(i).GetIsAromatic() for i in r):
            c, n = _cincin(L[list(r)])
            ring_l.append((list(r), c, n))
    ring_p = []
    for kk, anggota in per_res.items():
        nama = {nm(k): k for k in anggota}
        for pola in CINCIN_P.get(kk[2], []):
            if all(a in nama for a in pola):
                ks = [nama[a] for a in pola]
                c, n = _cincin(P[ks])
                ring_p.append((ks, c, n))
    for rl, cl, nl in ring_l:
        for rp, cp, np_ in ring_p:
            d = float(np.linalg.norm(cl - cp))
            if d > KRITERIA["pi"]:
                continue
            a = math.degrees(math.acos(min(1.0, abs(float(np.dot(nl, np_))))))
            off = min(_offset(cl, nl, cp), _offset(cp, np_, cl))
            if a <= KRITERIA["pi_tumpuk_sudut"] and off <= KRITERIA["pi_offset"]:
                tambah("pi", rp[0], rl, d, a, "tumpuk", p_xyz=cp, l_xyz=cl)
            elif a >= KRITERIA["pi_t_sudut"] and off <= KRITERIA["pi_offset"] + 1.5:
                tambah("pi", rp[0], rl, d, a, "bentuk T", p_xyz=cp, l_xyz=cl)

    # ---- muatan
    kation_l = [g for g in fit.get("PosIonizable", [])] + \
               [(a.GetIdx(),) for a in mol.GetAtoms() if a.GetFormalCharge() > 0 and a.GetSymbol() == "N"]
    anion_l = [g for g in fit.get("NegIonizable", [])] + \
              [(a.GetIdx(),) for a in mol.GetAtoms() if a.GetFormalCharge() < 0 and a.GetSymbol() == "O"]
    kation_l = list({tuple(sorted(g)) for g in kation_l})
    anion_l = list({tuple(sorted(g)) for g in anion_l})

    def his_positif(kk):
        anggota = per_res[kk]
        nd = [k for k in anggota if nm(k) in ("ND1", "NE2")]
        return rec.punya_h and len(nd) == 2 and all(any(el(j) == "H" for j in tetangga_p(k)) for k in nd)

    kation_p, anion_p = [], []
    for kk, anggota in per_res.items():
        for k in anggota:
            if nm(k) in POSITIF_P.get(kk[2], set()) or (kk[2] == "HIS" and nm(k) in ("ND1", "NE2")
                                                         and his_positif(kk)):
                kation_p.append(k)
            if nm(k) in NEGATIF_P.get(kk[2], set()) or nm(k) == "OXT":
                anion_p.append(k)
    sudah = set()
    for gp, gl in ((kation_p, anion_l), (anion_p, kation_l)):
        for k in gp:
            for g in gl:
                d = min(D[k, i] for i in g)
                kk = (rec.kunci(idx[k]), g)
                if d <= KRITERIA["garam"] and kk not in sudah:
                    sudah.add(kk)
                    li = min(g, key=lambda i: D[k, i])
                    tambah("garam", k, li, d)
    # π–kation: cincin ligan ↔ kation protein; cincin protein ↔ kation ligan
    sudah = set()
    for rl, cl, nl in ring_l:
        for k in kation_p:
            d = float(np.linalg.norm(P[k] - cl))
            kk = (rec.kunci(idx[k]), tuple(rl))
            if d <= KRITERIA["pikation"] and _offset(cl, nl, P[k]) <= KRITERIA["pikation_offset"] and kk not in sudah:
                sudah.add(kk)
                tambah("pikation", k, rl, d, sub="kation protein", l_xyz=cl)
    for rp, cp, np_ in ring_p:
        for g in kation_l:
            c = L[list(g)].mean(axis=0)
            d = float(np.linalg.norm(c - cp))
            if d <= KRITERIA["pikation"] and _offset(cp, np_, c) <= KRITERIA["pikation_offset"]:
                tambah("pikation", rp[0], list(g), d, sub="kation ligan", p_xyz=cp, l_xyz=c)

    # ---- halogen
    for a in mol.GetAtoms():
        if a.GetSymbol() not in ("Cl", "Br", "I"):
            continue
        cn = [n.GetIdx() for n in a.GetNeighbors() if n.GetSymbol() == "C"]
        if not cn:
            continue
        xi = a.GetIdx()
        for k in range(len(idx)):
            if el(k) in ("O", "N", "S") and D[k, xi] <= KRITERIA["halogen"]:
                s = _sudut(L[cn[0]], L[xi], P[k])
                if s >= KRITERIA["halogen_sudut"]:
                    tambah("halogen", k, xi, D[k, xi], s)

    # ---- logam
    for k in range(len(idx)):
        if el(k) in LOGAM:
            for li in range(len(el_l)):
                if el_l[li] in ("O", "N", "S") and D[k, li] <= KRITERIA["logam"]:
                    tambah("logam", k, li, D[k, li])

    # ---- van der Waals (residu tanpa interaksi lain)
    ada = {(h["rantai"], h["resi"], h["resn"]) for h in hasil}
    for kk, anggota in per_res.items():
        if (kk[0].strip(), kk[1], kk[2]) in ada:
            continue
        berat = [k for k in anggota if el(k) != "H"]
        if not berat:
            continue
        sub = D[np.ix_(berat, berat_l)]
        if sub.min() <= KRITERIA["vdw"]:
            a, b = np.unravel_index(int(sub.argmin()), sub.shape)
            tambah("vdw", berat[a], berat_l[b], sub.min())
    hasil.sort(key=lambda h: (URUT_JENIS.index(h["jenis"]), h["jarak"]))
    return hasil


def hitung(daftar):
    """Jumlah interaksi per jenis (tanpa vdW)."""
    n = {j: 0 for j in URUT_JENIS if j != "vdw"}
    for h in daftar:
        if h["jenis"] in n:
            n[h["jenis"]] += 1
    return n


def residu_kontak(daftar, jenis_min=True):
    """{label residu: jenis terkuat} untuk peta panas."""
    hasil = {}
    for h in daftar:
        r = h["residu"]
        if r not in hasil or URUT_JENIS.index(h["jenis"]) < URUT_JENIS.index(hasil[r]):
            hasil[r] = h["jenis"]
    return hasil


# --------------------------------------------------------------- RMSD & LE
def _graf_umum(mol):
    """Salinan atom berat dengan semua ikatan tunggal & tanpa muatan: cocok lintas protonasi/orde ikatan."""
    from rdkit import Chem
    m = Chem.RWMol(Chem.RemoveAllHs(mol, sanitize=False))
    for a in m.GetAtoms():
        a.SetFormalCharge(0)
        a.SetIsAromatic(False)
        a.SetNoImplicit(True)
        a.SetNumExplicitHs(0)
    for b in m.GetBonds():
        b.SetBondType(Chem.BondType.SINGLE)
        b.SetIsAromatic(False)
    m = m.GetMol()
    m.UpdatePropertyCache(strict=False)
    return m


def rmsd_simetri(prb, ref):
    """RMSD atom berat tanpa penjajaran, minimum atas semua pemetaan simetri (graf tanpa orde ikatan)."""
    a, b = _graf_umum(prb), _graf_umum(ref)
    if a.GetNumAtoms() != b.GetNumAtoms():
        raise ValueError(f"Jumlah atom berat berbeda ({a.GetNumAtoms()} vs {b.GetNumAtoms()}).")
    cocok = a.GetSubstructMatches(b, uniquify=False, useChirality=False, maxMatches=5000)
    if not cocok:
        raise ValueError("Struktur pose dan kristal tidak cocok.")
    pa, pb = a.GetConformer().GetPositions(), b.GetConformer().GetPositions()
    return min(float(np.sqrt(((pa[list(m)] - pb) ** 2).sum(axis=1).mean())) for m in cocok)


def mol_kristal(teks_pdb):
    from .prep_ligan import _dari_pdb
    return _dari_pdb(teks_pdb)


def efisiensi_ligan(energi, atom_berat):
    return round(-energi / atom_berat, 3) if atom_berat else None


# ------------------------------------------------------- ringkasan per ligan
def ringkas_ligan(proyek, l, pose, rec):
    """Tambahkan LE, jumlah interaksi, residu kontak, dan RMSD kristal ke dict ligan job (in-place)."""
    lig = proyek.cari_ligan(l["id"])
    teks_in = proyek.p(l["pdbqt"]).read_text()
    kr = None
    if lig and lig.get("kristal") and proyek.p(lig["kristal"]).exists():
        try:
            kr = mol_kristal(proyek.p(lig["kristal"]).read_text())
        except Exception:
            kr = None
    terbaik = None
    for i, p in enumerate(pose):
        if i > 0 and kr is None:
            break
        try:
            m = pose_mol(teks_in, p.pdbqt)
        except Exception:
            continue
        if i == 0:
            terbaik = m
        if kr is not None and i < len(l["pose"]):
            try:
                l["pose"][i]["rmsd_kristal"] = round(rmsd_simetri(m, kr), 2)
            except ValueError:
                kr = None
    if terbaik is not None:
        n_berat = terbaik.GetNumHeavyAtoms()
        l["atom_berat"] = n_berat
        l["le"] = efisiensi_ligan(pose[0].energi, n_berat)
        if rec is not None:
            I = interaksi(rec, terbaik)
            l["interaksi"] = hitung(I)
            l["residu"] = residu_kontak(I)
    if l["pose"] and "rmsd_kristal" in l["pose"][0]:
        l["rmsd_kristal"] = l["pose"][0]["rmsd_kristal"]
        l["rmsd_kristal_min"] = min(p.get("rmsd_kristal", 99) for p in l["pose"])


def analisis_ulang(proyek, lapor=None):
    """Lengkapi ringkasan (LE, interaksi, RMSD kristal) untuk ligan selesai yang belum punya. Untuk proyek lama."""
    from . import mesin as M
    rec_cache = {}
    n = 0
    for j in proyek.job:
        rf = proyek.p(j["reseptor"]) if j.get("reseptor") else None
        if rf is None or not rf.exists():
            continue
        if str(rf) not in rec_cache:
            rec_cache[str(rf)] = baca_reseptor(rf.read_text())
        for l in j["ligan"]:
            if l["status"] != "selesai" or ("le" in l and "interaksi" in l):
                continue
            out = proyek.p(l["keluaran"]) if l.get("keluaran") else None
            if not out or not out.exists():
                continue
            try:
                ringkas_ligan(proyek, l, M.baca_hasil(j["mesin"], out), rec_cache[str(rf)])
                n += 1
            except Exception as e:
                if lapor:
                    lapor.log.emit(f"Analisis {l['nama']} gagal: {e}")
    return n
