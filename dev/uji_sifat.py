"""Uji core/sifat.py: deskriptor obat dikenal vs nilai rujukan (SwissADME, kira-kira) + BOILED-Egg.

PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_sifat.py
"""
from pathlib import Path

from virmodock.core import sifat

OBAT = {  # SMILES, harapan GI, harapan BBB
    "Aspirin": ("CC(=O)Oc1ccccc1C(=O)O", True, True),
    "Kafein": ("Cn1cnc2c1c(=O)n(C)c(=O)n2C", True, False),
    "Diazepam": ("CN1C(=O)CN=C(c2ccccc2)c2cc(Cl)ccc21", True, True),
    "Indinavir": ("CC(C)(C)NC(=O)[C@@H]1CN(Cc2cccnc2)CCN1C[C@@H](O)C[C@@H](Cc1ccccc1)C(=O)N[C@@H]1c2ccccc2C[C@@H]1O",
                  True, False),
    "Siklosporin (besar)": ("CC[C@H]1C(=O)N(CC(=O)N([C@H](C(=O)N[C@H](C(=O)N([C@H](C(=O)N[C@H](C(=O)N[C@@H](C(=O)N([C@H](C(=O)N([C@H](C(=O)N([C@H](C(=O)N([C@H](C(=O)N1)[C@@H]([C@H](C)C/C=C/C)O)C)C(C)C)C)CC(C)C)C)CC(C)C)C)C)C)CC(C)C)C)C(C)C)CC(C)C)C)C",
                            False, False),
    "Kurkumin (Brenk)": ("COc1cc(/C=C/C(=O)CC(=O)/C=C/c2ccc(O)c(OC)c2)ccc1O", True, False),
}

titik = []
gagal = 0
for nama, (smi, gi, bbb) in OBAT.items():
    s = sifat.dari_teks(smi, "smiles")
    ok = s["gi"] == gi and s["bbb"] == bbb
    gagal += not ok
    print(f"{'OK ' if ok else 'BEDA'} {nama:22s} MW {s['mw']:7.2f} WLOGP {s['wlogp']:5.2f} TPSA {s['tpsa']:6.2f} "
          f"QED {s['qed']} Lip {sifat.sel(s, 'lipinski')} GI {s['gi']} BBB {s['bbb']} PAINS {s['pains']} "
          f"Brenk {len(s['brenk'])}")
    titik.append((nama, s["tpsa"], s["wlogp"]))
# tepi elips (titik dari poligon PyBOILEDegg) harus ~ batas
for p, el in (((97.80552, -2.22704), sifat.ELIPS_HIA), ((40.97018, 0.40626), sifat.ELIPS_BBB)):
    print("tepi elips (harus dekat batas):", sifat.di_elips(p[0] * 0.99 + el[0] * 0.01, p[1] * 0.99 + el[1] * 0.01, el),
          sifat.di_elips(p[0] * 1.01 - el[0] * 0.01, p[1] * 1.01 - el[1] * 0.01, el))
out = Path("dev/uji/sifat")
out.mkdir(parents=True, exist_ok=True)
(out / "egg.svg").write_text(sifat.boiled_egg_svg(titik, judul="BOILED-Egg uji", pilih=2), encoding="utf-8")
(out / "egg_gelap.svg").write_text(sifat.boiled_egg_svg(titik, gelap=True), encoding="utf-8")
print("gagal:", gagal)
