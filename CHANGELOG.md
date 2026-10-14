# Catatan perubahan VirmoLab

Format: setiap versi berisi **Baru**, **Diperbaiki**, dan **Diubah**. Versi 0.x adalah pra-rilis.

## [1.4.0] - 14 Oktober 2026

Menggabungkan rencana 1.3 (penargetan balik, jaringan farmakologi) dan 1.4 (QSAR, penapisan farmakofor, pelacak hipotesis).

### Baru
- **Penargetan balik** (Analisis › Penapisan banyak ligan › Penargetan balik & jaringan…; `core/target_balik.py`, `ui/dialog_target_balik.py`):
  - Jalur ligan memakai ChEMBL REST (daring, cache 7 hari): senyawa mirip, aktivitas pChEMBL >= 6 pada target protein tunggal, kemiripan Tanimoto Morgan2 dihitung lokal; target disatukan per UniProt.
  - Jalur struktur: docking Vina (CPU) ke panel struktur kristal lewat antrean; z-skor terhadap 49-50 umpan obat disetujui per target. Panel bawaan: antiinflamasi 8 target, antibakteri 9 target, semuanya lolos redocking RMSD <= 2 Å (disusun `dev/susun_panel.py` dari RCSB; log per langkah di `dev/panel_kandidat/log_*.jsonl`). Kofaktor (NAD, heme) tidak disertakan sehingga target yang bergantung padanya ditolak apa adanya.
  - Peringkat Borda (N+1 untuk target yang absen di satu jalur), label keyakinan, ekspor CSV, paragraf metode dirakit dari hasil nyata. Hasil adalah hipotesis komputasi.
- **Jaringan farmakologi & pengayaan jalur** (tab "Jaringan & jalur"; `core/pengayaan.py`, `core/jaringan.py`):
  - Pengayaan jalur hipergeometrik + Benjamini-Hochberg atas set gen bawaan Reactome v97 (2190 set) dan GO proses biologis (5552 set), dirakit `dev/buat_gmt.py` dari sumber resmi; latar dilaporkan apa adanya.
  - Tepi target-target STRING v12.5 (ambang 0,4/0,7/0,9) dan target-penyakit Open Targets (API v4, data 2026.09), keduanya lewat `core/sumber_data.py` sehingga versi dan lisensi tercatat sebagai jejak proyek.
  - Metrik graf (derajat, betweenness, closeness) dan uji sensitivitas lintas ambang yang melaporkan simpul inti stabil (muncul pada >= 80 % kombinasi).
  - Kanvas graf SVG dengan zoom dan geser, tabel Jalur/Simpul/Sensitivitas, ekspor GraphML dan CSV tepi, kirim ke Komposer Figur, serta paragraf metode berisi basis data, versi, ambang, dan latar.
- **QSAR & model prediksi** (Analisis › Penapisan banyak ligan › QSAR & model prediksi…; `core/qsar.py`, `core/konformal.py`, `ui/dialog_qsar.py`):
  - Wizard lima langkah: impor CSV atau tabel ChEMBL proyek, kurasi (pembakuan struktur, penggabungan duplikat sebagai median, penandaan rentang > 1 log dan activity cliff), pemilihan fitur dan algoritma, validasi, lalu prediksi.
  - Fitur Morgan2/MACCS/deskriptor RDKit tersaring; model Random Forest, SVR, kNN, Gaussian Process, dan Ridge dengan penyetelan validasi silang 5 lipatan di dalam set latih saja.
  - Validasi: Q² CV, R² dan RMSE set uji, Golbraikh-Tropsha, Y-randomization 50×, plot prediksi vs terukur, plot Williams, dan kepentingan fitur permutasi dengan bit Morgan disertai contoh substrukturnya.
  - Pembagian acak dan kerangka Bemis-Murcko dilaporkan berdampingan; selisih R² yang besar ditandai sebagai peringatan bahwa model hanya mengenali kerangka yang sudah dilihat.
  - Prediksi konformal split 90 % (`core/konformal.py`) dan domain aplikabilitas (leverage h* serta kemiripan Tanimoto kNN); senyawa di luar domain ditandai di dialog dan di kolom baru "pIC50 prediksi" panel Hasil.
  - Model disimpan sebagai joblib beserta kartu model JSON (sidik data, metrik, hiperparameter, versi paket, tanggal).
- **Penapisan berbasis ligan 3D (F4)** (Analisis › Penapisan banyak ligan › Penapisan farmakofor & bentuk 3D…; `core/farmakofor.py`, `core/bentuk.py`, `ui/dialog_farmakofor.py`):
  - Kueri farmakofor 3D dari pose aktif di penampil atau ligan ko-kristal proyek, dengan bola eksklusi dari atom berat reseptor proyek (4 Å); pembangkitan konformer ETKDGv3, pencocokan fitur per konformer terselaraskan (RMSD fitur dan penalti eksklusi), serta penapisan paralel ProcessPoolExecutor (kelompok ≤ 500 senyawa, dibagi rata ke semua proses).
  - Keselarasan bentuk dan warna farmakofor via `rdkit.Chem.rdShapeAlign` dengan skor gabungan berbobot dapat diatur.
  - Visualisasi ligan acuan, bola farmakofor, dan bola eksklusi di penampil 3D mengikuti tema; kandidat teratas dikirim sebagai ligan ke jendela utama lalu dialog Siapkan ligan dibuka (protonasi dan PDBQT sebelum docking).
  - Validasi kueri: aktif dari ChEMBL (pChEMBL ≥ 7, beragam kerangka) atau CSV, decoy sepadan gaya DUD-E dibangkitkan otomatis, lalu ROC-AUC, BEDROC, dan EF1% (EF1% hanya untuk himpunan ≥ 100 senyawa). Tolok ukur uji: kueri MK1 (1HSG) membedakan 8 inhibitor protease HIV dari 520 decoy obat sepadan dengan AUC 0,66 (0,71 tanpa bola eksklusi); pengayaan awal lemah, sehingga hasil penapisan diperlakukan sebagai saringan kasar sebelum docking.
- **Pelacak hipotesis → uji laboratorium (F12)** (tab "Hipotesis" di dialog Rencana uji lab; `core/hipotesis.py`, `ui/dialog_labplanner.py`):
  - Perluasan model data `proyek.eksperimen` menyimpan entri hasil uji `{id, ligan_id, assay, nilai, satuan, pIC50, tanggal, catatan, status_hipotesis}` (status: diajukan, diuji, didukung, ditolak) dengan migrasi round-trip utuh bagi data lama (ChEMBL dll).
  - Evaluasi korelasi prediksi in silico vs hasil lab nyata: Spearman ρ dan Kendall τ disertai 95% Confidence Interval bootstrap 1000×, peringatan sampel kecil n < 8, dan penanganan transparan bagi ligan tanpa pasangan.
  - Impor CSV: tabel IC50 per ligan, atau matriks bacaan plate reader 96-well. Bacaan mentah dinormalisasi dengan sumur blanko dan kendali pelarut menurut denah pelat, % inhibisi di-fit 4PL per ligan (semua replikat), dan IC50 hanya dilaporkan bila berada di dalam rentang uji; di luar itu ditandai tersensor (mis. "IC50 > 100 µM") dan tidak ikut dikorelasikan. Z′ dihitung dari kendali pelarut vs kontrol positif.
  - Prediksi pembanding: ΔG docking, MM/GBSA (dibaca dari run MD selesai, rerata replika), dan pIC50 estimasi dari ΔG; pilihan tanpa data di proyek dinonaktifkan.
  - Visualisasi grafik sebar Prediksi vs Terukur (SVG) dengan garis regresi dan pita kepercayaan 95%.
  - Tombol "Latih ulang QSAR dengan data baru" membuka wizard QSAR dengan aktivitas uji lab proyek sudah dimuat (SMILES ligan proyek dibaca lewat `Proyek.smiles_ligan`).

### Diperbaiki
- **QSAR menggantung di aplikasi terpasang.** `core/qsar.py` memakai `n_jobs=-1` pada GridSearchCV,
  `cross_val_predict`, dan `permutation_importance`; backend bawaan joblib (loky) membuat proses anak
  dengan menjalankan ulang program, sehingga di aplikasi beku PyInstaller yang dijalankan ulang adalah
  `VirmoLab.exe` dan bukan fungsi pekerjanya — pelatihan berhenti tanpa kemajuan dengan belasan proses
  menganggur dan tanpa pesan galat. Pelatihan, Y-randomization, dan kepentingan permutasi kini memakai
  backend thread saat berjalan beku (Random Forest sendiri sudah memakai thread sehingga tidak berubah).
- User-Agent permintaan daring (`core/sumber_data.py`) selalu tertulis versi 1.2.0 karena mengimpor nama `VERSI` yang tidak ada; kini memakai `__version__`. Kartu model QSAR kini mencatat versi aplikasi (sebelumnya kosong karena sebab yang sama).

### Diubah
- `--uji-mandiri` mencetak tiap uji begitu selesai; sebelumnya diam sampai seluruh uji tuntas sehingga
  uji yang menggantung tidak ketahuan namanya. `build_tools/rilis.py` membuang `build/uji_mandiri.json`
  lama sebelum menjalankan uji dan menolak hasil yang versinya tidak cocok, supaya hasil build terdahulu
  tidak terbaca sebagai hasil build sekarang.
- `VirmoLab.pyw` dan `VirmoLab_cli.py` kini memanggil `multiprocessing.freeze_support()` agar proses pekerja di build PyInstaller tidak membuka ulang aplikasi.

## [1.2.0] - 13 Oktober 2026

### Baru
- **Fondasi bersama VirmoLab 1.2**:
  - **Modul sumber data terpusat (`core/sumber_data.py`)**: Klien HTTP bersama dengan pencatatan `Jejak` asal-usul data daring (sumber, versi, tanggal ambil, kueri, lisensi), cache berkas lokal di `APPDATA/cache_http` dengan hash SHA-256 dan waktu kedaluwarsa, mode luring otomatis saat jaringan terputus, pembatas laju per domain (min. 0,5 detik; Wikidata 1,0 detik), User-Agent terstandarisasi, dan penanganan galat ramah Bahasa Indonesia.
  - **Pencatatan jejak sumber data di proyek (`core/proyek.py`)**: Atribut `Proyek.jejak` dan metode `catat_jejak` tanpa duplikat berdasarkan kunci sumber+kueri; tersimpan dan dipulihkan pulang-pergi di `proyek.json`, dengan kompatibilitas penuh untuk proyek lama.
  - **Bagian Sumber Data di Laporan Ilmiah & Draf Skripsi (`core/laporan.py`, `core/naskah.py`)**: Laporan otomatis memuat tabel sumber data daring beserta tanggal akses dan lisensi bila proyek memiliki jejak; penyertaan kalimat atribusi wajib untuk data berlisensi CC BY; fungsi `paragraf_sumber_data` menyusun draf metode Bab III skripsi dalam Bahasa Indonesia.
  - **Modul graf dan visualisasi jaringan (`core/graf.py`)**: Perhitungan tata letak Fruchterman-Reingold (`spring`) dan Kamada-Kawai (`kk`), pembuat dokumen SVG murni berbasis token tema terang/gelap tanpa ketergantungan pustaka visualisasi eksternal, ekspor format GraphML standar Cytoscape/Gephi, dan ekspor CSV daftar tepi interaksi.
  - **Dialog Pengaturan (`ui/dialog_pengaturan.py`)**: Antarmuka pengaturan terpadu untuk folder kerja bawaan, penentuan jalur program visualisasi eksternal (PyMOL, ChimeraX, Discovery Studio), serta pemantau ukuran dan tombol pembersih cache internet. Dapat diakses melalui menu `Alat › Pengaturan…` (`Ctrl+,`) dan palet perintah.
- **Analisis lintasan MD lengkap (F2)**:
  - **Modul analisis trajektori mandiri (`core/md_analisis.py`)**: Radius girasi berbobot massa ($R_g$), SASA protein/ligan/terkubur berbasis RDKit `rdFreeSASA` berakselerasi C++ dengan fallback Shrake–Rupley murni NumPy cKDTree, deteksi ikatan hidrogen dan barcode interaksi per frame berokupansi biner (dikompresi Run-Length Encoding / RLE untuk efisiensi ruang simpan di `proyek.json`), jarak Euclidean pasangan atom kunci vs waktu, PCA koordinat Cα ter-superposisi Kabsch, lanskap energi bebas 2D (FEL Boltzmann, $\Delta G = -k_B T \ln(P/P_{\max})$), clustering hierarki linkage average RMSD ligan 2,0 Å dengan penentuan konformasi medoid, serta estimasi konvergensi rata-rata blok (block averaging).
  - **Dukungan multi-replika dan versi analisis 2 (`core/md.py`)**: Opsi jumlah replika (1–5; bawaan 1, rekomendasi ilmiah 3) dengan variasi benih acak mandiri, estimasi waktu proporsional berbasis tolok ukur kecepatan lokal, penyimpanan struktur data analisis versi 2 terkompresi RLE, serta pembaca mandiri DCD biner (`baca_dcd`) untuk menghitung ulang simulasi lama melalui tombol *Hitung analisis lanjutan*.
  - **Antarmuka 7 Tab Komprehensif (`ui/dialog_md.py`)**: Tab *Ringkasan* (kartu metrik paruh kedua, lencana konvergensi, hitung ulang simulasi lama), *Stabilitas* (pemilih metrik dinamis RMSD, RMSF, Rg, SASA), *Interaksi* (tabel okupansi residu kontak dan barcode visual waktu × residu), *PCA & FEL* (sebaran proyeksi PC1–PC2 dan heatmap kontur energi bebas FEL 2D), *Klaster* (tabel klaster konformasi, pemuatan medoid ke penampil 3D, dan tombol *Pakai sebagai reseptor ensemble*), *Replika* (tabel konsistensi metrik dan grafik perbandingan kurva multi-replika), serta *Log*.
  - **Ekspor dan Integrasi Komposer**: Semua visualisasi mendukung tombol *Kirim ke komposer*, *Simpan figur…* (SVG vektor / PNG raster), *Ekspor CSV…*, serta ekspor PDB ensemble medoid reseptor.
  - **Laporan Trajektori MD Komprehensif (`core/laporan.py`)**: Laporan otomatis mencakup tabel statistik paruh kedua (rata-rata ± SD), evaluasi naratif konvergensi, dan 5 figur standar berkualitas tinggi (RMSD, RMSF, Rg, Ikatan H, dan kontur FEL 2D).
  - **Ketepatan interaksi lintasan**: okupansi kini dihitung per frame (sebelumnya satu residu dengan dua ikatan H terhitung dua kali sehingga bisa > 100 %); jumlah ikatan H per frame memakai kode jenis yang benar (`hbond`), sebelumnya selalu 0; analisis ulang MD lama memakai pose ligan ber-ikatan dari `tugas.json` sehingga ikatan H (mis. ASP 25 katalitik pada 1HSG) terdeteksi, bukan hanya kontak hidrofobik. Uji `uji_md_analisis` #11 menguncinya.
  - **Replika tahan jeda**: replika yang sudah tuntas disimpan (`replika_selesai.json`) dan tidak disimulasikan ulang saat MD dilanjutkan.
  - **Tampilan**: angka kartu bergaya Indonesia, label tab "PCA & FEL", catatan ringkasan menyebut jumlah replika dan lama MD sebenarnya beserta peringatan analisis, sumbu waktu barcode tanpa tik kembar, nama jenis interaksi dapat dibaca.
- **Senyawa dari tanaman obat (F1)**:
  - **Pencarian takson dan senyawa tanaman (`core/tanaman.py`)**: Pencarian metabolit sekunder tanaman obat Indonesia dari LOTUS (Wikidata SPARQL P703) dan COCONUT 2.0; pemetaan nama lokal (62 tanaman obat teruji di `data/nama_tanaman_id.csv`) ke takson resmi Wikidata (P225, P1420); penggabungan duplikat berbasis 14 karakter awal InChIKey; standarisasi RDKit (fragmen terbesar, netralisasi, kanonisasi, penjagaan stereokimia); serta penyaringan sifat obat (MW, Lipinski, QED, PAINS).
  - **Pembaruan skema COCONUT (`core/pustaka.py`, `ui/dialog_pustaka.py`)**: Penambahan kolom `organisme` pada skema tabel SQLite COCONUT lokal beserta migrasi otomatis tabel lama; opsi pengunduhan versi lengkap (197,5 MB, Zenodo, lisensi CC BY 4.0) vs versi ringkas (200 MB, Jena, data CC0) dengan konfirmasi pengguna di UI.
  - **Dialog Senyawa Tanaman Obat (`ui/dialog_tanaman.py`)**: Antarmuka pencarian takson, tabel senyawa dengan saringan interaktif, pratinjau struktur 2D molekul, tombol pembuka rujukan artikel ilmiah (DOI), tautan pencarian eksternal Wikidata & KNApSAcK, ekspor tabel CSV, dan tombol impor ke proyek dengan deteksi duplikasi dan pencatatan jejak sumber data (Provenance).
  - **Rujukan artikel lewat graf ilmiah Wikidata**: sejak Wikidata Query Service memisahkan graf artikel ilmiah, DOI dan tahun terbit tidak lagi tersedia di endpoint utama. Kueri LOTUS kini mengambil item artikel rujukan dari endpoint utama, lalu DOI, tahun, dan judulnya dari `query-scholarly.wikidata.org`; rujukan tanpa DOI ditautkan ke halaman Wikidata-nya. Sambiloto: 159/159 senyawa berujuk DOI.
  - **Pilihan senyawa**: tidak ada yang tercentang otomatis; centang bertahan saat saringan diubah dan jumlah terpilih diperbarui langsung. Pratinjau struktur dan warna lencana mengikuti mode gelap.
  - **Integrasi alur kerja**: Menu `Siapkan › Langkah 2 · Ligan › Senyawa dari tanaman obat…`, tombol `Senyawa tanaman obat…` pada panel Langkah 2, dan palet perintah `Ctrl+K`.
- **Paket validasi protokol (F11)**:
  - **Hasil yang jujur**: tombol pengayaan versi awal memakai skor aktif yang ditulis di kode dan skor decoy acak (`np.random`), dan ringkasan mengisi nilai bawaan karangan (RMSD 1,25 Å, AUC 0,85, PoseBusters 95 %) yang masuk ke paragraf metode dan laporan; dialog juga langsung galat saat dibuka (`kit.judul` salah argumen, `kit.tombol_aksi` tidak ada). Dialog ditulis ulang: semua langkah menjalankan docking nyata di utas latar (dapat dibatalkan), langkah yang belum dijalankan tampil "–" dan tidak masuk paragraf atau laporan.
  - **Enrichment**: docking yang gagal dikeluarkan dan dihitung (dulu dicatat skor 0, yang menghukum aktif dan menaikkan AUC lewat decoy gagal); menolak menghitung bila terlalu sedikit ligan berhasil; peringatan sampel kecil.
  - **Cross-docking**: struktur disuperposisikan lewat Cα bersama (dulu RMSD dibandingkan antar-kerangka koordinat berbeda), sel gagal bernilai kosong (dulu 0,0 = sempurna); satu ligan kristal terbesar per struktur (dulu semua HETATM digabung).
  - **Decoy**: dipilih acak dengan benih tetap dan dibagi seimbang antar-aktif (dulu berurutan menurut basis data); peringatan bahwa decoy bukan dari ZINC seperti DUD-E.
  - **Paragraf metode**: p-nilai diambil dari hasil (dulu selalu "p < 0,0001"), tidak menyebut "reproduced" bila redocking gagal, tidak menyebut uji yang tidak dijalankan, decoy tidak lagi disebut "DUD-E decoys".
  - Uji: `dev/uji_validasi_protokol.py` 14 kasus (docking tiruan untuk logika kegagalan, superposisi Cα sintetis, dialog dibuka).
  - **Generator decoy gaya DUD-E lokal (`core/decoy.py`)**: Pemilihan senyawa aktif bertarget ChEMBL dengan klasterisasi scaffold Taylor-Butina (ambang 0,6 / cutoff jarak 0,4) untuk menjamin diversitas kimiawi; pencocokan decoy fisikokimiawi lokal (MW ±25, logP ±0,5, HBD ±1, HBA ±1, ikatan berputar ±1, muatan identik) bersumber dari ChEMBL, COCONUT, atau pustaka obat lokal; penyaringan disimilaritas topologi Morgan2 Tanimoto ke semua aktif < 0,30 dan diversitas antar-decoy < 0,90; serta uji 2-sampel Kolmogorov-Smirnov per sifat membuktikan populasi decoy tidak bias ($p > 0,05$).
  - **Orkestrasi validasi multi-tahap (`core/validasi_protokol.py`)**: Redocking ligan kristal mandiri dengan perhitungan RMSD simetri (ambang baku $\le 2,0$ Å); cross-docking berpasangan multi-struktur PDB menghasilkan matriks RMSD dan heatmap SVG; penapisan virtual aktif vs decoy menghasilkan kurva ROC, BEDROC ($\alpha = 20$), Faktor Pengayaan EF 1% & 5%, dan logAUC; integrasi PoseBusters untuk persentase pose fisik valid; penyusunan narasi paragraf metodologi ilmiah baku dwibahasa (ID & EN); serta pembuatan laporan ringkasan mandiri HTML offline.
  - **Dialog Wizard 4 Langkah (`ui/dialog_validasi_protokol.py`)**: Redocking (validasi proyek atau berkas PDB), Cross-docking (≥ 2 PDB), Pengayaan (aktif ChEMBL/CSV, decoy, docking nyata), dan Ringkasan (kartu, paragraf metode, laporan HTML, komposer).
  - **Integrasi alur kerja**: Menu `Analisis › Validasi dan mutu › Paket validasi protokol…`, tombol toolbar tab `Uji`, dan entri palet perintah `Ctrl+K`.

### Diubah
- **Nama baru: VirmoLab.** Logo baru "heksa-kantong faset": cincin heksagon yang sisi atasnya terlipat membentuk V (kantong pengikatan sekaligus huruf V), ligan heksagon azure masuk ke kantong, lima faset navy. Palet navy `#12305A` + azure `#2F74E0`; huruf Figtree (SIL OFL). Set lengkap + panduan di `branding/virmolab_*` (`build_tools/logo/produksi_virmolab.py`); logo lama diarsipkan di `branding/arsip_logo_lama/`.
- Ikon aplikasi, logo halaman awal/Tentang/wizard, gambar installer, dan semua teks antarmuka (termasuk kamus Inggris) memakai nama VirmoLab.
- **Rebrand total ke VirmoLab**: program `VirmoLab.exe`/`VirmoLab-cli.exe`, paket Python `virmolab`, folder data `%LOCALAPPDATA%\VirmoLab`, pengaturan `HKCU\Software\VirmoLab`, berkas installer/portable `VirmoLab-*`, folder proyek bawaan `Documents\VirmoLab`, dan tutorial `Tutorial_Docking_VirmoLab.pdf`. Ekstensi `.vmd` dan `.vmdbackup` tetap.
- **Migrasi otomatis dari nama lama (versi ≤ 1.1.2)**: saat pertama jalan, isi folder data lama di `%LOCALAPPDATA%` dipindah/disalin (tanpa menimpa) dan pengaturan registry lama disalin bila pengaturan baru masih kosong; folder proyek lama di `Documents` yang sudah ada tetap dipakai; cadangan `.vmdbackup` buatan versi lama tetap bisa diimpor. Installer memakai AppId yang sama sehingga memasang sebagai upgrade: folder program, pintasan, dan asosiasi berkas lama dibersihkan.

## [1.1.2] - 13 Oktober 2026

### Diperbaiki
- **Terjemahan bahasa Inggris dilengkapi dan diaudit menyeluruh untuk seluruh fitur 0.9.7–1.1.2**: Kamus `en.json` diperluas menjadi 2.921 teks dan 659 pola dengan terminologi komputasi/kimia medisinal baku; seluruh teks antarmuka bebas teks campur sari, konsisten spasi/baris baru, dan lolos uji verifikasi `dev/uji_bahasa.py` serta audit mutu otomatis `dev/cek_mutu_i18n.py` (0 teks bermasalah).
- **Ikon tidak lagi berwarna saat diam.** Ubin halaman awal dan tombol panel langkah menggambar ikonnya dengan warna aksen, sementara toolbar dan panel Objek memakai abu-abu netral — dua gaya dalam satu jendela. Kini semua ikon netral saat diam dan menyala aksen hanya ketika disorot tetikus atau pada tombol utama.
- **29 warna tetap yang menduplikasi token tema** diganti pemanggilan token (`kit.hx`, `kit.warna`), jadi mode gelap memakai nilai tema gelap, bukan nilai tema terang yang dipatok di kode: dialog ADMET, wizard reseptor, MD, konsensus, komposer, residu fleksibel, panel docking, tab Uji, panel Objek, dan dialog perangkat. Warna yang memang harus tetap (palet pewarnaan molekul, lintasan saluran di viewport, ikon baki sistem) diberi keterangan agar tidak ikut terganti di kemudian hari.
- **Angka di tab Sifat ligan dan panel Hasil** ikut gaya Indonesia (QED, massa, ΔG, ambang syarat jarak, SD MM/GBSA), menyusul tabel Hasil yang sudah lebih dulu.
- **Angka di panel Properti** memakai gaya Indonesia seperti tabel Hasil (koma desimal, minus sebenarnya): ΔG, skor kovalen, RMSD kristal/masukan/l.b.–u.b., skor lokal, resolusi, dan massa molekul.

### Diubah
- **`mainwindow.py` dipecah jadi tiga mixin**: 27 pembuka dialog analisis ke `ui/mainwindow_dialog.py` (`PembukaDialog`), komposer figur ke `ui/mainwindow_komposer.py` (`KomposerFigur`), dan perekaman video ke `ui/mainwindow_media.py` (`MediaAnimasi`). Berkas utama turun dari 5.365 ke 4.628 baris, sehingga menambah alat analisis, mengubah tata letak figur, atau menyentuh perekaman video tidak lagi berbagi berkas yang sama — penyebab bug `kerja` yang tertutupi pada 1.1.1.
- **Kepala dialog seragam**: 14 dialog analisis lama (ADMET, ChEMBL, konsensus, MD, asisten, diagnostik, FBDD, kemiripan, rencana lab, MMP, penapisan, PPI, pustaka, selektivitas) kini dibuka dengan judul dan satu kalimat penjelasan lewat `kit.judul`, sama seperti dialog yang lebih baru. Keterangan pengantar yang sudah ada dipindah ke subjudul, bukan ditulis ulang.
- **Tanda proses** ditambahkan pada hitungan berat dialog lama: pemuatan ligan, perhitungan kemiripan, pengelompokan Butina, dan penyusunan ulang figur komposer.
- **Penanganan galat yang sengaja diam diberi alasan tertulis** di delapan tempat (sanitasi pose untuk diagram, stereo dari geometri 3D, optimasi MMFF aduk kovalen, warna tak dikenal pada pemeriksa figur, loguru opsional, pencarian platform OpenMM, deteksi PoseBusters, produk reaksi tak sah pada enumerasi) sehingga tidak terbaca sebagai kelalaian saat ditinjau.

### Baru
- **Uji mandiri untuk tiga modul inti yang selama ini tidak teruji**: `dev/uji_proyek.py` (simpan–buka pulang-pergi, penulisan atomik dan cadangan, migrasi format lawas, id ligan unik, SMILES dari REMARK PDBQT, penolakan folder bukan proyek), `dev/uji_molekul.py` (pemecahan 1HSG jadi protein/ligan/air, SMILES→3D, SDF bolak-balik, impor berkas, penolakan berkas asing, elemen PDBQT), dan `dev/uji_prep_ligan.py` (PDBQT Meeko, protonasi pH 7,4, mode tanpa minimisasi, pelaporan ligan gagal, pemrosesan banyak ligan), dan `dev/uji_analisis_inti.py` (deteksi interaksi MK1–protease HIV-1 pada 1HSG: ikatan hidrogen, kontak hidrofobik, residu katalitik ASP 25 dan flap ILE 50, sidik jari interaksi, Tanimoto IFP, efisiensi ligan).

## [1.1.1] - 12 Oktober 2026

### Baru
- **Peta organ ADMET** (Analisis › Prediksi ADMET › tab **Peta organ**): diagram alur dua dimensi tanpa figur manusia. Baris atas mengikuti perjalanan obat — penyerapan (saluran cerna) → peredaran (jantung) → metabolisme (hati) → pembuangan (ginjal) — dihubungkan panah dengan titik berjalan yang kecepatannya mengikuti waktu paruh prediksi; baris bawah memuat organ dan sistem terdampak (otak, kulit, inti sel, paparan menyeluruh). Tiap kartu berisi ikon organ, nama, skor 0–100, dan bilah skor. Skor organ = rata-rata endpoint ADMET-AI yang relevan, dibatasi oleh endpoint terburuknya supaya satu nilai buruk tidak tersamarkan; klik kartu untuk melihat endpoint penyusunnya satu per satu. Endpoint netral seperti BBB tampil sebagai angka informasi berwarna biru, bukan dinilai baik/buruk, dan organ tanpa model (paru, pankreas, tiroid) disebutkan apa adanya. Dilengkapi peralihan warna halus saat ganti ligan, denyut singkat pada kartu berisiko, animasi yang bisa dimatikan, serta ekspor PNG/SVG (`core/peta_tubuh.py`, `ui/peta_tubuh.py`).
- Gerak pada peta organ: kartu muncul bertahap dari bawah saat ligan berganti, tiga partikel menyusuri panah perjalanan obat (tersembunyi saat melintasi kartu), kartu berisiko berdenyut dengan halo yang meredup sendiri, kartu terangkat halus saat disorot tetikus, dan riak melebar sekali ketika sebuah kartu dipilih. Satu kotak centang mematikan seluruh gerak sekaligus menghentikan pengatur waktunya, jadi tidak ada beban gambar ulang saat tidak dipakai.
- Peta organ memuat nama ligan dan kalimat ringkasan di atas gambar, legenda warna (aman / perlu dicermati / berisiko / informasi) di bawahnya — keduanya ikut terekspor — serta keterangan jelas saat ligan belum diprediksi. Kartu bisa dijelajahi dengan panah papan ketik, dan hurufnya mengikuti huruf antarmuka sehingga tetap pas pada penskalaan Windows 125 % dan 150 %.
- **Ikon organ digambar sendiri** (`ui/bentuk_organ.py`): otak berlekuk, jantung beraorta, hati berlobus, lambung bergelung usus, sepasang ginjal, potongan kulit berlapis, sel berinti, dan kapsul paparan menyeluruh. Dirakit dari bentuk dasar dan tabung garis, jadi tetap tajam dari ikon kecil sampai ekspor 4K dan tidak bergantung pada aset berlisensi pihak lain.
- Daftar ligan pada dialog ADMET kini melewati aditif kristalografi (DMS, gliserol, sulfat) dan serpihan di bawah 6 atom berat, sama seperti dialog analisis lain.

### Diperbaiki
- **Dialog alat lanjutan tidak lagi gagal dibuka pada proyek nyata**: Deteksi kantong, Saluran akses ligan, Skrip figur publikasi, Desain berbasis fragmen, dan Periksa kontak atom pose sebelumnya memanggil `proyek.reseptor[0]`, `proyek.grid`, `self._info`, dan nama sinyal yang tidak ada sehingga langsung melempar `KeyError`/`AttributeError` begitu menu diklik. Semua dialog baru kini menerima jendela utama dan mengambil data lewat pembantu bersama `ui/kit.py` (`reseptor_proyek`, `ligan_proyek`, `pose_aktif`, `pusat_kotak`).
- **Deteksi kantong pengikatan ditulis ulang (LIGSITE)**: versi lama menggabungkan seluruh lekuk permukaan menjadi satu rongga raksasa (± 14.000 Å³ pada 1HSG) sehingga tidak berguna. Metode baru memakai pemindaian 13 sumbu (protein–pelarut–protein) plus saringan lapisan permukaan: pada 1HSG apo kantong teratas berpusat 0,9 Å dari ligan kristal MK1 dengan volume 207 Å³ dan dinding memuat ASP 25 katalitik. Air, ion, dan pelarut kristalisasi diabaikan.
- **Saluran akses ligan**: perhitungan dipindahkan ke NumPy (0,4 detik untuk 64 sinar), titik awal diambil dari grid box atau pose aktif (dulu pusat massa protein, yang jarang berada di kantong), titik awal digeser otomatis ke ruang kosong, "kurvatur" yang selalu bernilai ± 1,0 pada jalur lurus dihapus, dan garis tengah saluran kini benar-benar tergambar di viewport (`VM.terowongan`).
- **Perancang PROTAC menghasilkan molekul utuh**: perakitan dulu sering jatuh ke SMILES bertitik (`warhead.linker.E3`), yaitu tiga fragmen terpisah, lalu sifat fisikokimianya dihitung dari fragmen itu. Kini warhead, linker, dan pengikat E3 disambung kovalen lewat titik lekat RDKit dan rakitan yang gagal ditolak dengan pesan jelas.
- **Periksa kontak atom pose (dulu "Re-scoring Machine Learning")**: perhitungan kontak divektorkan dan hanya memakai atom reseptor di sekitar pose; ukuran baru kerapatan kontak per atom berat dan pangsa kontak polar; klaim "model Random Forest terlatih PDBbind" diganti keterangan jujur bahwa skornya bobot linier sederhana.
- **CNS-MPO**: preset dulu memakai RotB dan SAScore yang bukan bagian CNS-MPO Pfizer. Kini hanya empat suku Wager et al. 2010 yang bisa dihitung (MW, ClogP≈WLOGP, TPSA, HBD) dengan keterangan bahwa ClogD dan pKa tidak disertakan, sehingga nilainya tidak disamakan dengan CNS-MPO 0–6 asli.
- **Pengiriman ClusPro palsu dihapus**: fungsi lama menembak URL yang bukan API ClusPro, mengarang nomor job dari panjang teks, dan melaporkan "berhasil dikirim" untuk respons HTTP apa pun — padahal struktur dan alamat surel pengguna sudah terkirim ke luar. Penggantinya hanya menyiapkan dua berkas PDB untuk diunggah sendiri oleh pengguna; VirmoLab tidak mengirim data ke mana pun.
- **Telaah air sisi aktif**: angka yang dulu disebut "ΔG penggusuran (kkal/mol)" sebenarnya skor heuristik tanpa satuan dan kini dinamai demikian, lengkap dengan catatan bahwa termodinamika air sesungguhnya memerlukan WaterMap/GIST/3D-RISM.
- **Skrip figur publikasi**: perintah ChimeraX yang tidak sahih (`select #1 & (zone #2 4.5)`, `transparency sel 70`) diperbaiki, urutan `orient`/`zoom` PyMOL dibetulkan, label residu memakai rantai yang benar, dan struktur yang dirujuk ikut disalin ke folder tujuan sehingga skrip bisa langsung dijalankan.
- **Sifat ligan pada proyek lama**: ligan tanpa berkas SDF sumber (hanya PDBQT) kini dibaca dari `REMARK SMILES`, sehingga tab Sifat, MPO, MMP, penapisan, dan kalkulator lab basah tidak lagi kosong.
- **Dua nama lokal `kerja` menutupi modul `ui.kerja`** di `mainwindow.py` sehingga geser ligan utuh dan penilaian GNINA otomatis selalu berhenti dengan `AttributeError: 'function' object has no attribute 'jalankan'`. Keduanya diganti nama (`geser`, `nilai_gnina`).
- **Uji regresi dipulihkan**: berkas contoh `dev/uji/1HSG_rec.pdbqt`, `dev/uji/run/`, `dev/uji/zn/`, dan `dev/uji/kerja_docs/` dibangun ulang sehingga 26 uji yang gagal karena berkas contoh hilang kembali berjalan; `uji_mesin`, `uji_posemol`, `uji_protonasi`, dan `uji_p2rank` kini berhenti dengan pesan "LEWAT" yang jelas bila contohnya memang belum dibuat, bukan `IndexError`.
- `uji_kantong` diganti dengan uji struktur nyata (1HSG apo versus holo); `uji_gelombang_a_gui` tidak lagi memakai mock jendela (mock-nya lulus walau dialog tidak bisa dibuka dari aplikasi) melainkan harness jendela asli `dev/uji_dialog_lanjut_gui.py`, yang membuka 16 dialog lanjutan pada proyek nyata di tema terang dan gelap; `uji_095_gui` mengikuti jumlah templat yang sebenarnya.

### Diubah
- **Tata letak kini menyesuaikan ukuran layar.** Semua panel dulu memakai angka piksel mati (dok kiri 230/400 px, dok kanan 330 px dengan minimum 300 px, panel bawah 180 px), sehingga di layar 1366×768 panel memakan hampir separuh lebar jendela sedangkan di layar besar justru kekecilan. Sekarang lebar dan tinggi dok dihitung sebagai bagian dari ruang kerja (kiri ±18%, kanan ±24%, panel bawah ±20%) dengan batas bawah-atas, dan batas minimumnya mengikuti lebar huruf antarmuka sehingga tetap benar pada penskalaan Windows 125% dan 150%. Diuji pada 1366×768, 1600×900, 1920×1080, dan 2560×1440 lewat `dev/uji_tata_letak.py` — area tengah selalu mendapat 47–68% lebar jendela.
- **Mode ringkas untuk layar pendek** (tinggi < 800 px): panel Langkah dan Objek ditumpuk jadi tab (bukan dibagi dua vertikal), tinggi baris tabel/pohon dan isian tab serta menu dirapatkan. Peralihannya mengikuti ukuran jendela, bukan hanya ukuran saat aplikasi dibuka.
- **Panel bawah tidak lagi menetap menutupi hasil.** Dulu `_galat()` membuka panel Antrean/Log/Pesan dan tidak ada kode yang menutupnya lagi, jadi panel kosong menyita ruang selamanya. Kini panel terbuka sendiri hanya untuk galat atau saat ada job berjalan, lalu tertutup kembali setelah antrean selesai dan pesan dibaca; panel yang dibuka sendiri oleh pengguna tidak akan ditutup otomatis, dan bila pengguna menutupnya, galat berikutnya cukup muncul sebagai lencana "N pesan baru" berwarna merah di bilah status.
- **Tata letak tersimpan diperiksa dulu**: ukuran layar ikut disimpan, dan bila sekarang berbeda lebih dari 15% (mis. dulu di monitor eksternal), proporsinya dihitung ulang alih-alih dipakai mentah. `Tampilan › Atur ulang tata letak` kini punya pintasan `Ctrl+Shift+0`.
- **Menu Analisis dipadatkan**: dulu 40 butir lurus melebihi tinggi layar. Kini empat butir yang paling sering dipakai di tingkat atas (Tabel hasil, Diagram 2D, Sifat ligan, Bandingkan ligan) dan sisanya dikelompokkan ke submenu: Telaah pose dan interaksi, Validasi dan mutu, Struktur reseptor, Sifat ligan dan desain, Penapisan banyak ligan, Simulasi dan penelitian lanjut, serta Statistik dan figur.
- **Panah penanda hilang di seluruh aplikasi**: QSS lama menata ulang `QComboBox::drop-down` tanpa menyediakan gambar panah, sehingga kotak pilihan (mis. pemilih alur "Docking Molekuler" dan preset MPO) tampak seperti kotak teks biasa. Ikon chevron kini dirender per tema untuk kotak pilihan, tombol naik/turun spin box, penanda submenu, dan cabang pohon objek.
- **Tanda proses berjalan**: hitungan yang tadinya membekukan jendela tanpa keterangan kini memakai `kit.sibuk` (kursor tunggu + teks status di dialog): pasangan MMP, jurang aktivitas, matriks selektivitas, SASA dan evaluasi antarmuka PPI, penumbuhan/penyambungan fragmen, titik metabolisme, skor MPO, pemuatan dan penyaringan dasbor penapisan, serta pemeriksa kesehatan sistem. Pemindaian kantong tetap berjalan di thread terpisah.
- **Tampilan dialog baru diseragamkan dengan aplikasi**: warna tetap (biru, ungu, hijau, merah) diganti token tema sehingga mode gelap terbaca, judul jendela mengikuti gaya kalimat Bahasa Indonesia, tabel memakai pengurutan numerik dan format angka Indonesia (koma desimal, minus asli), tanda "&" tidak lagi tampil sebagai garis bawah pada tab, dan denah pelat mikro memakai warna pastel bertulisan gelap.
- **Catatan batas di tiap alat perkiraan**: kinetika/waktu tinggal, kelayakan kantong, titik metabolisme, skor kontak, dan interpretasi AI kini menyebutkan asumsi dan batas pemakaiannya langsung di dialog, termasuk pengingat agar hasil AI dicocokkan dengan tab Hasil sebelum masuk naskah.
- Dialog-dialog baru kini dibuka lewat jendela utama dengan satu pola yang sama (`DialogX(self)`), memakai pekerja latar belakang untuk pemindaian berat sehingga antarmuka tidak membeku.

## [1.1.0] - 11 Oktober 2026

### Baru
- **Deteksi Terowongan & Saluran Akses Ligan (Tunnel & Channel Finder)** (Analisis › Deteksi Terowongan Akses Ligan…): mendeteksi rute koridor akses molekul kecil dari sisi aktif menuju permukaan pelarut luar. Menghitung radius leher tersempit (bottleneck radius dalam Å), panjang total lorong, kurvatur lintasan, mengidentifikasi residu dinding pelindung serta residu pintu gerbang (*gatekeeper residues*), dan menampilkan lintasan centerline terowongan di viewer 3D (`terowongan.py`, `dialog_terowongan.py`).
- **Prediksi Kinetika Pengikatan & Waktu Tinggal (Residence Time & k_off Estimator)** (Analisis › Prediksi Kinetika & Waktu Tinggal…): estimasi parameter kinetika interaksi obat-reseptor ($k_{\text{off}}$, $k_{\text{on}}$, waktu tinggal $\tau = 1/k_{\text{off}}$, dan waktu paruh kompleks $t_{1/2} = \ln 2 / k_{\text{off}}$) berbasis energi docking $\Delta G$, derajat proteksi ikatan hidrogen terkubur (*shielded H-bonds*), dan kontak hidrofobik terkurung. Dilengkapi klasifikasi kinetik (*Transient*, *Moderate*, *Sustained*, *Ultra-Sustained*) dan wawasan translasi PK/PD (`kinetika.py`, `dialog_kinetika.py`).
- **Perancang Molekul PROTAC & Modalitas TPD (Targeted Protein Degradation)** (Analisis › Perancang PROTAC & Degradasi Target…): platform perakitan molekul chimera bivalen penarget degradasi protein: Warhead Ligan Target - Linker Modular - E3 Ligase Binder (VHL VH032, Cereblon Pomalidomide, Cereblon Thalidomide). Menyediakan pilihan linker PEG (PEG2, PEG3, PEG4), alkil (C4, C6, C8), dan piperazin semikaku, evaluasi parameter *Beyond Rule of 5* (bRo5: MW, LogP, TPSA, HBD/HBA, rotatable bonds, panjang rentang linker terentang dalam Å), serta tombol impor langsung ke daftar ligan proyek (`protac.py`, `dialog_protac.py`).
- **Prediksi Titik Metabolisme Ligan (Site of Metabolism / SoM Finder)** (Analisis › Prediksi Titik Metabolisme…): deteksi posisi atom ligan yang paling rentan terhadap metabolisme oksidatif fase I oleh enzim Sitokrom P450 (CYP3A4, CYP2D6, CYP2C9: N-dealkilasi, O-demetilasi, hidroksilasi benzilik/alifatik/aromatik, S-oksidasi). Menghitung skor stabilitas metabolik intrinsik ligan dan menyajikan rekomendasi substitusi bioisosterik pelindung metabolisme (misal fluorinasi metabolik $C-H \to C-F$, deuterasi, penambahan cincin kaku) (`metabolisme.py`, `dialog_metabolisme.py`).
- **Re-scoring Berbasis Machine Learning Kontak Atom (RF-Score & Footprinting)** (Analisis › Re-scoring Machine Learning…): ekstraksi sidik jari interaksi intermolekuler pasangan kontak atom protein-ligan ($d \le 4.0\text{ \AA}$) dan estimasi afinitas $\text{pK}_d$ serta $\Delta G_{\text{ML}}$ (kcal/mol) menggunakan model regresi machine learning terkalibrasi PDBbind. Dilengkapi detektor *False-Positive* otomatis untuk memvalidasi pose dengan afinitas Vina tinggi namun kontak atomiknya tidak realistis (`rescore_ml.py`, `dialog_rescore_ml.py`).

## [1.0.0] - 11 Oktober 2026

### Baru
- **Deteksi Kantong Pengikatan Otomatis (Cavity / Binding Site Finder)** (Analisis › Deteksi Kantong Pengikatan…): deteksi rongga aktif dan kantong pengikatan makromolekul secara otomatis berbasis grid geometri dan uji keterbukaan pelarut (burial check). Mendukung struktur apo atau model AlphaFold yang belum memiliki ko-kristal ligan. Menyediakan perankingan volume rongga (Å³), deteksi residu pembatas kantong (lining residues), visualisasi bola dummy di viewer 3D, serta tombol sekali-klik "Jadikan Kotak Docking Proyek Ini" (`kantong.py`, `dialog_kantong.py`).
- **Desain Berbasis Fragmen (Fragment-Based Drug Design / FBDD)** (Analisis › Desain Berbasis Fragmen…): platform komputasi untuk perancangan ligan rasional. Mendukung mode **Fragment Growing** (menumbuhkan 15 gugus bioisosterik pada atom hidrogen terpilih) dan **Fragment Linking** (menyambungkan dua fragmen aktif dengan 7 varian linker fleksibel/kaku). Menghitung secara seketika sifat fisikokimia, Lipinski Rule of 5, QED, dan SAScore, serta tombol impor langsung ke antrean ligan proyek (`fbdd.py`, `dialog_fbdd.py`).
- **Analisis Termodinamika Air Sisi Aktif (Active-Site Water Thermodynamics)**: modul evaluasi energetika molekul air kristal pada sisi aktif reseptor. Mengklasifikasikan air menjadi kategori "Stabil/Struktural" (merugikan bila digusur) dan "Frustrasi/Tidak Stabil" (menguntungkan bila digusur, ΔG_displacement < 0 kcal/mol) berbasis derajat penguburan (burial index) dan jejaring donor/akseptor hidrogen (`air_termo.py`).
- **Generator Skrip Visualisasi Publikasi PyMOL & UCSF ChimeraX** (Alat › Ekspor Skrip Publikasi…): menghasilkan skrip `.pml` dan `.cxc` siap pakai sekali-klik dengan standar estetika jurnal terkemuka (Nature / Journal of Medicinal Chemistry). Mengotomatisasi pewarnaan kontras ligan, kartun protein, stick residu kantong aktif, garis putus-putus ikatan hidrogen, permukaan kantong transparan, dan pengaturan ray-tracing 300 DPI (`skrip_publikasi.py`, `dialog_skrip_publikasi.py`).
- **Pemeriksa Kesehatan Lingkungan Sistem (System Diagnostics)** (Bantuan › Pemeriksa Kesehatan Sistem…): audit mandiri komprehensif terhadap 8 subsistem kunci (Python runtime, pustaka chemoinformatics RDKit, manipulasi struktur Gemmi & NumPy, mesin docking AutoDock Vina, akselerasi dinamika molekul OpenMM & GPU CUDA/ROCm/OpenCL, subsistem Linux WSL2 untuk GNINA/Boltz, serta peladen AI lokal Ollama). Dilengkapi penanda status visual, kartu rekomendasi aksi, dan tombol salin laporan sistem (`diagnostik.py`, `dialog_diagnostik.py`).

## [0.9.8] - 11 Oktober 2026

### Baru
- **Dashboard Penapisan Virtual (Batch Virtual Screening)** (Analisis › Dashboard Penapisan Virtual…): antarmuka interaktif untuk menganalisis hasil penapisan skala besar (>100 ligan). Peta panas (heatmap) ligan × parameter, multi-variabel scatter plot (ΔG vs SAScore bergradien warna QED/MPO), histogram distribusi afinitas dengan garis rata-rata & median, filter multi-kriteria dengan slider & checkbox (Lipinski, Veber, PAINS, Brenk, GI), peringkat komposit multi-dimensi, auto-flag "Top Hits", serta ekspor CSV data terfilter (`penapisan.py`, `dialog_penapisan.py`, `grafik.heatmap_svg`, `grafik.scatter_multi_svg`, `grafik.histogram_distribusi_svg`).
- **Analisis Molecular Matched Pair (MMP)** (Analisis › Analisis Molecular Matched Pair…): deteksi otomatis pasangan molekul yang berbeda hanya satu variasi substituen (RDKit `rdMMPA`), tabel transformasi R-group terhadap perubahan afinitas (ΔΔG), drug-likeness (ΔQED), dan kemudahan sintesis (ΔSAScore), deteksi SAR Activity Cliffs (|ΔΔG| ≥ 1.5 kcal/mol dengan kemiripan struktur tinggi), serta panel rekomendasi substitusi gugus R yang paling konsisten meningkatkan afinitas pada target (`mmp.py`, `dialog_mmp.py`).
- **Selektivitas Multi-Target & Matriks Ensemble Docking** (Analisis › Selektivitas Multi-Target…): membandingkan afinitas ligan ke beberapa target protein secara simultan. Menghasilkan matriks ligan × target berbasis SMILES kanonik, normalisasi Z-score relatif per target, klasifikasi otomatis profil farmakologis (Selektif Kuat, Semi-selektif, Promiskuitas obat), serta indeks gap selektivitas ΔΔG (`selektivitas.py`, `dialog_selektivitas.py`).
- **Interpretasi Hasil Docking AI (Ollama Enhanced & Expert Engine)** (Analisis › Interpretasi Hasil Docking (AI)…): generator narasi ilmiah otomatis untuk merangkum hasil simulasi docking dalam Bahasa Indonesia baku. Menyediakan mode Ringkasan Eksekutif dan draf Bab Hasil & Pembahasan karya ilmiah/skripsi yang menganalisis validitas RMSD, urutan afinitas ΔG, konstanta inhibisi Ki, Ligand Efficiency, dan jaringan ikatan hidrogen/hidrofobik. Terintegrasi langsung dengan model AI lokal Ollama (jika terpasang) atau fallback mulus ke Mesin Pakar VirmoLab (`asisten.py`, `dialog_asisten.py`).
- **Docking Protein–Protein (PPI) & Analisis Antarmuka** (Analisis › Docking Protein–Protein…): modul docking dan telaah interaksi makromolekul protein-protein. Prediksi residu permukaan/antarmuka aktif berbasis Solvent Accessible Surface Area (SASA Shrake-Rupley), evaluasi kompleks antarmuka (kontak atom berat, ikatan hidrogen antar-rantai, jembatan garam, Buried Surface Area / ΔSASA, dan skor komplementaritas), klastering pose rigid-body berdasarkan RMSD C-alfa, integrasi antrean ClusPro 2.0, serta visualisasi kompleks di viewer 3D (`ppi.py`, `dialog_ppi.py`).

## [0.9.7] - 11 Oktober 2026

### Baru
- **Synthetic Accessibility Score (SAScore)** (Ertl & Schuffenhauer 2009): perhitungan kemudahan sintesis berbasis fragmen dan kompleksitas molekul RDKit. Nilai 1 (sangat mudah) hingga 10 (sangat sulit). Tersedia di tab Sifat Ligan, variabel korelasi tab Statistik, tabel laporan HTML/PDF, dan komponen uji mandiri (`sascore.py`).
- **Multi-Parameter Optimization (MPO) & Radar Chart** (Analisis › Multi-Parameter Optimization (MPO) & Radar…): integrasi parameter fisikokimia, drug-likeness (QED), SAScore, dan afinitas docking ΔG menjadi satu skor desirability (0–100). Preset bawaan mencakup Oral Drug-like MPO dan CNS-MPO (Pfizer, Wager et al. 2016), dilengkapi grafik laba-laba/radar SVG interaktif per ligan yang dapat disalin dan diekspor (`mpo.py`, `dialog_mpo.py`, `grafik.radar_svg`).
- **Kalkulator Pengujian Laboratorium Basah (Wet-Lab Planner)** (Analisis › Kalkulator Uji Lab Basah (Wet-Lab Planner)…): menjembatani hasil docking in silico ke eksperimen in vitro basah. Menghitung prediksi Ki dan IC50 (Cheng-Prusoff), seri pengenceran bertingkat (1:3, 1:2, semi-log), kalkulasi volume pemipetan dan batas toleransi pelarut DMSO (≤ 0.5%), denah visual pelat mikro (96-well / 384-well / 48-well / 24-well) dengan triplo/duplo dan sumur kontrol (pelarut, positif, blanko), serta ekspor draf protokol pemipetan dan berkas CSV (`labplanner.py`, `dialog_labplanner.py`).

### Diperbaiki
- **Diagram interaksi 2D**: ikatan rangkap dengan stereo tak tentu (mis. C=N hidrazon dari SMILES tanpa E/Z) tidak lagi digambar sebagai ikatan silang yang tampak cacat; E/Z dan R/S kini diambil dari geometri pose 3D. Lingkaran residu tidak lagi menutupi label atom berhuruf (H₂N, NH, OH) (`diagram2d.py`).

## [0.9.6] - 10 Oktober 2026

### Baru
- **Penelitian lanjutan** (Analisis › Penelitian lanjutan…): konservasi residu dari FASTA (penjajaran lokal, diwarnai lewat B-faktor), sumbangan Vina per residu dan pemindaian alanin pada fungsi skor, penggabungan job (ensemble, selektivitas, kovalen lawan non-kovalen), umpan berpadanan sifat, regangan MMFF, kemiripan bentuk 3D, tautomer dan stereoisomer, enumerasi gugus R, bioisoster, telaah air penjembatan dan kofaktor, syarat interaksi, mutasi residu, sunting ligan di kantong, film trajektori MD, paket OpenMM untuk server, draf skripsi, BibTeX, dan pemeriksa figur (dpi, huruf, buta warna).
- Wizard reseptor: opsi mempertahankan air penjembatan dan kofaktor.
- Gugus reaktif kovalen tambahan: isotiosianat dan ester aktif pada alkena, beserta catatan reaktivitas.
- Templat **Bahan alam dari satu kelompok**.
- GNINA 1.3.3 dan Boltz 2.2.1 dijalankan lewat WSL (skor ulang CNN dan prediksi pose). Biner Linux-nya tidak ikut installer Windows. Skor GNINA pada reseptor tanpa hidrogen ditandai agar tidak dikutip. Boltz bisa meminta MSA ke ColabFold bila kotaknya dicentang; tanpa itu prediksinya satu sekuens.
- Sunting ligan di kantong kini dilanjutkan dengan minimisasi Vina di tempat (`--local_only`) bila reseptor PDBQT sudah ada.
- Asisten (Bantuan › Asisten…): jawaban dari catatan aplikasi, plus Ollama di komputer sendiri bila sebuah model sudah terpasang. Model tidak diunduh dan tidak dibundel.
- Konservasi bisa mengisi homolog dari BLAST NCBI Swiss-Prot. Persen identitas tetap dihitung lokal. BLAST mengirim sekuens ke NCBI.
- Arti angka (ΔG, skor kovalen, Ki, GNINA, CNNscore, CNNaffinity, RMSD redocking, RMSD Boltz, MM/GBSA) tertulis di tab Hasil, laporan, dan draf skripsi. Pada ringkasan langkah, skor terbaik kovalen tidak lagi disebut ΔG.
- Tab Hasil punya kolom GNINA Affinity (kcal/mol), CNNscore (0–1), dan CNNaffinity (pK). Kolom itu terisi sendiri setelah docking bila GNINA ada di WSL. Bila tidak ada, selnya kosong dan docking tetap selesai.
- Analisis › Seret atom ligan menggeser satu atom di viewer, merapikan ikatan, lalu menilai ulang dengan Vina di tempat bila reseptor PDBQT sudah ada.
- Boltz punya kotak pengaturan penuh (3 daur ulang, 200 langkah, semua rantai protein yang terbuka). Tanpa centang, pengaturan tetap diringkas untuk GPU 6 GB.
- Bila BLAST NCBI masih antre, homolog dicari lewat UniProt, lalu EBI, lalu pencarian sekuens RCSB PDB. Sekuens ikut terkirim. Identitas tetap dihitung lokal. Hasil RCSB bukan Swiss-Prot.
- Proyek contoh HIV-1 protease menyimpan hasil redocking buta MK1 yang sudah diukur: RMSD 1,39 Å, ΔG Vina −11,18 kcal/mol, GNINA Affinity −11,56 kcal/mol. Angka itu bukan docking baru.
- Jendela membuka dalam keadaan dimaksimalkan di area kerja, tanpa melewati tepi layar.
- Paket server menulis `kompleks.gro` dan topologi GROMACS vakum `kompleks.top` (ParmEd). Suku pelarut OBC2 tetap hanya di `sistem_obc2.xml`.
- Analisis › Geser ligan utuh memindahkan seluruh ligan tanpa mengubah bentuknya, lalu menilai ulang dengan Vina di tempat. Seret atom ligan tetap menggeser satu atom.
- Setelah docking, GNINA mengisi 10 ligan berenergi terbaik. Analisis › GNINA untuk sisa ligan menilai yang lain. Bila GNINA tidak ada, docking tetap selesai.
- Nomor BLAST NCBI disimpan di proyek. Tombol ambil hasil tetap bisa dipakai setelah jendela penelitian ditutup.
- Analisis › Syarat jarak menandai pose yang atom beratnya lebih jauh dari residu yang dipilih (misalnya 3,5 Å). Pencarian docking tidak dipaksa mendekat.
- Ctrl+Z dan Ctrl+Y juga mengembalikan atau mengulangi perubahan koordinat ligan.
- Syarat jarak diukur pada semua pose. Baris tabel memakai pose berenergi terbaik yang lolos ambang; pose yang gagal tetap terlihat. Dua residu bisa diisi sekaligus: lolos bila salah satu cukup dekat. Garis putus-putus di viewer menunjukkan pasangan atom terdekat.
- Skor Vina sesudah geser atom atau geser ligan utuh tersimpan sebagai skor lokal di panel Properti. ΔG docking di tabel tidak ditimpa.

### Diubah
- Koordinat 3D ligan dengan cincin ≥ 7 atom memakai torsi makrosiklus ETKDG. Meeko tetap membuat cincin itu fleksibel kecuali kotak “Makrosiklik kaku”.
- Uji mandiri kini mencakup satu pemeriksaan alat penelitian.

## [0.9.5] - 10 Oktober 2026

### Baru
- **Docking kovalen** (Siapkan › Docking kovalen…, atau *Atur…* di langkah 4): pilih residu nukleofil (Cys, Ser, Lys) di dalam grid box; ligan yang punya gugus reaktif diikat secara kimia ke rantai sampingnya dan di-docking sebagai satu aduk dengan metode *tethered* (AutoDock-GPU `--flexres`). Gugus reaktif yang dikenali: akseptor Michael (akrilamida/enon/vinil sulfon), alkuna teraktivasi, α-haloketon/haloasetamida, sulfonil fluorida, nitril, aldehida (termasuk basa Schiff untuk Lys). Dialog menampilkan deteksi per ligan sebelum dijalankan; ligan tanpa gugus reaktif yang cocok dilewati. Rantai samping residu sasaran tampil sebagai objek pose tersendiri dan interaksi dihitung pada posisi itu. Validasi: 6OIM (KRAS G12C–sotorasib) RMSD 1,34 Å dari SMILES.
- Docking kovalen di baris perintah: `VirmoLab-cli dock … --kovalen A:12`.
- **Pencarian struktur RCSB PDB** di dialog Impor: cari dengan nama protein/gen/ligan, saring organisme, "hanya dengan ligan", dan resolusi; VirmoLab menandai ★ struktur terbaik untuk docking (difraksi sinar-X, ada ligan kristal, resolusi terkecil).
- **Templat proyek** dan **proyek contoh HIV-1 protease** yang bisa dibuka sepenuhnya offline (1HSG + 9 inhibitor disetujui + aspirin sebagai kontrol).
- **Urungkan/Ulangi** (Ctrl+Z / Ctrl+Y) untuk grid box dan gaya tampilan.
- **Palet perintah** (Ctrl+K): cari dan jalankan perintah menu mana pun dengan mengetik.
- **Mode Pemula / Ahli**: mode Ahli menyembunyikan panel Langkah dan membuka pengaturan lanjutan.
- **Tur aplikasi** (Bantuan › Tur aplikasi): 9 langkah bagian jendela yang disorot satu per satu.
- **Paket Supplementary** (.zip) untuk publikasi: pose, tabel, parameter tiap job, berkas reseptor/ligan, README, dan SHA-256 tiap berkas.
- **Lapor masalah atau kirim saran…**: mengemas berkas log ke satu .zip untuk dilampirkan.
- **Konsol Python** (Alat › Konsol Python) dan **plugin pengguna** (berkas .py di folder plugin → menu Alat › Plugin); galat plugin ditangkap sehingga tidak menjatuhkan aplikasi.

### Diperbaiki
- Ekspor dan laporan tidak lagi menuliskan jalur berkas lengkap (yang memuat nama pengguna Windows) ke dalam berkas yang dibagikan - kini hanya nama berkas/folder.

### Diubah
- Uji mandiri kini 26 komponen (+ docking kovalen: aduk + flexres Meeko).
- Pose kovalen diperiksa PoseBusters tanpa uji *jarak minimum ke protein* (ikatan kovalen memang lebih pendek daripada kontak van der Waals); 21 uji lainnya tetap dijalankan.

## [0.9.4] - 9 Oktober 2026

### Baru
- **MD & MM/GBSA** (Analisis › MD & MM/GBSA…) dengan OpenMM: protein Amber ff14SB, ligan OpenFF Sage 2.3 dengan muatan parsial OpenFF NAGL (setara AM1-BCC), ion logam Li/Merz. Tiga tingkat sesuai rencana A8a:
 - **Ringan** - minimisasi kompleks + MM/GBSA satu titik (menit, semua laptop);
 - **Sedang** - MD pelarut implisit OBC2 + RMSD/RMSF + MM/GBSA rata-rata;
 - **Lengkap** - MD air eksplisit TIP3P/PME + MM/GBSA banyak frame.
- **Penilaian kemampuan laptop otomatis**: saat dialog pertama dibuka, kecepatan diukur pada kompleks Anda sendiri (implisit & eksplisit, disimpan per perangkat) → perkiraan waktu dan status *Disarankan / Bisa (lama) / Tidak disarankan*; peringatan bila laptop memakai baterai.
- **Jeda & lanjut**: checkpoint tiap ±5 menit; MD bisa dijeda dan dilanjutkan, juga setelah aplikasi ditutup (menutup VirmoLab saat MD berjalan otomatis menjeda dengan checkpoint).
- Hasil: ΔG MM/GBSA (vdW, elektrostatik, GB, SA) ± SD, grafik RMSD/RMSF/MM-GBSA per waktu (SVG/PDF/PNG/TIFF), **interaksi persisten** sepanjang trajektori, berkas kompleks terminimisasi (PDB) dan trajektori zat terlarut (DCD) untuk PyMOL/VMD.
- Kolom **MM/GBSA** di tabel Hasil, variabel MM/GBSA di Statistik, kolom di ekspor CSV/XLSX, serta bagian MM/GBSA, kalimat metode, dan sitasi (OpenMM 8, ff14SB, Sage, OpenFF, OBC, MM/GBSA) di laporan.
- Pose dari docking **residu fleksibel** dipakai lengkap: rantai samping diposisikan seperti di pose.
- Baris perintah: `VirmoLab-cli mmgbsa` (minimisasi, atau `--md` dengan `--pelarut implisit|eksplisit`) dari folder hasil `dock` atau pose SDF → `mmgbsa.csv`; `dock` kini juga menyimpan reseptor ber-H dengan keadaan protonasi docking.

### Diubah
- Uji mandiri kini 25 komponen (+ MD & MM/GBSA OpenMM/OpenFF).
- Dialog Tentang mencantumkan komponen MD dan pemberitahuan hak cipta Hilbert Curve (Rice University) yang diwajibkan lisensi OpenMM.

## [0.9.3] - 9 Oktober 2026

### Baru
- **Protein dari AlphaFold DB** (Siapkan › Protein dari AlphaFold DB…, atau tab *AlphaFold DB* di dialog impor): cari kode UniProt atau nama protein/gen (UniProt, saring organisme), unduh model prediksi terbaru. Protein diwarnai menurut **pLDDT** (pita resmi AlphaFold; juga pilihan warna *pLDDT* di panel Tampilan), ringkasan pLDDT di Properti dan Pesan, ujung N/C tak beraturan (pLDDT < 50) dipangkas otomatis (bisa diatur/dimatikan).
- **Peringatan pLDDT di grid box**: bila residu di area docking model AlphaFold ber-pLDDT rendah, VirmoLab mengingatkan bahwa pose dan ΔG kurang andal.
- **P2Rank untuk model AlphaFold** memakai konfigurasi resmi `alphafold` (tanpa fitur B-factor, yang di model AlphaFold berisi pLDDT).
- **Residu fleksibel** (Siapkan › Residu fleksibel…, atau *Atur…* di langkah Jalankan): pilih 1–8 rantai samping kantong (calon diurutkan menurut jarak ke ligan asli) yang boleh berotasi selama docking - AutoDock-GPU (`--flexres`) dan Vina (`--flex`). Rantai samping tiap pose tampil sebagai objek tersendiri, dan analisis interaksi, PoseBusters, serta laporan memakai posisi rantai samping pada pose itu.
- **Baris perintah `VirmoLab-cli.exe`** (di folder instalasi): `info`, `uji`, `reseptor`, `ligan`, `kantong`, `alphafold`, dan `dock` - satu perintah dari kode PDB/AF-UniProt/berkas sampai `ringkasan.csv` (ΔG, Ki, LE, interaksi, residu kontak) dan `metode.txt` (parameter lengkap + perintah yang bisa diulang) untuk skrip, batch, dan reproduksibilitas.
- Laporan mencantumkan sumber model AlphaFold (entri, versi, pLDDT, residu dipangkas) dan residu fleksibel.

### Diperbaiki
- Peta grid AutoGrid tidak lagi dipakai ulang setelah reseptor berubah dengan tipe atom yang sama (hash reseptor kini ikut diperiksa).

### Diubah
- Uji mandiri kini 24 komponen (+ residu fleksibel, baris perintah).

## [0.9.2] - 9 Oktober 2026

### Baru
- **Wizard preparasi reseptor 4 langkah** (Periksa struktur → Pembersihan → Protonasi & hidrogen → Ringkasan) dengan **pemeriksa kualitas protein**: resolusi, celah rantai, atom berat hilang, konformasi alternatif, residu non-standar, ligan & ion logam.
- **Protonasi berbasis pKa (PROPKA 3 + PDB2PQR)** pada pH pilihan: His → HID/HIE/HIP, Asp/Glu terkubur bisa netral, optimasi jaringan ikatan hidrogen (rotasi OH/SH/NH₃⁺, flip His/Asn/Gln), atom berat yang hilang dilengkapi (residu tidak lagi dibuang). His pengikat ion logam diberi tautomer sesuai geometri koordinasi. Tabel pKa disimpan di `reseptor/pka.csv`.
- **Peta sidik jari interaksi ala ProLIF** (Statistik › Peta sidik jari interaksi): ligan × residu × jenis interaksi + baris frekuensi.
- **Kemiripan, ruang kimia, farmakofor** (Analisis): Tanimoto ECFP4/FCFP4/MACCS/pasangan atom/farmakofor 2D, klaster Butina, peta ruang kimia (MDS/PCA), cari ligan mirip (termasuk SMILES acuan), **farmakofor 3D pose aktif** (tombol P) dan **farmakofor bersama** pose teratas (+ skrip PyMOL).
- **ChEMBL**: cari target dari ID PDB/UniProt/nama, ambil aktivitas (pChEMBL), impor senyawa aktif sebagai ligan, dan **korelasi ΔG docking vs pChEMBL**; pChEMBL tersedia sebagai variabel di tab Statistik.
- **Pustaka ligan**: 3.205 obat disetujui (offline, dari ChEMBL), ±700 ribu bahan alam **COCONUT 2.0** (unduh sekali, lalu offline; saring kelas, sifat, kemiripan), dan tautan ZINC22.
- **Gambar ligan dengan Ketcher** (offline) - juga *Edit struktur di Ketcher* dari klik kanan ligan.
- **Prediksi ADMET (ADMET-AI)**: 30 sifat absorpsi, distribusi, metabolisme (CYP), ekskresi, toksisitas (hERG, Ames, DILI), berjalan offline di proses terpisah.
- **Antarmuka bahasa Inggris** (Tampilan › Bahasa / Language; berlaku setelah aplikasi dibuka ulang).

### Diubah
- Uji mandiri kini 22 komponen.

## [0.9.1] - 9 Oktober 2026

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

## [0.9.0] - 8 Oktober 2026

### Baru
- **Uji & Grafik** ala Prism: panel Format (klik elemen grafik), gaya tersimpan, patah sumbu, skala log, ROC/AUC, tabel kontingensi (Fisher/χ²), IC₅₀ 4PL.
- **Komposer figur** panel A/B/C ukuran jurnal (PDF/SVG/TIFF 600 dpi).
- **Laporan** PDF, Word (.docx) yang bisa disunting, dan HTML interaktif dengan penjelajah 3D.
- **Video 3D** MP4 Full HD–4K, GIF/WebP, dan presentasi sinematik (zoom → putar → sorot interaksi).
- **Tampilan 3D**: label residu tajam di layar HiDPI dan anti-tabrakan, garis tepi, bayangan sekitar (AO), kabut kedalaman yang bisa diatur.
- **Deteksi kantong P2Rank** untuk protein tanpa ligan asli.
- Sifat ligan & BOILED-Egg, statistik & korelasi, kontrol kualitas pose PoseBusters, protonasi Dimorphite-DL, kontribusi energi per atom, sidik jari interaksi.
- Antarmuka pemula: halaman sambutan, panel langkah 1–5, menu berbahasa Indonesia dengan keterangan.
