"""Uji Penapisan Berbasis Ligan 3D (Farmakofor & Bentuk) - F4.

Memverifikasi:
1. Kueri farmakofor dari pose MK1 (1HSG) -> MK1 skor maksimum (>= 0.95).
2. Molekul acak menghasilkan skor rendah (< 0.35).
3. Skor bentuk molekul ke dirinya sendiri = 1,0 ± 0,01.
4. Kecocokan fitur dibaca dari konformer terselaraskan (molekul dari SMILES).
5. Validasi kueri: 8 inhibitor protease HIV vs decoy obat sepadan (AUC >= 0,6, EF1% hanya bila >= 100).
6. Penapisan pustaka (10.000 senyawa COCONUT lokal bila ada < 15 menit, atau LEWAT dengan pesan).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import Descriptors, rdFingerprintGenerator
from rdkit.Chem.MolStandardize import rdMolStandardize

from virmolab.core import bentuk, farmakofor, kemiripan, pustaka

RDLogger.DisableLog("rdApp.*")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 60)
    print("UJI PENAPISAN BERBASIS LIGAN 3D (F4)")
    print("=" * 60)

    # 1. Muat pose acuan MK1 (1HSG)
    p_mk1 = Path("dev/uji/cli/vina/pose/MK1_902_B_terbaik.sdf")
    if not p_mk1.exists():
        print(f"GAGAL: Berkas {p_mk1} tidak ditemukan.")
        sys.exit(1)

    suppl = Chem.SDMolSupplier(str(p_mk1))
    mk1 = suppl[0]
    if mk1 is None or mk1.GetNumConformers() == 0:
        print("GAGAL: Gagal membaca struktur 3D MK1.")
        sys.exit(1)

    print(f"OK    Struktur acuan MK1 dimuat ({mk1.GetNumAtoms()} atom).")

    # 2. Uji skor bentuk ke dirinya sendiri = 1,0 ± 0,01
    res_b = bentuk.skor_bentuk(mk1, mk1)
    sb = res_b["tanimoto_bentuk"]
    sw = res_b["tanimoto_warna"]
    sg = res_b["gabungan"]
    print(f"Bentuk MK1 vs MK1 -> bentuk: {sb:.4f}, warna: {sw:.4f}, gabungan: {sg:.4f}")
    assert abs(sb - 1.0) <= 0.01, f"Tanimoto bentuk ke dirinya salah: {sb}"
    assert abs(sw - 1.0) <= 0.01, f"Tanimoto warna ke dirinya salah: {sw}"
    assert abs(sg - 1.0) <= 0.01, f"Skor gabungan ke dirinya salah: {sg}"
    print("OK    Skor bentuk molekul ke dirinya sendiri = 1,0 ± 0,01.")

    # 3. Kueri farmakofor dari pose MK1 + protein 1HSG
    p_prot = Path("virmolab/aset/uji_1hsg.pdb")
    kueri = farmakofor.kueri_dari_pose(
        mk1,
        protein=p_prot if p_prot.exists() else None,
        toleransi=1.0,
        eksklusi=True
    )
    n_fitur = len(kueri["fitur"])
    n_eksklusi = len(kueri["eksklusi"])
    print(f"OK    Kueri farmakofor: {n_fitur} fitur, {n_eksklusi} bola eksklusi protein.")
    assert n_fitur >= 5, f"Jumlah fitur terlalu sedikit: {n_fitur}"

    # 4. Cocokkan MK1 -> harus skor maksimum
    res_mk1 = farmakofor.cocokkan(kueri, mk1)
    print(f"Cocokkan MK1 -> {res_mk1['n_cocok']}/{res_mk1['n_aktif']} fitur cocok, "
          f"RMSD: {res_mk1['rmsd_fitur']}, bentuk: {res_mk1['tanimoto_bentuk']}, "
          f"skor akhir: {res_mk1['skor_akhir']:.4f}")
    assert res_mk1["n_cocok"] == res_mk1["n_aktif"], "Semua fitur kueri harus cocok pada dirinya sendiri"
    assert res_mk1["skor_akhir"] >= 0.95, f"Skor MK1 harus maksimum: {res_mk1['skor_akhir']}"
    print("OK    MK1 mencapai skor maksimum (>= 0.95).")

    # 5. Molekul acak -> skor rendah
    acak_smiles = [
        ("Metanol", "CO"),
        ("Fenol", "Oc1ccccc1"),
        ("Toluen", "Cc1ccccc1"),
        ("Piridin", "c1ccncc1")
    ]
    for nm, smi in acak_smiles:
        res_acak = farmakofor.cocokkan(kueri, smi, n_konf=5)
        print(f"Molekul acak ({nm}) -> skor akhir: {res_acak['skor_akhir']:.4f}, cocok: {res_acak['n_cocok']}")
        assert res_acak["skor_akhir"] < 0.35, f"Skor {nm} terlalu tinggi: {res_acak['skor_akhir']}"
    print("OK    Molekul acak terverifikasi menghasilkan skor rendah (< 0.35).")

    # 6. Konformer hasil ETKDG (bukan pose kristal): fitur harus dibaca dari konformer yang
    #    diselaraskan. Hitung ulang kecocokan dari molekul keluaran -> harus sama dengan n_cocok.
    #    (Regresi: dulu fitur selalu diambil dari konformer 0 sehingga skor farmakofor salah.)
    smi_idv = next(d["smiles"] for d in pustaka.obat() if d["nama"] == "Indinavir Anhydrous")
    res_idv = farmakofor.cocokkan(kueri, smi_idv, n_konf=30)
    m_out = res_idv["mol"]
    assert m_out.GetNumConformers() == 1, "Molekul keluaran harus berkonformer tunggal"
    f_out = kemiripan.fitur(m_out)
    n_ulang = 0
    for qf in (f for f in kueri["fitur"] if f.get("aktif", True)):
        d = [float(np.linalg.norm(np.asarray(qf["xyz"]) - np.asarray(pf["xyz"])))
             for pf in f_out if pf["famili"] == qf["famili"]]
        n_ulang += bool(d) and min(d) <= qf["toleransi"]
    print(f"Indinavir dari SMILES -> konformer {res_idv['konformer_terbaik']}, cocok {res_idv['n_cocok']}"
          f"/{res_idv['n_aktif']} (hitung ulang {n_ulang}), skor {res_idv['skor_akhir']:.3f}")
    assert n_ulang == res_idv["n_cocok"], "Fitur tidak dibaca dari konformer yang diselaraskan"
    print("OK    Kecocokan fitur konsisten dengan konformer terselaraskan.")

    # 7. Validasi kueri pada himpunan nyata: 8 inhibitor protease HIV disetujui (selain indinavir =
    #    MK1 dan prodrug fosamprenavir) vs decoy obat disetujui ChEMBL yang sepadan sifatnya
    #    (BM ±10 % rentang aktif, >= 5 ikatan berputar) dan berbeda topologi (Tanimoto Morgan2 < 0,35
    #    terhadap semua aktif), gaya DUD-E. Batas AUC dikunci dari hasil terukur 0,71 (tanpa eksklusi).
    lf = rdMolStandardize.LargestFragmentChooser()
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    obat = pustaka.obat()
    nama_aktif = ["Saquinavir", "Nelfinavir", "Amprenavir", "Lopinavir", "Ritonavir",
                  "Atazanavir", "Darunavir", "Tipranavir"]
    aktif_set = []
    for nm in nama_aktif:
        m = lf.choose(Chem.MolFromSmiles(next(d["smiles"] for d in obat if d["nama"] == nm)))
        aktif_set.append({"nama": nm, "smiles": Chem.MolToSmiles(m), "m": m})
    fp_aktif = [gen.GetFingerprint(a["m"]) for a in aktif_set]
    bm = [Descriptors.MolWt(a["m"]) for a in aktif_set]
    decoy_set = []
    for d in obat:
        if "navir" in d["nama"].lower() or not d.get("smiles"):
            continue
        m = Chem.MolFromSmiles(d["smiles"])
        if m is None:
            continue
        m = lf.choose(m)
        if not (min(bm) * 0.9 <= Descriptors.MolWt(m) <= max(bm) * 1.1):
            continue
        if Descriptors.NumRotatableBonds(m) < 5:
            continue
        if max(DataStructs.BulkTanimotoSimilarity(gen.GetFingerprint(m), fp_aktif)) >= 0.35:
            continue
        decoy_set.append({"nama": d["nama"], "smiles": Chem.MolToSmiles(m)})
    t0 = time.time()
    val_res = farmakofor.validasi_kueri(kueri, [{"smiles": a["smiles"]} for a in aktif_set], decoy_set,
                                        konf_per_mol=10)
    print(f"Validasi {val_res['pesan']} ({time.time() - t0:.0f} s)")
    assert val_res["n_gagal"] == 0, f"{val_res['n_gagal']} senyawa gagal diproses"
    assert len(decoy_set) >= 100 and val_res["ef1"] is not None, "Himpunan decoy terlalu kecil untuk EF1%"
    assert val_res["auc"] >= 0.6, f"AUC kueri MK1 pada inhibitor protease nyata turun: {val_res['auc']}"
    print("OK    Kueri MK1 membedakan inhibitor protease HIV dari decoy sepadan (AUC >= 0,6).")

    # Himpunan < 100 senyawa: EF1% tidak boleh dilaporkan (1 % teratas < 1 senyawa)
    kecil = farmakofor.validasi_kueri(kueri, [{"smiles": a["smiles"]} for a in aktif_set[:3]],
                                      decoy_set[:6], konf_per_mol=3)
    assert kecil["ef1"] is None and "EF1% tidak dilaporkan" in kecil["pesan"], kecil["pesan"]
    print("OK    EF1% disembunyikan untuk himpunan kecil.")

    # 8. Penapisan pustaka 10.000 senyawa (COCONUT lokal bila ada)
    status_coco = pustaka.coconut_ada()
    if status_coco and status_coco.get("jumlah", 0) >= 10000:
        print("Mengambil 10.000 senyawa dari COCONUT lokal...")
        senyawa_10k = pustaka.cari_coconut(batas=10000)
        t0 = time.time()
        hasil_10k = farmakofor.saring_pustaka(kueri, senyawa_10k, konf_per_mol=10)
        durasi = time.time() - t0
        print(f"OK    Penapisan 10.000 senyawa ({len(hasil_10k)} terurut) tuntas dalam {durasi:.1f} s (< 15 menit).")
        assert durasi < 900, f"Penapisan 10.000 melebihi 15 menit: {durasi} s"
    else:
        print("LEWAT: Basis data COCONUT lokal lengkap belum terpasang (pustaka.coconut_ada() = None atau < 10.000).")
        # Uji himpunan obat snapshot ChEMBL lokal
        obat_list = pustaka.obat()[:100]
        t0 = time.time()
        hasil_obat = farmakofor.saring_pustaka(kueri, obat_list, konf_per_mol=5)
        durasi = time.time() - t0
        print(f"OK    Uji penapisan sampel 100 obat ChEMBL tuntas dalam {durasi:.2f} s ({len(hasil_obat)} terurut).")

    print("=" * 60)
    print("SEMUA UJI FARMAKOFOR DAN BENTUK (F4) LULUS!")
    print("=" * 60)


if __name__ == "__main__":
    main()
