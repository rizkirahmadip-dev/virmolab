"""Penapisan berbasis ligan 3D: kueri farmakofor 3D dan keselarasan bentuk (RDKit).

Mencakup:
1. Pembuatan kueri farmakofor 3D dari pose ligan (dengan volume eksklusi protein opsional).
2. Pembangkitan konformer ETKDGv3 dengan pemangkasan RMSD.
3. Pencocokan fitur farmakofor dan bentuk-warna terhadap kueri.
4. Penapisan pustaka senyawa massal secara paralel (per kelompok 500 senyawa).
5. Validasi bawaan kueri (ROC-AUC, BEDROC, EF1%) bila tersedia senyawa aktif dan decoy.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, rdShapeAlign

from . import catat, kemiripan, uji


def konformer(mol: Union[Chem.Mol, str], n: int = 30, prune: float = 0.5, seed: int = 42) -> Chem.Mol:
    """Hasilkan konformer 3D untuk molekul menggunakan algoritma ETKDGv3.

    Parameters
    ----------
    mol : Chem.Mol atau str
        Molekul input (RDKit Mol, SMILES, atau blok SDF).
    n : int, default 30
        Jumlah konformer maksimum yang dibangkitkan.
    prune : float, default 0.5
        Ambang pemangkasan RMSD (Å). Konformer yang berjarak RMSD < prune terhadap
        konformer sebelumnya akan disingkirkan untuk menjaga keragaman.
    seed : int, default 42
        Benih bilangan acak untuk reprodusibilitas.

    Returns
    -------
    Chem.Mol
        Molekul dengan konformer 3D yang telah dibangkitkan.
    """
    if isinstance(mol, str):
        teks = mol.strip()
        if "\n" in teks or "$$$$" in teks:
            m = Chem.MolFromMolBlock(teks.split("$$$$")[0], removeHs=False, sanitize=True)
        else:
            m = Chem.MolFromSmiles(teks.split()[0])
            if m:
                m = Chem.AddHs(m)
        if m is None:
            raise ValueError("Struktur molekul tidak dapat diurai")
    else:
        m = Chem.Mol(mol)

    if m.GetNumAtoms() == 0:
        return m

    # Pastikan memiliki hidrogen untuk koordinat 3D yang realistis
    try:
        m_hs = Chem.AddHs(m)
    except Exception:
        m_hs = m

    params = AllChem.ETKDGv3()
    params.pruneRmsThresh = float(prune)
    params.randomSeed = int(seed)

    cids = list(AllChem.EmbedMultipleConfs(m_hs, numConfs=n, params=params))
    if not cids:
        # Cadangan bila ETKDGv3 gagal (mis. molekul makrosiklik / kaku)
        cid = AllChem.EmbedMolecule(m_hs, AllChem.ETKDGv3())
        if cid < 0:
            cid = AllChem.EmbedMolecule(m_hs)
        if cid >= 0:
            cids = [cid]

    return m_hs if cids else m


def kueri_dari_pose(mol: Union[Chem.Mol, str],
                    protein: Optional[Union[Chem.Mol, str, Path]] = None,
                    fitur_aktif: Optional[Sequence[int]] = None,
                    toleransi: float = 1.0,
                    eksklusi: bool = True) -> Dict[str, Any]:
    """Ekstraksi kueri farmakofor 3D dari pose ligan dan volume eksklusi protein di sekitarnya.

    Parameters
    ----------
    mol : Chem.Mol atau str
        Pose ligan 3D acuan (harus memiliki konformer 3D).
    protein : Chem.Mol, str, Path, optional
        Struktur protein reseptor (teks PDB, berkas PDB, atau Mol) untuk menghitung
        volume eksklusi dalam radius 4.0 Å dari atom ligan.
    fitur_aktif : sequence of int, optional
        Daftar indeks fitur yang diaktifkan. Bila None, seluruh fitur diaktifkan.
    toleransi : float, default 1.0
        Toleransi spasial bawaan untuk tiap fitur farmakofor (Å).
    eksklusi : bool, default True
        Apakah menyertakan bola volume eksklusi dari atom berat protein sekitar.

    Returns
    -------
    dict:
        {
            "ref_mol": Chem.Mol,
            "fitur": list of dict,
            "eksklusi": list of dict,
            "toleransi": float,
            "n_fitur_aktif": int
        }
    """
    if isinstance(mol, str):
        teks = mol.strip()
        if "\n" in teks or "$$$$" in teks:
            m = Chem.MolFromMolBlock(teks.split("$$$$")[0], removeHs=False, sanitize=True)
        else:
            from .prep_ligan import mol_dari
            m = mol_dari(teks, "sdf")
    else:
        m = Chem.Mol(mol)

    if m is None or m.GetNumConformers() == 0:
        raise ValueError("Ligan acuan harus memiliki koordinat 3D")

    raw_fitur = kemiripan.fitur(m)
    aktif_set = set(fitur_aktif) if fitur_aktif is not None else None

    fitur_list = []
    for i, f in enumerate(raw_fitur):
        is_aktif = (i in aktif_set) if aktif_set is not None else True
        fitur_list.append({
            "id": i,
            "famili": f["famili"],
            "nama": f["nama"],
            "warna": f["warna"],
            "radius": f.get("radius", 0.6),
            "xyz": [round(float(c), 3) for c in f["xyz"]],
            "toleransi": round(float(toleransi), 2),
            "aktif": bool(is_aktif),
            "atom": f.get("atom", [])
        })

    # Volume eksklusi protein (atom berat protein dalam radius 4.0 Å dari ligan)
    eksklusi_list = []
    if eksklusi and protein:
        try:
            prot_coords = _koordinat_protein_berat(protein)
            if len(prot_coords) > 0:
                lig_coords = m.GetConformer().GetPositions()
                # Jarak berpasangan ligan vs protein
                diff = prot_coords[:, None, :] - lig_coords[None, :, :]
                dists = np.sqrt((diff ** 2).sum(axis=-1))
                min_dists = dists.min(axis=1)
                kontak = prot_coords[min_dists <= 4.0]

                # Saring agar tidak terlalu rapat (< 1.2 A satu sama lain)
                terpilih = []
                for p in kontak:
                    if not any(np.linalg.norm(p - q) < 1.2 for q in terpilih):
                        terpilih.append(p)
                        eksklusi_list.append({
                            "xyz": [round(float(c), 3) for c in p],
                            "radius": 1.2,
                            "jenis": "eksklusi",
                            "warna": "#888888"
                        })
        except Exception as e:
            catat.log.debug(f"Gagal mengekstrak volume eksklusi protein: {e}")

    n_aktif = sum(1 for f in fitur_list if f["aktif"])
    return {
        "ref_mol": m,
        "fitur": fitur_list,
        "eksklusi": eksklusi_list,
        "toleransi": float(toleransi),
        "n_fitur_aktif": n_aktif
    }


def _koordinat_protein_berat(protein: Union[Chem.Mol, str, Path]) -> np.ndarray:
    """Ambil koordinat atom berat (non-H) protein dari berkas, teks PDB, atau Mol."""
    coords = []
    if isinstance(protein, Path) or (isinstance(protein, str) and os.path.exists(protein)):
        with open(protein, "r", encoding="utf-8", errors="replace") as f:
            teks = f.read()
    elif isinstance(protein, str):
        teks = protein
    elif isinstance(protein, Chem.Mol):
        if protein.GetNumConformers() > 0:
            conf = protein.GetConformer()
            for a in protein.GetAtoms():
                if a.GetAtomicNum() > 1:
                    pos = conf.GetAtomPosition(a.GetIdx())
                    coords.append([pos.x, pos.y, pos.z])
            return np.array(coords) if coords else np.zeros((0, 3))
        teks = Chem.MolToPDBBlock(protein)
    else:
        return np.zeros((0, 3))

    for line in teks.splitlines():
        if line.startswith(("ATOM", "HETATM")):
            elem = line[76:78].strip().upper()
            if not elem and len(line) >= 14:
                elem = line[12:14].strip()
            if elem == "H":
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                coords.append([x, y, z])
            except ValueError:
                continue
    return np.array(coords) if coords else np.zeros((0, 3))


def cocokkan(kueri: Dict[str, Any],
             mol: Union[Chem.Mol, str],
             opt_param: float = 0.5,
             bobot_farma: float = 0.5,
             bobot_bentuk: float = 0.5,
             n_konf: int = 30,
             prune_rms: float = 0.5) -> Dict[str, Any]:
    """Cocokkan molekul kandidat terhadap kueri farmakofor 3D dan bentuk.

    Parameters
    ----------
    kueri : dict
        Kueri dari `kueri_dari_pose`.
    mol : Chem.Mol atau str
        Molekul kandidat (Mol, teks SDF, atau SMILES).
    opt_param : float, default 0.5
        Parameter optimasi rdShapeAlign (0.5 = bobot bentuk & warna seimbang).
    bobot_farma : float, default 0.5
        Bobot komponen skor farmakofor dalam skor akhir.
    bobot_bentuk : float, default 0.5
        Bobot komponen skor bentuk-warna dalam skor akhir.
    n_konf : int, default 30
        Jumlah konformer yang dibangkitkan bila mol belum memiliki koordinat 3D.
    prune_rms : float, default 0.5
        Ambang pemangkasan RMSD konformer.

    Returns
    -------
    dict:
        {
            "n_cocok": int,
            "n_aktif": int,
            "rmsd_fitur": float or None,
            "konformer_terbaik": int,
            "tanimoto_bentuk": float,
            "tanimoto_warna": float,
            "skor_bentuk_warna": float,
            "skor_farmakofor": float,
            "skor_akhir": float,
            "n_bentrok": int,
            "mol": Chem.Mol
        }
    """
    ref_mol = kueri.get("ref_mol")
    if ref_mol is None or ref_mol.GetNumConformers() == 0:
        raise ValueError("Kueri tidak memiliki molekul acuan 3D yang valid")

    # Siapkan kandidat mol
    if isinstance(mol, str):
        teks = mol.strip()
        if "\n" in teks or "$$$$" in teks:
            m = Chem.MolFromMolBlock(teks.split("$$$$")[0], removeHs=False, sanitize=True)
        else:
            m = Chem.MolFromSmiles(teks.split()[0])
            if m:
                m = Chem.AddHs(m)
        if m is None:
            return _hasil_kosong(kueri)
    else:
        m = Chem.Mol(mol)

    if m.GetNumConformers() == 0:
        m = konformer(m, n=n_konf, prune=prune_rms)

    if m.GetNumConformers() == 0:
        return _hasil_kosong(kueri, m)

    fitur_aktif = [f for f in kueri.get("fitur", []) if f.get("aktif", True)]
    n_aktif = len(fitur_aktif)
    eksklusi = kueri.get("eksklusi", [])
    tol_bawaan = float(kueri.get("toleransi", 1.0))

    terbaik_skor = -1.0
    terbaik_hasil = None
    terbaik_probe = None

    for conf in m.GetConformers():
        cid = conf.GetId()
        # Salinan berkonformer tunggal: kemiripan.fitur dan pemeriksaan eksklusi membaca
        # konformer bawaan, jadi konformer yang diselaraskan harus menjadi satu-satunya.
        probe = Chem.Mol(m, confId=cid)
        try:
            s, c = rdShapeAlign.AlignMol(ref_mol, probe, refConfId=-1, probeConfId=-1,
                                         useColors=True, opt_param=opt_param)
        except Exception:
            s, c = 0.0, 0.0

        s_score = float(max(0.0, min(1.0, s)))
        c_score = float(max(0.0, min(1.0, c)))
        skor_bw = 0.5 * s_score + 0.5 * c_score

        # Ekstraksi fitur probe yang telah terselaraskan
        try:
            p_feats = kemiripan.fitur(probe)
        except Exception:
            p_feats = []

        # Pencocokan fitur kueri aktif ke fitur probe
        n_cocok = 0
        sq_diffs = []
        for qf in fitur_aktif:
            fam = qf["famili"]
            q_xyz = np.asarray(qf["xyz"])
            tol = float(qf.get("toleransi", tol_bawaan))
            min_d = 999.0
            for pf in p_feats:
                if pf["famili"] == fam:
                    d = float(np.linalg.norm(q_xyz - np.asarray(pf["xyz"])))
                    if d < min_d:
                        min_d = d
            if min_d <= tol:
                n_cocok += 1
                sq_diffs.append(min_d ** 2)

        rmsd_fitur = float(np.sqrt(np.mean(sq_diffs))) if sq_diffs else None

        # Evaluasi bentrokan dengan bola volume eksklusi
        n_bentrok = 0
        if eksklusi:
            try:
                conf = probe.GetConformer()
                heavy_pos = [conf.GetAtomPosition(a.GetIdx()) for a in probe.GetAtoms() if a.GetAtomicNum() > 1]
                for e in eksklusi:
                    e_xyz = np.asarray(e["xyz"])
                    r_sph = float(e.get("radius", 1.2))
                    if any(np.linalg.norm(np.array([p.x, p.y, p.z]) - e_xyz) < r_sph for p in heavy_pos):
                        n_bentrok += 1
            except Exception:
                pass

        # Hitung skor farmakofor ternormalisasi (0.0 - 1.0)
        if n_aktif > 0:
            rasio_cocok = n_cocok / n_aktif
            if rmsd_fitur is not None:
                presisi = max(0.0, 1.0 - (rmsd_fitur / (2.0 * max(0.1, tol_bawaan))))
            else:
                presisi = 0.0
            skor_farma = rasio_cocok * presisi
            if n_bentrok > 0:
                skor_farma *= max(0.0, 1.0 - 0.15 * n_bentrok)
        else:
            skor_farma = 0.0

        skor_farma = float(max(0.0, min(1.0, skor_farma)))

        # Skor gabungan akhir
        skor_akhir = bobot_farma * skor_farma + bobot_bentuk * skor_bw
        skor_akhir = float(max(0.0, min(1.0, skor_akhir)))

        if skor_akhir > terbaik_skor or terbaik_hasil is None:
            terbaik_skor = skor_akhir
            terbaik_probe = probe
            terbaik_hasil = {
                "n_cocok": n_cocok,
                "n_aktif": n_aktif,
                "rmsd_fitur": round(rmsd_fitur, 3) if rmsd_fitur is not None else None,
                "konformer_terbaik": cid,
                "tanimoto_bentuk": round(s_score, 4),
                "tanimoto_warna": round(c_score, 4),
                "skor_bentuk_warna": round(skor_bw, 4),
                "skor_farmakofor": round(skor_farma, 4),
                "skor_akhir": round(skor_akhir, 4),
                "n_bentrok": n_bentrok
            }

    # terbaik_probe sudah berkonformer tunggal dan terselaraskan
    terbaik_hasil["mol"] = Chem.Mol(terbaik_probe)
    return terbaik_hasil


def _hasil_kosong(kueri: Dict[str, Any], mol: Optional[Chem.Mol] = None) -> Dict[str, Any]:
    n_aktif = sum(1 for f in kueri.get("fitur", []) if f.get("aktif", True))
    return {
        "n_cocok": 0,
        "n_aktif": n_aktif,
        "rmsd_fitur": None,
        "konformer_terbaik": -1,
        "tanimoto_bentuk": 0.0,
        "tanimoto_warna": 0.0,
        "skor_bentuk_warna": 0.0,
        "skor_farmakofor": 0.0,
        "skor_akhir": 0.0,
        "n_bentrok": 0,
        "mol": mol
    }


def _proses_kelompok_500(kueri_dict: Dict[str, Any],
                         kelompok: List[Dict[str, Any]],
                         opt_param: float,
                         bobot_farma: float,
                         bobot_bentuk: float,
                         konf_per_mol: int) -> List[Dict[str, Any]]:
    """Fungsi pekerja per kelompok 500 senyawa untuk ProcessPoolExecutor."""
    hasil_list = []
    for item in kelompok:
        nama = item.get("nama") or item.get("id") or "Senyawa"
        smi = item.get("smiles") or item.get("canonical_smiles") or ""
        mol = item.get("mol")
        target = mol if mol is not None else smi
        if not target:
            continue
        try:
            res = cocokkan(kueri_dict, target, opt_param=opt_param,
                           bobot_farma=bobot_farma, bobot_bentuk=bobot_bentuk,
                           n_konf=konf_per_mol)
            # Jangan kembalikan RDKit Mol utuh bila hanya data tabel (hemat memori IPC)
            # Konversi mol ke blok SDF ringkas
            mol_out = res.pop("mol", None)
            sdf_blok = Chem.MolToMolBlock(mol_out) if mol_out is not None else ""
            res["nama"] = nama
            res["smiles"] = smi
            res["sdf"] = sdf_blok
            hasil_list.append(res)
        except Exception:
            continue
    return hasil_list


def saring_pustaka(kueri: Dict[str, Any],
                   daftar: Sequence[Union[Dict[str, Any], str, Tuple[str, str]]],
                   n_proses: Optional[int] = None,
                   batal: Optional[Any] = None,
                   progres: Optional[Callable[[int, int, str], None]] = None,
                   bobot_farma: float = 0.5,
                   bobot_bentuk: float = 0.5,
                   opt_param: float = 0.5,
                   konf_per_mol: int = 30) -> List[Dict[str, Any]]:
    """Tapis pustaka senyawa secara paralel dalam kelompok 500 senyawa.

    Parameters
    ----------
    kueri : dict
        Kueri farmakofor 3D dari `kueri_dari_pose`.
    daftar : list
        Daftar senyawa (berupa dict {"nama", "smiles"}, tuple (nama, smiles), atau string SMILES).
    n_proses : int, optional
        Jumlah proses worker paralel (bawaan: jumlah CPU yang tersedia).
    batal : threading.Event atau Callable[[], bool], optional
        Pemicu pembatalan penapisan.
    progres : callable, optional
        Fungsi pemanggil progres (selesai, total, pesan).
    bobot_farma : float, default 0.5
        Bobot komponen skor farmakofor.
    bobot_bentuk : float, default 0.5
        Bobot komponen skor bentuk-warna.
    opt_param : float, default 0.5
        Keseimbangan bentuk vs warna dalam rdShapeAlign.
    konf_per_mol : int, default 30
        Jumlah konformer yang diuji per senyawa.

    Returns
    -------
    list of dict
        Hasil penapisan terurut dari skor_akhir tertinggi.
    """
    # Standarisasi daftar menjadi list of dict
    standar_daftar = []
    for item in daftar:
        if isinstance(item, dict):
            standar_daftar.append(item)
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            standar_daftar.append({"nama": str(item[0]), "smiles": str(item[1])})
        elif isinstance(item, str):
            standar_daftar.append({"nama": item.split()[0], "smiles": item.split()[0]})

    total = len(standar_daftar)
    if total == 0:
        return []

    def _cek_batal():
        if batal is None:
            return False
        if callable(batal):
            return batal()
        return getattr(batal, "is_set", lambda: False)()

    max_workers = n_proses or max(1, min(os.cpu_count() or 4, 16))
    # Kelompok paling banyak 500 senyawa, tetapi cukup kecil agar semua proses kebagian
    # (~4 kelompok per proses) dan kegagalan satu kelompok tidak menggugurkan ratusan senyawa.
    ukuran_kelompok = max(10, min(500, -(-total // (max_workers * 4))))
    kelompok_list = [
        standar_daftar[i:i + ukuran_kelompok]
        for i in range(0, total, ukuran_kelompok)
    ]

    semua_hasil = []
    selesai_hitung = 0

    if total <= 200 or max_workers <= 1:
        # Jalankan serial untuk himpunan kecil tanpa overhead multiprocessing
        for kel in kelompok_list:
            if _cek_batal():
                break
            res = _proses_kelompok_500(kueri, kel, opt_param, bobot_farma, bobot_bentuk, konf_per_mol)
            semua_hasil.extend(res)
            selesai_hitung += len(kel)
            if progres:
                progres(selesai_hitung, total, f"{selesai_hitung:,} / {total:,} senyawa...")
    else:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_proses_kelompok_500, kueri, kel, opt_param,
                                bobot_farma, bobot_bentuk, konf_per_mol): len(kel)
                for kel in kelompok_list
            }
            for fut in as_completed(futures):
                if _cek_batal():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    res = fut.result()
                    semua_hasil.extend(res)
                except Exception as e:
                    catat.log.warning(f"Kelompok penapisan gagal ({type(e).__name__}): {e}")
                selesai_hitung += futures[fut]
                if progres:
                    progres(selesai_hitung, total, f"{selesai_hitung:,} / {total:,} senyawa...")

    # Urutkan berdasarkan skor_akhir menurun
    semua_hasil.sort(key=lambda x: -x.get("skor_akhir", 0.0))
    for rank, h in enumerate(semua_hasil, 1):
        h["rank"] = rank

    return semua_hasil


def validasi_kueri(kueri: Dict[str, Any],
                   aktif: Sequence[Union[Dict[str, Any], str]],
                   decoy: Sequence[Union[Dict[str, Any], str]],
                   bobot_farma: float = 0.5,
                   bobot_bentuk: float = 0.5,
                   konf_per_mol: int = 30,
                   n_proses: Optional[int] = None) -> Dict[str, Any]:
    """Hitung metrik validasi diskriminasi kueri (ROC-AUC, BEDROC, EF) dari hasil nyata aktif vs decoy.

    Senyawa dinilai lewat `saring_pustaka` (paralel bila > 200 senyawa). EF1% hanya dilaporkan
    bila himpunan >= 100 senyawa; di bawahnya 1 % teratas kurang dari satu senyawa sehingga
    angkanya hanya cerminan rasio aktif:decoy.

    Returns
    -------
    dict: {"auc", "bedroc", "ef1", "ef5", "n_aktif", "n_decoy", "n_gagal", "skor_aktif",
           "skor_decoy", "pesan"}
    """
    def _hasil_kosong_val(pesan, n_gagal=0):
        return {"auc": None, "bedroc": None, "ef1": None, "ef5": None, "n_aktif": len(aktif),
                "n_decoy": len(decoy), "n_gagal": n_gagal, "skor_aktif": [], "skor_decoy": [],
                "pesan": pesan}

    if len(aktif) < 2 or len(decoy) < 2:
        return _hasil_kosong_val("Butuh minimal 2 senyawa aktif dan 2 umpan (decoy) untuk validasi kueri.")

    def _baku(item, label, i):
        if isinstance(item, dict):
            d = {k: item[k] for k in ("mol", "smiles") if item.get(k) is not None}
        else:
            d = {"smiles": str(item)}
        d["nama"] = f"{label}{i}"
        return d

    daftar = ([_baku(x, "A", i) for i, x in enumerate(aktif)] +
              [_baku(x, "D", i) for i, x in enumerate(decoy)])
    hasil = saring_pustaka(kueri, daftar, n_proses=n_proses, bobot_farma=bobot_farma,
                           bobot_bentuk=bobot_bentuk, konf_per_mol=konf_per_mol)
    skor = {h["nama"]: h["skor_akhir"] for h in hasil}
    # Senyawa yang gagal diproses (struktur tak terurai / tanpa konformer) dicatat, bukan diberi skor 0
    skor_aktif = [skor[d["nama"]] for d in daftar if d["nama"].startswith("A") and d["nama"] in skor]
    skor_decoy = [skor[d["nama"]] for d in daftar if d["nama"].startswith("D") and d["nama"] in skor]
    n_gagal = len(daftar) - len(skor_aktif) - len(skor_decoy)
    if len(skor_aktif) < 2 or len(skor_decoy) < 2:
        return _hasil_kosong_val(f"Terlalu banyak senyawa gagal diproses ({n_gagal}).", n_gagal)

    # Skor farmakofor: skor lebih tinggi = lebih baik -> rendah_positif=False
    roc_res = uji.roc(skor_decoy, skor_aktif, rendah_positif=False)
    if "galat" in roc_res:
        return _hasil_kosong_val(roc_res["galat"], n_gagal)

    n_total = len(skor_aktif) + len(skor_decoy)
    ef = roc_res.get("ef", {})
    auc_val = round(float(roc_res["auc"]), 3)
    bedroc_val = round(float(roc_res["bedroc"]), 3)
    ef1_val = round(float(ef[1]), 2) if n_total >= 100 and 1 in ef else None
    ef5_val = round(float(ef[5]), 2) if n_total >= 20 and 5 in ef else None

    bagian = [f"{len(skor_aktif)} aktif vs {len(skor_decoy)} decoy", f"AUC {uji.f_angka(auc_val, 3)}",
              f"BEDROC {uji.f_angka(bedroc_val, 3)}"]
    if ef1_val is not None:
        bagian.append(f"EF1% {uji.f_angka(ef1_val, 1)}×")
    if ef5_val is not None:
        bagian.append(f"EF5% {uji.f_angka(ef5_val, 1)}×")
    if n_gagal:
        bagian.append(f"{n_gagal} senyawa gagal diproses")
    pesan = " · ".join(bagian)
    if n_total < 100:
        pesan += ". Himpunan < 100 senyawa: EF1% tidak dilaporkan dan metrik masih kasar."

    return {"auc": auc_val, "bedroc": bedroc_val, "ef1": ef1_val, "ef5": ef5_val,
            "n_aktif": len(skor_aktif), "n_decoy": len(skor_decoy), "n_gagal": n_gagal,
            "skor_aktif": skor_aktif, "skor_decoy": skor_decoy, "pesan": pesan}

