# VirmoDock

Aplikasi desktop Windows untuk *molecular docking* — gratis dan open-source (GPL-3.0-or-later).
Pengganti alur AutoDockTools: impor protein/ligan, preparasi, grid box, docking, analisis interaksi,
dan ekspor siap publikasi dalam satu jendela berbahasa Indonesia.

- **Mesin**: AutoDock-GPU (OpenCL, native Windows — NVIDIA/AMD/Intel, tanpa WSL), AutoDock Vina 1.2.7,
  AutoDock 4.2.6. Fallback otomatis ke Vina bila GPU/OpenCL tidak tersedia.
- **Preparasi**: reseptor (gemmi, Open Babel), ligan (RDKit + Meeko), unduh langsung dari RCSB PDB & PubChem.
- **Antrean job**: banyak ligan, progres & ETA, jeda/lanjut, dilanjutkan setelah aplikasi ditutup.
- **Analisis**: ikatan H, hidrofobik, π–π, π–kation, jembatan garam, halogen, logam; tampilan 3D (3Dmol.js)
  dan diagram 2D; validasi redocking (RMSD); bandingkan 2–4 ligan; peta interaksi.
- **Ekspor**: gambar 3D/2D ber-DPI (PNG/TIFF/SVG/PDF), kompleks PDB, SDF, CSV, XLSX, laporan PDF.
- **Distribusi**: installer per-pengguna tanpa admin, versi portable, pindah laptop (`.vmdbackup`).

Status: **0.9.0 pra-rilis** — menunggu uji relawan di GPU AMD/Intel dan komputer tanpa GPU.

## Unduh

Installer dan versi portable tersedia di halaman *Releases*. Cek integritas dengan `SHA256SUMS`.
Setelah dipasang, jalankan **Tools › Uji mandiri komponen** untuk memastikan semua mesin berfungsi.

Panduan lengkap: folder [`docs/`](docs/) (juga Help › Panduan, F1) dan tutorial PDF di menu Help.

## Menjalankan dari kode sumber

Butuh Windows 10/11 x64 dan Python 3.14.

```bat
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m virmodock
```

Biner mesin docking ada di `vendor/bin/` (AutoDock-GPU dibangun sendiri dari `vendor/adgpu_src/`,
proyek Visual Studio dengan OpenCL; Vina, AutoGrid4, AutoDock4, Open Babel dari rilis resminya).

## Membuat rilis

1. Pasang [Inno Setup 6](https://jrsoftware.org/isinfo.php) ke `vendor/innosetup/`.
2. Jalankan:

```bat
.venv\Scripts\python.exe build_tools\rilis.py
```

Urutannya: dokumentasi → PyInstaller → uji mandiri (gagal = berhenti) → installer → zip portable →
SHA-256, hasil di `rilis/`.

## Lisensi & mengutip

VirmoDock: GPL-3.0-or-later ([`LICENSE`](LICENSE)). Komponen pihak ketiga dan tawaran kode sumbernya:
[`LISENSI_PIHAK_KETIGA.txt`](LISENSI_PIHAK_KETIGA.txt) dan folder [`licenses/`](licenses/).
Bila memakai VirmoDock dalam publikasi, kutip juga mesin dan pustaka yang dipakai (daftar sitasi
ada di Help › Lisensi & cara mengutip dan di laporan PDF).

© 2026 apt. Rizki Rahmadi Pratama, M. Farm
