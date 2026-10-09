"""Sifat ligan: deskriptor fisikokimia, aturan drug-likeness, peringatan struktur, BOILED-Egg.

Semua dihitung dengan RDKit (tanpa paket tambahan). Struktur dinetralkan dulu
(fragmen terbesar + Uncharger) agar hasil tidak bergantung protonasi pH saat
preparasi docking — mendekati cara SwissADME membaca SMILES masukan.

Catatan perbedaan dengan SwissADME: lipofilisitas memakai Wildman–Crippen
(= WLOGP, sama metode), tetapi aturan Lipinski & Muegge di SwissADME memakai
MLOGP/XLOGP3; di sini semuanya memakai WLOGP (dicantumkan di KRITERIA).
"""
import math
from xml.sax.saxutils import escape

VERSI = 1      # naikkan bila rumus berubah -> cache di proyek dihitung ulang

# BOILED-Egg (Daina & Zoete 2016): elips di ruang (TPSA, WLOGP), rotasi dalam satuan data.
# (pusat TPSA, pusat WLOGP, sumbu penuh TPSA, sumbu penuh WLOGP, sudut derajat)
ELIPS_HIA = (71.051, 2.292, 142.081, 8.740, -1.031325)     # putih: absorpsi saluran cerna
ELIPS_BBB = (38.117, 3.177, 82.061, 5.557, -0.171887)      # kuning telur: menembus sawar darah otak

KRITERIA = [
    ("Lipinski", "MW ≤ 500; WLOGP ≤ 5; donor H (NH+OH) ≤ 5; akseptor H (N+O) ≤ 10; lolos bila ≤ 1 pelanggaran"),
    ("Ghose", "160 ≤ MW ≤ 480; −0,4 ≤ WLOGP ≤ 5,6; 40 ≤ MR ≤ 130; 20 ≤ jumlah atom (dengan H) ≤ 70"),
    ("Veber", "ikatan rotasi ≤ 10; TPSA ≤ 140 Å²"),
    ("Egan", "WLOGP ≤ 5,88; TPSA ≤ 131,6 Å²"),
    ("Muegge", "200 ≤ MW ≤ 600; −2 ≤ WLOGP ≤ 5; TPSA ≤ 150; cincin ≤ 7; C > 4; heteroatom > 1; "
               "ikatan rotasi ≤ 15; akseptor H ≤ 10; donor H ≤ 5"),
    ("BOILED-Egg", "titik (TPSA, WLOGP) di dalam elips putih = absorpsi saluran cerna tinggi (GI); "
                   "di dalam kuning telur = menembus sawar darah otak (BBB)"),
    ("PAINS / Brenk", "substruktur pengganggu uji (PAINS A–C) dan gugus tak diinginkan (Brenk) — "
                      "peringatan, bukan larangan"),
    ("QED", "indeks kemiripan obat 0–1 (makin tinggi makin mirip obat oral)"),
]

SITASI = [
    "Daina A, Zoete V. A BOILED-Egg to predict gastrointestinal absorption and brain penetration of small "
    "molecules. ChemMedChem 2016;11:1117–21.",
    "Lipinski CA, et al. Adv Drug Deliv Rev 2001;46:3–26.",
    "Ghose AK, et al. J Comb Chem 1999;1:55–68.",
    "Veber DF, et al. J Med Chem 2002;45:2615–23.",
    "Egan WJ, et al. J Med Chem 2000;43:3867–77.",
    "Muegge I, et al. J Med Chem 2001;44:1841–6.",
    "Bickerton GR, et al. Quantifying the chemical beauty of drugs. Nat Chem 2012;4:90–8.",
    "Baell JB, Holloway GA. J Med Chem 2010;53:2719–40 (PAINS).",
    "Brenk R, et al. ChemMedChem 2008;3:435–44.",
    "Wildman SA, Crippen GM. J Chem Inf Comput Sci 1999;39:868–73 (WLOGP).",
]

# kolom tabel/ekspor: (kunci, judul)
KOLOM = [("nama", "Ligan"), ("rumus", "Rumus"), ("mw", "MW (g/mol)"), ("wlogp", "WLOGP"), ("tpsa", "TPSA (Å²)"),
         ("mr", "MR"), ("hbd", "Donor H"), ("hba", "Akseptor H"), ("rotb", "Ikatan rotasi"),
         ("cincin_ar", "Cincin aromatik"), ("atom_berat", "Atom berat"), ("fsp3", "Fsp3"), ("qed", "QED"),
         ("lipinski", "Lipinski (pelanggaran)"), ("ghose", "Ghose"), ("veber", "Veber"), ("egan", "Egan"),
         ("muegge", "Muegge"), ("gi", "Absorpsi GI"), ("bbb", "BBB"), ("pains", "PAINS"), ("brenk", "Brenk"),
         ("smiles", "SMILES")]

_katalog = {}


def _filter(nama):
    if nama not in _katalog:
        from rdkit.Chem import FilterCatalog as F
        p = F.FilterCatalogParams()
        p.AddCatalog(getattr(F.FilterCatalogParams.FilterCatalogs, nama))
        _katalog[nama] = F.FilterCatalog(p)
    return _katalog[nama]


def di_elips(tpsa, wlogp, elips):
    """True bila titik di dalam elips (rotasi di ruang data, seperti model asli)."""
    cx, cy, lebar, tinggi, sudut = elips
    t = math.radians(-sudut)
    dx, dy = tpsa - cx, wlogp - cy
    x = dx * math.cos(t) - dy * math.sin(t)
    y = dx * math.sin(t) + dy * math.cos(t)
    return (x / (lebar / 2)) ** 2 + (y / (tinggi / 2)) ** 2 <= 1.0


def titik_elips(elips, n=180):
    cx, cy, lebar, tinggi, sudut = elips
    t = math.radians(sudut)
    hasil = []
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        x, y = lebar / 2 * math.cos(a), tinggi / 2 * math.sin(a)
        hasil.append((cx + x * math.cos(t) - y * math.sin(t), cy + x * math.sin(t) + y * math.cos(t)))
    return hasil


def netralkan(mol):
    from rdkit import Chem
    from rdkit.Chem.MolStandardize import rdMolStandardize
    mol = Chem.RemoveHs(mol)
    frag = Chem.GetMolFrags(mol, asMols=True)
    if len(frag) > 1:
        mol = max(frag, key=lambda m: m.GetNumHeavyAtoms())
    try:
        mol = rdMolStandardize.Uncharger().uncharge(mol)
    except Exception:
        pass
    return mol


def hitung(mol):
    """Kembalikan dict sifat (angka dibulatkan, siap disimpan di proyek.json)."""
    from rdkit import Chem
    from rdkit.Chem import QED, Crippen, Descriptors, Lipinski, rdMolDescriptors as R
    m = netralkan(mol)
    mh = Chem.AddHs(m)
    mw = Descriptors.MolWt(m)
    wlogp = Crippen.MolLogP(m)
    mr = Crippen.MolMR(m)
    tpsa = R.CalcTPSA(m)                     # hanya N & O, seperti Ertl 2000 / SwissADME
    hbd, hba = R.CalcNumHBD(m), R.CalcNumHBA(m)
    l_hbd, l_hba = Lipinski.NHOHCount(m), Lipinski.NOCount(m)    # definisi asli Lipinski
    rotb = R.CalcNumRotatableBonds(m)
    cincin = R.CalcNumRings(m)
    n_c = sum(1 for a in m.GetAtoms() if a.GetAtomicNum() == 6)
    n_hetero = sum(1 for a in m.GetAtoms() if a.GetAtomicNum() not in (1, 6))
    n_atom = mh.GetNumAtoms()

    lip = [p for p, ok in (("MW > 500", mw <= 500), ("WLOGP > 5", wlogp <= 5),
                           ("donor H > 5", l_hbd <= 5), ("akseptor H > 10", l_hba <= 10)) if not ok]
    gho = [p for p, ok in (("MW di luar 160–480", 160 <= mw <= 480), ("WLOGP di luar −0,4–5,6", -0.4 <= wlogp <= 5.6),
                           ("MR di luar 40–130", 40 <= mr <= 130), ("atom di luar 20–70", 20 <= n_atom <= 70)) if not ok]
    veb = [p for p, ok in (("ikatan rotasi > 10", rotb <= 10), ("TPSA > 140", tpsa <= 140)) if not ok]
    ega = [p for p, ok in (("WLOGP > 5,88", wlogp <= 5.88), ("TPSA > 131,6", tpsa <= 131.6)) if not ok]
    mue = [p for p, ok in (("MW di luar 200–600", 200 <= mw <= 600), ("WLOGP di luar −2–5", -2 <= wlogp <= 5),
                           ("TPSA > 150", tpsa <= 150), ("cincin > 7", cincin <= 7), ("C ≤ 4", n_c > 4),
                           ("heteroatom ≤ 1", n_hetero > 1), ("ikatan rotasi > 15", rotb <= 15),
                           ("akseptor H > 10", hba <= 10), ("donor H > 5", hbd <= 5)) if not ok]
    try:
        qed = QED.qed(m)
    except Exception:
        qed = None
    pains = sorted({e.GetDescription() for e in _filter("PAINS").GetMatches(m)})
    brenk = sorted({e.GetDescription() for e in _filter("BRENK").GetMatches(m)})
    return {"v": VERSI, "smiles": Chem.MolToSmiles(m), "rumus": R.CalcMolFormula(m),
            "mw": round(mw, 2), "wlogp": round(wlogp, 2), "mr": round(mr, 2), "tpsa": round(tpsa, 2),
            "hbd": hbd, "hba": hba, "rotb": rotb, "cincin": cincin, "cincin_ar": R.CalcNumAromaticRings(m),
            "atom_berat": m.GetNumHeavyAtoms(), "fsp3": round(R.CalcFractionCSP3(m), 2),
            "qed": round(qed, 3) if qed is not None else None, "muatan_asal": Chem.GetFormalCharge(mol),
            "lipinski": len(lip), "lipinski_ok": len(lip) <= 1, "lipinski_alasan": lip,
            "ghose_ok": not gho, "ghose_alasan": gho, "veber_ok": not veb, "veber_alasan": veb,
            "egan_ok": not ega, "egan_alasan": ega, "muegge_ok": not mue, "muegge_alasan": mue,
            "gi": di_elips(tpsa, wlogp, ELIPS_HIA), "bbb": di_elips(tpsa, wlogp, ELIPS_BBB),
            "pains": pains, "brenk": brenk}


def dari_teks(teks, fmt="sdf"):
    from rdkit import Chem
    if fmt in ("sdf", "mol"):
        mol = Chem.MolFromMolBlock(teks, removeHs=False)
    elif fmt == "smiles":
        mol = Chem.MolFromSmiles(teks)
    else:
        from .prep_ligan import mol_dari
        mol = mol_dari(teks, fmt)
    if mol is None:
        raise ValueError("struktur tidak bisa dibaca RDKit")
    return hitung(mol)


def sel(s, k):
    """Teks sel tabel/ekspor untuk kunci k."""
    if k in ("ghose", "veber", "egan", "muegge"):
        return "Ya" if s[f"{k}_ok"] else f"Tidak ({len(s[f'{k}_alasan'])})"
    if k == "lipinski":
        return f"Ya ({s['lipinski']})" if s["lipinski_ok"] else f"Tidak ({s['lipinski']})"
    if k in ("gi", "bbb"):
        return ("Tinggi" if s["gi"] else "Rendah") if k == "gi" else ("Ya" if s["bbb"] else "Tidak")
    if k in ("pains", "brenk"):
        return "; ".join(s[k]) if s[k] else "–"
    return s.get(k)


def ringkas_alasan(s):
    """Teks tooltip/catatan: semua pelanggaran per aturan."""
    out = []
    for k, t in (("lipinski", "Lipinski"), ("ghose", "Ghose"), ("veber", "Veber"), ("egan", "Egan"),
                 ("muegge", "Muegge")):
        if s[f"{k}_alasan"]:
            out.append(f"{t}: " + ", ".join(s[f"{k}_alasan"]))
    if s["pains"]:
        out.append("PAINS: " + ", ".join(s["pains"]))
    if s["brenk"]:
        out.append("Brenk: " + ", ".join(s["brenk"]))
    return out


# ------------------------------------------------------------------ BOILED-Egg (SVG)
from .grafik import FONT, tik as _tik


def _fmt(v):
    from .grafik import fmt
    return fmt(v)


def boiled_egg_svg(titik, lebar=760, tinggi=600, gelap=False, transparan=False, label=True, pilih=None, judul=""):
    """titik: [(nama, tpsa, wlogp)]. pilih: indeks titik yang disorot. Kembalikan teks SVG."""
    tinta = "#e2e6ed" if gelap else "#1b2430"
    tinta2 = "#aab3c0" if gelap else "#465263"
    latar = "#14171c" if gelap else "#ffffff"
    area = "#3a3f47" if gelap else "#d9dde3"         # luar telur (abu)
    putih = "#f4f5f7"
    kuning = "#f2c94c"
    garis_elips = "#8a93a3"
    titik_warna = "#2b6fd6"
    xs = [t[1] for t in titik] + [0, 160]
    ys = [t[2] for t in titik] + [-4, 8]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    tx, _ = _tik(x0, x1, 8)
    ty, _ = _tik(y0, y1, 7)
    x0, x1, y0, y1 = tx[0], tx[-1], ty[0], ty[-1]
    kiri, kanan, atas, bawah = 64, 20, 40 if judul else 18, 92
    pw, ph = lebar - kiri - kanan, tinggi - atas - bawah

    def X(v):
        return kiri + (v - x0) / (x1 - x0) * pw

    def Y(v):
        return atas + (y1 - v) / (y1 - y0) * ph

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{lebar}" height="{tinggi}" '
           f'viewBox="0 0 {lebar} {tinggi}">']
    if not transparan:
        out.append(f'<rect x="0" y="0" width="{lebar}" height="{tinggi}" fill="{latar}"/>')
    if judul:
        out.append(f'<text x="{kiri}" y="24" font-family="{FONT}" font-size="14" font-weight="600" '
                   f'fill="{tinta}">{escape(judul)}</text>')
    out.append(f'<defs><clipPath id="plot"><rect x="{kiri}" y="{atas}" width="{pw}" height="{ph}"/></clipPath></defs>')
    out.append(f'<rect x="{kiri}" y="{atas}" width="{pw}" height="{ph}" fill="{area}"/>')
    out.append('<g clip-path="url(#plot)">')
    for el, isi in ((ELIPS_HIA, putih), (ELIPS_BBB, kuning)):
        d = "M" + " L".join(f"{X(a):.2f},{Y(b):.2f}" for a, b in titik_elips(el)) + " Z"
        out.append(f'<path d="{d}" fill="{isi}" stroke="{garis_elips}" stroke-width="0.8"/>')
    out.append("</g>")
    # sumbu & tik
    out.append(f'<rect x="{kiri}" y="{atas}" width="{pw}" height="{ph}" fill="none" stroke="{tinta2}" '
               f'stroke-width="1"/>')
    for v in tx:
        if x0 <= v <= x1:
            out.append(f'<line x1="{X(v):.1f}" y1="{atas + ph}" x2="{X(v):.1f}" y2="{atas + ph + 5}" '
                       f'stroke="{tinta2}"/>')
            out.append(f'<text x="{X(v):.1f}" y="{atas + ph + 19}" text-anchor="middle" font-family="{FONT}" '
                       f'font-size="11" fill="{tinta}">{_fmt(v)}</text>')
    for v in ty:
        if y0 <= v <= y1:
            out.append(f'<line x1="{kiri - 5}" y1="{Y(v):.1f}" x2="{kiri}" y2="{Y(v):.1f}" stroke="{tinta2}"/>')
            out.append(f'<text x="{kiri - 8}" y="{Y(v) + 4:.1f}" text-anchor="end" font-family="{FONT}" '
                       f'font-size="11" fill="{tinta}">{_fmt(v)}</text>')
    out.append(f'<text x="{kiri + pw / 2:.1f}" y="{atas + ph + 40}" text-anchor="middle" font-family="{FONT}" '
               f'font-size="12" fill="{tinta}">TPSA (Å²)</text>')
    out.append(f'<text transform="translate(18,{atas + ph / 2:.1f}) rotate(-90)" text-anchor="middle" '
               f'font-family="{FONT}" font-size="12" fill="{tinta}">WLOGP</text>')
    # titik ligan
    urut = list(enumerate(titik))
    if pilih is not None and 0 <= pilih < len(titik):   # titik terpilih digambar paling atas
        urut.append(urut.pop(pilih))
    for i, (nama, x, y) in urut:
        sorot = pilih is not None and i == pilih
        r = 6 if sorot else 4.5
        out.append(f'<circle cx="{X(x):.2f}" cy="{Y(y):.2f}" r="{r}" fill="{"#cf3f3f" if sorot else titik_warna}" '
                   f'stroke="#ffffff" stroke-width="1"><title>{escape(nama)}: TPSA {_fmt(x)}, WLOGP {_fmt(y)}'
                   f'</title></circle>')
        if label and len(titik) <= 40:
            out.append(f'<text x="{X(x) + 7:.2f}" y="{Y(y) - 5:.2f}" font-family="{FONT}" font-size="10" '
                       f'fill="{"#1b2430" if di_elips(x, y, ELIPS_HIA) or not gelap else tinta}">{i + 1}</text>')
    # legenda
    ly = tinggi - 26
    lx = kiri
    for isi, t in ((putih, "Absorpsi saluran cerna tinggi (HIA)"), (kuning, "Menembus sawar darah otak (BBB)")):
        out.append(f'<rect x="{lx}" y="{ly - 10}" width="14" height="12" fill="{isi}" stroke="{garis_elips}"/>')
        out.append(f'<text x="{lx + 20}" y="{ly}" font-family="{FONT}" font-size="11" fill="{tinta}">{escape(t)}</text>')
        lx += 26 + int(len(t) * 6.2)
    out.append(f'<circle cx="{lx + 6}" cy="{ly - 4}" r="4.5" fill="{titik_warna}" stroke="#ffffff"/>')
    out.append(f'<text x="{lx + 16}" y="{ly}" font-family="{FONT}" font-size="11" fill="{tinta}">Ligan</text>')
    out.append(f'<text x="{kiri}" y="{tinggi - 8}" font-family="{FONT}" font-size="9.5" fill="{tinta2}">'
               f'Model BOILED-Egg: Daina &amp; Zoete, ChemMedChem 2016. WLOGP = Wildman–Crippen (RDKit).</text>')
    out.append("</svg>")
    return "\n".join(out)


def csv_teks(data, pemisah=";", desimal_koma=True):
    """data: [(nama, sifat, dg)] -> CSV (BOM, cocok Excel Indonesia)."""
    import csv
    import io

    def f(v):
        if isinstance(v, bool):
            return "Ya" if v else "Tidak"
        if isinstance(v, float):
            t = f"{v:.3f}".rstrip("0").rstrip(".")
            return t.replace(".", ",") if desimal_koma else t
        return "" if v is None else str(v)

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=pemisah, lineterminator="\r\n")
    w.writerow(["No", "Ligan", "ΔG terbaik (kcal/mol)"] + [t for k, t in KOLOM if k != "nama"] + ["Catatan"])
    for i, (nama, s, dg) in enumerate(data, 1):
        isi = [nama if k == "nama" else sel(s, k) for k, _ in KOLOM if k != "nama"]
        w.writerow([i, nama, f(dg)] + [f(v) for v in isi] + ["; ".join(ringkas_alasan(s))])
    return "﻿" + buf.getvalue()


def baris_xlsx(data):
    """(kolom, baris) untuk lembar 'Sifat ligan' di XLSX."""
    kolom = ["Ligan", "ΔG terbaik (kcal/mol)"] + [t for k, t in KOLOM if k != "nama"] + ["Catatan"]
    baris = []
    for nama, s, dg in data:
        baris.append([nama, dg] + [sel(s, k) for k, _ in KOLOM if k != "nama"] + ["; ".join(ringkas_alasan(s))])
    return kolom, baris
