"""Residu hilang: deteksi celah rantai dari SEQRES dan pengisian loop sebelum preparasi reseptor.

Kristal sering kehilangan loop lentur yang tidak terlihat di peta elektron. Bila loop itu dekat kantong,
docking ke struktur berlubang memakai kantong yang terlalu terbuka. Dua cara pengisian:

  AlphaFold  segmen yang hilang diambil dari model AlphaFold DB untuk UniProt yang sama, disejajarkan pada
             residu sayap di kedua sisi celah, lalu sambungannya diminimisasi dengan OpenMM (atom lain
             dikekang). Uji hapus-loop pada 3KS3: RMSD tulang punggung 0,25-0,72 Å untuk loop 4-12 residu.
             Keandalannya mengikuti pLDDT segmen itu, yang ikut dilaporkan.
  PDBFixer   residu ditempatkan tanpa model struktur. Pada uji yang sama RMSD 3,8-12 Å, jadi hanya dipakai
             untuk celah pendek (<= 5 residu) dan selalu diberi peringatan.

Celah dicari dengan penjajaran sekuens (gemmi), bukan nomor residu: penomoran kristal sering melompat
(karbonat anhidrase II tidak punya residu 126) sehingga pencocokan berbasis nomor seperti di PDBFixer gagal.
Ujung-N/C yang hilang tidak dimodelkan: ekor lentur, bukan bagian kantong.
"""
import io
import re
from dataclasses import asdict, dataclass, field

import gemmi
import numpy as np

MAKS_PDBFIXER = 5            # residu; di atas ini PDBFixer tidak dipakai pada mode otomatis
PLDDT_MIN = 50.0             # segmen AlphaFold di bawah ini dianggap tidak terstruktur
SAYAP = 4                    # residu sayap per sisi untuk penjajaran
K_KEKANG = 1000.0            # kJ/mol/nm^2 pada atom berat di luar loop saat minimisasi
TIGA = {"ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H",
        "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
        "TYR": "Y", "VAL": "V", "MSE": "M", "SEC": "U", "PYL": "O"}


class GalatLoop(Exception):
    pass


@dataclass
class Celah:
    rantai: str
    i_sebelum: int               # indeks residu polimer sebelum celah (-1 = ujung-N)
    sebelum: str                 # "GLU 165" atau ""
    sesudah: str
    n: int                       # jumlah residu hilang (perkiraan bila tanpa SEQRES)
    nama: list = field(default_factory=list)     # nama residu dari SEQRES; kosong bila tidak diketahui
    jenis: str = "internal"      # internal | ujung-N | ujung-C
    jarak_kantong: float = None  # Å, atom sayap terdekat ke titik kantong
    bentang: float = None        # Å, jarak CA-CA kedua sayap
    mungkin: bool = True         # bentang <= 3,8 Å x (n + 1)
    # diisi setelah pengisian
    metode: str = ""
    catatan: str = ""
    plddt: float = None
    sambungan: tuple = ()
    bentrok: int = None
    dimodelkan: list = field(default_factory=list)

    def label(self):
        rentang = f"{self.sebelum} – {self.sesudah}" if self.sebelum and self.sesudah else (self.sebelum or self.sesudah)
        return f"{self.rantai}: {self.n} residu ({rentang})"

    def ke_dict(self):
        return asdict(self)


# ------------------------------------------------------------------ sekuens & UniProt dari berkas sumber
def info_sekuens(teks, fmt="pdb"):
    """Teks PDB/mmCIF asli -> ({rantai: [nama residu SEQRES]}, {rantai: aksesi UniProt})."""
    sek, unp = {}, {}
    try:
        if fmt == "cif":
            doc = gemmi.cif.read_string(teks)
            st = gemmi.make_structure_from_block(doc.sole_block())
            blok = doc.sole_block()
            ref = blok.find("_struct_ref.", ["id", "db_name", "pdbx_db_accession"])
            akses = {r[0]: r[2] for r in ref if r[1].upper() == "UNP"}
            rs = blok.find("_struct_ref_seq.", ["ref_id", "pdbx_strand_id"])
            for r in rs:
                if r[0] in akses:
                    unp[r[1]] = akses[r[0]]
        else:
            st = gemmi.read_pdb_string(teks)
            for b in teks.splitlines():
                if b.startswith("DBREF ") and b[26:32].strip() == "UNP":
                    unp.setdefault(b[12].strip() or "A", b[33:41].strip())
        st.setup_entities()
    except Exception:
        return {}, {}
    for ch in st[0]:
        pol = ch.get_polymer()
        if not len(pol):
            continue
        ent = st.get_entity_of(pol)
        if ent is not None and ent.full_sequence and ent.polymer_type == gemmi.PolymerType.PeptideL:
            sek[ch.name] = [s.split(",")[0] for s in ent.full_sequence]
    if fmt != "cif" and not sek:
        sek = _seqres_pdb(teks)
    return sek, unp


def _seqres_pdb(teks):
    """Baca baris SEQRES langsung (berkas header RCSB tidak memuat atom, jadi entitas gemmi kosong)."""
    sek = {}
    for b in teks.splitlines():
        if b.startswith("SEQRES"):
            sek.setdefault(b[11].strip() or "A", []).extend(b[19:].split())
    return {k: v for k, v in sek.items() if any(x in TIGA for x in v)}


def info_dari_rcsb(kode):
    """SEQRES dan DBREF dari header RCSB (tanpa koordinat, ±20 KB) untuk struktur yang dimuat tanpa SEQRES."""
    from . import sumber_data
    kode = re.sub(r"[^A-Za-z0-9]", "", kode).upper()[:4]
    teks, _ = sumber_data.ambil_teks(f"https://files.rcsb.org/header/{kode}.pdb", batas=60, coba=2,
                                     cache_jam=24 * 30, lisensi="CC0 1.0", sumber="RCSB PDB")
    unp = {}
    for b in teks.splitlines():
        if b.startswith("DBREF ") and b[26:32].strip() == "UNP":
            unp.setdefault(b[12].strip() or "A", b[33:41].strip())
    return _seqres_pdb(teks), unp


# ------------------------------------------------------------------ deteksi
def _label(r):
    return f"{r.name} {r.seqid.num}{r.seqid.icode.strip()}"


def _ca(r):
    a = r.find_atom("CA", "*")
    return None if a is None else np.array([a.pos.x, a.pos.y, a.pos.z])


def _jarak_titik(res_list, titik):
    if titik is None or not len(titik):
        return None
    t = np.asarray(titik, float)
    d = []
    for r in res_list:
        for a in r:
            p = np.array([a.pos.x, a.pos.y, a.pos.z])
            d.append(float(np.sqrt(((t - p) ** 2).sum(1)).min()))
    return round(min(d), 1) if d else None


def cari_celah(st, sekuens=None, titik_kantong=None):
    """Celah per rantai protein. sekuens: {rantai: [nama]} dari info_sekuens; tanpa itu celah dicari dari
    jarak C-N (> 2 Å) dan jumlahnya ditebak dari selisih nomor residu."""
    hasil = []
    for ch in st[0]:
        pol = ch.get_polymer()
        if len(pol) < 2 or (pol.check_polymer_type() != gemmi.PolymerType.PeptideL):
            continue
        full = (sekuens or {}).get(ch.name)
        if full:
            hasil += _celah_sekuens(ch.name, pol, full, titik_kantong)
        else:
            hasil += _celah_geometri(ch.name, pol, titik_kantong)
    return hasil


def _celah_sekuens(rantai, pol, full, titik):
    aln = gemmi.align_sequence_to_polymer(full, pol, gemmi.PolymerType.PeptideL, gemmi.AlignmentScoring())
    a = aln.add_gaps(gemmi.one_letter_code(full), 1)
    b = aln.add_gaps(gemmi.one_letter_code([r.name for r in pol]), 2)
    hasil, run, i_obs, i_full = [], [], -1, 0
    for x, y in zip(a, b):
        if x != "-" and y == "-":
            run.append(full[i_full])
        if y != "-":
            if run:
                hasil.append(_buat_celah(rantai, pol, i_obs, run, titik))
                run = []
            i_obs += 1
        if x != "-":
            i_full += 1
    if run:
        hasil.append(_buat_celah(rantai, pol, i_obs, run, titik))
    return hasil


def _buat_celah(rantai, pol, i_sebelum, nama, titik):
    n = len(nama)
    if i_sebelum < 0:
        jenis, sayap = "ujung-N", [pol[0]]
    elif i_sebelum >= len(pol) - 1:
        jenis, sayap = "ujung-C", [pol[len(pol) - 1]]
    else:
        jenis, sayap = "internal", [pol[i_sebelum], pol[i_sebelum + 1]]
    c = Celah(rantai=rantai, i_sebelum=i_sebelum, n=n, nama=list(nama), jenis=jenis,
              sebelum=_label(pol[i_sebelum]) if i_sebelum >= 0 else "",
              sesudah=_label(pol[i_sebelum + 1]) if i_sebelum + 1 < len(pol) else "",
              jarak_kantong=_jarak_titik(sayap, titik))
    if jenis == "internal":
        p, q = _ca(sayap[0]), _ca(sayap[1])
        if p is not None and q is not None:
            c.bentang = round(float(np.linalg.norm(p - q)), 1)
            c.mungkin = c.bentang <= 3.8 * (n + 1) + 0.5
    return c


def _celah_geometri(rantai, pol, titik):
    hasil = []
    for i in range(len(pol) - 1):
        c_atom, n_atom = pol[i].find_atom("C", "*"), pol[i + 1].find_atom("N", "*")
        if c_atom is None or n_atom is None or c_atom.pos.dist(n_atom.pos) <= 2.0:
            continue
        n = max(1, pol[i + 1].seqid.num - pol[i].seqid.num - 1)
        hasil.append(_buat_celah(rantai, pol, i, ["UNK"] * n, titik))
        hasil[-1].nama = []
    return hasil


# ------------------------------------------------------------------ geometri bantu
def _kabsch(P, Q):
    pc, qc = P.mean(0), Q.mean(0)
    H = (P - pc).T @ (Q - qc)
    U, _S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, d]) @ U.T
    return R, qc - R @ pc


def _pos(r, nama):
    a = r.find_atom(nama, "*")
    return None if a is None else np.array([a.pos.x, a.pos.y, a.pos.z])


def _indeks_rantai(ch, res):
    for k, r in enumerate(ch):
        if r.seqid == res.seqid and r.name == res.name:
            return k
    raise GalatLoop(f"residu {_label(res)} tidak ditemukan di rantai {ch.name}")


def _nomori(sebelum, sesudah, m):
    """Nomor residu sisipan: berurutan bila celah nomornya pas, kalau tidak pakai kode sisipan pada residu
    sebelum (165A, 165B, …), supaya residu sesudahnya tidak perlu dinomori ulang."""
    a, b = sebelum.seqid.num, sesudah.seqid.num
    if b - a - 1 == m and not sebelum.seqid.icode.strip() and not sesudah.seqid.icode.strip():
        return [gemmi.SeqId(a + k + 1, " ") for k in range(m)]
    if m > 26:
        raise GalatLoop("celah terlalu panjang untuk dinomori dengan kode sisipan")
    return [gemmi.SeqId(a, chr(ord("A") + k)) for k in range(m)]


def _residu_baru(nama, seqid, atom, contoh, b_iso=0.0):
    r = gemmi.Residue()
    r.name = nama
    r.seqid = seqid
    r.het_flag = "A"
    r.entity_type = gemmi.EntityType.Polymer
    r.subchain = contoh.subchain
    for nm, el, p in atom:
        a = gemmi.Atom()
        a.name = nm
        a.element = gemmi.Element(el)
        a.pos = gemmi.Position(*[float(v) for v in p])
        a.occ = 1.0
        a.b_iso = b_iso
        r.add_atom(a)
    return r


# ------------------------------------------------------------------ cangkok AlphaFold
def model_alphafold(aksesi):
    """Teks PDB model AlphaFold DB untuk aksesi UniProt (cache sumber_data). GalatLoop bila tidak ada."""
    from . import alphafold, sumber_data
    try:
        m = alphafold.info(aksesi)
        teks, _ = sumber_data.ambil_teks(m["pdbUrl"], batas=120, coba=2, cache_jam=24 * 90,
                                         lisensi="CC BY 4.0", sumber="AlphaFold DB")
        return teks, f"{m.get('entryId', aksesi)} v{m.get('latestVersion', '?')}"
    except Exception as e:
        raise GalatLoop(f"model AlphaFold untuk {aksesi} tidak tersedia ({e})") from e


def _peta_ke_af(pol, af_res):
    obs = gemmi.one_letter_code([r.name for r in pol])
    af = gemmi.one_letter_code([r.name for r in af_res])
    aln = gemmi.align_string_sequences(list(obs), list(af), [])
    a, b = aln.add_gaps(obs, 1), aln.add_gaps(af, 2)
    peta, i, j = {}, 0, 0
    for x, y in zip(a, b):
        if x != "-" and y != "-":
            peta[i] = j
        i += x != "-"
        j += y != "-"
    return peta


def _cangkok(ch, celah, af_res, peta):
    """Sisipkan segmen AF untuk satu celah internal. -> (residu baru, pLDDT rerata, rms sayap)."""
    pol = ch.get_polymer()
    i = celah.i_sebelum
    if i not in peta or i + 1 not in peta:
        raise GalatLoop("residu sayap tidak terpetakan ke model AlphaFold")
    j, k = peta[i], peta[i + 1]
    seg = af_res[j + 1:k]
    if not seg:
        raise GalatLoop("model AlphaFold tidak memuat residu di antara kedua sayap")
    P, Q = [], []
    sayap = [x for x in range(i - SAYAP + 1, i + 1) if x in peta] + [x for x in range(i + 1, i + 1 + SAYAP) if x in peta]
    for x in sayap:
        for nm in ("N", "CA", "C"):
            p, q = _pos(af_res[peta[x]], nm), _pos(pol[x], nm)
            if p is not None and q is not None:
                P.append(p)
                Q.append(q)
    if len(P) < 6:
        raise GalatLoop("atom sayap terlalu sedikit untuk penjajaran")
    P, Q = np.array(P), np.array(Q)
    R, t = _kabsch(P, Q)
    rms = float(np.sqrt((((P @ R.T + t) - Q) ** 2).sum(1).mean()))
    seqid = _nomori(pol[i], pol[i + 1], len(seg))
    nama_kristal = celah.nama if len(celah.nama) == len(seg) else []
    baru = []
    for m_, (r_af, sid) in enumerate(zip(seg, seqid)):
        nama = r_af.name
        atom = [(a.name, a.element.name, R @ np.array([a.pos.x, a.pos.y, a.pos.z]) + t)
                for a in r_af if a.element.name not in ("H", "D")]
        if nama_kristal and nama_kristal[m_] != nama:
            # mutasi di konstruk kristal: tulang punggung dari AF, rantai samping dibangun ulang PDBFixer
            nama = nama_kristal[m_]
            atom = [x for x in atom if x[0] in ("N", "CA", "C", "O") or (x[0] == "CB" and nama != "GLY")]
        baru.append(_residu_baru(nama, sid, atom, pol[i], b_iso=r_af[0].b_iso))
    pos = _indeks_rantai(ch, pol[i]) + 1
    for m_, r in enumerate(baru):
        ch.add_residue(r, pos + m_)
    plddt = float(np.mean([r[0].b_iso for r in seg]))
    return [(ch.name, r.seqid.num, r.seqid.icode) for r in baru], plddt, rms, (len(nama_kristal) and
                                                                                 any(a != b.name for a, b in zip(nama_kristal, seg)))


# ------------------------------------------------------------------ PDBFixer
def _isi_pdbfixer(st, daftar):
    """daftar: [(Celah)] celah internal dengan nama residu diketahui. Disisipkan langsung ke st."""
    from openmm import unit
    from pdbfixer import PDBFixer
    prot = _hanya_polimer(st)
    rantai = [ch.name for ch in prot[0]]
    # indeks celah dihitung ulang: cangkok AlphaFold di rantai yang sama bisa menggeser posisinya
    idx = {id(c): _i_sekarang(prot[0][c.rantai], c) for c in daftar}
    f = PDBFixer(pdbfile=io.StringIO(prot.make_pdb_string(_opsi_tulis())))
    f.missingResidues = {(rantai.index(c.rantai), idx[id(c)] + 1): list(c.nama) for c in daftar}
    f.findMissingAtoms()
    f.missingAtoms, f.missingTerminals = {}, {}
    f.addMissingAtoms(seed=7)
    pos = f.positions.value_in_unit(unit.angstrom)
    ch_fix = list(f.topology.chains())
    hasil = {}
    for c in daftar:
        res = list(ch_fix[rantai.index(c.rantai)].residues())
        seg = res[idx[id(c)] + 1:idx[id(c)] + 1 + len(c.nama)]
        hasil[id(c)] = [(r.name, [(a.name, a.element.symbol, np.array([pos[a.index][0], pos[a.index][1],
                                                                      pos[a.index][2]]))
                                  for a in r.atoms() if a.element.symbol not in ("H", "D")]) for r in seg]
    # sisipkan dari belakang supaya indeks celah lain di rantai yang sama tidak bergeser
    kunci = []
    for c in sorted(daftar, key=lambda x: (x.rantai, -idx[id(x)])):
        ch = st[0][c.rantai]
        pol = ch.get_polymer()
        i = _i_sekarang(ch, c)
        seg = hasil[id(c)]
        seqid = _nomori(pol[i], pol[i + 1], len(seg))
        posisi = _indeks_rantai(ch, pol[i]) + 1
        baru = [_residu_baru(nm, sid, atom, pol[i]) for (nm, atom), sid in zip(seg, seqid)]
        for m_, r in enumerate(baru):
            ch.add_residue(r, posisi + m_)
        c.dimodelkan = [f"{r.name} {r.seqid.num}{r.seqid.icode.strip()}" for r in baru]
        kunci += [(c.rantai, r.seqid.num, r.seqid.icode) for r in baru]
    return kunci


def _i_sekarang(ch, c):
    """Indeks polimer residu sayap kiri celah c pada keadaan rantai saat ini (dicari dari labelnya)."""
    for i, r in enumerate(ch.get_polymer()):
        if _label(r) == c.sebelum:
            return i
    raise GalatLoop(f"residu sayap {c.sebelum} rantai {c.rantai} tidak ditemukan")


def _opsi_tulis():
    o = gemmi.PdbWriteOptions()
    o.minimal_file = True
    o.ter_records = True
    return o


def _hanya_polimer(st):
    s = st.clone()
    s.remove_ligands_and_waters()
    s.remove_empty_chains()
    return s


# ------------------------------------------------------------------ minimisasi sambungan
def _minimisasi(st, bebas):
    """Minimisasi OpenMM pada polimer saja; atom berat di luar `bebas` dikekang kuat. Koordinat residu bebas
    (beserta atom rantai samping yang dilengkapi PDBFixer) ditulis kembali ke st. bebas: set (rantai, num, icode)."""
    import openmm
    from openmm import app, unit
    from pdbfixer import PDBFixer
    prot = _hanya_polimer(st)
    f = PDBFixer(pdbfile=io.StringIO(prot.make_pdb_string(_opsi_tulis())))
    f.findMissingResidues()
    f.missingResidues = {}
    f.findNonstandardResidues()
    f.replaceNonstandardResidues()
    f.findMissingAtoms()
    f.addMissingAtoms(seed=7)
    f.addMissingHydrogens(7.4)
    # Pelarut implisit OBC2 wajib: di vakum muatan penuh Lys/Glu loop menarik pasangan jembatan garamnya terlalu
    # dekat (3KS3: H Lys168 1,24 Å dari O Glu238), lalu Meeko menolak kedua residu itu. Platform GPU dipakai bila ada.
    ff = app.ForceField("amber14-all.xml", "implicit/obc2.xml")
    sistem = ff.createSystem(f.topology, nonbondedMethod=app.CutoffNonPeriodic, nonbondedCutoff=1.2 * unit.nanometer,
                             constraints=app.HBonds)
    kekang = openmm.CustomExternalForce("k*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
    kekang.addGlobalParameter("k", K_KEKANG)
    for p in ("x0", "y0", "z0"):
        kekang.addPerParticleParameter(p)
    pos = f.positions
    kunci_atom = []
    for a in f.topology.atoms():
        r = a.residue
        k = (r.chain.id, int(re.sub(r"\D", "", r.id) or 0), (r.insertionCode or " "))
        kunci_atom.append(k)
        if a.element is not None and a.element.symbol != "H" and k not in bebas:
            x = pos[a.index].value_in_unit(unit.nanometer)
            kekang.addParticle(a.index, [x[0], x[1], x[2]])
    sistem.addForce(kekang)
    integ = openmm.VerletIntegrator(0.001)
    try:
        from .md import platform_terbaik
        _nama, plat, prop = platform_terbaik()
        ctx = openmm.Context(sistem, integ, plat, prop)
    except Exception:
        ctx = openmm.Context(sistem, integ, openmm.Platform.getPlatformByName("CPU"))
    ctx.setPositions(pos)
    openmm.LocalEnergyMinimizer.minimize(ctx, 10.0, 1000)
    akhir = ctx.getState(getPositions=True).getPositions(asNumpy=True).value_in_unit(unit.angstrom)
    per_res = {}
    for a, k in zip(f.topology.atoms(), kunci_atom):
        if k in bebas and a.element is not None and a.element.symbol != "H":
            per_res.setdefault(k, []).append((a.name, a.element.symbol, akhir[a.index]))
    for ch in st[0]:
        for i in range(len(ch)):
            r = ch[i]
            k = (ch.name, r.seqid.num, r.seqid.icode or " ")
            if k in per_res:
                pengganti = _residu_baru(r.name, r.seqid, per_res[k], r, b_iso=r[0].b_iso if len(r) else 0.0)
                pengganti.het_flag = r.het_flag
                ch.add_residue(pengganti, i)        # gemmi.Chain tidak punya __setitem__: sisip lalu hapus
                del ch[i + 1]


def _ukur(st, c, kunci):
    """Panjang ikatan peptida di kedua sambungan dan jumlah bentrok atom berat (< 2,2 Å) loop vs sekitar."""
    ch = st[0][c.rantai]
    res = list(ch)
    idx = [k for k, r in enumerate(res) if (ch.name, r.seqid.num, r.seqid.icode) in kunci]
    if not idx:
        return
    a, b = idx[0] - 1, idx[-1] + 1
    def ikatan(r1, r2):
        p, q = _pos(r1, "C"), _pos(r2, "N")
        return round(float(np.linalg.norm(p - q)), 2) if p is not None and q is not None else None
    c.sambungan = (ikatan(res[a], res[idx[0]]), ikatan(res[idx[-1]], res[b]))
    ns = gemmi.NeighborSearch(st[0], st.cell, 5).populate()
    bentrok = 0
    for k in idx:
        for at in res[k]:
            for m in ns.find_atoms(at.pos, "\0", radius=2.2):
                cra = m.to_cra(st[0])
                if cra.residue.name in ("HOH",) or cra.atom.element.name in ("H", "D"):
                    continue
                kk = (cra.chain.name, cra.residue.seqid.num, cra.residue.seqid.icode)
                j = next((t for t, r in enumerate(res) if cra.chain.name == ch.name
                          and (ch.name, r.seqid.num, r.seqid.icode) == kk), None)
                if j is not None and abs(j - k) <= 1:
                    continue
                bentrok += 1
    c.bentrok = bentrok // 2 if bentrok else 0


# ------------------------------------------------------------------ alur utama
def lengkapi(st, celah, metode="otomatis", uniprot=None, lapor=None, model_af=None):
    """Isi celah internal pada salinan st. -> (st baru, daftar Celah dengan hasil terisi).

    metode: otomatis | alphafold | pdbfixer. uniprot: {rantai: aksesi}. model_af: {aksesi: (teks, label)}
    (untuk uji tanpa internet). Celah yang tidak dapat diisi dibiarkan dan diberi catatan."""
    log = lapor or (lambda s: None)
    st = st.clone()
    internal = [c for c in celah if c.jenis == "internal"]
    for c in celah:
        if c.jenis != "internal":
            c.metode, c.catatan = "dibiarkan", "ujung rantai tidak dimodelkan"
    bebas, pakai_pdbfixer = set(), []
    model_af = dict(model_af or {})
    # AlphaFold per rantai; urutan dari belakang supaya indeks celah sebelumnya tidak bergeser
    for c in sorted(internal, key=lambda x: (x.rantai, -x.i_sebelum)):
        if not c.mungkin:
            c.metode, c.catatan = "dibiarkan", (f"jarak sayap {c.bentang} Å terlalu jauh untuk {c.n} residu; "
                                                "sekuens kristal dan struktur tidak cocok")
            continue
        aks = (uniprot or {}).get(c.rantai)
        if metode in ("otomatis", "alphafold") and aks:
            try:
                if aks not in model_af:
                    log(f"Mengambil model AlphaFold {aks}…")
                    model_af[aks] = model_alphafold(aks)
                teks_af, label_af = model_af[aks]
                af = gemmi.read_pdb_string(teks_af)
                af_res = list(af[0][0])
                ch = st[0][c.rantai]
                peta = _peta_ke_af(ch.get_polymer(), af_res)
                j, k = peta.get(c.i_sebelum), peta.get(c.i_sebelum + 1)
                if j is not None and k is not None:
                    pl = float(np.mean([r[0].b_iso for r in af_res[j + 1:k]])) if k - j > 1 else 0.0
                    if metode == "otomatis" and pl < PLDDT_MIN:
                        raise GalatLoop(f"pLDDT segmen AlphaFold {pl:.0f} < {PLDDT_MIN:.0f} (tidak terstruktur)")
                kunci, plddt, rms, mutasi = _cangkok(ch, c, af_res, peta)
                bebas |= set(kunci)
                c.metode, c.plddt = f"AlphaFold {label_af}", round(plddt, 1)
                c.dimodelkan = [f"{r.name} {r.seqid.num}{r.seqid.icode.strip()}" for r in st[0][c.rantai]
                                if (c.rantai, r.seqid.num, r.seqid.icode) in set(kunci)]
                c.catatan = f"RMSD sayap {rms:.2f} Å" + ("; rantai samping mutan dibangun ulang" if mutasi else "")
                log(f"Loop {c.label()}: dicangkok dari {label_af}, pLDDT rerata {plddt:.0f}")
                continue
            except GalatLoop as e:
                c.catatan = str(e)
            except Exception as e:
                c.catatan = f"cangkok AlphaFold gagal ({str(e).splitlines()[0][:120] if str(e) else type(e).__name__})"
        elif metode in ("otomatis", "alphafold") and not aks:
            c.catatan = "aksesi UniProt rantai ini tidak diketahui"
        if metode == "alphafold":
            c.metode = "dibiarkan"
            continue
        batas = 10 ** 6 if metode == "pdbfixer" else MAKS_PDBFIXER
        if c.nama and c.n <= batas:
            pakai_pdbfixer.append(c)
        else:
            c.metode = "dibiarkan"
            c.catatan = (c.catatan + "; " if c.catatan else "") + (
                "nama residu tidak diketahui (berkas tanpa SEQRES)" if not c.nama
                else f"lebih dari {MAKS_PDBFIXER} residu; PDBFixer tidak dipakai untuk loop panjang")
    if pakai_pdbfixer:
        kunci = _isi_pdbfixer(st, pakai_pdbfixer)
        bebas |= set(kunci)
        for c in pakai_pdbfixer:
            c.metode = "PDBFixer"
            c.catatan = (c.catatan + "; " if c.catatan else "") + "bentuk loop tidak dioptimasi, perlakukan sebagai perkiraan kasar"
            log(f"Loop {c.label()}: diisi PDBFixer")
    if bebas:
        # sayap dua residu di tiap sisi ikut bebas supaya sambungan bisa menyesuaikan
        tambah = set()
        for ch in st[0]:
            res = list(ch)
            for k, r in enumerate(res):
                if (ch.name, r.seqid.num, r.seqid.icode) in bebas:
                    for d in (-2, -1, 1, 2):
                        if 0 <= k + d < len(res) and res[k + d].het_flag != "H":
                            tambah.add((ch.name, res[k + d].seqid.num, res[k + d].seqid.icode))
        log("Minimisasi sambungan loop (OpenMM, atom lain dikekang)…")
        _minimisasi(st, bebas | tambah)
        for c in internal:
            if c.dimodelkan:
                kunci_c = {(c.rantai, r.seqid.num, r.seqid.icode) for r in st[0][c.rantai]
                           if f"{r.name} {r.seqid.num}{r.seqid.icode.strip()}" in c.dimodelkan}
                _ukur(st, c, kunci_c)
    return st, celah
