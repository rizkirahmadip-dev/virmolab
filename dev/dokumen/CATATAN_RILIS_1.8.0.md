# Catatan rilis 1.8.0 (draf untuk halaman GitHub Release)

Teks di bawah siap disalin ke halaman rilis. Bagian Indonesia dulu, lalu Inggris. Ganti `<SHA>` dengan sidik
jari dari `SHA256SUMS-1.8.0.txt` sebelum diterbitkan, dan tambahkan badge DOI setelah Zenodo menerbitkannya.

---

## VirmoLab 1.8.0 — rilis publik pertama

VirmoLab adalah aplikasi desktop Windows untuk *molecular docking*: impor protein dan ligan, preparasi,
grid box, docking, analisis interaksi, uji statistik, dan ekspor siap publikasi dalam satu jendela berbahasa
Indonesia atau Inggris. Gratis dan sumber terbuka (GPL-3.0-or-later). Tidak perlu Python, WSL, MGLTools,
atau baris perintah.

### Yang baru di 1.8.0

- **Alat › Pasang alat lanjutan (WSL)…** — Uni-Dock, OpenFE, GNINA, dan Boltz-2 hanya tersedia untuk Linux,
  dan sekarang dipasang dari dalam aplikasi. Dialognya memeriksa prasyarat (WSL 2, GPU NVIDIA, ruang disk,
  memori, alat dasar, internet), menawarkan perbaikan untuk yang belum terpenuhi, menampilkan kemajuan per
  langkah, dan dapat dihentikan atau dilanjutkan tanpa mengulang unduhan. Fitur yang membutuhkannya kini
  menawarkan "Pasang sekarang…" alih-alih pesan buntu.
- **Perbaikan dari pemasangan sungguhan di distro Linux bersih**: micromamba tetap terpasang pada Ubuntu
  tanpa `bzip2`; bobot Boltz-2 diunduh dengan pemeriksaan ukuran, pengulangan, dan tahan putus; arsip paket
  (± 4,5 GB) dihapus setelah pemasangan berhasil; batas memori WSL yang terlalu kecil untuk Boltz-2 kini
  terdeteksi sebelum memasang, bukan berakhir dengan proses yang dihentikan sistem tanpa penjelasan.
- Padding label keterangan yang hilang saat gaya berganti (tujuh dialog) dan pemeriksaan status alat WSL yang
  berjalan berulang kali saat memilih pose sudah diperbaiki.
- Dokumentasi, pernyataan privasi, catatan lisensi, dan metadata sitasi disiapkan untuk rilis publik.

Daftar lengkap: [CHANGELOG.md](../CHANGELOG.md).

### Unduh dan periksa

| Berkas | Untuk |
|---|---|
| `VirmoLab-Setup-1.8.0.exe` | pemasangan biasa (per pengguna, tanpa hak administrator) |
| `VirmoLab-Portable-1.8.0.zip` | dijalankan dari folder mana saja |
| `SHA256SUMS-1.8.0.txt` | sidik jari kedua berkas di atas |

```powershell
Get-FileHash .\VirmoLab-Setup-1.8.0.exe -Algorithm SHA256
```

Installer **belum ditandatangani sertifikat berbayar**, jadi SmartScreen menampilkan "Windows protected your
PC" — klik *More info › Run anyway* setelah sidik jarinya cocok. Sertifikat sedang diurus dan akan dipakai
mulai rilis berikutnya.

### Yang perlu diketahui sebelum memakai

- **Diuji di satu laptop pengembang** (Windows 10 64-bit, RTX 3060 Laptop, 16 GB RAM) dan satu distro WSL
  bersih untuk pemasang alat lanjutan. Belum ada laporan dari laptop lain, terutama tanpa GPU NVIDIA atau
  dengan RAM 8 GB. Laporan pengalaman Anda sangat membantu —
  [buka issue](https://github.com/rizkirahmadip-dev/virmolab/issues).
- **Pemutakhiran dari pemasangan 1.7.0 lama belum teruji** (1.7.0 tidak pernah diedarkan ke publik).
  Installer membersihkan berkas program versi lama sebelum menyalin; proyek dan pengaturan tidak disentuh.
  Bila ragu, copot versi lama lebih dulu — proyek di `Documents\VirmoLab` tetap ada.
- Hasil docking adalah prediksi komputasi, bukan bukti aktivitas biologis.
- VirmoLab tidak mengirim proyek, struktur, atau hasil Anda ke mana pun. Rinciannya di bagian *Privasi* pada
  README dan Bantuan › Panduan.

### Setelah memasang

1. **Alat › Uji mandiri komponen…** (58 butir) untuk memastikan semua mesin berfungsi.
2. **Bantuan › Tutorial docking (PDF)** — docking pertama dengan 1HSG.
3. Mengutip VirmoLab: tombol *Cite this repository* di GitHub, atau berkas `CITATION.cff`.

---

## VirmoLab 1.8.0 — first public release (English)

VirmoLab is a Windows desktop application for molecular docking: import proteins and ligands, prepare them,
set the grid box, dock, analyse interactions, run statistics, and export publication-ready output — all in
one window, in Indonesian or English. Free and open source (GPL-3.0-or-later). No Python, WSL, MGLTools, or
command line needed.

**New in 1.8.0.** Uni-Dock, OpenFE, GNINA, and Boltz-2 are Linux-only tools that now install from inside the
app (**Tools › Install advanced tools (WSL)**): prerequisites are checked, failures come with a fix button,
progress is shown per step, and an interrupted install resumes without re-downloading. Features that need
those tools now offer to install them instead of showing a dead end. Installing into a clean Linux distro
surfaced and fixed four real bugs (missing `bzip2`, Boltz weight downloads, leftover package archives,
and a WSL memory limit too small for Boltz-2). Documentation, a privacy statement, license records, and
citation metadata were prepared for public release.

**Download and verify.** Take `VirmoLab-Setup-1.8.0.exe` (per-user install, no administrator rights) or
`VirmoLab-Portable-1.8.0.zip`, then check it against `SHA256SUMS-1.8.0.txt`
(`Get-FileHash .\VirmoLab-Setup-1.8.0.exe -Algorithm SHA256`). The installer is **not signed with a paid
certificate** yet, so SmartScreen will warn — choose *More info › Run anyway* once the hash matches.

**Please note.** This build was tested on one developer laptop (Windows 10 64-bit, RTX 3060 Laptop, 16 GB RAM)
and one clean WSL distro for the tool installer; reports from other machines are very welcome via
[Issues](https://github.com/rizkirahmadip-dev/virmolab/issues). Upgrading over an old 1.7.0 install is untested
(1.7.0 was never distributed publicly); the installer clears the previous program files before copying, and
projects and settings are left untouched. Docking results are computational predictions,
not evidence of biological activity. VirmoLab sends no project data anywhere (see *Privasi* in the README).
