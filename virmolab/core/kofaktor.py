"""Preparasi kofaktor (HEM, FAD, NAD(P), FMN, SAM, …) terpisah dari polimer protein.

Meeko tidak punya templat residu untuk kebanyakan kofaktor, dan Open Babel pada koordinat PDB (tanpa orde
ikatan) salah mengenali aromatisitas dan gugus asam: fosfat FAD tidak terdeprotonasi, heme gagal dikekulisasi
bila atom Fe ikut sehingga seluruh preparasi reseptor gagal. Di sini tiap residu kofaktor:

  1. logam di dalamnya (Fe heme, Mg klorofil, Co B12) dipisah dan ditulis sebagai ion, sama seperti ion lain;
  2. orde ikatan diambil dari SMILES Chemical Component Dictionary (dibundel, cadangan daring); N yang tadinya
     terikat logam diberi muatan formal secukupnya agar valensinya sah;
  3. protonasi pada pH lewat Open Babel dari blok MOL (orde ikatan sudah benar);
  4. tipe atom AD4 dan muatan Gasteiger lewat Meeko, koordinat atom berat tidak berubah;
  5. H pada N yang mengoordinasi logam dibuang (di kristal N itu mengikat logam, bukan donor).

Bila templat tidak ada atau tidak cocok dengan atom yang terlihat di kristal, kofaktor disiapkan dengan Open
Babel langsung dan diberi peringatan; bila itu pun gagal, kofaktor dibuang dan dilaporkan, preparasi tetap jalan.
"""
import itertools
import json
from dataclasses import dataclass, field
from functools import lru_cache

LOGAM_EL = {"Fe": 2.0, "Mg": 2.0, "Co": 3.0, "Ni": 2.0, "Cu": 2.0, "Zn": 2.0, "Mn": 2.0, "Mo": 4.0, "W": 4.0,
            "Ca": 2.0, "V": 3.0}
JARAK_KOORDINASI = 2.7       # Å, N/O dianggap mengikat logam
TIPE_LOGAM_AD = {"Fe": "Fe", "Mg": "Mg", "Zn": "Zn", "Mn": "Mn", "Ca": "Ca", "Cu": "Cu", "Co": "Zn", "Ni": "Zn",
                 "Mo": "Zn", "W": "Zn", "V": "Zn"}


@dataclass
class HasilKofaktor:
    baris: list = field(default_factory=list)          # baris HETATM PDBQT (tanpa nomor urut final)
    logam: list = field(default_factory=list)          # (resn, elemen, muatan, (x, y, z), rantai, resi)
    ringkas: list = field(default_factory=list)        # "HEM A143: templat CCD, Fe sebagai ion"
    peringatan: list = field(default_factory=list)


@lru_cache(maxsize=1)
def _bundel():
    from . import paths
    for p in (paths.PAKET / "data" / "kofaktor_ccd.json",):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def smiles_ccd(resn):
    """SMILES CCD untuk satu kode residu: bundel lalu RCSB (cache sumber_data). None bila tidak diketahui."""
    d = _bundel().get(resn.upper())
    if d and d.get("smiles"):
        return d["smiles"]
    try:
        from . import sumber_data
        js, _ = sumber_data.ambil_json(f"https://data.rcsb.org/rest/v1/core/chemcomp/{resn.upper()}",
                                       batas=30, coba=1, cache_jam=24 * 365, lisensi="CC0 1.0",
                                       sumber="wwPDB CCD")
        desk = js.get("rcsb_chem_comp_descriptor") or {}
        return desk.get("SMILES_stereo") or desk.get("SMILES")
    except Exception:
        return None


def _templat_tanpa_logam(smiles):
    """Mol templat tanpa atom logam, tersanitasi. N yang kehilangan logam diberi muatan -1 seperlunya."""
    from rdkit import Chem
    m = Chem.MolFromSmiles(smiles, sanitize=False)
    if m is None:
        return None
    rw = Chem.RWMol(m)
    yatim = set()
    for a in sorted((a for a in m.GetAtoms() if a.GetSymbol() in LOGAM_EL), key=lambda a: -a.GetIdx()):
        for n in a.GetNeighbors():
            yatim.add(n.GetIdx())
        rw.RemoveAtom(a.GetIdx())
    # indeks bergeser setelah penghapusan: petakan ulang lewat jumlah logam berindeks lebih kecil
    logam_idx = sorted(a.GetIdx() for a in m.GetAtoms() if a.GetSymbol() in LOGAM_EL)
    geser = lambda i: i - sum(1 for j in logam_idx if j < i)     # noqa: E731
    yatim = sorted(geser(i) for i in yatim if i not in logam_idx)
    dasar = rw.GetMol()
    for a in dasar.GetAtoms():
        a.SetNoImplicit(False)
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")          # percobaan muatan yang gagal kekulisasi memang diharapkan
    try:
        for k in range(len(yatim) + 1):
            for pilih in itertools.combinations(yatim, k):
                uji = Chem.RWMol(dasar)
                for i in yatim:
                    at = uji.GetAtomWithIdx(i)
                    at.SetFormalCharge(-1 if i in pilih else 0)
                    at.SetNumExplicitHs(0)
                try:
                    Chem.SanitizeMol(uji)
                    return uji.GetMol()
                except Exception:
                    continue
    finally:
        RDLogger.EnableLog("rdApp.*")
    return None


def _blok_residu(res, rantai):
    """gemmi.Residue -> blok PDB HETATM (atom berat) dan daftar logam [(elemen, (x, y, z))]."""
    baris, logam = [], []
    for i, a in enumerate(res, 1):
        el = a.element.name
        if el in ("H", "D"):
            continue
        p = a.pos
        if el.capitalize() in LOGAM_EL:
            logam.append((el.capitalize(), (p.x, p.y, p.z)))
            continue
        nama = a.name if len(a.name) == 4 else f" {a.name:<3}"
        baris.append(f"HETATM{i:5d} {nama} {res.name:>3} {rantai[:1]}{res.seqid.num % 10000:4d}    "
                     f"{p.x:8.3f}{p.y:8.3f}{p.z:8.3f}  1.00  0.00          {el:>2}")
    return "\n".join(baris) + "\nEND\n", logam


def _meeko_baris(molh):
    """RDKit Mol ber-H -> baris ATOM/HETATM PDBQT (tipe AD4, muatan Gasteiger) dari Meeko."""
    import io
    from contextlib import redirect_stderr, redirect_stdout
    from meeko import MoleculePreparation, PDBQTWriterLegacy
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        setups = MoleculePreparation().prepare(molh)
        pdbqt, ok, pesan = PDBQTWriterLegacy.write_string(setups[0], bad_charge_ok=True)
    if not ok:
        raise ValueError(pesan or "Meeko gagal menulis PDBQT kofaktor")
    return [b for b in pdbqt.splitlines() if b.startswith(("ATOM", "HETATM"))]


def _obabel_baris(blok, ph):
    from . import obabel
    teks = obabel.konversi(blok, "pdb", "pdbqt", ["-xr", "-p", f"{ph:g}", "--partialcharge", "gasteiger"])
    return [b for b in teks.splitlines() if b.startswith(("ATOM", "HETATM"))]


def _lepas_h_pengikat(molh, koord_logam):
    """Lepas H pada N/O yang mengoordinasi logam sebelum muatan dihitung, sehingga muatan Gasteiger
    mencerminkan keadaan terikat logam (porfirin heme = dianion), bukan basa bebas hasil protonasi pH."""
    from rdkit import Chem
    conf = molh.GetConformer()
    rw = Chem.RWMol(molh)
    hapus = []
    for a in molh.GetAtoms():
        if a.GetSymbol() not in ("N", "O"):
            continue
        p = conf.GetAtomPosition(a.GetIdx())
        if not any(_jarak((p.x, p.y, p.z), q) <= JARAK_KOORDINASI for q in koord_logam):
            continue
        h = [n.GetIdx() for n in a.GetNeighbors() if n.GetAtomicNum() == 1]
        if h:
            rw.GetAtomWithIdx(a.GetIdx()).SetFormalCharge(a.GetFormalCharge() - len(h))
            hapus += h
    for i in sorted(hapus, reverse=True):
        rw.RemoveAtom(i)
    m = rw.GetMol()
    Chem.SanitizeMol(m)
    return m


def _pos(b):
    return float(b[30:38]), float(b[38:46]), float(b[46:54])


def _jarak(p, q):
    return sum((a - c) ** 2 for a, c in zip(p, q)) ** 0.5


def _rapikan(baris, resn, rantai, resi, logam):
    """Seragamkan kolom residu/rantai, ubah ke HETATM, buang H pada N pengikat logam."""
    koord = [p for _, p in logam]
    n_pengikat = [_pos(b) for b in baris if b[77:79].strip() in ("N", "NA")
                  and any(_jarak(_pos(b), p) <= JARAK_KOORDINASI for p in koord)]
    hasil = []
    for b in baris:
        b = b.ljust(79)
        if b[77:79].strip() == "HD" and any(_jarak(_pos(b), n) <= 1.15 for n in n_pengikat):
            continue
        hasil.append("HETATM" + b[6:17] + f"{resn:>3} {rantai[:1]}{int(resi) % 10000:4d}" + b[26:])
    return hasil


def siapkan_residu(res, rantai, ph=7.4):
    """Satu residu gemmi -> (baris PDBQT, logam, metode, peringatan)."""
    from rdkit import Chem
    from rdkit.Chem import AllChem
    resn, resi = res.name.upper(), res.seqid.num
    blok, logam = _blok_residu(res, rantai)
    ion = [(el.upper(), el, LOGAM_EL[el], p, rantai, resi) for el, p in logam]
    smi = smiles_ccd(resn)
    alasan = ""
    if smi:
        try:
            kristal = Chem.MolFromPDBBlock(blok, removeHs=True, sanitize=False, proximityBonding=True)
            templat = _templat_tanpa_logam(smi)
            if kristal is None or templat is None:
                raise ValueError("templat CCD tidak dapat dibaca")
            templat = Chem.RemoveHs(templat)
            if templat.GetNumAtoms() != kristal.GetNumAtoms():
                raise ValueError(f"atom kristal {kristal.GetNumAtoms()} ≠ templat {templat.GetNumAtoms()} "
                                 "(kofaktor tidak lengkap di kristal)")
            mol = AllChem.AssignBondOrdersFromTemplate(templat, kristal)
            from .prep_ligan import _protonasi
            molh, catatan = _protonasi(mol, ph)
            if catatan:
                raise ValueError(catatan)
            if molh.GetNumHeavyAtoms() != mol.GetNumAtoms():
                raise ValueError("protonasi mengubah jumlah atom berat")
            if logam:
                molh = _lepas_h_pengikat(molh, [p for _, p in logam])
            baris = _rapikan(_meeko_baris(molh), resn, rantai, resi, logam)
            return baris, ion, "templat CCD", ""
        except Exception as e:
            alasan = str(e).splitlines()[0][:160] if str(e) else type(e).__name__
    else:
        alasan = "SMILES CCD tidak tersedia"
    baris = _rapikan(_obabel_baris(blok, ph), resn, rantai, resi, logam)
    return baris, ion, "Open Babel", (f"{resn} {rantai}{resi}: orde ikatan ditebak Open Babel ({alasan}); "
                                      "tipe atom aromatik dan keadaan protonasi bisa keliru.")


def siapkan(residu, ph=7.4, lapor=None):
    """residu: [(gemmi.Residue, rantai)] -> HasilKofaktor. Kofaktor yang gagal dibuang dan dilaporkan."""
    h = HasilKofaktor()
    for res, rantai in residu:
        label = f"{res.name} {rantai}{res.seqid.num}"
        try:
            baris, ion, metode, peringatan = siapkan_residu(res, rantai, ph)
        except Exception as e:
            h.peringatan.append(f"{label}: kofaktor tidak dapat disiapkan dan dibuang "
                                f"({str(e).splitlines()[0][:160] if str(e) else type(e).__name__}).")
            continue
        h.baris += baris
        h.logam += ion
        teks = f"{label}: {metode}"
        if ion:
            teks += ", " + ", ".join(f"{e} sebagai ion {q:+.0f}" for _, e, q, _, _, _ in ion)
        h.ringkas.append(teks)
        if peringatan:
            h.peringatan.append(peringatan)
        if lapor:
            lapor(f"Kofaktor {teks}")
    return h
