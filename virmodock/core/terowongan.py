"""Saluran akses ligan: pemindaian sinar lurus dari pusat kantong ke pelarut.

Dari titik awal (pusat grid box / ligan aktif) dipancarkan 64 sinar (bola Fibonacci). Sepanjang tiap sinar dihitung
celah bebas = jarak ke permukaan van der Waals atom berat terdekat. Sinar yang mencapai pelarut (celah ≥ 6 Å, minimal
8 Å dari awal) tanpa celah < 0,2 Å dianggap saluran. Dilaporkan: jari-jari leher (bottleneck), jari-jari rerata,
panjang, residu leher (gatekeeper) dan residu dinding. Sinar keluar di mulut yang sama (< 5 Å) digabung.

Batasan: jalur lurus saja; lorong berkelok tidak terdeteksi. Untuk analisis definitif gunakan CAVER atau MOLE.
"""
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

R_VDW = {"C": 1.70, "N": 1.55, "O": 1.52, "S": 1.80, "P": 1.80, "F": 1.47, "CL": 1.75, "BR": 1.85, "I": 1.98,
         "SE": 1.90, "ZN": 1.39, "MG": 1.73, "FE": 1.80, "CA": 1.97, "MN": 1.73}
CELAH_PELARUT = 6.0     # Å: dianggap sudah di pelarut bebas
JARAK_MIN_KELUAR = 8.0  # Å: sinar harus menempuh minimal ini sebelum dianggap keluar
CELAH_TABRAK = 0.2      # Å: celah lebih kecil = sinar tertutup atom


def _teks(sumber: str) -> str:
    if "\n" in sumber:
        return sumber
    p = Path(sumber)
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def _ambil_atom_reseptor(sumber: str):
    """(xyz N×3, jari-jari N, label residu N) atom berat protein dari teks/berkas PDB(QT)."""
    xyz, rad, res = [], [], []
    for b in _teks(sumber).splitlines():
        if not b.startswith("ATOM  "):
            continue
        try:
            x, y, z = float(b[30:38]), float(b[38:46]), float(b[46:54])
        except ValueError:
            continue
        el = b[76:78].strip().upper() if len(b) >= 78 else ""
        if not el or not el.isalpha():
            el = b[12:16].strip()[:1].upper()
        if el in ("H", "D"):
            continue
        xyz.append((x, y, z))
        rad.append(R_VDW.get(el, 1.70))
        res.append(f"{b[17:20].strip()} {b[22:26].strip()} ({b[21:22].strip() or 'A'})")
    return np.asarray(xyz, float).reshape(-1, 3), np.asarray(rad, float), res


def _arah(n: int) -> np.ndarray:
    i = np.arange(n, dtype=float)
    y = 1.0 - 2.0 * i / (n - 1)
    r = np.sqrt(np.clip(1.0 - y * y, 0.0, 1.0))
    th = math.pi * (math.sqrt(5.0) - 1.0) * i
    return np.column_stack([np.cos(th) * r, y, np.sin(th) * r])


def _celah(titik: np.ndarray, xyz: np.ndarray, rad: np.ndarray):
    """Celah bebas (Å) dan indeks atom terdekat untuk tiap titik (M×3)."""
    d = np.sqrt(((titik[:, None, :] - xyz[None, :, :]) ** 2).sum(-1)) - rad[None, :]
    i = d.argmin(axis=1)
    return d[np.arange(len(titik)), i], i, d


def _awal_bebas(p0: np.ndarray, xyz, rad, maks=3.0, langkah=0.5):
    """Geser titik awal ke titik kisi terdekat (≤ maks Å) yang celahnya ≥ 1 Å."""
    c, _, _ = _celah(p0[None, :], xyz, rad)
    if c[0] >= 1.0:
        return p0
    g = np.arange(-maks, maks + 1e-6, langkah)
    kis = np.array(np.meshgrid(g, g, g, indexing="ij")).reshape(3, -1).T
    kis = kis[np.linalg.norm(kis, axis=1) <= maks]
    kis = kis[np.argsort(np.linalg.norm(kis, axis=1))] + p0
    c, _, _ = _celah(kis, xyz, rad)
    ok = np.where(c >= 1.0)[0]
    return kis[ok[0]] if len(ok) else p0


def cari_terowongan(
    jalur_reseptor: str,
    titik_awal: Optional[Tuple[float, float, float]] = None,
    radius_probe: float = 1.2,
    resolusi_grid: float = 1.0,
    maks_jarak: float = 30.0,
    n_arah: int = 64,
) -> List[Dict[str, Any]]:
    """Saluran lurus dari titik awal ke pelarut, urut leher terlebar.

    jalur_reseptor: berkas atau teks PDB/PDBQT reseptor. titik_awal: pusat kantong (bawaan: pusat atom, kurang
    bermakna; sebaiknya pusat grid box). radius_probe: jari-jari leher minimal yang masih dilaporkan (× 0,7).

    Tiap saluran: id, bottleneck_radius, avg_radius, panjang, gatekeeper, residu_dinding, jalur_titik, jalur_radius.
    """
    xyz, rad, res = _ambil_atom_reseptor(jalur_reseptor)
    if not len(xyz):
        return []
    p0 = np.asarray(titik_awal if titik_awal is not None else xyz.mean(axis=0), float)
    p0 = _awal_bebas(p0, xyz, rad)
    jarak = np.arange(0.0, maks_jarak + 1e-6, resolusi_grid)
    # atom yang mungkin tersentuh sinar mana pun (≤ maks_jarak + 6 Å dari awal) — memangkas hitungan
    dekat = np.linalg.norm(xyz - p0, axis=1) <= maks_jarak + CELAH_PELARUT + 2.0
    xyz_d, rad_d = xyz[dekat], rad[dekat]
    idx_asli = np.where(dekat)[0]
    hasil = []
    for d in _arah(n_arah):
        titik = p0 + jarak[:, None] * d
        celah, terdekat, semua = _celah(titik, xyz_d, rad_d)
        tabrak = np.where(celah < CELAH_TABRAK)[0]
        batas = tabrak[0] if len(tabrak) else len(titik)
        keluar = np.where((celah[:batas] >= CELAH_PELARUT) & (jarak[:batas] >= JARAK_MIN_KELUAR))[0]
        if not len(keluar):
            continue
        n = keluar[0] + 1
        r = celah[:n]
        if len(r) < 4 or r.min() < radius_probe * 0.7:
            continue
        i_min = int(r.argmin())
        leher = semua[i_min] <= r[i_min] + 1.2
        gate = sorted({res[idx_asli[k]] for k in np.where(leher)[0]})[:6]
        dinding = sorted({res[idx_asli[k]] for k in np.where((semua[:n] <= 4.0).any(axis=0))[0]})
        hasil.append({
            "bottleneck_radius": round(float(r.min()), 2),
            "avg_radius": round(float(r.mean()), 2),
            "panjang": round(float(jarak[n - 1]), 1),
            "gatekeeper": gate,
            "residu_dinding": dinding,
            "jalur_titik": [[round(float(v), 2) for v in t] for t in titik[:n]],
            "jalur_radius": [round(float(v), 2) for v in r],
        })
    hasil.sort(key=lambda t: (-t["bottleneck_radius"], t["panjang"]))
    unik = []
    for t in hasil:
        mulut = np.array(t["jalur_titik"][-1])
        if all(np.linalg.norm(mulut - np.array(u["jalur_titik"][-1])) >= 5.0 for u in unik):
            t["id"] = len(unik) + 1
            unik.append(t)
    return unik
