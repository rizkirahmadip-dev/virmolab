"""Docking peptida (F10): sekuens peptida ke kompleks dengan reseptor.

Vina dan AutoDock-GPU lemah untuk peptida karena jumlah ikatan berputarnya besar, jadi alur ini
memakai co-folding Boltz-2 (lihat `core/kofolding.py`) untuk membangun kompleks, lalu:

1. `validasi_sekuens` memeriksa panjang dan residu sebelum apa pun dijalankan.
2. `cofold_peptida` menjalankan Boltz-2 lewat WSL dengan peptida sebagai rantai protein tersendiri.
3. `murnikan` meminimisasi kompleks di pelarut implisit, dengan pilihan dinamika singkat.
4. `mmgbsa_peptida` menghitung MM/GBSA dengan peptida sebagai bagian "ligan".
5. `analisis_antarmuka` memakai `core/ppi.py` untuk kontak, ikatan hidrogen, jembatan garam, dan ΔSASA.

AutoDock CrankPep (ADCP) sengaja tidak dipakai: lisensinya belum diverifikasi sebagai sumber terbuka,
dan aturan proyek melarang memakai komponen yang status lisensinya tidak jelas.

Semua kegagalan dilaporkan sebagai nilai kosong beserta sebabnya, bukan angka bawaan.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import catat, kofolding, ppi

# 20 asam amino standar (kode satu huruf)
ASAM_AMINO_STANDAR = set("ACDEFGHIKLMNPQRSTVWY")

# Residu non-standar yang didukung Boltz-2 lewat kode satu huruf; dipetakan ke padanan standarnya
# hanya untuk pemeriksaan panjang, bukan untuk mengubah sekuens yang dikirim.
NON_STANDAR_DIDUKUNG = {
    "B": "Asx (Asn atau Asp)",
    "Z": "Glx (Gln atau Glu)",
    "X": "residu tidak diketahui",
    "U": "selenosistein",
    "O": "pirolisin",
}

PANJANG_MAKS = 30
PANJANG_MIN = 2


@dataclass
class HasilPeptida:
    """Hasil satu alur docking peptida. Nilai None berarti tahap itu tidak berjalan."""

    tersedia: bool = False
    pesan: str = ""
    sekuens: str = ""
    rantai_peptida: str = ""
    pdb_kompleks: str = ""
    pdb_kompleks_murni: str = ""
    plddt: Optional[float] = None
    ptm: Optional[float] = None
    rmsd_minimisasi: Optional[float] = None
    mmgbsa: Optional[Dict[str, float]] = None
    antarmuka: Optional[Dict[str, Any]] = None
    rincian: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tersedia": self.tersedia,
            "pesan": self.pesan,
            "sekuens": self.sekuens,
            "rantai_peptida": self.rantai_peptida,
            "plddt": self.plddt,
            "ptm": self.ptm,
            "rmsd_minimisasi": self.rmsd_minimisasi,
            "mmgbsa": self.mmgbsa,
            "antarmuka": self.antarmuka,
        }


def validasi_sekuens(sekuens: str) -> Dict[str, Any]:
    """Periksa sekuens peptida satu huruf sebelum dijalankan.

    Kembalikan {"sah", "sekuens", "panjang", "posisi_galat", "pesan", "peringatan"}. `posisi_galat`
    berisi indeks berbasis nol pada sekuens yang sudah dibersihkan, untuk disorot di antarmuka.
    """
    mentah = sekuens or ""
    bersih = "".join(c for c in mentah.upper() if not c.isspace())
    # Sekuens dari FASTA sering memuat tanda '*' di ujung dan '-' sebagai sisipan
    bersih = bersih.replace("*", "").replace("-", "")

    hasil: Dict[str, Any] = {"sah": False, "sekuens": bersih, "panjang": len(bersih),
                             "posisi_galat": [], "pesan": "", "peringatan": ""}
    if not bersih:
        hasil["pesan"] = "Sekuens peptida masih kosong."
        return hasil

    dikenal = ASAM_AMINO_STANDAR | set(NON_STANDAR_DIDUKUNG)
    hasil["posisi_galat"] = [i for i, c in enumerate(bersih) if c not in dikenal]
    if hasil["posisi_galat"]:
        huruf = sorted({bersih[i] for i in hasil["posisi_galat"]})
        hasil["pesan"] = (f"Huruf tidak dikenal sebagai asam amino: {', '.join(huruf)}. "
                          "Pakai kode satu huruf, misalnya ETFSDLWKLLP.")
        return hasil

    if len(bersih) < PANJANG_MIN:
        hasil["pesan"] = f"Peptida terlalu pendek ({len(bersih)} residu); minimal {PANJANG_MIN}."
        return hasil
    if len(bersih) > PANJANG_MAKS:
        hasil["pesan"] = (f"Peptida {len(bersih)} residu melebihi batas {PANJANG_MAKS}. Batas ini dipakai "
                          "karena prediksi menjadi jauh lebih lambat dan kurang dapat dipercaya untuk rantai panjang.")
        hasil["posisi_galat"] = list(range(PANJANG_MAKS, len(bersih)))
        return hasil

    non_standar = sorted({c for c in bersih if c in NON_STANDAR_DIDUKUNG})
    if non_standar:
        rinci = ", ".join(f"{c} ({NON_STANDAR_DIDUKUNG[c]})" for c in non_standar)
        hasil["peringatan"] = (f"Sekuens memuat kode tidak baku: {rinci}. Prediksinya kurang dapat dipercaya "
                               "dibandingkan sekuens yang seluruhnya memakai 20 asam amino standar.")

    hasil["sah"] = True
    return hasil


def sekuens_dari_pdb(pdb_teks: str, rantai: Optional[str] = None) -> List[Tuple[str, str]]:
    """Sekuens satu huruf per rantai dari teks PDB, memakai tabel residu `core/analisis.py`."""
    from .konservasi import TIGA_KE_SATU

    per_rantai: Dict[str, List[Tuple[str, str]]] = {}
    terlihat = set()
    for b in pdb_teks.splitlines():
        if not b.startswith("ATOM"):
            continue
        ch = b[21]
        if rantai and ch != rantai:
            continue
        resi = b[22:27].strip()
        kunci = (ch, resi)
        if kunci in terlihat:
            continue
        terlihat.add(kunci)
        per_rantai.setdefault(ch, []).append((resi, TIGA_KE_SATU.get(b[17:20].strip(), "X")))
    return [(ch, "".join(h for _, h in daftar)) for ch, daftar in sorted(per_rantai.items())]


def cofold_peptida(sekuens_reseptor: Sequence[Tuple[str, str]], sekuens_peptida: str, folder,
                   gpu: bool = True, msa_server: bool = False, penuh: bool = False) -> str:
    """Jalankan Boltz-2 dengan peptida sebagai rantai protein tersendiri. Kembalikan log Boltz."""
    from . import lanjutan

    v = validasi_sekuens(sekuens_peptida)
    if not v["sah"]:
        raise ValueError(v["pesan"])
    if not sekuens_reseptor:
        raise ValueError("Reseptor tidak punya sekuens asam amino.")
    return lanjutan.prediksi_boltz(list(sekuens_reseptor), None, Path(folder), gpu=gpu,
                                   msa_server=msa_server, penuh=penuh, peptida=v["sekuens"])


def pisahkan_rantai(pdb_teks: str, rantai: str) -> Tuple[str, str]:
    """Pisahkan PDB kompleks menjadi (teks rantai terpilih, teks rantai lainnya)."""
    dipilih, sisa = [], []
    for b in pdb_teks.splitlines():
        if b.startswith(("ATOM", "HETATM")):
            (dipilih if b[21] == rantai else sisa).append(b)
        elif b.startswith("TER"):
            continue
    return "\n".join(dipilih) + "\n", "\n".join(sisa) + "\n"


def tebak_rantai_peptida(pdb_teks: str, panjang_peptida: int) -> str:
    """Tebak rantai mana yang merupakan peptida: rantai terpendek yang panjangnya paling mendekati sekuens."""
    rantai = sekuens_dari_pdb(pdb_teks)
    if not rantai:
        return ""
    cocok = [c for c, s in rantai if len(s) == panjang_peptida]
    if cocok:
        return cocok[0]
    return min(rantai, key=lambda x: (abs(len(x[1]) - panjang_peptida), len(x[1])))[0]


def _indeks_rantai(topologi, rantai_id: str) -> List[int]:
    """Indeks atom OpenMM milik satu rantai PDB."""
    return [a.index for c in topologi.chains() if c.id == rantai_id for r in c.residues() for a in r.atoms()]


def murnikan(pdb_kompleks: str, rantai_peptida: str, ps_dinamika: float = 0.0,
             platform: Optional[str] = None, lapor=None) -> Dict[str, Any]:
    """Minimisasi kompleks di pelarut implisit, lalu MM/GBSA dengan peptida sebagai bagian "ligan".

    `ps_dinamika` > 0 menambah dinamika singkat sesudah minimisasi (rencana F10 memakai 100 ps);
    0 berarti minimisasi saja. Kembalikan {"pdb", "rmsd", "mmgbsa", "detik", "pesan"}.
    """
    import io as _io
    import time

    from openmm import app, unit
    import openmm as mm

    from .md import KKAL, MMGBSA, platform_terbaik, sistem_implisit

    log = lapor or (lambda s: None)
    t0 = time.time()
    plat = platform_terbaik(platform or "auto")
    nama_plat, p_obj, prop = plat

    pdb = app.PDBFile(_io.StringIO(pdb_kompleks))
    ff = app.ForceField("amber14-all.xml", "amber14/tip3p.xml")
    modeller = app.Modeller(pdb.topology, pdb.positions)
    modeller.addHydrogens(ff, pH=7.4)

    idx_pep = _indeks_rantai(modeller.topology, rantai_peptida)
    if not idx_pep:
        raise ValueError(f"Rantai peptida '{rantai_peptida}' tidak ada di kompleks.")
    info = {"idx_ligan": idx_pep}

    log(f"Minimisasi kompleks ({modeller.topology.getNumAtoms()} atom) di {nama_plat}…")
    sistem = sistem_implisit(ff, modeller.topology, grup=False)
    pos_awal = np.asarray(modeller.positions.value_in_unit(unit.nanometer))

    # Reseptor dikekang supaya peptida yang menyesuaikan diri, bukan seluruh kompleks bergeser
    kekang = mm.CustomExternalForce("0.5*kk*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
    kekang.addGlobalParameter("kk", 5.0 * KKAL * 100.0)
    for nm in ("x0", "y0", "z0"):
        kekang.addPerParticleParameter(nm)
    set_pep = set(idx_pep)
    for a in modeller.topology.atoms():
        if a.index not in set_pep and a.element is not None and a.element.symbol != "H":
            kekang.addParticle(a.index, pos_awal[a.index].tolist())
    sistem.addForce(kekang)

    integrator = mm.LangevinMiddleIntegrator(300 * unit.kelvin, 1 / unit.picosecond, 0.002 * unit.picoseconds)
    simulasi = app.Simulation(modeller.topology, sistem, integrator, p_obj, prop)
    simulasi.context.setPositions(modeller.positions)
    simulasi.minimizeEnergy(tolerance=10 * unit.kilojoule_per_mole, maxIterations=2000)

    if ps_dinamika > 0:
        n_langkah = int(ps_dinamika * 1000 / 2.0)      # langkah 2 fs
        log(f"Dinamika singkat {ps_dinamika:g} ps ({n_langkah} langkah)…")
        simulasi.context.setVelocitiesToTemperature(300 * unit.kelvin, 42)
        simulasi.step(n_langkah)
        simulasi.minimizeEnergy(tolerance=10 * unit.kilojoule_per_mole, maxIterations=500)

    keadaan = simulasi.context.getState(getPositions=True)
    pos_akhir = np.asarray(keadaan.getPositions(asNumpy=True).value_in_unit(unit.nanometer))
    rmsd = float(np.sqrt(np.mean(np.sum((pos_akhir[idx_pep] - pos_awal[idx_pep]) ** 2, axis=1))) * 10.0)

    tulis = _io.StringIO()
    app.PDBFile.writeFile(simulasi.topology, keadaan.getPositions(), tulis, keepIds=True)

    mmgbsa = None
    try:
        mmgbsa = MMGBSA(ff, modeller, info, plat).frame(pos_akhir)
        mmgbsa = {k: round(float(v), 2) for k, v in mmgbsa.items()}
    except Exception as e:
        catat.log.warning(f"MM/GBSA peptida gagal: {e}")

    return {"pdb": tulis.getvalue(), "rmsd": round(rmsd, 2), "mmgbsa": mmgbsa,
            "detik": round(time.time() - t0, 1), "platform": nama_plat}


def analisis_antarmuka(pdb_kompleks: str, rantai_peptida: str) -> Dict[str, Any]:
    """Metrik antarmuka peptida terhadap rantai reseptor, lewat `core/ppi.py`."""
    rantai = [c for c, _ in sekuens_dari_pdb(pdb_kompleks)]
    lawan = next((c for c in rantai if c != rantai_peptida), None)
    if lawan is None:
        return {"error": "Kompleks hanya memiliki satu rantai; antarmuka tidak dapat dihitung."}
    return ppi.skor_antarmuka(pdb_kompleks, rantai_a=lawan, rantai_b=rantai_peptida)


def _ca_rantai(pdb_teks: str, rantai: str) -> Tuple[List[str], np.ndarray]:
    """(kode residu satu huruf, koordinat Cα) satu rantai, berurut seperti di berkas."""
    from .konservasi import TIGA_KE_SATU

    huruf, titik = [], []
    for b in pdb_teks.splitlines():
        if b.startswith("ATOM") and b[12:16].strip() == "CA" and b[21] == rantai:
            huruf.append(TIGA_KE_SATU.get(b[17:20].strip(), "X"))
            titik.append([float(b[30:38]), float(b[38:46]), float(b[46:54])])
    return huruf, np.asarray(titik) if titik else np.zeros((0, 3))


def _pasangan_ca_berurut(pdb_a: str, pdb_b: str) -> Tuple[np.ndarray, np.ndarray, int]:
    """Pasangkan Cα dua struktur berdasarkan urutan sekuens, bukan nomor residu.

    Dipakai ketika penomoran residu berbeda: struktur kristal memakai penomoran aslinya (MDM2 pada
    1YCR mulai dari 25) sedangkan keluaran model menomori ulang dari 1. Pasangan dicari dengan
    menggeser sekuens prediksi di sepanjang sekuens acuan sampai sepenuhnya cocok.
    """
    pasangan_a, pasangan_b = [], []
    rantai_a = [c for c, _ in sekuens_dari_pdb(pdb_a)]
    rantai_b = [c for c, _ in sekuens_dari_pdb(pdb_b)]
    for ra, rb in zip(rantai_a, rantai_b):
        ha, xa = _ca_rantai(pdb_a, ra)
        hb, xb = _ca_rantai(pdb_b, rb)
        if len(ha) < 5 or len(hb) < 5:
            continue
        sa, sb = "".join(ha), "".join(hb)
        if len(sb) <= len(sa):
            i = sa.find(sb)
            if i >= 0:
                pasangan_a.append(xa[i:i + len(sb)])
                pasangan_b.append(xb)
        else:
            i = sb.find(sa)
            if i >= 0:
                pasangan_a.append(xa)
                pasangan_b.append(xb[i:i + len(sa)])
    if not pasangan_a:
        return np.zeros((0, 3)), np.zeros((0, 3)), 0
    A = np.vstack(pasangan_a)
    B = np.vstack(pasangan_b)
    return A, B, len(A)


def sejajarkan_ke_acuan(pdb_kompleks: str, pdb_acuan: str) -> Dict[str, Any]:
    """Sejajarkan kompleks prediksi ke kerangka koordinat struktur acuan lewat Cα reseptor.

    Boltz memprediksi di kerangka koordinatnya sendiri, sehingga RMSD terhadap struktur kristal
    tidak bermakna sebelum kedua struktur disuperposisikan: tanpa langkah ini angkanya puluhan
    angstrom. Jalur utama memakai `core/kofolding.sejajarkan_ke_reseptor`, yang memasangkan Cα
    menurut nomor residu. Bila penomorannya berbeda, pasangan dicari menurut urutan sekuens.

    Kembalikan {"pdb", "rmsd_ca_reseptor", "n_ca", "cara", "pesan"}; kegagalan memberi pdb kosong
    beserta sebabnya, bukan angka.
    """
    from .md import kabsch

    try:
        kompleks, _ligan, rmsd_rec, n_ca = kofolding.sejajarkan_ke_reseptor(pdb_kompleks, pdb_acuan)
        return {"pdb": kompleks, "rmsd_ca_reseptor": round(float(rmsd_rec), 2), "n_ca": int(n_ca),
                "cara": "nomor residu", "pesan": ""}
    except Exception as e:
        sebab = str(e)

    # Cadangan: penomoran residu tidak sepadan, pasangkan menurut urutan sekuens
    A, B, n = _pasangan_ca_berurut(pdb_acuan, pdb_kompleks)
    if n < 15:
        return {"pdb": "", "rmsd_ca_reseptor": None, "n_ca": n, "cara": "",
                "pesan": f"{sebab} Pencocokan berdasarkan urutan sekuens juga gagal ({n} Cα berpadanan)."}

    R, cp, cq = kabsch(B, A)        # pindahkan prediksi (B) ke kerangka acuan (A)
    sisa = (B - cp) @ R + cq
    rmsd_rec = float(np.sqrt(((sisa - A) ** 2).sum(1).mean()))

    keluar = []
    for b in pdb_kompleks.splitlines():
        if b.startswith(("ATOM", "HETATM")):
            xyz = np.array([float(b[30:38]), float(b[38:46]), float(b[46:54])])
            xyz = (xyz - cp) @ R + cq
            b = f"{b[:30]}{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}{b[54:]}"
        keluar.append(b)
    pdb_baru = chr(10).join(keluar) + chr(10)
    return {"pdb": pdb_baru, "rmsd_ca_reseptor": round(rmsd_rec, 2), "n_ca": n,
            "cara": "urutan sekuens", "pesan": ""}


def rmsd_ca(pdb_acuan: str, pdb_uji: str, rantai_acuan: str, rantai_uji: str) -> Optional[float]:
    """RMSD Cα dua rantai peptida sepanjang residu yang berpadanan, tanpa superposisi ulang.

    Kedua struktur HARUS sudah berada di kerangka koordinat yang sama; pakai `sejajarkan_ke_acuan`
    lebih dulu untuk keluaran Boltz, yang berada di kerangkanya sendiri. Tanpa itu angkanya puluhan
    angstrom dan tidak bermakna. Kembalikan None bila jumlah Cα tidak sama atau salah satu kosong,
    bukan 0,0.
    """
    def _ca(teks, rantai):
        keluar = []
        for b in teks.splitlines():
            if b.startswith("ATOM") and b[12:16].strip() == "CA" and b[21] == rantai:
                keluar.append([float(b[30:38]), float(b[38:46]), float(b[46:54])])
        return np.asarray(keluar)

    a, u = _ca(pdb_acuan, rantai_acuan), _ca(pdb_uji, rantai_uji)
    if len(a) == 0 or len(u) == 0 or len(a) != len(u):
        return None
    return round(float(np.sqrt(np.mean(np.sum((a - u) ** 2, axis=1)))), 2)


def analisis_peptida(folder_boltz, sekuens_peptida: str, ps_dinamika: float = 0.0,
                     murni: bool = True, lapor=None) -> HasilPeptida:
    """Baca keluaran Boltz-2, tentukan rantai peptida, murnikan, lalu nilai antarmukanya."""
    log = lapor or (lambda s: None)
    v = validasi_sekuens(sekuens_peptida)
    hasil = HasilPeptida(sekuens=v["sekuens"])
    if not v["sah"]:
        hasil.pesan = v["pesan"]
        return hasil

    try:
        keluaran = kofolding.baca_keluaran_boltz(Path(folder_boltz))
    except Exception as e:
        hasil.pesan = f"Gagal membaca keluaran Boltz: {e}"
        return hasil

    pdb_kompleks = keluaran.get("teks_pdb") or ""
    if not pdb_kompleks:
        hasil.pesan = "Keluaran Boltz tidak memuat struktur kompleks."
        return hasil

    hasil.pdb_kompleks = pdb_kompleks
    hasil.plddt = keluaran.get("complex_plddt")
    hasil.ptm = keluaran.get("ligand_iptm")
    hasil.rantai_peptida = tebak_rantai_peptida(pdb_kompleks, len(v["sekuens"]))

    pdb_dinilai = pdb_kompleks
    if murni:
        try:
            murni_hasil = murnikan(pdb_kompleks, hasil.rantai_peptida, ps_dinamika=ps_dinamika, lapor=log)
            hasil.pdb_kompleks_murni = murni_hasil["pdb"]
            hasil.rmsd_minimisasi = murni_hasil["rmsd"]
            hasil.mmgbsa = murni_hasil["mmgbsa"]
            hasil.rincian["pemurnian"] = {k: murni_hasil[k] for k in ("detik", "platform")}
            pdb_dinilai = murni_hasil["pdb"] or pdb_kompleks
        except Exception as e:
            catat.log.warning(f"Pemurnian peptida gagal: {e}")
            hasil.rincian["pemurnian_galat"] = str(e)

    hasil.antarmuka = analisis_antarmuka(pdb_dinilai, hasil.rantai_peptida)
    hasil.tersedia = True
    hasil.pesan = v.get("peringatan", "")
    return hasil
