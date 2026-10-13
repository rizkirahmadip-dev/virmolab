"""Pengayaan jalur (over-representation analysis) untuk F3b.

Uji hipergeometrik satu sisi (P[X >= k]) per set gen terhadap latar yang dinyatakan eksplisit, lalu koreksi
Benjamini-Hochberg. Berkas GMT bawaan ada di virmolab/data/gmt/ (dirakit dev/buat_gmt.py; versi di versi.json).
"""
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from scipy.stats import hypergeom

DIR_GMT = Path(__file__).resolve().parent.parent / "data" / "gmt"
GMT_BAWAAN = {"reactome": "reactome_manusia.gmt", "go_bp": "go_bp_manusia.gmt"}


def baca_gmt(path) -> Dict[str, Dict]:
    """GMT -> {id: {"nama": str, "gen": set}}. Kolom: id, deskripsi, gen..."""
    hasil = {}
    for b in Path(path).read_text(encoding="utf-8").splitlines():
        k = b.split("\t")
        if len(k) >= 3:
            hasil[k[0]] = {"nama": k[1], "gen": {g.upper() for g in k[2:] if g}}
    return hasil


def gmt_bawaan(nama: str) -> Dict[str, Dict]:
    p = DIR_GMT / GMT_BAWAAN[nama]
    if not p.exists():
        raise FileNotFoundError(f"Berkas GMT '{nama}' tidak ada di paket ({p.name}).")
    return baca_gmt(p)


def versi_gmt() -> Dict[str, Dict]:
    p = DIR_GMT / "versi.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def benjamini_hochberg(p: List[float]) -> List[float]:
    """q-nilai BH (step-up), urutan sama dengan masukan."""
    n = len(p)
    if not n:
        return []
    urut = sorted(range(n), key=lambda i: p[i])
    q = [0.0] * n
    terkecil = 1.0
    for peringkat in range(n, 0, -1):
        i = urut[peringkat - 1]
        terkecil = min(terkecil, p[i] * n / peringkat)
        q[i] = terkecil
    return q


def hipergeometrik(gen: Iterable[str], set_gen: Dict[str, Dict], latar: Optional[Iterable[str]] = None,
                   min_overlap: int = 1) -> List[Dict]:
    """ORA: gen kueri vs tiap set. latar = semesta gen (bawaan: gabungan semua gen di GMT).

    Gen kueri dan set dipotong ke latar. p = P(X >= k), X ~ Hipergeometrik(N=|latar|, K=|set|, n=|kueri|).
    Hanya set dengan overlap >= min_overlap yang diuji (q dihitung atas set yang diuji; jumlahnya dilaporkan).
    Keluaran terurut p: [{jalur, nama, n_overlap, n_set, n_kueri, n_latar, p, q, gen}].
    """
    semesta = {g.upper() for g in latar} if latar is not None else set().union(*(s["gen"] for s in set_gen.values()))
    kueri = {g.upper() for g in gen} & semesta
    N, n = len(semesta), len(kueri)
    baris = []
    for sid, s in set_gen.items():
        anggota = s["gen"] & semesta
        hit = kueri & anggota
        if len(hit) < max(1, min_overlap):
            continue
        p = float(hypergeom.sf(len(hit) - 1, N, len(anggota), n))
        baris.append({"jalur": sid, "nama": s["nama"], "n_overlap": len(hit), "n_set": len(anggota), "n_kueri": n,
                      "n_latar": N, "p": p, "gen": sorted(hit)})
    for b, q in zip(baris, benjamini_hochberg([b["p"] for b in baris])):
        b["q"] = q
    baris.sort(key=lambda b: (b["p"], -b["n_overlap"]))
    return baris
