#!/usr/bin/env python3
"""Uji QSAR (F5): konversi satuan, kurasi, pembagian, pelatihan, validasi, domain, konformal, simpan-muat.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_qsar.py [--lambat]

Data nyata: dev/data/qsar_ache.csv (ChEMBL CHEMBL220, IC50, CC BY-SA 3.0). Metrik data nyata dilaporkan apa adanya;
ambangnya longgar dan hanya untuk menangkap kerusakan besar. Kebenaran pipeline diuji pada data sintetis yang
hubungannya diketahui.
"""
import sys
import tempfile
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

import numpy as np  # noqa: E402

from virmolab.core import konformal, qsar  # noqa: E402

DATA = AKAR / "dev" / "data" / "qsar_ache.csv"
LAMBAT = "--lambat" in sys.argv


def cek(k, pesan):
    if not k:
        print(f"GAGAL: {pesan}")
        sys.exit(1)
    print(f"OK: {pesan}")


def uji_konversi():
    cek(qsar.ke_pic50(1000, "nM") == 6.0, "1000 nM -> pIC50 6,0")
    cek(qsar.ke_pic50(1, "uM") == 6.0, "1 uM -> pIC50 6,0")
    cek(qsar.ke_pic50(1, "M") == 0.0, "1 M -> pIC50 0,0")
    cek(qsar.ke_pic50(100, ">") is None and qsar.ke_pic50(100, "nM", ">") is None,
        "satuan tak dikenal dan relasi '>' ditolak (bukan diisi angka)")
    cek(qsar.ke_pic50(0, "nM") is None and qsar.ke_pic50(None, "nM") is None, "nilai 0 atau kosong ditolak")


def uji_kurasi():
    baris = [
        {"smiles": "CCO", "pic50": 5.0, "nama": "etanol"},                      # terlalu kecil
        {"smiles": "[Na+].[Cl-]", "pic50": 5.0, "nama": "garam"},               # anorganik
        {"smiles": "bukan-smiles", "pic50": 5.0, "nama": "rusak"},
        {"smiles": "CCCCc1ccc(cc1)C(=O)Nc1ccccc1", "pic50": 7.0, "nama": "a"},
        {"smiles": "CCCCc1ccc(cc1)C(=O)Nc1ccccc1", "pic50": 8.4, "nama": "a lagi"},   # duplikat, rentang 1,4 log
        {"smiles": "CCCCCc1ccc(cc1)C(=O)Nc1ccccc1", "pic50": 5.2, "nama": "b"},       # Tanimoto 0,91 dengan a -> cliff
    ]
    h = qsar.kurasi(baris)
    alasan = " ".join(d["alasan"] for d in h["dibuang"])
    cek(len(h["dibuang"]) == 3 and "kecil" in alasan and "anorganik" in alasan and "RDKit" in alasan,
        "baris tidak sah dibuang dengan alasan tercatat")
    a = next(d for d in h["data"] if d["n_ukur"] == 2)
    cek(abs(a["pic50"] - 7.7) < 1e-6 and abs(a["rentang"] - 1.4) < 1e-6, "duplikat digabung sebagai median, rentang dicatat")
    jenis = [p["jenis"] for p in h["peringatan"]]
    cek("rentang" in jenis and "cliff" in jenis, f"peringatan rentang dan activity cliff muncul ({jenis})")


def uji_pembagian():
    data = [{"smiles": s, "pic50": 6.0} for s in
            ["c1ccccc1C", "c1ccccc1CC", "c1ccccc1CCC", "C1CCCCC1C", "C1CCCCC1CC", "N1CCCCC1C"]]
    lat, uji = qsar.bagi(data, "acak", 0.34, benih=1)
    cek(len(uji) == 2 and not set(lat) & set(uji), "pembagian acak: ukuran benar dan tanpa tumpang tindih")
    cek(qsar.bagi(data, "acak", 0.34, benih=1) == (lat, uji), "pembagian acak dapat diulang dengan benih sama")
    lat2, uji2 = qsar.bagi(data, "kerangka", 0.34, benih=1)
    kerangka = lambda idx: {qsar.kerangka_murcko(data[i]["smiles"]) for i in idx}  # noqa: E731
    cek(not kerangka(lat2) & kerangka(uji2), "pembagian kerangka: tidak ada kerangka yang sama di kedua sisi")


def uji_fitur():
    X, nama, kolom = qsar.hitung_fitur(["c1ccccc1", "CCCCO"], "morgan")
    cek(X.shape[0] == 2 and len(nama) == X.shape[1] == len(kolom), "matriks Morgan dan nama fitur sepadan")
    X2, _n2, _k2 = qsar.hitung_fitur(["c1ccccc1"], "morgan", kolom_terpilih=kolom)
    cek(X2.shape[1] == X.shape[1], "data baru memakai kolom hasil penyaringan set latih")
    smi_banyak = [d["smiles"] for d in _data_sintetis(60, benih=3)]
    X_mentah, nama_mentah, _km = qsar.hitung_fitur(smi_banyak[:2], "deskriptor", kolom_terpilih=list(range(5)))
    Xd, namad, _k = qsar.hitung_fitur(smi_banyak, "deskriptor")
    cek(len(namad) < 200 and Xd.shape[1] == len(namad), f"deskriptor RDKit tersaring: {Xd.shape[1]} kolom (dari ±210)")
    cek(X_mentah.shape[1] == 5 and len(nama_mentah) == 5, "kolom_terpilih dihormati tanpa penyaringan ulang")
    cek(float(np.abs(np.corrcoef(Xd, rowvar=False)[np.triu_indices(Xd.shape[1], 1)]).max()) <= qsar.KORELASI_MAKS + 1e-9,
        "tidak ada pasangan deskriptor dengan |r| > 0,95 yang tersisa")
    try:
        qsar.hitung_fitur(["bukan-smiles"], "morgan")
        cek(False, "SMILES rusak harus menimbulkan galat")
    except qsar.GalatQSAR:
        cek(True, "SMILES rusak menimbulkan GalatQSAR, bukan baris kosong")


def _data_sintetis(n=200, derau=0.1, benih=0):
    """pIC50 = fungsi linear logP dan MW + derau kecil: pipeline yang benar harus menemukannya (R2 tinggi)."""
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors
    rng = np.random.default_rng(benih)
    inti = ["c1ccc(cc1)C(=O)N", "c1ccc(cc1)S(=O)(=O)N", "c1ccc(cc1)OC(=O)N", "c1ccc(nc1)C(=O)N", "c1ccc(cc1)NC(=O)N"]
    ujung = ["C", "CC", "CCC", "CCCC", "C1CC1", "C1CCCCC1", "Cc1ccccc1", "CCO", "CCN(C)C", "CC(C)C"]
    data = []
    for i in range(n):
        smi = f"{'C' * (1 + i % 8)}{inti[i % len(inti)]}{ujung[(i // 3) % len(ujung)]}"
        m = Chem.MolFromSmiles(smi)
        if m is None:
            continue
        y = 4.0 + 0.6 * Crippen.MolLogP(m) - 0.004 * Descriptors.MolWt(m) + rng.normal(0, derau)
        data.append({"smiles": Chem.MolToSmiles(m), "pic50": round(float(y), 3), "nama": f"s{i}"})
    # buang duplikat SMILES supaya setiap senyawa unik
    unik = {}
    for d in data:
        unik.setdefault(d["smiles"], d)
    return list(unik.values())


def uji_pipeline_sintetis():
    data = _data_sintetis(400)
    h = qsar.latih(data, "rf", "deskriptor", "acak", benih=7)
    cek(h["eksternal"]["r2"] >= 0.8, f"data sintetis berhubungan: R2 uji {h['eksternal']['r2']:.3f} >= 0,8")
    cek(h["internal"]["q2"] >= 0.7, f"Q2 validasi silang {h['internal']['q2']:.3f} >= 0,7")
    y = qsar.y_acak(data, "rf", "deskriptor", n=10, benih=7)
    cek(y["rata"] < 0.2, f"Y-randomization rata-rata R2 {y['rata']:.3f} < 0,2 (tanpa korelasi kebetulan)")
    cek(y["maks"] < 0.5, f"Y-randomization maksimum {y['maks']:.3f} < 0,5")
    return h, data


def uji_domain(h, data):
    jauh = ["CCCCCCCCCCCCCCCCCCCC", "[Si](C)(C)(C)C1=CC=CC=C1", "C1CC2CCC1C2"]
    dekat = max(data, key=lambda d: 0)["smiles"]
    p_dekat = qsar.prediksi(h, [d["smiles"] for d in data[:20]])
    cek(sum(1 for x in p_dekat if x["dalam_domain"]) >= 15,
        f"senyawa set data sendiri sebagian besar di dalam domain "
        f"({sum(1 for x in p_dekat if x['dalam_domain'])}/20)")
    p = qsar.prediksi(h, [dekat] + jauh)
    cek(sum(1 for x in p[1:] if not x["dalam_domain"]) >= 2,
        f"senyawa asing ditandai di luar domain ({sum(1 for x in p[1:] if not x['dalam_domain'])}/3)")
    cek(all(x["bawah"] < x["pic50"] < x["atas"] for x in p), "interval konformal mengapit prediksi")


def uji_konformal_sendiri():
    rng = np.random.default_rng(0)
    y_kal = rng.normal(0, 1, 500)
    p_kal = y_kal + rng.normal(0, 0.5, 500)
    k = konformal.KonformalRegresi(0.1)
    q = k.kalibrasi(y_kal, p_kal)
    y_uji = rng.normal(0, 1, 1000)
    p_uji = y_uji + rng.normal(0, 0.5, 1000)
    c = k.cakupan(y_uji, p_uji)
    cek(0.85 <= c <= 0.95, f"cakupan konformal regresi {c:.3f} dalam 0,85-0,95 (nominal 0,90; q = {q:.3f})")
    try:
        konformal.KonformalRegresi().kalibrasi([1, 2, 3], [1, 2, 3])
        cek(False, "kalibrasi dengan 3 titik harus ditolak")
    except ValueError:
        cek(True, "set kalibrasi terlalu kecil ditolak, bukan dipaksa")
    peluang = np.clip(np.column_stack([1 - np.abs(y_kal) / 4, np.abs(y_kal) / 4]), 0.01, 0.99)
    kk = konformal.KonformalKlasifikasi(0.1)
    kk.kalibrasi((np.abs(y_kal) > 1).astype(int), peluang)
    cek(kk.q is not None and 0 <= kk.q <= 1, "konformal klasifikasi terkalibrasi")


def uji_simpan_muat(h, data):
    with tempfile.TemporaryDirectory() as d:
        jalur = qsar.simpan(h, data, d, "uji", sumber_data="data sintetis")
        import json
        kartu = json.loads(jalur["kartu"].read_text(encoding="utf-8"))
        for k in ("hash_data", "algoritma", "fitur", "metrik_eksternal", "versi", "tanggal", "parameter"):
            cek(k in kartu, f"kartu model memuat '{k}'")
        h2 = qsar.muat(jalur["model"])
        a = qsar.prediksi(h, [data[0]["smiles"], data[1]["smiles"]])
        b = qsar.prediksi(h2, [data[0]["smiles"], data[1]["smiles"]])
        cek(all(abs(x["pic50"] - y["pic50"]) < 1e-12 for x, y in zip(a, b)), "model yang dimuat memberi prediksi identik")


def uji_paragraf(h, data):
    teks = qsar.susun_paragraf_metode(h, data, sumber_data="data sintetis",
                                      y_acak_hasil={"n": 10, "rata": -0.1, "maks": 0.05})
    for frasa in ("OECD", "Q2", "R2", "Y-randomization", "domain aplikabilitas", "konformal", "Golbraikh"):
        cek(frasa.lower() in teks.lower(), f"paragraf metode menyebut {frasa}")
    cek("nan" not in teks.lower(), "paragraf metode tidak memuat nilai nan")
    cek(qsar.susun_paragraf_metode({}, data) == "", "tanpa model: paragraf kosong")


def uji_data_nyata():
    """Metrik data ChEMBL nyata dilaporkan apa adanya; ambang longgar hanya untuk menangkap kerusakan besar."""
    baris = qsar.muat_csv(DATA)
    h0 = qsar.kurasi(baris)
    data = h0["data"]
    print(f"  {len(baris)} baris -> {len(data)} senyawa unik, {len(h0['dibuang'])} dibuang, "
          f"{len(h0['peringatan'])} peringatan")
    acak = qsar.latih(data, "rf", "morgan", "acak")
    kerangka = qsar.latih(data, "rf", "morgan", "kerangka")
    print(f"  pembagian acak   : Q2 {acak['internal']['q2']:.3f}, R2 uji {acak['eksternal']['r2']:.3f}, "
          f"RMSE {acak['eksternal']['rmse']:.3f}, cakupan konformal {acak['konformal']['cakupan_uji']:.3f}")
    print(f"  pembagian kerangka: Q2 {kerangka['internal']['q2']:.3f}, R2 uji {kerangka['eksternal']['r2']:.3f}, "
          f"RMSE {kerangka['eksternal']['rmse']:.3f}")
    print(f"  Golbraikh-Tropsha (acak): {'lulus' if acak['golbraikh_tropsha']['lulus'] else 'tidak lulus'}")
    cek(acak["eksternal"]["r2"] > 0.3, f"data AChE nyata: R2 uji pembagian acak {acak['eksternal']['r2']:.3f} > 0,3")
    cek(0.80 <= acak["konformal"]["cakupan_uji"] <= 1.0,
        f"cakupan konformal data nyata {acak['konformal']['cakupan_uji']:.3f} masuk akal")
    cek(kerangka["eksternal"]["r2"] < acak["eksternal"]["r2"],
        "pembagian kerangka lebih rendah daripada acak (pembagian acak terlalu optimistis)")
    kl = qsar.latih(data, "rf", "morgan", "acak", klasifikasi=True)
    print(f"  klasifikasi (pIC50 >= 6): BA {kl['eksternal']['ba']:.3f}, MCC {kl['eksternal']['mcc']:.3f}, "
          f"ROC-AUC {kl['eksternal'].get('roc_auc', float('nan')):.3f}")
    cek(kl["eksternal"].get("roc_auc", 0) > 0.7, "klasifikasi: ROC-AUC > 0,7")
    penting = qsar.kepentingan_permutasi(acak, data, n_ulang=3, n_teratas=5)
    cek(len(penting) > 0, f"kepentingan permutasi menghasilkan {len(penting)} fitur teratas")


if __name__ == "__main__":
    uji_konversi()
    uji_kurasi()
    uji_pembagian()
    uji_fitur()
    uji_konformal_sendiri()
    h, data = uji_pipeline_sintetis()
    uji_domain(h, data)
    uji_simpan_muat(h, data)
    uji_paragraf(h, data)
    if LAMBAT:
        uji_data_nyata()
    print("SEMUA UJI LULUS")
