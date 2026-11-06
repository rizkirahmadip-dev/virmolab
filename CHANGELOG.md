# Catatan perubahan VirmoLab

Format: setiap versi berisi **Baru**, **Diperbaiki**, dan **Diubah**. Versi 0.x adalah pra-rilis.

## [1.9.2] - 6 November 2026

Kesiapan pemakaian internasional, bantuan di dalam aplikasi, dan empat perbaikan dari laporan
pengguna pertama di luar laptop pengembang.

### Baru
- **Pemilih bahasa ID | EN di bilah alat**, di sebelah tombol tema. Menggantinya menawarkan **Mulai ulang
  sekarang**, yang menutup jendela lewat pemeriksaan biasa (docking atau MD yang berjalan tetap ditanyakan)
  lalu menjalankan VirmoLab lagi.
- **Installer meneruskan bahasa yang dipilih penggunanya** ke aplikasi lewat `HKCU\Software\VirmoLab`.
  Sebelumnya installer berbahasa Inggris tetap membuka aplikasi berbahasa Indonesia.
- **Bahasa bawaan mengikuti locale Windows** pada pemasangan yang belum pernah menyetelnya — terutama untuk
  versi portable, yang tidak melewati installer.
- **Bantuan kontekstual**: `F1` di dialog mana pun membuka bagian panduan untuk fitur itu, dan
  **Bantuan › Panduan fitur** mendaftar 38 alat dengan tautan langsung ke bagiannya. Dipasang lewat penyaring
  kejadian aplikasi, sehingga berlaku untuk seluruh dialog tanpa mengubah tata letaknya.
- **Dokumen instalasi berbahasa Inggris** (`docs/instalasi_en.html`); antarmuka Inggris membuka versi Inggris
  sebuah dokumen bila tersedia.
- **65 tooltip parameter baru** di 21 dialog, menjelaskan nilai yang wajar dan akibat mengubahnya — bukan
  mengulang rentang yang sudah tertulis di label.

### Diperbaiki
- **Dialog Sunting di kantong (3D) gagal dibuka sama sekali** untuk ligan dengan nitrogen terprotonasi
  (lazim pada pH fisiologis, termasuk ligan contoh MK1): `Chem.RemoveHs` menolak sanitasi ulang dengan
  `AtomValenceException`, di `core/sunting3d.py` dan di diagram 2D dialognya.
- **Setelah docking selesai, pose terbaik dimuat tetapi viewport tetap tersembunyi** di balik tab Tabel hasil,
  sehingga pengguna mengira visualisasinya belum ada dan mencarinya dengan klik dua kali. Viewport kini dibawa
  ke depan beserta pesan yang menunjuk ke tab Hasil.
- **Memuat pose menuntut klik dua kali.** Satu klik pada baris tabel hasil kini sudah menampilkan posenya;
  klik dua kali tetap bekerja.
- Antarmuka Inggris: 100 teks yang masih berbahasa Indonesia diperbaiki, termasuk **seluruh modul farmakologi
  jaringan**. Penyebabnya tiga: teks yang diberikan lewat konstruktor widget tidak pernah melewati lapisan
  terjemahan, sepuluh entri kamus berisi terjemahan setengah jadi, dan label figur siap publikasi tidak memakai
  i18n sama sekali — figur yang ditempel ke naskah berbahasa Inggris tetap bersumbu Indonesia.
- **Tab Diagram 2D tidak punya cara mengganti senyawa.** Satu-satunya jalan adalah kembali ke tab Hasil,
  mengklik baris lain, lalu kembali lagi. Kini ada pemilih ligan di bilah atas tab itu sendiri, lengkap
  dengan ΔG tiap senyawa (laporan pengguna).
- **Catatan "Belum divalidasi (redocking)." terbaca seperti galat** — menyebut kekurangan tanpa menyebut
  tindakannya, dan tanpa mengatakan bahwa validasi itu opsional (laporan pengguna).
- **Impor banyak senyawa dari PubChem ditolak seluruhnya dengan 503.** PubChem membatasi 5 permintaan
  per detik; aplikasi menjalankan enam unduhan sekaligus, dan tiap senyawa dapat memakan dua permintaan.
  Laju kini ditahan per host untuk seluruh aplikasi, 503 dan 429 dicoba lagi, dan pekerjanya diturunkan
  ke tiga.
- `dev/uji_alur.py` menimpa widget `JendelaUtama.langkah` dengan pencacah integer, sehingga uji itu selalu gagal.

## [1.9.1] - 5 November 2026

Rilis perbaikan. Satu kriteria ilmiah yang dapat menyesatkan pembacaan hasil diperbaiki, pemakaian
layanan NCBI dibuat patuh pada pedoman resminya, dan metadata sitasi dilengkapi DOI.

### Diperbaiki
- **Keyakinan konsensus penargetan balik memakai ambang mutlak, bukan peringkat** (`core/target_balik.py`).
  Syarat lama "10 besar kedua jalur" tidak bermakna pada panel yang memang kecil: panel antibakteri berisi
  9 target dan antiinflamasi 8, sehingga setiap target otomatis memenuhinya dan dilabeli berkeyakinan
  **tinggi** — termasuk target dengan z-skor −0,4 dan kemiripan Tanimoto 0,17. Label itu juga dipakai untuk
  memilih target yang dikirim ke tab Jaringan & jalur, jadi kesalahannya merambat ke analisis berikutnya.
  Keyakinan kini dinilai pada besaran yang benar-benar diukur: **tinggi** bila target mencapai z ≤ −2
  sekaligus 3 besar jalur struktur *dan* kemiripan Tanimoto ≥ 0,40 pada jalur ligan, **sedang** bila hanya
  satu jalur memenuhi, **rendah** bila tidak satu pun. Ambangnya sama dengan yang dipakai pada analisis
  terbit. Paragraf metode Indonesia dan Inggris menyebutkan ambang itu beserta alasan pemilihannya, dirakit
  dari konstanta yang sama sehingga tidak dapat menyimpang dari kodenya.
  **Hasil penargetan balik dari versi sebelumnya perlu dibaca ulang:** sebagian label "tinggi" akan turun.
- **Pemakaian API BLAST NCBI dibuat patuh** (`core/konservasi.py`). Satu pekerjaan diperiksa tiap 12 detik,
  padahal NCBI meminta tidak lebih sering dari sekali semenit, dan pemeriksaan pertama langsung menyusul
  pengiriman. Pemanggil yang melanggar dipindahkan ke antrean lambat atau diblokir — artinya konservasi
  kantong berhenti bekerja. Kini jeda 10 detik sebelum pemeriksaan pertama, 60 detik antar pemeriksaan
  (jeda yang lebih kecil dinaikkan), dan tiap permintaan menyebut `tool=VirmoLab` sesuai pedoman NCBI.
  Akibatnya pencarian homolog terasa lebih lambat; itu harga kepatuhan, bukan kemunduran.

### Diubah
- **Metadata sitasi memuat DOI.** Tiap rilis kini diarsipkan di Zenodo. `CITATION.cff` memuat DOI konsep
  10.5281/zenodo.23978036 (selalu menunjuk versi terbaru) dan ORCID penulis; dialog **Bantuan › Lisensi dan
  cara mengutip** menampilkan DOI itu di contoh sitasinya, lengkap dengan penjelasan beda DOI konsep dan DOI
  versi. README memperoleh badge DOI.
- **Catatan lisensi melengkapi layanan daring yang dipanggil aplikasi.** CTD (interaksi senyawa-gen, baru di
  1.9.0), Wikidata/LOTUS, dan NCBI BLAST kini tercatat di `LISENSI_PIHAK_KETIGA.txt` beserta lisensi dan
  sitasinya — termasuk syarat CTD yang membatasi pemakaian komersial. Skrip baru `dev/cek_sumber_daring.py`
  menjaga daftar itu tetap sepadan dengan host yang benar-benar dihubungi kode; `dev/cek_lisensi.py` hanya
  memeriksa isi build sehingga tidak pernah dapat menangkap celah ini.

### Diperbaiki (dari uji pemasangan)
- **Bilah status menampilkan "RAM 0 GB" dan nama CPU kosong** pada komputer yang PATH-nya dipangkas
  (`core/env.py`). `powershell` dipanggil lewat nama telanjang, padahal `powershell.exe` tidak berada di
  `System32` melainkan di `System32\WindowsPowerShell\v1.0`; deteksi perangkat lalu gagal tanpa pesan.
  Jalurnya kini disusun mutlak dari `%SystemRoot%`, dan bila tetap gagal alasannya muncul di panel pesan.
- **Copot pemasangan meninggalkan kunci registri kosong** `HKCU\Software\Classes\.vmdbackup`
  (`installer/virmolab.iss`). `uninsdeletevalue` hanya menghapus nilai di dalam kunci; kini ditambah
  `uninsdeletekeyifempty` pada asosiasi `.vmdbackup` dan `.pdbqt`.

## [1.9.0] - 5 November 2026

Farmakologi jaringan masuk sebagai alur kerja kedua di samping docking. Satu tanaman kini bisa ditelusuri
dari daftar senyawanya sampai jalur biologis dan penyakit tanpa berpindah-pindah antara KNApSAcK, PubChem,
ADMETLab, SwissTargetPrediction, CTD, GeneCards, jvenn, dan STRING — delapan tahap yang sebelumnya
dikerjakan manual lewat tujuh laman web dan Excel. Docking tetap ada di belakangnya sebagai pemeriksaan
struktural atas pasangan senyawa-target yang sudah terpilih.

Selain itu: grid box docking sepenuhnya dapat diatur, tampilan jaringan menjadi yang pertama bisa
ditelusuri di VirmoLab, dan satu cacat lama diperbaiki — pengambilan senyawa tanaman obat yang belum pernah
berhasil sejak 1.8.0.

### Baru
- **Farmakologi jaringan** sebagai alur kerja tersendiri, dengan menu **Jaringan** di bilah menu (Ctrl+Shift+J) dan pilihan *Farmakologi Jaringan* di pemilih alur panel Langkah. Seluruh rantai senyawa › target › jalur › penyakit dikerjakan dalam satu jendela tujuh tahap (`ui/dialog_farmakologi.py`, `core/farmakologi.py`), tanpa lagi berpindah-pindah antara tujuh laman web dan Excel.
  - **1 Senyawa**: dari takson tanaman obat (LOTUS/Wikidata, COCONUT), dari ligan proyek, atau impor CSV/TSV berisi kolom SMILES — mis. ekspor KNApSAcK yang sudah dilengkapi SMILES dari PubChem. Pemisah kolom dan nama kolom dikenali otomatis.
  - **2 Saring ADMET**: aturan Lipinski dan peringatan PAINS dari RDKit, ditambah ambang HIA, bioavailabilitas oral, DILI, hERG, dan Ames bila ADMET-AI terpasang. Senyawa yang belum punya nilai ADMET tidak digugurkan karena alasan itu; alasannya dicatat untuk tiap senyawa.
  - **3 Target senyawa**: kemiripan ligan ChEMBL (ECFP4, pChEMBL ≥ 6) dan/atau interaksi senyawa–gen terkurasi literatur dari CTD (`core/ctd.py`, Batch Query, kolom dibaca berdasarkan nama sehingga tahan perubahan skema). Tabel target juga bisa diimpor dari berkas.
  - **4 Gen penyakit dan irisan**: pencarian penyakit dan gen terasosiasi lewat Open Targets Platform (`jaringan.cari_penyakit`, `jaringan.target_penyakit`), atau impor CSV ekspor GeneCards/DisGeNET/OMIM milik pengguna sendiri. Irisannya digambar sebagai diagram Venn (`core/venn.py`, SVG 2 dan 3 himpunan, palet aman buta warna).
  - **5 Jaringan PPI**: tepi STRING pada ambang yang dapat diatur, tampilan jaringan **interaktif** pertama di VirmoLab (`ui/widget_graf.py`: geser, perbesar, klik simpul untuk menyorot tetangganya), dan peringkat protein hub memakai Maximal Clique Centrality cytoHubba di samping derajat, betweenness, dan closeness. Ekspor GraphML (Cytoscape/Gephi), CSV tepi, dan PNG.
  - **6 Jalur**: pengayaan Reactome atau GO-BP dengan uji hipergeometrik satu sisi dan koreksi Benjamini-Hochberg, lengkap dengan grafik batang 15 jalur teratas.
  - **7 Laporan**: kartu ringkasan tiap tahap, paragraf metode siap tempel dalam Bahasa Indonesia dan Inggris, serta ekspor seluruh keadaan alur ke JSON untuk lampiran suplemen.
  - Keadaan alur disimpan di dalam berkas proyek (kunci `farmakologi` pada `proyek.json`), dan tiap sumber data daring dicatat sebagai jejak sehingga ikut ke paragraf metode dan laporan.
- Uji mandiri: tiga butir baru — *Diagram Venn*, *Alur farmakologi jaringan* (penyaringan, irisan, nilai MCC yang dihitung tangan, paragraf metode), dan *CTD (pengurai interaksi senyawa–gen)*; seluruhnya tanpa internet.

- **Laporan lengkap otomatis** (tahap 8, `core/laporan_jaringan.py`): sepuluh bagian yang dirakit ulang tiap kali ada tahap selesai — ringkasan angka, paragraf metode, daftar senyawa, hasil penyaringan beserta alasan pengguguran, target per senyawa, gen penyakit dan irisannya, topologi jaringan dan tabel protein hub, tabel jalur, Keterbatasan enam butir, serta tabel sumber data beserta versi dan lisensinya. Diekspor ke PDF, Word, atau HTML.
- **Statistik memakai mesin uji yang sudah ada** (`core.uji`), bukan hitungan sendiri, sehingga pemilihan uji, pemeriksaan asumsi, ukuran efek, dan kalimat metodenya sama dengan bagian aplikasi yang lain:
  - Perbandingan sifat fisikokimia senyawa yang lolos penyaringan dengan yang gugur (Welch atau Mann-Whitney, dipilih otomatis dari uji normalitas) untuk lima sifat: massa molekul, WLOGP, TPSA, QED, SA Score. Menjawab pertanyaan "penyaringan ini sebenarnya membuang apa".
  - Ringkasan topologi jaringan PPI: kerapatan, sebaran derajat, koefisien klaster, jumlah komponen, dan protein terpencil — lengkap dengan paragraf pembacaannya, bukan sekadar daftar angka.
- **Tombol Lanjut yang mengerti tahapnya**: menunjuk tahap berikutnya dan mati bila tahap sekarang belum ada isinya, dengan alasan di tooltip. Di tahap terakhir berubah menjadi **Bawa ke docking molekuler…**, yang menyiapkan hanya senyawa yang mengenai target hub sebagai ligan lalu memindahkan jendela utama ke alur docking — urutan farmakologi jaringan memang menempatkan docking di belakang, sebagai pemeriksaan struktural atas pasangan yang sudah terpilih.
- **Tab Figur** (tahap 7): lima gambar siap publikasi dari keadaan alur, dengan pratinjau dan ekspor SVG vektor atau raster ber-DPI (96–1200), satu per satu atau seluruhnya sekaligus ke satu folder.
  - *Hub melingkar* (`core/figur_jaringan.lingkar_hub`) — protein paling sentral disusun melingkar dan diwarnai menurut peringkat MCC, padanan terbuka untuk gambar cytoHubba yang lazim di naskah farmakologi jaringan.
  - *Bubble plot jalur* (`gelembung_jalur`) — sumbu x rasio gen, ukuran titik jumlah gen, warna −log₁₀(q), lengkap dengan dua keterangan dan angka di samping tiap titik agar tetap terbaca saat dicetak hitam-putih.
  - *Batang jalur* (`batang_jalur`), *diagram Venn*, dan *jaringan berlapis* memakai modul yang sudah ada.
  - Besaran berurutan memakai satu rona terang-ke-gelap dari ramp biru yang sudah divalidasi (pita terang, lantai kroma, pemisahan buta warna, kontras terhadap latar), bukan pelangi; peringkat teratas selalu yang tergelap.

### Diubah
- **Grid box docking lebih rinci dan sepenuhnya dapat diatur.** Kolom **Tepi di sekeliling ligan (Å)** menggantikan angka yang dulu dipatok di dalam kode (8 Å untuk *Sesuaikan ke ligan terpilih*, 10 Å untuk *Pusat di ligan asli*); label tombolnya ikut menampilkan angka yang sedang berlaku. Centang **Samakan ketiga sisi** menjaga kotak tetap kubus saat satu sisi diubah. Di bawah kotak isian kini tertulis **batas kotak** (rentang minimum–maksimum tiap sumbu) dan **volume**, untuk mencocokkan kotak dengan kantong di viewport dan memperkirakan lama pencarian. Spasi grid dan tiap kendali lain mendapat keterangan yang menjelaskan akibat perubahannya.
- Angka di panel Area kini memakai koma desimal dan tanda minus yang benar, seragam dengan bagian aplikasi yang lain.

### Diperbaiki
- **Senyawa tanaman untuk farmakologi jaringan ikut masuk sebagai ligan docking.** Tombol *Senyawa tanaman obat…* memakai jalur impor ligan, sehingga satu takson memasukkan ratusan objek ke panel Objek, membuatkan konformasi 3D untuk semuanya, dan memenuhi proyek dengan ligan yang belum tentu akan didocking (*Curcuma zedoaria*: 108 objek, 4096 atom). Dialog senyawa tanaman kini punya mode kedua yang hanya memulangkan nama dan SMILES; struktur 3D baru dibuat saat senyawanya benar-benar dibawa ke docking.
- **Keadaan alur hilang saat jendela ditutup.** Seluruh VirmoLab menyimpan sendiri, tetapi keadaan alur hanya ditulis saat tombol ditekan — satu-satunya tempat yang membuang pekerjaan diam-diam, dan tahap target bisa memakan belasan menit. Kini tiap tahap yang selesai menyimpan sendiri; bila belum ada proyek terbuka, pengguna diberi tahu di tahap pertama yang menghasilkan sesuatu.
- **Tampilan jaringan tidak terbaca karena label diborong dan ikut diperbesar.** Tiga pembetulan: label kini berukuran tetap di layar (`ItemIgnoresTransformations`) sehingga jaringan kecil tidak lagi menghasilkan tulisan raksasa; label diberikan secara terpilih menurut prioritas (simpul terpilih dan tetangganya, lalu derajat tertinggi) dengan yang bertabrakan disembunyikan dan dihitung ulang tiap kali perbesaran berubah; dan tiap label memakai bayangan warna latar di belakangnya agar tetap terbaca saat melintasi tepi. Nama lengkap selalu tersedia di tooltip.
- Keterangan warna (legenda) kini selalu ada di pojok tampilan jaringan bila ada lebih dari satu jenis simpul — identitas tidak boleh bergantung pada pencocokan warna saja.
- Tata letak jaringan memakai Kamada-Kawai untuk graf sampai 60 simpul (persilangan tepi lebih sedikit, jarak lebih merata) dan jarak antarsimpul kini naik seiring jumlahnya, bukan makin rapat.
- **Protein tanpa tepi PPI muncul di tabel hub dengan nilai nol.** Protein terpencil bukan hub menurut definisi apa pun; kini dibuang dari peringkat dan jumlahnya dilaporkan terpisah beserta namanya, karena ketiadaan tepi bisa berarti ambang STRING-nya yang terlalu tinggi.

Lima hal berikut ketahuan saat alur dijalankan ujung ke ujung dengan jaringan hidup (*Curcuma longa* terhadap *colorectal cancer*, mengikuti contoh modul BBB NET):
- **"Ambil senyawa" di dialog Senyawa dari tanaman obat selalu gagal** dengan `TypeError: 'Event' object is not callable` begitu takson yang dipilih punya rujukan artikel. `ui/dialog_tanaman.py` mengirim `threading.Event`, sedangkan `core/tanaman.py` memanggilnya seperti fungsi. Keduanya masuk pada commit yang sama, jadi jalur ini belum pernah berhasil sejak 1.8.0. Diperbaiki dengan `tanaman.dibatalkan()` yang menerima Event, fungsi, atau None — pola yang sudah dipakai `core/generatif.py`, `core/xtb.py`, dan `core/farmakofor.py`.
- **Nama senyawa kembar menyatu dan salah satunya kehilangan target.** Peta target berkunci nama senyawa, padahal LOTUS memulangkan nama yang sama untuk stereoisomer dan tautomer berbeda (kunyit: dua `desmethoxycurcumin`, dua `bisdemethoxycurcumin`). Nama kini dibuat unik dengan akhiran berangka saat ditambahkan.
- **Sumber senyawa tidak masuk paragraf metode.** Kolom di tahap 1 hanya dibaca saat menyimpan proyek, sehingga paragraf metode memakai teks pengganti "sumber senyawa" walau penggunanya sudah mengisi. Kini dibaca setiap kali ringkasan disegarkan.
- **Paragraf metode Inggris kemasukan teks Indonesia** pada bagian sumber target ("assigned by kemiripan ligan ChEMBL…"). Sumber target kini disimpan sebagai kunci, bukan kalimat, dan diterjemahkan saat paragraf dirakit.
- **Daftar gen penyakit terpotong tanpa pemberitahuan.** Open Targets dibatasi 500 gen teratas; bila hasilnya pas sebanyak batas, gen di bawahnya tidak pernah diadu dengan target senyawa sehingga irisannya kehilangan anggota. Batasnya kini dapat diatur dan keadaan terpotong diberitahukan di tempat.
- Satu nama senyawa panjang (nama IUPAC bahan alam bisa lebih dari 70 huruf) melebarkan kanvas jaringan sehingga seluruh graf mengecil saat dipaskan; label di gambar kini dipotong pada 26 huruf dengan nama utuh tetap di tooltip.

### Diubah
- GeneCards sengaja tidak dihubungi otomatis: lisensinya berbayar dan melarang pengambilan otomatis. Jalurnya adalah pengguna mengunduh sendiri lalu mengimpor berkasnya; Open Targets dipakai sebagai sumber gen penyakit yang terbuka.

## [1.8.0] - 25 Oktober 2026

Rilis publik pertama. Alat Linux lanjutan kini dipasang dari dalam aplikasi, dan tidak ada lagi pesan yang menyuruh
pengguna menjalankan skrip yang tidak ikut installer.

### Baru
- **Pasang alat lanjutan (WSL)** (Alat › Pasang alat lanjutan (WSL)…; `core/alat_wsl.py`, `ui/dialog_alat_wsl.py`). Dua paket: *Docking GPU & RBFE* (Uni-Dock 1.2, OpenFE 1.13; ± 15 GB, ± 10 menit) dan *Co-folding & skor CNN* (Boltz-2 2.2.1 beserta bobotnya, GNINA 1.3.3; ± 17 GB, ± 14 menit), diukur pada pemasangan dari nol ke distro Ubuntu 26.04 bersih.
  - Prasyarat diperiksa dalam satu panggilan WSL: versi Windows, WSL dan distro, WSL 2, WSL dapat berjalan (termasuk `ERROR_NO_SYSTEM_RESOURCES`), GPU NVIDIA, ruang disk di drive Windows tempat disk virtual WSL berada (bukan ukuran virtual ±1 TB yang dilaporkan `df`), curl/tar/python3, internet, dan pengguna Linux. Tiap butir yang gagal punya tombol perbaikan: *Pasang WSL…* lewat persetujuan administrator, *Buka terminal Ubuntu* dengan perintah `apt` sudah tersalin, atau *Salin perintah*. Bila semua lulus, prasyarat diringkas menjadi satu baris.
  - Tanpa GPU NVIDIA: Uni-Dock dan GNINA (CUDA saja) dilewati, OpenFE dan Boltz-2 tetap dipasang dengan peringatan "sangat lambat". Bila ada lebih dari satu distro, distro dipilih di dialog dan dipakai semua alat lanjutan.
  - Skrip pemasang dikirim lewat stdin, jadi folder aplikasi berspasi atau ber-huruf non-ASCII tidak masalah. Kemajuan per langkah, waktu, dan log tampil langsung dan disimpan di `log/alat_wsl_<paket>.log`. *Hentikan* mematikan seluruh pohon proses di dalam WSL (diuji: < 1 detik), dan *Pasang* lagi melanjutkan dari unduhan yang tersimpan. Sesudah sukses, tombol fitur langsung aktif tanpa membuka ulang aplikasi.
  - Uji: `dev/uji_alat_wsl.py` (42 kasus keluaran WSL tiruan, penanda langkah dicocokkan dua arah dengan skrip) dan `dev/uji_alat_wsl_gui.py [--en]` (WSL sungguhan, skrip tiruan: sukses, gagal internet, dan Hentikan).
- Fitur yang membutuhkan alat WSL yang belum terpasang menawarkan *Pasang sekarang…* (docking Uni-Dock, co-folding, docking peptida) atau tombol *Pasang OpenFE…* / *Pasang Boltz-2…* di dialog RBFE dan panel co-folding.
- Uji mandiri: butir baru "Skrip alat WSL" (tiga skrip ikut build, berakhiran LF, sintaksis bash sah; 58 butir).

### Diperbaiki
- **Unduh bobot Boltz-2 gagal di distro baru**: `download_boltz2()` mengandaikan `~/.boltz` sudah ada. Unduhan yang putus juga meninggalkan berkas terpotong yang dianggap lengkap pada percobaan berikutnya. Kini tiap berkas diunduh ke `.part`, ukurannya dicocokkan dengan Content-Length, dicoba ulang hingga empat putaran, dan `mols.tar` diekstrak ke folder sementara.
- Pemasang OpenFE/Uni-Dock gagal di Ubuntu 26.04 bersih karena `bzip2` tidak ada; micromamba kini diekstrak dengan Python bila perlu. Arsip `.conda` (± 4,5 GB) dihapus sesudah pemasangan sukses.
- Label keterangan yang berganti gaya (muted → peringatan/info) kehilangan padding sehingga teks menempel ke garis tepinya, di tujuh dialog (alat WSL, glikosida, QSAR, RBFE, rescore ML, sunting 3D, pembelajaran aktif). Polish ulang Qt tidak menghitung ulang margin; kini `kit.gaya_ulang()` mengirim peristiwa StyleChange.
- Memilih pose memanggil WSL secara sinkron untuk memeriksa Boltz-2 setiap kali. Status GNINA dan Boltz kini disimpan (hasil "belum ada" hanya 60 detik) dan disegarkan sesudah pemasangan.

### Diubah
- **Siap dirilis ke publik**: README ditulis ulang (unduh dan verifikasi SHA-256, kebutuhan sistem, daftar kemampuan, alat lanjutan, privasi, cara melapor, cara mengutip, ringkasan bahasa Inggris), `SECURITY.md` dan templat issue GitHub ditambahkan, dan tangkapan layar dokumentasi dibuat ulang dari folder kerja netral sehingga tidak lagi memperlihatkan jalur folder pengembangan.
- **Privasi dinyatakan terbuka**: bagian baru di README dan panduan pengguna (Bantuan › Panduan › Privasi) merinci satu-satunya empat hal yang menghubungi internet — unduhan yang diminta pengguna, peladen MSA ColabFold bila dicentang, pemeriksaan pembaruan (dapat dimatikan), dan pemasang alat WSL — serta tempat penyimpanan proyek, log, dan pengaturan.
- **Lisensi**: tawaran kode sumber GPL kini menunjuk repositori publik dan arsip kode sumber tiap tag rilis; alat Linux yang diunduh atas permintaan pengguna (Uni-Dock, OpenFE, GNINA, Boltz-2, micromamba, uv, PyTorch) dicatat beserta lisensi dan sumber unduhannya; attrs, MarkupSafe, dan tqdm yang ikut terbundel sebelumnya belum tercatat. Alat baru `dev/cek_lisensi.py` membandingkan catatan lisensi dengan isi build (paket, versi, program, berkas lisensi yang dirujuk) — sekarang bersih.
- **Sitasi**: `CITATION.cff` memakai nama penulis sebenarnya, versi 1.8.0, dan `url` ke domain yang belum dimiliki dihapus; dialog Bantuan › Lisensi dan cara mengutip menampilkan contoh sitasi VirmoLab yang siap disalin.
- Enam pesan yang menunjuk `build_tools/pasang_*.sh` (skrip yang tidak ikut installer) kini menunjuk Alat › Pasang alat lanjutan (WSL).
- Panduan instalasi: bagian baru *Alat lanjutan (opsional, lewat WSL)*; folder bawaan installer dibetulkan (`%LOCALAPPDATA%\Programs\VirmoLab`, per pengguna, tanpa hak admin). Mengatasi masalah: lima gejala pemasangan alat lanjutan.

## [1.7.0] - 24 Oktober 2026

Rilis fitur untuk penelitian bahan alam: perbandingan glikosida–aglikon yang adil terhadap ukuran molekul, ringkasan
konservasi residu kantong, dan peringatan tegas bila model QSAR dipakai di luar domainnya. Seluruh 31 dialog analisis
diaudit otomatis untuk teks terpotong dalam bahasa Indonesia dan Inggris.

### Baru
- **Konservasi residu kantong** (Penelitian lanjutan › Konservasi residu; `core/konservasi.py`): setelah persen identitas dihitung, residu rantai yang atomnya ≤ 5 Å dari pose atau ligan terpilih diringkas, yaitu jumlah residu, identitas rata-rata kantong dibanding seluruh rantai, dan residu kantong yang paling kurang terkonservasi. Inilah angka yang dipakai untuk argumen selektivitas. Diuji pada 1HSG dengan homolog bermutasi yang diketahui (`dev/uji_konservasi_kantong.py [--gui]`): kantong MK1 16 residu, dan Asp25, Gly48, Ile50 yang dimutasi muncul sebagai yang paling kurang terkonservasi.
- **Glikosida dan aglikon** (Analisis › Sifat ligan dan desain › Glikosida dan aglikon…; `core/glikosida.py`, `ui/dialog_glikosida.py`):
  - Unit gula siklik (piranosa/furanosa, kriteria diadaptasi dari Sugar Removal Utility, Schaub dkk. 2020) dikenali pada ligan proyek dan disorot pada diagram 2D; ikatan O-, N-, S-glikosidik dan ester glikosil diputus pada karbon anomerik dengan heteroatom penghubung tetap pada aglikon, seperti hidrolisis enzimatik. C-glikosida tidak dipotong; oligosakarida, tanin terhidrolisis, dan aglikon < 6 atom berat ditandai.
  - Aglikon yang belum ada ditambahkan ke proyek dengan satu klik, siap didocking dengan reseptor dan kotak yang sama.
  - Pasangan glikosida–aglikon hanya dibandingkan bila keduanya didocking dengan reseptor, kotak, dan mesin yang sama: ΔΔG, efisiensi ligan (LE; Hopkins dkk. 2004), Fit Quality (FQ; Reynolds dkk. 2007), sumbangan skor per atom gula, dan kesimpulan ("Unggul karena ukuran" bila tiap atom gula menyumbang lebih kecil daripada LE aglikon). Paragraf metode berikut empat rujukan terverifikasi dan ekspor CSV.
  - Diuji pada 26 molekul rujukan PubChem (aglikon sama dengan entri PubChem untuk 9 glikosida) dan alur GUI dengan docking Vina sungguhan di 1HSG (`dev/uji_glikosida.py --gui`, ±45 detik, bahasa Indonesia dan Inggris).

### Diubah
- **QSAR: peringatan cakupan domain aplikabilitas** (langkah 5 Prediksi; `core/qsar.ringkas_domain`). Bila < 80 % ligan berada di dalam domain, muncul keterangan; bila < 50 %, peringatan tegas bahwa model tidak cocok untuk seri itu (dengan median kemiripan kNN dan ambangnya) dan prediksinya tidak boleh dipakai untuk memeringkat. Senyawa di dalam domain ditaruh di atas tabel; senyawa di luar domain diredupkan di bawah dengan keterangan alat. Menulis prediksi seperti itu ke panel Hasil disertai peringatan. Kasus nyata: 0 dari 156 senyawa galam berada di dalam domain model AChE.

### Diperbaiki
- **Aplikasi terpasang di folder ber-huruf non-ASCII** (mis. `C:\Users\Rizkí\AppData\Local\Programs\VirmoLab`): 5 dari 56 uji mandiri gagal. RDKit tidak bisa membuka `BaseFeatures.fdef`, sehingga analisis interaksi, PoseBusters, kemiripan, dan farmakofor mati, dan OpenMM tidak memuat plugin platform apa pun, sehingga MD dan MM/GBSA mati. Pembuka berkas C++ keduanya memakai API ANSI. Kini definisi fitur RDKit dibaca lewat Python, termasuk yang dibangun PoseBusters saat diimpor (`qc._fdef_lewat_python`), dan plugin OpenMM dimuat ulang dari jalur pendek 8.3 bila gagal (`paths.jalur_pendek`). Di folder yang sama, seluruh tema antarmuka juga hilang (tombol, tab, dan panah tampil polos): satu `url()` ikon tanpa tanda kutip yang memuat huruf non-ASCII membuat Qt menolak seluruh stylesheet tanpa pesan. Kini semua `url()` berkutip, dan uji mandiri punya butir baru "Tema antarmuka (stylesheet)" yang memeriksa stylesheet benar-benar berlaku (57 butir).
- Dialog MD: keterangan tiga tingkat simulasi terpotong atas-bawah pada ukuran jendela minimum.
- Mode English: dua kotak centang terpotong mendatar (Desain generatif: pelonggaran ambang; Tanaman obat: filter stereo); terjemahannya dipendekkan.
- Alat audit baru `dev/uji_label_terpotong.py [--en]`: membuka 31 dialog analisis pada ukuran bawaan dan minimum, mengunjungi setiap tab dan halaman wizard, dan mencatat label berbungkus yang lebih pendek dari teksnya serta label/tombol yang lebih sempit dari teksnya. Sekarang 0 temuan dalam kedua bahasa.

## [1.6.1] - 24 Oktober 2026

Rilis perbaikan: tiga perbaikan QSAR yang dapat membalik kesimpulan (model QSAR berpembagian kerangka dari versi
sebelumnya perlu dilatih ulang), impor hasil docking, trajektori MD, dan grafik dari program lain, serta paragraf
metode RBFE yang disusun dari run yang benar-benar selesai.

### Baru
- **Impor hasil docking dari program lain** (Berkas › Impor hasil eksternal › Hasil docking…; `core/impor_docking.py`, `ui/dialog_impor_docking.py`):
  - PDBQT AutoDock Vina, QuickVina, Smina, GNINA, dan Uni-Dock (multi-MODEL, termasuk residu fleksibel), DLG AutoDock4/AutoDock-GPU, SDF/MOL2 multi-pose (GNINA, GOLD, Glide, rDock, MOE, Discovery Studio, DiffDock), serta PDB kompleks atau multi-MODEL.
  - Pose dibangun ulang dengan orde ikatan benar (REMARK SMILES Meeko, atau Open Babel dengan perbaikan muatan dan H non-polar) lalu disimpan sebagai job proyek, sehingga tabel hasil, interaksi, diagram 2D, PoseBusters, MD, dan ekspor berjalan seperti hasil docking VirmoLab. Reseptor tiap job impor dipakai untuk analisisnya sendiri.
  - Kolom ΔG hanya diisi skor berdimensi energi. Fitness GOLD, CNNscore, atau confidence DiffDock tidak disamakan dengan ΔG: kolom ΔG diisi skor ulang Vina (`--score_only`) dan skor asli tetap tampil di tooltip, panel Properti, ekspor, dan laporan.
- **Impor trajektori MD** (Berkas › Impor hasil eksternal › Trajektori MD…; `core/impor_md.py`, `ui/dialog_impor_md.py`):
  - Topologi GRO, PDB, PRMTOP, PSF, CIF; trajektori XTC, TRR, DCD, NetCDF, MDCRD, serta PDB/GRO multi-frame. Beberapa bagian disambung menurut waktu atau diperlakukan sebagai replika independen. Topologi yang jumlah atomnya cocok dicari otomatis di folder trajektori.
  - Dibaca bertahap (frame terpilih dan atom zat terlarut saja) di proses terpisah. Molekul yang terpotong kotak periodik diutuhkan dan lompatan antarframe dihapus, lalu frame disejajarkan pada Cα. Koordinat terbaca sama persis dengan MDAnalysis 2.10, dan RMSD dari trajektori terbungkus PBC sama dengan trajektori asli (selisih ≤ 0,002 Å).
  - Analisis memakai pipa MD yang ada (RMSD, RMSF, Rg, SASA, ikatan H, okupansi interaksi, barcode, PCA, FEL, klaster ligan). Jendela analisis kini punya daftar Hasil untuk memilih run MD tersimpan dan tombol Putar di viewport.
- **Pemutar trajektori di viewport 3D**: bilah putar/jeda, penggeser bingkai, waktu (ns), dan kecepatan, untuk MD internal maupun impor.
- **Grafik dari berkas data** (Berkas › Impor hasil eksternal › Grafik XVG/CSV…; `core/impor_grafik.py`, `ui/dialog_grafik_berkas.py`): XVG gmx, DAT cpptraj/VMD, dan CSV/TSV (desimal koma dikenali); beberapa berkas ditumpuk, konversi nm→Å, nm²→Å², ps→ns, kJ/mol→kcal/mol, rata-rata bergerak, histogram, statistik paruh kedua, simpan SVG/PDF/PNG/TIFF atau kirim ke Komposer Figur.
- Seret-lepas dan Berkas › Buka mengarahkan berkas hasil docking, trajektori, dan grafik ke dialog impor yang sesuai.
- **Paragraf metode RBFE dari run yang benar-benar selesai** (Energi bebas relatif › Salin metode; `core/rbfe_openfe.py`): setelah simulasi OpenFE, versi OpenFE/OpenMM, platform, medan gaya protein dan ligan, model air, metode muatan parsial, jumlah jendela λ, ulangan, kotak, suhu, tekanan, dan panjang ekuilibrasi/produksi dibaca dari JSON hasil, bukan dari rencana di dialog. Bila belum ada tepi selesai atau pengaturannya tidak lengkap, dialog kembali ke paragraf rencana, tidak menulis paragraf separuh jadi.

### Diperbaiki
- Ligan PDB keluaran Vina/Open Babel yang nama atomnya kembar ("C", "C", "O", …) terpangkas menjadi beberapa atom karena gemmi menganggapnya konformasi alternatif; atom kini dinamai ulang sebelum dibaca.
- Analisis SASA MD bisa menjatuhkan aplikasi (access violation di FreeSASA Shrake-Rupley RDKit setelah beberapa panggilan beruntun); kini memakai algoritme Lee-Richards.
- **QSAR: pembagian berbasis kerangka terbalik** (`core/qsar.py`). Set uji diisi lebih dulu dengan kerangka terbesar, sehingga satu keluarga kongenerik besar menjadi set uji dan R² eksternal negatif besar walau RMSE kecil. Kini kerangka terbanyak masuk set latih dan kerangka jarang menjadi set uji, sesuai docstring-nya. Model QSAR berpembagian kerangka yang dibuat sebelumnya perlu dilatih ulang.
- **QSAR: prediksi molekul besar gagal** ("Input X contains infinity…"). Deskriptor `Ipc` mencapai ±10⁴² pada triterpenoid dan tanin, melampaui float32 scikit-learn. `Ipc` dikeluarkan (AvgIpc tetap dipakai) dan nilai fitur dipangkas ke rentang float32 yang aman.
- **QSAR: model tersimpan dicocokkan lewat nama fitur.** `qsar.muat()` memetakan ulang indeks kolom bila daftar deskriptor berubah, dan menolak model yang memakai deskriptor yang tidak lagi dihitung (misalnya `Ipc`) dengan anjuran melatih ulang, alih-alih diam-diam memakai kolom yang salah.
- **Mode English: sisa teks Indonesia** di dialog Penapisan bertahap (ringkasan setelan docking, sumber pustaka, tooltip tombol Mulai), Sunting di kantong 3D (nama gugus, status penilaian), Energi bebas relatif (beban simulasi, status run), dan halaman Uni-Dock panel docking. Teks yang dirakit dari potongan kini diterjemahkan per potongan; 186 entri kamus baru. Audit `dev/uji_bahasa_lanjut.py` kini ikut memeriksa kedua dialog baru dan halaman Uni-Dock.
- **OpenFE/Uni-Dock dilaporkan "belum terpasang" padahal ada** (`core/rbfe_openfe.py`, `core/unidock.py`). Pemeriksaan WSL ditandai selesai sebelum WSL menjawab, sehingga dialog yang dibuka selama WSL masih menyala (±10 detik saat dingin) diberi status kosong dan tombol Jalankan mati. Pemanggil kedua kini menunggu jawaban pertama.
- **Tombol utama yang nonaktif tampak aktif** di seluruh aplikasi (misalnya Susun jaringan, Jalankan, Mulai penapisan): gaya `#primary` mengalahkan gaya `:disabled`. Kini tombol utama nonaktif berwarna redup seperti tombol lain.
- Teks status run RBFE dan rencana putaran penapisan bertahap terpotong atas-bawah; labelnya kini diberi tinggi cukup.

### Diubah
- **Cek pembaruan menunjuk repo pengembang** `rizkirahmadip-dev/virmolab` (`core/pembaruan.py`). Nama `virmolab` di GitHub belum terdaftar, sehingga siapa pun yang mendaftarkannya dapat menyajikan rilis palsu ke aplikasi terpasang. Selama repo masih privat, pemeriksaan menjawab "belum ada rilis". `CITATION.cff` dan URL deskripsi tanda tangan kode ikut diganti.
- Nomor versi di `pyproject.toml` kini dibaca dari `virmolab/__init__.py` (sebelumnya tertinggal di 1.1.1).

## [1.6.0] - 16 Oktober 2026

Rilis penapisan skala besar dan simulasi: mesin docking GPU Uni-Dock, simulasi RBFE OpenFE yang
berjalan langsung dari VirmoLab, penapisan pustaka besar dengan pembelajaran aktif, dan penyuntingan
ligan di dalam kantong dengan penilaian langsung.

### Baru
- **Mesin docking Uni-Dock (GPU, lewat WSL)** (langkah 4 · Jalankan; `core/unidock.py`, `core/antrean.py`, `ui/panel_docking.py`):
  - Ratusan ligan didocking dalam satu panggilan GPU dengan fungsi skor Vina atau Vinardo; mode pencarian Cepat, Seimbang, atau Detail.
  - Terdeteksi otomatis bila sudah dipasang di WSL lewat `build_tools/pasang_openfe_unidock_wsl.sh`; bila belum, tombolnya mati dan pesannya menjelaskan cara memasang. Tidak ikut pemasang Windows.
  - Keluarannya PDBQT bergaya Vina, sehingga tabel hasil, interaksi, PoseBusters, dan RMSD redocking berjalan seperti biasa.
  - Batch diulang sekali bila WSL gagal menyalakan mesin virtualnya, dan pesan galat wsl.exe (UTF-16) kini terbaca benar.
  - Tolok ukur Astex Diverse (85 kompleks): Uni-Dock RMSD ≤ 2 Å pada 57,6 % kasus (PB-valid 55,3 %) dibanding Vina 62,4 % (60,0 %), dengan median 3,5 detik per ligan satuan dan ±0,7 detik per ligan dalam batch, dibanding 11,9 detik untuk Vina.
  - Perbedaan per kasus tetap ada (redocking MK1 pada 1HSG meleset 9,9 Å di Uni-Dock, benar 1,7 Å di Vina), jadi pose yang akan dilaporkan sebaiknya diperiksa ulang dengan Vina atau AutoDock-GPU.
- **Simulasi RBFE dijalankan dari VirmoLab** (Analisis › Sifat ligan dan desain › Energi bebas relatif (eksperimental)…; `core/rbfe_openfe.py`, `ui/dialog_rbfe.py`):
  - OpenFE 1.13 dijalankan di WSL: transformasi dibuat (pemetaan atom LOMAP, hybrid topology), tiap kaki dijalankan dengan `openfe quickrun`, hasilnya disalin kembali ke folder proyek.
  - Simulasi berjalan terlepas dari aplikasi dan dapat dilanjutkan; kemajuan dibaca dari log dan berkas analisis OpenFE.
  - Preset protokol: bawaan OpenFE (5 ns × 3 repeat) atau uji cepat (0,5 ns × 1 repeat). Muatan parsial ligan memakai OpenFF NAGL.
  - Uji pemasangan TYK2 (lig_ejm_31 → lig_ejm_43, protokol uji cepat, RTX 3060 Laptop): ΔΔG +2,28 ± 0,95 kkal/mol terhadap +1,28 kkal/mol dari Ki eksperimen — arah benar, selisih 1,0 kkal/mol.
- **Penapisan pustaka besar dengan pembelajaran aktif** (Analisis › Penapisan banyak ligan › Penapisan pustaka besar…; `core/pembelajaran_aktif.py`, `ui/pengendali_al.py`, `ui/dialog_pembelajaran_aktif.py`):
  - Mengikuti MolPAL (Graff dkk., 2021): batch awal acak didocking, model pengganti dilatih dari skornya, lalu batch berikutnya dipilih menurut prediksi dan ketidakpastiannya.
  - Pustaka dari berkas SMILES/CSV/SDF (boleh .gz), COCONUT, atau obat disetujui; sidik jari pasangan atom 2048 bit; model ensemble jaringan saraf atau random forest; akuisisi UCB, greedy, atau acak sebagai pembanding.
  - Docking tiap putaran lewat antrean biasa dengan setelan yang dikunci saat kampanye dimulai; kampanye tersimpan di proyek, tetap berjalan walau dialognya ditutup, dan dapat dilanjutkan setelah aplikasi dibuka lagi.
  - Akurasi prospektif model (Spearman ρ) diukur pada tiap batch sebelum batch itu didocking, dan ditampilkan apa adanya.
  - Uji retrospektif dengan skor Enamine MolPAL: mendocking 6 % pustaka menemukan 64 % (10 ribu) dan 74 % (50 ribu) senyawa 1 % terbaik, dibanding 6 % dan 5 % untuk pemilihan acak (`dev/tolok_ukur_al.py`).
- **Sunting di kantong (3D)** (Analisis › Sifat ligan dan desain › Sunting di kantong (3D)…; `core/sunting3d.py`, `ui/dialog_sunting3d.py`):
  - Gugus disambungkan pada atom yang dipilih dengan mengeklik diagram 2D, atau gugus fungsi diganti bioisosternya; analog dibangun dengan inti dipaku pada koordinat pose induk lalu dinilai dengan Vina `--local_only` dalam hitungan detik.
  - Tabel usulan memuat ΔG lokal, ΔΔG terhadap induk, efisiensi ligan, jumlah tabrakan, MW, logP, QED, dan SAScore; pose dapat dibuka di penampil dan usulan ditambahkan ke proyek sebagai ligan untuk didocking ulang.

- **Halaman dokumentasi Validasi** (Bantuan › Dokumentasi › Validasi; `docs/_sumber/validasi.html`): angka tolok ukur yang diukur sendiri beserta cara menjalankannya kembali — redocking Astex Diverse (85) dan PoseBusters Benchmark (428), penapisan bertahap, RBFE TYK2, serta cross-docking dengan rantai samping fleksibel.
  - AutoDock Vina: Astex 62,4 % RMSD ≤ 2 Å (PB-valid 60,0 %), PoseBusters 50,5 % (48,8 %); sebanding dengan 58 % dan 60 % yang dilaporkan makalah PoseBusters untuk himpunan versi pertama.
  - Uni-Dock: Astex 57,6 % (55,3 %). Pada 85 kompleks yang sama, 48 kasus benar di kedua mesin, 5 hanya di Vina, 1 hanya di Uni-Dock.

### Diperbaiki
- Jaringan RBFE tidak lagi memuat tepi ganda untuk pasangan yang sama (menggandakan simulasi tanpa informasi baru), dan tepi penutup siklus hanya ditambahkan bila pasangannya memang belum menjadi tepi.

## [1.5.0] - 15 Oktober 2026

Rilis fitur lanjutan: co-folding Boltz-2, docking peptida, sifat elektronik kuantum, desain
generatif, dan perencanaan energi bebas relatif. Dengan ini seluruh fitur F1 sampai F12 pada
`dev/dokumen/RENCANA_PENGEMBANGAN.md` sudah dikerjakan.

### Baru
- **Konsensus docking dengan co-folding Boltz-2 (F6)** (tab "Co-folding" di panel Properti; kolom baru di dialog Konsensus; `core/kofolding.py`, `ui/panels.py`, `ui/dialog_konsensus.py`):
  - Menjalankan Boltz-2 lewat WSL untuk satu pose docking terpilih, lalu membaca struktur kompleks, nilai afinitas, dan metrik keyakinan dari folder keluarannya.
  - Struktur Boltz-2 disuperposisikan ke reseptor proyek dengan Kabsch pada Cα sebelum RMSD ligan dihitung, sehingga perbandingannya memakai kerangka koordinat yang sama.
  - Label kesepakatan Sepakat, Sebagian, atau Bertentangan disusun dari RMSD ligan, kemiripan Tanimoto sidik jari interaksi, dan hasil PoseBusters kedua pose.
  - Kolom "Boltz-2 afinitas" dan "Kesepakatan" di dialog Konsensus, beserta saringan untuk menampilkan hanya ligan yang sepakat.
  - Kebaruan ligan diperiksa terhadap ligan yang sudah ada di PDB; kemiripan tinggi diberi peringatan karena struktur tersebut kemungkinan ikut dalam data latih model.
  - Paragraf metode dialog Konsensus menyebut pemeriksaan silang co-folding hanya bila ada ligan yang benar-benar dianalisis, memuat jumlah per label, dan menyatakan risiko kebocoran data latih.
  - Kegagalan Boltz-2 atau WSL dilaporkan apa adanya sebagai nilai kosong, bukan angka bawaan.

- **Docking peptida (F10)** (Siapkan › Langkah 2 · Ligan › Peptida dari sekuens…; `core/peptida.py`, `ui/dialog_peptida.py`):
  - Masukan sekuens satu huruf dengan pemeriksaan langsung: huruf yang bukan asam amino disorot merah di tempatnya, batas 30 residu ditegakkan, dan kode tidak baku (B, Z, X, U, O) diterima dengan peringatan.
  - Kompleks dibangun dengan co-folding Boltz-2, dengan peptida dikirim sebagai rantai protein tersendiri, bukan sebagai ligan bermolekul kecil. Fungsi skor docking tidak dipakai karena dirancang untuk molekul kecil.
  - Pemurnian OpenMM di pelarut implisit: minimisasi dengan reseptor dikekang, pilihan dinamika singkat, lalu MM/GBSA dengan peptida sebagai bagian "ligan".
  - Analisis antarmuka lewat `core/ppi.py`: kontak, ikatan hidrogen, jembatan garam, luas terkubur, dan daftar residu antarmuka kedua rantai.
  - Kompleks dapat dimuat ke penampil dengan peptida ditandai warna tersendiri; hasilnya tersimpan di proyek.
  - AutoDock CrankPep (ADCP) tidak dipakai karena status lisensinya belum diverifikasi sebagai sumber terbuka.
- **Sifat elektronik kuantum (F7)** (Analisis › Sifat ligan dan desain › Sifat elektronik (xTB)…; `core/xtb.py`, `ui/dialog_xtb.py`):
  - xtb 6.7.1pre (GFN2-xTB, LGPL-3.0) ikut dibundel di `bin/xtb`; biner resmi grimme-lab, SHA-256 dicocokkan saat pemasangan.
  - Deskriptor per ligan: HOMO, LUMO, celah, kekerasan kimia, potensial kimia, elektrofilisitas, dan momen dipol, dengan pelarut implisit ALPB atau fase gas.
  - Indeks Fukui f(+), f(-), f(0) dan muatan parsial Mulliken per atom, ditampilkan sebagai pewarnaan atom divergen di penampil 3D beserta skalanya.
  - Potensial elektrostatik dari xtb dipetakan ke atom terdekat untuk pewarnaan; nilai yang dilaporkan di tabel tetap berasal langsung dari xtb.
  - Indeks Fukui f(-) dibandingkan dengan prediksi situs metabolisme CYP, dengan penomoran atom dipetakan lewat pencocokan substruktur supaya tidak salah menunjuk atom.
  - Perhitungan berjalan di proses terpisah dan paralel per inti CPU; kegagalan, batas waktu, dan SCF yang tidak konvergen dilaporkan sebagai nilai kosong beserta sebabnya.
  - Peringatan metode ikut di dialog, paragraf metode, dan ekspor CSV: GFN2-xTB semi-empiris, celahnya cenderung lebih kecil dari DFT, dipakai untuk tren antar-ligan, bukan nilai absolut.
- **Desain generatif terpandu docking (F8)** (Analisis › Sifat ligan dan desain › Desain generatif…; `core/generatif.py`, `ui/dialog_generatif.py`):
  - Analog dibangun dengan CReM (BSD-3-Clause) memakai basis data fragmen yang dibangun sendiri dari 2316 obat disetujui di pustaka lokal (`dev/buat_db_fragmen.py`, 42 MB), bukan mengunduh basis data ChEMBL penuh yang berukuran gigabyte.
  - Operasi ganti fragmen dan tambah fragmen dengan radius konteks yang dapat diatur; duplikat disaring berdasarkan InChIKey dan induk tidak ikut sebagai anak.
  - Saringan PAINS, Brenk, SAScore, QED, dan kebaruan terhadap induk; setiap penolakan menyimpan alasannya dan ditampilkan sebagai ringkasan supaya ambang yang terlalu ketat terlihat.
  - Ambang QED dan SAScore dapat mengikuti induk bila induknya sendiri di luar ambang. Tanpa ini, senyawa seperti indinavir (QED sekitar 0,24) membuat seluruh turunannya tertolak, sehingga fiturnya tidak terpakai justru pada kasus yang membutuhkannya.
  - Peringkat multi-objektif front Pareto atas ΔG, QED, dan SAScore; kandidat tanpa ΔG tidak diperingkat dan kandidat yang gagal di-docking dihitung terpisah.
  - Silsilah induk ke anak, ekspor CSV beserta asal fragmen, dan impor kandidat terpilih sebagai ligan proyek.
- **Energi bebas relatif alkimia (F9, eksperimental)** (Analisis › Sifat ligan dan desain › Energi bebas relatif (eksperimental)…, hanya di mode ahli; `core/rbfe.py`, `ui/dialog_rbfe.py`):
  - Pasangan perturbasi dipilih dari MMP dengan batas 10 atom berat berubah; pemetaan atom memakai substruktur bersama maksimum RDKit dengan pencocokan unsur, orde ikatan, dan cincin utuh.
  - Jaringan perturbasi bintang atau pohon rentang minimum atas skor kemudahan, ditambah tepi penutup siklus untuk memeriksa konsistensi.
  - Analisis MBAR dengan pymbar atas energi tereduksi tiap jendela lambda, menghasilkan ΔG beserta galat bakunya; pemeriksaan penutupan siklus menandai jaringan yang tidak konsisten.
  - Perkiraan beban perhitungan ditampilkan sebelum apa pun dijalankan, dan lama perhitungan dibiarkan kosong bila kecepatan mesin belum diukur, bukan ditebak.
  - **Simulasinya tidak dapat dijalankan di Windows.** OpenFE, mesin RBFE sumber terbuka yang matang, hanya mendukung Linux dan macOS menurut dokumentasi resminya. Dialog menyatakan hal ini terus terang dan tidak menyediakan tombol jalankan yang tidak akan berfungsi; perencanaan jaringan dan analisis hasil dari mesin Linux tetap tersedia.

### Diperbaiki
- **Afinitas Boltz-2 tidak pernah dihitung.** YAML yang dikirim ke Boltz tidak memuat blok `properties: - affinity: binder: L`, dan tanpa itu Boltz melewati perhitungan afinitas sepenuhnya serta tidak menulis `affinity_*.json`, berapa pun nilai `--diffusion_samples_affinity` yang diberikan. Akibatnya kolom "Boltz-2 afinitas" di dialog Konsensus selalu kosong. Ditemukan saat menjalankan Boltz-2 2.2.1 sungguhan pada 1HSG, dikonfirmasi di `boltz/data/parse/schema.py`, dan kini dikunci uji.
- Perbandingan peptida hasil prediksi terhadap struktur kristal dilakukan tanpa superposisi, padahal Boltz memprediksi di kerangka koordinatnya sendiri; RMSD-nya puluhan angstrom dan tidak bermakna. `peptida.sejajarkan_ke_acuan` menyuperposisikan Cα reseptor lebih dulu, dengan jalur cadangan berbasis urutan sekuens ketika penomoran residu berbeda antara struktur kristal dan keluaran model.
- Metrik keyakinan Boltz-2 berskala 0 sampai 1, bukan 0 sampai 100 seperti pLDDT AlphaFold. Kartu pLDDT di dialog peptida menampilkannya sebagai persen, dan fixture uji diselaraskan dengan keluaran sungguhan.
- Sisa ruang di kanan kepala tabel tampil putih pada tema gelap karena QSS hanya mengatur tiap seksi kepala, bukan `QHeaderView` itu sendiri.
- `ui/mainwindow.py` memanggil `analisis.TIGA_KE_SATU` yang tidak pernah ada, sehingga menjalankan co-folding gagal seketika dengan `AttributeError`. Tabel kode residu kini satu-satunya, di `core/konservasi.py`.
- `kit.pesan_peringatan` dipanggil tiga tempat tetapi belum pernah didefinisikan, sehingga impor CSV plate reader yang gagal justru melempar `AttributeError`, bukan menampilkan peringatan.

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
