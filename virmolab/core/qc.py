"""Kontrol kualitas pose docking dengan PoseBusters (Buttenschoen, Morris & Deane 2024; MIT).

Konfigurasi "dock": kimia (sanitasi, InChI, keterhubungan, radikal), geometri (panjang & sudut ikatan,
tabrakan internal, kerataan cincin aromatik & ikatan rangkap, energi internal UFF) dan
antarmolekul (jarak minimum & tumpang-tindih volume dengan protein, kofaktor, air).
Pose dianggap "lulus" bila SEMUA uji biner lulus (definisi "PB-valid" di makalah PoseBusters).

PoseBusters dijalankan di PROSES terpisah (satu proses pekerja, dipakai ulang): ETKDG/UFF untuk uji
energi memegang GIL hingga detik-an sehingga di thread biasa GUI tersendat. Protein dimuat sekali per
berkas di proses itu. Fungsi publik dipanggil dari thread pekerja (tidak boleh menyentuh GUI).
"""
import logging
import threading
import warnings

VERSI = 1

# kolom biner keluaran PoseBusters -> (nama Indonesia, kelompok)
UJI = {
    "mol_pred_loaded": ("Pose terbaca", "Kimia"),
    "mol_cond_loaded": ("Protein terbaca", "Kimia"),
    "sanitization": ("Sanitasi RDKit", "Kimia"),
    "inchi_convertible": ("Dapat diubah ke InChI", "Kimia"),
    "all_atoms_connected": ("Semua atom terhubung", "Kimia"),
    "no_radicals": ("Tanpa radikal", "Kimia"),
    "bond_lengths": ("Panjang ikatan", "Geometri"),
    "bond_angles": ("Sudut ikatan", "Geometri"),
    "internal_steric_clash": ("Tanpa tabrakan sterik internal", "Geometri"),
    "aromatic_ring_flatness": ("Cincin aromatik datar", "Geometri"),
    "non-aromatic_ring_non-flatness": ("Cincin non-aromatik tidak datar", "Geometri"),
    "double_bond_flatness": ("Ikatan rangkap datar", "Geometri"),
    "internal_energy": ("Energi internal wajar (UFF)", "Geometri"),
    "protein-ligand_maximum_distance": ("Ligan dekat protein (≤ 5 Å)", "Antarmolekul"),
    "minimum_distance_to_protein": ("Jarak minimum ke protein", "Antarmolekul"),
    "minimum_distance_to_organic_cofactors": ("Jarak minimum ke kofaktor organik", "Antarmolekul"),
    "minimum_distance_to_inorganic_cofactors": ("Jarak minimum ke ion/kofaktor anorganik", "Antarmolekul"),
    "minimum_distance_to_waters": ("Jarak minimum ke air", "Antarmolekul"),
    "volume_overlap_with_protein": ("Tumpang-tindih volume dengan protein", "Antarmolekul"),
    "volume_overlap_with_organic_cofactors": ("Tumpang-tindih dengan kofaktor organik", "Antarmolekul"),
    "volume_overlap_with_inorganic_cofactors": ("Tumpang-tindih dengan ion/kofaktor anorganik", "Antarmolekul"),
    "volume_overlap_with_waters": ("Tumpang-tindih dengan air", "Antarmolekul"),
}
# besaran yang ditampilkan di detail
ANGKA = {
    "energy_ratio": "Rasio energi (pose / rerata konformer)",
    "smallest_distance_protein": "Jarak terdekat ke protein (Å)",
    "num_pairwise_clashes_protein": "Jumlah tabrakan dengan protein",
    "number_clashes": "Jumlah tabrakan internal",
    "number_short_outlier_bonds": "Ikatan terlalu pendek",
    "number_long_outlier_bonds": "Ikatan terlalu panjang",
    "number_outlier_angles": "Sudut menyimpang",
    "aromatic_ring_maximum_distance_from_plane": "Simpangan maks. cincin aromatik (Å)",
}
SITASI = ("Buttenschoen M, Morris GM, Deane CM. PoseBusters: AI-based docking methods fail to generate "
          "physically valid poses or generalise to novel sequences. Chem Sci. 2024;15:3130-3139. "
          "doi:10.1039/D3SC04185A")

_kunci = threading.Lock()
_pb = None
_protein = {}      # (jalur, mtime) -> Mol


def tersedia():
    """Cek ringan (tanpa mengimpor pandas) apakah paket posebusters ada."""
    import importlib.util
    try:
        return importlib.util.find_spec("posebusters") is not None
    except Exception:
        return False   # pencarian paket gagal = anggap tidak terpasang; PoseBusters memang opsional


def _busters():
    global _pb
    if _pb is None:
        from posebusters import PoseBusters
        logging.getLogger("posebusters").setLevel(logging.ERROR)
        _pb = PoseBusters(config="dock", max_workers=0)   # tanpa multiprocessing (aman di exe beku)
    return _pb


def _muat_protein(path):
    from pathlib import Path
    from posebusters.tools.loading import safe_load_mol
    p = Path(path)
    k = (str(p), p.stat().st_mtime)
    if k not in _protein:
        _protein.clear()
        _protein[k] = safe_load_mol(p)
    return _protein[k]


def periksa(mol, path_protein):
    """Kembalikan dict ringkas: lulus, n_uji, gagal [nama], uji [(kunci, nama, kelompok, ok)], angka {}."""
    import math
    with _kunci, warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from rdkit import RDLogger
        RDLogger.DisableLog("rdApp.*")
        try:
            pb = _busters()
            prot = _muat_protein(path_protein)
            df = pb.bust(mol_pred=mol, mol_cond=prot, full_report=True)
        finally:
            RDLogger.EnableLog("rdApp.*")
    baris = df.iloc[0].to_dict()
    uji = []
    for k, (nama, kel) in UJI.items():
        if k in baris and baris[k] is not None and not (isinstance(baris[k], float) and math.isnan(baris[k])):
            uji.append((k, nama, kel, bool(baris[k])))
    angka = {}
    for k in ANGKA:
        v = baris.get(k)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            angka[k] = int(v) if k.startswith(("num_", "number_")) else round(float(v), 3)
    gagal = [n for _, n, _, ok in uji if not ok]
    return {"v": VERSI, "lulus": not gagal, "n_uji": len(uji), "gagal": gagal, "uji": uji, "angka": angka}


def tanpa_uji_jarak(q):
    """Buang uji jarak minimum ke protein (docking kovalen: ikatan kovalen memang lebih pendek dari kontak vdW)."""
    if not q or q.get("galat"):
        return q
    uji = [u for u in q["uji"] if u[0] != "minimum_distance_to_protein"]
    gagal = [n for _, n, _, ok in uji if not ok]
    return dict(q, uji=uji, gagal=gagal, n_uji=len(uji), lulus=not gagal, kovalen=True)


def teks_sel(q):
    """Isi kolom tabel."""
    if not q:
        return ""
    if q.get("galat"):
        return "galat"
    return "Lulus" if q["lulus"] else f"Gagal ({len(q['gagal'])})"


def tooltip(q):
    if not q:
        return "Belum diperiksa"
    if q.get("galat"):
        return "PoseBusters gagal: " + q["galat"]
    t = [f"PoseBusters: {q['n_uji'] - len(q['gagal'])}/{q['n_uji']} uji lulus"]
    t += ["✗ " + g for g in q["gagal"]]
    if q.get("kovalen"):
        t.append("Uji jarak minimum ke protein dilewati (ikatan kovalen lebih pendek dari kontak vdW).")
    for k, v in q.get("angka", {}).items():
        t.append(f"{ANGKA[k]}: {v}")
    return "\n".join(t)


def jalur_protein(proyek, j=None):
    """PDB reseptor bersih (berelemen) untuk PoseBusters; None bila tidak ada."""
    r = proyek.reseptor or {}
    for k in ("bersih", "asli"):
        if r.get(k) and proyek.p(r[k]).exists():
            return proyek.p(r[k])
    return None


# ------------------------------------------------------- proses pekerja
_pek = None              # (Popen, Connection)
_pek_kunci = threading.Lock()


def _perintah_pekerja(alamat, kunci_hex):
    import sys
    if getattr(sys, "frozen", False):
        from . import paths
        return [str(paths.EXE_UTAMA), "--qc-pekerja", alamat, kunci_hex]
    return [sys.executable, "-m", "virmolab", "--qc-pekerja", alamat, kunci_hex]


def _mulai_pekerja():
    import os
    import subprocess
    from multiprocessing.connection import Listener
    kunci = os.urandom(16)
    lst = Listener(family="AF_PIPE", authkey=kunci)
    proc = subprocess.Popen(_perintah_pekerja(lst.address, kunci.hex()), stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    hasil = {}

    def terima():
        try:
            hasil["c"] = lst.accept()
        except Exception as e:
            hasil["e"] = e
    t = threading.Thread(target=terima, daemon=True)
    t.start()
    t.join(90)
    if "c" not in hasil:
        proc.kill()
        lst.close()
        raise RuntimeError("proses pekerja PoseBusters tidak tersambung")
    lst.close()
    return proc, hasil["c"]


def layani(alamat, kunci_hex):
    """Titik masuk proses pekerja: terima {'blok','protein'} -> kirim hasil periksa()."""
    from multiprocessing.connection import Client
    from rdkit import Chem
    c = Client(alamat, family="AF_PIPE", authkey=bytes.fromhex(kunci_hex))
    while True:
        try:
            m = c.recv()
        except (EOFError, OSError):
            break
        if m is None:
            break
        try:
            mol = Chem.MolFromMolBlock(m["blok"], removeHs=False, sanitize=False)
            Chem.SanitizeMol(mol, catchErrors=True)
            c.send(("ok", periksa(mol, m["protein"])))
        except Exception as e:
            c.send(("galat", f"{type(e).__name__}: {e}"))


def periksa_proses(mol, path_protein):
    """Seperti periksa(), tetapi di proses pekerja terpisah (GUI tetap mulus). Bila gagal, jalan di proses ini."""
    global _pek
    from rdkit import Chem
    blok = Chem.MolToMolBlock(mol, kekulize=False)
    with _pek_kunci:
        try:
            if _pek is None or _pek[0].poll() is not None:
                _pek = _mulai_pekerja()
            _pek[1].send({"blok": blok, "protein": str(path_protein)})
            status, isi = _pek[1].recv()
        except Exception:
            if _pek is not None:
                try:
                    _pek[0].kill()
                except Exception:
                    pass
            _pek = None
            return periksa(mol, path_protein)
    if status != "ok":
        raise RuntimeError(isi)
    return isi


def tutup():
    """Hentikan proses pekerja (dipanggil saat aplikasi ditutup)."""
    global _pek
    with _pek_kunci:
        if _pek is not None:
            try:
                _pek[1].send(None)
                _pek[1].close()
                _pek[0].wait(3)
            except Exception:
                _pek[0].kill()
            _pek = None


def periksa_ligan(proyek, j, l, pose):
    """QC pose terbaik satu ligan job. Kembalikan dict (atau {'galat': ...}); tidak mengubah l."""
    from .analisis import pose_mol
    prot = jalur_protein(proyek, j)
    if prot is None or not pose:
        return None
    try:
        mol = pose_mol(proyek.p(l["pdbqt"]).read_text(), pose[0].pdbqt)
        if pose[0].flex:   # residu fleksibel: protein dengan rantai samping pada posisi pose
            from . import mesin as M
            from . import paths
            f = paths.CACHE / f"qc_flex_{j['id']}_{l['id']}.pdb"
            f.write_text(M.terapkan_flex(prot.read_text(), pose[0].flex), encoding="utf-8")
            prot = f
        h = periksa_proses(mol, prot)
        return tanpa_uji_jarak(h) if j.get("kovalen") else h
    except Exception as e:
        return {"v": VERSI, "galat": (str(e).strip().splitlines() or [type(e).__name__])[0][:200]}
