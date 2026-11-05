"""Comparative Toxicogenomics Database (CTD) — interaksi senyawa–gen yang dikurasi dari literatur.

Berbeda dengan prediksi berbasis kemiripan struktur (lihat core.target_balik), CTD berisi hubungan
senyawa–gen yang dibaca dan dikurasi kurator dari publikasi toksikologi dan biomedis. Keduanya saling
melengkapi: kemiripan memberi target yang *mungkin* terikat, CTD memberi target yang *pernah dilaporkan*.

Dipakai lewat Batch Query (http://ctdbase.org/tools/batchQuery.go) dengan laporan `genes_curated`.
Hasilnya TSV. Kolom dibaca berdasarkan nama di baris kepala, bukan posisi, supaya perubahan skema di
sisi CTD tidak langsung mematahkan modul ini.

Lisensi & etika pemakaian: data CTD gratis untuk penelitian akademik dengan kewajiban sitasi; tidak
boleh diunduh massal untuk didistribusikan ulang. Karena itu jumlah istilah per permintaan dibatasi
(MAKS_ISTILAH) dan hasilnya hanya disimpan di cache lokal pengguna.

Sitasi wajib: Davis AP, dkk. Comparative Toxicogenomics Database (CTD): update 2025. Nucleic Acids Res.
"""
import csv
import io
from typing import Any, Dict, List, Sequence

from . import sumber_data

API_BATCH = "https://ctdbase.org/tools/batchQuery.go"
MAKS_ISTILAH = 200          # jauh di bawah batas CTD (4000) — menjaga permintaan tetap kecil dan sopan
SPESIES_MANUSIA = "9606"
LISENSI = "CTD — gratis untuk penelitian akademik, wajib sitasi"


class GalatCtd(Exception):
    """Galat yang harus sampai ke pengguna (jaringan mati, CTD menolak kueri). Tidak ada data pengganti."""


def _jejak(j) -> Dict[str, Any]:
    return j.to_dict() if hasattr(j, "to_dict") else dict(j)


def _kolom(baris: Dict[str, str], *nama: str) -> str:
    """Ambil nilai kolom pertama yang ada (nama kolom CTD pernah berubah antarversi)."""
    for n in nama:
        for k, v in baris.items():
            if (k or "").strip().lstrip("#").strip().lower() == n.lower():
                return (v or "").strip()
    return ""


def urai_tsv(teks: str, spesies: str = SPESIES_MANUSIA) -> List[Dict[str, Any]]:
    """Urai TSV Batch Query CTD menjadi [{senyawa, mesh, gen, gen_id, organisme, aksi, pubmed, n_pubmed}].

    Baris komentar CTD diawali '#'; baris kepala adalah baris '#' terakhir sebelum data.
    Bila `spesies` diisi, hanya baris dengan Organism ID itu yang dikembalikan.
    """
    baris_teks = [b for b in teks.splitlines() if b.strip()]
    kepala, mulai = None, 0
    for i, b in enumerate(baris_teks):
        if b.startswith("#"):
            calon = [x.strip().lstrip("#").strip() for x in b.lstrip("#").split("\t")]
            if len(calon) >= 3:
                kepala, mulai = calon, i + 1
        elif kepala is not None:
            break
    if not kepala:
        # Sebagian laporan CTD tidak memakai '#'; anggap baris pertama sebagai kepala.
        kepala, mulai = [x.strip() for x in baris_teks[0].split("\t")], 1

    hasil = []
    for b in baris_teks[mulai:]:
        if b.startswith("#"):
            continue
        nilai = b.split("\t")
        if len(nilai) < 2:
            continue
        baris = dict(zip(kepala, nilai))
        org = _kolom(baris, "Organism ID", "OrganismID")
        if spesies and org and org != spesies:
            continue
        gen = _kolom(baris, "Gene Symbol", "GeneSymbol").upper()
        if not gen:
            continue
        pubmed = [p for p in _kolom(baris, "PubMed IDs", "PubMedIDs", "Reference Count").replace(",", "|").split("|") if p.strip()]
        hasil.append({
            "senyawa": _kolom(baris, "Input", "ChemicalName", "Chemical Name"),
            "mesh": _kolom(baris, "ChemicalID", "Chemical ID"),
            "gen": gen,
            "gen_id": _kolom(baris, "GeneID", "Gene ID"),
            "organisme": _kolom(baris, "Organism", "OrganismName") or "Homo sapiens",
            "aksi": _kolom(baris, "Interaction Actions", "InteractionActions"),
            "pubmed": pubmed,
            "n_pubmed": len(pubmed),
        })
    return hasil


def interaksi_senyawa(nama: Sequence[str], spesies: str = SPESIES_MANUSIA,
                      min_pubmed: int = 1, lapor=None) -> tuple:
    """Interaksi senyawa–gen terkurasi dari CTD. Kembalikan ([baris], [jejak]).

    nama: nama senyawa (CTD mencari berdasarkan nama/sinonim, bukan SMILES).
    min_pubmed: buang baris yang jumlah rujukan PubMed-nya di bawah ini (0 = jangan saring).
    """
    istilah = [n.strip() for n in dict.fromkeys(nama) if n and n.strip()]
    if not istilah:
        return [], []
    if len(istilah) > MAKS_ISTILAH:
        raise GalatCtd(f"Terlalu banyak senyawa untuk satu permintaan CTD ({len(istilah)}). "
                       f"Batas modul ini {MAKS_ISTILAH}; pecah daftarnya menjadi beberapa bagian.")
    if lapor is not None:
        lapor.log.emit(f"CTD: meminta interaksi terkurasi untuk {len(istilah)} senyawa…")

    params = {
        "inputType": "chem",
        "inputTerms": "|".join(istilah),
        "report": "genes_curated",
        "format": "tsv",
        "inputTermSearchType": "directAssociations",
        "action": "Download",
    }
    try:
        teks, j = sumber_data.ambil_teks(API_BATCH, params=params, cache_jam=168.0,
                                         lisensi=LISENSI, sumber="CTD (Comparative Toxicogenomics Database)",
                                         batas=120)
    except Exception as e:
        raise GalatCtd(f"Gagal mengakses CTD: {e}")
    if "<html" in teks[:400].lower():
        raise GalatCtd("CTD mengembalikan halaman web, bukan TSV — kemungkinan kueri ditolak atau "
                       "layanan sedang sibuk. Coba lagi beberapa saat kemudian.")

    baris = urai_tsv(teks, spesies=spesies)
    if min_pubmed > 0:
        baris = [b for b in baris if b["n_pubmed"] >= min_pubmed or not b["pubmed"]]
    if lapor is not None:
        lapor.log.emit(f"CTD: {len(baris)} interaksi senyawa–gen diterima.")
    return baris, [_jejak(j)]


def per_senyawa(baris: Sequence[Dict[str, Any]]) -> Dict[str, List[str]]:
    """{nama_senyawa: [gen, ...]} terurut jumlah rujukan PubMed menurun."""
    kumpul: Dict[str, Dict[str, int]] = {}
    for b in baris:
        s = b.get("senyawa") or ""
        kumpul.setdefault(s, {})
        g = b["gen"]
        kumpul[s][g] = max(kumpul[s].get(g, 0), int(b.get("n_pubmed") or 0))
    return {s: [g for g, _ in sorted(d.items(), key=lambda x: (-x[1], x[0]))] for s, d in kumpul.items()}


def gen_unik(baris: Sequence[Dict[str, Any]]) -> List[str]:
    """Daftar simbol gen unik, terurut abjad."""
    return sorted({b["gen"] for b in baris if b.get("gen")})


def baca_unduhan(path) -> List[Dict[str, Any]]:
    """Baca berkas TSV/CSV yang diunduh pengguna sendiri dari laman CTD.

    Dipakai bila pengguna lebih suka memakai antarmuka CTD langsung, atau bila kueri daringnya gagal.
    """
    from pathlib import Path
    teks = Path(path).read_text(encoding="utf-8", errors="replace")
    if "\t" in teks.splitlines()[0] if teks.splitlines() else False:
        return urai_tsv(teks)
    # Varian CSV: ubah ke TSV sederhana lalu pakai pengurai yang sama.
    pembaca = csv.reader(io.StringIO(teks))
    return urai_tsv("\n".join("\t".join(r) for r in pembaca))
