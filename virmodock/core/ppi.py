"""Protein-Protein Interaction (PPI) Docking & Interface Analysis Module.

Menyediakan:
1. Prediksi residu antarmuka (surface exposure & SASA Shrake-Rupley).
2. Penilaian kompleks antarmuka PPI: luas permukaan terkubur (Buried Surface Area / ΔSASA),
   ikatan hidrogen antar-rantai, jembatan garam, dan skor komplementaritas.
3. Klastering pose docking model protein-protein berbasis RMSD C-alfa.
4. Penyiapan berkas untuk docking rigid-body di ClusPro 2.0 (diunggah sendiri oleh pengguna).
"""
from typing import Any, Dict, List, Optional
import math
import numpy as np

# Jari-jari Van der Waals atomik standar (Å)
VDW_RADIUS = {
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "S": 1.80,
    "H": 1.20,
    "P": 1.80,
}
PROBE_RADIUS = 1.40  # Jari-jari molekul air (Å)

# Maksimum luas permukaan residu standar terisolasi (Å², Tien et al. 2013)
MAX_SASA_RESIDU = {
    "ALA": 121.0, "ARG": 265.0, "ASN": 187.0, "ASP": 187.0, "CYS": 148.0,
    "GLU": 214.0, "GLN": 214.0, "GLY": 97.0,  "HIS": 216.0, "ILE": 195.0,
    "LEU": 191.0, "LYS": 230.0, "MET": 203.0, "PHE": 228.0, "PRO": 154.0,
    "SER": 143.0, "THR": 163.0, "TRP": 264.0, "TYR": 255.0, "VAL": 165.0,
}


def _uraikan_pdb(pdb_teks: str) -> List[Dict[str, Any]]:
    """Uraikan atom ATOM/HETATM dari string teks PDB ke list dict."""
    atom_list = []
    for baris in (pdb_teks or "").splitlines():
        if baris.startswith("ATOM  ") or baris.startswith("HETATM"):
            try:
                nama_atom = baris[12:16].strip()
                resn = baris[17:20].strip()
                rantai = baris[21].strip() or "A"
                resi = int(baris[22:26].strip())
                x = float(baris[30:38].strip())
                y = float(baris[38:46].strip())
                z = float(baris[46:54].strip())
                simbol = baris[76:78].strip() if len(baris) >= 78 else nama_atom[0]
                if not simbol or simbol.isdigit():
                    simbol = nama_atom[0]
                simbol = simbol.upper()

                # Abaikan atom hidrogen untuk perhitungan atom berat
                if simbol == "H":
                    continue

                atom_list.append({
                    "nama": nama_atom,
                    "resn": resn,
                    "rantai": rantai,
                    "resi": resi,
                    "pos": np.array([x, y, z], dtype=np.float64),
                    "simbol": simbol,
                    "r": VDW_RADIUS.get(simbol, 1.70),
                })
            except (ValueError, IndexError):
                continue
    return atom_list


def _hitung_sasa_shrake_rupley(atom_list: List[Dict[str, Any]], n_titik: int = 96) -> np.ndarray:
    """Hitung Solvent Accessible Surface Area (SASA) untuk tiap atom menggunakan algoritma Shrake-Rupley.

    Menggunakan distribusi bola Fibonacci. Cepat dan akurat.
    """
    n_atom = len(atom_list)
    if n_atom == 0:
        return np.array([])

    posisi = np.array([a["pos"] for a in atom_list])
    radii = np.array([a["r"] + PROBE_RADIUS for a in atom_list])

    # Titik pada bola satuan menggunakan kisi Fibonacci
    i_ind = np.arange(0, n_titik, dtype=np.float64)
    phi = (1.0 + np.sqrt(5.0)) / 2.0  # Golden ratio
    theta = 2.0 * np.pi * i_ind / phi
    z_pts = 1.0 - (2.0 * i_ind + 1.0) / n_titik
    r_pts = np.sqrt(np.maximum(0.0, 1.0 - z_pts * z_pts))
    x_pts = r_pts * np.cos(theta)
    y_pts = r_pts * np.sin(theta)
    bola_satuan = np.column_stack((x_pts, y_pts, z_pts))  # (n_titik, 3)

    sasa_per_atom = np.zeros(n_atom, dtype=np.float64)
    luas_titik = 4.0 * np.pi / n_titik

    # Cari tetangga potensial dengan bounding box
    for i in range(n_atom):
        r_i = radii[i]
        pos_i = posisi[i]

        # Jarak ke atom lain
        d_vec = posisi - pos_i
        dist_sq = np.sum(d_vec * d_vec, axis=1)

        # Hanya periksa tetangga dalam jangkauan r_i + r_j
        jangkauan_maks = r_i + radii
        tetangga_mask = (dist_sq > 1e-6) & (dist_sq < jangkauan_maks * jangkauan_maks)
        tetangga_idx = np.where(tetangga_mask)[0]

        if len(tetangga_idx) == 0:
            # Tidak ada tetangga menutupi
            sasa_per_atom[i] = 4.0 * np.pi * r_i * r_i
            continue

        # Titik uji pada permukaan atom i
        titik_uji = pos_i + bola_satuan * r_i  # (n_titik, 3)
        pos_tetangga = posisi[tetangga_idx]
        radii_tetangga = radii[tetangga_idx]

        # Periksa apakah titik uji berada di dalam salah satu tetangga
        terbuka_count = 0
        for pt in titik_uji:
            d_sq = np.sum((pos_tetangga - pt) ** 2, axis=1)
            if np.all(d_sq >= radii_tetangga * radii_tetangga):
                terbuka_count += 1

        sasa_per_atom[i] = luas_titik * r_i * r_i * terbuka_count

    return sasa_per_atom


def prediksi_antarmuka(pdb_teks: str, ambang_relatif: float = 0.25) -> List[Dict[str, Any]]:
    """Prediksi residu kandidat antarmuka pengikatan protein berbasis keterpaparan pelarut (SASA).

    Residu dengan SASA relatif >= ambang_relatif diklasifikasikan sebagai kandidat antarmuka.
    """
    atom_list = _uraikan_pdb(pdb_teks)
    if not atom_list:
        return []

    sasa_atoms = _hitung_sasa_shrake_rupley(atom_list, n_titik=72)

    # Agregasi per residu: (rantai, resi, resn)
    residu_sasa = {}
    for idx, a in enumerate(atom_list):
        kunci = (a["rantai"], a["resi"], a["resn"])
        residu_sasa[kunci] = residu_sasa.get(kunci, 0.0) + sasa_atoms[idx]

    hasil = []
    for (rantai, resi, resn), val_sasa in residu_sasa.items():
        max_sasa = MAX_SASA_RESIDU.get(resn, 180.0)
        rel_sasa = round(val_sasa / max_sasa, 3) if max_sasa > 0 else 0.0
        is_kandidat = (rel_sasa >= ambang_relatif)

        hasil.append({
            "rantai": rantai,
            "resi": resi,
            "resn": resn,
            "label": f"{resn} {resi} ({rantai})",
            "sasa": round(val_sasa, 1),
            "rel_sasa": rel_sasa,
            "kandidat": is_kandidat,
        })

    # Urutkan berdasarkan nomor residu
    hasil.sort(key=lambda x: (x["rantai"], x["resi"]))
    return hasil


def skor_antarmuka(
    pdb_kompleks_teks: str,
    rantai_a: Optional[str] = None,
    rantai_b: Optional[str] = None,
    cutoff_jarak: float = 4.5,
) -> Dict[str, Any]:
    """Hitung metrik kualitas dan interaksi antarmuka kompleks Protein-Protein.

    Metrik yang dievaluasi:
      - Kontak antarmuka atom berat (≤ 4.5 Å)
      - Ikatan hidrogen antar-rantai (donor/akseptor N, O ≤ 3.5 Å)
      - Jembatan garam antar-rantai (Asp/Glu vs Lys/Arg/His ≤ 4.0 Å)
      - Buried Surface Area (ΔSASA)
      - Skor komplementaritas antarmuka
      - Daftar residu antarmuka rantai A dan rantai B
    """
    atom_list = _uraikan_pdb(pdb_kompleks_teks)
    if not atom_list:
        return {"error": "Format PDB tidak valid atau kosong"}

    rantai_semua = sorted(list({a["rantai"] for a in atom_list}))
    if len(rantai_semua) < 2:
        return {"error": f"Struktur hanya memiliki satu rantai ({rantai_semua}). Diperlukan minimal 2 rantai protein."}

    ch_a = rantai_a or rantai_semua[0]
    ch_b = rantai_b or (rantai_semua[1] if len(rantai_semua) > 1 else rantai_semua[0])

    atoms_a = [a for a in atom_list if a["rantai"] == ch_a]
    atoms_b = [a for a in atom_list if a["rantai"] == ch_b]

    if not atoms_a or not atoms_b:
        return {"error": f"Rantai {ch_a} atau {ch_b} tidak ditemukan di struktur PDB"}

    pos_a = np.array([a["pos"] for a in atoms_a])
    pos_b = np.array([a["pos"] for a in atoms_b])

    # Hitung matriks jarak antar-rantai
    # (N_A, N_B)
    diff = pos_a[:, np.newaxis, :] - pos_b[np.newaxis, :, :]
    dist = np.sqrt(np.sum(diff * diff, axis=-1))

    # 1. Kontak Atom Berat
    mask_kontak = dist <= cutoff_jarak
    idx_a, idx_b = np.where(mask_kontak)
    kontak_total = len(idx_a)

    res_a_antarmuka = set()
    res_b_antarmuka = set()
    for ia, ib in zip(idx_a, idx_b):
        res_a_antarmuka.add((atoms_a[ia]["resn"], atoms_a[ia]["resi"], ch_a))
        res_b_antarmuka.add((atoms_b[ib]["resn"], atoms_b[ib]["resi"], ch_b))

    # 2. Ikatan Hidrogen Antar-Rantai (N & O <= 3.5 Å)
    hbond_count = 0
    for ia, ib in zip(idx_a, idx_b):
        if dist[ia, ib] <= 3.5:
            sa = atoms_a[ia]["simbol"]
            sb = atoms_b[ib]["simbol"]
            if (sa in ("N", "O")) and (sb in ("N", "O")):
                hbond_count += 1

    # 3. Jembatan Garam (Acidic vs Basic <= 4.0 Å)
    asam = {"ASP", "GLU"}
    basa = {"ARG", "LYS", "HIS"}
    garam_count = 0
    for ia, ib in zip(idx_a, idx_b):
        if dist[ia, ib] <= 4.0:
            ra = atoms_a[ia]["resn"]
            rb = atoms_b[ib]["resn"]
            if (ra in asam and rb in basa) or (ra in basa and rb in asam):
                garam_count += 1

    # 4. Buried Surface Area (ΔSASA)
    sasa_kompleks = np.sum(_hitung_sasa_shrake_rupley(atoms_a + atoms_b, n_titik=64))
    sasa_mono_a = np.sum(_hitung_sasa_shrake_rupley(atoms_a, n_titik=64))
    sasa_mono_b = np.sum(_hitung_sasa_shrake_rupley(atoms_b, n_titik=64))
    bsa = max(0.0, (sasa_mono_a + sasa_mono_b - sasa_kompleks) / 2.0)

    # 5. Skor Komplementaritas / Kerapatan Kontak Antarmuka
    n_res_int = len(res_a_antarmuka) + len(res_b_antarmuka)
    skor_komp = min(1.0, round(kontak_total / max(1.0, n_res_int * 3.5), 2)) if n_res_int else 0.0

    return {
        "rantai_a": ch_a,
        "rantai_b": ch_b,
        "kontak_total": kontak_total,
        "ikatan_h": hbond_count,
        "jembatan_garam": garam_count,
        "bsa_luas": round(bsa, 1),
        "skor_komplementaritas": skor_komp,
        "jumlah_residu_a": len(res_a_antarmuka),
        "jumlah_residu_b": len(res_b_antarmuka),
        "residu_a": sorted([f"{r[0]} {r[1]}" for r in res_a_antarmuka], key=lambda x: int(x.split()[1])),
        "residu_b": sorted([f"{r[0]} {r[1]}" for r in res_b_antarmuka], key=lambda x: int(x.split()[1])),
    }


def klaster_pose(daftar_pdb_teks: List[str], rmsd_ambang: float = 4.0) -> List[Dict[str, Any]]:
    """Klastering pose docking protein-protein berdasarkan RMSD C-alfa antar model."""
    if not daftar_pdb_teks:
        return []

    # Ambil koordinat C-alfa untuk tiap model
    model_ca = []
    for pdb in daftar_pdb_teks:
        atoms = _uraikan_pdb(pdb)
        ca_pts = np.array([a["pos"] for a in atoms if a["nama"] == "CA"], dtype=np.float64)
        if len(ca_pts) > 0:
            model_ca.append(ca_pts)
        else:
            # Fallback ke semua atom berat bila tidak ada CA
            pts = np.array([a["pos"] for a in atoms], dtype=np.float64)
            model_ca.append(pts)

    n_model = len(model_ca)
    if n_model == 0:
        return []

    # Fungsi hitung RMSD sederhana tanpa rotasi (karena rigid-body docking sudah di frame referensi reseptor)
    def _rmsd(p1, p2):
        min_len = min(len(p1), len(p2))
        if min_len == 0:
            return 999.0
        d = p1[:min_len] - p2[:min_len]
        return math.sqrt(np.mean(np.sum(d * d, axis=1)))

    # Algoritma Klastering Leader
    klaster_list = []  # list of list of model index
    for i in range(n_model):
        dimasukkan = False
        for k in klaster_list:
            leader_idx = k[0]
            if _rmsd(model_ca[i], model_ca[leader_idx]) <= rmsd_ambang:
                k.append(i)
                dimasukkan = True
                break
        if not dimasukkan:
            klaster_list.append([i])

    # Urutkan klaster berdasarkan jumlah anggota terbanyak
    klaster_list.sort(key=lambda k: len(k), reverse=True)

    hasil = []
    for c_id, anggota in enumerate(klaster_list):
        hasil.append({
            "klaster_id": c_id + 1,
            "ukuran": len(anggota),
            "representatif": anggota[0],
            "anggota": anggota,
        })
    return hasil


def berkas_cluspro(folder_tujuan: str, pdb_reseptor: str, pdb_ligan: str) -> Dict[str, Any]:
    """Siapkan dua berkas PDB untuk diunggah sendiri ke ClusPro 2.0 lewat peramban.

    VirmoLab tidak mengirim struktur ke server mana pun: pengunggahan dilakukan pengguna di
    https://cluspro.bu.edu/ dengan akun miliknya sendiri (ClusPro mewajibkan pendaftaran dan
    hanya gratis untuk penggunaan non-komersial).
    """
    from pathlib import Path
    f = Path(folder_tujuan)
    f.mkdir(parents=True, exist_ok=True)
    rec, lig = f / "cluspro_reseptor.pdb", f / "cluspro_ligan.pdb"
    rec.write_text(pdb_reseptor, encoding="utf-8")
    lig.write_text(pdb_ligan, encoding="utf-8")
    return {"reseptor": str(rec), "ligan": str(lig), "url": "https://cluspro.bu.edu/",
            "catatan": "Unggah kedua berkas di laman ClusPro memakai akun Anda; VirmoLab tidak mengirim data."}
