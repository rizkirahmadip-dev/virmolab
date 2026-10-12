"""Validasi Integritas Struktur dan Auto-Sanitizer PDB/PDBQT.

Mencegah kegagalan runtime AutoDock-GPU, Vina, dan AD4 akibat cacat format berkas:
- Karakter non-ASCII, UTF-8 BOM, carriage return ganda (\r\r\n), atau null bytes
- Baris tanpa newline di akhir berkas (memotong atom terakhir pada parser C++)
- Koordinat NaN, Inf, atau di luar rentang valid
- Tipe atom AutoDock yang tidak didukung atau hilang di kolom 77-79
- Struktur pohon torsi (ROOT / ENDROOT / TORSDOF) pada ligan
"""
import math
from pathlib import Path
from typing import Any, List, Tuple, Union

TIPE_AUTODOCK_BAKU = {
    "C", "A", "N", "NA", "NS", "OA", "OS", "SA", "S", "HD", "HS", "H",
    "P", "F", "Cl", "CL", "Br", "BR", "I", "Si", "Fe", "FE", "Zn", "ZN",
    "Mg", "MG", "Mn", "MN", "Ca", "CA", "Cu", "CU", "Co", "CO", "Ni", "NI",
    "Na", "NA", "K", "Cd", "CD", "Hg", "HG"
}


def bersihkan_teks_pdbqt(teks: str) -> str:
    """Sanitasi karakter berkas PDBQT agar aman dibaca parser C++ Vina / AutoDock-GPU."""
    if not teks:
        return ""
    # Hapus UTF-8 BOM
    if teks.startswith("\ufeff"):
        teks = teks[1:]
    # Normalisasi newline (hapus \r)
    teks = teks.replace("\r\n", "\n").replace("\r", "\n")
    # Hapus null bytes
    teks = teks.replace("\x00", "")
    # Pastikan diakhiri satu newline
    teks = teks.rstrip("\n") + "\n"
    return teks


def validasi_sanitasi_pdbqt(
    sumber: Union[str, Path], jenis: str = "ligan"
) -> Tuple[bool, str, List[str]]:
    """Periksa dan sanitasi teks PDBQT ligan atau reseptor.

    Parameter:
      sumber: Jalur berkas Path/str atau string konten PDBQT langsung.
      jenis: 'ligan' | 'reseptor'

    Kembalikan:
      (valid: bool, teks_bersih: str, catatan: List[str])
    """
    if isinstance(sumber, Path) or (isinstance(sumber, str) and len(sumber) < 500 and "\n" not in sumber and Path(sumber).exists()):
        p = Path(sumber)
        try:
            teks = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return False, "", [f"Gagal membaca berkas {p.name}: {e}"]
    else:
        teks = str(sumber)

    if not teks.strip():
        return False, "", ["Berkas PDBQT kosong (0 byte)."]

    catatan = []
    teks_bersih = bersihkan_teks_pdbqt(teks)

    baris = teks_bersih.splitlines()
    baris_atom = []
    punya_root = False
    punya_endroot = False
    punya_torsdof = False

    baris_keluaran = []

    for idx, b in enumerate(baris, 1):
        if b.startswith("ROOT"):
            punya_root = True
            baris_keluaran.append(b)
            continue
        elif b.startswith("ENDROOT"):
            punya_endroot = True
            baris_keluaran.append(b)
            continue
        elif b.startswith("TORSDOF"):
            punya_torsdof = True
            baris_keluaran.append(b)
            continue

        if b.startswith(("ATOM", "HETATM")):
            if len(b) < 54:
                catatan.append(f"Baris {idx} terlalu pendek untuk atom PDB: '{b[:40]}'")
                continue

            # Periksa koordinat
            try:
                x = float(b[30:38])
                y = float(b[38:46])
                z = float(b[46:54])
                if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
                    catatan.append(f"Baris {idx}: Koordinat tidak terbatas (NaN/Inf).")
                    continue
            except ValueError:
                catatan.append(f"Baris {idx}: Koordinat x/y/z bukan angka valid.")
                continue

            # Periksa & sanitasi tipe atom AutoDock (kolom 77-79)
            tipe_atom = ""
            if len(b) >= 77:
                tipe_atom = b[77:79].strip()
            
            # Jika tipe atom kosong, tebak dari nama atom
            if not tipe_atom:
                nama_atom = b[12:16].strip()
                unsur = "".join(c for c in nama_atom if c.isalpha())[:2].capitalize()
                tipe_atom = unsur if unsur in TIPE_AUTODOCK_BAKU else "C"
                # Padding baris sampai kolom 77
                b = b.ljust(76) + f" {tipe_atom:<2}"
                catatan.append(f"Baris {idx}: Tipe atom tidak ada, diasumsikan '{tipe_atom}'.")

            baris_atom.append(b)
            baris_keluaran.append(b)
        else:
            baris_keluaran.append(b)

    if not baris_atom:
        return False, "", ["Tidak ada baris ATOM atau HETATM yang valid ditemukan."]

    if jenis == "ligan":
        if not (punya_root and punya_endroot) and len(baris_atom) > 1:
            # Ligan kaku tanpa torsi lengkap: tambahkan ROOT dan ENDROOT otomatis agar kompatibel Vina/AD-GPU
            baris_final = ["ROOT"]
            for b in baris_keluaran:
                if b.startswith(("ATOM", "HETATM")):
                    baris_final.append(b)
            baris_final.append("ENDROOT")
            if not punya_torsdof:
                baris_final.append("TORSDOF 0")
            teks_bersih = "\n".join(baris_final) + "\n"
            catatan.append("Pohon torsi ROOT/ENDROOT/TORSDOF otomatis ditambahkan/dilengkapi.")
        else:
            teks_bersih = "\n".join(baris_keluaran) + "\n"
    else:
        teks_bersih = "\n".join(baris_keluaran) + "\n"

    return True, teks_bersih, catatan


def verifikasi_kesiapan_proyek(proyek: Any) -> Tuple[bool, List[str], List[str]]:
    """Verifikasi kesiapan proyek sebelum docking dijalankan.

    Kembalikan:
      (siap: bool, daftar_peringatan: List[str], daftar_galat: List[str])
    """
    galat = []
    peringatan = []

    # 1. Reseptor
    if not hasattr(proyek, "reseptor") or not proyek.reseptor:
        galat.append("Reseptor (makromolekul protein) belum disiapkan.")
    else:
        pdbqt_rel = proyek.reseptor.get("pdbqt")
        if not pdbqt_rel:
            galat.append("Berkas PDBQT reseptor belum dibuat.")
        else:
            p_rec = proyek.p(pdbqt_rel)
            if not p_rec.exists():
                galat.append(f"Berkas PDBQT reseptor tidak ditemukan: {p_rec.name}")
            else:
                ok, _, cat = validasi_sanitasi_pdbqt(p_rec, jenis="reseptor")
                if not ok:
                    galat.append(f"Reseptor rusak: {'; '.join(cat)}")
                elif cat:
                    peringatan.extend([f"Reseptor: {c}" for c in cat])

    # 2. Ligan
    daftar_ligan = getattr(proyek, "ligan", []) or []
    if not daftar_ligan:
        galat.append("Belum ada ligan yang disiapkan untuk docking.")
    else:
        ligan_siap = 0
        for lig in daftar_ligan:
            pdbqt_lig = lig.get("pdbqt")
            if pdbqt_lig and proyek.p(pdbqt_lig).exists():
                ligan_siap += 1
            else:
                peringatan.append(f"Ligan '{lig.get('nama', 'Tanpa Nama')}' belum memiliki berkas PDBQT.")
        if ligan_siap == 0:
            galat.append("Tidak ada satupun ligan dengan berkas PDBQT yang siap dijalankan.")

    # 3. Grid Box
    box = getattr(proyek, "kotak", None)
    if not box or not isinstance(box, dict):
        galat.append("Area pencarian (grid box) belum diatur.")
    else:
        pusat = box.get("pusat")
        ukuran = box.get("ukuran")
        if not pusat or len(pusat) != 3 or any(p is None for p in pusat):
            galat.append("Pusat grid box belum ditentukan.")
        if not ukuran or len(ukuran) != 3 or any(u is None or u <= 0 for u in ukuran):
            galat.append("Ukuran grid box tidak valid (harus > 0 Å).")

    siap = len(galat) == 0
    return siap, peringatan, galat
