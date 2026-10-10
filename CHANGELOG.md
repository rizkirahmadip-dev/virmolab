# Catatan perubahan VirmoDock

Format: setiap versi berisi **Baru**, **Diperbaiki**, dan **Diubah**. Versi 0.x adalah pra-rilis.

## [0.9.4] — 9 Oktober 2026

### Baru
- **MD & MM/GBSA** (Analisis › MD & MM/GBSA…) dengan OpenMM: protein Amber ff14SB, ligan OpenFF Sage 2.3 dengan muatan parsial OpenFF NAGL (setara AM1-BCC), ion logam Li/Merz. Tiga tingkat sesuai rencana A8a:
  - **Ringan** — minimisasi kompleks + MM/GBSA satu titik (menit, semua laptop);
  - **Sedang** — MD pelarut implisit OBC2 + RMSD/RMSF + MM/GBSA rata-rata;
  - **Lengkap** — MD air eksplisit TIP3P/PME + MM/GBSA banyak frame.
- **Penilaian kemampuan laptop otomatis**: saat dialog pertama dibuka, kecepatan diukur pada kompleks Anda sendiri (implisit & eksplisit, disimpan per perangkat) → perkiraan waktu dan status *Disarankan / Bisa (lama) / Tidak disarankan*; peringatan bila laptop memakai baterai.
- **Jeda & lanjut**: checkpoint tiap ±5 menit; MD bisa dijeda dan dilanjutkan, juga setelah aplikasi ditutup (menutup VirmoDock saat MD berjalan otomatis menjeda dengan checkpoint).
- Hasil: ΔG MM/GBSA (vdW, elektrostatik, GB, SA) ± SD, grafik RMSD/RMSF/MM-GBSA per waktu (SVG/PDF/PNG/TIFF), **interaksi persisten** sepanjang trajektori, berkas kompleks terminimisasi (PDB) dan trajektori zat terlarut (DCD) untuk PyMOL/VMD.
- Kolom **MM/GBSA** di tabel Hasil, variabel MM/GBSA di Statistik, kolom di ekspor CSV/XLSX, serta bagian MM/GBSA, kalimat metode, dan sitasi (OpenMM 8, ff14SB, Sage, OpenFF, OBC, MM/GBSA) di laporan.
- Pose dari docking **residu fleksibel** dipakai lengkap: rantai samping diposisikan seperti di pose.
- Baris perintah: `VirmoDock-cli mmgbsa` (minimisasi, atau `--md` dengan `--pelarut implisit|eksplisit`) dari folder hasil `dock` atau pose SDF → `mmgbsa.csv`; `dock` kini juga menyimpan reseptor ber-H dengan keadaan protonasi docking.

### Diubah
- Uji mandiri kini 25 komponen (+ MD & MM/GBSA OpenMM/OpenFF).
- Dialog Tentang mencantumkan komponen MD dan pemberitahuan hak cipta Hilbert Curve (Rice University) yang diwajibkan lisensi OpenMM.

## [0.9.3] — 9 Oktober 2026

### Baru
- **Protein dari AlphaFold DB** (Siapkan › Protein dari AlphaFold DB…, atau tab *AlphaFold DB* di dialog impor): cari kode UniProt atau nama protein/gen (UniProt, saring organisme), unduh model prediksi terbaru. Protein diwarnai menurut **pLDDT** (pita resmi AlphaFold; juga pilihan warna *pLDDT* di panel Tampilan), ringkasan pLDDT di Properti dan Pesan, ujung N/C tak beraturan (pLDDT < 50) dipangkas otomatis (bisa diatur/dimatikan).
- **Peringatan pLDDT di grid box**: bila residu di area docking model AlphaFold ber-pLDDT rendah, VirmoDock mengingatkan bahwa pose dan ΔG kurang andal.
- **P2Rank untuk model AlphaFold** memakai konfigurasi resmi `alphafold` (tanpa fitur B-factor, yang di model AlphaFold berisi pLDDT).
- **Residu fleksibel** (Siapkan › Residu fleksibel…, atau *Atur…* di langkah Jalankan): pilih 1–8 rantai samping kantong (calon diurutkan menurut jarak ke ligan asli) yang boleh berotasi selama docking — AutoDock-GPU (`--flexres`) dan Vina (`--flex`). Rantai samping tiap pose tampil sebagai objek tersendiri, dan analisis interaksi, PoseBusters, serta laporan memakai posisi rantai samping pada pose itu.
- **Baris perintah `VirmoDock-cli.exe`** (di folder instalasi): `info`, `uji`, `reseptor`, `ligan`, `kantong`, `alphafold`, dan `dock` — satu perintah dari kode PDB/AF-UniProt/berkas sampai `ringkasan.csv` (ΔG, Ki, LE, interaksi, residu kontak) dan `metode.txt` (parameter lengkap + perintah yang bisa diulang) untuk skrip, batch, dan reproduksibilitas.
- Laporan mencantumkan sumber model AlphaFold (entri, versi, pLDDT, residu dipangkas) dan residu fleksibel.

### Diperbaiki
- Peta grid AutoGrid tidak lagi dipakai ulang setelah reseptor berubah dengan tipe atom yang sama (hash reseptor kini ikut diperiksa).

### Diubah
- Uji mandiri kini 24 komponen (+ residu fleksibel, baris perintah).

## [0.9.2] — 9 Oktober 2026

### Baru
- **Wizard preparasi reseptor 4 langkah** (Periksa struktur → Pembersihan → Protonasi & hidrogen → Ringkasan) dengan **pemeriksa kualitas protein**: resolusi, celah rantai, atom berat hilang, konformasi alternatif, residu non-standar, ligan & ion logam.
- **Protonasi berbasis pKa (PROPKA 3 + PDB2PQR)** pada pH pilihan: His → HID/HIE/HIP, Asp/Glu terkubur bisa netral, optimasi jaringan ikatan hidrogen (rotasi OH/SH/NH₃⁺, flip His/Asn/Gln), atom berat yang hilang dilengkapi (residu tidak lagi dibuang). His pengikat ion logam diberi tautomer sesuai geometri koordinasi. Tabel pKa disimpan di `reseptor/pka.csv`.
- **Peta sidik jari interaksi ala ProLIF** (Statistik › Peta sidik jari interaksi): ligan × residu × jenis interaksi + baris frekuensi.
- **Kemiripan, ruang kimia, farmakofor** (Analisis): Tanimoto ECFP4/FCFP4/MACCS/pasangan atom/farmakofor 2D, klaster Butina, peta ruang kimia (MDS/PCA), cari ligan mirip (termasuk SMILES acuan), **farmakofor 3D pose aktif** (tombol P) dan **farmakofor bersama** pose teratas (+ skrip PyMOL).
- **ChEMBL**: cari target dari ID PDB/UniProt/nama, ambil aktivitas (pChEMBL), impor senyawa aktif sebagai ligan, dan **korelasi ΔG docking vs pChEMBL**; pChEMBL tersedia sebagai variabel di tab Statistik.
- **Pustaka ligan**: 3.205 obat disetujui (offline, dari ChEMBL), ±700 ribu bahan alam **COCONUT 2.0** (unduh sekali, lalu offline; saring kelas, sifat, kemiripan), dan tautan ZINC22.
- **Gambar ligan dengan Ketcher** (offline) — juga *Edit struktur di Ketcher* dari klik kanan ligan.
- **Prediksi ADMET (ADMET-AI)**: 30 sifat absorpsi, distribusi, metabolisme (CYP), ekskresi, toksisitas (hERG, Ames, DILI), berjalan offline di proses terpisah.
- **Antarmuka bahasa Inggris** (Tampilan › Bahasa / Language; berlaku setelah aplikasi dibuka ulang).

### Diubah
- Uji mandiri kini 22 komponen.

## [0.9.1] — 9 Oktober 2026

### Baru
- **Konsensus skor** (Analisis › Konsensus skor…): gabungkan beberapa mesin docking dan *rescoring* pose terbaik dengan fungsi skor Vina & Vinardo menjadi satu peringkat. Ligan yang konsisten di atas pada semua fungsi skor ditandai ✓; kesepakatan antar fungsi skor diukur dengan Kendall W.
- **Validasi penapisan lebih lengkap**: BEDROC (α = 20) dan logAUC untuk pengayaan dini, interval kepercayaan bootstrap untuk EF dan BEDROC, serta grafik ROC semilog dan kurva pengayaan.
- **Apa yang baru**: ringkasan perubahan muncul sekali setelah pembaruan (Bantuan › Apa yang baru).
- **Statistik setara Prism**: ANOVA dua arah (jenis data "Dua faktor", grafik batang berkelompok), ANOVA pengukuran berulang (koreksi Greenhouse–Geisser) dan Friedman untuk ≥ 3 kolom berpasangan, pilihan koreksi perbandingan ganda (Holm, Bonferroni, Šidák, Benjamini–Hochberg), D'Agostino–Pearson, deteksi pencilan Grubbs, dan Q–Q plot.
- **Pemilihan model IC₅₀ otomatis**: 4PL vs 3PL (Hill = 1) dengan uji F extra sum-of-squares dan AICc.
- **Garis acuan & anotasi** di grafik (mis. ΔG ligan asli sebagai garis putus-putus berlabel).

### Diperbaiki
- Angka di laporan dan tabel memakai format Indonesia (koma desimal, tanda minus asli).
- Kurva IC₅₀ dari data yang tidak membentuk sigmoid kini ditolak atau diberi peringatan (ekstrapolasi, CI terlalu lebar, R² rendah).
- ROC memberi peringatan bila arah skor terbalik (AUC < 0,5) atau data terlalu sedikit.
- Video yang dibatalkan tidak lagi dilaporkan "tersimpan".
- Tab Statistik tidak lagi kosong bila job terbaru hanya berisi sedikit ligan.
- Nilai p < 0,0001 kini tampil di tabel hasil uji (sebelumnya kosong).

## [0.9.0] — 8 Oktober 2026

### Baru
- **Uji & Grafik** ala Prism: panel Format (klik elemen grafik), gaya tersimpan, patah sumbu, skala log, ROC/AUC, tabel kontingensi (Fisher/χ²), IC₅₀ 4PL.
- **Komposer figur** panel A/B/C ukuran jurnal (PDF/SVG/TIFF 600 dpi).
- **Laporan** PDF, Word (.docx) yang bisa disunting, dan HTML interaktif dengan penjelajah 3D.
- **Video 3D** MP4 Full HD–4K, GIF/WebP, dan presentasi sinematik (zoom → putar → sorot interaksi).
- **Tampilan 3D**: label residu tajam di layar HiDPI dan anti-tabrakan, garis tepi, bayangan sekitar (AO), kabut kedalaman yang bisa diatur.
- **Deteksi kantong P2Rank** untuk protein tanpa ligan asli.
- Sifat ligan & BOILED-Egg, statistik & korelasi, kontrol kualitas pose PoseBusters, protonasi Dimorphite-DL, kontribusi energi per atom, sidik jari interaksi.
- Antarmuka pemula: halaman sambutan, panel langkah 1–5, menu berbahasa Indonesia dengan keterangan.
