"""Penapisan bertahap dengan pembelajaran aktif (active learning) untuk pustaka besar.

Mendocking seluruh pustaka besar (puluhan sampai ratusan ribu senyawa, mis. COCONUT ±700 ribu bahan alam) memakan
waktu berhari-hari. Penapisan bertahap mendocking sebagian kecil pustaka, melatih model pengganti (surrogate) yang
memprediksi skor docking dari sidik jari molekul, lalu memilih batch berikutnya menurut fungsi akuisisi. Rancangannya
mengikuti MolPAL (Graff, Shakhnovich & Coley, Chem. Sci. 2021;12:7866-7881): sidik jari pasangan atom (atom pair)
2048 bit, ensemble jaringan saraf atau random forest dengan ketidakpastian dari sebaran prediksi anggotanya, akuisisi
greedy atau UCB, batch awal acak lalu batch berukuran sama tiap putaran.

Uji retrospektif dengan skor docking Enamine 10k dari MolPAL (dev/tolok_ukur_al.py; 6 % pustaka didocking): sidik
jari pasangan atom menemukan ±64 % senyawa 1 % teratas dengan jaringan saraf dan ±50 % dengan random forest, setara
angka makalah MolPAL; sidik jari Morgan hanya ±40-45 %, pemilihan acak ±6 %.

Modul ini murni (tanpa Qt): membaca pustaka, sidik jari, model, akuisisi, status kampanye yang disimpan di proyek, dan
uji retrospektif terhadap skor yang sudah diketahui (dev/tolok_ukur_al.py). Docking tiap batch lewat antrean biasa.
"""
import csv
import gzip
import io
import itertools
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

NBIT = 2048
JARAK_MAKS = 3                  # pasangan atom berjarak topologi 1-3 ikatan (bawaan MolPAL: radius 2 -> maxLength 3)
POTONGAN = 8192                 # baris per potongan prediksi (bit dibuka ke float32 hanya per potongan)
EKSTENSI = (".smi", ".smiles", ".txt", ".csv", ".tsv", ".sdf", ".gz")
KOLOM_SMILES = ("smiles", "canonical_smiles", "isomeric_smiles", "smi", "smiles_kanonik")
KOLOM_NAMA = ("nama", "name", "id", "identifier", "title", "compound", "compound_id", "molecule_name", "zinc_id",
              "chembl_id", "coconut_id", "catalog_id", "idnumber")
MODEL = {"rf": "Random forest", "mlp": "Jaringan saraf (ensemble)"}
AKUISISI = {"ucb": "UCB (prediksi + ketidakpastian)", "greedy": "Greedy (prediksi terbaik)", "acak": "Acak (pembanding)"}
BAWAAN = {"model": "mlp", "akuisisi": "greedy", "beta": 2.0, "awal": 0, "batch": 0, "putaran": 5, "seed": 42,
          "persen": 1.0}
SITASI = ("Graff DE, Shakhnovich EI, Coley CW. Accelerating high-throughput virtual screening through molecular "
          "pool-based active learning. Chem Sci. 2021;12(22):7866-7881. doi:10.1039/D0SC06805E")


class GalatPustaka(ValueError):
    pass


def _generator():
    """Sidik jari pasangan atom ter-hash 2048 bit (jarak 1-3 ikatan). Bitnya identik dengan bawaan MolPAL,
    rdMolDescriptors.GetHashedAtomPairFingerprintAsBitVect(mol, minLength=1, maxLength=3, nBits=2048)."""
    from rdkit.Chem import rdFingerprintGenerator
    return rdFingerprintGenerator.GetAtomPairGenerator(minDistance=1, maxDistance=JARAK_MAKS, fpSize=NBIT)


# ----------------------------------------------------------------------------------------------- pustaka
def _buka(path):
    """Berkas teks (boleh .gz) -> (objek berkas, ekstensi format di balik .gz)."""
    p = Path(path)
    suf = p.suffix.lower()
    if suf == ".gz":
        return io.TextIOWrapper(gzip.open(p, "rb"), encoding="utf-8", errors="replace", newline=""), \
            Path(p.stem).suffix.lower()
    return open(p, encoding="utf-8", errors="replace", newline=""), suf


def _kolom(header, calon):
    h = [x.strip().lower() for x in header]
    return next((h.index(c) for c in calon if c in h), None)


def _format(path):
    p = Path(path)
    return Path(p.stem).suffix.lower() if p.suffix.lower() == ".gz" else p.suffix.lower()


def baca_entri(path, batas=None):
    """[(smiles, nama)] dari .smi/.txt (SMILES [nama]), .csv/.tsv (kolom 'smiles' + nama/id), atau .sdf; boleh .gz.
    Belum memeriksa kimia (dikerjakan siapkan_pustaka)."""
    hasil = []
    if _format(path) == ".sdf":
        from rdkit import Chem, RDLogger
        RDLogger.DisableLog("rdApp.*")
        with (gzip.open(path, "rb") if str(path).lower().endswith(".gz") else open(path, "rb")) as f:
            for i, m in enumerate(Chem.ForwardSDMolSupplier(f, sanitize=True, removeHs=True)):
                if batas and len(hasil) >= batas:
                    break
                if m is None:
                    hasil.append(("", f"SDF#{i + 1}"))
                    continue
                nama = m.GetProp("_Name").strip() if m.HasProp("_Name") else ""
                hasil.append((Chem.MolToSmiles(m), nama or f"SDF#{i + 1}"))
        return hasil
    f, fmt = _buka(path)
    with f:
        if fmt in (".csv", ".tsv"):
            baris = csv.reader(f, delimiter="\t" if fmt == ".tsv" else ",")
            header = next(baris, None)
            if header is None:
                return hasil
            ks, kn = _kolom(header, KOLOM_SMILES), _kolom(header, KOLOM_NAMA)
            if ks is None:                      # tanpa judul kolom: kolom 1 SMILES, kolom 2 nama
                ks, kn = 0, (1 if len(header) > 1 else None)
                baris = itertools.chain([header], baris)
            for r in baris:
                if batas and len(hasil) >= batas:
                    break
                if len(r) <= ks or not r[ks].strip():
                    continue
                hasil.append((r[ks].strip(), r[kn].strip() if kn is not None and len(r) > kn else ""))
            return hasil
        for b in f:                             # .smi / .smiles / .txt
            if batas and len(hasil) >= batas:
                break
            b = b.strip()
            if not b or b.startswith("#"):
                continue
            bag = b.split(None, 1)
            if bag[0].lower() in ("smiles", "smi"):   # baris judul
                continue
            hasil.append((bag[0], bag[1].strip() if len(bag) > 1 else ""))
    return hasil


@dataclass
class Pustaka:
    smiles: list                        # SMILES kanonik unik (RDKit), satu fragmen terbesar
    nama: list
    fp: np.ndarray                      # uint8 [N, NBIT/8]: sidik jari pasangan atom dipadatkan (np.packbits)
    ringkasan: dict = field(default_factory=dict)

    def __len__(self):
        return len(self.smiles)

    def X(self, idx):
        """Matriks fitur float32 [len(idx), NBIT] untuk baris idx."""
        return np.unpackbits(self.fp[np.asarray(idx, dtype=np.int64)], axis=1).astype(np.float32)


def siapkan_pustaka(entri, lapor=None, batal=None):
    """[(smiles, nama)] -> Pustaka: SMILES diperiksa RDKit, garam/pelarut dibuang (fragmen terbesar), duplikat dibuang
    (SMILES kanonik), sidik jari pasangan atom 2048 bit."""
    from rdkit import Chem, RDLogger
    from rdkit.Chem.MolStandardize import rdMolStandardize
    RDLogger.DisableLog("rdApp.*")
    gen = _generator()
    pilih = rdMolStandardize.LargestFragmentChooser(preferOrganic=True)
    terlihat = set()
    smi, nama, fp = [], [], []
    tidak_valid = ganda = garam = 0
    n = len(entri)
    for i, (s, nm) in enumerate(entri):
        if batal is not None and batal():
            raise InterruptedError("Dibatalkan.")
        m = Chem.MolFromSmiles(s) if s else None
        if m is None or m.GetNumHeavyAtoms() == 0:
            tidak_valid += 1
            continue
        if len(Chem.GetMolFrags(m)) > 1:
            m = pilih.choose(m)
            garam += 1
        k = Chem.MolToSmiles(m)
        if k in terlihat:
            ganda += 1
            continue
        terlihat.add(k)
        smi.append(k)
        nama.append(nm or f"L{i + 1:07d}")
        fp.append(np.packbits(gen.GetFingerprintAsNumPy(m)))
        if lapor is not None and i % 2000 == 0:
            lapor.progres.emit(i, n, f"Sidik jari {i:,}/{n:,}".replace(",", "."))
    arr = np.vstack(fp) if fp else np.zeros((0, NBIT // 8), np.uint8)
    return Pustaka(smi, nama, arr, {"dibaca": n, "valid": len(smi), "tidak_valid": tidak_valid, "ganda": ganda,
                                    "garam": garam})


def tulis_pustaka(pustaka, path):
    """Simpan pustaka (SMILES kanonik + nama) ke TSV.gz di folder proyek; urutan baris = indeks kampanye."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as f:
        f.write("smiles\tnama\n")
        for s, n in zip(pustaka.smiles, pustaka.nama):
            f.write(f"{s}\t{n.replace(chr(9), ' ')}\n")


def pustaka_dari_berkas(path, lapor=None):
    """Baca ulang pustaka kampanye (tulis_pustaka) tanpa membuang baris apa pun, supaya indeks tetap sama.
    SMILES yang (tak terduga) gagal dibaca mendapat sidik jari nol."""
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    gen = _generator()
    with gzip.open(path, "rt", encoding="utf-8") as f:
        next(f, None)
        baris = [b.rstrip("\n").split("\t", 1) for b in f if b.strip()]
    n = len(baris)
    fp = np.zeros((n, NBIT // 8), dtype=np.uint8)
    for i, (s, _nm) in enumerate(baris):
        m = Chem.MolFromSmiles(s)
        if m is not None:
            fp[i] = np.packbits(gen.GetFingerprintAsNumPy(m))
        if lapor is not None and i % 2000 == 0:
            lapor.progres.emit(i, n, "Memuat pustaka")
    return Pustaka([b[0] for b in baris], [b[1] if len(b) > 1 else "" for b in baris], fp, {"valid": n})


# ----------------------------------------------------------------------------------------------- model
class ModelRF:
    """Random forest (sklearn); ketidakpastian = simpangan baku prediksi antarpohon (seperti MolPAL)."""
    nama = MODEL["rf"]

    def __init__(self, seed=42, n_pohon=100, kedalaman=None, daun=1):
        self.seed, self.n_pohon, self.kedalaman, self.daun = seed, n_pohon, kedalaman, daun
        self.m = None

    def latih(self, X, y):
        from sklearn.ensemble import RandomForestRegressor
        self.m = RandomForestRegressor(n_estimators=self.n_pohon, max_depth=self.kedalaman,
                                       min_samples_leaf=self.daun, max_features=1.0, n_jobs=-1,
                                       random_state=self.seed)
        self.m.fit(X, y)
        return self

    def prediksi(self, X):
        pohon = self.m.estimators_
        with ThreadPoolExecutor(max_workers=8) as ex:     # predict pohon sklearn melepas GIL
            P = np.stack(list(ex.map(lambda t: t.predict(X), pohon)))
        return P.mean(0), P.std(0)


class ModelMLP:
    """Ensemble jaringan saraf umpan maju (sklearn MLPRegressor, 2 lapis × 100 neuron); ketidakpastian = sebaran
    prediksi antaranggota."""
    nama = MODEL["mlp"]

    def __init__(self, seed=42, anggota=3, lapis=(100, 100)):
        self.seed, self.anggota, self.lapis = seed, anggota, lapis
        self.m, self.rata, self.sb = [], 0.0, 1.0

    def latih(self, X, y):
        from sklearn.neural_network import MLPRegressor
        y = np.asarray(y, dtype=np.float64)
        self.rata, self.sb = float(y.mean()), float(y.std() or 1.0)
        z = (y - self.rata) / self.sb
        self.m = [MLPRegressor(hidden_layer_sizes=self.lapis, alpha=1e-3, learning_rate_init=1e-3, max_iter=200,
                               early_stopping=len(y) >= 200, n_iter_no_change=10, random_state=self.seed + i)
                  .fit(X, z) for i in range(self.anggota)]
        return self

    def prediksi(self, X):
        P = np.stack([m.predict(X) for m in self.m]) * self.sb + self.rata
        return P.mean(0), P.std(0)


def buat_model(jenis, seed=42):
    return ModelMLP(seed=seed) if jenis == "mlp" else ModelRF(seed=seed)


def prediksi_potongan(model, pustaka, idx, lapor=None):
    """Prediksi (rata, sb) untuk banyak baris tanpa membuka seluruh sidik jari sekaligus."""
    idx = np.asarray(idx, dtype=np.int64)
    mu = np.empty(len(idx))
    sd = np.empty(len(idx))
    for a in range(0, len(idx), POTONGAN):
        b = min(a + POTONGAN, len(idx))
        mu[a:b], sd[a:b] = model.prediksi(pustaka.X(idx[a:b]))
        if lapor is not None:
            lapor.progres.emit(b, len(idx), "Memprediksi skor")
    return mu, sd


def nilai_akuisisi(mu, sd, cara, beta=2.0, rng=None):
    """Nilai akuisisi; makin kecil makin diprioritaskan (skor docking: makin negatif makin baik)."""
    if cara == "greedy":
        return mu
    if cara == "ucb":
        return mu - beta * sd
    rng = rng or np.random.default_rng()
    return rng.random(len(mu))


def _ambil_terkecil(nilai, k):
    k = min(k, len(nilai))
    if k <= 0:
        return np.zeros(0, dtype=np.int64)
    pos = np.argpartition(nilai, k - 1)[:k]
    return pos[np.argsort(nilai[pos], kind="stable")]


def mutu_prediksi(prediksi, aktual):
    """Mutu prediksi prospektif (sebelum docking) terhadap skor docking: r Pearson, rho Spearman, MAE."""
    pasang = [(prediksi[i], aktual[i]) for i in prediksi if aktual.get(i) is not None]
    if len(pasang) < 5:
        return {}
    p, a = np.array(pasang).T
    from scipy.stats import spearmanr
    r = float(np.corrcoef(p, a)[0, 1]) if p.std() > 0 and a.std() > 0 else float("nan")
    rho = float(spearmanr(p, a).statistic) if p.std() > 0 and a.std() > 0 else float("nan")
    return {"n": len(pasang), "r": r, "rho": rho, "mae": float(np.mean(np.abs(p - a)))}


# ----------------------------------------------------------------------------------------------- kampanye
class Kampanye:
    """Status skrining bertahap yang bisa disimpan di proyek (ke_dict/dari_dict).

    skor     : {indeks pustaka: skor docking (kkal/mol) | None (gagal disiapkan/didocking)}
    putaran  : [{ke, indeks, metode, prediksi {indeks: rata}, mutu {...}, job}]
    """

    def __init__(self, n, pengaturan=None, skor=None, putaran=None):
        self.n = int(n)
        self.p = {**BAWAAN, **(pengaturan or {})}
        self.skor = dict(skor or {})
        self.putaran = list(putaran or [])

    # ---- ukuran
    def _persen(self, nilai):
        if nilai:
            return int(min(nilai, self.n))
        return int(min(self.n, max(50, round(self.n * self.p["persen"] / 100))))

    def ukuran_awal(self):
        return self._persen(self.p["awal"])

    def ukuran_batch(self):
        return self._persen(self.p["batch"])

    def total_rencana(self):
        return min(self.n, self.ukuran_awal() + self.p["putaran"] * self.ukuran_batch())

    def selesai(self):
        """Semua putaran rencana sudah didocking (atau pustaka habis)."""
        return len(self.putaran) > self.p["putaran"] or len(self.skor) >= self.n

    # ---- data
    def dievaluasi(self):
        return np.fromiter(self.skor.keys(), dtype=np.int64, count=len(self.skor))

    def latih_data(self):
        idx = [i for i, s in self.skor.items() if s is not None and math.isfinite(s)]
        return np.array(idx, dtype=np.int64), np.array([self.skor[i] for i in idx], dtype=np.float64)

    def kandidat(self):
        sudah = np.zeros(self.n, dtype=bool)
        if self.skor:
            sudah[self.dievaluasi()] = True
        for p in self.putaran:            # batch yang sedang didocking juga bukan kandidat
            sudah[np.asarray(p["indeks"], dtype=np.int64)] = True
        return np.flatnonzero(~sudah)

    # ---- langkah
    def batch_awal(self):
        rng = np.random.default_rng(self.p["seed"])
        idx = np.sort(rng.choice(self.n, size=self.ukuran_awal(), replace=False))
        self.putaran.append({"ke": 0, "indeks": idx.tolist(), "metode": "acak", "prediksi": {}, "mutu": {}})
        return idx.tolist()

    def catat(self, hasil):
        """hasil: {indeks: skor | None}. Mutu prediksi putaran terakhir dihitung bila batch itu dipilih model."""
        for i, s in hasil.items():
            self.skor[int(i)] = None if s is None or not math.isfinite(float(s)) else float(s)
        if self.putaran:
            akhir = self.putaran[-1]
            if akhir.get("prediksi"):
                akhir["mutu"] = mutu_prediksi({int(k): v for k, v in akhir["prediksi"].items()}, self.skor)

    def rencana_berikut(self, pustaka, lapor=None):
        """Latih model pada skor yang ada dan pilih batch berikutnya TANPA mengubah status (aman di thread latar).
        -> {indeks, metode, prediksi, info}; terapkan dengan terima_rencana()."""
        kand = self.kandidat()
        b = min(self.ukuran_batch(), len(kand))
        ke = len(self.putaran)
        cara = self.p["akuisisi"]
        rng = np.random.default_rng(self.p["seed"] + ke)
        if b == 0:
            return {"indeks": [], "metode": "", "prediksi": {}, "info": {"pesan": "Pustaka sudah habis didocking."}}
        if cara == "acak":
            pilih = np.sort(rng.choice(kand, size=b, replace=False))
            return {"indeks": pilih.tolist(), "metode": "acak", "prediksi": {}, "info": {"model": "", "n_latih": 0}}
        idx, y = self.latih_data()
        if len(idx) < 10:
            raise GalatPustaka("Skor docking yang berhasil terlalu sedikit untuk melatih model (perlu ≥ 10). "
                               "Periksa log antrean: banyak ligan gagal disiapkan atau didocking.")
        model = buat_model(self.p["model"], self.p["seed"] + ke).latih(pustaka.X(idx), y)
        mu, sd = prediksi_potongan(model, pustaka, kand, lapor)
        urut = _ambil_terkecil(nilai_akuisisi(mu, sd, cara, self.p["beta"], rng), b)
        pilih = kand[urut]
        info = {"model": model.nama, "n_latih": int(len(idx)), "n_kandidat": int(len(kand)),
                "prediksi_terbaik": float(mu.min()) if len(mu) else None,
                "sb_rata": float(sd.mean()) if len(sd) else None}
        return {"indeks": pilih.tolist(), "metode": f"{self.p['model']}+{cara}",
                "prediksi": {int(i): round(float(m), 3) for i, m in zip(pilih, mu[urut])}, "info": info}

    def terima_rencana(self, r):
        if r["indeks"]:
            self.putaran.append({"ke": len(self.putaran), "indeks": list(r["indeks"]), "metode": r["metode"],
                                 "prediksi": dict(r["prediksi"]), "mutu": {}, "info": r.get("info") or {}})
        return r["indeks"]

    def pilih_berikut(self, pustaka, lapor=None):
        """rencana_berikut + terima_rencana -> (indeks, info)."""
        r = self.rencana_berikut(pustaka, lapor)
        return self.terima_rencana(r), r["info"]

    def lepas(self, indeks):
        """Keluarkan indeks yang batal didocking (job dibatalkan) dari putaran terakhir supaya bisa dipilih lagi."""
        buang = {int(i) for i in indeks}
        if not (self.putaran and buang):
            return
        akhir = self.putaran[-1]
        akhir["indeks"] = [i for i in akhir["indeks"] if i not in buang or i in self.skor]
        akhir["prediksi"] = {k: v for k, v in (akhir.get("prediksi") or {}).items() if k not in buang}
        if not akhir["indeks"]:
            self.putaran.pop()

    def prediksi_kandidat(self, pustaka, k=200, lapor=None):
        """Model dilatih pada semua skor; -> [(indeks, rata, sb)] k kandidat belum didocking dengan prediksi terbaik."""
        idx, y = self.latih_data()
        if len(idx) < 10:
            raise GalatPustaka("Belum cukup skor docking untuk melatih model (perlu ≥ 10).")
        kand = self.kandidat()
        model = buat_model(self.p["model"], self.p["seed"]).latih(pustaka.X(idx), y)
        mu, sd = prediksi_potongan(model, pustaka, kand, lapor)
        urut = _ambil_terkecil(mu, k)
        return [(int(kand[u]), float(mu[u]), float(sd[u])) for u in urut]

    def peringkat(self, k=None):
        """[(indeks, skor)] terbaik yang sudah didocking."""
        ada = sorted(((i, s) for i, s in self.skor.items() if s is not None), key=lambda x: x[1])
        return ada[:k] if k else ada

    def ringkasan_putaran(self, k_top=100):
        """Per putaran: jumlah didocking kumulatif, skor terbaik, rata-rata k terbaik, mutu prediksi."""
        hasil, kum = [], {}
        for p in self.putaran:
            for i in p["indeks"]:
                if i in self.skor:
                    kum[i] = self.skor[i]
            ok = sorted(s for s in kum.values() if s is not None)
            k = min(k_top, len(ok))
            hasil.append({"ke": p["ke"], "metode": p["metode"], "n_batch": len(p["indeks"]), "n_kumulatif": len(kum),
                          "gagal": sum(1 for i in p["indeks"] if i in self.skor and self.skor[i] is None),
                          "terbaik": ok[0] if ok else None, "rata_top": float(np.mean(ok[:k])) if k else None,
                          "k_top": k, "mutu": p.get("mutu") or {}, "selesai": all(i in self.skor for i in p["indeks"])})
        return hasil

    def ke_dict(self):
        return {"n": self.n, "pengaturan": dict(self.p),
                "skor": [[i, s] for i, s in sorted(self.skor.items())],
                "putaran": [dict(p, prediksi={str(k): v for k, v in (p.get("prediksi") or {}).items()})
                            for p in self.putaran]}

    @classmethod
    def dari_dict(cls, d):
        putaran = []
        for p in d.get("putaran") or []:
            putaran.append(dict(p, prediksi={int(k): v for k, v in (p.get("prediksi") or {}).items()}))
        return cls(d["n"], d.get("pengaturan"), {int(i): s for i, s in d.get("skor") or []}, putaran)


# ----------------------------------------------------------------------------------------------- uji retrospektif
def uji_retrospektif(pustaka, skor_benar, pengaturan=None, k_top=None, lapor=None):
    """Simulasikan kampanye memakai skor yang sudah diketahui (pengganti docking). skor_benar: array (nan = gagal).
    -> [{ke, n_dievaluasi, persen_pustaka, temuan_top (fraksi k terbaik yang sudah ditemukan), mutu}]"""
    skor_benar = np.asarray(skor_benar, dtype=np.float64)
    n = len(skor_benar)
    k_top = k_top or max(1, round(0.01 * n))
    urut = np.argsort(np.where(np.isnan(skor_benar), np.inf, skor_benar), kind="stable")
    terbaik = set(urut[:k_top].tolist())
    kp = Kampanye(n, pengaturan)
    idx = kp.batch_awal()
    hasil = []
    while True:
        kp.catat({i: (None if np.isnan(skor_benar[i]) else float(skor_benar[i])) for i in idx})
        ditemukan = len(terbaik.intersection(kp.skor))
        hasil.append({"ke": len(kp.putaran) - 1, "n_dievaluasi": len(kp.skor),
                      "persen_pustaka": 100.0 * len(kp.skor) / n, "temuan_top": ditemukan / k_top,
                      "mutu": kp.putaran[-1].get("mutu") or {}})
        if lapor is not None:
            lapor(hasil[-1])
        if kp.selesai():
            break
        idx, _info = kp.pilih_berikut(pustaka)
        if not idx:
            break
    return hasil


# ----------------------------------------------------------------------------------------------- metode
def _angka(n, en):
    s = f"{n:,}"
    return s if en else s.replace(",", ".")


def _persen_teks(x, en):
    s = f"{x:.1f}"
    return s if en else s.replace(".", ",")


def teks_metode(kp, mesin="AutoDock Vina", ringkasan_pustaka=None, en=False):
    """Paragraf metode (Bahasa Indonesia atau Inggris) untuk naskah."""
    p = kp.p
    rp = ringkasan_pustaka or {}
    a = lambda n: _angka(int(n), en)    # noqa: E731
    n_dock = len(kp.skor)
    n_ok = sum(1 for s in kp.skor.values() if s is not None)
    putaran = max(0, len(kp.putaran) - 1)
    persen = _persen_teks(100.0 * n_dock / max(1, kp.n), en)
    beta = f"{p['beta']:g}" if en else f"{p['beta']:g}".replace(".", ",")
    if en:
        model = {"rf": "a random forest (100 trees; uncertainty from the spread of per-tree predictions)",
                 "mlp": "an ensemble of three feed-forward neural networks (two hidden layers of 100 units; "
                        "uncertainty from the spread of member predictions)"}[p["model"]]
        akuisisi = {"ucb": f"an upper-confidence-bound acquisition (predicted score − {beta} × uncertainty)",
                    "greedy": "a greedy acquisition (best predicted score)", "acak": "random selection"}[p["akuisisi"]]
        return (f"A library of {a(kp.n)} unique compounds (RDKit canonical SMILES, largest fragment; "
                f"{a(rp.get('tidak_valid', 0))} invalid and {a(rp.get('ganda', 0))} duplicate entries removed) was "
                f"screened with pool-based active learning following MolPAL (Graff et al., 2021). Compounds were "
                f"featurized as 2048-bit hashed atom-pair fingerprints (topological distances of 1-3 bonds). An initial random batch of "
                f"{a(kp.ukuran_awal())} compounds was docked with {mesin}; thereafter {model} was retrained on all "
                f"docking scores obtained so far and {akuisisi} selected the next {a(kp.ukuran_batch())} compounds "
                f"in each round ({putaran} rounds). In total {a(n_dock)} compounds ({persen}% of the library) were "
                f"docked, {a(n_ok)} of them successfully. The surrogate's prospective accuracy was checked on every "
                f"batch before it was docked.")
    model = {"rf": "random forest (100 pohon; ketidakpastian dari sebaran prediksi antarpohon)",
             "mlp": "ensemble tiga jaringan saraf umpan maju (dua lapis tersembunyi 100 neuron; ketidakpastian dari "
                    "sebaran prediksi antaranggota)"}[p["model"]]
    akuisisi = {"ucb": f"akuisisi upper confidence bound (prediksi skor − {beta} × ketidakpastian)",
                "greedy": "akuisisi greedy (prediksi skor terbaik)", "acak": "pemilihan acak"}[p["akuisisi"]]
    return (f"Pustaka berisi {a(kp.n)} senyawa unik (SMILES kanonik RDKit, fragmen terbesar; "
            f"{a(rp.get('tidak_valid', 0))} entri tidak valid dan {a(rp.get('ganda', 0))} duplikat dibuang) disaring "
            f"dengan pembelajaran aktif berbasis kumpulan mengikuti MolPAL (Graff dkk., 2021). Senyawa "
            f"direpresentasikan sebagai sidik jari pasangan atom ter-hash 2048 bit (jarak topologi 1-3 ikatan). Batch awal acak berisi "
            f"{a(kp.ukuran_awal())} senyawa didocking dengan {mesin}; setelah itu model {model} dilatih ulang pada "
            f"seluruh skor docking yang sudah diperoleh dan {akuisisi} memilih {a(kp.ukuran_batch())} senyawa "
            f"berikutnya pada setiap putaran ({putaran} putaran). Secara keseluruhan {a(n_dock)} senyawa ({persen}% "
            f"pustaka) didocking, {a(n_ok)} di antaranya berhasil. Akurasi prospektif model diperiksa pada setiap "
            f"batch sebelum didocking.")
