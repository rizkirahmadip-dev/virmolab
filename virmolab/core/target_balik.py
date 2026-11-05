"""Modul penargetan balik (reverse docking / target fishing) VirmoLab (F3 tahap a).

Menyediakan dua jalur komplementer:
1. Jalur berbasis ligan: kemiripan 2D (Morgan2/ECFP4) terhadap ligan aktif ChEMBL (pChEMBL >= 6) per target.
2. Jalur berbasis struktur: docking molekul terhadap panel target terkurasi (Vina) yang dinormalisasi dengan z-skor
   terhadap 50 umpan/decoy latar belakang.
3. Integrasi konsensus: peringkat Borda (R_ligan + R_struktur) dengan evaluasi keyakinan berambang mutlak
   (tinggi bila z <= -2 dan 3 besar jalur struktur, sekaligus Tanimoto >= 0,40 jalur ligan).

Peringatan ilmiah (pedoman BCPT 2025):
Hasil penargetan balik adalah hipotesis komputasi; klaim interaksi dan mekanisme farmakologi memerlukan validasi eksperimental.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from rdkit import Chem, DataStructs
    from rdkit.Chem import AllChem
except ImportError:
    Chem = None
    DataStructs = None
    AllChem = None

DIR_DATA_PANEL = Path(__file__).resolve().parent.parent / "data" / "panel_target"
RMSD_MAKS = 2.0          # ambang redocking yang sah untuk masuk panel (Å)
PCHEMBL_MIN = 6.0        # ambang "aktif" jalur ligan
AMBANG_SIM = 40          # persen kemiripan minimum kueri similarity ChEMBL

# Ambang keyakinan konsensus. Peringkat saja tidak berarti apa-apa pada panel kecil: panel antibakteri
# berisi 9 target, jadi syarat lama "10 besar kedua jalur" dipenuhi SETIAP target dan semuanya tampak
# berkeyakinan tinggi. Keyakinan karena itu diukur dengan ambang mutlak pada besaran yang benar-benar
# diukur, dan peringkat hanya dipakai sebagai syarat tambahan di jalur struktur.
AMBANG_Z = -2.0                  # z-skor energi docking terhadap umpan acak target itu
AMBANG_PERINGKAT_STRUKTUR = 3    # sekaligus harus 3 besar jalur struktur
AMBANG_TANIMOTO = 0.40           # kemiripan Morgan2 ke ligan aktif terdekat (seirama AMBANG_SIM)


class GalatTargetBalik(Exception):
    """Galat yang harus sampai ke pengguna (data panel kosong, jaringan mati, dll.) — tidak ada data pengganti."""


def alasan_tidak_sah(tgt: Dict[str, Any], kelas: str) -> str:
    """Kembalikan alasan entri panel tidak boleh dipakai ("" bila sah). Tidak ada nilai bawaan untuk z-skor/RMSD."""
    for k in ("pdb", "gen", "pusat", "ukuran", "rmsd_redocking", "z_rata", "z_sd"):
        if tgt.get(k) is None:
            return f"kolom '{k}' kosong"
    if float(tgt["rmsd_redocking"]) > RMSD_MAKS:
        return f"RMSD redocking {tgt['rmsd_redocking']} Å > {RMSD_MAKS} Å"
    if float(tgt["z_sd"]) <= 0:
        return "z_sd <= 0"
    if not (DIR_DATA_PANEL / kelas.lower().strip() / f"{tgt['pdb']}.pdbqt").exists():
        return "berkas reseptor .pdbqt tidak ada"
    return ""


def muat_panel(kelas: str) -> List[Dict[str, Any]]:
    """Muat panel target kelas tertentu (virmolab/data/panel_target/<kelas>.json). Kosong bila belum dibangun.

    Panel dibangun dengan alat pengembang (redocking nyata); aplikasi tidak pernah mengarang isinya."""
    berkas = DIR_DATA_PANEL / f"{kelas.lower().strip()}.json"
    if not berkas.exists():
        return []
    try:
        return json.loads(berkas.read_text(encoding="utf-8"))
    except Exception as e:
        raise GalatTargetBalik(f"Panel '{kelas}' rusak: {e}")


def muat_panel_sah(kelas: str) -> tuple:
    """(sah, dilewati): entri panel yang lolos pemeriksaan dan [(gen/pdb, alasan)] untuk yang tidak."""
    sah, lewat = [], []
    for t in muat_panel(kelas):
        a = alasan_tidak_sah(t, kelas)
        if a:
            lewat.append((t.get("gen") or t.get("pdb") or "?", a))
        else:
            sah.append(t)
    return sah, lewat


def daftar_kelas_panel() -> List[str]:
    """Kelas panel yang benar-benar ada di paket (daftar kosong bila panel belum dibangun)."""
    if not DIR_DATA_PANEL.exists():
        return []
    return sorted(f.stem for f in DIR_DATA_PANEL.glob("*.json"))


def organisme_kelas(kelas: str) -> str:
    """Organisme untuk menyaring target jalur ligan: manusia bila >= separuh target panel dari manusia (atau tanpa panel);
    "" (semua organisme) untuk panel yang didominasi protein bakteri/patogen."""
    panel = muat_panel_sah(kelas)[0] if kelas else []
    if not panel:
        return "Homo sapiens"
    manusia = sum(1 for t in panel if "Homo sapiens" in (t.get("organisme") or []))
    return "Homo sapiens" if manusia * 2 >= len(panel) else ""


def _hitung_fp_morgan(smiles: str, n_bits: int = 2048, radius: int = 2):
    """Hitung sidik jari Morgan2/ECFP4 RDKit."""
    if not Chem or not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    from rdkit.Chem import rdFingerprintGenerator
    return rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits).GetFingerprint(mol)


def _peringkatkan_target(fp_kueri, pasangan: List[tuple], k: int) -> List[Dict[str, Any]]:
    """Inti jalur ligan (murni, bisa diuji): pasangan = [(target_info, smiles_ligan, id_ligan, nama_ligan)].
    Kemiripan Tanimoto Morgan2 dihitung lokal; skor_max = tetangga terdekat, skor_knn = jumlah k kemiripan terbesar / k (kurang dari k ligan = sisanya 0)."""
    per_target: Dict[str, Dict[str, Any]] = {}
    for info, smi, lid, nama in pasangan:
        fp = _hitung_fp_morgan(smi)
        if fp is None:
            continue
        sim = float(DataStructs.TanimotoSimilarity(fp_kueri, fp))
        # kunci = UniProt (beberapa ID target ChEMBL dapat menunjuk protein yang sama); ligan yang sama dihitung sekali
        e = per_target.setdefault(info.get("uniprot") or info["target"], {"info": info, "sims": {}})
        e["sims"][lid] = (sim, {"id": lid, "nama": nama, "smiles": smi})
    hasil = []
    for e in per_target.values():
        urut = sorted(e["sims"].values(), key=lambda x: x[0], reverse=True)
        top = [x[0] for x in urut[:k]]
        contoh = dict(urut[0][1])
        contoh["kemiripan"] = round(urut[0][0], 4)
        hasil.append({**e["info"], "skor_max": round(urut[0][0], 4),
                      "skor_knn": round(sum(top) / k, 4), "n_ligan": len(urut), "contoh_ligan": contoh})
    hasil.sort(key=lambda x: (x["skor_max"], x["skor_knn"], x["n_ligan"]), reverse=True)
    return hasil


def jalur_ligan(smiles: str, k: int = 5, organisme: str = "Homo sapiens", lapor=None) -> tuple:
    """Penargetan balik berbasis ligan lewat ChEMBL REST (daring; cache lokal dari sumber_data bila ada).

    Langkah: similarity ChEMBL (>= 40 %) -> aktivitas pChEMBL >= 6 senyawa mirip pada target SINGLE PROTEIN ->
    kemiripan Tanimoto Morgan2 dihitung ulang lokal -> per target skor_max dan skor_knn.
    organisme: saring target (bawaan manusia; "" = semua organisme).
    Kembalikan (hasil, daftar_jejak). Jaringan mati tanpa cache -> GalatTargetBalik (tanpa data pengganti)."""
    from urllib.parse import quote
    from . import chembl, sumber_data
    log = lapor or (lambda s: None)
    fp_kueri = _hitung_fp_morgan(smiles)
    if fp_kueri is None:
        raise GalatTargetBalik("SMILES kueri tidak valid.")
    jejak = []

    def ambil(url, kueri):
        try:
            d, j = sumber_data.ambil_json(url, cache_jam=168.0, lisensi="CC BY-SA 3.0", sumber="ChEMBL")
        except Exception as e:
            raise GalatTargetBalik(f"Gagal mengakses ChEMBL: {e}")
        jejak.append(j.to_dict() if hasattr(j, "to_dict") else j)
        return d

    log("ChEMBL: mencari senyawa mirip…")
    d = ambil(f"{chembl.API}/similarity/{quote(smiles, safe='')}/{AMBANG_SIM}.json?limit=200"
              "&only=molecule_chembl_id,pref_name,molecule_structures", "similarity")
    mols = {}
    for m in d.get("molecules", []):
        smi = (m.get("molecule_structures") or {}).get("canonical_smiles")
        if smi:
            mols[m["molecule_chembl_id"]] = (smi, m.get("pref_name") or m["molecule_chembl_id"])
    if not mols:
        return [], jejak

    ids = list(mols)
    akt = []
    for i in range(0, len(ids), 40):
        log(f"ChEMBL: aktivitas senyawa mirip {i + 1}–{min(i + 40, len(ids))}/{len(ids)}…")
        d = ambil(f"{chembl.API}/activity.json?molecule_chembl_id__in={','.join(ids[i:i + 40])}"
                  f"&pchembl_value__gte={PCHEMBL_MIN}&target_type=SINGLE%20PROTEIN"
                  + (f"&target_organism={quote(organisme)}" if organisme else "")
                  + "&only=molecule_chembl_id,target_chembl_id,target_pref_name,pchembl_value&limit=1000", "aktivitas")
        akt += d.get("activities", [])
    tids = sorted({a["target_chembl_id"] for a in akt if a.get("target_chembl_id")})
    info_t = {}
    for i in range(0, len(tids), 40):
        d = ambil(f"{chembl.API}/target.json?target_chembl_id__in={','.join(tids[i:i + 40])}"
                  "&only=target_chembl_id,pref_name,target_components&limit=1000", "target")
        for t in d.get("targets", []):
            komp = t.get("target_components") or []
            acc = komp[0].get("accession", "") if komp else ""
            gen = ""
            for sn in (komp[0].get("target_component_synonyms") or []) if komp else []:
                if sn.get("syn_type") == "GENE_SYMBOL":
                    gen = sn.get("component_synonym", "")
                    break
            info_t[t["target_chembl_id"]] = {"target": t["target_chembl_id"], "gen": gen, "uniprot": acc,
                                             "nama": t.get("pref_name") or ""}
    pasangan = []
    for a in akt:
        t = info_t.get(a.get("target_chembl_id"))
        m = mols.get(a.get("molecule_chembl_id"))
        if t and m:
            pasangan.append((t, m[0], a["molecule_chembl_id"], m[1]))
    return _peringkatkan_target(fp_kueri, pasangan, k), jejak


def jalur_struktur(proyek: Any, lig: Dict[str, Any], kelas: str, exhaustiveness: int = 8,
                   lewati=(), daftarkan=None) -> List[Dict[str, Any]]:
    """Buat job docking (Vina, CPU) satu per target panel sah untuk satu ligan proyek (lig harus punya 'pdbqt').

    Reseptor panel disalin ke folder proyek (reseptor/panel_<PDB>.pdbqt) supaya proyek tetap portabel. Parameter docking
    sama dengan yang dipakai saat menyusun statistik umpan (z_rata/z_sd), agar z-skor sebanding.
    lewati: kumpulan ID PDB yang sudah punya job untuk ligan ini.
    daftarkan: fungsi yang dipanggil per job segera setelah dibuat (mis. pelaksana.tambah); perlu karena ID job dibuat dari
    waktu dan daftar job proyek, sehingga job yang belum terdaftar bisa bertabrakan ID.
    """
    import shutil
    from . import antrean
    if not lig.get("pdbqt"):
        raise GalatTargetBalik("Ligan belum disiapkan (tidak ada PDBQT). Siapkan ligan di proyek lebih dulu.")
    panel, _lewat = muat_panel_sah(kelas)
    folder_kelas = DIR_DATA_PANEL / kelas.lower().strip()
    jobs = []
    for tgt in panel:
        pdb = tgt["pdb"].upper()
        if pdb in {x.upper() for x in lewati}:
            continue
        tujuan = proyek.p("reseptor", f"panel_{pdb}.pdbqt")
        tujuan.parent.mkdir(parents=True, exist_ok=True)
        if not tujuan.exists():
            shutil.copyfile(folder_kelas / f"{pdb}.pdbqt", tujuan)
        pd = tgt.get("parameter_docking") or {}
        param = {"exhaustiveness": exhaustiveness if exhaustiveness else pd.get("exhaustiveness", 8),
                 "num_modes": pd.get("num_modes", 9), "energy_range": 3.0, "seed": pd.get("seed", 42)}
        kotak = {"pusat": list(tgt["pusat"]), "ukuran": list(tgt["ukuran"]), "spasi": 0.375}
        j = antrean.job_baru(proyek, [lig], "vina", "cpu", param, kotak,
                             nama=f"Target balik · {tgt.get('gen', pdb)} ({pdb}) · {lig.get('nama', lig.get('id', ''))}")
        j.pop("flex", None)
        j.pop("fleksibel", None)
        j["reseptor"] = proyek.rel(tujuan)
        j["target_balik"] = {"kelas": kelas, "pdb": pdb, "gen": tgt.get("gen", ""), "uniprot": tgt.get("uniprot", ""),
                             "nama": tgt.get("nama", ""), "z_rata": tgt["z_rata"], "z_sd": tgt["z_sd"],
                             "rmsd_redocking": tgt["rmsd_redocking"]}
        if daftarkan:
            daftarkan(j)
        jobs.append(j)
    return jobs


def kumpulkan(proyek: Any, kelas: str, ligan_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Kumpulkan hasil docking panel target dari proyek dan hitung z-skor tiap target.

    Target yang gagal docking memiliki energi=None dan z_skor=None, dilaporkan sebagai gagal,
    dan tidak diikutsertakan dalam peringkat numerik (sesuai Blok Verifikasi Wajib Poin 3).
    """
    panel = muat_panel(kelas)
    peta_panel = {t["pdb"].upper(): t for t in panel}

    # Cari job yang sesuai dengan target_balik dan kelas
    hasil_per_target = {}

    for j in getattr(proyek, "job", []):
        tb_info = j.get("target_balik")
        if not tb_info or tb_info.get("kelas", "").lower() != kelas.lower():
            continue

        pdb = tb_info.get("pdb", "").upper()
        if pdb not in peta_panel:
            continue

        # Cari ligan yang sesuai
        for l in j.get("ligan", []):
            if ligan_id and l.get("id") != ligan_id:
                continue

            status = l.get("status", "menunggu")
            energi = l.get("energi")
            pose_pdbqt = ""
            if l.get("pose") and isinstance(l["pose"], list) and len(l["pose"]) > 0:
                pose_pdbqt = l["pose"][0].get("pdbqt", "")

            # Jika berhasil dan memiliki energi
            en_val = None
            if status == "selesai" and energi is not None:
                try:
                    en_val = float(energi)
                except (ValueError, TypeError):
                    en_val = None

            hasil_per_target[pdb] = {
                "pdb": pdb,
                "gen": tb_info.get("gen", peta_panel[pdb].get("gen", pdb)),
                "uniprot": tb_info.get("uniprot", peta_panel[pdb].get("uniprot", "")),
                "nama": tb_info.get("nama", peta_panel[pdb].get("nama", "")),
                "z_rata": tb_info.get("z_rata", peta_panel[pdb].get("z_rata")),
                "z_sd": tb_info.get("z_sd", peta_panel[pdb].get("z_sd")),
                "energi": en_val,
                "status": status,
                "pose_pdbqt": pose_pdbqt,
                "pesan": l.get("pesan", "")
            }

    # Masukkan juga target panel yang belum ada job-nya
    for pdb, tgt in peta_panel.items():
        if pdb not in hasil_per_target:
            hasil_per_target[pdb] = {
                "pdb": pdb,
                "gen": tgt.get("gen", pdb),
                "uniprot": tgt.get("uniprot", ""),
                "nama": tgt.get("nama", ""),
                "z_rata": tgt.get("z_rata"),
                "z_sd": tgt.get("z_sd"),
                "energi": None,
                "status": "belum_dijalankan",
                "pose_pdbqt": "",
                "pesan": ""
            }

    # Hitung z-skor: z = (delta_G - rata) / sd
    # z yang makin negatif = pengikatan makin kuat relatif terhadap umpan latar
    daftar_hasil = []
    for pdb, h in hasil_per_target.items():
        z_val = None
        if h["energi"] is not None and h.get("z_rata") is not None and (h.get("z_sd") or 0) > 0:
            z_val = round((h["energi"] - h["z_rata"]) / h["z_sd"], 2)

        h["z_skor"] = z_val
        daftar_hasil.append(h)

    # Urutkan: yang berhasil menurut z-skor terkecil (paling negatif), lalu yang gagal/belum di bawah
    def _kunci_urut(x):
        if x["z_skor"] is not None:
            return (0, x["z_skor"])
        return (1, 0)

    daftar_hasil.sort(key=_kunci_urut)
    return daftar_hasil


def _kunci(e: Dict[str, Any]) -> str:
    """Identitas target lintas jalur: UniProt; tanpa UniProt pakai ID target ChEMBL / PDB."""
    return (e.get("uniprot") or e.get("target") or e.get("pdb") or "").upper()


def gabung(peringkat_ligan: List[Dict[str, Any]], peringkat_struktur: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Gabungkan peringkat jalur ligan dan jalur struktur dengan hitungan Borda (target diidentifikasi lewat UniProt).

    Borda = R_ligan + R_struktur; terkecil = paling konsisten. Target yang tak muncul di satu jalur diberi N+1 jalur itu.

    Keyakinan memakai ambang mutlak, bukan peringkat (lihat AMBANG_* di atas): jalur struktur lolos bila
    z <= AMBANG_Z dan masuk AMBANG_PERINGKAT_STRUKTUR besar, jalur ligan lolos bila kemiripan tetangga
    terdekat >= AMBANG_TANIMOTO. Lolos keduanya = "tinggi", salah satu = "sedang", tidak keduanya = "rendah".
    Target gagal/belum di-docking tidak diperingkat pada jalur struktur dan dilaporkan statusnya.
    """
    peta_ligan = {}
    for idx, e in enumerate(peringkat_ligan, start=1):
        peta_ligan.setdefault(_kunci(e), (idx, e))

    # beberapa struktur panel untuk protein yang sama: pakai z terbaik (paling negatif) per UniProt
    valid, terlihat = [], set()
    for e in sorted((s for s in peringkat_struktur if s.get("z_skor") is not None), key=lambda s: s["z_skor"]):
        if _kunci(e) not in terlihat:
            terlihat.add(_kunci(e))
            valid.append(e)
    peta_struktur = {_kunci(e): (idx, e) for idx, e in enumerate(valid, start=1)}
    peta_status = {}
    for e in peringkat_struktur:
        peta_status.setdefault(_kunci(e), e)

    n_ligan, n_struktur = len(peringkat_ligan) + 1, len(valid) + 1
    gabungan = []
    for kunci in set(peta_ligan) | set(peta_status):
        r_lig, d_lig = peta_ligan.get(kunci, (None, None))
        r_str, d_str = peta_struktur.get(kunci, (None, None))
        d_status = d_str or peta_status.get(kunci)
        ref = d_status or d_lig or {}
        borda = (r_lig if r_lig is not None else n_ligan) + (r_str if r_str is not None else n_struktur)
        z_str = d_str.get("z_skor") if d_str else None
        sim_lig = d_lig.get("skor_max") if d_lig else None
        lolos_struktur = (r_str is not None and r_str <= AMBANG_PERINGKAT_STRUKTUR
                          and z_str is not None and z_str <= AMBANG_Z)
        lolos_ligan = sim_lig is not None and sim_lig >= AMBANG_TANIMOTO
        if lolos_struktur and lolos_ligan:
            keyakinan = "tinggi"
        elif lolos_struktur or lolos_ligan:
            keyakinan = "sedang"
        else:
            keyakinan = "rendah"
        gabungan.append({
            "target": kunci,
            "gen": ref.get("gen") or (d_lig or {}).get("gen", ""),
            "uniprot": ref.get("uniprot") or (d_lig or {}).get("uniprot", ""),
            "nama": ref.get("nama") or (d_lig or {}).get("nama", ""),
            "pdb": (d_status or {}).get("pdb", ""),
            "skor_ligan": sim_lig,
            "struktur_z": z_str,
            "energi": d_status.get("energi") if d_status else None,
            "r_ligan": r_lig, "r_struktur": r_str, "borda": borda, "keyakinan": keyakinan,
            "status": d_status.get("status", "") if d_status else "tidak_diuji",
            "pose_pdbqt": (d_status or {}).get("pose_pdbqt", ""),
            "contoh_ligan": d_lig.get("contoh_ligan") if d_lig else None,
        })
    gabungan.sort(key=lambda x: (x["borda"], -(x["skor_ligan"] or 0), x["struktur_z"] if x["struktur_z"] is not None else 0))
    return gabungan


def susun_paragraf_metode(
    kelas: str,
    parameter: Optional[Dict[str, Any]] = None,
    n_sukses: int = 0,
    n_gagal: int = 0,
    jejak: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Rakit paragraf metode dari parameter dan panel nyata. Bagian yang tidak dijalankan tidak disebut."""
    param = parameter or {}
    panel, _ = muat_panel_sah(kelas)
    from .. import i18n
    if i18n.inggris():
        return _paragraf_metode_en(kelas, param, panel, n_sukses, n_gagal, jejak)
    bagian = []
    if param.get("jalur_ligan"):
        sumber = "; ".join(sorted({f"{j.get('sumber', 'ChEMBL')} {j.get('versi', '')}".strip() for j in (jejak or [])})) or "ChEMBL"
        bagian.append(
            "Pada jalur berbasis ligan, kemiripan struktur 2D dihitung dengan koefisien Tanimoto pada sidik jari Morgan "
            f"(radius 2, 2048 bit) terhadap senyawa aktif (pChEMBL >= {PCHEMBL_MIN:g}) pada target protein tunggal dari {sumber}; "
            "tiap target diberi skor tetangga terdekat dan rata-rata lima tetangga terdekat.")
    if param.get("jalur_struktur"):
        if not panel:
            bagian.append("Jalur berbasis struktur tidak dijalankan karena panel target belum tersedia.")
        else:
            rm = [float(t["rmsd_redocking"]) for t in panel]
            nu = sorted({t.get("n_umpan") for t in panel if t.get("n_umpan")})
            bagian.append(
                f"Pada jalur berbasis struktur, molekul ditambatkan ke {len(panel)} struktur kristal panel '{kelas}' "
                f"(RMSD redocking ligan ko-kristal {min(rm):.2f}–{max(rm):.2f} Å, ambang {RMSD_MAKS:g} Å) memakai AutoDock Vina "
                f"(exhaustiveness {param.get('exhaustiveness', 8)}). Energi dinormalisasi menjadi z-skor terhadap distribusi skor "
                f"{'/'.join(str(n) for n in nu) if nu else 'sejumlah'} umpan acak per target; {n_sukses} target berhasil ditambatkan, "
                f"{n_gagal} gagal dan tidak diperingkat.")
    if param.get("jalur_ligan") and param.get("jalur_struktur"):
        bagian.append(
            f"Peringkat kedua jalur digabung dengan hitungan Borda. Keyakinan dinilai dengan ambang mutlak, bukan "
            f"peringkat relatif: 'tinggi' bila target mencapai z <= {AMBANG_Z:g} sekaligus {AMBANG_PERINGKAT_STRUKTUR} "
            f"besar pada jalur struktur dan kemiripan Tanimoto >= {AMBANG_TANIMOTO:.2f} pada jalur ligan, 'sedang' bila "
            f"hanya satu jalur yang memenuhi, 'rendah' bila tidak satu pun. Ambang mutlak dipakai karena panel target "
            f"berisi puluhan struktur saja, sehingga syarat berbasis peringkat akan meloloskan hampir semua target.")
    if not bagian:
        return ""
    bagian.append("Seluruh target kandidat merupakan hipotesis komputasi dan memerlukan validasi eksperimental sebelum "
                  "mekanisme farmakologi dapat dinyatakan.")
    return "Penargetan balik. " + " ".join(bagian)


def _paragraf_metode_en(kelas, param, panel, n_sukses, n_gagal, jejak):
    """Versi Inggris susun_paragraf_metode dengan syarat kalimat yang sama."""
    bagian = []
    if param.get("jalur_ligan"):
        sumber = "; ".join(sorted({f"{j.get('sumber', 'ChEMBL')} {j.get('versi', '')}".strip()
                                   for j in (jejak or [])})) or "ChEMBL"
        bagian.append(
            "In the ligand-based route, 2D structural similarity was computed as the Tanimoto coefficient on Morgan "
            f"fingerprints (radius 2, 2048 bits) against actives (pChEMBL >= {PCHEMBL_MIN:g}) on single-protein "
            f"targets from {sumber}; each target was scored by the nearest neighbour and by the mean of the five "
            "nearest neighbours.")
    if param.get("jalur_struktur"):
        if not panel:
            bagian.append("The structure-based route was not run because the target panel is not available yet.")
        else:
            rm = [float(t["rmsd_redocking"]) for t in panel]
            nu = sorted({t.get("n_umpan") for t in panel if t.get("n_umpan")})
            bagian.append(
                f"In the structure-based route, molecules were docked to {len(panel)} crystal structures of the "
                f"'{kelas}' panel (co-crystal ligand redocking RMSD {min(rm):.2f}–{max(rm):.2f} Å, threshold "
                f"{RMSD_MAKS:g} Å) using AutoDock Vina (exhaustiveness {param.get('exhaustiveness', 8)}). Energies "
                "were normalised to z-scores against the score distribution of "
                f"{'/'.join(str(n) for n in nu) if nu else 'several'} random decoys per target; {n_sukses} targets "
                f"were docked successfully, {n_gagal} failed and were not ranked.")
    if param.get("jalur_ligan") and param.get("jalur_struktur"):
        bagian.append(
            "The ranks from both routes were combined by Borda count. Confidence was assessed with absolute "
            f"thresholds rather than relative ranks: 'high' when a target reaches z <= {AMBANG_Z:g} and is within the "
            f"top {AMBANG_PERINGKAT_STRUKTUR} of the structure-based route while also reaching a Tanimoto similarity "
            f">= {AMBANG_TANIMOTO:.2f} in the ligand-based route, 'medium' when only one route qualifies, and 'low' "
            "when neither does. Absolute thresholds were used because the target panel holds only tens of structures, "
            "so a rank-based criterion would qualify almost every target.")
    if not bagian:
        return ""
    bagian.append("All candidate targets are computational hypotheses and require experimental validation before "
                  "a pharmacological mechanism can be claimed.")
    return "Reverse targeting. " + " ".join(bagian)
