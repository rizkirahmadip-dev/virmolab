"""Pembuat decoy gaya DUD-E lokal dan pemilihan senyawa aktif beragam kerangka.

Menghasilkan decoy fisikokimia yang cocok (MW, logP, HBD, HBA, rotatable bonds, muatan bersih)
namun secara topologis berbeda (Tanimoto ECFP4 < 0,3 ke semua aktif).
Dilengkapi evaluasi kemiripan sifat aktif vs decoy menggunakan uji Kolmogorov-Smirnov (KS).
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import Descriptors, rdFingerprintGenerator, rdMolDescriptors
from rdkit.ML.Cluster import Butina
from scipy import stats

from . import catat, chembl, pustaka

RDLogger.DisableLog("rdApp.*")

_gen_morgan = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


@dataclass
class SifatMolekul:
    """Deskriptor fisikokimia untuk pencocokan decoy ala DUD-E."""
    mw: float
    logp: float
    hbd: int
    hba: int
    rotb: int
    muatan: int
    smiles: str
    nama: str = ""
    chembl_id: str = ""
    pchembl: Optional[float] = None


def hitung_sifat(mol_or_smi: Any, nama: str = "", cid: str = "", pchembl: Optional[float] = None) -> Optional[Tuple[SifatMolekul, Any]]:
    """Hitung sifat fisikokimia dan sidik jari Morgan2 dari molekul RDKit atau string SMILES.

    Kembalikan (SifatMolekul, ExplicitBitVect) atau None jika tidak valid.
    """
    if isinstance(mol_or_smi, str):
        mol = Chem.MolFromSmiles(mol_or_smi)
    else:
        mol = mol_or_smi

    if mol is None or mol.GetNumHeavyAtoms() < 4:
        return None

    try:
        mw = float(Descriptors.MolWt(mol))
        logp = float(Descriptors.MolLogP(mol))
        hbd = int(rdMolDescriptors.CalcNumHBD(mol))
        hba = int(rdMolDescriptors.CalcNumHBA(mol))
        rotb = int(rdMolDescriptors.CalcNumRotatableBonds(mol))
        muatan = int(Chem.GetFormalCharge(mol))
        smi = Chem.MolToSmiles(mol, isomericSmiles=True)
        fp = _gen_morgan.GetFingerprint(mol)

        sifat = SifatMolekul(
            mw=round(mw, 2),
            logp=round(logp, 2),
            hbd=hbd,
            hba=hba,
            rotb=rotb,
            muatan=muatan,
            smiles=smi,
            nama=nama or smi,
            chembl_id=cid,
            pchembl=pchembl,
        )
        return sifat, fp
    except Exception as e:
        catat.log.debug(f"Gagal hitung sifat molekul: {e}")
        return None


def pilih_aktif(target_chembl: str,
                pchembl_min: float = 7.0,
                maks: int = 50,
                lapor: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Ambil senyawa aktif target ChEMBL dan pilih representatif beragam kerangka (Butina 0,6 pada Morgan2).

    target_chembl: ID target ChEMBL (mis. 'CHEMBL243' atau teks target).
    pchembl_min: ambang batas pChEMBL minimal (bawaan 7.0 = 100 nM).
    maks: jumlah maksimal senyawa aktif beragam kerangka (bawaan 50).
    """
    log = (lambda s: lapor.log.emit(s)) if lapor and hasattr(lapor, "log") else (lambda s: catat.log.info(s))
    log(f"Mengambil bioaktivitas ChEMBL untuk target {target_chembl}...")

    # Pastikan ID target berupa CHEMBL ID
    t_id = target_chembl.strip()
    if not t_id.upper().startswith("CHEMBL"):
        target_list = chembl.cari_target(t_id)
        if not target_list:
            raise ValueError(f"Target '{target_chembl}' tidak ditemukan di ChEMBL.")
        t_id = target_list[0]["chembl"]

    baris = chembl.aktivitas(t_id, maks=1500, lapor=lapor)
    if not baris:
        raise ValueError(f"Tidak ada data aktivitas untuk target {t_id}.")

    ringkas = chembl.ringkas_senyawa(baris)
    aktif_mentah = [r for r in ringkas if (r.get("pchembl") or 0.0) >= pchembl_min]
    if not aktif_mentah:
        # Fallback relaksasi jika sangat sedikit
        aktif_mentah = sorted(ringkas, key=lambda r: -(r.get("pchembl") or 0.0))[:maks * 2]

    mols_data = []
    for r in aktif_mentah:
        res = hitung_sifat(r["smiles"], nama=r["nama"], cid=r["chembl"], pchembl=r["pchembl"])
        if res is not None:
            sifat, fp = res
            mols_data.append((sifat, fp))

    if not mols_data:
        raise ValueError("Tidak ada molekul aktif yang valid untuk target ini.")

    n = len(mols_data)
    log(f"Melakukan klasterisasi Butina (ambang 0,6) pada {n} calon senyawa aktif...")

    if n == 1:
        s0, fp0 = mols_data[0]
        return [{
            "id": s0.chembl_id or "ACT_1",
            "nama": s0.nama,
            "smiles": s0.smiles,
            "pchembl": s0.pchembl,
            "mw": s0.mw,
            "logp": s0.logp,
            "hbd": s0.hbd,
            "hba": s0.hba,
            "rotb": s0.rotb,
            "muatan": s0.muatan,
        }]

    # Matriks jarak untuk Butina
    fps = [fp for _, fp in mols_data]
    jarak = []
    for i in range(1, n):
        sims = DataStructs.BulkTanimotoSimilarity(fps[i], fps[:i])
        jarak.extend([1.0 - s for s in sims])

    # Butina clustering dengan cutoff jarak 1 - 0.6 = 0.4
    klaster = Butina.ClusterData(jarak, n, 0.4, isDistData=True, reordering=True)

    terpilih = []
    for c in klaster:
        # Pilih yang memiliki pChEMBL tertinggi di klaster tersebut (atau pusat klaster c[0])
        sub_indices = list(c)
        sub_indices.sort(key=lambda idx: -(mols_data[idx][0].pchembl or 0.0))
        terpilih_idx = sub_indices[0]
        s, _ = mols_data[terpilih_idx]
        terpilih.append({
            "id": s.chembl_id or f"ACT_{len(terpilih) + 1}",
            "nama": s.nama,
            "smiles": s.smiles,
            "pchembl": s.pchembl,
            "mw": s.mw,
            "logp": s.logp,
            "hbd": s.hbd,
            "hba": s.hba,
            "rotb": s.rotb,
            "muatan": s.muatan,
            "ukuran_klaster": len(c),
        })
        if len(terpilih) >= maks:
            break

    log(f"Terpilih {len(terpilih)} senyawa aktif dengan kerangka molekul beragam.")
    return terpilih


def ambil_kumpulan_bawaan(batas: int = 5000) -> List[Dict[str, Any]]:
    """Ambil calon molekul decoy dari database lokal (obat disetujui ChEMBL dan COCONUT)."""
    kumpulan = []
    # 1. Obat disetujui lokal
    try:
        daftar_obat = pustaka.obat()
        for o in daftar_obat:
            kumpulan.append({"id": o["id"], "nama": o["nama"], "smiles": o["smiles"]})
    except Exception as e:
        catat.log.debug(f"Tidak dapat memuat obat disetujui: {e}")

    # 2. COCONUT lokal jika tersedia
    try:
        if pustaka.coconut_ada():
            baris_coco = pustaka.cari_coconut(batas=batas, acak=True)
            for c in baris_coco:
                kumpulan.append({"id": c.get("id", "COCO"), "nama": c.get("nama", ""), "smiles": c.get("smiles", "")})
    except Exception as e:
        catat.log.debug(f"Tidak dapat memuat COCONUT lokal: {e}")

    return kumpulan


def buat_decoy(aktif: List[Dict[str, Any]],
               kumpulan: Optional[List[Dict[str, Any]]] = None,
               per_aktif: int = 50,
               batas_tanimoto: float = 0.3,
               toleransi_mw: float = 25.0,
               toleransi_logp: float = 0.5,
               toleransi_hbd: int = 1,
               toleransi_hba: int = 1,
               toleransi_rotb: int = 1,
               lapor: Optional[Any] = None,
               benih: int = 42) -> Dict[str, Any]:
    """Hasilkan molekul decoy gaya DUD-E dari sekumpulan molekul dasar.

    Kriteria pencocokan:
    - MW ± 25 Da
    - logP ± 0,5
    - HBD ± 1
    - HBA ± 1
    - Rotatable bonds ± 1
    - Muatan bersih sama
    - Tanimoto Morgan2 ke SEMUA aktif < 0,3
    - Tanimoto ke decoy terpilih lain < 0,9 (mencegah redundansi decoy)

    Kembalikan dict memuat:
    - 'decoy': list decoy terpilih
    - 'statistik_sifat': ringkasan perbandingan sifat aktif vs decoy (rata ± SD, uji KS)
    - 'peringatan': daftar peringatan bila jumlah decoy kurang dari target
    """
    log = (lambda s: lapor.log.emit(s)) if lapor and hasattr(lapor, "log") else (lambda s: catat.log.info(s))

    if not aktif:
        raise ValueError("Daftar molekul aktif tidak boleh kosong.")

    # 1. Parse dan hitung sifat semua aktif
    aktif_parsed = []
    for a in aktif:
        smi = a.get("smiles") if isinstance(a, dict) else str(a)
        nama = a.get("nama", "") if isinstance(a, dict) else ""
        cid = a.get("id", "") if isinstance(a, dict) else ""
        res = hitung_sifat(smi, nama=nama, cid=cid)
        if res is not None:
            aktif_parsed.append(res)

    if not aktif_parsed:
        raise ValueError("Tidak ada molekul aktif dengan struktur SMILES valid.")

    fps_aktif = [fp for _, fp in aktif_parsed]
    sifat_aktif = [s for s, _ in aktif_parsed]

    # 2. Siapkan kumpulan calon decoy
    if kumpulan is None:
        kumpulan = ambil_kumpulan_bawaan()

    if not kumpulan:
        raise ValueError("Kumpulan calon decoy kosong. Unduh sampel molekul terlebih dahulu.")

    log(f"Memproses {len(kumpulan)} molekul calon decoy untuk {len(aktif_parsed)} senyawa aktif...")

    calon_parsed = []
    inchikeys_terlihat = set()

    # Cegah memasukkan aktif itu sendiri ke calon decoy
    for s, _ in aktif_parsed:
        try:
            m = Chem.MolFromSmiles(s.smiles)
            if m:
                inchikeys_terlihat.add(Chem.MolToInchiKey(m)[:14])
        except Exception:
            pass

    for k in kumpulan:
        smi = k.get("smiles") if isinstance(k, dict) else str(k)
        nama = k.get("nama", "") if isinstance(k, dict) else ""
        cid = k.get("id", "") if isinstance(k, dict) else ""
        res = hitung_sifat(smi, nama=nama, cid=cid)
        if res is None:
            continue
        s, fp = res
        try:
            m = Chem.MolFromSmiles(s.smiles)
            ik14 = Chem.MolToInchiKey(m)[:14] if m else ""
            if ik14 in inchikeys_terlihat:
                continue
            inchikeys_terlihat.add(ik14)
        except Exception:
            pass
        calon_parsed.append((s, fp))

    log(f"Tersedia {len(calon_parsed)} molekul unik calon decoy yang valid.")

    decoy_terpilih: List[Dict[str, Any]] = []
    fps_decoy_terpilih = []
    target_total = len(aktif_parsed) * per_aktif

    # Pemilihan decoy: kandidat diacak (benih tetap -> dapat diulang), lalu tiap kandidat diberikan ke aktif yang
    # sifat fisikokimianya cocok dan decoy-nya paling sedikit. Dengan begitu jumlah decoy per aktif seimbang dan tidak
    # bergantung urutan basis data (seperti DUD-E yang memilih acak dari kandidat yang sifatnya cocok).
    import random
    acak = random.Random(benih)
    acak.shuffle(calon_parsed)
    jumlah = [0] * len(aktif_parsed)
    for s_cand, fp_cand in calon_parsed:
        if all(j >= per_aktif for j in jumlah):
            break

        # 1. Aktif yang masih butuh decoy dan sifatnya cocok (kriteria DUD-E)
        pasangan = [i for i, (s_act, _) in enumerate(aktif_parsed)
                    if jumlah[i] < per_aktif
                    and abs(s_cand.mw - s_act.mw) <= toleransi_mw
                    and abs(s_cand.logp - s_act.logp) <= toleransi_logp
                    and abs(s_cand.hbd - s_act.hbd) <= toleransi_hbd
                    and abs(s_cand.hba - s_act.hba) <= toleransi_hba
                    and abs(s_cand.rotb - s_act.rotb) <= toleransi_rotb
                    and s_cand.muatan == s_act.muatan]
        if not pasangan:
            continue

        # 2. Disimilaritas topologi ke SEMUA aktif (< batas_tanimoto)
        sims_aktif = DataStructs.BulkTanimotoSimilarity(fp_cand, fps_aktif)
        maks_sim_aktif = max(sims_aktif) if sims_aktif else 0.0
        if maks_sim_aktif >= batas_tanimoto:
            continue

        # 3. Diversitas antar decoy terpilih (< 0,9)
        if fps_decoy_terpilih and max(DataStructs.BulkTanimotoSimilarity(fp_cand, fps_decoy_terpilih)) >= 0.90:
            continue

        i_act = min(pasangan, key=lambda i: jumlah[i])
        s_act = aktif_parsed[i_act][0]
        decoy_terpilih.append({
            "id": s_cand.chembl_id or f"DECOY_{len(decoy_terpilih) + 1}",
            "nama": s_cand.nama or f"Decoy {len(decoy_terpilih) + 1}",
            "smiles": s_cand.smiles,
            "pasangan_aktif": s_act.nama or s_act.smiles,
            "mw": s_cand.mw,
            "logp": s_cand.logp,
            "hbd": s_cand.hbd,
            "hba": s_cand.hba,
            "rotb": s_cand.rotb,
            "muatan": s_cand.muatan,
            "tanimoto_maks_aktif": round(maks_sim_aktif, 3),
        })
        fps_decoy_terpilih.append(fp_cand)
        jumlah[i_act] += 1

    peringatan = [
        "Decoy diambil dari obat disetujui dan produk alam, bukan senyawa mirip obat ZINC seperti DUD-E. "
        "Pencocokan sifat tidak menghapus perbedaan topologi, sehingga enrichment bisa terlalu optimistis; "
        "obat disetujui juga dapat mencakup ligan sungguhan untuk target yang sama. Nilai AUC/BEDROC dibaca sebagai "
        "perkiraan atas, bukan setara DUD-E."
    ]
    if min(jumlah) < per_aktif:
        kurang = [aktif_parsed[i][0].nama or aktif_parsed[i][0].smiles for i, j in enumerate(jumlah) if j < per_aktif]
        peringatan.append(f"{len(kurang)} aktif belum mencapai {per_aktif} decoy (kumpulan kandidat terbatas): "
                          + ", ".join(kurang[:5]) + (" …" if len(kurang) > 5 else ""))
    if len(decoy_terpilih) < target_total:
        peringatan.append(
            f"Jumlah decoy yang ditemukan ({len(decoy_terpilih)}) kurang dari target ideal ({target_total}). "
            f"Diperoleh rata-rata {len(decoy_terpilih) / max(1, len(aktif_parsed)):.1f} decoy per aktif."
        )

    # 3. Evaluasi kemiripan sifat aktif vs decoy menggunakan uji KS
    statistik_sifat = evaluasi_bias_sifat(sifat_aktif, [
        SifatMolekul(
            mw=d["mw"], logp=d["logp"], hbd=d["hbd"], hba=d["hba"],
            rotb=d["rotb"], muatan=d["muatan"], smiles=d["smiles"]
        ) for d in decoy_terpilih
    ])

    return {
        "decoy": decoy_terpilih,
        "n_aktif": len(aktif_parsed),
        "n_decoy": len(decoy_terpilih),
        "rasio": round(len(decoy_terpilih) / max(1, len(aktif_parsed)), 1),
        "statistik_sifat": statistik_sifat,
        "peringatan": peringatan,
    }


def evaluasi_bias_sifat(aktif_list: List[SifatMolekul],
                        decoy_list: List[SifatMolekul]) -> Dict[str, Any]:
    """Lakukan uji Kolmogorov-Smirnov (KS-test) antara populasi aktif dan decoy untuk setiap sifat fisikokimia."""
    sifat_kunci = [("mw", "Berat Molekul (MW)"),
                   ("logp", "LogP"),
                   ("hbd", "Donor Ikatan H (HBD)"),
                   ("hba", "Akseptor Ikatan H (HBA)"),
                   ("rotb", "Ikatan Berputar"),
                   ("muatan", "Muatan Bersih")]

    hasil = {}
    if not aktif_list or not decoy_list:
        return hasil

    for k, label in sifat_kunci:
        val_aktif = [getattr(s, k) for s in aktif_list]
        val_decoy = [getattr(s, k) for s in decoy_list]

        m_a = float(np.mean(val_aktif))
        sd_a = float(np.std(val_aktif, ddof=1)) if len(val_aktif) > 1 else 0.0

        m_d = float(np.mean(val_decoy))
        sd_d = float(np.std(val_decoy, ddof=1)) if len(val_decoy) > 1 else 0.0

        if len(set(val_aktif)) > 1 or len(set(val_decoy)) > 1:
            ks_res = stats.ks_2samp(val_aktif, val_decoy)
            d_stat = float(ks_res.statistic)
            p_val = float(ks_res.pvalue)
        else:
            d_stat = 0.0
            p_val = 1.0

        hasil[k] = {
            "label": label,
            "aktif_rerata": round(m_a, 2),
            "aktif_sd": round(sd_a, 2),
            "decoy_rerata": round(m_d, 2),
            "decoy_sd": round(sd_d, 2),
            "ks_d": round(d_stat, 3),
            "ks_p": round(p_val, 4),
            "bias": bool(p_val < 0.05),
        }

    return hasil
