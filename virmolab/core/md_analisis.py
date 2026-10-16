"""Analisis trajektori Dinamika Molekul (MD) lengkap (F2).

Menyediakan fungsi analisis struktur, dinamika, dan termodinamika menggunakan
NumPy, SciPy, dan RDKit (tanpa dependensi paket eksternal tambahan):
- Radius girasi (Rg)
- Luas permukaan terakses pelarut (SASA) via rdFreeSASA & Shrake-Rupley NumPy
- Ikatan hidrogen per frame
- Garis waktu interaksi (Barcode RLE)
- Jarak antar-atom/residu kunci
- Analisis Komponen Utama (PCA) Cα
- Lanskap energi bebas (FEL) 2D dari proyeksi PC1-PC2
- Pengelompokan konformasi ligan (hierarchical clustering & medoid)
- Analisis konvergensi rata-rata blok (block averaging)
"""
import math
from typing import Any

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.distance import pdist, squareform
from scipy.cluster.hierarchy import linkage, fcluster

from rdkit import Chem
try:
    from rdkit.Chem import rdFreeSASA
    ADA_FREESASA = True
except ImportError:
    ADA_FREESASA = False

from . import catat


# ------------------------------------------------------------------ RLE
def encode_rle(arr: np.ndarray) -> dict:
    """Run-Length Encoding untuk array numerik/biner (1D atau 2D)."""
    flat = np.asarray(arr, dtype=np.int8).ravel()
    bentuk = list(arr.shape)
    if len(flat) == 0:
        return {"awal": 0, "runs": [], "bentuk": bentuk}

    awal = int(flat[0])
    perubahan = np.diff(flat) != 0
    idx = np.where(perubahan)[0] + 1
    pos = np.concatenate([[0], idx, [len(flat)]])
    runs = np.diff(pos).tolist()
    return {"awal": awal, "runs": runs, "bentuk": bentuk}


def decode_rle(rle: dict) -> np.ndarray:
    """Decode Run-Length Encoding kembali ke ndarray asli."""
    awal = rle.get("awal", 0)
    runs = rle.get("runs", [])
    bentuk = tuple(rle.get("bentuk", [0]))
    if not runs:
        return np.zeros(bentuk, dtype=np.int8)

    nilai = awal
    bagian = []
    for panjang in runs:
        bagian.append(np.full(panjang, nilai, dtype=np.int8))
        nilai = 1 - nilai
    return np.concatenate(bagian).reshape(bentuk)


# ------------------------------------------------------------------ Radius Girasi (Rg)
def radius_girasi(frames: np.ndarray, massa: np.ndarray | None = None,
                  idx: list[int] | None = None,
                  ke_angstrom: float = 10.0) -> tuple[list[float], str | None]:
    """Hitung radius girasi (Rg) per frame dalam Ångström.

    frames: (N_frame, N_atom, 3) dalam nm (atau Å bila ke_angstrom=1.0).
    massa: bobot massa per atom (N_atom,). Bila None, diasumsikan seragam.
    idx: subset indeks atom (misal protein zat terlarut).
    """
    frames = np.asarray(frames, dtype=np.float64)
    if frames.ndim != 3 or len(frames) == 0:
        return [], "Data frame kosong."

    if idx is not None:
        frames = frames[:, idx]

    # Konversi koordinat ke Ångström bila data dalam nm
    if ke_angstrom != 1.0:
        frames = frames * ke_angstrom

    n_frames, n_atoms, _ = frames.shape
    if massa is None:
        m = np.ones(n_atoms, dtype=np.float64)
    else:
        m = np.asarray(massa, dtype=np.float64)
        if idx is not None:
            m = m[idx]

    m_tot = np.sum(m)
    if m_tot <= 0:
        m_tot = float(n_atoms)
        m = np.ones(n_atoms, dtype=np.float64)

    # Pusat massa per frame: (n_frames, 3)
    cm = np.sum(frames * m[np.newaxis, :, np.newaxis], axis=1) / m_tot
    diff = frames - cm[:, np.newaxis, :]
    d2 = np.sum(diff ** 2, axis=-1)
    rg = np.sqrt(np.sum(d2 * m[np.newaxis, :], axis=1) / m_tot)

    peringatan = None
    if n_frames < 20:
        peringatan = f"Jumlah frame ({n_frames}) sangat sedikit untuk analisis stabilitas Rg."

    return rg.tolist(), peringatan


# ------------------------------------------------------------------ SASA
def _fibonacci_sphere(samples: int = 96) -> np.ndarray:
    """Hasilkan titik terdistribusi merata pada permukaan bola unit."""
    phi = np.pi * (np.sqrt(5.0) - 1.0)
    idx = np.arange(samples)
    y = 1.0 - (idx / float(samples - 1)) * 2.0
    radius = np.sqrt(np.maximum(0.0, 1.0 - y * y))
    theta = phi * idx
    return np.column_stack([np.cos(theta) * radius, y, np.sin(theta) * radius])


def sasa_shrake_rupley_numpy(coords: np.ndarray, radii: np.ndarray,
                             probe: float = 1.4, n_sphere: int = 96,
                             n_titik: int | None = None) -> tuple[float, np.ndarray]:
    """Hitung SASA (Å²) dengan algoritma Shrake-Rupley tervektorisasi via cKDTree.

    coords: (N, 3) dalam Å.
    radii: (N,) jari-jari van der Waals dalam Å.
    """
    if n_titik is not None:
        n_sphere = n_titik
    n_atoms = len(coords)
    if n_atoms == 0:
        return 0.0, np.zeros(0, dtype=np.float64)

    sphere = _fibonacci_sphere(n_sphere)
    r_eff = radii + probe
    tree = cKDTree(coords)
    max_d = float(np.max(r_eff) * 2.0)
    tetangga_list = tree.query_ball_point(coords, r=max_d)

    area_total = 0.0
    area_per_atom = np.zeros(n_atoms, dtype=np.float64)

    for i in range(n_atoms):
        ri = coords[i]
        reff_i = r_eff[i]
        pts = ri + reff_i * sphere
        tetangga = [j for j in tetangga_list[i] if j != i]
        if not tetangga:
            bebas = n_sphere
        else:
            rj = coords[tetangga]
            reff_j = r_eff[tetangga]
            diff = pts[:, np.newaxis, :] - rj[np.newaxis, :, :]
            d2 = np.sum(diff ** 2, axis=-1)
            tertutup = np.any(d2 < (reff_j ** 2)[np.newaxis, :], axis=1)
            bebas = n_sphere - int(np.sum(tertutup))

        atom_area = 4.0 * np.pi * (reff_i ** 2) * (bebas / float(n_sphere))
        area_per_atom[i] = atom_area
        area_total += atom_area

    return float(area_total), area_per_atom


def hitung_sasa_frame(coords_angstrom: np.ndarray,
                      radii: np.ndarray,
                      idx_protein: list[int] | None = None,
                      idx_ligan: list[int] | None = None,
                      probe: float = 1.4,
                      mol_rdkit: Chem.Mol | None = None,
                      pakai_freesasa: bool = True) -> dict[str, float]:
    """Hitung SASA protein, ligan, kompleks, dan ΔSASA terkubur untuk 1 frame.

    ΔSASA terkubur = SASA(protein bebas) + SASA(ligan bebas) - SASA(kompleks).
    """
    if ADA_FREESASA and pakai_freesasa:
        try:
            rw = Chem.RWMol()
            for _ in range(len(coords_angstrom)):
                rw.AddAtom(Chem.Atom(6))
            m = rw.GetMol()
            conf = Chem.Conformer(len(coords_angstrom))
            for i, c in enumerate(coords_angstrom):
                conf.SetAtomPosition(i, (float(c[0]), float(c[1]), float(c[2])))
            m.AddConformer(conf)

            # Lee-Richards, bukan Shrake-Rupley: SR FreeSASA (RDKit 2026.03) bisa access violation setelah beberapa
            # panggilan beruntun pada sistem ribuan atom, dan crash di kode C itu menjatuhkan seluruh aplikasi.
            opts = rdFreeSASA.SASAOpts(rdFreeSASA.SASAAlgorithm.LeeRichards, rdFreeSASA.SASAClassifier.Protor)
            opts.probeRadius = probe
            rad_list = [float(r) for r in radii]
            sasa_kompleks = rdFreeSASA.CalcSASA(m, rad_list, -1, None, opts)

            # Bebas protein & bebas ligan bila ada pemisahan
            if idx_protein and idx_ligan:
                rw_p = Chem.RWMol()
                for _ in range(len(idx_protein)):
                    rw_p.AddAtom(Chem.Atom(6))
                m_p = rw_p.GetMol()
                conf_p = Chem.Conformer(len(idx_protein))
                for i_p, orig_i in enumerate(idx_protein):
                    conf_p.SetAtomPosition(i_p, (float(coords_angstrom[orig_i][0]),
                                                float(coords_angstrom[orig_i][1]),
                                                float(coords_angstrom[orig_i][2])))
                m_p.AddConformer(conf_p)
                rad_p = [float(radii[orig_i]) for orig_i in idx_protein]
                s_prot_bebas = rdFreeSASA.CalcSASA(m_p, rad_p, -1, None, opts)

                rw_l = Chem.RWMol()
                for _ in range(len(idx_ligan)):
                    rw_l.AddAtom(Chem.Atom(6))
                m_l = rw_l.GetMol()
                conf_l = Chem.Conformer(len(idx_ligan))
                for i_l, orig_i in enumerate(idx_ligan):
                    conf_l.SetAtomPosition(i_l, (float(coords_angstrom[orig_i][0]),
                                                float(coords_angstrom[orig_i][1]),
                                                float(coords_angstrom[orig_i][2])))
                m_l.AddConformer(conf_l)
                rad_l = [float(radii[orig_i]) for orig_i in idx_ligan]
                s_lig_bebas = rdFreeSASA.CalcSASA(m_l, rad_l, -1, None, opts)

                terkubur = max(0.0, s_prot_bebas + s_lig_bebas - sasa_kompleks)
            else:
                s_prot_bebas = sasa_kompleks
                s_lig_bebas = 0.0
                terkubur = 0.0

            return {
                "total": float(sasa_kompleks),
                "protein": float(s_prot_bebas),
                "ligan": float(s_lig_bebas),
                "terkubur": float(terkubur),
            }
        except Exception as e:
            catat.log.debug(f"rdFreeSASA gagal, beralih ke Shrake-Rupley NumPy: {e}")

    # Fallback murni NumPy Shrake-Rupley
    s_tot, s_atom = sasa_shrake_rupley_numpy(coords_angstrom, radii, probe=probe)
    if idx_protein and idx_ligan:
        s_prot_bebas, _ = sasa_shrake_rupley_numpy(coords_angstrom[idx_protein], radii[idx_protein], probe=probe)
        s_lig_bebas, _ = sasa_shrake_rupley_numpy(coords_angstrom[idx_ligan], radii[idx_ligan], probe=probe)
        terkubur = max(0.0, s_prot_bebas + s_lig_bebas - s_tot)
    else:
        s_prot_bebas = s_tot
        s_lig_bebas = 0.0
        terkubur = 0.0

    return {
        "total": float(s_tot),
        "protein": float(s_prot_bebas),
        "ligan": float(s_lig_bebas),
        "terkubur": float(terkubur),
    }



def sasa(frames: np.ndarray,
         radii: np.ndarray,
         idx_protein: list[int] | None = None,
         idx_ligan: list[int] | None = None,
         stride: int = 1,
         probe: float = 1.4,
         mol_rdkit: Chem.Mol | None = None,
         ke_angstrom: float = 10.0) -> dict[str, Any]:
    """Hitung runtutan waktu SASA di sepanjang lintasan MD."""
    frames = np.asarray(frames, dtype=np.float64)
    if ke_angstrom != 1.0:
        frames = frames * ke_angstrom

    n_sampel = len(frames[::stride])
    s_prot, s_lig, s_terkubur, s_tot = [], [], [], []

    for f in frames[::stride]:
        hasil = hitung_sasa_frame(f, radii, idx_protein=idx_protein,
                                  idx_ligan=idx_ligan, probe=probe,
                                  mol_rdkit=mol_rdkit)
        s_tot.append(hasil["total"])
        s_prot.append(hasil["protein"])
        s_lig.append(hasil["ligan"])
        s_terkubur.append(hasil["terkubur"])

    peringatan = None
    if n_sampel < 10:
        peringatan = f"Jumlah sampel SASA ({n_sampel}) sedikit; gunakan interval_ps lebih kecil."

    return {
        "total": s_tot,
        "protein": s_prot,
        "ligan": s_lig,
        "terkubur": s_terkubur,
        "rerata_terkubur": float(np.mean(s_terkubur)) if s_terkubur else 0.0,
        "sd_terkubur": float(np.std(s_terkubur, ddof=1)) if len(s_terkubur) > 1 else 0.0,
        "peringatan": peringatan,
    }


# ------------------------------------------------------------------ Jarak Kunci
def jarak_kunci(frames: np.ndarray,
                idx_a: int | list[int],
                idx_b: int | list[int],
                ke_angstrom: float = 10.0) -> list[float]:
    """Hitung jarak Euclidean (Å) antara atom/residu A dan B di setiap frame."""
    frames = np.asarray(frames, dtype=np.float64)
    if ke_angstrom != 1.0:
        frames = frames * ke_angstrom

    if isinstance(idx_a, (list, tuple, np.ndarray)):
        pos_a = frames[:, idx_a].mean(axis=1)
    else:
        pos_a = frames[:, idx_a]

    if isinstance(idx_b, (list, tuple, np.ndarray)):
        pos_b = frames[:, idx_b].mean(axis=1)
    else:
        pos_b = frames[:, idx_b]

    diff = pos_a - pos_b
    d = np.sqrt(np.sum(diff ** 2, axis=-1))
    return d.tolist()


# ------------------------------------------------------------------ PCA Cα
def kabsch_sejajarkan(P: np.ndarray, Q: np.ndarray) -> np.ndarray:
    """Superposisi koordinat P ke Q menggunakan algoritma Kabsch."""
    cp = P.mean(axis=0)
    cq = Q.mean(axis=0)
    P_c = P - cp
    Q_c = Q - cq
    H = P_c.T @ Q_c
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    return P_c @ R.T + cq


def pca(frames_ca: np.ndarray, n_komponen: int = 3,
        ke_angstrom: float = 10.0) -> dict[str, Any]:
    """Analisis Komponen Utama (PCA) pada atom Cα protein.

    frames_ca: (N_frame, N_ca, 3) dalam nm (atau Å bila ke_angstrom=1.0).
    """
    frames = np.asarray(frames_ca, dtype=np.float64)
    if ke_angstrom != 1.0:
        frames = frames * ke_angstrom

    n_frames, n_ca, _ = frames.shape
    peringatan = None
    if n_frames < 20:
        peringatan = f"Jumlah frame ({n_frames}) sangat sedikit untuk analisis PCA yang bermakna."

    if n_frames < 3 or n_ca < 3:
        return {
            "proyeksi": np.zeros((n_frames, n_komponen), dtype=float).tolist(),
            "varians_rasio": [0.0] * n_komponen,
            "peringatan": peringatan or "Data frame atau atom Cα tidak memadai.",
        }

    # 1. Superposisi iteratif ke struktur rata-rata
    ref = frames[0]
    sejajar = np.empty_like(frames)
    for i in range(n_frames):
        sejajar[i] = kabsch_sejajarkan(frames[i], ref)

    # 1 iterasi penyempurnaan ke mean
    ref = sejajar.mean(axis=0)
    for i in range(n_frames):
        sejajar[i] = kabsch_sejajarkan(frames[i], ref)

    # 2. Koordinat deviasi terhadap rata-rata: (n_frames, 3 * n_ca)
    flat = sejajar.reshape((n_frames, -1))
    mu = flat.mean(axis=0)
    diff = flat - mu

    # 3. SVD / Dual Covariance
    k = min(n_komponen, n_frames - 1, diff.shape[1])
    # Gunakan SVD langsung pada matriks deviasi (sangat stabil & cepat)
    U, S, Vt = np.linalg.svd(diff, full_matrices=False)
    var = (S ** 2) / max(1, n_frames - 1)
    tot_var = float(np.sum(var))
    var_rasio = (var[:k] / tot_var).tolist() if tot_var > 0 else [0.0] * k

    # Proyeksi frame ke ruang komponen utama: (n_frames, k)
    proyeksi = (diff @ Vt[:k].T).tolist()

    return {
        "proyeksi": proyeksi,
        "varians_rasio": var_rasio,
        "n_frames": n_frames,
        "peringatan": peringatan,
    }


# ------------------------------------------------------------------ FEL (Lanskap Energi Bebas)
def fel(proyeksi: list | np.ndarray,
        T: float = 300.0,
        bin: int = 50) -> dict[str, Any]:
    """Hitung Lanskap Energi Bebas 2D (FEL): G = -k_B * T * ln(P / P_max) dalam kJ/mol.

    proyeksi: (N_frame, >=2) proyeksi koordinat PC1 dan PC2.
    """
    proyeksi = np.asarray(proyeksi, dtype=np.float64)
    n_frames = len(proyeksi)
    peringatan = None
    if n_frames < 500:
        peringatan = f"Jumlah frame ({n_frames}) belum memadai (< 500 frame) untuk konvergensi lanskap energi bebas (FEL)."

    if n_frames < 5 or proyeksi.shape[1] < 2:
        return {
            "G": [], "x": [], "y": [], "min_pos": [0.0, 0.0],
            "n_frame": n_frames, "peringatan": peringatan or "Data tidak mencukupi untuk FEL.",
        }

    pc1 = proyeksi[:, 0]
    pc2 = proyeksi[:, 1]

    H, xedges, yedges = np.histogram2d(pc1, pc2, bins=bin)
    # Pusatkan koordinat bin
    x_centers = ((xedges[:-1] + xedges[1:]) / 2.0).tolist()
    y_centers = ((yedges[:-1] + yedges[1:]) / 2.0).tolist()

    p_max = float(np.max(H))
    if p_max <= 0:
        return {"G": [], "x": x_centers, "y": y_centers, "min_pos": [0.0, 0.0],
                "n_frame": n_frames, "peringatan": "Semua bin histogram bernilai nol."}

    # Konstanta Boltzmann k_B dalam kJ/(mol·K)
    k_B = 8.314462618e-3
    RT = k_B * float(T)

    # G = -RT * ln(P / P_max)
    # Untuk bin kosong, tetapkan nilai cutoff yang tinggi (mis. G_max + 2 kJ/mol)
    G = np.zeros_like(H, dtype=np.float64)
    isi = H > 0
    G[isi] = -RT * np.log(H[isi] / p_max)
    g_max_valid = float(np.max(G[isi])) if np.any(isi) else 25.0
    G[~isi] = g_max_valid + 2.5

    # Temukan koordinat minimum energi bebas (G = 0)
    idx_min = np.unravel_index(np.argmin(G), G.shape)
    min_x = x_centers[idx_min[0]]
    min_y = y_centers[idx_min[1]]

    return {
        "G": G.tolist(),
        "x": x_centers,
        "y": y_centers,
        "min_pos": [min_x, min_y],
        "n_frame": n_frames,
        "peringatan": peringatan,
    }


# ------------------------------------------------------------------ Klaster Ligan
def klaster_ligan(frames: np.ndarray,
                  idx_ligan: list[int],
                  ambang: float = 2.0,
                  ke_angstrom: float = 10.0) -> list[dict[str, Any]]:
    """Pengelompokan hierarki konformasi ligan sepanjang lintasan.

    frames: (N_frame, N_atom, 3) dalam nm (atau Å bila ke_angstrom=1.0).
    idx_ligan: list indeks atom ligan.
    ambang: batas jarak RMSD dalam Å (bawaan 2.0 Å).
    """
    frames = np.asarray(frames, dtype=np.float64)
    if ke_angstrom != 1.0:
        frames = frames * ke_angstrom

    n_frames = len(frames)
    if n_frames < 2 or not idx_ligan:
        return [{"klaster_id": 1, "anggota": list(range(n_frames)), "medoid": 0,
                 "ukuran": n_frames, "persen": 100.0, "rmsd_medoid": 0.0}]

    lig_coords = frames[:, idx_ligan]  # (n_frames, n_lig, 3)
    n_lig = len(idx_ligan)
    flat = lig_coords.reshape((n_frames, -1))

    # Matriks jarak RMSD berpasangan: ||A - B|| / sqrt(N_atom)
    dists = pdist(flat) / np.sqrt(n_lig)
    dist_mat = squareform(dists)

    Z = linkage(dists, method="average")
    labels = fcluster(Z, t=ambang, criterion="distance")

    hasil = []
    for cid in np.unique(labels):
        anggota = np.where(labels == cid)[0].tolist()
        ukuran = len(anggota)
        sub_dists = dist_mat[anggota][:, anggota]
        rata_jarak = sub_dists.mean(axis=1)
        medoid_idx_lokal = int(np.argmin(rata_jarak))
        medoid = anggota[medoid_idx_lokal]
        rmsd_rata = float(rata_jarak[medoid_idx_lokal])

        hasil.append({
            "klaster_id": int(cid),
            "anggota": anggota,
            "medoid": medoid,
            "ukuran": ukuran,
            "persen": round(ukuran / n_frames * 100.0, 1),
            "rmsd_medoid": round(rmsd_rata, 2),
        })

    # Urutkan berdasarkan ukuran klaster terbesar
    hasil.sort(key=lambda x: -x["ukuran"])
    # Perbarui klaster_id berurutan 1..K
    for i, h in enumerate(hasil):
        h["klaster_id"] = i + 1

    return hasil


# ------------------------------------------------------------------ Konvergensi Blok Rata-rata
def blok_rata(nilai: list | np.ndarray, n_blok: int = 5) -> tuple[float, float]:
    """Hitung rata-rata dan galat standar (SE) menggunakan metode rata-rata blok."""
    arr = np.asarray(nilai, dtype=np.float64)
    if len(arr) == 0:
        return 0.0, 0.0
    if len(arr) < n_blok:
        n_blok = max(1, len(arr))

    ukuran = len(arr) // n_blok
    if ukuran == 0:
        return float(np.mean(arr)), 0.0

    blok_vals = [float(np.mean(arr[i * ukuran : (i + 1) * ukuran])) for i in range(n_blok)]
    rata = float(np.mean(blok_vals))
    gs = float(np.std(blok_vals, ddof=1) / math.sqrt(n_blok)) if n_blok > 1 else 0.0
    return rata, gs


# ------------------------------------------------------------------ Barcode & Interaksi Lengkap
def barcode_interaksi_dan_hb(modeller, info, frames, mol, stride: int = 1,
                             ambang_okupansi: float = 0.05) -> dict[str, Any]:
    """Analisis interaksi per-frame yang diperluas:

    Menghasilkan:
    - Garis waktu barcode residu × frame (RLE compressed)
    - Ikatan hidrogen per frame
    - Okupansi interaksi frekuensi
    """
    from . import analisis

    top = modeller.topology
    atoms = list(top.atoms())
    lig = info["idx_ligan"]
    if not lig:     # MD protein tanpa ligan (mis. trajektori impor apo): tidak ada interaksi protein–ligan
        return {"hb_per_frame": [], "interaksi_frek": {},
                "barcode": {"residu": [], "matriks_rle": encode_rle(np.zeros((0, 0))), "n_frame": 0}}
    rec_idx = [i for i in range(len(atoms)) if i not in set(lig)]

    # Saring residu reseptor dalam radius 12 Å dari ligan pada frame acuan
    if len(frames) and len(lig) and len(rec_idx):
        x0 = np.asarray(frames[0], dtype=float) * 10.0
        c_lig0 = x0[lig]
        res_kantong = set()
        for i in rec_idx:
            if np.min(np.linalg.norm(c_lig0 - x0[i], axis=1)) <= 12.0:
                res_kantong.add(atoms[i].residue)
        rec_idx_kantong = [i for i in rec_idx if atoms[i].residue in res_kantong]
        if rec_idx_kantong:
            rec_idx = rec_idx_kantong

    # Siapkan molekul RDKit dasar
    if mol is None:
        rw = Chem.RWMol()
        for i in lig:
            sym = atoms[i].element.symbol if atoms[i].element else "C"
            try:
                rw.AddAtom(Chem.Atom(sym))
            except Exception:
                rw.AddAtom(Chem.Atom(6))
        m_dasar = rw.GetMol()
        for a in m_dasar.GetAtoms():
            a.SetNoImplicit(True)
        try:
            m_dasar.UpdatePropertyCache(strict=False)
            Chem.FastFindRings(m_dasar)
        except Exception:
            pass
        m_dasar.AddConformer(Chem.Conformer(len(lig)))
    else:
        m_dasar = Chem.Mol(mol)
        for a in m_dasar.GetAtoms():
            a.SetNoImplicit(True)
        try:
            m_dasar.UpdatePropertyCache(strict=False)
            Chem.FastFindRings(m_dasar)
        except Exception:
            pass

    frames_sampel = frames[::stride]
    n_sampel = len(frames_sampel)
    if n_sampel == 0:
        return {
            "hb_per_frame": [], "interaksi_frek": {},
            "barcode": {"residu": [], "matriks_rle": encode_rle(np.zeros((0, 0)))},
        }

    rekam_frame = []
    hitung_frek = {}
    hb_list = []

    for f in frames_sampel:
        x = np.asarray(f, dtype=float) * 10.0
        baris = []
        for j, i in enumerate(rec_idx):
            a = atoms[i]
            el = a.element.symbol if a.element is not None else "C"
            baris.append(f"ATOM  {j + 1:5d} {a.name:<4s} {a.residue.name:>3s} {a.residue.chain.id[:1]:1s}"
                         f"{int(''.join(c for c in str(a.residue.id) if c.isdigit()) or 0):4d}    "
                         f"{x[i, 0]:8.3f}{x[i, 1]:8.3f}{x[i, 2]:8.3f}  1.00  0.00          {el:>2s}")
        rec = analisis.baca_reseptor("\n".join(baris))
        m = Chem.Mol(m_dasar)
        conf = m.GetConformer()
        for k_, i in enumerate(lig):
            conf.SetAtomPosition(k_, x[i].tolist())


        inter = [d for d in analisis.interaksi(rec, m) if d.get("jenis") != "vdw"]
        # Hitung jumlah ikatan H
        n_hb = sum(1 for d in inter if d.get("jenis") == "hbond")  # kode jenis di analisis.interaksi
        hb_list.append(n_hb)

        # Himpunan kunci residu aktif pada frame ini; okupansi dihitung per frame (dua ikatan H ke residu yang
        # sama dalam satu frame tetap satu), jadi nilainya 0–100 %.
        aktif_frame = {f"{d['residu']}|{d['jenis']}" for d in inter}
        for kunci in aktif_frame:
            hitung_frek[kunci] = hitung_frek.get(kunci, 0) + 1

        rekam_frame.append(aktif_frame)

    interaksi_frek = {k: v / n_sampel for k, v in sorted(hitung_frek.items(), key=lambda kv: -kv[1])}

    # Saring residu untuk barcode (okupansi >= ambang)
    calon_barcode = [k for k, v in interaksi_frek.items() if v >= ambang_okupansi]
    if not calon_barcode:
        calon_barcode = list(interaksi_frek.keys())[:15]

    matriks = np.zeros((len(calon_barcode), n_sampel), dtype=np.int8)
    for col, aktif in enumerate(rekam_frame):
        for row, kunci in enumerate(calon_barcode):
            if kunci in aktif:
                matriks[row, col] = 1

    rle = encode_rle(matriks)

    return {
        "hb_per_frame": hb_list,
        "interaksi_frek": interaksi_frek,
        "barcode": {
            "residu": calon_barcode,
            "matriks_rle": rle,
            "n_frame": n_sampel,
        },
    }


# ------------------------------------------------------------------ Analisis Lengkap Versi 2
BONDI_VDW = {
    "H": 1.20, "C": 1.70, "N": 1.55, "O": 1.52, "F": 1.47, "P": 1.80, "S": 1.80,
    "CL": 1.75, "BR": 1.85, "I": 1.98, "ZN": 1.39, "MG": 1.73, "CA": 1.00,
    "FE": 1.80, "NA": 2.27, "K": 2.75,
}


def analisis_lengkap(modeller, info: dict, frames: np.ndarray, mol: Chem.Mol,
                      dt_ps: float = 10.0, stride_sasa: int | None = None) -> dict[str, Any]:
    """Eksekusi seluruh analisis MD tingkat lanjut (F2) versi 2.

    Menghasilkan dict struktur analisis yang kompatibel dengan proyek.md["analisis"].
    """
    frames = np.asarray(frames, dtype=np.float32)
    n_frames = len(frames)
    if n_frames == 0:
        return {"versi": 2, "peringatan": ["Trajektori kosong."]}

    top = modeller.topology
    atoms = list(top.atoms())
    n_tot = len(atoms)

    ca_idx = [a.index for a in atoms if a.name == "CA" and a.element is not None and a.element.symbol == "C"]
    lig_idx = [i for i in info.get("idx_ligan", []) if i < n_tot]
    rec_idx = [i for i in range(n_tot) if i not in set(lig_idx)]

    # Massa atom
    massa = np.array([a.element.mass._value if (a.element and hasattr(a.element, "mass")) else 12.0
                      for a in atoms], dtype=np.float64)

    # Jari-jari Bondi
    radii = np.array([BONDI_VDW.get(a.element.symbol.upper() if a.element else "C", 1.70)
                      for a in atoms], dtype=np.float64)

    peringatan_semua = []

    # 1. Radius Girasi protein (dan kompleks)
    rg_prot, warn_rg = radius_girasi(frames, massa=massa, idx=rec_idx, ke_angstrom=10.0)
    if warn_rg:
        peringatan_semua.append(warn_rg)

    # 2. SASA protein & ligan
    if stride_sasa is None:
        stride_sasa = max(1, n_frames // 100)
    hasil_sasa = sasa(frames, radii, idx_protein=rec_idx, idx_ligan=lig_idx,
                      stride=stride_sasa, probe=1.4, mol_rdkit=None, ke_angstrom=10.0)
    if hasil_sasa.get("peringatan"):
        peringatan_semua.append(hasil_sasa["peringatan"])

    # 3. Barcode & Ikatan Hidrogen per frame
    stride_inter = max(1, n_frames // 100)
    hasil_inter = barcode_interaksi_dan_hb(modeller, info, frames, mol, stride=stride_inter)

    # 4. PCA pada Cα
    if ca_idx:
        frames_ca = frames[:, ca_idx]
        hasil_pca = pca(frames_ca, n_komponen=3, ke_angstrom=10.0)
        if hasil_pca.get("peringatan"):
            peringatan_semua.append(hasil_pca["peringatan"])
    else:
        hasil_pca = {"proyeksi": [], "varians_rasio": [], "peringatan": "Residu Cα tidak terdeteksi."}

    # 5. FEL dari proyeksi PC1-PC2
    if hasil_pca.get("proyeksi"):
        hasil_fel = fel(hasil_pca["proyeksi"], T=300.0, bin=50)
        if hasil_fel.get("peringatan"):
            peringatan_semua.append(hasil_fel["peringatan"])
    else:
        hasil_fel = {"G": [], "x": [], "y": [], "min_pos": [0.0, 0.0], "peringatan": "PCA kosong."}

    # 6. Klaster konformasi ligan
    if lig_idx:
        hasil_klaster = klaster_ligan(frames, idx_ligan=lig_idx, ambang=2.0, ke_angstrom=10.0)
    else:
        hasil_klaster = []

    # 7. Konvergensi (block averaging)
    rata_rg, gs_rg = blok_rata(rg_prot, n_blok=5) if rg_prot else (0.0, 0.0)
    rata_hb, gs_hb = blok_rata(hasil_inter["hb_per_frame"], n_blok=5) if hasil_inter.get("hb_per_frame") else (0.0, 0.0)

    konvergensi = {
        "rg_rerata": round(rata_rg, 3),
        "rg_gs": round(gs_rg, 3),
        "hb_rerata": round(rata_hb, 2),
        "hb_gs": round(gs_hb, 2),
    }

    return {
        "versi": 2,
        "rg": rg_prot,
        "sasa": hasil_sasa,
        "hb": hasil_inter["hb_per_frame"],
        "interaksi_frek": hasil_inter["interaksi_frek"],
        "barcode": hasil_inter["barcode"],
        "pca": hasil_pca,
        "fel": hasil_fel,
        "klaster": hasil_klaster,
        "konvergensi": konvergensi,
        "peringatan": peringatan_semua,
    }


# ------------------------------------------------------------------ DCD & Ekspor Klaster
def baca_dcd(f_dcd) -> tuple[np.ndarray, int]:
    """Membaca file binary DCD (OpenMM/CHARMM) ke ndarray koordinat (N_frame, N_atom, 3) dalam nm.

    Mengembalikan (frames_nm, dt_ps).
    """
    import struct
    from pathlib import Path
    f_path = Path(f_dcd)
    if not f_path.exists():
        raise FileNotFoundError(f"Berkas DCD tidak ditemukan: {f_dcd}")

    with open(f_path, "rb") as f:
        magic = f.read(8)
        if len(magic) < 8 or magic[4:8] != b"CORD":
            raise ValueError("Bukan format DCD yang valid.")
        n_frame = struct.unpack("<i", f.read(4))[0]
        f.seek(32)
        box_flag = struct.unpack("<i", f.read(4))[0]
        f.seek(44)
        dt_raw = struct.unpack("<f", f.read(4))[0]
        dt_ps = dt_raw * 0.04888821 if dt_raw > 0 else 10.0

        f.seek(92)
        com_bytes = struct.unpack("<i", f.read(4))[0]
        f.seek(104 + com_bytes)
        n_atoms = struct.unpack("<i", f.read(4))[0]
        f.seek(104 + com_bytes + 8)

        frames_nm = []
        for _ in range(n_frame):
            if box_flag == 1:
                f.read(56)  # 4 + 48 + 4 byte unit cell
            xyz = []
            for _ in range(3):
                l1_bytes = f.read(4)
                if len(l1_bytes) < 4:
                    break
                l1 = struct.unpack("<i", l1_bytes)[0]
                data = f.read(l1)
                arr = np.frombuffer(data, dtype=np.float32)
                _ = f.read(4)
                xyz.append(arr)
            if len(xyz) == 3 and len(xyz[0]) == n_atoms:
                coords_nm = np.stack(xyz, axis=1) / 10.0
                frames_nm.append(coords_nm)

    return np.asarray(frames_nm, dtype=np.float32), int(round(dt_ps))


def ekspor_pdb_medoid(topologi, frames: np.ndarray, klaster_list: list[dict],
                      folder_keluaran) -> list[str]:
    """Ekspor pose medoid setiap klaster ke berkas PDB kompleks di folder_keluaran."""
    from pathlib import Path
    from openmm import app, unit
    folder = Path(folder_keluaran)
    folder.mkdir(parents=True, exist_ok=True)
    hasil_pdb = []

    for k_idx, kl in enumerate(klaster_list):
        med_fr = kl.get("medoid", 0)
        if 0 <= med_fr < len(frames):
            f_out = folder / f"klaster_{k_idx + 1}_medoid.pdb"
            pos_nm = unit.Quantity(np.asarray(frames[med_fr], dtype=float), unit.nanometer)
            with open(f_out, "w", encoding="utf-8") as h:
                app.PDBFile.writeFile(topologi, pos_nm, h, keepIds=True)
            hasil_pdb.append(str(f_out))
            kl["pdb_medoid"] = str(f_out)

    return hasil_pdb


# ------------------------------------------------------------------ Visualisasi SVG F2
def _label_interaksi(kunci):
    """'ASP 25 A|hbond' -> 'ASP 25 A · Ikatan hidrogen'."""
    from .analisis import NAMA_JENIS
    res, _, jenis = str(kunci).partition("|")
    return f"{res} · {NAMA_JENIS.get(jenis, jenis)}" if jenis else res


def svg_barcode_interaksi(barcode_data: dict, dt_ps: float = 10.0,
                          lebar: int = 760, tinggi: int = 400,
                          gelap: bool = False, judul: str = "Garis Waktu Interaksi") -> str:
    """Render heatmap SVG 'barcode' residu × waktu."""
    from . import grafik
    from xml.sax.saxutils import escape

    residu_list = barcode_data.get("residu", [])
    rle = barcode_data.get("matriks_rle", {})
    if not residu_list or not rle:
        k = grafik.Kanvas(lebar, tinggi, gelap, judul=judul)
        k.teks(lebar / 2, tinggi / 2, "Tidak ada interaksi persisten", 12, "middle", warna_=k.w["tinta2"])
        return k.selesai()

    matriks = decode_rle(rle)  # (n_residu, n_frame)
    n_res, n_frame = matriks.shape
    if n_res == 0 or n_frame == 0:
        k = grafik.Kanvas(lebar, tinggi, gelap, judul=judul)
        k.teks(lebar / 2, tinggi / 2, "Matriks interaksi kosong", 12, "middle", warna_=k.w["tinta2"])
        return k.selesai()

    if n_res > 35:
        frek = np.sum(matriks, axis=1)
        urut_idx = np.argsort(-frek)[:35]
        matriks = matriks[urut_idx]
        residu_list = [residu_list[i] for i in urut_idx]
        n_res = 35

    pjg_label = max(len(str(r)) for r in residu_list)
    kiri = min(220, max(120, int(pjg_label * 6.5) + 20))
    tinggi = max(tinggi, 50 + n_res * 18 + 50)

    k = grafik.Kanvas(lebar, tinggi, gelap, judul=judul, kiri=kiri, bawah=45, atas=45)
    pw, ph = k.pw, k.ph
    b_y = k.atas + ph

    t_maks_ns = max(0.1, (n_frame * dt_ps) / 1000.0)
    tx, langkah = grafik.tik(0.0, t_maks_ns, 7)
    k.x0, k.x1 = tx[0], tx[-1]
    desimal = max(0, -int(np.floor(np.log10(langkah))) + (1 if round(langkah / 10 ** np.floor(np.log10(langkah)), 1) == 2.5 else 0))

    for v in tx:
        px = k.X(v)
        k.out.append(f'<line x1="{px:.1f}" y1="{b_y}" x2="{px:.1f}" y2="{b_y + 4}" stroke="{k.w["garis"]}"/>')
        k.teks(px, b_y + 16, grafik.fmt(v, desimal), 10, anchor="middle", warna_=k.w["tinta2"])
    k.teks(kiri + pw / 2.0, b_y + 32, "Waktu (ns)", 11, anchor="middle", tebal=True)

    k.out.append(f'<line x1="{kiri}" y1="{b_y}" x2="{kiri + pw}" y2="{b_y}" stroke="{k.w["garis"]}"/>')
    k.out.append(f'<line x1="{kiri}" y1="{k.atas}" x2="{kiri}" y2="{b_y}" stroke="{k.w["garis"]}"/>')

    h_baris = ph / float(n_res)
    w_kolom = pw / float(n_frame)
    warna_aktif = "#2563eb" if not gelap else "#3b82f6"

    for r_i, r_label in enumerate(residu_list):
        py = k.atas + r_i * h_baris
        k.teks(kiri - 8, py + h_baris / 2.0 + 3.5, _label_interaksi(r_label), 9.5, anchor="end")

        baris_bit = matriks[r_i]
        perubahan = np.where(np.diff(np.concatenate([[0], baris_bit, [0]])) != 0)[0]
        for idx_seg in range(0, len(perubahan) - 1, 2):
            f_start = perubahan[idx_seg]
            f_end = perubahan[idx_seg + 1]
            x_balok = kiri + f_start * w_kolom
            w_balok = max(0.8, (f_end - f_start) * w_kolom)
            k.out.append(f'<rect x="{x_balok:.1f}" y="{py + 1:.1f}" width="{w_balok:.1f}" '
                         f'height="{max(1.0, h_baris - 2):.1f}" fill="{warna_aktif}" opacity="0.9">'
                         f'<title>{escape(str(r_label))}: aktif</title></rect>')

    return k.selesai()


def svg_fel_2d(fel_data: dict, var_pc1: float | None = None, var_pc2: float | None = None,
               lebar: int = 480, tinggi: int = 440, gelap: bool = False,
               judul: str = "Lanskap Energi Bebas (FEL)") -> str:
    """Render peta panas FEL 2D (kJ/mol) beserta titik energi minimum."""
    from . import grafik

    G = np.asarray(fel_data.get("G", []), dtype=float)
    x = np.asarray(fel_data.get("x", []), dtype=float)
    y = np.asarray(fel_data.get("y", []), dtype=float)

    if G.ndim != 2 or len(x) == 0 or len(y) == 0:
        k = grafik.Kanvas(lebar, tinggi, gelap, judul=judul)
        k.teks(lebar / 2, tinggi / 2, "Data FEL tidak cukup", 12, "middle", warna_=k.w["tinta2"])
        return k.selesai()

    nx, ny = len(x), len(y)
    g_ada = G[np.isfinite(G)]
    g_min = float(np.min(g_ada)) if len(g_ada) else 0.0
    g_max = float(np.max(g_ada)) if len(g_ada) else 10.0
    g_max = min(g_max, 25.0)

    k = grafik.Kanvas(lebar, tinggi, gelap, judul=judul, kiri=55, kanan=75, atas=45,
                      bawah=75 if fel_data.get("peringatan") else 55)
    tx, _ = grafik.tik(float(x[0]), float(x[-1]), 6)
    ty, _ = grafik.tik(float(y[0]), float(y[-1]), 6)
    k.x0, k.x1 = tx[0], tx[-1]
    k.y0, k.y1 = ty[0], ty[-1]

    lbl_x = "PC1 (Å)" + (f" [{grafik.fmt(var_pc1 * 100, 1)} %]" if var_pc1 is not None else "")
    lbl_y = "PC2 (Å)" + (f" [{grafik.fmt(var_pc2 * 100, 1)} %]" if var_pc2 is not None else "")
    k.sumbu([tx[0], tx[-1]], [ty[0], ty[-1]], label_x=lbl_x, label_y=lbl_y, pad=0.0)

    dx_pix = k.pw / float(nx)
    dy_pix = k.ph / float(ny)

    warna_latar_inf = "#0f172a" if gelap else "#f8fafc"
    for i in range(nx):
        for j in range(ny):
            val = G[i, j]
            if not np.isfinite(val) or val >= g_max:
                isi = warna_latar_inf
            else:
                frac = max(0.0, min(1.0, (val - g_min) / (g_max - g_min) if g_max > g_min else 0.0))
                isi = grafik._skala_biru(frac)
            px = k.X(x[i]) - dx_pix / 2.0
            py = k.Y(y[j]) - dy_pix / 2.0
            k.out.append(f'<rect x="{px:.1f}" y="{py:.1f}" width="{dx_pix + 0.3:.1f}" '
                         f'height="{dy_pix + 0.3:.1f}" fill="{isi}"/>')

    min_pos = fel_data.get("min_pos", [0.0, 0.0])
    px_min = k.X(min_pos[0])
    py_min = k.Y(min_pos[1])
    k.out.append(f'<circle cx="{px_min:.1f}" cy="{py_min:.1f}" r="6" fill="#ef4444" stroke="#ffffff" stroke-width="1.5">'
                 f'<title>Minimum FEL (ΔG = 0 kJ/mol)</title></circle>')

    lx = k.kiri + k.pw + 15
    lh = min(200, k.ph)
    ly = k.atas + (k.ph - lh) / 2.0
    for s in range(40):
        frac = 1.0 - (s / 39.0)
        col = grafik._skala_biru(frac)
        sy = ly + s * (lh / 40.0)
        k.out.append(f'<rect x="{lx}" y="{sy:.1f}" width="12" height="{lh / 40.0 + 0.5:.1f}" fill="{col}"/>')
    k.teks(lx + 16, ly + 6, f"{grafik.fmt(g_max, 1)}", 9.5, warna_=k.w["tinta2"])
    k.teks(lx + 16, ly + lh, "0", 9.5, warna_=k.w["tinta2"])
    k.teks(lx - 2, ly - 6, "kJ/mol", 9, tebal=True, warna_=k.w["tinta"])

    if fel_data.get("peringatan"):
        k.catatan(fel_data["peringatan"])

    return k.selesai()


def svg_pca_sebar(pca_data: dict, dt_ps: float = 10.0,
                  lebar: int = 480, tinggi: int = 440, gelap: bool = False,
                  judul: str = "Proyeksi PC1 vs PC2") -> str:
    """Render scatter plot PC1 vs PC2 diwarnai waktu trajektori."""
    from . import grafik

    proyeksi = np.asarray(pca_data.get("proyeksi", []), dtype=float)
    if len(proyeksi) == 0:
        k = grafik.Kanvas(lebar, tinggi, gelap, judul=judul)
        k.teks(lebar / 2, tinggi / 2, "Data PCA kosong", 12, "middle", warna_=k.w["tinta2"])
        return k.selesai()

    x = proyeksi[:, 0]
    y = proyeksi[:, 1]
    n_frames = len(x)
    t_ns = [(i * dt_ps) / 1000.0 for i in range(n_frames)]

    var = pca_data.get("varians_rasio", [0.0, 0.0])
    lbl_x = f"PC1 (Å) [{grafik.fmt(var[0] * 100, 1)} %]" if len(var) > 0 else "PC1 (Å)"
    lbl_y = f"PC2 (Å) [{grafik.fmt(var[1] * 100, 1)} %]" if len(var) > 1 else "PC2 (Å)"

    return grafik.sebar_kelompok(x, y, [f"Frame {i+1}" for i in range(n_frames)],
                                 nilai=t_ns, label_x=lbl_x, label_y=lbl_y,
                                 judul=judul, gelap=gelap, lebar=lebar, tinggi=tinggi,
                                 label_nilai="Waktu (ns)", tanpa_tik=False)


def hitung_analisis_lanjutan(folder_sub, dt_ps: float = 10.0, mol_rdkit=None) -> dict:
    """Membaca trajektori_terlarut.dcd dan topologi.pdb dari folder simulasi MD,

    lalu menjalankan analisis MD lengkap (F2 versi 2).
    """
    from pathlib import Path
    from openmm import app
    p = Path(folder_sub)
    f_dcd = p / "trajektori_terlarut.dcd"
    f_top = p / "topologi.pdb"

    if not f_dcd.exists() or not f_top.exists():
        # Cek apakah ada di subfolder replika_1
        if (p / "replika_1" / "trajektori_terlarut.dcd").exists():
            f_dcd = p / "replika_1" / "trajektori_terlarut.dcd"
            f_top = p / "replika_1" / "topologi.pdb"
        else:
            raise FileNotFoundError(f"Berkas DCD atau topologi PDB tidak ditemukan di {folder_sub}")

    frames, dt_baca = baca_dcd(f_dcd)
    pdb = app.PDBFile(str(f_top))

    # Ekstraksi indeks ligan & protein dari residu topologi
    top = pdb.topology
    atoms = list(top.atoms())
    lig_idx = [a.index for a in atoms if a.residue.name not in {"ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU",
                                                                 "GLY", "HIS", "ILE", "LEU", "LYS", "MET", "PHE",
                                                                 "PRO", "SER", "THR", "TRP", "TYR", "VAL", "HID",
                                                                 "HIE", "HIP", "ASH", "GLH", "LYN", "CYX", "CYM",
                                                                 "HOH", "WAT", "NA", "CL", "K"}]
    info = {"idx_ligan": lig_idx}

    class ModellerDummy:
        def __init__(self, topology):
            self.topology = topology

    m_dummy = ModellerDummy(top)
    return analisis_lengkap(m_dummy, info, frames, mol_rdkit, dt_ps=dt_baca or dt_ps)


