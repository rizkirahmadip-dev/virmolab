"""Prediksi ADMET dengan ADMET-AI (Swanson et al. 2024, Bioinformatics 40:btae416; MIT) — model Chemprop-RDKit
yang dilatih pada 41 dataset TDC.

Dijalankan di PROSES TERPISAH (`VirmoDock.exe --admet MASUK.json KELUAR.json` / `python -m virmodock --admet …`):
PyTorch memegang GIL lama saat impor/inferensi sehingga GUI akan tersendat bila dijalankan di thread.
Persentil pembanding DrugBank (data CC BY-NC) sengaja TIDAK dipakai/dibundel (drugbank_path=None).
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SITASI = ("Swanson K, Walther P, Leitz J, et al. ADMET-AI: a machine learning ADMET platform for evaluation of "
          "large-scale chemical libraries. Bioinformatics. 2024;40(7):btae416. doi:10.1093/bioinformatics/btae416")

# (kolom ADMET-AI, label Indonesia, kelompok, jenis: 'p' = probabilitas 0–1 | satuan teks, arah baik: +1/-1/0)
SIFAT = [
    ("HIA_Hou", "Absorpsi usus manusia (HIA)", "Absorpsi", "p", +1),
    ("Bioavailability_Ma", "Bioavailabilitas oral ≥ 20 %", "Absorpsi", "p", +1),
    ("Caco2_Wang", "Permeabilitas Caco-2 (log cm/s)", "Absorpsi", "log cm/s", +1),
    ("PAMPA_NCATS", "Permeabilitas PAMPA", "Absorpsi", "p", +1),
    ("Pgp_Broccatelli", "Penghambat P-gp", "Absorpsi", "p", 0),
    ("Solubility_AqSolDB", "Kelarutan air (log mol/L)", "Absorpsi", "log mol/L", +1),
    ("Lipophilicity_AstraZeneca", "Lipofilisitas (log D7.4)", "Absorpsi", "logD", 0),
    ("BBB_Martins", "Menembus sawar darah otak (BBB)", "Distribusi", "p", 0),
    ("PPBR_AZ", "Ikatan protein plasma (%)", "Distribusi", "%", 0),
    ("VDss_Lombardo", "Volume distribusi (L/kg)", "Distribusi", "L/kg", 0),
    ("CYP1A2_Veith", "Penghambat CYP1A2", "Metabolisme", "p", -1),
    ("CYP2C19_Veith", "Penghambat CYP2C19", "Metabolisme", "p", -1),
    ("CYP2C9_Veith", "Penghambat CYP2C9", "Metabolisme", "p", -1),
    ("CYP2D6_Veith", "Penghambat CYP2D6", "Metabolisme", "p", -1),
    ("CYP3A4_Veith", "Penghambat CYP3A4", "Metabolisme", "p", -1),
    ("CYP2C9_Substrate_CarbonMangels", "Substrat CYP2C9", "Metabolisme", "p", 0),
    ("CYP2D6_Substrate_CarbonMangels", "Substrat CYP2D6", "Metabolisme", "p", 0),
    ("CYP3A4_Substrate_CarbonMangels", "Substrat CYP3A4", "Metabolisme", "p", 0),
    ("Half_Life_Obach", "Waktu paruh (jam)", "Ekskresi", "jam", 0),
    ("Clearance_Hepatocyte_AZ", "Klirens hepatosit (µL/min/10⁶ sel)", "Ekskresi", "µL/min/10⁶", 0),
    ("Clearance_Microsome_AZ", "Klirens mikrosom (mL/min/g)", "Ekskresi", "mL/min/g", 0),
    ("AMES", "Mutagenik (uji Ames)", "Toksisitas", "p", -1),
    ("hERG", "Penghambat hERG (kardiotoksik)", "Toksisitas", "p", -1),
    ("DILI", "Cedera hati (DILI)", "Toksisitas", "p", -1),
    ("ClinTox", "Toksisitas uji klinis", "Toksisitas", "p", -1),
    ("Carcinogens_Lagunin", "Karsinogenik", "Toksisitas", "p", -1),
    ("Skin_Reaction", "Reaksi kulit", "Toksisitas", "p", -1),
    ("LD50_Zhu", "Toksisitas akut LD50 (−log mol/kg)", "Toksisitas", "−log mol/kg", -1),
    ("NR-AhR", "Reseptor AhR (Tox21)", "Toksisitas", "p", -1),
    ("SR-p53", "Respons stres p53 (Tox21)", "Toksisitas", "p", -1),
]
LABEL = {k: l for k, l, *_ in SIFAT}
KELOMPOK = ["Absorpsi", "Distribusi", "Metabolisme", "Ekskresi", "Toksisitas"]
VERSI = 1


# ------------------------------------------------------------------ sisi pekerja
def _prediksi_lokal(smiles):
    import logging
    import warnings
    warnings.filterwarnings("ignore")
    for n in ("lightning", "lightning.pytorch", "pytorch_lightning", "lightning_fabric"):
        logging.getLogger(n).setLevel(logging.ERROR)
    os.environ.setdefault("TQDM_DISABLE", "1")
    from admet_ai import ADMETModel
    model = ADMETModel(drugbank_path=None, num_workers=0)
    df = model.predict(smiles=list(smiles))
    out = []
    for i in range(len(df)):
        r = df.iloc[i]
        out.append({k: (None if r.get(k) is None or r.get(k) != r.get(k) else round(float(r[k]), 4))
                    for k, *_ in SIFAT})
    return out


def jalankan_cli(masuk, keluar):
    """Entri proses: masuk.json = {"smiles": [...]} -> keluar.json = {"hasil": [...]} atau {"galat": "..."}."""
    import contextlib
    import io
    d = json.loads(Path(masuk).read_text(encoding="utf-8"))
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            hasil = _prediksi_lokal(d["smiles"])
        Path(keluar).write_text(json.dumps({"hasil": hasil, "v": VERSI}), encoding="utf-8")
        return 0
    except Exception as e:
        Path(keluar).write_text(json.dumps({"galat": f"{type(e).__name__}: {e}", "log": buf.getvalue()[-2000:]}),
                                encoding="utf-8")
        return 1


# ------------------------------------------------------------------ sisi aplikasi
def _perintah(masuk, keluar):
    if getattr(sys, "frozen", False):
        from . import paths
        return [str(paths.EXE_UTAMA), "--admet", str(masuk), str(keluar)]
    return [sys.executable, "-m", "virmodock", "--admet", str(masuk), str(keluar)]


def tersedia():
    import importlib.util
    return importlib.util.find_spec("admet_ai") is not None


def prediksi(smiles, lapor=None, batas_waktu=900):
    """Jalankan ADMET-AI di proses terpisah (panggil dari thread latar). Kembalikan list dict per SMILES."""
    if not smiles:
        return []
    log = (lambda s: lapor.log.emit(s)) if lapor else (lambda s: None)
    with tempfile.TemporaryDirectory(prefix="vd_admet_") as d:
        masuk, keluar = Path(d) / "masuk.json", Path(d) / "keluar.json"
        masuk.write_text(json.dumps({"smiles": list(smiles)}), encoding="utf-8")
        log(f"ADMET-AI: memprediksi {len(smiles)} senyawa (memuat model ±10–20 s)…")
        flag = 0x08000000 if os.name == "nt" else 0       # CREATE_NO_WINDOW
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        if not getattr(sys, "frozen", False):      # mode pengembangan: paket virmodock dari akar proyek
            from . import paths
            env["PYTHONPATH"] = os.pathsep.join(x for x in (str(paths.AKAR), env.get("PYTHONPATH", "")) if x)
        p = subprocess.run(_perintah(masuk, keluar), capture_output=True, timeout=batas_waktu, creationflags=flag,
                           env=env, cwd=d)
        if not keluar.exists():
            raise RuntimeError("Proses ADMET-AI berhenti tanpa hasil: "
                               + (p.stderr.decode("utf-8", "replace")[-600:] or f"kode {p.returncode}"))
        r = json.loads(keluar.read_text(encoding="utf-8"))
    if "galat" in r:
        raise RuntimeError(r["galat"])
    return r["hasil"]


def teks_nilai(k, v):
    if v is None:
        return "–"
    jenis = next(j for kk, _l, _g, j, _a in SIFAT if kk == k)
    if jenis == "p":
        return f"{v:.2f}".replace(".", ",")
    return (f"{v:.2f}" if abs(v) < 100 else f"{v:.0f}").replace(".", ",").replace("-", "−")


def warna(k, v):
    """Warna sel: probabilitas buruk tinggi -> merah, baik tinggi -> hijau; netral/regresi -> None."""
    if v is None:
        return None
    _kk, _l, _g, jenis, arah = next(x for x in SIFAT if x[0] == k)
    if jenis != "p" or arah == 0:
        return None
    baik = v if arah > 0 else 1 - v
    if baik >= 0.7:
        return "#2e9e5b"
    if baik <= 0.3:
        return "#cf3f3f"
    return "#c98a12"
