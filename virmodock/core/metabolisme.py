"""Prediksi Titik Metabolisme Ligan (Site of Metabolism / SoM Finder).

Mengidentifikasi atom-atom pada molekul ligan yang paling rentan mengalami
metabolisme fase I oleh enzim Sitokrom P450 (CYP3A4, CYP2D6, CYP2C9),
serta memberikan saran strategi modifikasi bioisosterik pelindung metabolisme.
"""
from typing import Any, Dict, List, Tuple
from rdkit import Chem

# Definisi pola SMARTS reaksi metabolisme CYP450 umum
POLA_METABOLISME = [
    {
        "nama": "N-Dealkilasi (N-Metil / N-Alkil)",
        "smarts": "[NX3;H0,H1][CH3,CH2]",
        "indeks_target": 1,  # atom C yang terdealkilasi
        "kerentanan": "Sangat Labil (High)",
        "bobot": 1.0,
        "saran": "Ganti N-metil dengan cincin heterosiklik kaku (morfolin/azetidin) atau deuterasi (N-CD3)."
    },
    {
        "nama": "O-Demetilasi (Metoksi / Eter)",
        "smarts": "[OX2][CH3]",
        "indeks_target": 1,
        "kerentanan": "Labil (High)",
        "bobot": 0.9,
        "saran": "Ganti metoksi (-OCH3) dengan difluorometoksi (-OCHF2) atau trifluorometoksi (-OCF3)."
    },
    {
        "nama": "Hidroksilasi Benzilik (C-H Benzylic)",
        "smarts": "[c][CH2,CH1][C,c,O,N]",
        "indeks_target": 1,
        "kerentanan": "Labil (High)",
        "bobot": 0.85,
        "saran": "Substitusi hidrogen benzilik dengan atom Fluorin (-F) atau gem-dimetilasi."
    },
    {
        "nama": "Hidroksilasi Alifatik Terminal (Metil C-H3)",
        "smarts": "[CX4;H3][CX4]",
        "indeks_target": 0,
        "kerentanan": "Sedang (Moderate)",
        "bobot": 0.7,
        "saran": "Ganti gugus metil dengan trifluorometil (-CF3), fluoro (-F), atau gugus siano (-CN)."
    },
    {
        "nama": "Hidroksilasi Aromatik (Cincin Benzen Tak Terhambat)",
        "smarts": "[c;H1]:[c;H1]",
        "indeks_target": 0,
        "kerentanan": "Sedang (Moderate)",
        "bobot": 0.65,
        "saran": "Pasang gugus penarik elektron seperti Fluorin (-F) atau Kloro (-Cl) pada posisi para."
    },
    {
        "nama": "S-Oksidasi (Thioeter / Sulfida)",
        "smarts": "[#16X2][C,c]",
        "indeks_target": 0,
        "kerentanan": "Labil (High)",
        "bobot": 0.8,
        "saran": "Gantikan thioeter dengan sulfon (-SO2-), sulfonamida, atau eter (-O-)."
    },
]


def prediksi_titik_metabolisme(smiles: str) -> Dict[str, Any]:
    """Analisis kerentanan metabolisme pada struktur ligan."""
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        raise ValueError(f"SMILES tidak valid: {smiles}")

    mol = Chem.AddHs(mol)
    daftar_som = []
    atom_tercatat = set()

    for p in POLA_METABOLISME:
        patt = Chem.MolFromSmarts(p["smarts"])
        if not patt:
            continue
        cocok = mol.GetSubstructMatches(patt)
        for c in cocok:
            idx_atom = c[p["indeks_target"]]
            if idx_atom in atom_tercatat:
                continue
            atom = mol.GetAtomWithIdx(idx_atom)
            simbol = atom.GetSymbol()
            if simbol == "H":
                continue

            atom_tercatat.add(idx_atom)
            daftar_som.append({
                "indeks_atom": idx_atom,
                "simbol": simbol,
                "tipe_reaksi": p["nama"],
                "tingkat_kerentanan": p["kerentanan"],
                "bobot": p["bobot"],
                "rekomendasi_bioisosterik": p["saran"],
            })

    # Urutkan berdasarkan bobot kerentanan tertinggi
    daftar_som.sort(key=lambda x: x["bobot"], reverse=True)

    # Hitung Indeks Stabilitas Metabolik (0 - 100)
    # Semakin banyak titik labil, stabilitas semakin rendah
    penalti = sum(s["bobot"] for s in daftar_som) * 18.0
    stabilitas = max(10.0, min(100.0, 100.0 - penalti))

    if stabilitas >= 75.0:
        klasifikasi = "Metabolically Robust (Stabilitas Metabolik Tinggi)"
        ringkasan = "Ligan memiliki sedikit titik labil CYP450. Klirens intrinsik hepatik diprediksi rendah."
    elif stabilitas >= 45.0:
        klasifikasi = "Moderate Clearance (Klirens Sedang)"
        ringkasan = "Terdapat beberapa gugus alifatik/metoksi yang rentan teroksidasi. Pertimbangkan fluorinasi."
    else:
        klasifikasi = "Rapid Clearance / Soft Drug (Metabolisme Sangat Cepat)"
        ringkasan = "Banyak titik lunak metabolik terbuka. Ligan berisiko memiliki waktu paruh eliminasi singkat."

    return {
        "smiles": Chem.MolToSmiles(Chem.RemoveHs(mol)),
        "jumlah_som": len(daftar_som),
        "daftar_som": daftar_som,
        "skor_stabilitas": round(stabilitas, 1),
        "klasifikasi": klasifikasi,
        "ringkasan": ringkasan,
    }
