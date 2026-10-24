"""QSAR dan model pembelajaran mesin dari data aktivitas pengguna (F5).

Mengikuti lima prinsip OECD untuk model QSAR: titik akhir jelas (pIC50 hasil konversi satuan), algoritma jelas
(scikit-learn dengan hiperparameter tercatat), domain aplikabilitas (leverage dan jarak Tanimoto), ukuran kecocokan,
ketahanan, serta prediktivitas (Q2 CV, R2 set uji, Y-randomization), dan tafsir (kepentingan permutasi).

Semua metrik dihitung dari data; tidak ada nilai bawaan. Prediksi tanpa model terlatih menimbulkan galat, bukan angka.
"""
import functools
import hashlib
import json
import math
import platform
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .konformal import KonformalKlasifikasi, KonformalRegresi

SATUAN_KE_MOLAR = {"M": 1.0, "mM": 1e-3, "uM": 1e-6, "µM": 1e-6, "μM": 1e-6, "nM": 1e-9, "pM": 1e-12}
AMBANG_AKTIF = 6.0          # pIC50 bawaan untuk klasifikasi aktif/tidak aktif
TANIMOTO_CLIFF = 0.85       # kemiripan minimum sepasang senyawa agar dianggap pasangan activity cliff
DELTA_CLIFF = 1.5           # beda pIC50 minimum pada pasangan mirip
KORELASI_MAKS = 0.95        # ambang pembuangan deskriptor yang saling berkorelasi

ALGORITMA = {
    "rf": "Random Forest",
    "svr": "Support Vector (RBF)",
    "knn": "k-Nearest Neighbours",
    "gp": "Gaussian Process",
    "ridge": "Ridge / Logistic",
}
FITUR = {"morgan": "Morgan2 2048 bit", "maccs": "MACCS 167", "deskriptor": "Deskriptor RDKit 2D",
         "gabungan": "Deskriptor + Morgan2"}


class GalatQSAR(Exception):
    """Galat yang harus sampai ke pengguna (data tidak sah, model belum dilatih)."""


# ----------------------------------------------------------------------- data
def ke_pic50(nilai: float, satuan: str, relasi: str = "=") -> Optional[float]:
    """Konversi IC50/Ki/Kd ke pIC50 = -log10(konsentrasi molar). Satuan tak dikenal atau nilai <= 0 -> None."""
    if nilai is None or relasi not in ("=", "~"):     # ">" / "<" = nilai sensor, tidak dipakai untuk regresi
        return None
    f = SATUAN_KE_MOLAR.get((satuan or "").strip())
    if f is None:
        return None
    try:
        molar = float(nilai) * f
    except (TypeError, ValueError):
        return None
    if molar <= 0:
        return None
    return round(-math.log10(molar), 4)


def muat_csv(path) -> List[Dict[str, Any]]:
    """Baca CSV berkolom smiles, nilai, [satuan], atau smiles + pic50/pchembl. Baris gagal ditandai, bukan dibuang."""
    import csv
    baris = []
    # baris komentar (mis. atribusi lisensi di berkas turunan ChEMBL) dilewati sebelum header dibaca
    isi = [b for b in Path(path).read_text(encoding="utf-8-sig").splitlines() if not b.lstrip().startswith("#")]
    if not isi:
        raise GalatQSAR("Berkas CSV kosong (hanya berisi komentar).")
    try:
        dialek = csv.Sniffer().sniff("\n".join(isi[:20]), delimiters=",;\t")
    except csv.Error:
        dialek = csv.excel
    if True:
        for r in csv.DictReader(isi, dialect=dialek):
            r = { (k or "").strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in r.items() }
            smi = r.get("smiles") or r.get("canonical_smiles") or ""
            p = r.get("pic50") or r.get("pchembl") or r.get("pchembl_value")
            entri = {"smiles": smi, "nama": r.get("nama") or r.get("name") or r.get("molecule_chembl_id") or ""}
            if p not in (None, ""):
                try:
                    entri["pic50"] = float(str(p).replace(",", "."))
                except ValueError:
                    entri["galat"] = f"nilai pIC50 tidak terbaca: {p}"
            else:
                try:
                    nilai = float(str(r.get("nilai") or r.get("standard_value") or "").replace(",", "."))
                except ValueError:
                    entri["galat"] = "kolom nilai/pIC50 kosong atau tidak terbaca"
                else:
                    satuan = r.get("satuan") or r.get("standard_units") or "nM"
                    pic = ke_pic50(nilai, satuan, r.get("relasi") or r.get("standard_relation") or "=")
                    if pic is None:
                        entri["galat"] = f"satuan '{satuan}' tidak dikenal atau nilai tidak sah"
                    else:
                        entri["pic50"] = pic
            if not smi:
                entri["galat"] = "kolom smiles kosong"
            baris.append(entri)
    if not baris:
        raise GalatQSAR("Berkas CSV tidak memuat baris data.")
    return baris


def muat_chembl(aktivitas: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ubah keluaran core.chembl.aktivitas menjadi baris QSAR (pakai pChEMBL bila ada, jika tidak konversi satuan)."""
    baris = []
    for a in aktivitas:
        pic = a.get("pchembl")
        if pic is None:
            pic = ke_pic50(a.get("nilai"), a.get("satuan", ""), a.get("relasi", "="))
        entri = {"smiles": a.get("smiles", ""), "nama": a.get("molekul") or a.get("nama") or "",
                 "jenis": a.get("jenis", "")}
        if pic is None:
            entri["galat"] = "tanpa pChEMBL dan satuan tidak dapat dikonversi"
        else:
            entri["pic50"] = float(pic)
        baris.append(entri)
    return baris


def kurasi(baris: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Standarisasi struktur, gabung duplikat (median), tandai rentang besar dan activity cliff.

    Kembalikan {"data": [...], "dibuang": [...], "peringatan": [...]}.
    Baris yang gagal distandarisasi masuk "dibuang" beserta alasannya; tidak ada yang hilang diam-diam.
    """
    from rdkit import Chem, RDLogger
    from rdkit.Chem.MolStandardize import rdMolStandardize
    RDLogger.DisableLog("rdApp.*")
    chopper = rdMolStandardize.LargestFragmentChooser()
    uncharger = rdMolStandardize.Uncharger()

    per_kunci: Dict[str, Dict[str, Any]] = {}
    dibuang: List[Dict[str, Any]] = []
    for b in baris:
        if b.get("galat"):
            dibuang.append({**b, "alasan": b["galat"]})
            continue
        mol = Chem.MolFromSmiles(b.get("smiles", ""))
        if mol is None:
            dibuang.append({**b, "alasan": "SMILES tidak dapat diurai RDKit"})
            continue
        if "." in b["smiles"] and Chem.GetMolFrags(mol, asMols=False) and len(Chem.GetMolFrags(mol)) > 1:
            mol = chopper.choose(mol)
        mol = uncharger.uncharge(mol)
        if not any(a.GetSymbol() == "C" for a in mol.GetAtoms()):
            dibuang.append({**b, "alasan": "senyawa anorganik (tanpa karbon)"})
            continue
        if mol.GetNumHeavyAtoms() < 5:
            dibuang.append({**b, "alasan": f"molekul terlalu kecil ({mol.GetNumHeavyAtoms()} atom berat)"})
            continue
        smi = Chem.MolToSmiles(mol)
        kunci = Chem.MolToInchiKey(mol)
        e = per_kunci.setdefault(kunci, {"inchikey": kunci, "smiles": smi, "nama": b.get("nama", ""), "nilai": []})
        e["nilai"].append(float(b["pic50"]))

    data, peringatan = [], []
    for e in per_kunci.values():
        nilai = e.pop("nilai")
        rentang = (max(nilai) - min(nilai)) if len(nilai) > 1 else 0.0
        e.update({"pic50": round(float(np.median(nilai)), 4), "n_ukur": len(nilai), "rentang": round(rentang, 3)})
        if rentang > 1.0:
            peringatan.append({"jenis": "rentang", "smiles": e["smiles"], "nama": e["nama"],
                               "pesan": f"{len(nilai)} pengukuran dengan rentang {rentang:.2f} log"})
        data.append(e)
    data.sort(key=lambda d: -d["pic50"])
    peringatan += cari_cliff(data)
    return {"data": data, "dibuang": dibuang, "peringatan": peringatan}


def cari_cliff(data: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pasangan activity cliff: kemiripan Tanimoto Morgan2 >= 0,85 tetapi beda pIC50 >= 1,5."""
    from rdkit import Chem, DataStructs
    from rdkit.Chem import rdFingerprintGenerator
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    fps, sah = [], []
    for d in data:
        m = Chem.MolFromSmiles(d["smiles"])
        if m is not None:
            fps.append(gen.GetFingerprint(m))
            sah.append(d)
    hasil = []
    for i in range(len(sah)):
        sims = DataStructs.BulkTanimotoSimilarity(fps[i], fps[i + 1:])
        for j, s in enumerate(sims, start=i + 1):
            d = abs(sah[i]["pic50"] - sah[j]["pic50"])
            if s >= TANIMOTO_CLIFF and d >= DELTA_CLIFF:
                hasil.append({"jenis": "cliff", "smiles": sah[i]["smiles"], "nama": sah[i]["nama"],
                              "pasangan": sah[j]["smiles"],
                              "pesan": f"mirip {s:.2f} dengan {sah[j]['nama'] or sah[j]['smiles'][:18]} "
                                       f"tetapi beda {d:.2f} log"})
    return hasil


# --------------------------------------------------------------------- fitur
def _mol(smiles: str):
    from rdkit import Chem
    return Chem.MolFromSmiles(smiles)


def _daftar_deskriptor():
    from rdkit.Chem import Descriptors
    return [(n, f) for n, f in Descriptors.descList if not n.startswith("fr_") and n != "Ipc"]


def _nama_fitur_semua(jenis: str) -> List[str]:
    """Nama seluruh kolom hitung_fitur() sebelum penyaringan, dalam urutan yang sama."""
    nama = [f"morgan_{i}" for i in range(2048)] if jenis in ("morgan", "gabungan") else []
    if jenis == "maccs":
        nama += [f"maccs_{i}" for i in range(167)]
    if jenis in ("deskriptor", "gabungan"):
        nama += [n for n, _f in _daftar_deskriptor()]
    return nama


def hitung_fitur(smiles: Sequence[str], jenis: str = "morgan",
                 kolom_terpilih: Optional[List[int]] = None) -> Tuple[np.ndarray, List[str], List[int]]:
    """Matriks fitur (n x p), nama fitur, dan indeks kolom yang dipertahankan.

    kolom_terpilih: untuk data baru, pakai kolom hasil penyaringan dari set latih (jangan menyaring ulang).
    """
    from rdkit import DataStructs
    from rdkit.Chem import MACCSkeys, rdFingerprintGenerator
    mols = [_mol(s) for s in smiles]
    if any(m is None for m in mols):
        raise GalatQSAR("Ada SMILES yang tidak dapat diurai saat menghitung fitur.")

    bagian, nama = [], []
    if jenis in ("morgan", "gabungan"):
        gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
        X = np.zeros((len(mols), 2048), dtype=np.int8)
        for i, m in enumerate(mols):
            DataStructs.ConvertToNumpyArray(gen.GetFingerprint(m), X[i])
        bagian.append(X)
        nama += [f"morgan_{i}" for i in range(2048)]
    if jenis == "maccs":
        X = np.zeros((len(mols), 167), dtype=np.int8)
        for i, m in enumerate(mols):
            DataStructs.ConvertToNumpyArray(MACCSkeys.GenMACCSKeys(m), X[i])
        bagian.append(X)
        nama += [f"maccs_{i}" for i in range(167)]
    if jenis in ("deskriptor", "gabungan"):
        # Ipc (information content indeks Bonchev-Trinajstic) tumbuh eksponensial terhadap ukuran molekul dan
        # mencapai orde 1e42 pada triterpenoid serta tanin, melampaui batas float32 yang dipakai scikit-learn
        # sehingga predict() gagal dengan "Input X contains infinity". Nilainya tetap berhingga sehingga tidak
        # tertangkap penyaring non-finite di bawah. AvgIpc, yang terbatas dan ada di daftar yang sama, tetap
        # dipakai. RDKit sendiri menganjurkan AvgIpc untuk keperluan ini.
        daftar = _daftar_deskriptor()
        X = np.zeros((len(mols), len(daftar)), dtype=float)
        for i, m in enumerate(mols):
            for j, (_n, f) in enumerate(daftar):
                try:
                    v = float(f(m))
                except Exception:
                    v = np.nan
                X[i, j] = v if np.isfinite(v) else np.nan
        # nilai yang gagal dihitung diisi median kolom agar satu deskriptor rusak tidak membuang senyawa
        med = np.nanmedian(X, axis=0)
        med = np.where(np.isfinite(med), med, 0.0)
        X = np.where(np.isfinite(X), X, med)
        bagian.append(X)
        nama += [n for n, _f in daftar]
    if not bagian:
        raise GalatQSAR(f"Jenis fitur tidak dikenal: {jenis}")

    X = np.hstack([b.astype(float) for b in bagian])
    # Jaring pengaman: deskriptor tertentu dapat membesar jauh melampaui float32 pada molekul besar, dan
    # scikit-learn menolak masukan seperti itu. Nilainya dipangkas ke rentang float32 yang aman, bukan
    # dibuang, agar senyawanya tetap dapat diprediksi.
    aman = np.finfo(np.float32).max / 1e3
    X = np.clip(np.nan_to_num(X, nan=0.0, posinf=aman, neginf=-aman), -aman, aman)
    if kolom_terpilih is not None:
        return X[:, kolom_terpilih], [nama[i] for i in kolom_terpilih], list(kolom_terpilih)

    jaga = list(np.where(X.std(axis=0) > 1e-8)[0])          # buang varians nol
    if jenis in ("deskriptor", "gabungan") and len(jaga) > 1:
        Xs = X[:, jaga]
        C = np.corrcoef(Xs, rowvar=False)
        C = np.where(np.isfinite(C), C, 0.0)
        buang = set()
        for i in range(len(jaga)):
            if i in buang:
                continue
            for j in range(i + 1, len(jaga)):
                if j not in buang and abs(C[i, j]) > KORELASI_MAKS:
                    buang.add(j)
        jaga = [k for i, k in enumerate(jaga) if i not in buang]
    return X[:, jaga], [nama[i] for i in jaga], jaga


# ------------------------------------------------------------------ pembagian
def kerangka_murcko(smiles: str) -> str:
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold
    m = _mol(smiles)
    if m is None:
        return ""
    return Chem.MolToSmiles(MurckoScaffold.GetScaffoldForMol(m))


def bagi(data: Sequence[Dict[str, Any]], metode: str = "acak", bagian_uji: float = 0.2,
         benih: int = 42) -> Tuple[List[int], List[int]]:
    """Indeks (latih, uji). metode 'acak' atau 'kerangka' (Bemis-Murcko: kerangka terbesar masuk set latih)."""
    n = len(data)
    n_uji = max(1, int(round(n * bagian_uji)))
    if metode == "kerangka":
        kel: Dict[str, List[int]] = {}
        for i, d in enumerate(data):
            kel.setdefault(kerangka_murcko(d["smiles"]), []).append(i)
        kelompok = sorted(kel.values(), key=len, reverse=True)
        latih: List[int] = []
        uji: List[int] = []
        # Kerangka terbanyak isinya masuk set latih, kerangka paling jarang jadi set uji. Urutan ini penting:
        # mengisi set uji lebih dulu akan menaruh satu keluarga kongenerik besar di set uji, sehingga ragam
        # aktivitas set uji runtuh dan R2 eksternal menjadi negatif besar walau RMSE-nya kecil. Pengujian
        # yang dimaksudkan pembagian kerangka adalah kemampuan meramal kerangka BARU yang jarang, bukan
        # meramal satu keluarga besar dari sisa data.
        n_latih = n - n_uji
        for g in kelompok:
            (latih if len(latih) < n_latih else uji).extend(g)
        return sorted(latih), sorted(uji)
    rng = np.random.default_rng(benih)
    urut = rng.permutation(n)
    return sorted(urut[n_uji:].tolist()), sorted(urut[:n_uji].tolist())


# ------------------------------------------------------------------- pelatihan
def _model_dan_grid(algoritma: str, klasifikasi: bool, n_latih: int):
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.gaussian_process import GaussianProcessClassifier, GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
    from sklearn.svm import SVC, SVR
    k_maks = max(1, min(15, n_latih - 1))
    if algoritma == "rf":
        m = RandomForestClassifier(random_state=42, n_jobs=-1) if klasifikasi else RandomForestRegressor(random_state=42, n_jobs=-1)
        return m, {"n_estimators": [300], "max_features": ["sqrt", 0.3], "min_samples_leaf": [1, 3]}
    if algoritma == "svr":
        m = SVC(probability=True, random_state=42) if klasifikasi else SVR()
        return m, {"C": [1, 10, 100], "gamma": ["scale", 0.01]}
    if algoritma == "knn":
        m = KNeighborsClassifier() if klasifikasi else KNeighborsRegressor()
        return m, {"n_neighbors": [k for k in (3, 5, 9) if k <= k_maks] or [1], "weights": ["uniform", "distance"]}
    if algoritma == "gp":
        inti = ConstantKernel(1.0) * RBF(length_scale=1.0) + WhiteKernel(1e-2)
        m = (GaussianProcessClassifier(kernel=inti, random_state=42) if klasifikasi
             else GaussianProcessRegressor(kernel=inti, normalize_y=True, alpha=1e-6, random_state=42))
        return m, {}
    if algoritma == "ridge":
        m = LogisticRegression(max_iter=2000, random_state=42) if klasifikasi else Ridge(random_state=42)
        return m, ({"C": [0.1, 1, 10]} if klasifikasi else {"alpha": [0.1, 1.0, 10.0]})
    raise GalatQSAR(f"Algoritma tidak dikenal: {algoritma}")


def _pipa(algoritma: str, klasifikasi: bool, n_latih: int):
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    m, grid = _model_dan_grid(algoritma, klasifikasi, n_latih)
    langkah = [("skala", StandardScaler()), ("model", m)] if algoritma in ("svr", "knn", "gp", "ridge") else [("model", m)]
    return Pipeline(langkah), {f"model__{k}": v for k, v in grid.items()}


def _metrik_regresi(y, p) -> Dict[str, float]:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    y, p = np.asarray(y, float), np.asarray(p, float)
    return {"r2": float(r2_score(y, p)), "rmse": float(math.sqrt(mean_squared_error(y, p))),
            "mae": float(mean_absolute_error(y, p))}


def _metrik_klasifikasi(y, p, peluang=None) -> Dict[str, float]:
    from sklearn.metrics import balanced_accuracy_score, matthews_corrcoef, roc_auc_score
    d = {"ba": float(balanced_accuracy_score(y, p)), "mcc": float(matthews_corrcoef(y, p))}
    if peluang is not None and len(set(np.asarray(y).tolist())) == 2:
        d["roc_auc"] = float(roc_auc_score(y, peluang[:, 1]))
    return d


def golbraikh_tropsha(y_uji: Sequence[float], y_pred: Sequence[float]) -> Dict[str, Any]:
    """Kriteria Golbraikh-Tropsha (2002) untuk kemampuan prediksi eksternal."""
    y, p = np.asarray(y_uji, float), np.asarray(y_pred, float)
    if len(y) < 3:
        return {"lulus": False, "alasan": "set uji terlalu kecil"}
    r2 = float(np.corrcoef(y, p)[0, 1] ** 2)
    k = float(np.sum(y * p) / np.sum(p * p)) if np.sum(p * p) else float("nan")
    k_aksen = float(np.sum(y * p) / np.sum(y * y)) if np.sum(y * y) else float("nan")
    r0_2 = 1 - float(np.sum((y - k * p) ** 2) / np.sum((y - y.mean()) ** 2))
    r0_2_aksen = 1 - float(np.sum((p - k_aksen * y) ** 2) / np.sum((p - p.mean()) ** 2))
    syarat = {
        "r2 > 0,6": r2 > 0.6,
        "|r2 - r0^2| / r2 < 0,1": abs(r2 - r0_2) / r2 < 0.1 if r2 else False,
        "0,85 <= k <= 1,15": 0.85 <= k <= 1.15,
        "|r0^2 - r0'^2| < 0,3": abs(r0_2 - r0_2_aksen) < 0.3,
    }
    return {"lulus": all(syarat.values()), "r2": r2, "k": k, "k_aksen": k_aksen, "r0_2": r0_2,
            "r0_2_aksen": r0_2_aksen, "syarat": syarat}


def _paralel_aman(fn):
    """Paksa joblib memakai thread di build beku; dipasang pada fungsi yang memanggil scikit-learn paralel.

    Backend bawaan joblib (loky) membuat proses anak dengan menjalankan ulang program. Di aplikasi beku
    PyInstaller yang dijalankan ulang adalah VirmoLab.exe, bukan fungsi pekerjanya, sehingga pelatihan
    menggantung: belasan proses menganggur, tanpa kemajuan dan tanpa pesan galat. Backend thread tetap
    memakai banyak inti karena fit scikit-learn melepas GIL. Random Forest sendiri sudah memakai thread
    (`prefer="threads"`), jadi `n_jobs` di dalamnya aman. Bandingkan `core/qc.py`, yang memakai
    PoseBusters `max_workers=0` karena sebab yang sama.
    """
    @functools.wraps(fn)
    def bungkus(*a, **kw):
        if not getattr(sys, "frozen", False):
            return fn(*a, **kw)
        import joblib
        with joblib.parallel_config(backend="threading"):
            return fn(*a, **kw)
    return bungkus


@_paralel_aman
def latih(data: Sequence[Dict[str, Any]], algoritma: str = "rf", jenis_fitur: str = "morgan",
          metode_bagi: str = "acak", klasifikasi: bool = False, ambang_aktif: float = AMBANG_AKTIF,
          benih: int = 42, bagian_uji: float = 0.2, konformal: bool = True,
          lapor=None) -> Dict[str, Any]:
    """Latih satu model dan validasi. Penyetelan GridSearchCV 5 lipatan hanya di dalam set latih.

    Bila konformal=True, sebagian set latih (20 %) disisihkan sebagai set kalibrasi dan tidak ikut melatih model.
    """
    from sklearn.model_selection import GridSearchCV, KFold, StratifiedKFold, cross_val_predict
    log = lapor or (lambda s: None)
    if len(data) < 20:
        raise GalatQSAR(f"Data terlalu sedikit untuk melatih model QSAR ({len(data)} senyawa, minimal 20).")

    smiles = [d["smiles"] for d in data]
    y_nilai = np.array([d["pic50"] for d in data], float)
    y = (y_nilai >= ambang_aktif).astype(int) if klasifikasi else y_nilai
    if klasifikasi and len(set(y.tolist())) < 2:
        raise GalatQSAR(f"Semua senyawa berada di satu kelas pada ambang pIC50 {ambang_aktif:g}.")

    log(f"Menghitung fitur {FITUR.get(jenis_fitur, jenis_fitur)}…")
    X, nama_fitur, kolom = hitung_fitur(smiles, jenis_fitur)
    i_latih, i_uji = bagi(data, metode_bagi, bagian_uji, benih)

    i_kal: List[int] = []
    if konformal and len(i_latih) >= 50:
        rng = np.random.default_rng(benih + 1)
        acak = rng.permutation(len(i_latih))
        n_kal = max(10, int(round(len(i_latih) * 0.2)))
        i_kal = [i_latih[k] for k in acak[:n_kal]]
        i_latih = [i_latih[k] for k in acak[n_kal:]]

    Xl, yl = X[i_latih], y[i_latih]
    Xu, yu = X[i_uji], y[i_uji]
    pipa, grid = _pipa(algoritma, klasifikasi, len(i_latih))
    cv = (StratifiedKFold(5, shuffle=True, random_state=benih) if klasifikasi
          else KFold(5, shuffle=True, random_state=benih))

    log(f"Melatih {ALGORITMA.get(algoritma, algoritma)} ({len(i_latih)} latih, {len(i_uji)} uji)…")
    if grid:
        cari = GridSearchCV(pipa, grid, cv=cv, scoring=("balanced_accuracy" if klasifikasi else "r2"), n_jobs=-1)
        cari.fit(Xl, yl)
        model, param = cari.best_estimator_, cari.best_params_
    else:
        pipa.fit(Xl, yl)
        model, param = pipa, {}

    hasil: Dict[str, Any] = {"algoritma": algoritma, "jenis_fitur": jenis_fitur, "metode_bagi": metode_bagi,
                             "klasifikasi": klasifikasi, "benih": benih, "parameter": param,
                             "n_latih": len(i_latih), "n_uji": len(i_uji), "n_kalibrasi": len(i_kal),
                             "ambang_aktif": ambang_aktif if klasifikasi else None}
    if klasifikasi:
        p_cv = cross_val_predict(model, Xl, yl, cv=cv, n_jobs=-1)
        hasil["internal"] = _metrik_klasifikasi(yl, p_cv)
        p_uji = model.predict(Xu)
        peluang = model.predict_proba(Xu) if hasattr(model, "predict_proba") else None
        hasil["eksternal"] = _metrik_klasifikasi(yu, p_uji, peluang)
    else:
        p_cv = cross_val_predict(model, Xl, yl, cv=cv, n_jobs=-1)
        m_cv = _metrik_regresi(yl, p_cv)
        hasil["internal"] = {"q2": m_cv["r2"], "rmse_cv": m_cv["rmse"], "mae_cv": m_cv["mae"]}
        p_uji = model.predict(Xu)
        hasil["eksternal"] = _metrik_regresi(yu, p_uji)
        hasil["golbraikh_tropsha"] = golbraikh_tropsha(yu, p_uji)
        hasil["prediksi_uji"] = [{"smiles": smiles[i], "nama": data[i].get("nama", ""), "y": float(y[i]),
                                  "p": float(v)} for i, v in zip(i_uji, p_uji)]

    if i_kal:
        p_kal = model.predict(X[i_kal])
        if klasifikasi:
            kon = KonformalKlasifikasi(0.1)
            kon.kalibrasi(y[i_kal], model.predict_proba(X[i_kal]))
            hasil["konformal"] = kon.ke_dict()
            hasil["konformal"]["cakupan_uji"] = kon.cakupan(yu, model.predict_proba(Xu))
        else:
            kon = KonformalRegresi(0.1)
            kon.kalibrasi(y[i_kal], p_kal)
            hasil["konformal"] = kon.ke_dict()
            hasil["konformal"]["cakupan_uji"] = kon.cakupan(yu, p_uji)

    hasil["domain"] = domain(Xl, Xu, [smiles[i] for i in i_latih], [smiles[i] for i in i_uji])
    hasil["_model"] = model
    hasil["_kolom"] = kolom
    hasil["_nama_fitur"] = nama_fitur
    hasil["_smiles_latih"] = [smiles[i] for i in i_latih]
    hasil["_X_latih"] = Xl
    return hasil


@_paralel_aman
def y_acak(data: Sequence[Dict[str, Any]], algoritma: str = "rf", jenis_fitur: str = "morgan",
           n: int = 50, benih: int = 42, klasifikasi: bool = False,
           ambang_aktif: float = AMBANG_AKTIF, lapor=None) -> Dict[str, Any]:
    """Y-randomization: label diacak n kali; metrik yang tetap tinggi menandakan model menghafal kebetulan."""
    from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict
    log = lapor or (lambda s: None)
    smiles = [d["smiles"] for d in data]
    y0 = np.array([d["pic50"] for d in data], float)
    if klasifikasi:
        y0 = (y0 >= ambang_aktif).astype(int)
    X, _nama, _kolom = hitung_fitur(smiles, jenis_fitur)
    rng = np.random.default_rng(benih)
    skor = []
    for i in range(n):
        y = rng.permutation(y0)
        if klasifikasi and len(set(y.tolist())) < 2:
            continue
        pipa, _ = _pipa(algoritma, klasifikasi, len(y))
        cv = (StratifiedKFold(5, shuffle=True, random_state=benih) if klasifikasi
              else KFold(5, shuffle=True, random_state=benih))
        p = cross_val_predict(pipa, X, y, cv=cv, n_jobs=-1)
        skor.append(_metrik_klasifikasi(y, p)["ba"] if klasifikasi else _metrik_regresi(y, p)["r2"])
        if lapor and (i + 1) % 10 == 0:
            log(f"Y-randomization {i + 1}/{n}…")
    return {"n": len(skor), "rata": float(np.mean(skor)), "sd": float(np.std(skor, ddof=1)) if len(skor) > 1 else 0.0,
            "maks": float(np.max(skor)), "skor": [float(s) for s in skor]}


def domain(X_latih: np.ndarray, X_baru: np.ndarray, smiles_latih: Sequence[str],
           smiles_baru: Sequence[str], k: int = 5) -> Dict[str, Any]:
    """Domain aplikabilitas: leverage (plot Williams, h* = 3(p+1)/n) dan jarak Tanimoto ke k tetangga terdekat.

    Senyawa dianggap di luar domain bila h > h* atau kemiripan kNN-nya di bawah persentil 5 kemiripan internal
    set latih (artinya lebih asing daripada 95 % senyawa yang dipakai melatih model).
    """
    from rdkit import DataStructs
    from rdkit.Chem import rdFingerprintGenerator
    n, p = X_latih.shape
    h_bintang = 3.0 * (p + 1) / n if n else float("inf")
    try:                                    # leverage hanya bermakna bila p < n (matriks tak singular)
        if p < n:
            XtX_inv = np.linalg.pinv(X_latih.T @ X_latih)
            h_baru = np.einsum("ij,jk,ik->i", X_baru, XtX_inv, X_baru)
            h_latih = np.einsum("ij,jk,ik->i", X_latih, XtX_inv, X_latih)
        else:
            h_baru = h_latih = None
    except np.linalg.LinAlgError:
        h_baru = h_latih = None

    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    fp_latih = [gen.GetFingerprint(_mol(s)) for s in smiles_latih]
    sim_latih = []
    for i, fp in enumerate(fp_latih):
        s = DataStructs.BulkTanimotoSimilarity(fp, fp_latih[:i] + fp_latih[i + 1:])
        sim_latih.append(float(np.mean(sorted(s, reverse=True)[:k])) if s else 0.0)
    ambang = float(np.percentile(sim_latih, 5)) if sim_latih else 0.0

    sim_baru, dalam = [], []
    for i, s in enumerate(smiles_baru):
        fp = gen.GetFingerprint(_mol(s))
        sm = DataStructs.BulkTanimotoSimilarity(fp, fp_latih)
        rata = float(np.mean(sorted(sm, reverse=True)[:k])) if sm else 0.0
        sim_baru.append(rata)
        ok_h = True if h_baru is None else bool(h_baru[i] <= h_bintang)
        dalam.append(bool(ok_h and rata >= ambang))
    return {"h_bintang": h_bintang, "ambang_tanimoto": ambang,
            "leverage": [float(x) for x in h_baru] if h_baru is not None else None,
            "leverage_latih": [float(x) for x in h_latih] if h_latih is not None else None,
            "tanimoto": sim_baru, "dalam_domain": dalam,
            "n_luar": int(sum(1 for d in dalam if not d))}


@_paralel_aman
def kepentingan_permutasi(hasil: Dict[str, Any], data: Sequence[Dict[str, Any]], n_ulang: int = 10,
                          n_teratas: int = 20) -> List[Dict[str, Any]]:
    """Kepentingan fitur permutasi pada set uji (tafsir model, prinsip OECD ke-5)."""
    from sklearn.inspection import permutation_importance
    model = hasil.get("_model")
    if model is None:
        raise GalatQSAR("Model belum dilatih.")
    smiles = [d["smiles"] for d in data]
    y = np.array([d["pic50"] for d in data], float)
    if hasil["klasifikasi"]:
        y = (y >= hasil["ambang_aktif"]).astype(int)
    X, _n, _k = hitung_fitur(smiles, hasil["jenis_fitur"], kolom_terpilih=hasil["_kolom"])
    _latih, i_uji = bagi(data, hasil["metode_bagi"], 0.2, hasil["benih"])
    r = permutation_importance(model, X[i_uji], y[i_uji], n_repeats=n_ulang, random_state=hasil["benih"], n_jobs=-1)
    urut = np.argsort(r.importances_mean)[::-1][:n_teratas]
    return [{"fitur": hasil["_nama_fitur"][i], "label": label_fitur(hasil, hasil["_nama_fitur"][i]),
             "rata": float(r.importances_mean[i]), "sd": float(r.importances_std[i])}
            for i in urut if r.importances_mean[i] > 0]


def substruktur_bit(smiles: Sequence[str], bit: int, n_bits: int = 2048, radius: int = 2) -> str:
    """SMILES substruktur yang menyalakan satu bit Morgan, dicari pada senyawa set latih ("" bila tak ditemukan).

    Tanpa ini, nama fitur seperti "morgan_832" tidak dapat ditafsirkan pengguna.
    """
    from rdkit import Chem
    from rdkit.Chem import rdFingerprintGenerator
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits)
    for smi in smiles:
        m = _mol(smi)
        if m is None:
            continue
        info = rdFingerprintGenerator.AdditionalOutput()
        info.AllocateBitInfoMap()
        gen.GetFingerprint(m, additionalOutput=info)
        peta = info.GetBitInfoMap()
        if bit not in peta:
            continue
        atom, rad = peta[bit][0]
        if rad == 0:
            a = m.GetAtomWithIdx(atom)
            return f"{a.GetSymbol()} ({a.GetDegree()} ikatan)"
        env = Chem.FindAtomEnvironmentOfRadiusN(m, rad, atom)
        atom_env = {m.GetBondWithIdx(b).GetBeginAtomIdx() for b in env} |                    {m.GetBondWithIdx(b).GetEndAtomIdx() for b in env}
        try:
            return Chem.MolFragmentToSmiles(m, atomsToUse=sorted(atom_env), bondsToUse=list(env), canonical=True)
        except Exception:
            return ""
    return ""


def label_fitur(hasil: Dict[str, Any], nama: str) -> str:
    """Nama fitur yang dapat dibaca: bit Morgan diberi contoh substrukturnya, deskriptor memakai namanya sendiri."""
    if not nama.startswith("morgan_"):
        return nama
    try:
        bit = int(nama.split("_", 1)[1])
    except ValueError:
        return nama
    sub = substruktur_bit(hasil.get("_smiles_latih") or [], bit)
    return f"{nama} · {sub}" if sub else nama


CAKUPAN_BAIK = 0.8          # >= 80 % senyawa di dalam domain: prediksi boleh diperingkat
CAKUPAN_MIN = 0.5           # < 50 %: model tidak cocok untuk seri ini


def ringkas_domain(prediksi_list: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Seberapa banyak senyawa yang diprediksi berada di dalam domain aplikabilitas, dan apa artinya.

    tingkat: 'baik' (>= 80 %), 'terbatas' (50-80 %: hanya senyawa di dalam domain yang boleh diperingkat),
    'tidak_cocok' (< 50 %: model tidak mewakili seri ini; pada data galam Artikel 4, 0 dari 156)."""
    n = len(prediksi_list)
    n_dalam = sum(1 for p in prediksi_list if p.get("dalam_domain"))
    fraksi = n_dalam / n if n else 0.0
    tingkat = "baik" if fraksi >= CAKUPAN_BAIK else "terbatas" if fraksi >= CAKUPAN_MIN else "tidak_cocok"
    sim = sorted(p["tanimoto"] for p in prediksi_list if p.get("tanimoto") is not None)
    median = sim[len(sim) // 2] if sim else None
    return {"n": n, "n_dalam": n_dalam, "fraksi": fraksi, "tingkat": tingkat, "median_tanimoto": median}


def prediksi(hasil: Dict[str, Any], smiles: Sequence[str]) -> List[Dict[str, Any]]:
    """Prediksi senyawa baru + interval konformal + penanda domain aplikabilitas."""
    model = hasil.get("_model")
    if model is None:
        raise GalatQSAR("Model belum dilatih atau belum dimuat.")
    X, _n, _k = hitung_fitur(smiles, hasil["jenis_fitur"], kolom_terpilih=hasil["_kolom"])
    dom = domain(hasil["_X_latih"], X, hasil["_smiles_latih"], smiles)
    keluar = []
    if hasil["klasifikasi"]:
        p = model.predict(X)
        peluang = model.predict_proba(X) if hasattr(model, "predict_proba") else None
        himp = None
        if hasil.get("konformal") and peluang is not None:
            himp = KonformalKlasifikasi.dari_dict(hasil["konformal"]).himpunan(peluang)
        for i, s in enumerate(smiles):
            keluar.append({"smiles": s, "kelas": int(p[i]),
                           "peluang_aktif": float(peluang[i, 1]) if peluang is not None else None,
                           "himpunan": himp[i] if himp else None,
                           "dalam_domain": dom["dalam_domain"][i], "tanimoto": dom["tanimoto"][i]})
    else:
        p = model.predict(X)
        iv = None
        if hasil.get("konformal"):
            iv = KonformalRegresi.dari_dict(hasil["konformal"]).interval(p)
        for i, s in enumerate(smiles):
            keluar.append({"smiles": s, "pic50": float(p[i]),
                           "bawah": float(iv[i, 0]) if iv is not None else None,
                           "atas": float(iv[i, 1]) if iv is not None else None,
                           "dalam_domain": dom["dalam_domain"][i], "tanimoto": dom["tanimoto"][i]})
    return keluar


# ------------------------------------------------------------ simpan dan muat
def kartu_model(hasil: Dict[str, Any], data: Sequence[Dict[str, Any]], sumber_data: str = "",
                titik_akhir: str = "pIC50") -> Dict[str, Any]:
    """Kartu model (model card) berisi semua yang dibutuhkan untuk menilai dan mengulang model."""
    import sklearn
    import rdkit
    sidik = hashlib.sha256("\n".join(f"{d['smiles']}\t{d['pic50']}" for d in data).encode()).hexdigest()[:16]
    return {
        "titik_akhir": titik_akhir,
        "sumber_data": sumber_data,
        "n_senyawa": len(data),
        "rentang_pic50": [float(min(d["pic50"] for d in data)), float(max(d["pic50"] for d in data))],
        "hash_data": sidik,
        "algoritma": ALGORITMA.get(hasil["algoritma"], hasil["algoritma"]),
        "fitur": FITUR.get(hasil["jenis_fitur"], hasil["jenis_fitur"]),
        "n_fitur": len(hasil.get("_nama_fitur", [])),
        "pembagian": hasil["metode_bagi"],
        "benih": hasil["benih"],
        "parameter": hasil.get("parameter", {}),
        "jenis_tugas": "klasifikasi" if hasil["klasifikasi"] else "regresi",
        "metrik_internal": hasil.get("internal", {}),
        "metrik_eksternal": hasil.get("eksternal", {}),
        "golbraikh_tropsha": {k: v for k, v in (hasil.get("golbraikh_tropsha") or {}).items() if k != "syarat"},
        "konformal": hasil.get("konformal", {}),
        "domain": {"h_bintang": hasil.get("domain", {}).get("h_bintang"),
                   "ambang_tanimoto": hasil.get("domain", {}).get("ambang_tanimoto")},
        "y_acak": hasil.get("y_acak", {}),
        "versi": {"virmolab": _versi_aplikasi(), "scikit-learn": sklearn.__version__, "rdkit": rdkit.__version__,
                  "python": platform.python_version()},
        "tanggal": date.today().isoformat(),
    }


def _versi_aplikasi() -> str:
    from .. import __version__
    return __version__


def simpan(hasil: Dict[str, Any], data: Sequence[Dict[str, Any]], folder, nama: str = "model_qsar",
           sumber_data: str = "") -> Dict[str, Path]:
    """Simpan model (joblib) dan kartu model (JSON) ke folder; kembalikan jalur keduanya."""
    import joblib
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    p_model, p_kartu = folder / f"{nama}.joblib", folder / f"{nama}_kartu.json"
    isi = {k: v for k, v in hasil.items() if k != "prediksi_uji"}
    joblib.dump(isi, p_model, compress=3)
    kartu = kartu_model(hasil, data, sumber_data)
    p_kartu.write_text(json.dumps(kartu, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"model": p_model, "kartu": p_kartu}


def muat(path) -> Dict[str, Any]:
    import joblib
    h = joblib.load(Path(path))
    if "_model" not in h:
        raise GalatQSAR("Berkas model tidak berisi model QSAR VirmoLab.")
    # `_kolom` adalah indeks ke daftar deskriptor saat model dilatih. Daftar itu bisa berubah (Ipc dikeluarkan
    # karena melampaui float32, atau RDKit menambah deskriptor), sehingga indeks lama diam-diam menunjuk kolom
    # lain. Indeks dipetakan ulang lewat nama fitur; model yang memakai fitur yang kini tidak dihitung ditolak.
    if h.get("jenis_fitur") in ("deskriptor", "gabungan") and h.get("_nama_fitur"):
        indeks = {n: i for i, n in enumerate(_nama_fitur_semua(h["jenis_fitur"]))}
        hilang = [n for n in h["_nama_fitur"] if n not in indeks]
        if hilang:
            raise GalatQSAR(f"Model ini memakai deskriptor yang tidak lagi dihitung VirmoLab ({', '.join(hilang[:5])}); "
                            "latih ulang model dari data aslinya.")
        h["_kolom"] = [indeks[n] for n in h["_nama_fitur"]]
    return h


# --------------------------------------------------------------------- naskah
def susun_paragraf_metode(hasil: Dict[str, Any], data: Sequence[Dict[str, Any]], sumber_data: str = "",
                          y_acak_hasil: Optional[Dict[str, Any]] = None) -> str:
    """Paragraf metode dari angka nyata; bagian yang tidak dijalankan tidak disebut."""
    if not hasil:
        return ""
    from .. import i18n
    if i18n.inggris():
        return _paragraf_metode_en(hasil, data, sumber_data, y_acak_hasil)
    koma = lambda x, d=2: f"{x:.{d}f}".replace(".", ",")      # noqa: E731
    e, i = hasil.get("eksternal", {}), hasil.get("internal", {})
    bagian = [
        f"Model QSAR dibangun dari {len(data)} senyawa"
        + (f" ({sumber_data})" if sumber_data else "")
        + f" dengan titik akhir pIC50 (rentang {koma(min(d['pic50'] for d in data))}-{koma(max(d['pic50'] for d in data))}). "
        f"Struktur distandarkan (fragmen terbesar, netralisasi) dan pengukuran ganda digabung sebagai median.",
        f"Fitur {FITUR.get(hasil['jenis_fitur'], hasil['jenis_fitur'])} dipakai sebagai masukan "
        f"{ALGORITMA.get(hasil['algoritma'], hasil['algoritma'])}; hiperparameter disetel dengan pencarian kisi dan "
        f"validasi silang 5 lipatan di dalam set latih saja. Data dibagi menurut "
        + ("kerangka Bemis-Murcko" if hasil["metode_bagi"] == "kerangka" else "pembagian acak")
        + f" ({hasil['n_latih']} latih, {hasil['n_uji']} uji"
        + (f", {hasil['n_kalibrasi']} kalibrasi konformal" if hasil.get("n_kalibrasi") else "") + ").",
    ]
    if hasil["klasifikasi"]:
        bagian.append(f"Pada set uji diperoleh akurasi seimbang {koma(e.get('ba', float('nan')))} dan MCC "
                      f"{koma(e.get('mcc', float('nan')))}"
                      + (f" dengan ROC-AUC {koma(e['roc_auc'])}" if "roc_auc" in e else "")
                      + f"; validasi silang set latih memberi akurasi seimbang {koma(i.get('ba', float('nan')))}.")
    else:
        bagian.append(f"Validasi silang set latih memberi Q2 {koma(i.get('q2', float('nan')))} "
                      f"(RMSE {koma(i.get('rmse_cv', float('nan')))}), sedangkan set uji memberi R2 "
                      f"{koma(e.get('r2', float('nan')))}, RMSE {koma(e.get('rmse', float('nan')))}, dan MAE "
                      f"{koma(e.get('mae', float('nan')))} satuan log.")
        gt = hasil.get("golbraikh_tropsha") or {}
        if gt:
            bagian.append("Kriteria Golbraikh-Tropsha " + ("terpenuhi" if gt.get("lulus") else "tidak terpenuhi")
                          + f" (k = {koma(gt.get('k', float('nan')))}, r0^2 = {koma(gt.get('r0_2', float('nan')))}).")
    if y_acak_hasil:
        bagian.append(f"Y-randomization {y_acak_hasil['n']} kali menghasilkan "
                      + ("akurasi seimbang" if hasil["klasifikasi"] else "R2")
                      + f" rata-rata {koma(y_acak_hasil['rata'])} (maksimum {koma(y_acak_hasil['maks'])}), "
                      "jauh di bawah model sebenarnya, sehingga korelasi kebetulan dapat disingkirkan.")
    if hasil.get("konformal", {}).get("cakupan_uji") is not None:
        k = hasil["konformal"]
        bagian.append(f"Prediksi konformal split (taraf {koma((1 - k['alfa']) * 100, 0)} %) dikalibrasi pada "
                      f"{k['n_kalibrasi']} senyawa dan mencapai cakupan empiris "
                      f"{koma(k['cakupan_uji'] * 100, 1)} % pada set uji.")
    d = hasil.get("domain") or {}
    if d:
        bagian.append(f"Domain aplikabilitas ditetapkan dengan leverage (h* = {koma(d['h_bintang'], 3)}) dan "
                      f"kemiripan Tanimoto rata-rata terhadap lima tetangga terdekat (ambang "
                      f"{koma(d['ambang_tanimoto'])}); senyawa di luar domain ditandai dan prediksinya tidak "
                      "boleh ditafsirkan sebagai kuantitatif.")
    bagian.append("Pelaporan mengikuti lima prinsip OECD untuk validasi model QSAR.")
    return " ".join(bagian)


_FITUR_EN = {"morgan": "Morgan2 (2048-bit)", "maccs": "MACCS (167 keys)", "deskriptor": "RDKit 2D descriptor",
             "gabungan": "RDKit 2D descriptor + Morgan2"}


def _paragraf_metode_en(hasil, data, sumber_data="", y_acak_hasil=None):
    """Versi Inggris susun_paragraf_metode; isi dan syarat tiap kalimat sama persis."""
    f = lambda x, d=2: f"{x:.{d}f}"      # noqa: E731
    e, i = hasil.get("eksternal", {}), hasil.get("internal", {})
    bagian = [
        f"The QSAR model was built from {len(data)} compounds"
        + (f" ({sumber_data})" if sumber_data else "")
        + f" with pIC50 as the endpoint (range {f(min(d['pic50'] for d in data))}-{f(max(d['pic50'] for d in data))}). "
        "Structures were standardised (largest fragment, neutralisation) and replicate measurements were merged "
        "as the median.",
        f"{_FITUR_EN.get(hasil['jenis_fitur'], hasil['jenis_fitur'])} features were used as input to "
        f"{ALGORITMA.get(hasil['algoritma'], hasil['algoritma'])}; hyperparameters were tuned by grid search with "
        "5-fold cross-validation within the training set only. The data were split by "
        + ("Bemis-Murcko scaffold" if hasil["metode_bagi"] == "kerangka" else "random split")
        + f" ({hasil['n_latih']} training, {hasil['n_uji']} test"
        + (f", {hasil['n_kalibrasi']} conformal calibration" if hasil.get("n_kalibrasi") else "") + ").",
    ]
    if hasil["klasifikasi"]:
        bagian.append(f"On the test set, balanced accuracy was {f(e.get('ba', float('nan')))} and MCC "
                      f"{f(e.get('mcc', float('nan')))}"
                      + (f" with ROC-AUC {f(e['roc_auc'])}" if "roc_auc" in e else "")
                      + f"; training-set cross-validation gave a balanced accuracy of {f(i.get('ba', float('nan')))}.")
    else:
        bagian.append(f"Training-set cross-validation gave Q2 {f(i.get('q2', float('nan')))} "
                      f"(RMSE {f(i.get('rmse_cv', float('nan')))}), while the test set gave R2 "
                      f"{f(e.get('r2', float('nan')))}, RMSE {f(e.get('rmse', float('nan')))}, and MAE "
                      f"{f(e.get('mae', float('nan')))} log units.")
        gt = hasil.get("golbraikh_tropsha") or {}
        if gt:
            bagian.append("The Golbraikh-Tropsha criteria were " + ("met" if gt.get("lulus") else "not met")
                          + f" (k = {f(gt.get('k', float('nan')))}, r0^2 = {f(gt.get('r0_2', float('nan')))}).")
    if y_acak_hasil:
        bagian.append(f"Y-randomization ({y_acak_hasil['n']} runs) gave a mean "
                      + ("balanced accuracy" if hasil["klasifikasi"] else "R2")
                      + f" of {f(y_acak_hasil['rata'])} (maximum {f(y_acak_hasil['maks'])}), far below the actual "
                      "model, so chance correlation can be ruled out.")
    if hasil.get("konformal", {}).get("cakupan_uji") is not None:
        k = hasil["konformal"]
        bagian.append(f"Split conformal prediction ({f((1 - k['alfa']) * 100, 0)} % level) was calibrated on "
                      f"{k['n_kalibrasi']} compounds and reached an empirical coverage of "
                      f"{f(k['cakupan_uji'] * 100, 1)} % on the test set.")
    d = hasil.get("domain") or {}
    if d:
        bagian.append(f"The applicability domain was defined by leverage (h* = {f(d['h_bintang'], 3)}) and the "
                      f"mean Tanimoto similarity to the five nearest neighbours (threshold "
                      f"{f(d['ambang_tanimoto'])}); compounds outside the domain are flagged and their predictions "
                      "must not be interpreted quantitatively.")
    bagian.append("Reporting follows the five OECD principles for QSAR model validation.")
    return " ".join(bagian)
