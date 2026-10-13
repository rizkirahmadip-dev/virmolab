#!/usr/bin/env python3
"""Uji pengayaan jalur dan jaringan farmakologi (F3b).

Data sintetis dengan jawaban yang dihitung tangan; `--daring` menguji STRING, Open Targets, dan GMT paket.
"""
import math
import sys
import tempfile
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

import networkx as nx  # noqa: E402

from virmolab.core import graf, jaringan as J, pengayaan as E  # noqa: E402


def cek(k, pesan):
    if not k:
        print(f"GAGAL: {pesan}")
        sys.exit(1)
    print(f"OK: {pesan}")


def uji_hipergeometrik():
    """p dihitung tangan: latar 20 gen, set 5 gen, kueri 4 gen, overlap 3 -> P(X>=3) = (C(5,3)C(15,1)+C(5,4)C(15,0))/C(20,4)."""
    latar = [f"G{i}" for i in range(1, 21)]
    set_gen = {"SET1": {"nama": "set uji", "gen": {"G1", "G2", "G3", "G4", "G5"}},
               "SET2": {"nama": "set lain", "gen": {"G10", "G11", "G12", "G13", "G14"}}}
    h = {b["jalur"]: b for b in E.hipergeometrik(["G1", "G2", "G3", "G9"], set_gen, latar)}
    manual = (math.comb(5, 3) * math.comb(15, 1) + math.comb(5, 4) * math.comb(15, 0)) / math.comb(20, 4)
    cek(abs(h["SET1"]["p"] - manual) < 1e-12, f"p hipergeometrik = hitungan manual ({manual:.6f})")
    cek(h["SET1"]["n_overlap"] == 3 and h["SET1"]["n_latar"] == 20, "overlap dan latar dilaporkan apa adanya")
    cek("SET2" not in h, "set tanpa overlap tidak diuji")
    kueri_luar = E.hipergeometrik(["G1", "ZZZ"], set_gen, latar)
    cek(kueri_luar[0]["n_kueri"] == 1, "gen di luar latar dibuang dari kueri")


def uji_bh():
    """BH step-up: q_i = min_{j>=i} (p_j * n / j) dengan p terurut naik."""
    p = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216]
    q = E.benjamini_hochberg(p)
    manual = []
    kecil = 1.0
    for i in range(len(p), 0, -1):
        kecil = min(kecil, p[i - 1] * len(p) / i)
        manual.append(kecil)
    manual.reverse()
    cek(all(abs(a - b) < 1e-12 for a, b in zip(q, manual)), f"q BH = hitungan manual (q1={q[0]:.4f}, q10={q[-1]:.4f})")
    cek(E.benjamini_hochberg([]) == [], "BH pada daftar kosong")
    # p=[0,04; 0,01; 0,03] -> peringkat 3,1,2; step-up: q3=0,04*3/3=0,04; q2=min(0,04; 0,03*3/2)=0,04; q1=min(0,04; 0,01*3/1)=0,03
    acak = E.benjamini_hochberg([0.04, 0.01, 0.03])
    cek([round(x, 4) for x in acak] == [0.04, 0.03, 0.04], f"urutan keluaran BH sama dengan masukan, didapat {acak}")


def uji_graf_berlapis():
    senyawa = {"kurkumin": ["PTGS2", "MAPK14", "JAK2"]}
    jalur = [{"jalur": "R-1", "nama": "radang", "q": 0.001, "n_overlap": 2, "gen": ["PTGS2", "MAPK14"]}]
    G = J.bangun(senyawa, jalur, [("PTGS2", "MAPK14", 0.9), ("PTGS2", "ZZZ", 0.9)],
                 [("PTGS2", "MONDO_1", "artritis", 0.7), ("ZZZ", "MONDO_2", "lain", 0.9)])
    jenis = {n: d["jenis"] for n, d in G.nodes(data=True)}
    cek(sorted(jenis.values()).count("target") == 3 and "J:R-1" in G and "P:MONDO_1" in G, "4 lapisan terbentuk")
    cek(not G.has_edge("T:PTGS2", "T:ZZZ") and "P:MONDO_2" not in G, "tepi ke gen di luar jaringan dibuang")
    cek(G["T:PTGS2"]["T:MAPK14"]["skor"] == 0.9, "skor STRING tersimpan di tepi")
    m = {b["simpul"]: b for b in J.metrik(G)}
    cek(m["T:PTGS2"]["derajat"] == 4, f"derajat PTGS2 = 4 (senyawa, PPI, jalur, penyakit); didapat {m['T:PTGS2']['derajat']}")
    cek(J.metrik(nx.Graph()) == [], "metrik graf kosong")


def uji_sensitivitas():
    """A terhubung ke semua pada tiap ambang -> inti stabil; D hanya muncul pada satu kombinasi."""
    senyawa = {"s": ["A", "B", "C", "D"]}
    tepi = {0.4: [("A", "B", .5), ("A", "C", .5), ("A", "D", .5), ("C", "D", .45)],
            0.7: [("A", "B", .8), ("A", "C", .8)],
            0.9: [("A", "B", .95)]}
    s = J.sensitivitas(senyawa, tepi, ambang_target=(2, 4), bagian_inti=0.25)
    cek(s["kombinasi"] == 6, f"6 kombinasi dievaluasi, didapat {s['kombinasi']}")
    cek(s["inti_stabil"] == ["A"], f"inti stabil hanya A, didapat {s['inti_stabil']}")
    persen = {d["gen"]: d["persen"] for d in s["simpul"]}
    cek(persen["A"] == 100.0, "A muncul di 100 % kombinasi")


def uji_graphml_pulang_pergi():
    G = J.bangun({"kurkumin": ["PTGS2", "MAPK14"]},
                 [{"jalur": "R-1", "nama": "radang", "q": 0.002, "n_overlap": 2, "gen": ["PTGS2", "MAPK14"]}],
                 [("PTGS2", "MAPK14", 0.9)], [("PTGS2", "MONDO_1", "artritis", 0.7)])
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "uji.graphml"
        graf.ekspor_graphml(G, p)
        H = nx.read_graphml(p)
        cek(set(H.nodes()) == set(G.nodes()) and H.number_of_edges() == G.number_of_edges(), "GraphML pulang-pergi: simpul dan tepi sama")
        cek(H.nodes["J:R-1"]["label"] == "radang" and abs(float(H.nodes["J:R-1"]["q"]) - 0.002) < 1e-9, "atribut simpul bertahan")
        cek(abs(float(H["T:PTGS2"]["T:MAPK14"]["skor"]) - 0.9) < 1e-9, "atribut tepi bertahan")
        pcsv = Path(d) / "tepi.csv"
        graf.ekspor_csv_tepi(G, pcsv)
        cek(len(pcsv.read_text(encoding="utf-8").strip().splitlines()) == G.number_of_edges() + 1, "CSV tepi lengkap")


def uji_paragraf():
    cek(J.susun_paragraf_metode("penargetan balik", 0, "reactome", [], 0.7, 0, None, 0) == "", "tanpa target: paragraf kosong")
    teks = J.susun_paragraf_metode("penargetan balik", 3, "reactome", [], 0.7, 0, None, 0)
    cek("hipotesis" in teks and "STRING" not in teks and "Open Targets" not in teks,
        "paragraf tidak menyebut sumber yang tidak dipakai")
    lengkap = J.susun_paragraf_metode(
        "penargetan balik", 3, "reactome",
        [{"q": 0.001, "n_latar": 11682}, {"q": 0.2, "n_latar": 11682}], 0.7, 5, 0.5, 4,
        {"kombinasi": 6, "inti_stabil": ["PTGS2"]}, versi_ot="data 2026.09", versi_string="v12.5")
    for frasa in ("11682", "v12.5", "2026.09", "1 jalur memenuhi q < 0,05", "6 kombinasi", ">= 0,7", ">= 0,5"):
        cek(frasa in lengkap, f"paragraf memuat {frasa}")


def uji_daring():
    gen = ["PTGS2", "PTGS1", "MAPK14", "JAK2"]
    tepi, jk = J.tepi_string(gen, 0.4)
    cek(any({a, b} == {"PTGS1", "PTGS2"} for a, b, _ in tepi), f"STRING: PTGS1-PTGS2 terhubung ({len(tepi)} tepi)")
    cek(all(s >= 0.4 for _, _, s in tepi) and jk[0]["lisensi"] == "CC BY 4.0", "skor >= ambang dan jejak lisensi tercatat")
    cek(J.tepi_string(gen, 0.99)[0] == [] or len(J.tepi_string(gen, 0.99)[0]) < len(tepi), "ambang lebih ketat mengurangi tepi")
    v, _ = J.versi_string()
    vo, _ = J.versi_opentargets()
    print("  STRING", v, "| Open Targets", vo)
    pen, _ = J.tepi_penyakit(["PTGS2"], 0.5, 5)
    cek(pen and all(s >= 0.5 for *_, s in pen), f"Open Targets: {len(pen)} penyakit skor >= 0,5")
    gmt = E.gmt_bawaan("reactome")
    cek(len(gmt) > 1000, f"GMT Reactome paket: {len(gmt)} set")
    h = E.hipergeometrik(["PTGS1", "PTGS2", "MAPK14", "JAK2", "BTK", "PDE4D", "DHODH", "NR3C1"], gmt, min_overlap=2)
    print("  5 jalur teratas:", [(b["nama"][:40], round(b["q"], 4)) for b in h[:5]])
    cek(h and h[0]["q"] < 0.05, "ada jalur q < 0,05 untuk panel antiinflamasi")


if __name__ == "__main__":
    for f in (uji_hipergeometrik, uji_bh, uji_graf_berlapis, uji_sensitivitas, uji_graphml_pulang_pergi, uji_paragraf):
        f()
    if "--daring" in sys.argv:
        uji_daring()
    print("SEMUA UJI LULUS")
