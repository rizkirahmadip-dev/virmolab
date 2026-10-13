#!/usr/bin/env python3
"""Uji penargetan balik. Semua data di sini SINTETIS dan hanya menguji rumus (z-skor, Borda, peringkat Tanimoto,
penolakan entri panel tak sah). Tidak ada klaim biologis; jalur ChEMBL daring diuji terpisah (--daring)."""
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from virmolab.core import target_balik as tb


def cek(k, pesan):
    if not k:
        print(f"GAGAL: {pesan}")
        sys.exit(1)
    print(f"OK: {pesan}")


def uji_zskor():
    class P:
        job = [{"target_balik": {"kelas": "x", "pdb": "AAAA", "gen": "A", "z_rata": -6.0, "z_sd": 1.0},
                "ligan": [{"id": "l", "status": "selesai", "energi": -8.0}]},
               {"target_balik": {"kelas": "x", "pdb": "BBBB", "gen": "B", "z_rata": -6.0, "z_sd": 2.0},
                "ligan": [{"id": "l", "status": "gagal", "energi": None}]}]
    orig = tb.muat_panel
    tb.muat_panel = lambda k: [{"pdb": "AAAA", "gen": "A"}, {"pdb": "BBBB", "gen": "B"}, {"pdb": "CCCC", "gen": "C"}]
    try:
        h = {x["pdb"]: x for x in tb.kumpulkan(P(), "x")}
    finally:
        tb.muat_panel = orig
    cek(h["AAAA"]["z_skor"] == -2.0, "z = (E - rata)/sd = -2,0")
    cek(h["BBBB"]["z_skor"] is None, "target gagal docking: z None (tidak dikarang)")
    cek(h["CCCC"]["z_skor"] is None and h["CCCC"]["z_rata"] is None, "tanpa statistik umpan: z None, tak ada nilai bawaan")


def uji_borda():
    lig = [{"gen": "A", "uniprot": "UA", "skor_max": .9}, {"gen": "B", "uniprot": "UB", "skor_max": .8}, {"gen": "C", "uniprot": "UC", "skor_max": .7}]
    st = [{"gen": "B", "uniprot": "UB", "pdb": "BBBB", "z_skor": -3.0, "energi": -9}, {"gen": "A", "uniprot": "UA", "pdb": "AAAA", "z_skor": -1.0, "energi": -7},
          {"gen": "D", "uniprot": "UD", "pdb": "DDDD", "z_skor": None, "energi": None, "status": "gagal"}]
    g = {x["gen"]: x for x in tb.gabung(lig, st)}
    cek(g["B"]["borda"] == 2 + 1 and g["A"]["borda"] == 1 + 2, "Borda B=2+1, A=1+2")
    cek(g["C"]["borda"] == 3 + 3, "target hanya di satu jalur: peringkat terburuk jalur lain + 1 (=N+1)")
    cek(g["D"]["r_struktur"] is None, "target gagal docking tidak diperingkat")
    cek(g["A"]["keyakinan"] == "tinggi" and g["C"]["keyakinan"] == "sedang", "label keyakinan")


def uji_uniprot_ganda():
    """Dua struktur panel untuk protein yang sama -> satu baris (z terbaik); dua ID ChEMBL satu UniProt -> satu baris."""
    st = [{"gen": "X", "uniprot": "UX", "pdb": "1AAA", "z_skor": -1.0}, {"gen": "X", "uniprot": "UX", "pdb": "2BBB", "z_skor": -4.0}]
    g = tb.gabung([], st)
    cek(len(g) == 1 and g[0]["pdb"] == "2BBB" and g[0]["r_struktur"] == 1, "UniProt sama: satu baris, struktur z terbaik")
    fp = tb._hitung_fp_morgan("CCO")
    r = tb._peringkatkan_target(fp, [({"target": "T1", "uniprot": "U"}, "CCO", "m1", "a"), ({"target": "T2", "uniprot": "U"}, "CCO", "m1", "a")], k=5)
    cek(len(r) == 1 and r[0]["n_ligan"] == 1, "ID target ChEMBL berbeda, UniProt sama, ligan sama: dihitung sekali")


def uji_tanimoto():
    fp = tb._hitung_fp_morgan("CCO")
    r = tb._peringkatkan_target(fp, [({"target": "T1"}, "CCO", "m1", "etanol"), ({"target": "T2"}, "c1ccccc1", "m2", "benzena"),
                                     ({"target": "T1"}, "CCC", "m3", "propana")], k=5)
    cek(r[0]["target"] == "T1" and r[0]["skor_max"] == 1.0, "etanol identik -> skor_max 1,0 pada T1")
    from rdkit import DataStructs
    sim_ccc = DataStructs.TanimotoSimilarity(fp, tb._hitung_fp_morgan("CCC"))
    cek(r[0]["skor_knn"] == round((1.0 + sim_ccc) / 5, 4), "skor_knn = jumlah kemiripan / k (bukan / jumlah ligan)")
    cek(r[0]["n_ligan"] == 2 and r[1]["skor_max"] < 0.3, "benzena tak mirip etanol")


def uji_panel_tak_sah():
    t = {"pdb": "XXXX", "gen": "X", "pusat": [0, 0, 0], "ukuran": [20, 20, 20], "rmsd_redocking": 3.1, "z_rata": -6, "z_sd": 1}
    cek("RMSD" in tb.alasan_tidak_sah(t, "x"), "RMSD > 2 Å ditolak")
    t["rmsd_redocking"] = 1.0
    cek("reseptor" in tb.alasan_tidak_sah(t, "x"), "tanpa berkas reseptor ditolak")
    t.pop("z_sd")
    cek("z_sd" in tb.alasan_tidak_sah(t, "x"), "tanpa z_sd ditolak (tak ada nilai bawaan)")
    cek(tb.susun_paragraf_metode("x", {}) == "", "tak ada jalur dijalankan -> paragraf kosong")


def uji_panel_nyata():
    """Panel yang dikirim: reseptor nyata (ukuran, atom protein), statistik dari hasil docking, jejak redocking di log."""
    import json
    kelas = tb.daftar_kelas_panel()
    cek(len(kelas) > 0, f"panel tersedia: {kelas}")
    for k in kelas:
        panel = tb.muat_panel(k)
        cek(len(panel) >= 5, f"{k}: {len(panel)} target (>= 5)")
        log = {}
        berkas_log = AKAR / "dev" / "panel_kandidat" / f"log_{k}.jsonl"
        if berkas_log.exists():
            for b in berkas_log.read_text(encoding="utf-8").splitlines():
                d = json.loads(b)
                if d.get("langkah") == "redocking":
                    log[d["pdb"]] = d
        for t in panel:
            f = tb.DIR_DATA_PANEL / k / f"{t['pdb']}.pdbqt"
            teks = f.read_text(encoding="utf-8")
            n_atom = sum(1 for b in teks.splitlines() if b.startswith(("ATOM", "HETATM")))
            cek(f.stat().st_size > 50_000 and n_atom > 1000, f"{t['pdb']}: reseptor {f.stat().st_size // 1024} KB, {n_atom} atom")
            cek(tb.alasan_tidak_sah(t, k) == "", f"{t['pdb']}: entri sah")
            cek(t["n_umpan"] >= 30 and t["z_sd"] > 0 and t["resolusi"] <= 2.5, f"{t['pdb']}: n_umpan {t['n_umpan']}, z_sd {t['z_sd']}, res {t['resolusi']}")
            if log:
                cek(t["pdb"] in log and abs(log[t["pdb"]]["rmsd"] - t["rmsd_redocking"]) <= 0.006,
                    f"{t['pdb']}: RMSD redocking cocok dengan baris log ({t['rmsd_redocking']})")


def uji_daring():
    h, j = tb.jalur_ligan("CC(C)Cc1ccc(cc1)C(C)C(=O)O")
    print([(x["gen"], x["skor_max"], x["skor_knn"], x["n_ligan"]) for x in h[:8]])
    cek(len(h) > 0 and len(j) > 0, "ChEMBL daring mengembalikan target + jejak")


if __name__ == "__main__":
    for f in (uji_zskor, uji_borda, uji_uniprot_ganda, uji_tanimoto, uji_panel_tak_sah):
        f()
    if "--panel" in sys.argv:
        uji_panel_nyata()
    if "--daring" in sys.argv:
        uji_daring()
    print("SEMUA UJI LULUS")
