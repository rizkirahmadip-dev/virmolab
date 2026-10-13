"""Jaringan farmakologi berlapis untuk F3b: senyawa - target - jalur - penyakit.

Sumber daring (lewat core.sumber_data sehingga jejak dan cache tercatat):
- STRING API (CC BY 4.0) untuk tepi target-target; skor API 0-1000 dinormalisasi ke 0-1.
- Open Targets Platform GraphQL (CC BY 4.0 / CC0 per sumber) untuk tepi target-penyakit.
Jalur berasal dari pengayaan GMT bawaan (core.pengayaan), bukan dari internet.

Jaringan ini adalah ringkasan hipotesis; tepi STRING memuat bukti teks dan ko-ekspresi, bukan hanya interaksi fisik.
"""
import json
from typing import Any, Dict, Iterable, List, Optional, Sequence

import networkx as nx

from . import pengayaan, sumber_data

API_STRING = "https://string-db.org/api"
API_OPENTARGETS = "https://api.platform.opentargets.org/api/v4/graphql"
SPESIES_STRING = 9606          # Homo sapiens
AMBANG_STRING = 0.7
AMBANG_PENYAKIT = 0.5


class GalatJaringan(Exception):
    """Galat yang harus sampai ke pengguna (jaringan mati, gen tak dikenal); tidak ada data pengganti."""


def _jejak(j) -> Dict[str, Any]:
    return j.to_dict() if hasattr(j, "to_dict") else dict(j)


def tepi_string(gen: Sequence[str], ambang: float = AMBANG_STRING, spesies: int = SPESIES_STRING) -> tuple:
    """Tepi protein-protein STRING antar gen yang diberikan. Kembalikan ([(a, b, skor)], jejak).

    ambang: skor gabungan STRING 0-1 (0,4 rendah; 0,7 tinggi; 0,9 sangat tinggi).
    """
    gen = [g for g in dict.fromkeys(g.upper() for g in gen if g)]
    if len(gen) < 2:
        return [], []
    url = f"{API_STRING}/json/network"
    params = {"identifiers": "\r".join(gen), "species": spesies,
              "required_score": int(round(ambang * 1000)), "caller_identity": "virmolab"}
    try:
        d, j = sumber_data.ambil_json(url, params=params, cache_jam=168.0, lisensi="CC BY 4.0", sumber="STRING")
    except Exception as e:
        raise GalatJaringan(f"Gagal mengakses STRING: {e}")
    tepi = {}
    sah = set(gen)
    for r in d if isinstance(d, list) else []:
        a, b = (r.get("preferredName_A") or "").upper(), (r.get("preferredName_B") or "").upper()
        skor = float(r.get("score") or 0)
        if a in sah and b in sah and a != b and skor >= ambang:
            tepi[tuple(sorted((a, b)))] = max(skor, tepi.get(tuple(sorted((a, b))), 0))
    return [(a, b, s) for (a, b), s in sorted(tepi.items())], [_jejak(j)]


def versi_string() -> tuple:
    """Versi basis data STRING yang dilayani API saat ini."""
    try:
        d, j = sumber_data.ambil_json(f"{API_STRING}/json/version", params={"caller_identity": "virmolab"},
                                      cache_jam=168.0, lisensi="CC BY 4.0", sumber="STRING")
    except Exception as e:
        raise GalatJaringan(f"Gagal mengakses STRING: {e}")
    v = (d[0] if isinstance(d, list) and d else {}).get("string_version", "")
    return f"v{v}" if v else "", _jejak(j)


def _ot(kueri: str, variabel: Dict[str, Any]) -> tuple:
    try:
        d, j = sumber_data.ambil_json(API_OPENTARGETS, data=json.dumps({"query": kueri, "variables": variabel}),
                                      headers={"Content-Type": "application/json"}, cache_jam=168.0,
                                      lisensi="CC BY 4.0", sumber="Open Targets Platform")
    except Exception as e:
        raise GalatJaringan(f"Gagal mengakses Open Targets: {e}")
    if d.get("errors"):
        raise GalatJaringan(f"Open Targets menolak kueri: {d['errors'][0].get('message', '')[:160]}")
    return d.get("data") or {}, _jejak(j)


def versi_opentargets() -> tuple:
    d, j = _ot("{ meta { apiVersion { x y z } dataVersion { year month } } }", {})
    m = d.get("meta") or {}
    a, v = m.get("apiVersion") or {}, m.get("dataVersion") or {}
    return f"API {a.get('x')}.{a.get('y')}.{a.get('z')}, data 20{v.get('year')}.{v.get('month')}", j


def tepi_penyakit(gen: Sequence[str], ambang: float = AMBANG_PENYAKIT, maks_per_target: int = 10) -> tuple:
    """Asosiasi target-penyakit Open Targets dengan skor >= ambang. Kembalikan ([(gen, id, nama, skor)], jejak)."""
    hasil, jejak = [], []
    q_cari = """query($s:String!){ search(queryString:$s, entityNames:["target"]){ hits { id name } } }"""
    q_assoc = """query($e:String!,$n:Int!){ target(ensemblId:$e){ approvedSymbol
        associatedDiseases(page:{index:0,size:$n}){ rows { score disease { id name } } } } }"""
    for g in dict.fromkeys(x.upper() for x in gen if x):
        d, j = _ot(q_cari, {"s": g})
        jejak.append(j)
        hit = next((h for h in ((d.get("search") or {}).get("hits") or []) if (h.get("name") or "").upper() == g), None)
        if not hit:
            continue
        d2, j2 = _ot(q_assoc, {"e": hit["id"], "n": maks_per_target})
        jejak.append(j2)
        for r in (((d2.get("target") or {}).get("associatedDiseases") or {}).get("rows") or []):
            if float(r.get("score") or 0) >= ambang:
                hasil.append((g, r["disease"]["id"], r["disease"]["name"], float(r["score"])))
    return hasil, jejak


def bangun(senyawa: Dict[str, Sequence[str]], jalur: Optional[List[Dict]] = None,
           tepi_ppi: Sequence = (), penyakit: Sequence = (), maks_jalur: int = 15) -> nx.Graph:
    """Rakit graf berlapis dari bagian yang sudah dihitung (tanpa akses internet di sini).

    senyawa: {nama_senyawa: [gen target, ...]}  (hasil penargetan balik)
    jalur: keluaran pengayaan.hipergeometrik (diambil maks_jalur teratas menurut q)
    tepi_ppi: [(gen_a, gen_b, skor)] dari tepi_string
    penyakit: [(gen, id, nama, skor)] dari tepi_penyakit
    Atribut simpul: jenis (senyawa|target|jalur|penyakit), label, dan atribut spesifik lapisan.
    """
    G = nx.Graph()
    for nama, target in senyawa.items():
        G.add_node(f"S:{nama}", jenis="senyawa", label=nama)
        for g in target:
            g = g.upper()
            G.add_node(f"T:{g}", jenis="target", label=g)
            G.add_edge(f"S:{nama}", f"T:{g}", jenis="senyawa-target")
    for a, b, s in tepi_ppi:
        if f"T:{a}" in G and f"T:{b}" in G:
            G.add_edge(f"T:{a}", f"T:{b}", jenis="target-target", skor=round(float(s), 3))
    for p in (jalur or [])[:maks_jalur]:
        pid = f"J:{p['jalur']}"
        G.add_node(pid, jenis="jalur", label=p["nama"], q=float(p["q"]), n_overlap=int(p["n_overlap"]))
        for g in p["gen"]:
            if f"T:{g}" in G:
                G.add_edge(pid, f"T:{g}", jenis="target-jalur")
    for g, pid, nama, skor in penyakit:
        if f"T:{g.upper()}" not in G:
            continue
        nid = f"P:{pid}"
        G.add_node(nid, jenis="penyakit", label=nama)
        G.add_edge(f"T:{g.upper()}", nid, jenis="target-penyakit", skor=round(float(skor), 3))
    return G


def metrik(G: nx.Graph) -> List[Dict[str, Any]]:
    """Derajat, betweenness, dan closeness tiap simpul (terurut derajat menurun)."""
    if len(G) == 0:
        return []
    bc = nx.betweenness_centrality(G) if len(G) > 2 else {n: 0.0 for n in G}
    cc = nx.closeness_centrality(G)
    baris = [{"simpul": n, "jenis": d.get("jenis", ""), "label": d.get("label", n), "derajat": G.degree(n),
              "betweenness": round(bc.get(n, 0.0), 4), "closeness": round(cc.get(n, 0.0), 4)}
             for n, d in G.nodes(data=True)]
    baris.sort(key=lambda b: (-b["derajat"], -b["betweenness"]))
    return baris


def sensitivitas(senyawa: Dict[str, Sequence[str]], tepi_per_ambang: Dict[float, Sequence],
                 ambang_target: Iterable[int] = (5, 10, 20), bagian_inti: float = 0.2,
                 batas_stabil: float = 0.8) -> Dict[str, Any]:
    """Ulangi pembangunan graf untuk tiap kombinasi (ambang STRING, jumlah target teratas) dan cari simpul inti stabil.

    tepi_per_ambang: {ambang_string: tepi_string(...)} — dihitung pemanggil supaya modul ini tidak mengakses internet.
    ambang_target: berapa banyak target teratas per senyawa yang dipakai (urutan daftar senyawa dianggap peringkat).
    Simpul inti satu kombinasi = simpul target dengan derajat di bagian_inti teratas (minimal 1).
    Stabil = muncul pada >= batas_stabil bagian kombinasi.
    """
    hitung: Dict[str, int] = {}
    kombinasi = 0
    for ambang, tepi in sorted(tepi_per_ambang.items()):
        for n_target in ambang_target:
            sub = {s: list(t)[:n_target] for s, t in senyawa.items()}
            sah = {g.upper() for t in sub.values() for g in t}
            G = bangun(sub, tepi_ppi=[e for e in tepi if e[0] in sah and e[1] in sah])
            target = [b for b in metrik(G) if b["jenis"] == "target"]
            if not target:
                continue
            kombinasi += 1
            n_inti = max(1, int(round(len(target) * bagian_inti)))
            for b in target[:n_inti]:
                hitung[b["label"]] = hitung.get(b["label"], 0) + 1
    daftar = [{"gen": g, "muncul": n, "kombinasi": kombinasi, "persen": round(100 * n / kombinasi, 1)}
              for g, n in sorted(hitung.items(), key=lambda x: (-x[1], x[0]))] if kombinasi else []
    return {"kombinasi": kombinasi, "simpul": daftar,
            "inti_stabil": [d["gen"] for d in daftar if d["persen"] >= batas_stabil * 100]}


def _koma(x) -> str:
    """Angka dengan pemisah desimal koma (Bahasa Indonesia baku)."""
    return f"{x:g}".replace(".", ",")


def susun_paragraf_metode(sumber_gen: str, n_gen: int, nama_gmt: str, hasil_pengayaan: Sequence[Dict],
                          ambang_string: float, n_ppi: int, ambang_penyakit: Optional[float], n_penyakit: int,
                          sens: Optional[Dict] = None, versi_ot: str = "", versi_string: str = "") -> str:
    """Paragraf metode dari angka nyata. Bagian yang tidak dijalankan tidak disebut."""
    v = pengayaan.versi_gmt().get(pengayaan.GMT_BAWAAN.get(nama_gmt, ""), {})
    sig = [b for b in hasil_pengayaan if b["q"] < 0.05]
    if not n_gen:
        return ""
    bagian = [f"Jaringan farmakologi dirakit dari {n_gen} target {sumber_gen}."]
    if hasil_pengayaan:
        latar = hasil_pengayaan[0]["n_latar"]
        bagian.append(
            f"Pengayaan jalur memakai {v.get('sumber', nama_gmt)} ({v.get('versi', 'versi tak tercatat')}; {v.get('n_set', '?')} set gen) "
            f"dengan uji hipergeometrik satu sisi terhadap latar {latar} gen beranotasi dan koreksi Benjamini-Hochberg; "
            f"{len(sig)} jalur memenuhi q < 0,05.")
    if n_ppi:
        bagian.append(f"Tepi protein-protein berasal dari STRING {versi_string or 'versi tak tercatat'} dengan skor gabungan "
                      f">= {_koma(ambang_string)} ({n_ppi} tepi).")
    if n_penyakit:
        bagian.append(f"Asosiasi target-penyakit berasal dari Open Targets Platform ({versi_ot or 'versi tak tercatat'}) "
                      f"dengan skor asosiasi >= {_koma(ambang_penyakit)} ({n_penyakit} tepi).")
    if sens and sens.get("kombinasi"):
        inti = ", ".join(sens["inti_stabil"]) or "tidak ada"
        bagian.append(f"Uji sensitivitas atas {sens['kombinasi']} kombinasi ambang STRING dan jumlah target "
                      f"menghasilkan simpul inti stabil (muncul pada >= 80 % kombinasi): {inti}.")
    catatan = ("Jaringan ini merupakan hipotesis komputasi: tepi STRING mencakup bukti ko-ekspresi dan penambangan teks "
               "selain interaksi fisik, dan seluruh hubungan memerlukan validasi eksperimental.") if n_ppi else         "Jaringan ini merupakan hipotesis komputasi dan memerlukan validasi eksperimental."
    bagian.append(catatan)
    return " ".join(bagian)
