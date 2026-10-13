"""Perhitungan Synthetic Accessibility Score (SAScore).

Berdasarkan metode Ertl & Schuffenhauer (2009):
"Estimation of Synthetic Accessibility Score of Drug-like Molecules based on
Molecular Complexity and Fragment Contributions", J. Cheminform. 1:8.

Skor berkisar antara 1 (sangat mudah disintesis) sampai 10 (sangat sulit / mustahil).
Menggunakan RDKit Contrib SA_Score resmi dan pangkalan data fpscores bawaan.
"""
import sys
from pathlib import Path
from . import catat

_sascorer = None
_inited = False


def _muat_sascorer():
    """Inisialisasi modul sascorer secara aman dan mendukung mode PyInstaller/frozen."""
    global _sascorer, _inited
    if _inited:
        return _sascorer
    _inited = True
    try:
        from . import _sascorer_impl
        # Cari berkas database fpscores.pkl.gz
        kandidat = [
            Path(__file__).resolve().parent.parent / "aset" / "sascore" / "fpscores.pkl.gz",
            Path(__file__).resolve().parent.parent / "aset" / "fpscores.pkl.gz",
        ]
        if getattr(sys, "frozen", False):
            meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
            kandidat.extend([
                meipass / "virmolab" / "aset" / "sascore" / "fpscores.pkl.gz",
                meipass / "virmolab" / "aset" / "fpscores.pkl.gz",
                meipass / "_internal" / "virmolab" / "aset" / "sascore" / "fpscores.pkl.gz",
                meipass / "_internal" / "virmolab" / "aset" / "fpscores.pkl.gz",
                Path(sys.executable).parent / "_internal" / "virmolab" / "aset" / "sascore" / "fpscores.pkl.gz",
                Path(sys.executable).parent / "_internal" / "virmolab" / "aset" / "fpscores.pkl.gz",
            ])
        try:
            from rdkit import RDConfig
            if hasattr(RDConfig, "RDContribDir") and RDConfig.RDContribDir:
                kandidat.append(Path(RDConfig.RDContribDir) / "SA_Score" / "fpscores.pkl.gz")
        except Exception:
            pass

        for p in kandidat:
            if p.is_file():
                _sascorer_impl.readFragmentScores(str(p))
                _sascorer = _sascorer_impl
                return _sascorer
    except Exception:
        _sascorer = None
    return _sascorer


def hitung_sascore(mol):
    """Hitung SAScore untuk objek RDKit Mol atau string SMILES.

    Kembalikan float (1.0 - 10.0 dibulatkan 2 desimal) atau None bila gagal.
    """
    if mol is None:
        return None
    from rdkit import Chem
    if isinstance(mol, str):
        try:
            m = Chem.MolFromSmiles(mol)
            if m is None:
                return None
            mol = m
        except Exception as e:
            catat.log.debug(f"SAScore: gagal parse SMILES '{mol}': {e}")
            return None

    mod = _muat_sascorer()
    if mod is None:
        return None

    try:
        # Netralkan atau buang atom H eksplisit jika perlu
        m = Chem.RemoveHs(mol) if mol.GetNumAtoms() > 0 else mol
        skor = mod.calculateScore(m)
        if skor is not None and not (isinstance(skor, float) and (skor != skor or skor == float("inf"))):
            return round(float(skor), 2)
    except Exception as e:
        catat.log.debug(f"SAScore kalkulasi gagal: {e}")
    return None


def kategori(skor):
    """Kategori kemudahan sintesis: 'Mudah' (<= 3.0), 'Sedang' (3.0-6.0), 'Sulit' (> 6.0)."""
    if skor is None:
        return "-"
    if skor <= 3.0:
        return "Mudah"
    if skor <= 6.0:
        return "Sedang"
    return "Sulit"


def token_warna(skor):
    """Kunci warna tema VirmoLab: 'ok' (hijau), 'warn' (kuning), 'bad' (merah)."""
    if skor is None:
        return "ink"
    if skor <= 3.0:
        return "ok"
    if skor <= 6.0:
        return "warn"
    return "bad"


def keterangan(skor):
    """Penjelasan ringkas untuk tooltip dan laporan."""
    if skor is None:
        return "SAScore tidak dapat dihitung."
    kat = kategori(skor)
    if kat == "Mudah":
        return f"SAScore {skor:.2f}: Struktur sederhana, blok pembangun tersedia komersial (mudah disintesis)."
    if kat == "Sedang":
        return f"SAScore {skor:.2f}: Kompleksitas moderat, membutuhkan beberapa tahap reaksi sintesis."
    return f"SAScore {skor:.2f}: Sangat kompleks, pusat kiral banyak, atau cincin non-standar (sulit disintesis)."
