"""Deteksi kantong pengikatan otomatis (gaya LIGSITE).

Struktur dibungkus kisi 0,8 Å. Titik kisi di luar permukaan van der Waals diperiksa pada 13 sumbu (3 sumbu utama,
6 diagonal bidang, 4 diagonal ruang): sumbu yang terhalang protein di kedua arah dihitung sebagai satu kejadian
"protein–pelarut–protein" (PSP). Titik dengan PSP ≥ ambang berarti terkurung di cekungan, bukan di permukaan datar.
Titik demikian diklasterkan (konektivitas 26) menjadi kantong, lalu diperingkat menurut volume dan kedalaman.

Rujukan metode: Hendlich, Rippmann & Barnickel (1997), LIGSITE. Implementasi ini disederhanakan dan tidak
mengurutkan kantong dengan model druggability terlatih.
"""
from typing import Any, Dict, List

import numpy as np

from .ppi import _uraikan_pdb

ARAH = [(1, 0, 0), (0, 1, 0), (0, 0, 1),
        (1, 1, 0), (1, -1, 0), (1, 0, 1), (1, 0, -1), (0, 1, 1), (0, 1, -1),
        (1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1)]
ABAIKAN = {"HOH", "WAT", "DOD", "SO4", "PO4", "GOL", "EDO", "PEG", "MPD", "DMS", "ACT", "CL", "NA", "K", "IOD"}
PSP_MIN = 10         # dari 13 sumbu: makin tinggi makin dalam kantongnya
JANGKAU = 12.0       # Å, jarak maksimum pencarian dinding di satu arah
CELAH_MAKS = 5.0     # Å, jarak maksimum titik kantong dari permukaan protein


def _kisi_protein(pos, rad, spasi, pad):
    min_b = pos.min(0) - pad
    dim = np.ceil(((pos.max(0) + pad) - min_b) / spasi).astype(int) + 1
    isi = np.zeros(tuple(dim), dtype=bool)
    for p, r in zip(pos, rad):
        i0 = np.maximum(0, np.floor((p - r - min_b) / spasi).astype(int))
        i1 = np.minimum(dim, np.ceil((p + r - min_b) / spasi).astype(int) + 1)
        if (i1 <= i0).any():
            continue
        g = np.meshgrid(*[np.arange(a, b) * spasi + min_b[k] for k, (a, b) in enumerate(zip(i0, i1))], indexing="ij")
        d2 = sum((g[k] - p[k]) ** 2 for k in range(3))
        isi[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]] |= d2 <= r * r
    return isi, min_b


def _terhalang(isi, arah, langkah_maks):
    """Untuk tiap titik: True bila ada atom protein di sepanjang arah ini dalam langkah_maks langkah."""
    ketemu = np.zeros_like(isi)
    geser = isi
    for _ in range(langkah_maks):
        geser = _geser(geser, arah)
        ketemu |= geser
    return ketemu


def _geser(a, arah):
    """Geser kisi satu langkah ke arah tertentu; bagian yang keluar batas diisi False."""
    keluar = np.zeros_like(a)
    irisan_sumber, irisan_tujuan = [], []
    for d in arah:
        if d == 0:
            irisan_sumber.append(slice(None))
            irisan_tujuan.append(slice(None))
        elif d > 0:
            irisan_sumber.append(slice(1, None))
            irisan_tujuan.append(slice(0, -1))
        else:
            irisan_sumber.append(slice(0, -1))
            irisan_tujuan.append(slice(1, None))
    keluar[tuple(irisan_tujuan)] = a[tuple(irisan_sumber)]
    return keluar


def deteksi_kantong(pdb_teks: str, spasi_kisi: float = 0.8, min_volume: float = 80.0,
                    maks_kantong: int = 8, psp_min: int = PSP_MIN) -> List[Dict[str, Any]]:
    """Kantong pada struktur protein, urut volume.

    spasi_kisi: resolusi kisi (Å). min_volume: volume minimum kantong yang dilaporkan (Å³).
    psp_min: jumlah minimum sumbu terkurung dari 13 (makin besar = hanya rongga dalam).

    Tiap kantong: peringkat, pusat {x,y,z}, ukuran {x,y,z} (usulan grid box), volume, n_titik, kedalaman_psp,
    skor_druggability, residu_pelapis, jumlah_residu.
    """
    from scipy import ndimage
    atom = [a for a in _uraikan_pdb(pdb_teks) if a["resn"] not in ABAIKAN]
    if len(atom) < 10:
        return []
    pos = np.array([a["pos"] for a in atom], float)
    rad = np.array([a["r"] for a in atom], float)
    isi, min_b = _kisi_protein(pos, rad, spasi_kisi, pad=4.0)
    langkah = max(1, int(JANGKAU / spasi_kisi))
    psp = np.zeros(isi.shape, dtype=np.int8)
    for arah in ARAH:
        maju = _terhalang(isi, arah, langkah)
        mundur = _terhalang(isi, tuple(-d for d in arah), langkah)
        psp += (maju & mundur).astype(np.int8)
    # hanya lapisan dekat permukaan: titik berjarak probe..CELAH_MAKS dari dinding (bukan ruang pelarut terbuka)
    celah = ndimage.distance_transform_edt(~isi) * spasi_kisi
    rongga = (~isi) & (psp >= psp_min) & (celah >= 1.4) & (celah <= CELAH_MAKS)
    if not rongga.any():
        return []
    label, n = ndimage.label(rongga, structure=np.ones((3, 3, 3), bool))
    if not n:
        return []
    vol_titik = spasi_kisi ** 3
    hasil = []
    for idx in range(1, n + 1):
        titik = np.argwhere(label == idx)
        vol = len(titik) * vol_titik
        if vol < min_volume:
            continue
        xyz = titik * spasi_kisi + min_b
        pusat = xyz.mean(0)
        ukuran = np.maximum((xyz.max(0) - xyz.min(0)) + 8.0, 16.0)
        kedalaman = float(psp[label == idx].mean())
        # residu dinding: atom ≤ 5 Å dari titik kantong mana pun
        cuplik = xyz[:: max(1, len(xyz) // 300)]
        d = np.sqrt(((pos[:, None, :] - cuplik[None, :, :]) ** 2).sum(-1)).min(1)
        res = sorted({(atom[i]["rantai"], atom[i]["resi"], atom[i]["resn"]) for i in np.where(d <= 5.0)[0]},
                     key=lambda r: (r[0], r[1]))
        label_res = [f"{r[2]} {r[1]} ({r[0]})" for r in res]
        # skor gabungan: volume mendekati rentang obat kecil (200–900 Å³), kedalaman, jumlah residu dinding
        s_vol = min(1.0, vol / 400.0) if vol <= 900 else max(0.3, 1.0 - (vol - 900) / 2500.0)
        s_dalam = min(1.0, (kedalaman - psp_min + 1) / 4.0)
        s_res = min(1.0, len(label_res) / 20.0)
        hasil.append({
            "pusat": {"x": round(float(pusat[0]), 2), "y": round(float(pusat[1]), 2), "z": round(float(pusat[2]), 2)},
            "ukuran": {"x": round(float(ukuran[0]), 1), "y": round(float(ukuran[1]), 1),
                       "z": round(float(ukuran[2]), 1)},
            "volume": round(vol, 1),
            "n_titik": int(len(titik)),
            "kedalaman_psp": round(kedalaman, 1),
            "skor_druggability": round(0.45 * s_vol + 0.35 * s_dalam + 0.20 * s_res, 2),
            "residu_pelapis": label_res,
            "jumlah_residu": len(label_res),
        })
    if not hasil and psp_min > 8:   # struktur dangkal (mis. model AlphaFold): longgarkan satu tingkat
        return deteksi_kantong(pdb_teks, spasi_kisi, min_volume, maks_kantong, psp_min - 1)
    hasil.sort(key=lambda k: (-k["skor_druggability"], -k["volume"]))
    for i, k in enumerate(hasil[:maks_kantong]):
        k["peringkat"] = i + 1
    return hasil[:maks_kantong]
