"""Konsensus docking × co-folding (Boltz-2).

Modul ini mengintegrasikan prediksi struktur kompleks protein-ligan berbasis AI (Boltz-2)
dengan pose docking berbasis fisika (Vina/GNINA):
1. Membaca koordinat keluaran Boltz-2 (PDB/CIF) dan metrik afinitas (affinity_*.json).
2. Menyelaraskan koordinat kompleks co-folding ke sistem koordinat reseptor proyek (Kabsch Cα).
3. Menghitung RMSD atom berat simetris antara pose docking dan pose co-folding terselaraskan.
4. Mengevaluasi validitas fisik kedua pose dengan PoseBusters (stereokimia, bentrok sterik, geometri).
5. Membandingkan pola interaksi protein-ligan (Interaction Fingerprint / IFP Tanimoto).
6. Menetapkan label kesepakatan objektif: Sepakat | Sebagian | Bertentangan.
7. Memeriksa kebaruan ligan terhadap basis data PDB (Tanimoto < 0,3 -> peringatan kebaruan).
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, DataStructs

from . import analisis, catat, qc, sumber_data, validasi_protokol

AMBANG_RMSD_SEPAKAT = 2.0
AMBANG_IFP_SEBAGIAN = 0.6
AMBANG_KEBARUAN_RENDAH = 0.3


@dataclass
class HasilKofolding:
    """Hasil analisis komparatif docking vs co-folding Boltz-2."""
    tersedia: bool
    pesan: str = ""
    rmsd: Optional[float] = None
    rmsd_ca: Optional[float] = None
    n_ca: int = 0
    ifp_tanimoto: Optional[float] = None
    posebusters_docking: Optional[Dict[str, Any]] = None
    posebusters_cofold: Optional[Dict[str, Any]] = None
    kesepakatan: str = "–"
    kebaruan: Optional[float] = None
    peringatan_kebaruan: str = ""
    afinitas_pred_value: Optional[float] = None
    afinitas_probabilitas: Optional[float] = None
    complex_plddt: Optional[float] = None
    ligand_iptm: Optional[float] = None
    pdb_kompleks_terselaraskan: str = ""
    pdb_ligan_terselaraskan: str = ""
    rincian: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tersedia": self.tersedia,
            "pesan": self.pesan,
            "rmsd": self.rmsd,
            "rmsd_ca": self.rmsd_ca,
            "n_ca": self.n_ca,
            "ifp_tanimoto": self.ifp_tanimoto,
            "posebusters_docking": self.posebusters_docking,
            "posebusters_cofold": self.posebusters_cofold,
            "kesepakatan": self.kesepakatan,
            "kebaruan": self.kebaruan,
            "peringatan_kebaruan": self.peringatan_kebaruan,
            "afinitas_pred_value": self.afinitas_pred_value,
            "afinitas_probabilitas": self.afinitas_probabilitas,
            "complex_plddt": self.complex_plddt,
            "ligand_iptm": self.ligand_iptm,
        }


def cari_berkas_boltz(folder_atau_berkas: Path) -> Dict[str, Optional[Path]]:
    """Temukan berkas PDB kompleks, affinity JSON, dan confidence JSON di folder keluaran Boltz."""
    jalur = Path(folder_atau_berkas)
    hasil: Dict[str, Optional[Path]] = {"pdb": None, "affinity": None, "confidence": None}

    if jalur.is_file():
        if jalur.suffix.lower() in (".pdb", ".cif", ".mmcif"):
            hasil["pdb"] = jalur
            folder = jalur.parent
        else:
            folder = jalur.parent
    else:
        folder = jalur

    if not folder.exists():
        return hasil

    # 1. Cari PDB / CIF model_0 atau yang pertama
    calon_pdb = sorted(folder.rglob("*_model_0.pdb")) or sorted(folder.rglob("*.pdb"))
    if not calon_pdb:
        calon_pdb = sorted(folder.rglob("*_model_0.cif")) or sorted(folder.rglob("*.cif"))
    if calon_pdb:
        hasil["pdb"] = calon_pdb[0]

    # 2. Cari affinity_*.json
    calon_aff = sorted(folder.rglob("affinity_*.json")) or sorted(folder.rglob("*affinity*.json"))
    if calon_aff:
        hasil["affinity"] = calon_aff[0]

    # 3. Cari confidence_*.json
    calon_conf = sorted(folder.rglob("confidence_*_model_0.json")) or sorted(folder.rglob("*confidence*.json"))
    if calon_conf:
        hasil["confidence"] = calon_conf[0]

    return hasil


def baca_keluaran_boltz(folder_atau_berkas: Path) -> Dict[str, Any]:
    """Baca struktur koordinat dan metrik afinitas/keyakinan dari keluaran Boltz-2."""
    berkas = cari_berkas_boltz(folder_atau_berkas)
    if not berkas["pdb"] or not berkas["pdb"].exists():
        raise FileNotFoundError(f"Struktur PDB/CIF keluaran Boltz tidak ditemukan di {folder_atau_berkas}")

    teks_pdb = berkas["pdb"].read_text(encoding="utf-8", errors="replace")

    afinitas_pred = None
    afinitas_prob = None
    if berkas["affinity"] and berkas["affinity"].exists():
        try:
            d_aff = json.loads(berkas["affinity"].read_text(encoding="utf-8"))
            afinitas_pred = d_aff.get("affinity_pred_value")
            afinitas_prob = d_aff.get("affinity_probability_binary")
            # Nama kunci mengikuti skema Boltz-2 yang terdokumentasi. Bila rilis Boltz memakai nama
            # lain, berkas terbaca tetapi nilainya kosong; sebut kunci yang benar-benar ada agar
            # penyebabnya terlihat, bukan tampil "-" tanpa alasan.
            if afinitas_pred is None and afinitas_prob is None:
                catat.log.warning(
                    f"Berkas afinitas Boltz {berkas['affinity'].name} tidak memuat kunci "
                    f"'affinity_pred_value' / 'affinity_probability_binary'; kunci yang ada: "
                    f"{', '.join(sorted(d_aff)) or 'tidak ada'}")
        except Exception as e:
            catat.log.warning(f"Gagal membaca berkas afinitas Boltz {berkas['affinity']}: {e}")

    complex_plddt = None
    ligand_iptm = None
    if berkas["confidence"] and berkas["confidence"].exists():
        try:
            d_conf = json.loads(berkas["confidence"].read_text(encoding="utf-8"))
            complex_plddt = d_conf.get("complex_plddt")
            ligand_iptm = d_conf.get("ligand_iptm") or d_conf.get("iptm")
        except Exception as e:
            catat.log.warning(f"Gagal membaca berkas keyakinan Boltz {berkas['confidence']}: {e}")

    # Pisahkan rantai protein dan ligan dari PDB
    baris_protein = []
    baris_ligan = []
    for b in teks_pdb.splitlines():
        if b.startswith("ATOM"):
            rantai = b[21:22].strip()
            resn = b[17:20].strip()
            # Di Boltz, ligan biasanya di chain L atau residu non-standar / HETATM
            if rantai == "L" or resn in ("LIG", "MK1", "UNL"):
                baris_ligan.append(b)
            else:
                baris_protein.append(b)
        elif b.startswith("HETATM"):
            resn = b[17:20].strip()
            if resn not in validasi_protokol._PELARUT_ION:
                baris_ligan.append(b)

    return {
        "teks_pdb": teks_pdb,
        "protein_pdb": "\n".join(baris_protein) + "\nEND\n" if baris_protein else "",
        "ligan_pdb": "\n".join(baris_ligan) + "\nEND\n" if baris_ligan else "",
        "afinitas_pred_value": float(afinitas_pred) if afinitas_pred is not None else None,
        "afinitas_probabilitas": float(afinitas_prob) if afinitas_prob is not None else None,
        "complex_plddt": float(complex_plddt) if complex_plddt is not None else None,
        "ligand_iptm": float(ligand_iptm) if ligand_iptm is not None else None,
    }


def sejajarkan_ke_reseptor(
    pdb_kompleks_boltz: str,
    pdb_reseptor_proyek: str,
    residu_kantong: Optional[List[Tuple[str, str, str]]] = None,
    minimal_ca: int = 15,
) -> Tuple[str, str, float, int]:
    """Sejajarkan struktur kompleks Boltz ke kerangka koordinat reseptor proyek via Cα Kabsch.

    Mengembalikan (kompleks_terselaraskan, ligan_terselaraskan, rmsd_ca, n_ca).
    Jika residu_kantong diberikan, superposisi difokuskan pada Cα residu kantong pengikatan.
    """
    ca_boltz = validasi_protokol._peta_ca(pdb_kompleks_boltz)
    ca_proyek = validasi_protokol._peta_ca(pdb_reseptor_proyek)

    if residu_kantong:
        himpunan_kantong = set(residu_kantong)
        ca_boltz_fokus = {k: v for k, v in ca_boltz.items() if k in himpunan_kantong}
        ca_proyek_fokus = {k: v for k, v in ca_proyek.items() if k in himpunan_kantong}
        if len(set(ca_boltz_fokus) & set(ca_proyek_fokus)) >= minimal_ca:
            ca_boltz = ca_boltz_fokus
            ca_proyek = ca_proyek_fokus

    sup = validasi_protokol._superposisi(ca_boltz, ca_proyek, minimal=min(minimal_ca, len(ca_boltz)))
    if not sup:
        raise ValueError("Residu Cα bersama antara Boltz dan reseptor tidak mencukupi untuk penyelarasan.")

    R, t, rmsd_ca, n_ca = sup

    baris_kompleks_align = []
    baris_ligan_align = []

    for baris in pdb_kompleks_boltz.splitlines():
        if baris.startswith(("ATOM", "HETATM")):
            try:
                x = float(baris[30:38])
                y = float(baris[38:46])
                z = float(baris[46:54])
                xyz_baru = R @ np.array([x, y, z]) + t
                baris_baru = f"{baris[:30]}{xyz_baru[0]:8.3f}{xyz_baru[1]:8.3f}{xyz_baru[2]:8.3f}{baris[54:]}"
                baris_kompleks_align.append(baris_baru)

                # Identifikasi ligan
                rantai = baris[21:22].strip()
                resn = baris[17:20].strip()
                if rantai == "L" or resn in ("LIG", "MK1", "UNL") or (
                    baris.startswith("HETATM") and resn not in validasi_protokol._PELARUT_ION
                ):
                    baris_ligan_align.append(baris_baru)
            except Exception:
                baris_kompleks_align.append(baris)
        else:
            baris_kompleks_align.append(baris)

    teks_kompleks = "\n".join(baris_kompleks_align) + "\n"
    teks_ligan = "\n".join(baris_ligan_align) + "\nEND\n" if baris_ligan_align else ""
    return teks_kompleks, teks_ligan, float(rmsd_ca), int(n_ca)


def hitung_rmsd_pose(mol_docking: Chem.Mol, mol_cofold: Chem.Mol) -> float:
    """Hitung RMSD simetris atom berat antara pose docking dan pose co-folding yang telah disejajarkan."""
    if not mol_docking or not mol_cofold:
        raise ValueError("Molekul docking atau co-folding tidak valid untuk komputasi RMSD.")
    return analisis.rmsd_simetri(mol_cofold, mol_docking)


def evaluasi_posebusters_dan_ifp(
    path_reseptor_pdb: Path,
    mol_docking: Chem.Mol,
    mol_cofold: Chem.Mol,
    teks_reseptor: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[float]]:
    """Evaluasi kontrol kualitas fisik PoseBusters dan kesamaan sidik jari interaksi (IFP)."""
    # 1. PoseBusters
    pb_dock = None
    pb_cofold = None
    if qc.tersedia() and path_reseptor_pdb.exists():
        try:
            pb_dock = qc.periksa(mol_docking, path_reseptor_pdb)
        except Exception as e:
            catat.log.warning(f"QC PoseBusters pose docking gagal: {e}")
            pb_dock = {"lulus": False, "galat": str(e), "gagal": ["galat komputasi"]}

        try:
            pb_cofold = qc.periksa(mol_cofold, path_reseptor_pdb)
        except Exception as e:
            catat.log.warning(f"QC PoseBusters pose co-folding gagal: {e}")
            pb_cofold = {"lulus": False, "galat": str(e), "gagal": ["galat komputasi"]}

    # 2. IFP Tanimoto
    ifp_tanimoto = None
    try:
        rec_data = analisis.baca_reseptor(teks_reseptor)
        inter_dock = analisis.interaksi(rec_data, mol_docking)
        inter_cofold = analisis.interaksi(rec_data, mol_cofold)
        ifp_dock = analisis.sidik_jari(inter_dock)
        ifp_cofold = analisis.sidik_jari(inter_cofold)
        ifp_tanimoto = analisis.tanimoto(ifp_dock, ifp_cofold)
    except Exception as e:
        catat.log.warning(f"Komputasi IFP gagal: {e}")

    return pb_dock, pb_cofold, ifp_tanimoto


def label_kesepakatan(
    rmsd: Optional[float],
    pb_docking_lulus: bool = True,
    pb_cofold_lulus: bool = True,
    ifp_tanimoto: Optional[float] = None,
) -> str:
    """Tentukan label kesepakatan konsensus berdasarkan RMSD, PoseBusters, dan IFP."""
    if rmsd is None:
        return "–"

    # Sepakat: RMSD < 2.0 Å DAN keduanya lolos PoseBusters
    if rmsd < AMBANG_RMSD_SEPAKAT and pb_docking_lulus and pb_cofold_lulus:
        return "Sepakat"

    # Sebagian: RMSD < 2.0 Å (tetapi ada yang gagal QC), ATAU interaksi kunci sangat mirip (IFP ≥ 0.6)
    if rmsd < AMBANG_RMSD_SEPAKAT:
        return "Sebagian"
    if ifp_tanimoto is not None and ifp_tanimoto >= AMBANG_IFP_SEBAGIAN:
        return "Sebagian"

    # Selain itu: Bertentangan
    return "Bertentangan"


def kebaruan_ligan_pdb(smiles: str) -> Tuple[Optional[float], str]:
    """Cek kemiripan ligan terhadap ligan kristal PDB.

    Memakai RCSB chemical search melalui sumber_data (dengan cache).
    Bila luring / gagal kueri, membandingkan dengan panel target ligan lokal.
    """
    if not smiles:
        return None, ""

    mol_kueri = Chem.MolFromSmiles(smiles)
    if not mol_kueri:
        return None, ""

    fp_kueri = AllChem.GetMorganFingerprintAsBitVect(mol_kueri, 2, nBits=2048)

    # 1. Coba kueri daring via RCSB chemical similarity search
    url = "https://search.rcsb.org/rcsbsearch/v2/query"
    body = json.dumps({
        "query": {
            "type": "terminal",
            "service": "chemical",
            "parameters": {
                "value": smiles,
                "type": "descriptor",
                "descriptor_type": "SMILES",
                "match_type": "similar"
            }
        },
        "return_type": "mol_definition",
        "request_options": {
            "scoring_strategy": "combined",
            "paginate": {"start": 0, "rows": 1}
        }
    })

    skor_maks: Optional[float] = None
    try:
        raw_resp, _ = sumber_data.ambil_teks(
            url,
            data=body,
            sumber="RCSB Chemical Search",
            kueri_label=f"similarity:{smiles[:30]}",
            batas=10,
            coba=1
        )
        data = json.loads(raw_resp)
        hasil = data.get("result_set") or []
        if hasil:
            skor_maks = float(hasil[0].get("score", 0.0))
    except Exception as e:
        catat.log.debug(f"Pencarian kemiripan daring RCSB gagal ({e}); menggunakan fallback panel ligan lokal.")

    # 2. Fallback luring: bandingkan dengan ligan kristal di pustaka panel_target bawaan
    if skor_maks is None:
        skor_maks = 0.0
        folder_panel = Path(__file__).resolve().parents[1] / "data" / "panel_target"
        if folder_panel.exists():
            for f_json in folder_panel.glob("*.json"):
                try:
                    target_list = json.loads(f_json.read_text(encoding="utf-8"))
                    for tgt in target_list:
                        smi_ref = tgt.get("smiles") or tgt.get("ligan_smiles")
                        if smi_ref:
                            m_ref = Chem.MolFromSmiles(smi_ref)
                            if m_ref:
                                fp_ref = AllChem.GetMorganFingerprintAsBitVect(m_ref, 2, nBits=2048)
                                sim = DataStructs.TanimotoSimilarity(fp_kueri, fp_ref)
                                if sim > skor_maks:
                                    skor_maks = sim
                except Exception:
                    continue

    peringatan = ""
    if skor_maks is not None and skor_maks < AMBANG_KEBARUAN_RENDAH:
        peringatan = (
            f"Kemiripan ligan terhadap struktur PDB rendah (Tanimoto {skor_maks:.2f} < 0,30). "
            "Ligan kemungkinan berada di luar data latih model; keyakinan co-folding rendah."
        )

    return round(skor_maks, 3) if skor_maks is not None else None, peringatan


def analisis_kofolding(
    folder_atau_berkas_boltz: Path,
    reseptor_pdb: str,
    mol_docking: Chem.Mol,
    smiles: str = "",
    path_reseptor_pdb: Optional[Path] = None,
    residu_kantong: Optional[List[Tuple[str, str, str]]] = None,
) -> HasilKofolding:
    """Orkestrasi alur utuh analisis konsensus docking vs co-folding Boltz-2."""
    try:
        data_boltz = baca_keluaran_boltz(folder_atau_berkas_boltz)
    except Exception as e:
        return HasilKofolding(tersedia=False, pesan=f"Gagal membaca keluaran Boltz: {e}")

    if not data_boltz.get("teks_pdb"):
        return HasilKofolding(tersedia=False, pesan="Berkas PDB kompleks Boltz tidak memuat koordinat atom.")

    # 1. Superposisi Kabsch ke kerangka reseptor proyek
    try:
        pdb_kompleks_align, pdb_ligan_align, rmsd_ca, n_ca = sejajarkan_ke_reseptor(
            data_boltz["teks_pdb"],
            reseptor_pdb,
            residu_kantong=residu_kantong
        )
    except Exception as e:
        return HasilKofolding(tersedia=False, pesan=f"Gagal menyelaraskan struktur Boltz: {e}")

    if not pdb_ligan_align:
        return HasilKofolding(
            tersedia=False,
            pesan="Ligan tidak terdeteksi dalam struktur kompleks keluaran Boltz."
        )

    # 2. Bangun RDKit Mol untuk ligan co-folding
    mol_cofold = Chem.MolFromPDBBlock(pdb_ligan_align)
    if not mol_cofold or mol_cofold.GetNumAtoms() == 0:
        return HasilKofolding(
            tersedia=False,
            pesan="Gagal membaca topologi ligan co-folding dari koordinat terselaraskan."
        )

    # Tetapkan orde ikatan dari pose docking bila jumlah atom cocok
    try:
        ref_no_h = Chem.RemoveHs(mol_docking)
        mol_cofold_bo = AllChem.AssignBondOrdersFromTemplate(ref_no_h, mol_cofold)
        if mol_cofold_bo:
            mol_cofold = mol_cofold_bo
    except Exception:
        pass

    # 3. Hitung RMSD atom berat simetris
    try:
        rmsd_lig = hitung_rmsd_pose(mol_docking, mol_cofold)
    except Exception as e:
        catat.log.warning(f"Perhitungan RMSD ligan gagal: {e}")
        rmsd_lig = None

    # 4. Evaluasi PoseBusters & IFP
    pb_dock, pb_cofold, ifp_tan = None, None, None
    if path_reseptor_pdb and path_reseptor_pdb.exists():
        pb_dock, pb_cofold, ifp_tan = evaluasi_posebusters_dan_ifp(
            path_reseptor_pdb, mol_docking, mol_cofold, reseptor_pdb
        )

    # 5. Label kesepakatan konsensus
    pb_dock_ok = pb_dock.get("lulus", True) if pb_dock else True
    pb_cofold_ok = pb_cofold.get("lulus", True) if pb_cofold else True
    kesepakatan = label_kesepakatan(rmsd_lig, pb_dock_ok, pb_cofold_ok, ifp_tan)

    # 6. Pengecekan kebaruan ligan PDB
    kebaruan_skor, peringatan_kebaruan = kebaruan_ligan_pdb(smiles)

    return HasilKofolding(
        tersedia=True,
        pesan="Analisis konsensus docking × co-folding selesai.",
        rmsd=round(rmsd_lig, 3) if rmsd_lig is not None else None,
        rmsd_ca=round(rmsd_ca, 3),
        n_ca=n_ca,
        ifp_tanimoto=ifp_tan,
        posebusters_docking=pb_dock,
        posebusters_cofold=pb_cofold,
        kesepakatan=kesepakatan,
        kebaruan=kebaruan_skor,
        peringatan_kebaruan=peringatan_kebaruan,
        afinitas_pred_value=data_boltz.get("afinitas_pred_value"),
        afinitas_probabilitas=data_boltz.get("afinitas_probabilitas"),
        complex_plddt=data_boltz.get("complex_plddt"),
        ligand_iptm=data_boltz.get("ligand_iptm"),
        pdb_kompleks_terselaraskan=pdb_kompleks_align,
        pdb_ligan_terselaraskan=pdb_ligan_align,
    )


def status_boltz() -> Dict[str, Any]:
    """Periksa kesiapan instalasi Boltz-2 di WSL."""
    from . import lanjutan
    return lanjutan.status_boltz()


def jalankan_boltz(
    sekuens_rantai: List[Tuple[str, str]],
    smiles: str,
    folder: Path,
    gpu: bool = True,
    msa_server: bool = False,
    penuh: bool = False,
) -> str:
    """Jalankan inferensi Boltz-2 via WSL."""
    from . import lanjutan
    return lanjutan.prediksi_boltz(
        sekuens_rantai, smiles, folder, gpu=gpu, msa_server=msa_server, penuh=penuh
    )
