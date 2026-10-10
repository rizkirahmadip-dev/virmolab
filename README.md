# VirmoDock

Aplikasi desktop Windows untuk *molecular docking* — gratis dan open-source (GPL-3.0-or-later).
Pengganti alur AutoDockTools: impor protein/ligan, preparasi, grid box, docking, analisis interaksi,
dan ekspor siap publikasi dalam satu jendela berbahasa Indonesia.

- **Mesin**: AutoDock-GPU (OpenCL, native Windows — NVIDIA/AMD/Intel, tanpa WSL), AutoDock Vina 1.2.7,
  AutoDock 4.2.6. Fallback otomatis ke Vina bila GPU/OpenCL tidak tersedia.
- **Preparasi**: reseptor (gemmi, Meeko, PROPKA/PDB2PQR, residu fleksibel), ligan (RDKit + Meeko), unduh langsung
  dari RCSB PDB, AlphaFold DB (pLDDT), PubChem, ChEMBL, COCONUT.
- **Antrean job**: banyak ligan, progres & ETA, jeda/lanjut, dilanjutkan setelah aplikasi ditutup.
- **Analisis**: ikatan H, hidrofobik, π–π, π–kation, jembatan garam, halogen, logam; tampilan 3D (3Dmol.js)
  dan diagram 2D; validasi redocking (RMSD); bandingkan 2–4 ligan; peta interaksi.
- **Ekspor**: gambar 3D/2D ber-DPI (PNG/TIFF/SVG/PDF), kompleks PDB, SDF, CSV, XLSX, laporan PDF.
- **Distribusi**: installer per-pengguna tanpa admin, versi portable, pindah laptop (`.vmdbackup`).
- **MD & MM/GBSA**: OpenMM (ff14SB + OpenFF Sage/NAGL), pelarut implisit OBC2 atau air eksplisit, dengan
  saran tingkat sesuai kemampuan laptop, jeda/lanjut, RMSD/RMSF, interaksi persisten.
- **Baris perintah**: `VirmoDock-cli.exe` untuk docking batch dan skrip (lihat di bawah).

Status: **0.9.4 pra-rilis** (lihat CHANGELOG.md) — menunggu uji relawan di GPU AMD/Intel dan komputer tanpa GPU.

## Unduh

Installer dan versi portable tersedia di halaman *Releases*. Cek integritas dengan `SHA256SUMS`.
Setelah dipasang, jalankan **Tools › Uji mandiri komponen** untuk memastikan semua mesin berfungsi.

Panduan lengkap: folder [`docs/`](docs/) (juga Help › Panduan, F1) dan tutorial PDF di menu Help.

## Baris perintah

`VirmoDock-cli.exe` ada di folder instalasi (dari kode sumber: `python -m virmodock.cli`). Contoh:

```bat
VirmoDock-cli dock -r 1HSG -l kandidat.smi --acuan auto -o hasil_1hsg
VirmoDock-cli dock -r AF-P00918 -l ligan\ --kantong 1 --mesin vina --exhaustiveness 32 -o hasil_ca2
VirmoDock-cli reseptor 1HSG -o rec.pdbqt --protonasi propka --flex A:25,B:25
VirmoDock-cli kantong AF-P00918
VirmoDock-cli mmgbsa -r hasil_1hsg -o mmgbsa_1hsg --md --ns 2
```

`dock` menyiapkan reseptor (berkas PDB/CIF, kode PDB, `AF-<UniProt>`, atau PDBQT siap) dan ligan
(SDF/MOL2/PDB/SMI/PDBQT, folder, atau SMILES) bila perlu, menentukan grid box (`--pusat`, `--acuan`
berkas/`auto`, atau `--kantong N` P2Rank), lalu menulis pose, `ringkasan.csv`, `metode.txt`, dan `log.txt`.
`VirmoDock-cli <perintah> -h` menampilkan semua opsi.

## Menjalankan dari kode sumber

Butuh Windows 10/11 x64 dan Python 3.14.

```bat
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m virmodock
```

Biner mesin docking ada di `vendor/bin/` (AutoDock-GPU dibangun sendiri dari `vendor/adgpu_src/`,
proyek Visual Studio dengan OpenCL; Vina, AutoGrid4, AutoDock4, Open Babel dari rilis resminya).

Deteksi kantong memakai P2Rank + Java yang **tidak ikut repo** (±262 MB). Pasang manual:

- `vendor/bin/p2rank/` — P2Rank 2.5.1 (https://github.com/rdk/p2rank/releases); cukup `bin/`, `config/`,
  dan model `default`, `alphafold`, `_score_transform` (data uji & model lain boleh dibuang).
- `vendor/bin/jre/` — Eclipse Temurin JRE 21 (Windows x64, zip) dari https://adoptium.net, diekstrak
  sehingga ada `vendor/bin/jre/bin/java.exe`.

Uji mandiri (`python -m virmodock --uji-mandiri hasil.json`) memeriksa keduanya.

Modul MD & MM/GBSA memakai OpenMM (PyPI, ada di `requirements.txt`) dan tumpukan OpenFF yang **tidak ada di
PyPI** untuk Windows. Pasang dari arsip rilis GitHub tanpa dependensi (dependensi PyPI-nya sudah ada di
`requirements.txt`):

```bat
set G=https://github.com/openforcefield
set SETUPTOOLS_SCM_PRETEND_VERSION_FOR_OPENFF_UTILITIES=0.1.18
set SETUPTOOLS_SCM_PRETEND_VERSION_FOR_OPENFF_UNITS=0.4.0
set SETUPTOOLS_SCM_PRETEND_VERSION_FOR_OPENFORCEFIELDS=2026.09.0
set SETUPTOOLS_SCM_PRETEND_VERSION_FOR_OPENFF_INTERCHANGE=0.5.5
set SETUPTOOLS_SCM_PRETEND_VERSION_FOR_OPENFF_TOOLKIT=0.19.0
set SETUPTOOLS_SCM_PRETEND_VERSION_FOR_OPENFF_NAGL=0.6.1
set SETUPTOOLS_SCM_PRETEND_VERSION_FOR_OPENFF_NAGL_MODELS=2026.09.0
.venv\Scripts\python.exe -m pip install --no-deps "openff-utilities @ %G%/openff-utilities/archive/refs/tags/v0.1.18.tar.gz" "openff-units @ %G%/openff-units/archive/refs/tags/0.4.0.tar.gz" "openforcefields @ %G%/openff-forcefields/archive/refs/tags/2026.09.0.tar.gz" "openff-interchange @ %G%/openff-interchange/archive/refs/tags/v0.5.5.tar.gz" "openff-toolkit @ %G%/openff-toolkit/archive/refs/tags/0.19.0.tar.gz" "openff-nagl @ %G%/openff-nagl/archive/refs/tags/v0.6.1.tar.gz" "openff-nagl-models @ %G%/openff-nagl-models/archive/refs/tags/v2026.09.0.tar.gz"
```

Variabel `SETUPTOOLS_SCM_PRETEND_VERSION_*` perlu karena arsip GitHub tidak membawa riwayat git (tanpanya
versi terbaca "unavailable"). `openff-amber-ff-ports` tidak diperlukan.

Editor struktur Ketcher juga **tidak ikut repo** (±30 MB): unduh `ketcher-standalone-3.18.0.zip` dari
https://github.com/epam/ketcher/releases (SHA-256 `484e7f10…a3e7e`) lalu ekstrak ke `vendor/ketcher/` cukup
`index.html`, `favicon*`, `static/css/main.*.css`, dan `static/js/main.*.js`, `114.*`, `127.*`, `609.*` (chunk).

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
