# Catatan perubahan VirmoDock

Format: setiap versi berisi **Baru**, **Diperbaiki**, dan **Diubah**. Versi 0.x adalah pra-rilis.

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
