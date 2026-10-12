"""Generator Skrip Publikasi PyMOL (.pml) & UCSF ChimeraX (.cxc).

Menghasilkan skrip visualisasi otomatis dengan standar tata letak jurnal ilmiah internasional
(Nature / Journal of Medicinal Chemistry):
  - Kartun protein resolusi tinggi dengan warna tema harmonis
  - Residu kantong aktif dalam bentuk stick berlabel
  - Ligan penambatan dalam gaya stick dengan pewarnaan atom kontras
  - Garis putus-putus ikatan hidrogen dan kontak kunci
  - Permukaan kantong transparan (solvent-accessible pocket surface)
  - Pengaturan ray-tracing kamera resolusi tinggi 300 DPI siap cetak
"""
from typing import Dict, List, Optional
from pathlib import Path


def buat_skrip_pymol(
    jalur_reseptor: str,
    jalur_ligan: str,
    residu_kunci: Optional[List[str]] = None,
    nama_output: str = "figur_docking",
) -> str:
    """Buat skrip PyMOL (.pml) siap jalan sekali klik."""
    p_rec = Path(jalur_reseptor).as_posix()
    p_lig = Path(jalur_ligan).as_posix()

    skrip = f"""# ==============================================================================
# Skrip Visualisasi Publikasi PyMOL - Dihasilkan oleh VirmoDock
# Buka di PyMOL: File -> Run Script -> pilih berkas ini, atau jalankan via terminal:
# pymol {nama_output}.pml
# ==============================================================================

# 1. Bersihkan sesi dan muat struktur
reinitialize
load {p_rec}, reseptor
load {p_lig}, ligan

# 2. Pengaturan Tampilan & Warna Jurnal (Nature / JMC Style)
bg_color white
set ray_shadows, 1
set ray_opaque_background, 1
set antialias, 2
set depth_cue, 1
set fog_start, 0.45

# 3. Tampilan Protein Reseptor
hide everything, reseptor
show cartoon, reseptor
color slate, reseptor
set cartoon_transparency, 0.15
set cartoon_fancy_helices, 1
set cartoon_highlight_color, grey90

# 4. Tampilan Ligan Penambatan
hide everything, ligan
show sticks, ligan
set stick_radius, 0.28, ligan
# Karbon ligan hijau mint agar kontras tajam dengan protein
color lightgreen, ligan and elem C
color red, ligan and elem O
color blue, ligan and elem N
color yellow, ligan and elem S
color orange, ligan and elem P
color forest, ligan and elem Cl
color smudge, ligan and elem F

# 5. Kantong Pengikatan & Residu Sisi Aktif (dalam 4.5 Å dari ligan)
select kantong, byres (reseptor within 4.5 of ligan)
show sticks, kantong
color grey80, kantong and elem C
set stick_radius, 0.20, kantong

# 6. Permukaan Rongga Kantong Transparan
show surface, kantong
set transparency, 0.70, kantong
set surface_color, grey90, kantong

# 7. Deteksi & Garis Ikatan Hidrogen Antar-Molekul
distance ikatan_h, (ligan and (elem O,N)), (kantong and (elem O,N)), 3.5, mode=2
color cyan, ikatan_h
set dash_radius, 0.08, ikatan_h
set dash_gap, 0.3, ikatan_h
set dash_length, 0.15, ikatan_h
hide labels, ikatan_h

# 8. Label Residu Interaksi Kunci
"""
    if residu_kunci:
        for res in residu_kunci:
            parts = res.split()
            if len(parts) >= 2:
                r_num = "".join(c for c in parts[1] if c.isdigit())
                rantai = parts[2].strip("()") if len(parts) > 2 else ""
                if r_num:
                    pilih = f"reseptor and resi {r_num} and name CA"
                    if rantai:
                        pilih += f" and chain {rantai}"
                    skrip += f"label ({pilih}), '{res}'\n"
        skrip += "set label_size, 14\nset label_color, black\nset label_font_id, 7\n"

    skrip += f"""
# 9. Pusatkan Kamera dan Ray-Trace Resolusi Tinggi (300 DPI)
orient ligan
zoom ligan, 6.0
set ray_trace_mode, 0
ray 2400, 1800
png {nama_output}.png, dpi=300
print("Visualisasi docking selesai! Berkas gambar tersimpan di {nama_output}.png")
"""
    return skrip.strip()


def buat_skrip_chimerax(
    jalur_reseptor: str,
    jalur_ligan: str,
    residu_kunci: Optional[List[str]] = None,
    nama_output: str = "figur_docking",
) -> str:
    """Buat skrip UCSF ChimeraX (.cxc) siap jalan sekali klik."""
    p_rec = Path(jalur_reseptor).as_posix()
    p_lig = Path(jalur_ligan).as_posix()

    skrip = f"""# ==============================================================================
# Skrip Visualisasi Publikasi UCSF ChimeraX - Dihasilkan oleh VirmoDock
# Buka di ChimeraX: File -> Open -> pilih berkas ini, atau jalankan di Command line
# ==============================================================================

# 1. Bersihkan dan buka model
close session
open "{p_rec}"
open "{p_lig}"

# 2. Pengaturan Latar Belakang & Pencahayaan Publikasi
set bgColor white
lighting soft
graphics quality 3

# 3. Representasi Reseptor (#1) dan Ligan (#2)
hide #1 atoms
show #1 cartoons
color #1 #64748b

# Ligan dalam gaya stick tebal
show #2
style #2 stick
color #2 & C #10b981
color #2 & O red
color #2 & N blue
color #2 & S yellow

# 4. Sisi Aktif Kantong (residu reseptor dalam 4.5 A dari ligan)
select zone #2 4.5 residues true & #1
name kantong sel
show kantong atoms
style kantong stick
color kantong & C gray(150)
color kantong & O red
color kantong & N blue

# 5. Permukaan Kantong Transparan
surface kantong
transparency kantong 70 surfaces

# 6. Ikatan Hidrogen Antar-Molekul
hbonds #2 restrict #1 reveal false makePseudobonds true color #06b6d4 radius 0.08 dashes 6

# 7. Orientasi & Simpan Snapshot Resolusi Tinggi
view #2
zoom 0.8
save "{nama_output}_chimerax.png" width 2400 height 1800 supersample 3
"""
    return skrip.strip()


def simpan_skrip_publikasi(
    folder_tujuan: str,
    nama_berkas_dasar: str,
    jalur_reseptor: str,
    jalur_ligan: str,
    residu_kunci: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Tulis berkas skrip .pml dan .cxc ke folder tujuan."""
    f = Path(folder_tujuan)
    f.mkdir(parents=True, exist_ok=True)

    jalur_pml = f / f"{nama_berkas_dasar}.pml"
    jalur_cxc = f / f"{nama_berkas_dasar}.cxc"

    teks_pml = buat_skrip_pymol(jalur_reseptor, jalur_ligan, residu_kunci, nama_berkas_dasar)
    teks_cxc = buat_skrip_chimerax(jalur_reseptor, jalur_ligan, residu_kunci, nama_berkas_dasar)

    jalur_pml.write_text(teks_pml, encoding="utf-8")
    jalur_cxc.write_text(teks_cxc, encoding="utf-8")

    return {
        "pymol": str(jalur_pml),
        "chimerax": str(jalur_cxc),
    }
