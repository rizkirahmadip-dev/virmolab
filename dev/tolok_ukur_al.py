"""Uji retrospektif skrining bertahap (core/pembelajaran_aktif.py) dengan data MolPAL.

Skor docking AutoDock Vina pustaka Enamine 10k / 50k terhadap thymidylate kinase (4UNN) dari repositori MolPAL
(Graff dkk., Chem. Sci. 2021) dipakai sebagai pengganti docking: tiap putaran "didocking" = skornya dibuka.
Ukurannya: fraksi 1 % senyawa terbaik (top-100 untuk 10k, top-500 untuk 50k) yang sudah ditemukan sesudah
batch awal acak 1 % + 5 putaran × 1 % (total 6 % pustaka), sama dengan rancangan uji di makalah MolPAL.

  python dev/tolok_ukur_al.py --set 10k --ulang 5
  python dev/tolok_ukur_al.py --set 50k --ulang 3 --strategi rf+ucb rf+greedy acak
"""
import argparse
import csv
import gzip
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from virmolab.core import pembelajaran_aktif as PA   # noqa: E402

DATA = Path("C:/VirmoLab-tolok-ukur/unduhan")
HASIL = Path("C:/VirmoLab-tolok-ukur/hasil")
BERKAS = {"10k": "Enamine10k_scores.csv.gz", "50k": "Enamine50k_scores.csv.gz"}


def muat(nama):
    with gzip.open(DATA / BERKAS[nama], "rt", encoding="utf-8") as f:
        baris = list(csv.DictReader(f))
    entri = [(b["smiles"], f"E{i:06d}") for i, b in enumerate(baris)]
    t = time.time()
    pus = PA.siapkan_pustaka(entri)
    print(f"{nama}: {len(baris)} baris, {len(pus)} unik, sidik jari {time.time() - t:.1f} s; {pus.ringkasan}")
    skor_smi = {}
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    from rdkit.Chem.MolStandardize import rdMolStandardize
    pilih = rdMolStandardize.LargestFragmentChooser(preferOrganic=True)
    for b in baris:
        m = Chem.MolFromSmiles(b["smiles"])
        if m is None:
            continue
        if len(Chem.GetMolFrags(m)) > 1:
            m = pilih.choose(m)
        k = Chem.MolToSmiles(m)
        s = float(b["score"]) if b["score"] not in ("", None) else np.nan
        skor_smi[k] = np.nanmin([skor_smi.get(k, np.nan), s]) if k in skor_smi else s
    skor = np.array([skor_smi.get(s, np.nan) for s in pus.smiles])
    return pus, skor


def jalankan(pus, skor, strategi, ulang, putaran, persen):
    hasil = {}
    for st in strategi:
        model, _, akuisisi = st.partition("+")
        if model == "acak":
            model, akuisisi = "rf", "acak"
        kurva = []
        for r in range(ulang):
            t = time.time()
            h = PA.uji_retrospektif(pus, skor, {"model": model, "akuisisi": akuisisi, "seed": 1000 + r,
                                                "putaran": putaran, "persen": persen})
            kurva.append(h)
            mutu = [x["mutu"].get("rho") for x in h if x["mutu"]]
            print(f"  {st:12s} ulang {r + 1}: top-1% ditemukan {100 * h[-1]['temuan_top']:5.1f}% "
                  f"({h[-1]['n_dievaluasi']} didocking, {h[-1]['persen_pustaka']:.1f}%), "
                  f"rho prospektif {np.nanmean(mutu) if mutu else float('nan'):.2f}, {time.time() - t:.0f} s", flush=True)
        akhir = np.array([100 * k[-1]["temuan_top"] for k in kurva])
        per_putaran = np.array([[100 * x["temuan_top"] for x in k] for k in kurva])
        hasil[st] = {"akhir_rata": float(akhir.mean()), "akhir_sb": float(akhir.std(ddof=1)) if len(akhir) > 1 else 0.0,
                     "per_putaran_rata": per_putaran.mean(0).round(2).tolist(),
                     "persen_pustaka": [round(x["persen_pustaka"], 2) for x in kurva[0]],
                     "rho_prospektif": [round(float(np.nanmean([k[i]["mutu"].get("rho", np.nan) for k in kurva])), 3)
                                        if kurva[0][i]["mutu"] else None for i in range(len(kurva[0]))],
                     "ulang": akhir.round(2).tolist()}
        print(f"{st:12s}: {hasil[st]['akhir_rata']:.1f} ± {hasil[st]['akhir_sb']:.1f} %  per putaran "
              f"{hasil[st]['per_putaran_rata']}", flush=True)
    return hasil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="10k", choices=sorted(BERKAS))
    ap.add_argument("--ulang", type=int, default=5)
    ap.add_argument("--putaran", type=int, default=5)
    ap.add_argument("--persen", type=float, default=1.0)
    ap.add_argument("--strategi", nargs="+", default=["acak", "rf+greedy", "rf+ucb", "mlp+greedy", "mlp+ucb"])
    a = ap.parse_args()
    pus, skor = muat(a.set)
    hasil = jalankan(pus, skor, a.strategi, a.ulang, a.putaran, a.persen)
    HASIL.mkdir(parents=True, exist_ok=True)
    keluar = HASIL / f"al_{a.set}.json"
    lama = json.loads(keluar.read_text(encoding="utf-8")) if keluar.exists() else {}
    lama.update({"set": a.set, "n": len(pus), "k_top": max(1, round(0.01 * len(pus))), "putaran": a.putaran,
                 "persen": a.persen, "tanggal": time.strftime("%Y-%m-%d %H:%M")})
    lama.setdefault("strategi", {}).update(hasil)
    keluar.write_text(json.dumps(lama, indent=1, ensure_ascii=False), encoding="utf-8")
    print("tersimpan", keluar)


if __name__ == "__main__":
    main()
