"""Sifat elektronik semi-empiris dengan xtb (GFN2-xTB), F7.

Menghitung deskriptor elektronik satu molekul lewat biner `xtb` (LGPL-3.0, grimme-lab):
HOMO, LUMO, celah, kekerasan kimia, potensial kimia, elektrofilisitas, momen dipol, muatan parsial
Mulliken, indeks Fukui (f+, f-, f0), dan titik potensial elektrostatik untuk permukaan di penampil.

PERINGATAN ILMIAH yang wajib ikut ke mana pun angka ini dibawa (lihat `CATATAN_METODE`):
GFN2-xTB adalah metode semi-empiris, bukan DFT. Celah HOMO-LUMO-nya cenderung lebih kecil daripada
DFT, jadi angkanya hanya layak untuk membandingkan tren antar-ligan, bukan sebagai nilai mutlak.

Perhitungan berjalan di proses terpisah dengan folder kerja sementara, jadi kegagalan satu molekul
tidak menjatuhkan aplikasi. Kegagalan mengembalikan None beserta sebabnya, bukan angka bawaan.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from . import catat, paths

NOWIN = 0x08000000

CATATAN_METODE = (
    "GFN2-xTB semi-empiris; celah HOMO–LUMO cenderung lebih kecil dari DFT, pakai untuk tren "
    "antar-ligan, bukan nilai absolut. Bukan DFT."
)

# Pelarut ALPB yang didukung xtb dan masuk akal untuk kerja docking
PELARUT = ("water", "methanol", "dmso", "acetonitrile", "chcl3", "toluene", "none")

HARTREE_KE_EV = 27.211386245988


@dataclass
class HasilXtb:
    """Hasil satu molekul. Semua nilai None berarti tidak terhitung, bukan nol."""

    tersedia: bool = False
    pesan: str = ""
    nama: str = ""
    energi_hartree: Optional[float] = None
    homo_ev: Optional[float] = None
    lumo_ev: Optional[float] = None
    celah_ev: Optional[float] = None
    kekerasan_ev: Optional[float] = None          # eta = (LUMO - HOMO) / 2
    potensial_kimia_ev: Optional[float] = None    # mu = (HOMO + LUMO) / 2
    elektrofilisitas_ev: Optional[float] = None   # omega = mu^2 / (2 eta)
    dipol_debye: Optional[float] = None
    muatan: List[float] = field(default_factory=list)
    fukui: List[Dict[str, float]] = field(default_factory=list)   # per atom: {plus, minus, nol}
    simbol: List[str] = field(default_factory=list)
    esp: Optional[np.ndarray] = None              # (n, 4): x, y, z (Angstrom) dan nilai ESP
    detik: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Bentuk yang aman disimpan ke proyek (tanpa larik ESP yang besar)."""
        return {
            "tersedia": self.tersedia, "pesan": self.pesan, "nama": self.nama,
            "energi_hartree": self.energi_hartree, "homo_ev": self.homo_ev, "lumo_ev": self.lumo_ev,
            "celah_ev": self.celah_ev, "kekerasan_ev": self.kekerasan_ev,
            "potensial_kimia_ev": self.potensial_kimia_ev,
            "elektrofilisitas_ev": self.elektrofilisitas_ev, "dipol_debye": self.dipol_debye,
            "muatan": self.muatan, "fukui": self.fukui, "simbol": self.simbol,
            "metode": "GFN2-xTB", "catatan": CATATAN_METODE,
        }


def folder_xtb() -> Optional[Path]:
    """Folder pemasangan xtb di dalam paket (vendor/bin/xtb atau bin/xtb pada versi terpasang)."""
    for kandidat in (paths.BIN / "xtb", paths.BIN / "xtb" / "xtb"):
        if (kandidat / "bin" / "xtb.exe").exists():
            return kandidat
    return None


def jalur_biner() -> Optional[str]:
    """Jalur xtb.exe bawaan paket, atau xtb di PATH sistem bila pengguna memasangnya sendiri."""
    f = folder_xtb()
    if f:
        return str(f / "bin" / "xtb.exe")
    return shutil.which("xtb")


def tersedia() -> Dict[str, Any]:
    """{ada, jalur, versi, pesan}. Versi dibaca dari biner, bukan ditulis tetap di kode."""
    exe = jalur_biner()
    if not exe:
        return {"ada": False, "jalur": "", "versi": "",
                "pesan": "xtb tidak ikut dalam pemasangan ini. Unduh dari github.com/grimme-lab/xtb "
                         "(LGPL-3.0) lalu letakkan di folder bin/xtb."}
    try:
        p = subprocess.run([exe, "--version"], capture_output=True, timeout=60, creationflags=NOWIN)
        teks = (p.stdout + p.stderr).decode("utf-8", "replace")
        m = re.search(r"xtb version\s+(\S+)", teks)
        versi = m.group(1) if m else ""
    except Exception as e:
        return {"ada": False, "jalur": exe, "versi": "", "pesan": f"xtb ada tetapi gagal dijalankan: {e}"}
    return {"ada": True, "jalur": exe, "versi": versi,
            "pesan": f"xtb {versi} siap (GFN2-xTB). {CATATAN_METODE}"}


def _lingkungan() -> Dict[str, str]:
    """Salinan environment dengan XTBPATH menunjuk berkas parameter bawaan paket."""
    env = dict(os.environ)
    f = folder_xtb()
    if f:
        env["XTBPATH"] = str(f / "share" / "xtb")
    env.setdefault("OMP_NUM_THREADS", "1")   # paralel diurus pemanggil, per molekul satu inti
    return env


def _baca_json_xtb(p: Path) -> Dict[str, Any]:
    """Baca xtbout.json; perbaiki dulu bila rusak oleh jalur berkutip.

    xtb 6.7.1 menulis `"program call": ""C:\\...\\xtb.exe" mol.xyz ..."` tanpa melarikan tanda kutip
    di dalamnya, sehingga berkasnya bukan JSON sah ketika jalur programnya mengandung spasi. Nilai itu
    tidak dipakai, jadi barisnya dibuang sebelum diurai.
    """
    import json

    teks = p.read_text(encoding="utf-8", errors="replace")
    try:
        return json.loads(teks)
    except json.JSONDecodeError:
        bersih = re.sub(r'^\s*"program call":.*?,\s*$', "", teks, flags=re.MULTILINE)
        try:
            return json.loads(bersih)
        except json.JSONDecodeError as e:
            catat.log.warning(f"xtbout.json tidak dapat diurai: {e}")
            return {}


def _urai_fukui(teks: str) -> List[Dict[str, float]]:
    """Tabel Fukui dari keluaran layar xtb (`--vfukui`): '  1N   0.031  0.146  0.088'."""
    baris = teks.splitlines()
    mulai = next((i for i, b in enumerate(baris) if re.search(r"f\(\+\)\s+f\(-\)\s+f\(0\)", b)), None)
    if mulai is None:
        return []
    keluar = []
    for b in baris[mulai + 1:]:
        m = re.match(r"\s*(\d+)([A-Za-z]{1,2})\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*$", b)
        if not m:
            break
        keluar.append({"indeks": int(m.group(1)) - 1, "simbol": m.group(2),
                       "plus": float(m.group(3)), "minus": float(m.group(4)), "nol": float(m.group(5))})
    return keluar


def _urai_dipol(teks: str) -> Optional[float]:
    """Momen dipol total (Debye) dari blok 'molecular dipole'."""
    baris = teks.splitlines()
    i = next((k for k, b in enumerate(baris) if "molecular dipole" in b), None)
    if i is None:
        return None
    for b in baris[i:i + 6]:
        m = re.match(r"\s*full:\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*$", b)
        if m:
            return round(float(m.group(4)), 4)
    return None


def _urai_orbital(teks: str) -> Dict[str, Optional[float]]:
    """HOMO, LUMO, dan celah (eV) dari ringkasan xtb."""
    hasil: Dict[str, Optional[float]] = {"homo_ev": None, "lumo_ev": None, "celah_ev": None}
    for b in teks.splitlines():
        m = re.search(r"(-?\d+\.\d+)\s+\(HOMO\)", b)
        if m:
            hasil["homo_ev"] = float(m.group(1))
        m = re.search(r"(-?\d+\.\d+)\s+\(LUMO\)", b)
        if m:
            hasil["lumo_ev"] = float(m.group(1))
        m = re.search(r"HOMO-LUMO gap\s+(-?\d+\.\d+)\s+eV", b)
        if m:
            hasil["celah_ev"] = float(m.group(1))
    return hasil


def _esp_ke_angstrom(p: Path) -> Optional[np.ndarray]:
    """xtb_esp.dat: x, y, z dalam Bohr dan nilai ESP. Dikembalikan dengan koordinat Angstrom."""
    try:
        a = np.loadtxt(p)
    except Exception as e:
        catat.log.debug(f"xtb_esp.dat tidak terbaca: {e}")
        return None
    if a.ndim != 2 or a.shape[1] < 4:
        return None
    a = a[:, :4].astype(float)
    a[:, :3] *= 0.529177210903      # Bohr ke Angstrom
    return a


def _tulis_xyz(mol, folder: Path) -> Path:
    from rdkit import Chem

    if mol.GetNumConformers() == 0:
        raise ValueError("Molekul tidak punya koordinat 3D.")
    p = folder / "mol.xyz"
    Chem.MolToXYZFile(mol, str(p))
    return p


def hitung(mol, pelarut: str = "water", fukui: bool = True, esp: bool = True,
           optimasi: bool = False, batas: int = 300, batal=None, nama: str = "") -> HasilXtb:
    """Hitung deskriptor elektronik satu molekul berkonformer 3D.

    pelarut: salah satu PELARUT ('none' berarti fase gas). batas: batas waktu detik per molekul.
    batal: Event atau callable yang bernilai benar bila pengguna membatalkan.
    """
    import time

    hasil = HasilXtb(nama=nama or (mol.GetProp("_Name") if mol and mol.HasProp("_Name") else ""))
    info = tersedia()
    if not info["ada"]:
        hasil.pesan = info["pesan"]
        return hasil
    if pelarut not in PELARUT:
        hasil.pesan = f"Pelarut '{pelarut}' tidak dikenal. Pilihan: {', '.join(PELARUT)}."
        return hasil

    def _dibatalkan():
        if batal is None:
            return False
        return batal() if callable(batal) else bool(getattr(batal, "is_set", lambda: False)())

    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="virmolab_xtb_") as d:
        folder = Path(d)
        try:
            xyz = _tulis_xyz(mol, folder)
        except Exception as e:
            hasil.pesan = f"Struktur tidak dapat ditulis sebagai XYZ: {e}"
            return hasil

        arg = [info["jalur"], xyz.name, "--gfn", "2", "--json"]
        if pelarut != "none":
            arg += ["--alpb", pelarut]
        if optimasi:
            arg.append("--opt")
        if fukui:
            arg.append("--vfukui")
        if esp:
            arg.append("--esp")

        if _dibatalkan():
            hasil.pesan = "Dibatalkan sebelum xtb dijalankan."
            return hasil
        try:
            p = subprocess.run(arg, cwd=folder, capture_output=True, timeout=batas,
                               env=_lingkungan(), creationflags=NOWIN)
        except subprocess.TimeoutExpired:
            hasil.pesan = f"xtb melewati batas waktu {batas} detik untuk molekul ini."
            return hasil
        except Exception as e:
            hasil.pesan = f"xtb gagal dijalankan: {e}"
            return hasil

        teks = (p.stdout + p.stderr).decode("utf-8", "replace")
        if p.returncode != 0 or "normal termination" not in teks:
            galat = next((b.strip() for b in teks.splitlines()[::-1] if b.strip()), "")
            hasil.pesan = f"xtb berhenti tidak normal: {galat[:200]}"
            return hasil
        if "convergence criteria cannot be satisfied" in teks or "SCF not converged" in teks:
            hasil.pesan = "SCF xtb tidak konvergen untuk molekul ini; hasilnya tidak dipakai."
            return hasil

        d_json = _baca_json_xtb(folder / "xtbout.json") if (folder / "xtbout.json").exists() else {}
        orbital = _urai_orbital(teks)
        hasil.homo_ev = orbital["homo_ev"]
        hasil.lumo_ev = orbital["lumo_ev"]
        hasil.celah_ev = orbital["celah_ev"] if orbital["celah_ev"] is not None else d_json.get("HOMO-LUMO gap/eV")
        hasil.energi_hartree = d_json.get("total energy")
        hasil.dipol_debye = _urai_dipol(teks)
        hasil.muatan = [float(x) for x in (d_json.get("partial charges") or [])]
        hasil.simbol = [a.GetSymbol() for a in mol.GetAtoms()]
        if fukui:
            hasil.fukui = _urai_fukui(teks)
        if esp and (folder / "xtb_esp.dat").exists():
            hasil.esp = _esp_ke_angstrom(folder / "xtb_esp.dat")

    if hasil.homo_ev is not None and hasil.lumo_ev is not None:
        eta = (hasil.lumo_ev - hasil.homo_ev) / 2.0
        mu = (hasil.homo_ev + hasil.lumo_ev) / 2.0
        hasil.kekerasan_ev = round(eta, 4)
        hasil.potensial_kimia_ev = round(mu, 4)
        # Elektrofilisitas tidak terdefinisi bila kekerasan nol; jangan dipaksa jadi angka
        hasil.elektrofilisitas_ev = round(mu * mu / (2.0 * eta), 4) if abs(eta) > 1e-6 else None

    hasil.tersedia = hasil.celah_ev is not None
    if not hasil.tersedia and not hasil.pesan:
        hasil.pesan = "xtb selesai tetapi tidak melaporkan celah HOMO-LUMO."
    hasil.detik = round(time.time() - t0, 1)
    return hasil


def _kerja_satu(args):
    """Pekerja ProcessPoolExecutor: (smiles_atau_molblock, nama, opsi) -> dict hasil."""
    molblok, nama, opsi = args
    from rdkit import Chem

    mol = Chem.MolFromMolBlock(molblok, removeHs=False)
    if mol is None:
        return {"tersedia": False, "nama": nama, "pesan": "Struktur tidak dapat diurai."}
    h = hitung(mol, nama=nama, **opsi)
    d = h.to_dict()
    d["detik"] = h.detik
    return d


def hitung_banyak(molekul_dan_nama: Sequence, pelarut: str = "water", fukui: bool = True,
                  esp: bool = False, batas: int = 300, n_proses: Optional[int] = None,
                  batal=None, progres: Optional[Callable[[int, int, str], None]] = None
                  ) -> List[Dict[str, Any]]:
    """Hitung banyak molekul paralel per inti CPU. Masukan: [(mol, nama), ...].

    ESP dimatikan secara bawaan di sini karena larik titiknya besar dan hanya berguna untuk satu
    molekul yang sedang dilihat di penampil.
    """
    from rdkit import Chem

    opsi = {"pelarut": pelarut, "fukui": fukui, "esp": esp, "batas": batas}
    tugas = []
    for mol, nama in molekul_dan_nama:
        if mol is None or mol.GetNumConformers() == 0:
            continue
        tugas.append((Chem.MolToMolBlock(mol), nama, opsi))
    total = len(tugas)
    if not total:
        return []

    def _dibatalkan():
        if batal is None:
            return False
        return batal() if callable(batal) else bool(getattr(batal, "is_set", lambda: False)())

    n = n_proses or max(1, min(os.cpu_count() or 4, 8))
    hasil: List[Dict[str, Any]] = []
    if total == 1 or n == 1:
        for t in tugas:
            if _dibatalkan():
                break
            hasil.append(_kerja_satu(t))
            if progres:
                progres(len(hasil), total, f"{len(hasil)} / {total} molekul")
        return hasil

    with ProcessPoolExecutor(max_workers=n) as ex:
        futur = {ex.submit(_kerja_satu, t): t[1] for t in tugas}
        for f in as_completed(futur):
            if _dibatalkan():
                ex.shutdown(wait=False, cancel_futures=True)
                break
            try:
                hasil.append(f.result())
            except Exception as e:
                hasil.append({"tersedia": False, "nama": futur[f], "pesan": f"Gagal: {e}"})
            if progres:
                progres(len(hasil), total, f"{len(hasil)} / {total} molekul")
    return hasil


def korelasi_som(hasil: HasilXtb, situs_som: Sequence[int]) -> Dict[str, Any]:
    """Bandingkan indeks Fukui f(-) dengan prediksi situs metabolisme CYP (`core/metabolisme.py`).

    f(-) besar berarti atom mudah diserang elektrofil, yang sejalan dengan oksidasi CYP. Dikembalikan
    peringkat atom SoM menurut f(-) supaya pengguna melihat apakah keduanya menunjuk atom yang sama.
    Himpunan kosong mengembalikan hasil kosong, bukan kesimpulan.
    """
    if not hasil.fukui or not situs_som:
        return {"cocok": [], "n_som": len(situs_som or []), "pesan": "Belum ada data Fukui atau situs SoM."}
    urut = sorted(hasil.fukui, key=lambda f: -f["minus"])
    peringkat = {f["indeks"]: i + 1 for i, f in enumerate(urut)}
    n = len(urut)
    cocok = [{"atom": i, "peringkat_fukui": peringkat.get(i), "dari": n,
              "f_minus": next((f["minus"] for f in hasil.fukui if f["indeks"] == i), None)}
             for i in situs_som if i in peringkat]
    teratas = [c for c in cocok if c["peringkat_fukui"] and c["peringkat_fukui"] <= max(3, n // 4)]
    pesan = (f"{len(teratas)} dari {len(cocok)} situs metabolisme berada di peringkat atas f(-). "
             if cocok else "Situs metabolisme tidak ditemukan pada daftar atom Fukui. ")
    return {"cocok": cocok, "n_som": len(situs_som), "pesan": pesan + CATATAN_METODE}


def paragraf_metode(hasil: HasilXtb, pelarut: str = "water") -> str:
    """Kalimat metode dari hasil nyata; kosong bila belum ada perhitungan."""
    if not hasil or not hasil.tersedia:
        return ""
    info = tersedia()
    versi = f" {info['versi']}" if info.get("versi") else ""
    larut = "fase gas" if pelarut == "none" else f"pelarut implisit ALPB ({pelarut})"
    bagian = [f"Deskriptor elektronik dihitung dengan GFN2-xTB (xtb{versi}) pada {larut}"]
    if hasil.celah_ev is not None:
        bagian.append(f"celah HOMO-LUMO {hasil.celah_ev:.2f} eV".replace(".", ","))
    if hasil.dipol_debye is not None:
        bagian.append(f"momen dipol {hasil.dipol_debye:.2f} D".replace(".", ","))
    if hasil.fukui:
        bagian.append("indeks Fukui kondensasi muatan Mulliken (f+, f-, f0)")
    return ". ".join([", ".join(bagian), CATATAN_METODE])


def esp_per_atom(hasil: HasilXtb, mol, k: int = 8) -> List[Optional[float]]:
    """Rata-rata ESP dari k titik terdekat tiap atom, untuk mewarnai permukaan di penampil.

    Titik ESP xtb terletak di permukaan Lebedev sekeliling molekul, bukan di atom, jadi nilainya
    dipetakan ke atom terdekat. Ini pendekatan untuk tampilan; angka yang dilaporkan di tabel tetap
    berasal langsung dari xtb. Atom tanpa titik terdekat bernilai None, bukan nol.
    """
    if hasil.esp is None or len(hasil.esp) == 0 or mol is None or mol.GetNumConformers() == 0:
        return [None] * (mol.GetNumAtoms() if mol else 0)
    pos = mol.GetConformer().GetPositions()
    titik, nilai = hasil.esp[:, :3], hasil.esp[:, 3]
    keluar: List[Optional[float]] = []
    for p in pos:
        d = np.linalg.norm(titik - p, axis=1)
        dekat = np.argsort(d)[:max(1, k)]
        keluar.append(float(np.mean(nilai[dekat])) if len(dekat) else None)
    return keluar


def rentang_simetris(nilai: Sequence[Optional[float]]) -> Dict[str, float]:
    """Batas skala warna divergen yang simetris terhadap nol, supaya positif dan negatif sebanding."""
    ada = [v for v in nilai if v is not None]
    if not ada:
        return {"min": -1.0, "max": 1.0}
    batas = max(abs(min(ada)), abs(max(ada))) or 1.0
    return {"min": -batas, "max": batas}


def situs_som(mol) -> List[int]:
    """Indeks atom situs metabolisme CYP pada `mol`, dipetakan dari `core/metabolisme.py`.

    Modul metabolisme bekerja pada molekul yang dibangun ulang dari SMILES, sehingga penomoran
    atomnya belum tentu sama dengan molekul 3D di sini. Pemetaan dilakukan lewat pencocokan
    substruktur; bila gagal, daftar dikembalikan kosong supaya tidak ada atom yang salah ditunjuk.
    """
    from rdkit import Chem

    from . import metabolisme

    if mol is None:
        return []
    try:
        tanpa_h = Chem.RemoveHs(mol)
        smi = Chem.MolToSmiles(tanpa_h)
        hasil = metabolisme.prediksi_titik_metabolisme(smi)
    except Exception as e:
        catat.log.debug(f"Prediksi situs metabolisme gagal: {e}")
        return []

    acuan = Chem.MolFromSmiles(smi)
    cocok = tanpa_h.GetSubstructMatch(acuan) if acuan is not None else ()
    if not cocok:
        catat.log.debug("Penomoran atom SMILES tidak dapat dipetakan ke molekul 3D; korelasi SoM dilewati.")
        return []

    berat = [a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum() > 1]
    keluar = []
    for s in (hasil.get("daftar_som") or hasil.get("som") or []):
        i = s.get("indeks_atom")
        if i is None or i >= len(cocok):
            continue
        j = cocok[i]
        if j < len(berat):
            keluar.append(berat[j])
    return sorted(set(keluar))
