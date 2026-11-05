"""Modul pencarian senyawa bahan alam dari takson tanaman obat (F1).

Menghubungkan nama lokal/ilmiah tanaman obat Indonesia dengan:
1. LOTUS (Knowledge Base of Natural Products) via Wikidata SPARQL (P703).
2. COCONUT 2.0 (Collection of Open Natural Products) lokal jika tersedia.
3. Standarisasi struktur (RDKit rdMolStandardize) dan penghitungan sifat obat (sifat.py).
"""
import csv
from pathlib import Path
import urllib.parse

from rdkit import Chem
from rdkit.Chem.MolStandardize import rdMolStandardize

from . import paths, pustaka, sifat, sumber_data
from .sumber_data import Jejak


def _jalur_csv_tanaman() -> Path:
    """Temukan jalur berkas nama_tanaman_id.csv."""
    calon = [
        paths.PAKET / "data" / "nama_tanaman_id.csv",
        paths.AKAR / "data" / "nama_tanaman_id.csv",
        Path(__file__).resolve().parents[2] / "data" / "nama_tanaman_id.csv",
        Path(__file__).resolve().parents[1] / "data" / "nama_tanaman_id.csv",
    ]
    for c in calon:
        if c.exists():
            return c
    return calon[0]


def daftar_tanaman_lokal() -> list[dict]:
    """Baca daftar tanaman obat Indonesia dari berkas CSV yang dibundel."""
    jalur = _jalur_csv_tanaman()
    if not jalur.exists():
        return []
    hasil = []
    with open(jalur, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            hasil.append({
                "nama_lokal": r.get("nama_lokal", "").strip(),
                "nama_ilmiah": r.get("nama_ilmiah", "").strip(),
                "famili": r.get("famili", "").strip(),
                "sumber": r.get("sumber", "").strip(),
            })
    return hasil


def _bersihkan_teks(t: str) -> str:
    return t.strip().lower()


def cari_takson(nama: str) -> list[dict]:
    """Cari takson tanaman berdasarkan nama lokal atau nama ilmiah.

    Mengembalikan daftar entri:
    [{"qid": str, "nama_ilmiah": str, "peringkat": str, "sinonim": list[str],
      "nama_lokal": str, "famili": str, "sumber": str}]
    """
    q_bersih = _bersihkan_teks(nama)
    if not q_bersih:
        return []

    daftar_lokal = daftar_tanaman_lokal()
    cocok_lokal = []
    nama_ilmiah_calon = []

    for d in daftar_lokal:
        nl = _bersihkan_teks(d["nama_lokal"])
        ni = _bersihkan_teks(d["nama_ilmiah"])
        if q_bersih == nl or q_bersih in nl:
            cocok_lokal.append(d)
            nama_ilmiah_calon.append(d["nama_ilmiah"])
        elif q_bersih == ni or q_bersih in ni:
            cocok_lokal.append(d)
            nama_ilmiah_calon.append(d["nama_ilmiah"])

    # Bila tidak ada di lokal, jadikan masukan sebagai nama ilmiah langsung
    if not nama_ilmiah_calon:
        nama_ilmiah_calon.append(nama.strip())

    # Kueri Wikidata SPARQL untuk taksonomi resmi
    values_clause = " ".join(f'"{urllib.parse.quote(n, safe=" ")}"' for n in nama_ilmiah_calon[:5])
    # Gunakan kueri SPARQL yang mencari takson (P225) atau sinonim takson (P1420)
    sparql_query = f"""
SELECT ?item ?taxonName ?rankLabel ?familyLabel (GROUP_CONCAT(DISTINCT ?synonym; separator="|") AS ?synonyms) WHERE {{
  VALUES ?targetName {{ {values_clause} }}
  {{
    ?item wdt:P225 ?targetName ;
          wdt:P31 wd:Q16521 .
  }} UNION {{
    ?item wdt:P1420 ?targetName ;
          wdt:P31 wd:Q16521 .
  }}
  OPTIONAL {{ ?item wdt:P225 ?taxonName . }}
  OPTIONAL {{ ?item wdt:P105 ?rank . }}
  OPTIONAL {{
    ?item wdt:P171* ?family .
    ?family wdt:P105 wd:Q35409 .
  }}
  OPTIONAL {{ ?item wdt:P1420 ?synonym . }}
  FILTER(STRSTARTS(STR(?item), "http://www.wikidata.org/entity/Q"))
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "id,en". }}
}}
GROUP BY ?item ?taxonName ?rankLabel ?familyLabel
LIMIT 20
"""
    endpoint = "https://query.wikidata.org/sparql"
    hasil = []
    sudah_qid = set()

    try:
        bindings, _ = sumber_data.sparql(endpoint, sparql_query, batas=45, lisensi="CC0 1.0", sumber="Wikidata Takson")
        for b in bindings:
            uri = b.get("item", {}).get("value", "")
            qid = uri.split("/")[-1] if "/" in uri else uri
            if not qid.startswith("Q") or qid in sudah_qid:
                continue
            sudah_qid.add(qid)

            t_name = b.get("taxonName", {}).get("value", "")
            rank = b.get("rankLabel", {}).get("value", "spesies")
            fam = b.get("familyLabel", {}).get("value", "")
            syns_raw = b.get("synonyms", {}).get("value", "")
            syns = [s.strip() for s in syns_raw.split("|") if s.strip()]

            # Cari nama lokal yang cocok
            nlokal = ""
            for cl in cocok_lokal:
                if cl["nama_ilmiah"].lower() == t_name.lower() or cl["sumber"].endswith(qid):
                    nlokal = cl["nama_lokal"]
                    if not fam and cl.get("famili"):
                        fam = cl["famili"]
                    break

            hasil.append({
                "qid": qid,
                "nama_ilmiah": t_name or nama.strip(),
                "peringkat": rank,
                "sinonim": syns,
                "nama_lokal": nlokal,
                "famili": fam,
                "sumber": f"Wikidata {qid}",
            })
    except Exception:
        # Fallback bila jaringan gagal tapi ada kecocokan di CSV lokal
        for cl in cocok_lokal:
            qid_part = cl["sumber"].replace("Wikidata", "").strip()
            if qid_part and qid_part not in sudah_qid:
                sudah_qid.add(qid_part)
                hasil.append({
                    "qid": qid_part,
                    "nama_ilmiah": cl["nama_ilmiah"],
                    "peringkat": "spesies",
                    "sinonim": [],
                    "nama_lokal": cl["nama_lokal"],
                    "famili": cl.get("famili", ""),
                    "sumber": cl["sumber"],
                })

    return hasil


def buat_kueri_lotus(qid: str, turunan: bool = False, batas: int = 5000) -> str:
    """Susun kueri SPARQL LOTUS untuk mengambil senyawa yang dilaporkan dari takson."""
    if turunan:
        takson_clause = f"?takson wdt:P171* wd:{qid} ."
    else:
        takson_clause = f"VALUES ?takson {{ wd:{qid} }}"

    q = f"""
SELECT ?senyawa ?nama ?smiles ?inchikey (GROUP_CONCAT(DISTINCT ?artikel; separator="|") AS ?artikels) WHERE {{
  ?senyawa wdt:P703 ?takson ;
           wdt:P235 ?inchikey .
  {takson_clause}
  OPTIONAL {{ ?senyawa wdt:P2017 ?isomericSmiles . }}
  OPTIONAL {{ ?senyawa wdt:P233 ?canonicalSmiles . }}
  BIND(COALESCE(?isomericSmiles, ?canonicalSmiles) AS ?smiles)
  FILTER(BOUND(?smiles))
  OPTIONAL {{
    ?senyawa p:P703 ?pernyataan .
    ?pernyataan ps:P703 ?takson ; prov:wasDerivedFrom/pr:P248 ?artikel .
  }}
  OPTIONAL {{ ?senyawa rdfs:label ?nama FILTER(lang(?nama)="en") }}
}}
GROUP BY ?senyawa ?nama ?smiles ?inchikey
LIMIT {batas}
"""
    return q


def proses_hasil_lotus(bindings_atau_data: list | dict) -> list[dict]:
    """Konversi bindings SPARQL LOTUS Wikidata menjadi daftar senyawa."""
    if isinstance(bindings_atau_data, dict):
        bindings = bindings_atau_data.get("results", {}).get("bindings", [])
    else:
        bindings = bindings_atau_data

    daftar = []
    for b in bindings:
        uri_senyawa = b.get("senyawa", {}).get("value", "")
        qid_senyawa = uri_senyawa.split("/")[-1] if "/" in uri_senyawa else uri_senyawa
        nama = b.get("nama", {}).get("value", "") or qid_senyawa
        smiles = b.get("smiles", {}).get("value", "")
        inchikey = b.get("inchikey", {}).get("value", "")
        # Rujukan LOTUS = item artikel (QID). DOI & tahun ada di graf ilmiah terpisah (lihat rincian_artikel).
        artikel = [a.rsplit("/", 1)[-1] for a in b.get("artikels", {}).get("value", "").split("|") if a.strip()]
        dois_str = b.get("dois", {}).get("value", "")  # format respons lama (sebelum graph split)
        rujukan = [doi.strip() for doi in dois_str.split("|") if doi.strip()]
        tahun_str = b.get("tahun", {}).get("value", "")
        tahun = int(tahun_str) if tahun_str.isdigit() else None

        if not smiles:
            continue

        daftar.append({
            "qid": qid_senyawa,
            "nama": nama,
            "smiles": smiles,
            "inchikey": inchikey,
            "rujukan": rujukan,
            "artikel": artikel,
            "tahun": tahun,
            "asal": "LOTUS",
        })

    return daftar


def dibatalkan(batal) -> bool:
    """True bila pemanggil meminta pekerjaan dihentikan.

    `batal` boleh berupa threading.Event (dipakai dialog, punya is_set()), fungsi yang mengembalikan
    bool, atau None. Dulu modul ini mengandaikan hanya fungsi, sehingga Event dari ui/dialog_tanaman.py
    memicu TypeError: 'Event' object is not callable begitu takson punya rujukan artikel.
    """
    if batal is None:
        return False
    cek = getattr(batal, "is_set", None)
    if callable(cek):
        return bool(cek())
    if callable(batal):
        return bool(batal())
    return bool(batal)


def senyawa_takson(qid: str, turunan: bool = False, batas: int = 5000,
                   batal=None) -> tuple[list[dict], Jejak]:
    """Ambil senyawa dari takson tanaman via SPARQL LOTUS (Wikidata)."""
    q = buat_kueri_lotus(qid, turunan=turunan, batas=batas)
    endpoint = "https://query.wikidata.org/sparql"
    bindings, jejak = sumber_data.sparql(
        endpoint, q, batas=60, lisensi="CC0 1.0", sumber="LOTUS (Wikidata)"
    )
    daftar = proses_hasil_lotus(bindings)
    qids = sorted({a for d in daftar for a in d.get("artikel", [])})
    if qids and not dibatalkan(batal):
        try:
            peta, _ = rincian_artikel(qids, batal=batal)
            gabung_rincian(daftar, peta)
        except Exception as e:  # rujukan tetap ada sebagai QID bila graf ilmiah tidak terjangkau
            jejak.versi = f"{jejak.versi}; rincian rujukan gagal: {e}"
    return daftar, jejak


ENDPOINT_ILMIAH = "https://query-scholarly.wikidata.org/sparql"


def rincian_artikel(qids: list[str], per_kueri: int = 150, batal=None) -> tuple[dict, Jejak | None]:
    """DOI, tahun, dan judul artikel rujukan.

    Sejak pemisahan graf Wikidata Query Service (2025), item artikel ilmiah hanya ada di endpoint
    query-scholarly; endpoint utama tidak lagi memuat P356 (DOI) / P577 (tanggal terbit) artikel.
    """
    peta, jejak = {}, None
    for i in range(0, len(qids), per_kueri):
        if dibatalkan(batal):
            break
        nilai = " ".join(f"wd:{q}" for q in qids[i:i + per_kueri])
        kueri = (f"SELECT ?artikel ?doi ?tgl ?judul WHERE {{ VALUES ?artikel {{ {nilai} }} "
                 "OPTIONAL { ?artikel wdt:P356 ?doi } OPTIONAL { ?artikel wdt:P577 ?tgl } "
                 "OPTIONAL { ?artikel wdt:P1476 ?judul } }")
        bindings, jejak = sumber_data.sparql(ENDPOINT_ILMIAH, kueri, batas=60, lisensi="CC0 1.0",
                                             sumber="Wikidata (graf artikel ilmiah)")
        for b in bindings:
            q = b.get("artikel", {}).get("value", "").rsplit("/", 1)[-1]
            r = peta.setdefault(q, {})
            if "doi" in b:
                r["doi"] = b["doi"]["value"].lower()
            if "tgl" in b and b["tgl"]["value"][:4].isdigit():
                r["tahun"] = max(r.get("tahun", 0), int(b["tgl"]["value"][:4]))
            if "judul" in b:
                r["judul"] = b["judul"]["value"]
    return peta, jejak


def gabung_rincian(daftar: list[dict], peta: dict) -> list[dict]:
    """Isi rujukan (DOI, atau 'Wikidata Qxx' bila tanpa DOI) dan tahun terbaru dari peta rincian_artikel."""
    for d in daftar:
        ruj, tahun = [], [d["tahun"]] if d.get("tahun") else []
        for q in d.get("artikel", []):
            r = peta.get(q, {})
            ruj.append(r.get("doi") or f"Wikidata {q}")
            if r.get("tahun"):
                tahun.append(r["tahun"])
        if ruj:
            d["rujukan"] = list(dict.fromkeys(ruj))
        d["tahun"] = max(tahun) if tahun else None
    return daftar


def senyawa_coconut_organisme(nama_ilmiah: str, batas: int = 5000) -> list[dict]:
    """Cari senyawa di COCONUT lokal jika database tersedia."""
    hasil_mentah = pustaka.cari_coconut_organisme(nama_ilmiah, batas=batas)
    daftar = []
    for r in hasil_mentah:
        smi = r.get("smiles", "")
        if not smi:
            continue
        daftar.append({
            "qid": r.get("id", ""),
            "nama": r.get("nama") or r.get("id", ""),
            "smiles": smi,
            "inchikey": "",  # Akan dihitung di standarisasi
            "rujukan": [r.get("id", "")],
            "tahun": None,
            "asal": "COCONUT",
            "coconut_data": r,
        })
    return daftar


def gabung_senyawa(daftar_lotus: list[dict], daftar_coconut: list[dict]) -> list[dict]:
    """Gabungkan senyawa LOTUS dan COCONUT menggunakan 14 karakter pertama InChIKey."""
    peta_14 = {}

    def get_kunci14(d):
        ik = d.get("inchikey", "")
        if len(ik) >= 14:
            return ik[:14]
        # Bila belum punya InChIKey, hitung dari SMILES
        try:
            m = Chem.MolFromSmiles(d.get("smiles", ""))
            if m:
                ik_hitung = Chem.MolToInchiKey(m)
                d["inchikey"] = ik_hitung
                return ik_hitung[:14]
        except Exception:
            pass
        return d.get("smiles", "")

    # Masukkan entri LOTUS
    for d in daftar_lotus:
        k = get_kunci14(d)
        peta_14[k] = dict(d)

    # Gabungkan entri COCONUT
    for d in daftar_coconut:
        k = get_kunci14(d)
        if k in peta_14:
            ada = peta_14[k]
            ada["asal"] = "keduanya"
            # Gabung rujukan tanpa duplikat
            semua_ruj = list(dict.fromkeys(ada.get("rujukan", []) + d.get("rujukan", [])))
            ada["rujukan"] = semua_ruj
            if not ada.get("nama") or ada["nama"].startswith("Q"):
                if d.get("nama") and not d["nama"].startswith("CNP"):
                    ada["nama"] = d["nama"]
        else:
            peta_14[k] = dict(d)

    return list(peta_14.values())


def standarisasi(daftar: list[dict]) -> list[dict]:
    """Standarisasi struktur kimia RDKit (fragmen terbesar, netralisasi) dan hitung sifat obat.

    Tidak membuang baris yang gagal, melainkan menandai kunci 'galat'.
    """
    chopper = rdMolStandardize.LargestFragmentChooser()
    uncharger = rdMolStandardize.Uncharger()

    hasil = []
    for d in daftar:
        entri = dict(d)
        smi = entri.get("smiles", "")
        mol = None
        try:
            mol = Chem.MolFromSmiles(smi)
            if mol is None:
                raise ValueError("SMILES tidak dapat diurai oleh RDKit")

            # 1. Fragmen terbesar (buang garam/air/pelarut)
            mol_terbesar = chopper.choose(mol)

            # 2. Netralisasi muatan parsial berlebih jika memungkinkan
            mol_netral = uncharger.uncharge(mol_terbesar)

            # Pertahankan representasi SMILES kanonik bersih
            smiles_std = Chem.MolToSmiles(mol_netral, isomericSmiles=True)
            entri["smiles_std"] = smiles_std
            entri["inchikey"] = Chem.MolToInchiKey(mol_netral)

            # Periksa stereokimia lengkap (apakah ada pusat kiral yang belum ditentukan)
            pusat_kiral = Chem.FindMolChiralCenters(mol_netral, includeUnassigned=True)
            ada_tak_terdefinisi = any(ch[1] == "?" for ch in pusat_kiral)
            entri["stereo_lengkap"] = (len(pusat_kiral) == 0) or (not ada_tak_terdefinisi)
            entri["jumlah_stereo"] = len(pusat_kiral)

            # 3. Hitung sifat fisikokimia & kemiripan obat
            sifat_data = sifat.hitung(mol_netral)
            entri["sifat"] = sifat_data
            entri["mw"] = sifat_data.get("mw", 0.0)
            entri["logp"] = sifat_data.get("wlogp", 0.0)
            entri["tpsa"] = sifat_data.get("tpsa", 0.0)
            entri["qed"] = sifat_data.get("qed", 0.0)
            entri["sascore"] = sifat_data.get("sascore", 0.0)
            entri["lipinski"] = sifat_data.get("lipinski", 0)
            entri["pains"] = sifat_data.get("pains", 0)
            entri["galat"] = None

        except Exception as e:
            entri["galat"] = str(e)
            entri["smiles_std"] = smi
            entri["sifat"] = None
            entri["stereo_lengkap"] = False
            entri["mw"] = 0.0
            entri["qed"] = 0.0
            entri["lipinski"] = 0

        hasil.append(entri)

    return hasil
