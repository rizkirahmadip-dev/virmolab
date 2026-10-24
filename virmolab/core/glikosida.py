"""Glikosida lawan aglikon: potong gula secara kimiawi, lalu bandingkan efisiensi ikatan keduanya.

Banyak senyawa bahan alam berupa glikosida. Skor docking glikosida hampir selalu lebih negatif daripada aglikonnya
karena molekulnya lebih besar, bukan karena gulanya berikatan lebih baik, sehingga membandingkan ΔG mentah mudah
menyesatkan. Modul ini:

1. Mengenali unit gula siklik (furanosa/piranosa): cincin 5 atau 6 anggota yang terisolasi (tidak berfusi), memuat
   tepat satu O cincin, atom karbonnya sp3, dan sedikitnya separuh karbon cincin membawa O/N eksosiklik. Kriteria ini
   mengikuti utilitas penghapus gula Schaub dkk. (2020) dalam bentuk yang lebih ringkas.
2. Memutus ikatan glikosidik pada karbon anomerik (karbon cincin yang bertetangga dengan O cincin). Heteroatom
   penghubung tetap pada aglikon dan diberi hidrogen, seperti hasil hidrolisis enzimatik (aglikon-O-gula + H2O ->
   aglikon-OH + gula). C-glikosida (karbon anomerik terikat langsung pada cincin aglikon) tidak dipotong karena tidak
   dihidrolisis beta-glukosidase; jumlahnya dilaporkan.
3. Memasangkan tiap glikosida proyek dengan aglikonnya bila aglikon itu juga ligan proyek, dan membandingkan hanya
   hasil docking dengan reseptor, kotak, dan mesin yang sama.

Ukuran yang dilaporkan: ΔΔG = ΔG glikosida - ΔG aglikon, efisiensi ligan LE = -ΔG / atom berat (Hopkins dkk., 2004),
Fit Quality FQ = LE / LE_scale(atom berat) yang menghapus ketergantungan LE pada ukuran (Reynolds dkk., 2007), dan
sumbangan per atom gula = -ΔΔG / (atom berat glikosida - atom berat aglikon). Bila sumbangan per atom gula lebih kecil
daripada LE aglikon, keunggulan skor glikosida terutama berasal dari ukurannya.
"""
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

UKURAN_CINCIN = (5, 6)
AGLIKON_MIN_ATOM = 6            # sama dengan ambang serpihan di kit.ligan_proyek

PUSTAKA = [
    "Hopkins AL, Groom CR, Alex A. Ligand efficiency: a useful metric for lead selection. Drug Discov Today. "
    "2004;9:430-431. doi:10.1016/S1359-6446(04)03069-7",
    "Reynolds CH, Bembenek SD, Tounge BA. The role of molecular size in ligand efficiency. Bioorg Med Chem Lett. "
    "2007;17:4258-4261. doi:10.1016/j.bmcl.2007.05.038",
    "Schaub J, Zielesny A, Steinbeck C, Sorokina M. Too sweet: cheminformatics for deglycosylation in natural "
    "products. J Cheminform. 2020;12:67. doi:10.1186/s13321-020-00467-y",
    "Németh K, Plumb GW, Berrin JG, dkk. Deglycosylation by small intestinal epithelial cell beta-glucosidases is a "
    "critical step in the absorption and metabolism of dietary flavonoid glycosides in humans. Eur J Nutr. "
    "2003;42:29-42. doi:10.1007/s00394-003-0397-3",
]


@dataclass
class Gula:
    jenis: str          # heksosa, deoksiheksosa, pentosa, asam uronat, gula amino, atau "gula"
    cincin: str         # piranosa / furanosa
    ikatan: str         # O-, N-, S-glikosida, atau ester glikosil


@dataclass
class Deglikosilasi:
    smiles: str
    status: str                       # ok, bukan, hanya_c, gula_saja, aglikon_kecil, ambigu, gagal
    pesan: str = ""
    smiles_aglikon: Optional[str] = None
    gula: List[Gula] = field(default_factory=list)
    n_c_glikosida: int = 0
    atom_gula: List[int] = field(default_factory=list)      # indeks atom berat pada mol(smiles) tanpa H
    atom_berat: int = 0
    atom_berat_aglikon: int = 0

    @property
    def glikosida(self):
        return self.status in ("ok", "ambigu", "aglikon_kecil")


def _cincin_gula(mol):
    """Tupel atom tiap cincin gula siklik pada mol (tanpa H eksplisit)."""
    from rdkit import Chem
    ri = mol.GetRingInfo()
    hasil = []
    for cincin in ri.AtomRings():
        if len(cincin) not in UKURAN_CINCIN:
            continue
        atom = [mol.GetAtomWithIdx(i) for i in cincin]
        if any(a.GetIsAromatic() or ri.NumAtomRings(a.GetIdx()) != 1 for a in atom):
            continue
        o_cincin = [a for a in atom if a.GetSymbol() == "O"]
        karbon = [a for a in atom if a.GetSymbol() == "C"]
        if len(o_cincin) != 1 or len(karbon) != len(cincin) - 1:
            continue
        if any(a.GetHybridization() != Chem.HybridizationType.SP3 for a in karbon):
            continue
        himpunan = set(cincin)
        berhetero = 0
        for c in karbon:
            for b in c.GetBonds():
                x = b.GetOtherAtom(c)
                if x.GetIdx() not in himpunan and x.GetSymbol() in ("O", "N") and \
                        b.GetBondType() == Chem.BondType.SINGLE:
                    berhetero += 1
                    break
        if berhetero * 2 >= len(karbon):
            hasil.append(tuple(cincin))
    return hasil


def _jenis_gula(frag_atom, mol, n_cincin, dipotong=True):
    """Kelas gula dari komposisinya setelah hidrolisis. Gula yang ikatan anomeriknya diputus kehilangan O
    penghubung ke aglikon dan mendapat OH kembali; gula yang tidak diputus (fruktosa pada sukrosa) sudah utuh."""
    n_c = sum(1 for i in frag_atom if mol.GetAtomWithIdx(i).GetSymbol() == "C")
    n_o = sum(1 for i in frag_atom if mol.GetAtomWithIdx(i).GetSymbol() == "O") + (1 if dipotong else 0)
    n_n = sum(1 for i in frag_atom if mol.GetAtomWithIdx(i).GetSymbol() == "N")
    cincin = "piranosa" if n_cincin == 6 else "furanosa"
    if n_n:
        return "gula amino", cincin
    if n_c == 6 and n_o == 7:
        return "asam uronat", cincin
    if n_c == 6 and n_o == 6:
        return "heksosa", cincin
    if n_c == 6 and n_o == 5:
        return "deoksiheksosa", cincin
    if n_c == 6 and n_o == 4:
        return "dideoksiheksosa", cincin
    if n_c == 5 and n_o == 5:
        return "pentosa", cincin
    return "gula", cincin


def deglikosilasi(smiles):
    """Potong semua ikatan O-, N-, S-glikosidik dan ester glikosil; kembalikan Deglikosilasi."""
    from rdkit import Chem
    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None:
        return Deglikosilasi(smiles, "gagal", "SMILES tidak dapat dibaca.")
    mol = Chem.RemoveHs(mol)
    n_berat = mol.GetNumHeavyAtoms()
    cincin = _cincin_gula(mol)
    if not cincin:
        return Deglikosilasi(smiles, "bukan", "Tidak ada unit gula siklik.", atom_berat=n_berat)
    atom_cincin_gula = {i: c for c in cincin for i in c}

    potong, jenis_ikatan, n_c, dipakai = [], {}, 0, set()
    for c in cincin:
        himpunan = set(c)
        o_cincin = next(i for i in c if mol.GetAtomWithIdx(i).GetSymbol() == "O")
        for nb in mol.GetAtomWithIdx(o_cincin).GetNeighbors():          # karbon anomerik
            for b in nb.GetBonds():
                x = b.GetOtherAtom(nb)
                if x.GetIdx() in himpunan or b.GetBondType() != Chem.BondType.SINGLE:
                    continue
                if x.GetSymbol() == "C":
                    if x.GetIsAromatic() or x.IsInRing():
                        n_c += 1
                    continue
                if x.GetSymbol() not in ("O", "N", "S") or x.GetDegree() < 2:
                    continue                     # OH anomerik bebas (gula pereduksi), bukan ikatan glikosidik
                if x.GetIdx() in dipakai:
                    continue                     # O jembatan dua karbon anomerik (sukrosa): cukup diputus sekali
                dipakai.add(x.GetIdx())
                ester = x.GetSymbol() == "O" and any(
                    y.GetIdx() != nb.GetIdx() and y.GetSymbol() == "C" and any(
                        bb.GetBondType() == Chem.BondType.DOUBLE and bb.GetOtherAtom(y).GetSymbol() == "O"
                        for bb in y.GetBonds())
                    for y in x.GetNeighbors())
                potong.append((nb.GetIdx(), x.GetIdx()))
                jenis_ikatan[c] = "ester glikosil" if ester else f"{x.GetSymbol()}-glikosida"

    if not potong:
        if n_c:
            return Deglikosilasi(smiles, "hanya_c", f"{n_c} C-glikosida; ikatan C-C anomerik tidak dihidrolisis "
                                 "beta-glukosidase sehingga tidak dipotong.", n_c_glikosida=n_c, atom_berat=n_berat)
        return Deglikosilasi(smiles, "bukan", "Cincin gula tidak terikat lewat ikatan glikosidik.", atom_berat=n_berat)

    rw = Chem.RWMol(mol)
    for a, x in potong:
        rw.RemoveBond(a, x)
        for i in (a, x):                        # kedua sisi mendapat H kembali (gula-OH dan aglikon-XH)
            at = rw.GetAtomWithIdx(i)
            at.SetNumExplicitHs(at.GetNumExplicitHs() + 1)
            at.SetNoImplicit(False)
    try:
        Chem.SanitizeMol(rw)
    except Exception as e:                      # noqa: BLE001
        return Deglikosilasi(smiles, "gagal", f"Hasil pemotongan tidak valid: {e}", atom_berat=n_berat)

    gula, atom_gula, bukan_gula = [], [], []
    for frag in Chem.GetMolFrags(rw, asMols=False, sanitizeFrags=False):
        cincin_frag = sorted({atom_cincin_gula[i] for i in frag if i in atom_cincin_gula}, key=min)
        aromatik = any(rw.GetAtomWithIdx(i).GetIsAromatic() for i in frag)
        batas = sum(2 * len(c) + 3 for c in cincin_frag)
        if cincin_frag and not aromatik and len(frag) <= batas:
            for c in cincin_frag:
                # Tiap ikatan glikosidik diputus, jadi satu fragmen biasanya satu gula; bila dua cincin gula
                # tersambung tanpa ikatan glikosidik, komposisinya tidak bisa dibagi dan dinamai "gula".
                j, r = _jenis_gula(frag, mol, len(c), c in jenis_ikatan) if len(cincin_frag) == 1 else ("gula", (
                    "piranosa" if len(c) == 6 else "furanosa"))
                gula.append(Gula(j, r, jenis_ikatan.get(c, "O-glikosida")))
            atom_gula.extend(frag)
        else:
            bukan_gula.append(frag)

    if not gula:
        return Deglikosilasi(smiles, "bukan", "Bagian bercincin gula terlalu besar atau aromatik untuk dianggap gula "
                             "(misalnya inti glukosa tanin terhidrolisis).", atom_berat=n_berat)
    if not bukan_gula:
        return Deglikosilasi(smiles, "gula_saja", "Seluruh molekul tersusun dari gula (oligosakarida).",
                             gula=gula, atom_gula=sorted(atom_gula), atom_berat=n_berat)

    bukan_gula.sort(key=len, reverse=True)
    terpilih = bukan_gula[0]
    sub = Chem.RWMol(rw)
    for i in sorted(set(range(rw.GetNumAtoms())) - set(terpilih), reverse=True):
        sub.RemoveAtom(i)
    agl = sub.GetMol()
    try:
        Chem.SanitizeMol(agl)
        smi_agl = Chem.MolToSmiles(agl)
        agl = Chem.MolFromSmiles(smi_agl)
        smi_agl = Chem.MolToSmiles(agl)
    except Exception as e:                      # noqa: BLE001
        return Deglikosilasi(smiles, "gagal", f"Aglikon tidak valid: {e}", atom_berat=n_berat)

    status, pesan = "ok", ""
    if len(bukan_gula) > 1:
        status = "ambigu"
        pesan = (f"Gula menghubungkan {len(bukan_gula)} bagian bukan-gula; yang diambil sebagai aglikon adalah bagian "
                 f"terbesar ({len(terpilih)} atom berat).")
    elif agl.GetNumHeavyAtoms() < AGLIKON_MIN_ATOM:
        status = "aglikon_kecil"
        pesan = (f"Aglikon hanya {agl.GetNumHeavyAtoms()} atom berat (misalnya metil glikosida); perbandingan "
                 "efisiensinya tidak bermakna.")
    if n_c:
        pesan = (pesan + " " if pesan else "") + f"{n_c} C-glikosida tetap menempel pada aglikon."
    return Deglikosilasi(smiles, status, pesan, smi_agl, gula, n_c, sorted(atom_gula), n_berat,
                         agl.GetNumHeavyAtoms())


def ringkas_gula(gula: List[Gula], t=lambda s: s):
    """'2: heksosa (O-glikosida), deoksiheksosa (O-glikosida)'. t: penerjemah per potongan (i18n.t di UI), karena
    lapisan terjemahan hanya mencocokkan string utuh."""
    if not gula:
        return "–"
    return f"{len(gula)}: " + ", ".join(f"{t(g.jenis)} ({t(g.ikatan)})" for g in gula)


# --------------------------------------------------------------------- efisiensi
def le_scale(ha):
    """LE yang lazim untuk ukuran ini (Reynolds dkk., 2007), kkal/mol per atom berat."""
    return 0.0715 + 7.5328 / ha + 25.7079 / ha ** 2 - 361.4722 / ha ** 3


def efisiensi(dg, ha):
    """(LE, FQ); None bila skor tidak negatif atau atom berat tidak sah."""
    if dg is None or not ha or dg >= 0:
        return None, None
    le = -dg / ha
    skala = le_scale(ha)
    return le, (le / skala if skala > 0 else None)


KESIMPULAN_SINGKAT = {"ukuran": "Unggul karena ukuran", "aglikon": "Aglikon lebih kuat",
                      "gula": "Gula ikut berikatan", "kurang": "Data kurang"}


def bandingkan(dg_g, ha_g, dg_a, ha_a):
    """Ukuran satu pasangan pada satu kondisi docking."""
    le_g, fq_g = efisiensi(dg_g, ha_g)
    le_a, fq_a = efisiensi(dg_a, ha_a)
    ddg = dg_g - dg_a if dg_g is not None and dg_a is not None else None
    tambah = ha_g - ha_a
    per_atom = (-ddg / tambah) if ddg is not None and tambah > 0 else None
    if ddg is None:
        kesimpulan, kode = "Salah satu belum didocking pada kondisi ini.", "kurang"
    elif ddg >= 0:
        kesimpulan, kode = "Aglikon setara atau lebih kuat; gula tidak menambah skor.", "aglikon"
    elif le_a is not None and per_atom is not None and per_atom < le_a:
        kesimpulan, kode = ("Glikosida lebih kuat, tetapi tiap atom gula menyumbang lebih sedikit daripada LE aglikon: "
                            "keunggulan skornya terutama karena ukuran."), "ukuran"
    else:
        kesimpulan, kode = ("Atom gula menyumbang sepadan atau melebihi LE aglikon: gula kemungkinan berinteraksi "
                            "spesifik."), "gula"
    return {"dg_g": dg_g, "dg_a": dg_a, "ddg": ddg, "le_g": le_g, "le_a": le_a, "fq_g": fq_g, "fq_a": fq_a,
            "per_atom_gula": per_atom, "kesimpulan": kesimpulan, "kode": kode,
            "aglikon_lebih_efisien": (le_a is not None and le_g is not None and le_a > le_g)}


# --------------------------------------------------------------------- proyek
def kondisi_job(job):
    """Kunci kondisi docking: reseptor, pusat dan ukuran kotak (0,1 Å), mesin."""
    rec = job.get("reseptor_pdb") or job.get("reseptor") or ""
    k = job.get("kotak") or {}
    bulat = lambda v: tuple(round(float(x), 1) for x in (v or ()))      # noqa: E731
    return (Path(str(rec)).name, bulat(k.get("pusat")), bulat(k.get("ukuran")), job.get("mesin", ""))


def label_kondisi(kunci, nama_reseptor=None):
    """'1HSG · AutoDock Vina'. Nama berkas reseptor proyek selalu 'reseptor.pdbqt', jadi nama reseptor proyek
    dipakai bila tersedia."""
    rec, _pusat, _ukuran, mesin = kunci
    from . import mesin as M
    return f"{nama_reseptor or Path(rec).stem or 'reseptor'} · {M.MESIN.get(mesin, mesin)}"


def _kunci_cocok(smiles):
    """(SMILES kanonik isomerik, kunci InChI 14 karakter pertama) untuk mencocokkan aglikon dengan ligan proyek."""
    from rdkit import Chem
    m = Chem.MolFromSmiles(smiles or "")
    if m is None:
        return None, None
    try:
        ik = Chem.MolToInchiKey(m)[:14]
    except Exception:                           # noqa: BLE001
        ik = None
    return Chem.MolToSmiles(m), ik


def analisis_proyek(proyek):
    """{'pasangan': [...], 'glikosida': [...]} dari ligan dan hasil docking proyek.

    glikosida: tiap ligan glikosida {lid, nama, hasil: Deglikosilasi, aglikon: (lid, nama, cocok) | None}.
    pasangan: tiap (glikosida, aglikon proyek, kondisi) yang KEDUANYA didocking pada kondisi itu, dengan ukuran
    dari bandingkan()."""
    from . import ekspor
    ligan = [(l["id"], l["nama"], proyek.smiles_ligan(l)) for l in proyek.ligan]
    kunci = {}
    for lid, nama, smi in ligan:
        k_iso, k_ik = _kunci_cocok(smi)
        if k_iso:
            kunci.setdefault(("iso", k_iso), (lid, nama))
        if k_ik:
            kunci.setdefault(("ik", k_ik), (lid, nama))

    kondisi = {j["id"]: kondisi_job(j) for j in proyek.job}
    terbaik: Dict[tuple, float] = {}
    for b in ekspor.baris_hasil(proyek):
        if b.get("kovalen") or b.get("energi") is None or b.get("job") not in kondisi:
            continue
        k = (b["lid"], kondisi[b["job"]])
        if k not in terbaik or b["energi"] < terbaik[k]:
            terbaik[k] = b["energi"]

    rec_proyek = Path(str((proyek.reseptor or {}).get("pdbqt") or "")).name
    nama_rec = (proyek.reseptor or {}).get("nama") or None
    label = {}
    for kd in sorted(set(kondisi.values()), key=str):
        dasar = label_kondisi(kd, nama_rec if kd[0] == rec_proyek else None)
        n = sum(1 for v in label.values() if v.split(" (kotak")[0] == dasar)
        label[kd] = dasar if n == 0 else f"{dasar} (kotak {n + 1})"     # beda kotak, reseptor dan mesin sama

    glikosida, pasangan = [], []
    for lid, nama, smi in ligan:
        h = deglikosilasi(smi)
        if h.status in ("bukan", "gagal"):
            continue
        agl = None
        if h.smiles_aglikon:
            k_iso, k_ik = _kunci_cocok(h.smiles_aglikon)
            if ("iso", k_iso) in kunci and kunci[("iso", k_iso)][0] != lid:
                agl = (*kunci[("iso", k_iso)], "persis")
            elif k_ik and ("ik", k_ik) in kunci and kunci[("ik", k_ik)][0] != lid:
                agl = (*kunci[("ik", k_ik)], "InChIKey sama")
        glikosida.append({"lid": lid, "nama": nama, "hasil": h, "aglikon": agl})
        if not agl or not h.glikosida:
            continue
        for kd in sorted({k for (l, k) in terbaik if l == lid}, key=str):
            dg_g, dg_a = terbaik.get((lid, kd)), terbaik.get((agl[0], kd))
            if dg_a is None:
                continue
            pasangan.append({"lid_g": lid, "nama_g": nama, "lid_a": agl[0], "nama_a": agl[1], "cocok": agl[2],
                             "kondisi": kd, "label_kondisi": label[kd], "ha_g": h.atom_berat,
                             "ha_a": h.atom_berat_aglikon, "n_gula": len(h.gula),
                             **bandingkan(dg_g, h.atom_berat, dg_a, h.atom_berat_aglikon)})
    return {"glikosida": glikosida, "pasangan": pasangan}


# --------------------------------------------------------------------- naskah
def _f(x, d=2, en=False):
    t = f"{x:.{d}f}"
    return t if en else t.replace(".", ",")


def teks_metode(analisis, en=False):
    """Paragraf metode dari pasangan yang benar-benar dibandingkan; kosong bila belum ada pasangan."""
    p = analisis.get("pasangan") or []
    if not p:
        return ""
    n_g = len({x["lid_g"] for x in p})
    n_lebih = sum(1 for x in p if x["aglikon_lebih_efisien"])
    n_ukuran = sum(1 for x in p if x["kode"] == "ukuran")
    if en:
        return (f"Glycosides were deglycosylated in silico: cyclic sugar units (isolated five- or six-membered rings "
                f"with one ring oxygen, sp3 ring carbons, and at least half of the ring carbons bearing an exocyclic "
                f"oxygen or nitrogen; adapted from Schaub et al., 2020) were removed by cleaving the glycosidic bond "
                f"at the anomeric carbon, leaving the linking heteroatom on the aglycone as in enzymatic hydrolysis; "
                f"C-glycosidic bonds were kept. Aglycones were relevant forms because dietary flavonoid O-glycosides "
                f"are largely deglycosylated before absorption (Németh et al., 2003). Each glycoside and its aglycone "
                f"were docked with the same receptor, search box, and engine. Besides the docking score difference "
                f"(ΔΔG = ΔG glycoside − ΔG aglycone), we report ligand efficiency (LE = −ΔG/heavy atoms; Hopkins et "
                f"al., 2004), the size-independent fit quality (FQ; Reynolds et al., 2007), and the score contributed "
                f"per added sugar heavy atom (−ΔΔG/Δheavy atoms). For {n_g} glycoside(s) in {len(p)} docking "
                f"comparison(s), the aglycone had the higher LE in {n_lebih}, and in {n_ukuran} the glycoside scored "
                f"better only because each sugar atom contributed less than the aglycone's LE. Docking scores are "
                f"not measured affinities.")
    return (f"Glikosida dideglikosilasi secara in silico: unit gula siklik (cincin lima atau enam anggota yang "
            f"terisolasi dengan satu O cincin, karbon cincin sp3, dan sedikitnya separuh karbon cincin membawa O atau "
            f"N eksosiklik; diadaptasi dari Schaub dkk., 2020) dilepas dengan memutus ikatan glikosidik pada karbon "
            f"anomerik, sedangkan heteroatom penghubung tetap pada aglikon seperti hasil hidrolisis enzimatik; ikatan "
            f"C-glikosidik dipertahankan. Aglikon relevan dikaji karena O-glikosida flavonoid dari makanan umumnya "
            f"dideglikosilasi sebelum diserap (Németh dkk., 2003). Tiap glikosida dan aglikonnya didocking dengan "
            f"reseptor, kotak pencarian, dan mesin yang sama. Selain selisih skor docking (ΔΔG = ΔG glikosida − ΔG "
            f"aglikon), dilaporkan efisiensi ligan (LE = −ΔG/atom berat; Hopkins dkk., 2004), fit quality yang bebas "
            f"pengaruh ukuran (FQ; Reynolds dkk., 2007), dan sumbangan skor per atom berat gula (−ΔΔG/Δatom berat). "
            f"Dari {n_g} glikosida dalam {len(p)} perbandingan docking, aglikon memiliki LE lebih tinggi pada "
            f"{n_lebih}, dan pada {n_ukuran} glikosida unggul skor semata karena tiap atom gula menyumbang lebih kecil "
            f"daripada LE aglikonnya. Skor docking bukan afinitas terukur.")


def baris_csv(analisis):
    """Baris ekspor (header + data) untuk tabel perbandingan."""
    kolom = ["glikosida", "aglikon", "kecocokan", "kondisi", "atom_berat_glikosida", "atom_berat_aglikon", "n_gula",
             "dG_glikosida", "dG_aglikon", "ddG", "LE_glikosida", "LE_aglikon", "FQ_glikosida", "FQ_aglikon",
             "sumbangan_per_atom_gula", "kesimpulan"]
    baris = [kolom]
    for x in analisis.get("pasangan") or []:
        bul = lambda v, d=3: "" if v is None or (isinstance(v, float) and math.isnan(v)) else round(v, d)  # noqa: E731
        baris.append([x["nama_g"], x["nama_a"], x["cocok"], x["label_kondisi"], x["ha_g"], x["ha_a"], x["n_gula"],
                      bul(x["dg_g"], 2), bul(x["dg_a"], 2), bul(x["ddg"], 2), bul(x["le_g"]), bul(x["le_a"]),
                      bul(x["fq_g"]), bul(x["fq_a"]), bul(x["per_atom_gula"]), x["kesimpulan"]])
    return baris
