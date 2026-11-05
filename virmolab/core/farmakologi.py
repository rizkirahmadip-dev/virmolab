"""Alur farmakologi jaringan: tanaman/senyawa -> saring ADMET -> target -> irisan gen penyakit -> PPI -> jalur.

Modul ini merangkai bagian yang sudah ada di VirmoLab menjadi satu alur yang utuh:

  core.tanaman      senyawa bahan alam dari takson tanaman (LOTUS/Wikidata, COCONUT)
  core.sifat        sifat fisikokimia dan aturan Lipinski/Veber/Egan
  core.admet        prediksi ADMET (ADMET-AI) untuk penyaringan
  core.target_balik target dugaan dari kemiripan ligan (ChEMBL) dan penargetan balik berbasis struktur
  core.ctd          interaksi senyawa–gen terkurasi dari literatur
  core.jaringan     gen penyakit (Open Targets), tepi PPI (STRING), perakitan graf, metrik
  core.pengayaan    pengayaan jalur (ORA hipergeometrik + Benjamini-Hochberg) atas GMT Reactome/GO-BP
  core.venn         diagram Venn irisan target senyawa dengan gen penyakit
  core.graf         tata letak, SVG, GraphML (Cytoscape/Gephi), CSV tepi

Fungsi di sini murni: tidak mengimpor Qt dan tidak menyentuh antarmuka. Yang mengakses internet hanya
pembungkus tipis di bagian "langkah alur"; sisanya bekerja atas data yang sudah di tangan.

Peringatan ilmiah yang melekat pada seluruh keluaran modul ini: hasil farmakologi jaringan adalah
hipotesis komputasi hasil penambangan basis data, bukan bukti aktivitas biologis. Tepi STRING memuat
bukti penambangan teks dan ko-ekspresi, bukan hanya interaksi fisik; asosiasi gen-penyakit bersifat
kualitatif dan tidak memperhitungkan dosis, metabolisme lintas pertama, maupun waktu dan lokasi di tubuh.
"""
import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import networkx as nx

from . import jaringan, pengayaan, venn

VERSI_KEADAAN = 1

# Parameter prioritas ADMET yang lazim dipakai pada penapisan awal network pharmacology.
# Nilai p adalah peluang 0-1 dari ADMET-AI; ambang di bawah ini adalah bawaan yang bisa diubah pengguna,
# bukan aturan baku. Sumber kebiasaan ambang: pedoman modul pelatihan dan praktik umum publikasi.
KRITERIA_BAWAAN: Dict[str, Any] = {
    "lipinski_maks": 1,          # pelanggaran aturan lima maksimum (0 = ketat)
    "hia_min": 0.30,             # peluang absorpsi usus manusia minimum
    "bioavailability_min": 0.30,  # peluang bioavailabilitas oral minimum (padanan F30%)
    "dili_maks": 0.70,           # peluang cedera hati maksimum
    "herg_maks": 0.70,           # peluang penghambatan hERG maksimum
    "ames_maks": 0.70,           # peluang mutagenik maksimum
    "pains": True,               # buang senyawa yang kena peringatan PAINS
}

# Pemetaan kriteria -> (kunci ADMET, arah). Arah +1 = nilai harus >= ambang, -1 = harus <= ambang.
_PETA_ADMET = {
    "hia_min": ("HIA_Hou", +1),
    "bioavailability_min": ("Bioavailability_Ma", +1),
    "dili_maks": ("DILI", -1),
    "herg_maks": ("hERG", -1),
    "ames_maks": ("AMES", -1),
}

# Sumber target disimpan sebagai kunci, bukan kalimat, supaya paragraf metode Inggris tidak kemasukan
# teks Indonesia. Nilai: (label Indonesia, label Inggris).
SUMBER_TARGET = {
    "kemiripan": ("kemiripan ligan ChEMBL (ECFP4, pChEMBL ≥ 6)",
                  "ligand similarity against ChEMBL actives (ECFP4, pChEMBL ≥ 6)"),
    "ctd": ("interaksi senyawa–gen terkurasi dari CTD", "curated chemical-gene interactions from CTD"),
    "impor": ("tabel target yang diimpor pengguna", "a user-supplied target table"),
    "docking": ("penargetan balik berbasis struktur", "structure-based reverse docking"),
}


def label_sumber(kunci: Sequence[str], inggris: bool = False) -> str:
    """Gabungkan kunci sumber target menjadi satu frasa dalam bahasa yang diminta."""
    label = [SUMBER_TARGET[k][1 if inggris else 0] for k in kunci if k in SUMBER_TARGET]
    sisa = [str(k) for k in kunci if k not in SUMBER_TARGET]      # kunci lama / tak dikenal: apa adanya
    label += sisa
    if not label:
        return SUMBER_TARGET["kemiripan"][1 if inggris else 0]
    if len(label) == 1:
        return label[0]
    return ("; ".join(label[:-1])) + (" and " if inggris else " dan ") + label[-1]


# Label alasan pengguguran, dipakai tabel ringkasan di laporan. Kuncinya sama dengan `alasan_kode`
# yang ditulis saring() pada tiap senyawa.
LABEL_ALASAN = {
    "struktur": "Struktur tidak terbaca",
    "lipinski": "Melanggar aturan lima Lipinski",
    "pains": "Kena peringatan PAINS",
    "hia_min": "Absorpsi usus di bawah ambang",
    "bioavailability_min": "Bioavailabilitas oral di bawah ambang",
    "dili_maks": "Risiko cedera hati di atas ambang",
    "herg_maks": "Risiko hERG di atas ambang",
    "ames_maks": "Risiko mutagenik di atas ambang",
}

# Nama set gen sebagaimana ditulis di naskah, bukan kunci berkasnya.
NAMA_GMT = {"reactome": "Reactome", "go_bp": "Gene Ontology — Biological Process"}

LABEL_KRITERIA = {
    "lipinski_maks": "Pelanggaran Lipinski maksimum",
    "hia_min": "Absorpsi usus manusia (HIA) minimum",
    "bioavailability_min": "Bioavailabilitas oral minimum",
    "dili_maks": "Risiko cedera hati (DILI) maksimum",
    "herg_maks": "Risiko hERG maksimum",
    "ames_maks": "Risiko mutagenik (Ames) maksimum",
    "pains": "Buang senyawa dengan peringatan PAINS",
}


class GalatFarmakologi(Exception):
    """Galat yang harus sampai ke pengguna (berkas tidak terbaca, data kosong, jaringan mati)."""


# ------------------------------------------------------------------ keadaan alur
def keadaan_baru() -> Dict[str, Any]:
    """Keadaan alur farmakologi jaringan yang kosong, siap disimpan ke proyek.json."""
    return {
        "versi": VERSI_KEADAAN,
        "tanaman": "",              # nama tanaman / sumber senyawa
        "penyakit": {"id": "", "nama": "", "sumber": ""},
        "senyawa": [],              # [{nama, smiles, sumber, sifat: {...}, admet: {...}, lolos: bool, alasan: [..]}]
        "target_senyawa": {},       # {nama_senyawa: [gen, ...]}
        "sumber_target": [],        # metode yang dipakai: kemiripan | ctd | docking
        "gen_penyakit": [],         # [{gen, skor, sumber}]
        "irisan": [],               # [gen, ...] target senyawa ∩ gen penyakit
        "tepi_ppi": [],             # [[a, b, skor], ...]
        "ambang_string": jaringan.AMBANG_STRING,
        "jalur": [],                # keluaran pengayaan.hipergeometrik
        "gmt": "reactome",
        "hub": [],                  # [{gen, derajat, betweenness, closeness, mcc}]
        "catatan": "",
    }


def migrasi(k: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Lengkapi keadaan lama dengan kunci baru (aditif, seperti core.proyek.migrasi_proyek)."""
    baru = keadaan_baru()
    if isinstance(k, dict):
        for kunci, nilai in k.items():
            if kunci in baru:
                baru[kunci] = nilai
    return baru


# ------------------------------------------------------------------ 1. senyawa
def senyawa_dari_daftar(baris: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalkan daftar senyawa dari sumber mana pun menjadi bentuk baku alur ini.

    Menerima dict dengan kunci nama/smiles dalam berbagai ejaan (nama, name, senyawa, judul; smiles, SMILES).
    """
    hasil, dilihat, nama_dipakai = [], set(), set()
    for b in baris:
        nama = str(b.get("nama") or b.get("name") or b.get("senyawa") or b.get("judul") or "").strip()
        smiles = str(b.get("smiles") or b.get("SMILES") or b.get("isomeric_smiles") or "").strip()
        if not smiles:
            continue
        if smiles in dilihat:
            continue
        dilihat.add(smiles)
        # Nama dibuat unik: peta target berkunci nama, jadi dua struktur bernama sama akan menyatu dan
        # satu kehilangan targetnya. LOTUS memang memulangkan nama kembar untuk stereoisomer/tautomer.
        nama = nama or f"Senyawa {len(hasil) + 1}"
        if nama in nama_dipakai:
            n = 2
            while f"{nama} ({n})" in nama_dipakai:
                n += 1
            nama = f"{nama} ({n})"
        nama_dipakai.add(nama)
        hasil.append({"nama": nama, "smiles": smiles,
                      "sumber": str(b.get("sumber") or b.get("source") or "").strip(),
                      "sifat": {}, "admet": {}, "lolos": True, "alasan": []})
    return hasil


def impor_senyawa_csv(path) -> List[Dict[str, Any]]:
    """Baca daftar senyawa dari CSV/TSV hasil unduhan pengguna (mis. ekspor KNApSAcK + kolom SMILES).

    Kolom dikenali dari baris kepala: nama/name/compound/metabolite dan smiles/isomeric smiles/canonical smiles.
    Pemisah dideteksi otomatis (koma, titik koma, atau tab).
    """
    p = Path(path)
    try:
        teks = p.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as e:
        raise GalatFarmakologi(f"Berkas senyawa tidak terbaca: {e}")
    if not teks.strip():
        raise GalatFarmakologi("Berkas senyawa kosong.")
    contoh = teks[:4096]
    pemisah = "\t" if contoh.count("\t") > contoh.count(";") and contoh.count("\t") > contoh.count(",") \
        else (";" if contoh.count(";") > contoh.count(",") else ",")
    pembaca = csv.DictReader(teks.splitlines(), delimiter=pemisah)

    def cari(baris, *kandidat):
        for k, v in baris.items():
            nama_kolom = (k or "").strip().lower()
            if nama_kolom in kandidat:
                return (v or "").strip()
        for k, v in baris.items():
            nama_kolom = (k or "").strip().lower()
            if any(c in nama_kolom for c in kandidat):
                return (v or "").strip()
        return ""

    mentah = []
    for baris in pembaca:
        if not baris:
            continue
        mentah.append({
            "nama": cari(baris, "nama", "name", "compound", "metabolite", "metabolit", "senyawa"),
            "smiles": cari(baris, "isomeric smiles", "isomeric_smiles", "smiles", "canonical smiles"),
            "sumber": cari(baris, "sumber", "source", "database") or p.name,
        })
    hasil = senyawa_dari_daftar(mentah)
    if not hasil:
        raise GalatFarmakologi("Tidak ada kolom SMILES yang bisa dibaca dari berkas itu. "
                               "Pastikan ada kolom bernama SMILES (atau Isomeric SMILES).")
    return hasil


# ------------------------------------------------------------------ 2. saring ADMET
def hitung_sifat(senyawa: List[Dict[str, Any]], lapor=None) -> List[Dict[str, Any]]:
    """Isi kunci `sifat` tiap senyawa dengan hasil core.sifat.hitung() dari SMILES-nya."""
    from rdkit import Chem
    from . import sifat as M_sifat
    for i, s in enumerate(senyawa):
        if lapor is not None and i % 20 == 0:
            lapor.progres.emit(i, len(senyawa), "Menghitung sifat fisikokimia")
        mol = Chem.MolFromSmiles(s["smiles"])
        if mol is None:
            s["sifat"] = {}
            s["sifat_gagal"] = "SMILES tidak bisa dibaca RDKit"
            continue
        try:
            s["sifat"] = M_sifat.hitung(mol)
            s.pop("sifat_gagal", None)
        except Exception as e:
            s["sifat"] = {}
            s["sifat_gagal"] = f"sifat gagal dihitung: {e}"
    return senyawa


def saring(senyawa: List[Dict[str, Any]], kriteria: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Tandai tiap senyawa lolos/tidak menurut kriteria ADMET dan Lipinski.

    Senyawa yang nilai ADMET-nya belum ada tidak digugurkan karena alasan itu — ketiadaan data bukan
    bukti buruk. Alasannya dicatat agar pengguna sadar penyaringannya belum lengkap.
    Kembalikan {lolos, gagal, tanpa_admet, kriteria}.
    """
    k = dict(KRITERIA_BAWAAN)
    if kriteria:
        k.update({x: y for x, y in kriteria.items() if x in KRITERIA_BAWAAN})
    n_lolos = n_gagal = n_tanpa = 0
    for s in senyawa:
        alasan: List[str] = []
        # Kode kriteria disimpan terpisah dari kalimatnya supaya laporan bisa mengelompokkan alasan
        # pengguguran tanpa memotong-motong teksnya.
        kode: List[str] = []
        sf, ad = s.get("sifat") or {}, s.get("admet") or {}
        # Struktur yang tidak terbaca digugurkan keras: tanpa struktur, tidak ada tahap berikutnya
        # yang bisa dikerjakan untuk senyawa itu.
        gagal_struktur = s.get("sifat_gagal")
        if gagal_struktur:
            alasan.append(str(gagal_struktur))
            kode.append("struktur")
        elif not sf:
            alasan.append("sifat belum dihitung")

        # core.sifat.hitung() memberi `lipinski` sebagai jumlah pelanggaran dan `pains` sebagai daftar
        # deskripsi pencocokan; keduanya juga diterima dalam bentuk lain agar aman dipakai sumber lain.
        pelanggaran = sf.get("lipinski")
        n_pelanggaran = len(pelanggaran) if isinstance(pelanggaran, (list, tuple)) else int(pelanggaran or 0)
        if sf and n_pelanggaran > int(k["lipinski_maks"]):
            alasan.append(f"pelanggaran Lipinski {n_pelanggaran} > {k['lipinski_maks']}")
            kode.append("lipinski")
        pains = sf.get("pains")
        kena_pains = bool(pains) if isinstance(pains, (list, tuple)) else \
            str(pains or "").strip().lower() not in ("", "0", "tidak", "no", "-", "none")
        if k.get("pains") and sf and kena_pains:
            n_pains = len(pains) if isinstance(pains, (list, tuple)) else 1
            alasan.append(f"kena peringatan PAINS ({n_pains})")
            kode.append("pains")

        if not ad:
            n_tanpa += 1
        for kunci, (kunci_admet, arah) in _PETA_ADMET.items():
            nilai = ad.get(kunci_admet)
            if nilai is None:
                continue
            ambang = float(k[kunci])
            if arah > 0 and float(nilai) < ambang:
                alasan.append(f"{kunci_admet} {float(nilai):.2f} < {ambang:g}")
                kode.append(kunci)
            elif arah < 0 and float(nilai) > ambang:
                alasan.append(f"{kunci_admet} {float(nilai):.2f} > {ambang:g}")
                kode.append(kunci)

        keras = [a for a in alasan if a != "sifat belum dihitung"]
        s["alasan"] = alasan
        s["alasan_kode"] = kode
        s["lolos"] = not keras
        n_lolos += bool(s["lolos"])
        n_gagal += not s["lolos"]
    return {"lolos": n_lolos, "gagal": n_gagal, "tanpa_admet": n_tanpa, "kriteria": k}


def yang_lolos(senyawa: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [s for s in senyawa if s.get("lolos")]


# ------------------------------------------------------------------ 3. gen penyakit
def impor_gen_penyakit(path, skor_min: float = 0.0) -> List[Dict[str, Any]]:
    """Baca gen penyakit dari ekspor CSV/TSV milik pengguna (GeneCards, DisGeNET, OMIM, CTD, dll.).

    GeneCards berlisensi berbayar dan melarang pengambilan otomatis, jadi VirmoLab tidak menghubunginya;
    jalurnya adalah pengguna mengunduh sendiri dari akunnya lalu mengimpor berkasnya di sini.

    Kolom gen dikenali dari: gene symbol, gene_symbol, symbol, gen, gene.
    Kolom skor (opsional): relevance score, score, gda, skor.
    """
    p = Path(path)
    try:
        teks = p.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as e:
        raise GalatFarmakologi(f"Berkas gen penyakit tidak terbaca: {e}")
    baris_teks = [b for b in teks.splitlines() if b.strip()]
    if not baris_teks:
        raise GalatFarmakologi("Berkas gen penyakit kosong.")
    contoh = teks[:4096]
    pemisah = "\t" if contoh.count("\t") > max(contoh.count(";"), contoh.count(",")) \
        else (";" if contoh.count(";") > contoh.count(",") else ",")
    pembaca = csv.DictReader(baris_teks, delimiter=pemisah)

    kunci_gen = ("gene symbol", "gene_symbol", "symbol", "gen", "gene", "genesymbol")
    kunci_skor = ("relevance score", "relevance_score", "score", "gda", "skor", "relevance")
    hasil, dilihat = [], set()
    for baris in pembaca:
        gen = skor = ""
        for k, v in (baris or {}).items():
            nama_kolom = (k or "").strip().lower()
            if not gen and nama_kolom in kunci_gen:
                gen = (v or "").strip()
            if not skor and nama_kolom in kunci_skor:
                skor = (v or "").strip()
        gen = gen.upper()
        if not gen or gen in dilihat:
            continue
        try:
            nilai = float(str(skor).replace(",", ".")) if skor else 0.0
        except ValueError:
            nilai = 0.0
        if skor and nilai < skor_min:
            continue
        dilihat.add(gen)
        hasil.append({"gen": gen, "skor": nilai, "sumber": p.name})
    if not hasil:
        raise GalatFarmakologi("Tidak ada kolom simbol gen yang bisa dibaca dari berkas itu. "
                               "Pastikan ada kolom bernama Gene Symbol (atau Symbol / Gene).")
    hasil.sort(key=lambda b: (-b["skor"], b["gen"]))
    return hasil


# ------------------------------------------------------------------ 4. irisan
def irisan(target_senyawa: Dict[str, Sequence[str]], gen_penyakit: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Irisan target senyawa dengan gen penyakit — "potential therapeutic target".

    Kembalikan {wilayah, target, penyakit, irisan} dengan `wilayah` siap dipakai core.venn.
    """
    t = sorted({g.upper() for daftar in target_senyawa.values() for g in daftar if g})
    p = sorted({str(b.get("gen") or "").upper() for b in gen_penyakit if b.get("gen")})
    w = venn.hitung2(t, p)
    return {"wilayah": w, "target": t, "penyakit": p, "irisan": w["AB"]}


# ------------------------------------------------------------------ 5. jaringan dan hub
def mcc(G: nx.Graph, batas_simpul: int = 400) -> Dict[str, float]:
    """Maximal Clique Centrality (cytoHubba): MCC(v) = Σ (|C| − 1)! atas semua klik maksimal C yang memuat v.

    Simpul tanpa klik berukuran ≥ 2 diberi nilai derajatnya, mengikuti definisi asli Chin dkk. (2014).
    Pencacahan klik maksimal berbiaya eksponensial pada graf padat, jadi graf di atas `batas_simpul`
    dikembalikan sebagai derajat saja agar antarmuka tidak membeku — pembatasan ini dilaporkan ke pemanggil
    lewat nilai yang identik dengan derajat.
    """
    import math
    if len(G) == 0:
        return {}
    if len(G) > batas_simpul:
        return {n: float(G.degree(n)) for n in G}
    nilai = {n: 0.0 for n in G}
    ada_klik = {n: False for n in G}
    for klik in nx.find_cliques(G):
        if len(klik) < 2:
            continue
        tambah = float(math.factorial(len(klik) - 1))
        for n in klik:
            nilai[n] += tambah
            ada_klik[n] = True
    for n in G:
        if not ada_klik[n]:
            nilai[n] = float(G.degree(n))
    return nilai


def hub(G: nx.Graph, n: int = 20, hanya_target: bool = True, min_derajat: int = 1) -> List[Dict[str, Any]]:
    """Peringkat hub protein: derajat, betweenness, closeness, dan MCC.

    Urutan utama memakai MCC (cytoHubba memakainya sebagai metode dengan ketepatan terbaik pada
    protein esensial), dengan derajat sebagai pemecah seri.

    min_derajat: protein tanpa tepi PPI sama sekali dibuang dari peringkat. Protein terpencil
    bukan hub menurut definisi apa pun, dan menampilkannya dengan nilai nol memenuhi tabel dengan
    baris yang tidak berarti. Jumlahnya dilaporkan terpisah lewat `terpencil()`.
    """
    if len(G) == 0:
        return []
    baris = jaringan.metrik(G)
    nilai_mcc = mcc(G)
    hasil = []
    for b in baris:
        if hanya_target and b["jenis"] != "target":
            continue
        if b["derajat"] < min_derajat:
            continue
        hasil.append({"gen": b["label"], "simpul": b["simpul"], "derajat": b["derajat"],
                      "betweenness": b["betweenness"], "closeness": b["closeness"],
                      "mcc": round(nilai_mcc.get(b["simpul"], 0.0), 2)})
    hasil.sort(key=lambda b: (-b["mcc"], -b["derajat"], b["gen"]))
    return hasil[:n] if n else hasil


def terpencil(G: nx.Graph, hanya_target: bool = True) -> List[str]:
    """Simbol gen yang tidak punya satu pun tepi PPI pada ambang yang dipakai.

    Berguna dilaporkan apa adanya: ketiadaan tepi bisa berarti ambang STRING terlalu tinggi,
    bukan berarti proteinnya tidak berperan.
    """
    return sorted(d.get("label", n) for n, d in G.nodes(data=True)
                  if G.degree(n) == 0 and (not hanya_target or d.get("jenis") == "target"))


def graf_ppi(gen: Sequence[str], tepi: Sequence) -> nx.Graph:
    """Graf PPI murni (hanya lapisan target-target) untuk analisis hub."""
    G = nx.Graph()
    for g in dict.fromkeys(x.upper() for x in gen if x):
        G.add_node(f"T:{g}", jenis="target", label=g)
    for e in tepi:
        a, b, s = (e[0], e[1], e[2]) if len(e) >= 3 else (e[0], e[1], 1.0)
        if f"T:{str(a).upper()}" in G and f"T:{str(b).upper()}" in G:
            G.add_edge(f"T:{str(a).upper()}", f"T:{str(b).upper()}", jenis="target-target",
                       skor=round(float(s), 3))
    return G


# ------------------------------------------------------------------ 6. jalur
def jalur(gen: Sequence[str], nama_gmt: str = "reactome", latar: Optional[Sequence[str]] = None,
          q_maks: float = 0.05, maks: int = 30) -> List[Dict[str, Any]]:
    """Pengayaan jalur atas gen yang diberikan (ORA hipergeometrik + Benjamini-Hochberg)."""
    gen = [g.upper() for g in gen if g]
    if not gen:
        return []
    set_gen = pengayaan.gmt_bawaan(nama_gmt)
    baris = pengayaan.hipergeometrik(gen, set_gen, latar=latar, min_overlap=2)
    terpilih = [b for b in baris if b.get("q", 1.0) <= q_maks]
    return (terpilih or baris)[:maks]


# ------------------------------------------------------------------ 7. metode dan ringkasan
def _koma(x) -> str:
    return f"{x:g}".replace(".", ",")


def paragraf_metode(k: Dict[str, Any], inggris: bool = False) -> str:
    """Paragraf metode siap tempel untuk bagian Methods, mengikuti keadaan alur yang sudah dijalankan."""
    n_senyawa = len(k.get("senyawa") or [])
    n_lolos = len(yang_lolos(k.get("senyawa") or []))
    n_target = len({g for d in (k.get("target_senyawa") or {}).values() for g in d})
    n_penyakit = len(k.get("gen_penyakit") or [])
    n_irisan = len(k.get("irisan") or [])
    n_tepi = len(k.get("tepi_ppi") or [])
    ambang = k.get("ambang_string", jaringan.AMBANG_STRING)
    n_jalur = len(k.get("jalur") or [])
    gmt = {"reactome": "Reactome", "go_bp": "Gene Ontology Biological Process"}.get(k.get("gmt"), k.get("gmt") or "")
    sumber = label_sumber(k.get("sumber_target") or [], inggris=inggris)
    penyakit = (k.get("penyakit") or {}).get("nama") or ("the disease studied" if inggris
                                                         else "penyakit yang diteliti")
    tanaman = k.get("tanaman") or ("the compound source" if inggris else "sumber senyawa")

    if inggris:
        def j(n, tunggal, jamak=None):
            return f"{n} {tunggal if n == 1 else (jamak or tunggal + 's')}"
        return (
            f"Network pharmacology analysis was performed in VirmoLab. {j(n_senyawa, 'compound')} from {tanaman} "
            f"were collected and screened on physicochemical and predicted ADMET criteria, leaving "
            f"{j(n_lolos, 'compound')}. Putative targets were assigned by {sumber}, giving "
            f"{j(n_target, 'unique gene symbol')}. Disease-associated genes for {penyakit} "
            f"({j(n_penyakit, 'gene')}) were intersected with the compound targets, yielding "
            f"{j(n_irisan, 'potential therapeutic target')}. A protein-protein interaction network "
            f"was retrieved from STRING (Homo sapiens, combined score ≥ {ambang:g}), producing "
            f"{j(n_tepi, 'edge')}; hub proteins were ranked by Maximal Clique Centrality. "
            f"Over-representation analysis against {gmt} gene sets used the one-sided hypergeometric test "
            f"with Benjamini-Hochberg correction, and {j(n_jalur, 'pathway')} are reported. These results are "
            f"computational hypotheses and require experimental validation."
        )
    return (
        f"Analisis farmakologi jaringan dikerjakan dengan VirmoLab. Sebanyak {n_senyawa} senyawa dari {tanaman} "
        f"dikumpulkan lalu disaring berdasarkan sifat fisikokimia dan prediksi ADMET, menyisakan {n_lolos} senyawa. "
        f"Target dugaan ditetapkan melalui {sumber}, menghasilkan {n_target} simbol gen unik. Sebanyak {n_penyakit} "
        f"gen yang berasosiasi dengan {penyakit} kemudian diiriskan dengan target senyawa, sehingga diperoleh "
        f"{n_irisan} target terapi potensial. Jaringan interaksi protein–protein diambil dari STRING (Homo sapiens, skor gabungan "
        f"≥ {_koma(ambang)}) dan memuat {n_tepi} tepi; protein hub diperingkat dengan Maximal Clique Centrality. "
        f"Pengayaan jalur terhadap set gen {gmt} memakai uji hipergeometrik satu sisi dengan koreksi Benjamini-Hochberg, "
        f"dan {n_jalur} jalur dilaporkan. Seluruh hasil ini merupakan hipotesis komputasi dan memerlukan validasi "
        f"eksperimental."
    )


def ringkasan(k: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Ringkasan angka per tahap, untuk kartu di antarmuka dan tabel di laporan."""
    senyawa = k.get("senyawa") or []
    return [
        {"tahap": "Senyawa", "nilai": len(senyawa), "satuan": "senyawa", "ket": k.get("tanaman") or ""},
        {"tahap": "Lolos ADMET", "nilai": len(yang_lolos(senyawa)), "satuan": "senyawa", "ket": ""},
        {"tahap": "Target senyawa", "nilai": len({g for d in (k.get("target_senyawa") or {}).values() for g in d}),
         "satuan": "gen", "ket": label_sumber(k.get("sumber_target") or []) if k.get("sumber_target") else ""},
        {"tahap": "Gen penyakit", "nilai": len(k.get("gen_penyakit") or []), "satuan": "gen",
         "ket": (k.get("penyakit") or {}).get("nama") or ""},
        {"tahap": "Irisan", "nilai": len(k.get("irisan") or []), "satuan": "target potensial", "ket": ""},
        {"tahap": "Tepi PPI", "nilai": len(k.get("tepi_ppi") or []), "satuan": "tepi",
         "ket": f"STRING ≥ {_koma(k.get('ambang_string', jaringan.AMBANG_STRING))}"},
        {"tahap": "Jalur", "nilai": len(k.get("jalur") or []), "satuan": "jalur",
         "ket": NAMA_GMT.get(k.get("gmt"), k.get("gmt") or "")},
    ]


def ke_json(k: Dict[str, Any]) -> str:
    """Keadaan alur sebagai JSON rapi (untuk ekspor dan lampiran suplemen)."""
    return json.dumps(k, ensure_ascii=False, indent=2, default=str)
