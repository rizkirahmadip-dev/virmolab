# VirmoLab — serah terima & prompt yang tersisa

Dibuat 13 Oktober 2026 untuk melanjutkan pekerjaan di sesi/akun baru. Berkas ini berdiri sendiri; dua berkas pendamping
ada di folder yang sama dan ikut Git:

- `RENCANA_PENGEMBANGAN.md` — dasar ilmiah, desain teknis, dan urutan rilis 1.2–1.6 (F1–F12).
- `PROMPT_PENGEMBANGAN.md` — sketsa UI tiap fitur (bagian "UI F…") dan **Lampiran UI** (aturan menu, tata letak, angka, warna).
  Prompt P0–P15 lama di sana sudah digantikan oleh berkas ini; pakai berkas itu hanya untuk sketsa UI dan lampiran.

---

## 1. Status saat ini

- Folder kerja: `E:\Bikin Docking Simpel\VirmoLab`. Python proyek: `.venv/Scripts/python.exe`
  (selalu `PYTHONIOENCODING=utf-8 PYTHONPATH=.`). Versi kode di `virmolab/__init__.py`: **1.1.2**.
- Commit terakhir: `07b767c` (fondasi sumber data, F1 tanaman obat, F2 analisis MD).
  Sebelumnya `585ab9f` = rilis 1.1.2 (sudah di-build, uji mandiri 40/40).
- **Belum di-commit:** pekerjaan F11 (paket validasi protokol): `core/decoy.py`, `core/validasi_protokol.py`,
  `ui/dialog_validasi_protokol.py`, `dev/uji_validasi_protokol.py`, perubahan `mainwindow*.py`, `tab_uji.py`,
  dokumen, terjemahan, CHANGELOG. Semua uji F11 lulus (14/14). → **jalankan P-COMMIT dulu.**
- CHANGELOG sudah punya bagian `[1.2.0]` (Fondasi, F1, F2, F11); versi belum dinaikkan (itu tugas P-RILIS).
- Terjemahan Inggris: `dev/i18n_tambahan.json` → `dev/buat_kamus.py` → `virmolab/i18n/en.json`;
  pemeriksa mutu `dev/cek_mutu_i18n.py` (0 masalah terakhir). Laporan PDF/Word memang tetap berbahasa Indonesia.

### Sudah selesai di rilis 1.2 (belum dirilis)

| Butir | Berkas utama |
|---|---|
| Fondasi: klien data internet bercache, Jejak sumber di proyek/laporan, graf | `core/sumber_data.py`, `core/graf.py`, `Proyek.jejak` |
| F1 Senyawa dari tanaman obat (LOTUS/Wikidata + COCONUT, DOI lewat graf artikel ilmiah) | `core/tanaman.py`, `ui/dialog_tanaman.py`, `virmolab/data/nama_tanaman_id.csv` |
| F2 Analisis lintasan MD lengkap (Rg, SASA, ikatan H, barcode, PCA, FEL, klaster, replika) | `core/md_analisis.py`, `ui/dialog_md.py` |
| F11 Paket validasi protokol (redocking, cross-docking, pengayaan, ringkasan) | `core/decoy.py`, `core/validasi_protokol.py`, `ui/dialog_validasi_protokol.py` |

### Yang masih harus dikerjakan

`P-COMMIT` → `P-RILIS` (1.2.0) → `P-COMMIT` → `P-BUILD`, lalu fitur 1.3–1.6: **P6, P7** (rilis 1.3) · **P8, P9, P10**
(1.4) · **P11, P12, P13** (1.5) · **P14, P15** (1.6).

---

## 2. Blok verifikasi wajib (berlaku untuk SETIAP prompt fitur)

Dua sesi sebelumnya melaporkan "selesai, uji lulus" padahal hasilnya salah. Pelajaran konkret dari F2 dan F11:

1. **Uji inti saja tidak cukup — buka dialognya.** Dialog F11 langsung galat saat dibuka (`kit.judul()` dipanggil dengan
   3 argumen; `kit.tombol_aksi` tidak ada) dan tidak ada uji yang membukanya. Tambahkan nama dialog ke daftar `DIALOG` di
   `dev/uji_dialog_lanjut_gui.py`, jalankan (`... uji_dialog_lanjut_gui.py <nama>`), lalu **lihat tangkapan layarnya**
   (`dev/uji/lanjut/<nama>_gelap.png`, `_terang.png`). Cek signature fungsi `kit` yang dipakai sebelum memanggilnya.
2. **Tidak ada angka karangan.** Pernah ditemukan: skor aktif tertulis di kode, skor decoy dari `np.random`, nilai bawaan
   "RMSD 1,25 / AUC 0,85 / PoseBusters 95 %" yang masuk paragraf metode dan laporan. Aturan: hasil yang belum dihitung tampil
   "–", tidak ikut paragraf/laporan; tidak ada nilai bawaan, contoh, atau acak di jalur hasil. Fallback offline tidak boleh
   diam-diam mengganti data (mis. daftar aktif HIV untuk target lain).
3. **Kegagalan komputasi bukan nilai angka.** Docking/RMSD yang gagal = `None` + dihitung + dilaporkan, **bukan** 0, 0,0, atau
   99. (0 kcal/mol pada ROC berarti "paling tidak aktif"; RMSD 0,0 berarti "sempurna".)
4. **Jangan ubah fungsi bersama tanpa uji penjaga.** Perubahan di `analisis._fitur` (demi MD) sempat merusak deteksi ikatan
   hidrogen docking biasa. Setelah menyentuh modul bersama, jalankan: `uji_analisis_inti`, `uji_md_analisis`, `uji_tanaman`,
   `uji_validasi_protokol`, `uji_proyek`.
5. **Periksa kebenaran ilmiah, bukan hanya "tidak crash".** Contoh yang lolos uji tetapi salah: ikatan H selalu 0 (kode
   jenis `"hbond"` ditulis `"ikatan_h"`), okupansi 176 % (dihitung per interaksi, bukan per frame), cross-docking tanpa
   superposisi. Tambahkan satu uji yang mengunci angka yang masuk akal secara kimia (mis. ASP 25 katalitik terdeteksi pada
   1HSG–MK1; okupansi ≤ 100 %).
6. **Teks hasil harus jujur.** Paragraf metode dirakit dari hasil nyata (p-nilai dari data, bukan "p < 0,0001" tetap),
   menyebut keterbatasan (mis. decoy bukan dari ZINC), dan tidak menyebut uji yang tidak dijalankan.
7. **Data paket vs data pengguna.** Berkas bawaan aplikasi → `virmolab/data/` **dan** tambahkan ke
   `build_tools/virmolab.spec` (`datas += ...`); jika tidak, aplikasi terpasang tidak menemukannya. `.gitignore`
   memakai `/data/` (folder data pengguna mode portabel di akar) — jangan kembalikan ke `data/`.
8. **Lint dan terjemahan.** `.venv/Scripts/python.exe -m pyflakes virmolab` harus bersih (CI menjalankannya).
   Teks UI baru: `dev/ekstrak_teks.py` → terjemahkan ke `dev/i18n_tambahan.json` → `dev/buat_kamus.py` →
   `dev/cek_mutu_i18n.py` = 0 (jangan terjemahkan SQL, path, atau teks laporan).
9. **Windows/Git Bash.** Skrip penyunting yang panjang atau berisi tanda kutip tiga → tulis dengan alat Write ke berkas,
   jalankan; jangan heredoc besar. Berkas Python berakhir baris CRLF — itu normal, jangan "diperbaiki".
9b. **UI/UX tanpa "AI slop" (aturan tegas pengguna).** Tanpa emoji dekoratif, gradien/kartu hiasan, kalimat promosi atau isian, ikon tanpa fungsi, dan salinan mikro bertele-tele. Pakai komponen `ui/kit.py` dan tema yang ada; tiap elemen berfungsi; teks ringkas, spesifik, baku; keadaan kosong/galat menjelaskan sebab + langkah berikut. Bandingkan dengan dialog lain, buka tema terang dan gelap, lihat tangkapan layar sebelum menyatakan selesai.
10. **Jangan menyatakan selesai sebelum** poin 1–8 terpenuhi. Laporan akhir wajib menyebut: uji apa yang dijalankan, apakah
    dialog dibuka dan dilihat tangkapan layarnya, dan apa yang **tidak** teruji (mis. jalur daring/GPU).

Aturan umum: jangan commit, jangan build, jangan jalankan `dev/regresi.py` penuh (±35 menit) kecuali di P-RILIS.
Hemat token: keluaran uji cukup ringkasan; jangan menampilkan daftar terjemahan atau berkas besar di obrolan.

---

## 3. Prompt siap salin

Satu prompt = satu sesi baru. Model saran: **Opus** untuk P6, P7, P8, P14, P15; **Sonnet** untuk sisanya.
Bila sesi terputus, buka sesi baru dan tempel prompt yang sama + baris:
`Lanjutkan: periksa git status dan CHANGELOG, kerjakan langkah yang belum selesai.`

### P-COMMIT

```text
Periksa git status di E:\Bikin Docking Simpel\VirmoLab. Tampilkan ringkasan berkas berubah (jumlah per folder).
Berkas tak terlacak yang tampak sementara (scratch/, *.tmp, keluaran uji) jangan ikut — tanyakan bila ragu.
Pastikan data paket baru tidak terabaikan: git check-ignore -v pada berkas baru di data/ atau virmolab/data/.
Commit satu commit, pesan Conventional Commits Bahasa Indonesia: feat(<area>): <ringkasan>, badan berupa poin per fitur,
diakhiri baris Co-Authored-By sesuai instruksi sesi. Jangan push. Laporkan hash.
```

### P-RILIS (1.2.0)

```text
Siapkan rilis VirmoLab 1.2.0. Folder: E:\Bikin Docking Simpel\VirmoLab.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).
Baca juga bagian "Blok verifikasi wajib" di PROMPT_SISA.md dan patuhi.

1. Naikkan versi di virmolab/__init__.py ke 1.2.0; rapikan CHANGELOG.md bagian [1.2.0] (tanggal hari ini, Baru/Diperbaiki/
   Diubah, tanpa duplikat; pastikan klaim sesuai kenyataan).
2. pyflakes virmolab bersih.
3. i18n: dev/ekstrak_teks.py → terjemahkan sisa → dev/buat_kamus.py → dev/cek_mutu_i18n.py = 0.
4. Pastikan build_tools/virmolab.spec menyertakan SEMUA berkas data bawaan baru (virmolab/data/nama_tanaman_id.csv, dll.).
5. Dokumen: python dev/buat_docs.py; periksa docs/panduan.html memuat bagian tanaman obat, analisis MD, validasi protokol.
   Tutorial PDF hanya bila alur dasar berubah.
6. dev/siapkan_contoh.py lalu dev/regresi.py SEKALI. Tampilkan hanya ringkasan + nama uji gagal. Bila gagal: bedakan
   bug aplikasi vs bug uji; perbaiki; ulangi HANYA uji yang gagal.
7. Tambahkan uji fitur baru ke core/ujimandiri.py (uji mandiri dalam aplikasi beku): sumber_data (cache), tanaman
   (nama lokal → takson dari CSV paket), md_analisis (SASA/PCA sintetis), validasi_protokol (paragraf dari ringkasan kosong = "").
8. Jalankan dev/uji_dialog_lanjut_gui.py untuk semua dialog baru (tanaman, validasi_protokol) dan lihat tangkapan layarnya.
9. Perbarui CATATAN_TAHAP2.md (status versi, peta berkas) dan RENCANA_PENGEMBANGAN.md (tandai F1, F2, F11 selesai).
10. Laporkan ringkas; JANGAN commit dan JANGAN build — pengguna yang memutuskan.
```

### P-BUILD

```text
Build rilis VirmoLab dari commit terakhir. Folder: E:\Bikin Docking Simpel\VirmoLab.
Pastikan git status bersih (kecuali berkas tak terlacak yang memang diabaikan). Jalankan di latar belakang:
.venv/Scripts/python.exe build_tools/rilis.py > build/rilis_<versi>.log 2>&1
Setelah selesai: laporkan ukuran Setup & Portable, hasil uji mandiri (jumlah OK / gagal / lewat), dan SHA256SUMS.
Jangan ubah berkas sumber selama build berjalan.
```

---

### P6 — F3a Penargetan balik (Opus) · rilis 1.3 · setelah rilis 1.2

```text
Kerjakan F3 tahap a "Penargetan balik" VirmoLab 1.3. Folder: E:\Bikin Docking Simpel\VirmoLab.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).
Baca juga bagian "Blok verifikasi wajib" di PROMPT_SISA.md dan patuhi.

Baca dulu: RENCANA_PENGEMBANGAN.md §0, §3 F3 (termasuk peringatan ilmiah), §5; PROMPT_PENGEMBANGAN.md "Lampiran UI" +
"UI F3"; core/antrean.py (cara membuat job massal); core/chembl.py; core/rcsb.py; core/prep_reseptor.py; fungsi redocking
yang ada; core/konsensus.py (peringkat gabungan); core/sumber_data.py.

Sebelum mulai, TANYA pengguna (AskUserQuestion) bila belum diputuskan: 2 kelas penyakit untuk panel pertama
(bawaan bila tak dijawab: antibakteri + antiinflamasi) dan izin unduh ChEMBL ringkas (sebut ukuran).

Tugas:
1. dev/susun_panel.py (alat pengembang): daftar PDB ID per kelas (≥ 25 target/kelas, resolusi ≤ 2,5 Å, ligan ko-kristal
   mirip obat) → unduh → bersihkan (prep_reseptor) → redocking → simpan hanya RMSD ≤ 2 Å ke
   virmolab/data/panel_target/<kelas>.json: {uniprot, gen, nama, pdb, rantai, ligan_kristal, pusat, ukuran,
   rmsd_redocking, resolusi, tanggal}, plus 50 umpan acak per target (skor docking) untuk z-skor (rata, sd).
   PDBQT reseptor siap pakai ke virmolab/data/panel_target/<kelas>/. Daftarkan folder itu ke build_tools/virmolab.spec.
2. core/target_balik.py:
   jalur_ligan(smiles, sumber="chembl_lokal"|"chembl_api", k=5) -> [{target, skor_max, skor_knn, contoh_ligan}] ;
   jalur_struktur(lig, kelas, exhaustiveness=8) -> job di antrean (satu per target) ;
   kumpulkan(proyek, kelas) -> z-skor per target ; gabung(peringkat_ligan, peringkat_struktur) Borda + label
   kepercayaan (tinggi bila keduanya ≤ 10 besar). Target yang gagal di-docking = tidak diperingkat + dilaporkan.
3. UI sesuai "UI F3" (tab Penargetan balik). Docking massal memakai antrean yang ada (jeda/lanjut).
4. Data: proyek.target_balik = [{ligan_id, kelas, hasil: [...], parameter, jejak}] (setdefault di core/proyek.py).
5. Uji dev/uji_target_balik.py: panel mini 5 target; z-skor benar pada data sintetis; Borda benar;
   ibuprofen → PTGS1/PTGS2 masuk 2 teratas jalur ligan (luring, data ChEMBL mini tersimpan di dev/data/).
6. Dokumen + paragraf metode dengan peringatan "hipotesis, butuh validasi eksperimen".
7. Penutup: poin 1–8 Blok verifikasi wajib (termasuk membuka dialog dan melihat tangkapan layar).
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

### P6 — status 13 Okt 2026 (opsi B)

Hasil sesi P6 pertama ditolak: 56 reseptor .pdbqt sintetis (40 atom, koordinat bulat), RMSD redocking dan z_rata/z_sd
diketik tangan, nilai bawaan z diam-diam, jalur "ChEMBL daring" yang selalu jatuh ke berkas mini karangan di `dev/data/`.
Semua itu sudah **dibuang** (`virmolab/data/panel_target/`, `dev/susun_panel.py`, `dev/data/chembl_mini_target.json`).

Yang dipertahankan dan sudah diperbaiki (belum di-commit):
- `core/target_balik.py`: jalur ligan kini **ChEMBL REST sungguhan** (similarity ≥ 40 % → aktivitas pChEMBL ≥ 6, target
  SINGLE PROTEIN, bawaan *Homo sapiens* → Tanimoto Morgan2 dihitung lokal; skor_knn = jumlah k terdekat / k). Galat
  jaringan → `GalatTargetBalik`, tanpa data pengganti. Panel: `muat_panel_sah()` menolak entri tanpa reseptor, tanpa
  z_rata/z_sd, atau RMSD > 2 Å — tidak ada nilai bawaan. Borda: target yang absen di satu jalur = peringkat N+1.
  Paragraf metode dirakit dari parameter dan panel nyata (kosong bila tak ada jalur dijalankan).
- `ui/dialog_target_balik.py`: kelas panel dibaca dari paket; tanpa panel → "(panel target belum dibangun)" dan
  jalur struktur nonaktif. Kueri ChEMBL di QThread; jejak ChEMBL dicatat ke proyek.
- `dev/uji_target_balik.py`: uji rumus dengan data sintetis berlabel (z-skor, Borda, Tanimoto, penolakan panel);
  `--daring` memanggil ChEMBL nyata (ibuprofen → PTGS1 #1, PTGS2 #3 pada 13 Okt 2026).
- spec: panel_target hanya ikut build bila foldernya ada.

Kekurangan yang tersisa (dikerjakan P6b): panel nyata belum ada; dialog **belum** membuat job docking panel (jalur struktur
hanya mengumpulkan job yang sudah ada); `gabung()` memakai gen sebagai kunci sehingga dua target ChEMBL dengan gen sama
(mis. CXCR2) bertabrakan.

### P6b — Bangun panel target nyata (Opus) · setelah P6

```text
Kerjakan P6b "panel target nyata" untuk penargetan balik VirmoLab. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).
Baca dulu: PROMPT_SISA.md bagian "Blok verifikasi wajib" dan "P6 — status"; core/target_balik.py;
core/validasi_protokol.py (jalankan_redocking_mandiri); core/rcsb.py; core/prep_reseptor.py; core/antrean.py (job_baru).

LARANGAN KERAS (pelanggaran = pekerjaan ditolak):
- Tidak ada angka yang diketik tangan untuk rmsd_redocking, z_rata, z_sd, pusat, ukuran, resolusi. Semua dihasilkan
  kode dari berkas PDB/hasil docking nyata. Tidak ada `import random` kecuali untuk memilih umpan dengan seed tercatat.
- Tidak ada reseptor sintetis. Setiap .pdbqt panel harus berasal dari unduhan RCSB dan prep_reseptor
  (ukuran wajar: ratusan KB; jumlah atom protein sesuai rantai).
- Tidak ada nilai bawaan/fallback di kode aplikasi. Data hilang = target dilewati dan dilaporkan.
- Bila waktu/GPU tidak cukup, BERHENTI dan laporkan target yang sudah selesai. Panel sebagian yang jujur lebih baik
  daripada panel lengkap yang dikarang.

Tugas:
1. dev/susun_panel.py (alat pengembang, dapat dilanjutkan):
   a. Daftar kandidat per kelas di dev/panel_kandidat/<kelas>.csv (pdb, rantai, kode ligan kristal, gen, uniprot,
      alasan pemilihan + rujukan). Mulai 10 target/kelas (antibakteri, antiinflamasi). Periksa tiap PDB ID ke RCSB
      (resolusi ≤ 2,5 Å, ligan ada, rantai benar) — data resolusi/tanggal diambil dari API, bukan diketik.
   b. Per target: unduh → pisahkan ligan kristal → prep_reseptor → kotak = pusat ligan kristal + margin (dihitung)
      → redocking (Vina, exhaustiveness 8, seed tercatat) → RMSD simetri-sadar terhadap pose kristal.
      Hanya RMSD ≤ 2 Å yang masuk panel; yang gagal dicatat beserta alasannya.
   c. Umpan: 50 molekul mirip-obat dari sumber nyata yang dicatat (mis. ChEMBL acak dengan seed tercatat, atau DUD-E
      bila tersedia), sama untuk semua target; docking ke tiap target → z_rata, z_sd, n_umpan dari skor nyata.
   d. Tulis virmolab/data/panel_target/<kelas>.json + <kelas>/<PDB>.pdbqt, dan dev/panel_kandidat/log_<kelas>.jsonl
      (satu baris per langkah: waktu, PDB, langkah, hasil, durasi). Kemajuan disimpan per target sehingga skrip bisa
      dilanjutkan setelah terputus (lewati target yang sudah selesai).
   e. Jalankan di latar belakang; perkiraan waktu dihitung dari target pertama, laporkan ke pengguna sebelum lanjut.
2. Dialog: tombol "Mulai" dengan jalur struktur aktif membuat job lewat antrean.job_baru (satu job per target sah,
   jeda/lanjut memakai antrean yang ada); hasil dikumpulkan dengan target_balik.kumpulkan saat job selesai.
3. gabung(): kunci per UniProt (bukan gen); target ChEMBL tanpa UniProt pakai target_chembl_id.
4. Uji: dev/uji_target_balik.py tetap lulus; tambah uji yang memeriksa panel nyata: tiap .pdbqt > 50 KB dan berisi
   ATOM protein, rmsd_redocking ≤ 2, n_umpan ≥ 30, z_sd > 0, dan tiap entri punya baris log redocking yang cocok.
   Uji jalur struktur: 1 ligan (ibuprofen) × panel antiinflamasi → laporkan z-skor PTGS1/PTGS2 apa adanya
   (jangan memaksa lulus).
5. build_tools/virmolab.spec sudah menyertakan panel_target bila ada — pastikan ukuran total wajar.
6. Penutup: poin 1–8 Blok verifikasi wajib; buka dialog via dev/uji_dialog_lanjut_gui.py target_balik dan lihat
   tangkapan layar. Laporan akhir ≤ 15 baris: berapa target lolos/gagal per kelas dan alasannya, waktu total,
   apa yang belum teruji.
Aturan: jangan commit/build/regresi penuh.
```

### P7 — F3b Jaringan & pengayaan jalur (Opus) · setelah P6

```text
Kerjakan F3 tahap b "Jaringan & pengayaan jalur" VirmoLab 1.3. Folder: E:\Bikin Docking Simpel\VirmoLab.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).
Baca juga bagian "Blok verifikasi wajib" di PROMPT_SISA.md dan patuhi.

Baca dulu: RENCANA_PENGEMBANGAN.md §3 F3 + §5; PROMPT_PENGEMBANGAN.md "Lampiran UI" + "UI F3b"; core/graf.py dan
core/sumber_data.py; core/target_balik.py dan ui/dialog_target_balik.py (P6).

Verifikasi dulu (sumber resmi, catat ke RENCANA, ganti tanda [cek] jadi [terverifikasi <tanggal>, sumber]): lisensi dan
endpoint Open Targets Platform GraphQL, berkas GMT Reactome (lisensi), GO GMT manusia, API STRING (lisensi, batas laju).
KEGG HANYA tautan luar. Unduhan GMT ke virmolab/data/gmt/: minta izin pengguna dulu (AskUserQuestion) dengan ukuran.
Catatan: Wikidata Query Service memisahkan graf artikel ilmiah ke query-scholarly.wikidata.org — endpoint layanan lain
bisa berubah serupa; uji kueri nyata sebelum menulis kode.

Tugas:
1. core/pengayaan.py: baca_gmt(path) ; hipergeometrik(gen, set_gen, latar) + Benjamini–Hochberg ;
   keluaran [{jalur, n_overlap, n_set, p, q, gen}]. Latar = gen panel/anotasi (jelaskan di laporan).
2. core/jaringan.py: bangun(senyawa→target dari P6, target→jalur dari pengayaan, target↔target STRING ambang s,
   target→penyakit Open Targets skor ≥ 0,5) -> networkx.Graph berlapis atribut jenis ;
   metrik (derajat, betweenness, closeness) ; sensitivitas(ambang_STRING=[0.4,0.7,0.9], ambang_target=[…]) ->
   simpul inti stabil (muncul di ≥ 80 % kombinasi) ; semua permintaan via sumber_data (Jejak tercatat).
3. UI tab "Jaringan & jalur" sesuai "UI F3b".
4. Ekspor GraphML + CSV tepi (Cytoscape) + SVG/PNG (komposer).
5. Uji dev/uji_jaringan.py: pengayaan pada set gen sintetis dengan jawaban diketahui; BH benar vs hitungan manual;
   graf sintetis → simpul inti stabil sesuai harapan; GraphML pulang-pergi.
6. Paragraf metode WAJIB memuat: basis data + versi + tanggal, ambang tiap tepi, hasil uji sensitivitas, latar pengayaan,
   kalimat "hipotesis".
7. Penutup: poin 1–8 Blok verifikasi wajib.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

---

### P8 — F5 QSAR & model ML (Opus) · rilis 1.4

```text
Kerjakan F5 "QSAR & model ML" VirmoLab 1.4. Folder: E:\Bikin Docking Simpel\VirmoLab.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).
scikit-learn 1.9.1 dan chemprop 2.3.1 SUDAH terpasang — jangan pasang paket lain.
Baca juga bagian "Blok verifikasi wajib" di PROMPT_SISA.md dan patuhi.

Baca dulu: RENCANA_PENGEMBANGAN.md §0, §3 F5, §5; PROMPT_PENGEMBANGAN.md "Lampiran UI" + "UI F5"; core/chembl.py
(format data aktivitas); core/mmp.py (activity cliff); core/kontribusi.py (peta atom); core/admet.py (cara memanggil
chemprop di proses terpisah); ui/panel_hasil.py (cara menambah kolom).

Tugas:
1. core/qsar.py: muat_data(csv|chembl) dengan konversi satuan → pIC50 ; kurasi (standarisasi seperti core/tanaman.standarisasi,
   gabung duplikat median, tandai rentang > 1 log, tandai activity cliff) ; fitur(deskriptor RDKit 2D tersaring, Morgan2
   2048, MACCS, gabungan) ; bagi(acak|kerangka Bemis–Murcko, uji=0.2, benih) ; latih(model, fitur, penyetelan CV5 di
   dalam set latih) untuk RF, SVR, kNN, GP, Ridge (+ klasifikasi) ; validasi(): Q², R²_pred, RMSE, MAE, Golbraikh–Tropsha,
   ROC-AUC/MCC/BA ; y_acak(n=50) ; domain(leverage h*, kNN Tanimoto) ; kepentingan_permutasi ; simpan/muat model joblib +
   kartu_model.json (hash data, fitur, metrik, versi paket, tanggal).
2. core/konformal.py: split conformal regresi & klasifikasi (90 %), ±40 baris, tanpa paket baru.
3. Opsi Chemprop D-MPNN: pelatihan di proses terpisah (pola admet), batas waktu & batal; nonaktif bila data < 200 senyawa.
4. UI wizard sesuai "UI F5". Pelatihan > 5 s di proses/utas dengan bilah progres dan tombol Batal.
5. Prediksi ligan proyek → kolom panel Hasil "pIC50 prediksi" (± interval, ikon "di luar domain").
6. Uji dev/uji_qsar.py: data publik kecil berlisensi terbuka di dev/data/ (verifikasi lisensinya) → RF R²_uji ≥ 0,7
   (pembagian acak); Y-acak R² rata < 0,2; cakupan konformal 0,85–0,95; domain menandai senyawa yang jauh; simpan-muat model
   menghasilkan prediksi identik. Laporkan R² pembagian kerangka juga (biasanya jauh lebih rendah — itu temuan, bukan galat).
7. Laporan: metrik kedua pembagian, prediksi vs terukur, plot Williams, Y-acak, kartu model; kalimat prinsip OECD.
8. Penutup: poin 1–8 Blok verifikasi wajib.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

### P9 — F4 Penapisan farmakofor & bentuk (Sonnet)

```text
Kerjakan F4 "Penapisan berbasis ligan 3D" VirmoLab 1.4. Folder: E:\Bikin Docking Simpel\VirmoLab.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).
Baca juga bagian "Blok verifikasi wajib" di PROMPT_SISA.md dan patuhi.

Baca dulu: RENCANA_PENGEMBANGAN.md §0, §3 F4; PROMPT_PENGEMBANGAN.md "Lampiran UI" + "UI F4"; core/kemiripan.py (fitur
farmakofor yang sudah ditampilkan); core/uji.py (AUC/BEDROC/EF); virmolab/viewer/viewer.js (cara menambah bentuk 3D,
fungsi VM.*); core/pustaka.py. rdkit.Chem.rdShapeAlign tersedia (AlignShapes, ScoreShape, ShapeInput) — terverifikasi.

Tugas:
1. core/farmakofor.py: kueri_dari_pose(mol, protein=None, fitur_aktif, toleransi=1.0, eksklusi=True) ;
   konformer(mol, n=30, prune=0.5) ETKDGv3 ; cocokkan(kueri, mol) -> {n_cocok, rmsd_fitur, konformer_terbaik} ;
   saring_pustaka(kueri, daftar, n_proses, batal, progres) di proses terpisah per kelompok 500.
2. core/bentuk.py: skor_bentuk(ref, mol) via rdShapeAlign -> {tanimoto_bentuk, tanimoto_warna, gabungan} + mol terselaraskan.
3. Skor akhir = 0,5·farmakofor ternormalisasi + 0,5·bentuk-warna (bobot dapat diatur).
4. Validasi bawaan: bila tab Uji punya aktif/decoy → AUC, BEDROC, EF1 % untuk kueri saat ini (hanya dari hasil nyata).
5. viewer.js: VM.tampilFarmakofor(fitur) bola transparan per jenis (warna dari token tema yang diteruskan Python) + bola
   eksklusi abu-abu; VM.hapusFarmakofor().
6. UI sesuai "UI F4". Hasil teratas → [Kirim N teratas ke docking] (job di antrean).
7. Uji dev/uji_farmakofor.py: kueri dari MK1 (1HSG) → MK1 skor maksimum; molekul acak skor rendah; 10 000 senyawa
   (COCONUT lokal bila ada) < 15 menit atau LEWAT dengan pesan; skor bentuk ke dirinya = 1 ± 0,01.
8. Penutup: poin 1–8 Blok verifikasi wajib (viewer: periksa juga bahwa bola fitur tampil di jendela, bukan hanya fungsi JS ada).
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

### P10 — F12 Pelacak hipotesis → uji lab (Sonnet) · setelah P8

```text
Kerjakan F12 "Pelacak hipotesis → uji lab" VirmoLab 1.4. Folder: E:\Bikin Docking Simpel\VirmoLab.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).
Baca juga bagian "Blok verifikasi wajib" di PROMPT_SISA.md dan patuhi.

Baca dulu: RENCANA_PENGEMBANGAN.md §3 F12; PROMPT_PENGEMBANGAN.md "Lampiran UI"; core/proyek.py (eksperimen);
core/labplanner.py; ui/dialog_labplanner.py; core/statistik.py; core/qsar.py (P8).

Tugas:
1. Perluas proyek.eksperimen: entri {id, ligan_id, assay, nilai, satuan, pIC50, tanggal, catatan, status_hipotesis
   (diajukan|diuji|didukung|ditolak)}. Migrasi data lama tanpa kehilangan isi (uji pulang-pergi proyek lama).
2. core/hipotesis.py: bandingkan(prediksi: ΔG, MM/GBSA, pIC50_pred, konsensus) vs terukur → Spearman ρ, Kendall τ
   (+ CI bootstrap 1000×), n; peringatan bila n < 8; ligan tanpa pasangan dilewati dan dihitung.
3. UI: tab "Hipotesis" di dialog Rencana lab: tabel ligan × (prediksi, terukur, status); impor CSV plate reader;
   grafik prediksi vs terukur per jenis prediksi; tombol [Latih ulang QSAR dengan data baru] (memanggil P8).
4. Uji dev/uji_hipotesis.py: korelasi sintetis diketahui; migrasi proyek lama.
5. Penutup: poin 1–8 Blok verifikasi wajib.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 10 baris.
```

---

### P11 — F6 Konsensus docking × co-folding (Sonnet) · rilis 1.5

```text
Kerjakan F6 "Konsensus docking × co-folding" VirmoLab 1.5. Folder: E:\Bikin Docking Simpel\VirmoLab.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).
Baca juga bagian "Blok verifikasi wajib" di PROMPT_SISA.md dan patuhi.

Baca dulu: RENCANA_PENGEMBANGAN.md §3 F6 + §5; PROMPT_PENGEMBANGAN.md "Lampiran UI" + "UI F6"; core/lanjutan.py (Boltz
lewat WSL: status, perintah, folder keluaran); core/qc.py (PoseBusters); core/konsensus.py; core/validasi_protokol.py
(_superposisi — pakai ulang untuk penyelarasan); analisis IFP.
Verifikasi di WSL: versi Boltz terpasang dan NAMA KUNCI keluaran afinitas dari berkas keluaran nyata — bukan ingatan.

Tugas:
1. core/kofolding.py: jalankan(seq_reseptor, smiles, n_sampel=5, afinitas=True) via lanjutan (WSL) ;
   baca_keluaran(folder) ; sejajarkan_ke_reseptor(struktur, reseptor_proyek, residu_kantong) Kabsch Cα ;
   banding(pose_docking, pose_cofold) -> {rmsd, ifp_tanimoto, posebusters_docking, posebusters_cofold} ;
   label(...) -> Sepakat | Sebagian | Bertentangan dengan aturan tertulis ;
   kebaruan(smiles) -> Tanimoto maks ke ligan PDB (RCSB chemical search via sumber_data, cache) + peringatan < 0,3.
   Kegagalan Boltz/WSL = None + pesan, bukan nilai bawaan.
2. Kolom baru di konsensus: "Boltz-2 afinitas" dan "Kesepakatan".
3. UI sesuai "UI F6" (tab Co-folding di panel Properti + kolom konsensus).
4. Uji dev/uji_kofolding.py: keluaran Boltz tersimpan (dev/data/boltz_1hsg/) → pembacaan, penyelarasan, label; bagian
   WSL nyata di belakang --daring.
5. Dokumen: jelaskan kebocoran data latih (1HSG ada di PDB → kesepakatan tinggi bukan bukti).
6. Penutup: poin 1–8 Blok verifikasi wajib.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

### P12 — F10 Docking peptida (Sonnet) · setelah P11

```text
Kerjakan F10 "Docking peptida" VirmoLab 1.5. Folder: E:\Bikin Docking Simpel\VirmoLab.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).
Baca juga bagian "Blok verifikasi wajib" di PROMPT_SISA.md dan patuhi.

Baca dulu: RENCANA_PENGEMBANGAN.md §3 F10; PROMPT_PENGEMBANGAN.md "Lampiran UI"; core/kofolding.py (P11);
core/md.py (minimisasi, mmgbsa_pose); core/ppi.py.
Cek lisensi AutoDock CrankPep (ADCP) dari sumber resmi; bila tidak jelas/bukan open-source, JANGAN dipakai.

Tugas:
1. core/peptida.py: validasi_sekuens (≤ 30 residu, 20 standar + non-standar yang didukung Boltz) ;
   cofold_peptida(seq_reseptor, seq_peptida, n=5) via kofolding ; pemurnian (minimisasi + 100 ps implisit OpenMM) ;
   mmgbsa ; antarmuka via ppi.
2. UI: Siapkan › Langkah 2 · Ligan › "Peptida dari sekuens…": kotak sekuens (huruf satu), validasi langsung (residu tak
   dikenal disorot merah), [Jalankan] → hasil sebagai objek kompleks + tabel antarmuka.
3. Uji dev/uji_peptida.py: validasi sekuens; keluaran Boltz tersimpan MDM2–p53 (1YCR) → RMSD Cα peptida < 3 Å (luring);
   nyata di belakang --daring.
4. Penutup: poin 1–8 Blok verifikasi wajib.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 10 baris.
```

### P13 — F7 Sifat elektronik xTB (Sonnet) · butuh izin unduh

```text
Kerjakan F7 "Sifat elektronik kuantum (xTB)" VirmoLab 1.5. Folder: E:\Bikin Docking Simpel\VirmoLab.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).
Baca juga bagian "Blok verifikasi wajib" di PROMPT_SISA.md dan patuhi.

Langkah 0 (wajib): verifikasi dari GitHub resmi grimme-lab/xtb versi rilis terbaru, lisensi, ukuran biner Windows; juga
status g-xTB (rilis resmi? lisensi?). Tanya izin unduh ke pengguna (AskUserQuestion) dengan nama berkas, sumber, ukuran.
Pasang ke vendor/bin/xtb/ ; tambahkan ke LISENSI_PIHAK_KETIGA dan spec PyInstaller.

Baca dulu: RENCANA_PENGEMBANGAN.md §3 F7; PROMPT_PENGEMBANGAN.md "Lampiran UI" + "UI F7"; core/lanjutan.cari_program;
pola proses terpisah di core/md.py; core/metabolisme.py; viewer.js (permukaan).

Tugas:
1. core/xtb.py: tersedia() ; hitung(mol, pelarut="water", fukui=True, esp=True, batas=300, batal) di proses terpisah,
   folder kerja sementara ; urai xtbout.json / fukui / charges / esp ; deskriptor HOMO, LUMO, celah, η, μ, ω, dipol ;
   paralel per inti CPU untuk banyak ligan. Kegagalan/konvergensi gagal = None + pesan.
2. UI sesuai "UI F7"; atom diwarnai Fukui di viewer; permukaan ESP; korelasi otomatis dengan SoM CYP.
3. Kalimat wajib di dialog & laporan: "GFN2-xTB semi-empiris; celah HOMO–LUMO cenderung lebih kecil dari DFT, pakai untuk
   tren antar-ligan, bukan nilai absolut. Bukan DFT."
4. Uji dev/uji_xtb.py: celah benzena > anilin; f⁻ anilin terbesar di orto/para; LEWAT bila xtb absen.
5. Penutup: poin 1–8 Blok verifikasi wajib (+ butir "xTB" di core/ujimandiri.py, + biner masuk spec).
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

---

### P14 — F8 Desain generatif terpandu docking (Opus) · rilis 1.6 · butuh izin unduh

```text
Kerjakan F8 "Desain generatif terpandu docking" VirmoLab 1.6. Folder: E:\Bikin Docking Simpel\VirmoLab.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).
Baca juga bagian "Blok verifikasi wajib" di PROMPT_SISA.md dan patuhi.

Langkah 0: verifikasi CReM (lisensi, versi, ukuran DB fragmen, cara membuat DB kecil sendiri dari ChEMBL/COCONUT lokal).
Tanya izin pengguna untuk paket crem + DB (sebut ukuran). Bila DB terlalu besar, buat DB kecil sendiri.

Baca dulu: RENCANA_PENGEMBANGAN.md §3 F8; PROMPT_PENGEMBANGAN.md "Lampiran UI" + "UI F8"; core/fbdd.py; core/mpo.py;
core/sascore.py; core/antrean.py; core/graf.py.

Tugas:
1. core/generatif.py: generasi(induk, operasi=mutate|grow|link, radius=2, maks=500) ; saring(PAINS, Brenk, SA ≤ 4,
   QED ≥ 0,4, MPO, kebaruan < 0,8) ; docking_cepat (exh 4) → 20 teratas docking penuh ; pareto(ΔG, QED, SA) ;
   siklus(n_generasi=3, batal, progres) di proses terpisah ; silsilah (graf induk→anak). Docking gagal = dikeluarkan + dihitung.
2. UI sesuai "UI F8". Kandidat bisa diimpor sebagai ligan proyek dengan l["asal"]={"sumber":"generatif",…}.
3. Uji dev/uji_generatif.py: dari MK1 generasi 1 ≥ 50 analog valid, tanpa duplikat InChIKey, semua lolos sanitasi;
   pareto benar pada data sintetis.
4. Penutup: poin 1–8 Blok verifikasi wajib.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

### P15 — F9 Energi bebas relatif RBFE, eksperimental (Opus) · butuh izin unduh & GPU

```text
Kerjakan F9 "Energi bebas relatif (RBFE) eksperimental" VirmoLab 1.6. Folder: E:\Bikin Docking Simpel\VirmoLab.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).
Baca juga bagian "Blok verifikasi wajib" di PROMPT_SISA.md dan patuhi.

Langkah 0: verifikasi OpenFE (versi terbaru, lisensi, dependensi: kartograf/lomap, gufe, openmmtools) dan kecocokan dengan
openmm 8.6.1 + tumpukan OpenFF yang SUDAH terpasang (CATATAN_TAHAP2 §4l). Simpan pip freeze > build/pip_sebelum_rbfe.txt.
Tanya izin pengguna (daftar paket + ukuran). Bila konflik versi dengan tumpukan MD yang ada → BERHENTI dan laporkan;
jangan memaksa upgrade.

Baca dulu: RENCANA_PENGEMBANGAN.md §3 F9; PROMPT_PENGEMBANGAN.md "Lampiran UI"; core/md.py (platform_terbaik,
uji_kecepatan, pola tugas); core/mmp.py.

Tugas:
1. core/rbfe.py: pasangan_dari_mmp(seri) (perubahan ≤ 10 atom berat) ; peta_atom ; jaringan(bintang|MST) ;
   jalankan_tepi(λ=11, replika=3, ns_per_λ) di proses terpisah dengan jeda/lanjut ; analisis MBAR ; ΔΔG ± galat ;
   cycle closure sebagai cek konsistensi.
2. UI: "Energi bebas relatif (eksperimental)…": pilih seri dari MMP → graf perturbasi → estimasi waktu (wajib tampil sebelum
   mulai) → jalankan → tabel ΔΔG + plot vs ΔΔG docking/terukur. Mode CPU nonaktif dengan pesan jelas. Menu hanya di mode ahli.
3. Uji dev/uji_rbfe.py: pemetaan atom benzena→toluena; jaringan benar; MBAR pada data sintetis; simulasi nyata di belakang
   --daring --gpu.
4. Penutup: poin 1–8 Blok verifikasi wajib; label "eksperimental" di menu, dokumen, dan laporan.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

---

## 4. Daftar periksa peninjauan (untuk Anda atau sesi peninjau)

Setelah tiap prompt selesai, minta sesi baru "periksa pekerjaan terakhir" dengan daftar ini — cara ini menemukan 9 dari 10
cacat serius di F1/F2/F11:

- [ ] `git status` + `git diff --stat`: hanya berkas yang masuk akal? Berkas data baru tidak terabaikan `.gitignore`?
- [ ] `pyflakes virmolab` bersih; semua uji baru lulus; uji penjaga (lihat poin 4 Blok verifikasi) masih lulus.
- [ ] Buka dialog baru (harness GUI) di tema terang dan gelap; lihat tangkapan layarnya: kosong/angka aneh/warna tetap/tombol ganda?
- [ ] Cari di kode baru: `np.random`, `random.`, nilai literal di jalur hasil, `except Exception: pass`, `return 0.0`/`99.0`
  sebagai sentinel, `QMessageBox.information(... "Simulasi ...")`, warna `#xxxxxx` di UI.
- [ ] Angka yang tampil masuk akal secara ilmiah? (okupansi ≤ 100 %, ikatan H > 0 bila memang ada, RMSD tidak 0,0 persis.)
- [ ] Paragraf metode/laporan hanya memuat uji yang dijalankan, dengan angka dari hasil, dan menyebut keterbatasannya.
- [ ] Teks UI baru sudah diterjemahkan (audit kamus 0 masalah); CHANGELOG sesuai kenyataan (bukan klaim yang belum benar).
- [ ] Data bawaan baru masuk `build_tools/virmolab.spec`.

---

## 5. Catatan teknis yang sering dibutuhkan

- Menu: `ui/mainwindow.py` — fungsi `_menu` (±baris 740+), submenu Analisis lewat `self._sub(m, "<judul>", (A(...), ...))`;
  format `A("Label…", "ikon", self.buka_x, None, "tooltip")`. Palet perintah: dict nama→fungsi (±baris 428).
- Pembuka dialog: `ui/mainwindow_dialog.py` (mixin `PembukaDialog`), pola `d = Dialog(self, ...); d.setAttribute(Qt.WA_DeleteOnClose); d.show()`.
- API `kit` (`ui/kit.py`): `judul(teks, sub)`, `catatan(teks, jenis)`, `lencana`, `Kartu(label, nilai, ket).isi(nilai, ket, nada)`,
  `baris_kartu`, `tabel(kolom, regang, urut)`, `sel`, `tombol(teks, fn, utama, tip)`, `bar_bawah(dialog, kiri, kanan)`,
  `f(v, d, satuan)`, `warna(token)`, `hx(token)`, `mode()`, `sibuk`, `bilah_sibuk`. Token warna: `acc, bad, ok, warn, mut, ink, ink2, line, panel, …`
  (BUKAN `err`/`sukses`/`putih`).
- Pekerjaan latar: `kerja.jalankan(fn, selesai=, galat=, log=, progres=)` memanggil `fn(..., lapor=SinyalKerja)`;
  `lapor.log.emit(str)`, `lapor.progres.emit(i, total, teks)`. Pembatalan: kirim callable `batal` ke fungsi inti.
- Proyek: `Proyek.p(rel)`, `.reseptor["pdbqt"]`, `.validasi` (redocking terakhir), `.job[*].ligan[*]` (`status`, `qc`, `energi`, `rmsd_kristal`),
  `.jejak` / `.catat_jejak(Jejak)`; kotak docking di `jendela.box = {"pusat","ukuran","spasi"}`.
- Data internet: selalu lewat `core/sumber_data.py` (`ambil_json`, `sparql`, cache, Jejak). Wikidata: graf artikel ilmiah di
  `https://query-scholarly.wikidata.org/sparql` (DOI P356, tanggal P577, judul P1476); graf utama hanya memuat nomor item artikel.
- Superposisi struktur: `core/validasi_protokol._superposisi(ca_dari, ca_ke)` (Kabsch, Cα bersama); `ligan_kristal_terbesar(teks_pdb, resn)`.
- Rilis: `build_tools/rilis.py` (docs → build → uji mandiri → installer + portable + SHA256SUMS). Uji mandiri dalam aplikasi: `core/ujimandiri.py`.
- Terakhir dibuild: 1.1.2 — Setup 476 MB, Portable 681 MB, uji mandiri 40/40.
