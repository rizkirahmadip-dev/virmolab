"""Energi bebas relatif alkimia (RBFE), F9, eksperimental.

Modul ini menyiapkan dan menganalisis perhitungan RBFE untuk seri senyawa kongenerik:

1. `pasangan_dari_mmp` memilih pasangan yang perubahannya cukup kecil untuk diperturbasi.
2. `peta_atom` memetakan atom antar pasangan lewat substruktur bersama maksimum (RDKit MCS).
3. `jaringan` menyusun graf perturbasi (bintang atau pohon rentang minimum).
4. `analisis_mbar` mengolah energi tereduksi tiap jendela lambda menjadi ΔG dengan pymbar.
5. `tutup_siklus` memeriksa konsistensi: jumlah ΔΔG mengelilingi siklus seharusnya nol.
6. `estimasi_waktu` memperkirakan lama perhitungan dari kecepatan mesin pengguna sendiri.

YANG TIDAK DILAKUKAN MODUL INI: menjalankan simulasi alkimianya. Modul ini hanya perencanaan dan analisis
(murni Python, tanpa Qt). Simulasinya dijalankan OpenFE, yang hanya berjalan di Linux dan macOS, jadi
VirmoLab memanggilnya lewat WSL: lihat `core/rbfe_openfe.py` (penyiapan run, eksekusi, pembacaan hasil,
paragraf metode dari hasil nyata). `status_mesin()` di bawah hanya menjawab apakah paket OpenFE ada di
lingkungan Python Windows ini, dan itu hampir selalu tidak; status yang dipakai dialog adalah
`rbfe_openfe.status()` (OpenFE di WSL). Jaringan yang disusun di sini juga dapat diekspor dan dijalankan
di mesin Linux lain, lalu keluarannya dibawa kembali untuk dianalisis.

Seluruh fitur ini berlabel eksperimental.
"""
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from . import catat

LABEL_EKSPERIMENTAL = (
    "Eksperimental. RBFE menuntut simulasi panjang di GPU dan protokol yang disetel hati-hati; "
    "hasilnya hanya bermakna untuk seri senyawa kongenerik dengan perubahan kecil."
)
LABEL_EKSPERIMENTAL_EN = (
    "Experimental. RBFE requires long GPU simulations and a carefully tuned protocol; "
    "the results are meaningful only for congeneric series with small changes."
)

MAKS_ATOM_BERUBAH = 10      # batas perubahan per perturbasi, sesuai rencana F9
K_BOLTZMANN_KKAL = 0.0019872041      # kkal/(mol K)


@dataclass
class Perturbasi:
    """Satu tepi jaringan: perubahan dari senyawa a ke senyawa b."""

    a: str
    b: str
    n_berubah: int = 0
    skor: float = 0.0                       # makin kecil makin mudah diperturbasi
    peta: Dict[int, int] = field(default_factory=dict)
    ddg: Optional[float] = None
    galat: Optional[float] = None
    pesan: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"a": self.a, "b": self.b, "n_berubah": self.n_berubah, "skor": round(self.skor, 3),
                "ddg": self.ddg, "galat": self.galat, "pesan": self.pesan}


def status_mesin() -> Dict[str, Any]:
    """Apakah mesin simulasi RBFE tersedia di komputer ini.

    OpenFE hanya mendukung linux-64 dan osx-arm64 menurut dokumentasi resminya, jadi di Windows
    jawabannya selalu tidak. Dikembalikan apa adanya, bukan disembunyikan.
    """
    import platform as plat

    sistem = plat.system()
    try:
        import importlib.util
        ada_openfe = importlib.util.find_spec("openfe") is not None
    except Exception:
        ada_openfe = False

    if ada_openfe:
        return {"ada": True, "sistem": sistem,
                "pesan": "OpenFE terdeteksi di lingkungan Python ini."}
    if sistem == "Windows":
        return {"ada": False, "sistem": sistem,
                "pesan": "Simulasi RBFE tidak dapat dijalankan di Windows: OpenFE hanya mendukung "
                         "Linux dan macOS. VirmoLab tetap dapat menyusun jaringan perturbasi dan "
                         "menganalisis hasil yang dihitung di mesin Linux."}
    return {"ada": False, "sistem": sistem,
            "pesan": "OpenFE belum terpasang di lingkungan ini. Pasang lewat conda-forge, lalu "
                     "jalankan ulang VirmoLab."}


def _mol(x):
    from rdkit import Chem

    if x is None:
        return None
    if isinstance(x, str):
        return Chem.MolFromSmiles(x)
    return x


def peta_atom(a, b, waktu_maks: int = 10) -> Dict[str, Any]:
    """Pemetaan atom dua molekul lewat substruktur bersama maksimum.

    Kembalikan {"peta", "n_bersama", "n_berubah", "mcs_smarts", "pesan"}. `peta` memetakan indeks
    atom molekul a ke indeks atom molekul b. `n_berubah` adalah jumlah atom berat yang tidak
    terpetakan di kedua sisi, yaitu ukuran perturbasinya.
    """
    from rdkit import Chem
    from rdkit.Chem import rdFMCS

    ma, mb = _mol(a), _mol(b)
    kosong = {"peta": {}, "n_bersama": 0, "n_berubah": 0, "mcs_smarts": "", "pesan": ""}
    if ma is None or mb is None:
        kosong["pesan"] = "Salah satu struktur tidak dapat diurai."
        return kosong

    hasil = rdFMCS.FindMCS([ma, mb], timeout=waktu_maks,
                           atomCompare=rdFMCS.AtomCompare.CompareElements,
                           bondCompare=rdFMCS.BondCompare.CompareOrder,
                           ringMatchesRingOnly=True, completeRingsOnly=True)
    if hasil.canceled or not hasil.smartsString:
        kosong["pesan"] = "Substruktur bersama tidak ditemukan dalam batas waktu."
        return kosong

    pola = Chem.MolFromSmarts(hasil.smartsString)
    cocok_a = ma.GetSubstructMatch(pola)
    cocok_b = mb.GetSubstructMatch(pola)
    if not cocok_a or not cocok_b:
        kosong["pesan"] = "Substruktur bersama tidak dapat dicocokkan ke kedua molekul."
        return kosong

    peta = {ia: ib for ia, ib in zip(cocok_a, cocok_b)}
    berat_a = ma.GetNumHeavyAtoms()
    berat_b = mb.GetNumHeavyAtoms()
    n_bersama = len(peta)
    return {"peta": peta, "n_bersama": n_bersama,
            "n_berubah": (berat_a - n_bersama) + (berat_b - n_bersama),
            "mcs_smarts": hasil.smartsString, "pesan": ""}


def pasangan_dari_mmp(seri: Sequence, maks_berubah: int = MAKS_ATOM_BERUBAH) -> List[Perturbasi]:
    """Pasangan kandidat perturbasi dari seri senyawa, lewat `core/mmp.py`.

    seri: [(id, smiles_atau_mol), ...]. Pasangan dengan perubahan lebih besar daripada
    `maks_berubah` atom berat dikeluarkan beserta alasannya, karena perturbasi besar bukan hanya
    lambat tetapi juga tidak dapat dipercaya.
    """
    from . import mmp

    pasang = mmp.cari_pasangan(list(seri))
    keluar = []
    for p in pasang:
        pm = peta_atom(p["mol_a"], p["mol_b"])
        if not pm["peta"]:
            keluar.append(Perturbasi(a=p["id_a"], b=p["id_b"], pesan=pm["pesan"] or "pemetaan gagal"))
            continue
        pt = Perturbasi(a=p["id_a"], b=p["id_b"], n_berubah=pm["n_berubah"], peta=pm["peta"])
        # Skor kemudahan: makin banyak atom berubah makin sulit; dipakai memilih tepi jaringan
        pt.skor = float(pm["n_berubah"])
        if pm["n_berubah"] > maks_berubah:
            pt.pesan = f"perubahan {pm['n_berubah']} atom berat melebihi batas {maks_berubah}"
        keluar.append(pt)
    return keluar


def jaringan(perturbasi: Sequence[Perturbasi], mode: str = "mst",
             pusat: Optional[str] = None) -> Dict[str, Any]:
    """Susun jaringan perturbasi dari kandidat tepi.

    mode 'bintang' menghubungkan semua senyawa ke satu pusat (paling sedikit tepi, tanpa siklus
    untuk diperiksa). mode 'mst' memilih pohon rentang minimum atas skor kemudahan, lalu menambah
    tepi cadangan sehingga terbentuk siklus yang dapat dipakai memeriksa konsistensi.
    """
    layak = [p for p in perturbasi if p.peta and not p.pesan]
    # MMP dapat menghasilkan pasangan yang sama lebih dari sekali (potongan berbeda, pemetaan sama);
    # tepi ganda tidak menambah informasi, hanya menggandakan simulasi. Disimpan yang paling mudah.
    terbaik = {}
    for p in layak:
        k = frozenset((p.a, p.b))
        if k not in terbaik or p.skor < terbaik[k].skor:
            terbaik[k] = p
    layak = list(terbaik.values())
    simpul = sorted({x for p in layak for x in (p.a, p.b)})
    if not layak:
        return {"tepi": [], "simpul": simpul, "mode": mode, "pesan": "Tidak ada pasangan yang layak."}

    if mode == "bintang":
        if pusat is None:
            derajat = {s: sum(1 for p in layak if s in (p.a, p.b)) for s in simpul}
            pusat = max(derajat, key=lambda s: derajat[s])
        tepi = [p for p in layak if pusat in (p.a, p.b)]
        return {"tepi": tepi, "simpul": simpul, "mode": "bintang", "pusat": pusat, "pesan": ""}

    # Pohon rentang minimum (Kruskal) atas skor kemudahan
    induk = {s: s for s in simpul}

    def cari(x):
        while induk[x] != x:
            induk[x] = induk[induk[x]]
            x = induk[x]
        return x

    tepi, sisa = [], []
    for p in sorted(layak, key=lambda p: p.skor):
        ra, rb = cari(p.a), cari(p.b)
        if ra != rb:
            induk[ra] = rb
            tepi.append(p)
        else:
            sisa.append(p)

    # Tambah tepi termurah yang benar-benar menutup siklus baru (bukan pasangan yang sudah jadi tepi),
    # supaya konsistensi jaringan bisa diperiksa tanpa menggandakan simulasi.
    dipakai = {frozenset((p.a, p.b)) for p in tepi}
    tambahan = [p for p in sisa if frozenset((p.a, p.b)) not in dipakai]
    tepi += tambahan[:max(0, min(len(tambahan), max(1, len(simpul) // 3)))]
    n_komponen = len({cari(s) for s in simpul})
    pesan = "" if n_komponen == 1 else f"Jaringan terpecah menjadi {n_komponen} bagian yang tidak terhubung."
    return {"tepi": tepi, "simpul": simpul, "mode": "mst", "pesan": pesan}


def analisis_mbar(energi_tereduksi: np.ndarray, n_sampel: Sequence[int],
                  suhu: float = 298.15) -> Dict[str, Any]:
    """ΔG antara jendela lambda pertama dan terakhir dengan MBAR.

    energi_tereduksi: matriks (K, N) berisi energi tereduksi (tanpa satuan, u = beta * U) tiap
    sampel pada tiap jendela. n_sampel: jumlah sampel per jendela. Kembalikan ΔG dalam kkal/mol
    beserta galat bakunya; kegagalan mengembalikan None dan pesan, bukan angka.
    """
    try:
        from pymbar import MBAR
    except ImportError:
        return {"dg": None, "galat": None, "pesan": "pymbar tidak terpasang."}

    u = np.asarray(energi_tereduksi, dtype=float)
    n = np.asarray(n_sampel, dtype=int)
    if u.ndim != 2 or u.shape[0] != len(n) or u.shape[1] != n.sum():
        return {"dg": None, "galat": None,
                "pesan": f"Bentuk matriks {u.shape} tidak cocok dengan jumlah sampel {n.sum()}."}
    try:
        mbar = MBAR(u, n)
        hasil = mbar.compute_free_energy_differences()
    except Exception as e:
        catat.log.warning(f"MBAR gagal: {e}")
        return {"dg": None, "galat": None, "pesan": f"MBAR gagal: {e}"}

    kt = K_BOLTZMANN_KKAL * suhu
    dg = float(hasil["Delta_f"][0, -1]) * kt
    galat = float(hasil["dDelta_f"][0, -1]) * kt
    return {"dg": round(dg, 3), "galat": round(galat, 3), "pesan": "",
            "matriks_dg": hasil["Delta_f"] * kt}


def tutup_siklus(tepi: Sequence[Perturbasi], toleransi: float = 1.0) -> List[Dict[str, Any]]:
    """Periksa konsistensi: jumlah ΔΔG mengelilingi siklus tertutup seharusnya nol.

    Penyimpangan besar menandakan sampling yang belum memadai pada salah satu tepi. Hanya siklus
    yang seluruh tepinya sudah punya ΔΔG yang diperiksa.
    """
    siap = {(p.a, p.b): p for p in tepi if p.ddg is not None}
    simpul = sorted({x for p in siap.values() for x in (p.a, p.b)})

    def nilai(x, y):
        if (x, y) in siap:
            return siap[(x, y)].ddg
        if (y, x) in siap:
            return -siap[(y, x)].ddg
        return None

    keluar = []
    for a, b, c in combinations(simpul, 3):
        bagian = [nilai(a, b), nilai(b, c), nilai(c, a)]
        if any(v is None for v in bagian):
            continue
        jumlah = sum(bagian)
        keluar.append({"siklus": [a, b, c], "jumlah": round(jumlah, 3),
                       "konsisten": abs(jumlah) <= toleransi})
    return keluar


def estimasi_waktu(n_tepi: int, n_lambda: int = 11, n_replika: int = 3, ns_per_lambda: float = 5.0,
                   ns_per_hari: Optional[float] = None) -> Dict[str, Any]:
    """Perkiraan lama perhitungan. Tanpa kecepatan terukur, kembalikan None, bukan tebakan.

    ns_per_hari diukur dari mesin pengguna sendiri lewat `core/md.uji_kecepatan`.
    """
    total_ns = n_tepi * n_lambda * n_replika * ns_per_lambda
    if not ns_per_hari or ns_per_hari <= 0:
        return {"total_ns": total_ns, "jam": None, "hari": None,
                "pesan": "Kecepatan mesin belum diukur, jadi lama perhitungan belum dapat diperkirakan."}
    hari = total_ns / ns_per_hari
    return {"total_ns": total_ns, "jam": round(hari * 24, 1), "hari": round(hari, 2),
            "pesan": f"{total_ns:g} ns simulasi pada {ns_per_hari:g} ns/hari."}


def paragraf_metode(hasil_jaringan: Dict[str, Any], n_lambda: int = 11, n_replika: int = 3,
                    ns_per_lambda: float = 5.0) -> str:
    """Kalimat metode dari jaringan yang benar-benar tersusun; kosong bila belum ada tepi."""
    tepi = hasil_jaringan.get("tepi") or []
    if not tepi:
        return ""
    selesai = [t for t in tepi if t.ddg is not None]
    from .. import i18n
    if i18n.inggris():
        teks = (f"A relative free-energy perturbation network was built over "
                f"{len(hasil_jaringan.get('simpul') or [])} compounds and {len(tepi)} edges "
                f"({hasil_jaringan.get('mode', 'mst')} mode). Atom mapping for each pair used the RDKit maximum "
                "common substructure with element and bond-order matching, and only pairs changing up to "
                f"{MAKS_ATOM_BERUBAH} heavy atoms were used. Planned protocol: {n_lambda} lambda windows, "
                f"{n_replika} replicas, {ns_per_lambda:g} ns per window.")
        if selesai:
            teks += (f" {len(selesai)} edges were analysed with MBAR; consistency was checked via cycle closure in "
                     "the network.")
        return teks + " " + LABEL_EKSPERIMENTAL_EN
    teks = (f"Jaringan perturbasi energi bebas relatif disusun atas {len(hasil_jaringan.get('simpul') or [])} "
            f"senyawa dan {len(tepi)} tepi (mode {hasil_jaringan.get('mode', 'mst')}). Pemetaan atom tiap "
            "pasangan memakai substruktur bersama maksimum RDKit dengan pencocokan unsur dan orde ikatan, "
            f"dan hanya pasangan dengan perubahan sampai {MAKS_ATOM_BERUBAH} atom berat yang dipakai. "
            f"Protokol yang direncanakan: {n_lambda} jendela lambda, {n_replika} replika, "
            f"{ns_per_lambda:g} ns per jendela.")
    if selesai:
        teks += (f" {len(selesai)} tepi telah dianalisis dengan MBAR; konsistensi diperiksa lewat penutupan "
                 "siklus pada jaringan.")
    return teks + " " + LABEL_EKSPERIMENTAL
