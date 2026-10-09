# VirmoDock — Rencana Lengkap Seluruh Tahap

Dokumen ini adalah peta kerja detail dari awal sampai rilis. Baca bersama `CATATAN_TAHAP2.md` (konteks, keputusan teknis, jebakan yang sudah ditemui).

**Status ringkas**

| Tahap | Isi | Status |
|---|---|---|
| 0 | Perbaikan aplikasi lama + mockup | Selesai |
| 1 | Kerangka aplikasi, viewer, impor, deteksi GPU, gaya ala PyMOL | Selesai |
| 2 | Preparasi reseptor/ligan, grid box, mesin docking, antrean job | Selesai (8 Okt 2026; uji GPU AMD/Intel menunggu relawan) |
| 3 | Analisis hasil, interaksi 3D/2D, validasi, ekspor, proyek | Selesai inti MVP (8 Okt 2026; sisa v1.x di CATATAN §4c) |
| 4 | Packaging, installer, portable, pindah laptop, dokumentasi | Selesai (8 Okt 2026; uji relawan & GitHub menunggu) |

**Aturan umum untuk semua tahap**
- Bahasa UI: Indonesia. Istilah ilmiah standar boleh tetap Inggris (PDBQT, RMSD, SMILES).
- Desain: palet di `ui/theme.py` saja (jangan warna baru di luar token), satu aksen biru, ikon dari `ui/icons.py`, sudut 2–4 px, angka monospace. Tanpa emoji, glow, kartu bulat besar.
- Semua proses berat lewat `ui/kerja.py` (thread) atau `QProcess`; UI tidak boleh freeze.
- Setiap fitur baru: uji dengan `dev/uji_layar.py` (tangkap jendela saja, jangan layar).
- Galat ditampilkan jelas di panel **Pesan**: apa yang gagal + apa yang harus dilakukan pengguna.

---

## Tahap 0 — Aplikasi lama & mockup (SELESAI)
- [x] `DockingSimpel.exe` (web UI + WSL): bug "GPU tidak terbaca" diperbaiki (race condition saat WSL cold start), tombol "Periksa ulang", info VRAM/driver.
- [x] Mockup jendela utama gaya Discovery Studio, terang & gelap → `E:\Bikin Docking Simpel\mockup\`. **Disetujui pengguna**, dengan tambahan: pemilihan warna & surface ala PyMOL, nama aplikasi **VirmoDock**, harus bisa dipasang di semua laptop.

## Tahap 1 — Kerangka (SELESAI)
- [x] Build AutoDock-GPU **OpenCL native Windows** (`vendor/bin/autodock_gpu.exe`) + `OpenCL.dll` + `vcomp140.dll`; teruji sama dengan versi CUDA.
- [x] Vina 1.2.7, autogrid4, autodock4, clinfo di `vendor/bin`.
- [x] `core/env.py` deteksi GPU/CPU/RAM/software eksternal tiap start; panduan driver per vendor.
- [x] Jendela PySide6: menu, toolbar, dock panel, tema gelap/terang, simpan layout.
- [x] Viewport 3Dmol + QWebChannel: pilih atom, ukur jarak, tooltip, gizmo, putar.
- [x] Impor PDB/PDBQT/CIF/SDF/MOL2/SMILES, RCSB, PubChem, drag-drop; pemecahan protein/ligan/air/ion.
- [x] Hierarki + menu konteks, panel Tampilan ala PyMOL (representasi, warna, permukaan, transparansi).
- [x] First-run wizard, "Buka di…" PyMOL/ChimeraX/DSV.

---

## Tahap 2 — Preparasi & Docking (SELESAI — rincian di CATATAN_TAHAP2.md §4b)

### 2.1 Model data proyek (kerjakan pertama, dipakai semua fitur berikutnya)
File baru: `core/proyek.py`.
- Kelas `Proyek`: `folder`, `nama`, `reseptor` (Objek + path PDBQT), `ligan` (daftar `LiganItem`: nama, sumber, path SDF asli, path PDBQT, status, info), `kotak` (pusat, ukuran, spasi), `parameter` (mesin, perangkat, nrun/exhaustiveness, num_modes, energy_range, seed, max_eval), `job` (riwayat), `hasil`.
- Struktur folder proyek:
  ```
  NamaProyek.vmd/
    proyek.json          ← semua metadata & parameter
    reseptor/  asli.pdb, bersih.pdb, reseptor.pdbqt, laporan_prep.txt
    ligan/     sumber/*.sdf, pdbqt/*.pdbqt
    grid/      reseptor.gpf, reseptor.glg, *.map, reseptor.maps.fld
    hasil/<id_job>/  <ligan>.dlg | <ligan>_out.pdbqt, log/, ringkasan.csv
  ```
- Simpan otomatis setiap perubahan penting (debounce 1 s). `File › Simpan proyek` dan `Buka proyek` (pilih folder `.vmd`).
- **Kriteria selesai:** tutup aplikasi lalu buka lagi → reseptor, ligan, kotak, parameter kembali persis.

### 2.2 Preparasi reseptor
File: `core/prep_reseptor.py`, dialog `ui/dialog_reseptor.py`. Aksi `a_rec`.
- Dialog: pilih objek protein, centang rantai, opsi:
  - Hapus air (default ya), hapus ligan asli (ya), **pertahankan ion logam** (Zn, Mg, Fe, Mn, Ca, Cu, Co, Ni — default ya jika dalam 8 Å dari ligan asli)
  - Altloc: ambil A / ambil okupansi tertinggi
  - Muatan: Gasteiger (Meeko, default) atau Kollman (via Open Babel `--partialcharge`? catat bila tidak tersedia)
  - Tambah hidrogen polar (default) / semua hidrogen
- Alur kode:
  1. gemmi: baca → `remove_alternative_conformations` → `remove_hydrogens` → filter rantai → hapus air/ligan sesuai opsi → `setup_entities` → tulis `bersih.pdb` (pastikan kolom elemen terisi).
  2. Meeko: `mk_prepare_receptor --read_pdb bersih.pdb -o reseptor -p -a` (panggil lewat `subprocess` ke `.venv` atau langsung API `meeko.Polymer.from_pdb_string`). Tangkap daftar residu yang dibuang (`-a`) → tampilkan sebagai peringatan + tulis ke `laporan_prep.txt`.
  3. Cadangan bila Meeko gagal: Open Babel `obabel bersih.pdb -xr -h --partialcharge gasteiger -O reseptor.pdbqt`.
  4. Ion logam dipertahankan: tambahkan baris ion ke PDBQT dengan tipe AD4 yang sesuai (Zn, Mg, Fe, Mn, Ca) dan muatan formal.
- Hasil jadi objek baru "Reseptor (siap)" di Hierarki, ikon centang.
- **Kriteria selesai:** 1HSG dan 1ITB (PDB lama tanpa kolom elemen) berhasil; jumlah atom ±1% dari MGLTools; residu cacat dilaporkan.

### 2.3 Preparasi ligan (batch)
File: `core/prep_ligan.py`, dialog `ui/dialog_ligan.py`. Aksi `a_lig`.
- Input: objek ligan di Hierarki (pilih banyak), atau tambah dari file/folder/PubChem/SMILES langsung di dialog.
- Opsi: pH protonasi (default 7.4, Open Babel `-p`), minimisasi (MMFF94, 500 langkah, default ya), buat konformer 3D jika 2D, pertahankan stereo, makrosiklik fleksibel (Meeko `rigid_macrocycles=False`).
- Alur per ligan (paralel, `ThreadPoolExecutor(max_workers = inti/2)`):
  1. RDKit mol (H eksplisit) → protonasi: tulis SDF → `pybel` `OBMol.CorrectForPH(pH)` → kembali ke RDKit.
  2. `AllChem.MMFFOptimizeMolecule` (cadangan UFF).
  3. Meeko `MoleculePreparation().prepare(mol)` → `PDBQTWriterLegacy.write_string(setup)` → simpan PDBQT.
  4. Validasi: torsi ≤ 32 dan atom ≤ 256 (batas AD-GPU), tipe atom didukung (B, Si → tandai), tidak ada atom tumpang tindih.
- Tabel di dialog: nama, rumus, MW, torsi, status (siap / peringatan / gagal + alasan). Ligan siap muncul di Hierarki di grup "Ligan siap docking".
- **Kriteria selesai:** 100 nama PubChem → < 3 menit, gagal tidak menghentikan yang lain, alasan gagal jelas.

### 2.4 Panel Parameter Docking
File: `ui/panel_docking.py`, dock kanan tab "Parameter" (tabify dengan Properti/Tampilan).
- Bagian **Mesin**: segmen AD-GPU / Vina / AD4. Mesin yang programnya tidak ada → nonaktif + tooltip alasan.
- Bagian **Perangkat**: GPU (nama) / CPU (n thread). AD-GPU tanpa OpenCL → otomatis pindah ke Vina + pesan.
- Bagian **Pencarian** (berubah sesuai mesin):
  - AD-GPU: jumlah run (10/50/100/kustom), max evaluasi (2.5 M), heuristik on/off, seed.
  - Vina: exhaustiveness (8–64), num_modes (9), energy_range (3), seed, CPU thread.
  - AD4: ga_run, ga_pop_size, ga_num_evals.
- Bagian **Grid box**: pusat X/Y/Z, ukuran X/Y/Z (Å), spasi (0.375), tombol: "Pusat ke ligan asli", "Pusat ke residu terpilih", "Seluruh protein (blind)", "Sesuaikan ke ligan +8 Å". Peringatan bila > 126 titik grid (otomatis naikkan spasi) atau ukuran > 30 Å.
- Preset tersimpan: "Cepat", "Standar", "Teliti", plus simpan preset kustom.

### 2.5 Grid box interaktif di viewport
File: `viewer/viewer.js` (tambah mode `kotak`), `viewer_widget.py` (sinyal `kotakBerubah`).
- Mode "Grid box" (tombol toolbar `a_box`, tombol G): tampilkan 6 pegangan (bola di tengah tiap sisi) + pegangan pusat.
- Drag pegangan sisi = ubah ukuran sumbu itu; drag pusat = geser (proyeksikan gerak mouse ke bidang layar → koordinat dunia; 3Dmol: gunakan `viewer.modelToScreen`/`screenToModel` atau hitung dari `getView()`).
- Alternatif yang lebih mudah dan tetap memenuhi syarat: Shift+drag = geser, Ctrl+scroll = ubah ukuran seragam, Alt+scroll = ubah satu sumbu terpilih.
- Setiap perubahan → `py.kotak(JSON)` → panel Parameter tersinkron dua arah (debounce 100 ms).
- **Kriteria selesai:** ubah dengan mouse dan angka, keduanya selalu sama; box ikut tema (aksen biru).

### 2.6 Mesin docking
File: `core/mesin.py` (antarmuka sama untuk semua mesin).
```python
class Mesin:
    def siapkan(self, proyek): ...            # grid map bila perlu
    def perintah(self, ligan, keluaran): ...  # list argumen subprocess
    def baca_progres(self, baris): ...        # -> (persen, pesan) atau None
    def baca_hasil(self, keluaran): ...       # -> daftar Pose(energi, rmsd_lb, rmsd_ub, koordinat, klaster)
```
- **AutoGrid** (AD-GPU & AD4): tulis GPF (port `tulis_gpf` dari `E:\Bikin Docking Simpel\app\server.py`: union tipe atom semua ligan, npts genap ≤126) → `autogrid4.exe -p reseptor.gpf -l reseptor.glg` di folder `grid/`. Pakai ulang map jika GPF identik (hash).
- **AutoDock-GPU**: `autodock_gpu.exe --ffile grid/reseptor.maps.fld --lfile L.pdbqt --nrun N --resnam hasil/<job>/L --xmloutput 0 --seed S [--nev M --heuristics 0]`. cwd = folder `bin` tidak perlu; kernel tertanam. Progres: baris tabel generasi `| ... |`. Hasil: parse `.dlg` (port `baca_dlg` dari `app\engine\dockgpu.py`).
  - Galat OpenCL (mis. "clGetPlatformIDs", "build program failure") → tandai GPU tidak bisa dipakai, jalankan ulang job dengan Vina, beri tahu pengguna.
- **Vina**: `vina.exe --receptor R.pdbqt --ligand L.pdbqt --center_x .. --size_x .. --exhaustiveness E --num_modes K --energy_range D --seed S --cpu C --out L_out.pdbqt`. Progres: bintang `*` (51 langkah) → persen. Hasil: tabel `mode | affinity | rmsd l.b. | rmsd u.b.` + `MODEL` di `_out.pdbqt`.
- **AutoDock4**: tulis DPF (ga_run, ga_pop_size, ga_num_evals, `ligand_types`, `fld`, `move`, `about`), `autodock4.exe -p L.dpf -l L.dlg`. Cek dulu dependensi DLL `autodock4.exe`/`autogrid4.exe` (dumpbin); bila butuh cygwin1.dll → bundel atau build dari source.
- Satu objek `Pose` seragam untuk semua mesin → tahap 3 tidak perlu tahu mesinnya.

### 2.7 Antrean job
File: `core/antrean.py`, UI `PanelAntrean`.
- `Job`: id, nama, mesin, perangkat, daftar ligan, parameter (salinan beku), status (menunggu/berjalan/dijeda/selesai/gagal/dibatalkan), progres per ligan, waktu mulai/selesai.
- Pelaksana: `QProcess` per ligan (bukan thread Python) → bisa dijeda (antar ligan) dan dibatalkan (`kill`). Satu job GPU sekaligus; job CPU paralel sesuai thread.
- Tombol di header dock Antrean: Jeda, Lanjut, Batal, Hapus selesai; klik kanan baris: buka folder hasil, jalankan ulang yang gagal, lihat log.
- Lanjut setelah aplikasi ditutup: status disimpan di `proyek.json`; saat dibuka, job "berjalan" berubah jadi "dijeda" dengan tombol Lanjutkan (lewati ligan yang sudah punya hasil).
- Notifikasi: `QSystemTrayIcon` (ikon VirmoDock) `showMessage("Docking selesai", "42 ligan · terbaik −9.95 kcal/mol")`; juga saat gagal. Taskbar progress opsional (`QWinTaskbarProgress` tidak ada di Qt6 → lewati atau pakai `ITaskbarList3` via ctypes).
- **Kriteria selesai (Tahap 2):** dari impor 1HSG → siapkan reseptor → 20 ligan PubChem → docking AD-GPU dan Vina → hasil masuk tabel; UI tetap responsif saat docking, minimize tidak menghentikan job, notifikasi muncul.

---

## Tahap 3 — Analisis & Ekspor (SELESAI inti MVP — rincian di CATATAN_TAHAP2.md §4c)

### 3.1 Tabel hasil
- Tab tengah baru "Hasil" (`ui/tab_hasil.py`): satu baris per ligan (pose terbaik) dengan kolom peringkat, ligan, ΔG (kcal/mol), Ki (perkiraan, 298 K), LE (−ΔG/atom berat), klaster teratas (n/N), RMSD l.b./u.b. (Vina) atau RMSD referensi (AD), jumlah interaksi per jenis.
- `QTableView` + `QSortFilterProxyModel`: sortir semua kolom, filter teks, filter rentang ΔG, centang untuk "Bandingkan".
- Baris dapat diperluas → semua pose (mode/klaster) ligan itu.
- Klik baris → muat pose ke viewport (objek "pose" di Hierarki, menggantikan pose sebelumnya kecuali disematkan).

### 3.2 Interaksi protein–ligan
File: `core/interaksi.py` (port & perluas `E:\Bikin Docking Simpel\app\analysis.py`).
- Jenis + kriteria (Å / derajat), semua tercatat di dokumen panduan:
  - Ikatan hidrogen: D···A ≤ 3.5, H···A ≤ 2.8, sudut D–H···A ≥ 110°
  - Hidrofobik: C nonpolar ligan ↔ C nonpolar residu hidrofobik ≤ 4.0
  - π–π: pusat cincin ≤ 5.5; tumpuk (sudut ≤ 30°, offset ≤ 3.0) / bentuk T (≥ 60°)
  - **π–kation (baru):** pusat cincin ↔ N+ LYS NZ / ARG NH1,NH2,NE / amina terprotonasi ligan ≤ 6.0
  - **Jembatan garam (baru):** gugus bermuatan berlawanan ≤ 4.0 (ASP OD1/OD2, GLU OE1/OE2 ↔ LYS/ARG/HIS; gugus karboksilat/amina ligan berdasarkan muatan formal RDKit setelah protonasi)
  - **Ikatan halogen (baru):** C–X···O/N, X···A ≤ 3.5, sudut C–X···A ≥ 140°
  - Kontak van der Waals: atom berat ≤ 4.2 (untuk diagram)
  - Logam (bila ion dipertahankan): ion ↔ O/N/S ≤ 2.8
- Panel kanan tab "Interaksi": daftar per jenis + jarak; klik → fokus residu di 3D.
- Viewport: `VM.interaksi()` sudah ada (garis putus-putus berwarna + label jarak + label residu). Toggle tiap jenis.

### 3.3 Diagram interaksi 2D
File: `ui/diagram2d.py` (render SVG; tampilkan di tab tengah "Diagram 2D" dengan `QSvgWidget` atau di QWebEngine).
- Gambar ligan 2D sungguhan dengan **RDKit** (`rdDepictor.Compute2DCoords` + `rdMolDraw2D.MolDraw2DSVG`) — lebih baik dari proyeksi PCA versi lama. Ambil koordinat atom 2D dari drawer untuk menautkan garis.
- Residu disusun melingkar sesuai arah atom kontak (algoritma relaksasi sudut dari `diagram2D` versi lama), warna lingkaran = kelas residu, garis = jenis interaksi + jarak.
- Legenda di bawah. Ekspor SVG & PNG (300/600 dpi).
- **Kriteria:** setara/lebih rapi dari diagram 2D Discovery Studio untuk 1HSG–MK1.

### 3.4 Validasi redocking
- Menu Analyze › Validasi redocking: pilih ligan asli kristal → siapkan dari koordinat kristal (pertahankan pose acuan) → docking dengan parameter yang sama → RMSD pose terbaik vs kristal (RDKit `rdMolAlign.CalcRMS` simetri-sadar, tanpa alignment).
- Laporan: RMSD (≤ 2.0 Å = valid, hijau), overlay 3D pose vs kristal (karbon abu-abu vs biru).
- Disimpan di proyek; dikutip di laporan PDF.

### 3.5 Perbandingan ligan
- Pilih 2–4 ligan di tabel → "Bandingkan": tab dengan viewport terbagi (grid 2×2, satu `Viewer` per panel, kamera tersinkron opsional) + tabel ringkas berdampingan (ΔG, LE, interaksi bersama/berbeda: residu yang sama disorot).
- Heatmap residu × ligan (warna = jenis interaksi terkuat) untuk semua hasil screening.

### 3.6 Ekspor
- Kompleks PDB (reseptor + pose terpilih), pose SDF/PDBQT, semua pose satu ligan.
- **Gambar resolusi tinggi:** render offscreen 3Dmol di kanvas besar (atur ukuran div sementara ke 4× lalu `pngURI()`), pilihan 1×/2×/4×, latar transparan/putih; SVG untuk diagram 2D.
- Tabel CSV dan **Excel** (`openpyxl`, satu sheet ringkasan + satu sheet semua pose + sheet interaksi).
- **Laporan PDF** ringkas (`QPdfWriter`/`QTextDocument` HTML → PDF): judul proyek, info reseptor & preparasi, parameter docking & perangkat, tabel 10 teratas, gambar 3D & diagram 2D ligan terbaik, hasil validasi redocking, metode singkat (kutipan software: AutoDock-GPU, Vina, Meeko, RDKit).

---

## Tahap 4 — Distribusi, Pindah Laptop, Dokumentasi (SELESAI — rincian di CATATAN_TAHAP2.md §4d)

### 4.1 Packaging
- Ikon aplikasi `virmodock/aset/virmodock.ico` (heksagon + aksen biru; adaptasi `E:\Bikin Docking Simpel\app\buat_ikon.py`).
- PyInstaller **onedir** (lebih cepat dibuka daripada onefile): `virmodock.spec` dengan data `virmodock/viewer` → `virmodock/viewer`, `vendor/bin/*` → `bin/`; hidden imports RDKit/Meeko/openbabel; sertakan `QtWebEngineProcess.exe` & resources (otomatis dari hook PySide6). `paths.BIN` sudah mencari `AKAR/bin`.
- Uji: jalankan dari folder hasil build di akun Windows lain / mesin bersih (tanpa Python, tanpa MGLTools, tanpa WSL).
- Ukuran target < 600 MB terpasang. Pertimbangkan Nuitka bila waktu buka > 4 detik.

### 4.2 Installer & portable
- Unduh Inno Setup 6 (izin sudah diberikan). Skrip `installer/virmodock.iss`: wizard Bahasa Indonesia, pilih folder, shortcut Desktop & Start Menu, uninstaller, asosiasi berkas opsional (.vmd, .pdbqt), sertakan VC++ runtime bila dibutuhkan.
- **Portable:** zip folder onedir + file `portable.flag` → bila ada, pengaturan disimpan di folder aplikasi, bukan `%LOCALAPPDATA%` (ubah `paths.APPDATA`).
- Nama hasil: `VirmoDock-Setup-x.y.z.exe`, `VirmoDock-Portable-x.y.z.zip`.

### 4.3 Pindah laptop
- Menu File › Ekspor pengaturan & proyek → satu file `.vmdbackup` (zip): QSettings (diekspor ke JSON), preset parameter, jalur software eksternal, daftar proyek terakhir, dan (opsional) folder proyek.
- File › Impor → pulihkan; jalur yang tidak ada di laptop baru diabaikan lalu dideteksi ulang.
- Deteksi GPU selalu berjalan ulang saat start (sudah) → konfigurasi menyesuaikan otomatis.

### 4.4 Perilaku jendela & DPI
- Uji 100/125/150/200% dan dua monitor beda DPI (pindahkan jendela antar layar), maximize/restore, layar kecil 1366×768 (panel bisa disembunyikan/menyusut).
- Bila geometri tersimpan berada di monitor yang sudah tidak ada → pusatkan di layar utama.
- Ikon tajam di DPI tinggi (sudah render SVG 2×; naikkan ke skala devicePixelRatio aktual).

### 4.5 Dokumentasi (Bahasa Indonesia, opsi Inggris)
Folder `docs/` → juga dibuat PDF dan dibuka dari menu Help.
1. **Instalasi baru** — unduh, jalankan setup, first-run wizard (screenshot tiap langkah).
2. **Pindah laptop** — ekspor/impor `.vmdbackup`, versi portable.
3. **Setup GPU** — NVIDIA/AMD/Intel, cara cek di VirmoDock, apa arti status di status bar.
4. **Troubleshooting** — GPU tidak terdeteksi, OpenCL gagal (fallback CPU), RCSB/PubChem gagal (internet/proxy), reseptor gagal Meeko, ligan > 32 torsi, viewport hitam (driver grafis / jalankan dengan `--disable-gpu`), antivirus memblokir.
5. **Panduan pengguna** — alur lengkap: impor → siapkan reseptor → grid box → siapkan ligan → docking → antrean → hasil → interaksi → diagram 2D → validasi → ekspor & laporan. Satu screenshot per langkah (pakai `dev/uji_layar.py`).
6. **Metode & kriteria** — definisi interaksi (§3.2), rumus Ki dan LE, parameter bawaan tiap mesin, kutipan software.

### 4.6 Kriteria selesai akhir (dari permintaan pengguna)
- [ ] Docking dari impor sampai ekspor hasil tanpa membuka software lain.
- [ ] UI tidak freeze selama docking (uji: putar molekul saat 100 ligan berjalan).
- [ ] Rapi saat maximize, resize, dan DPI berbeda.
- [ ] Instalasi di laptop baru tanpa langkah manual tambahan (uji di mesin tanpa Python/WSL/MGLTools).
- [ ] Desain lolos kriteria "anti AI slop".

---

## Urutan kerja yang disarankan untuk sesi berikutnya
1. 2.1 model proyek → 2.2 reseptor → 2.3 ligan (bisa diuji tanpa docking).
2. 2.6 mesin (AD-GPU dulu, lalu Vina, lalu AD4) + 2.4 panel parameter.
3. 2.7 antrean + notifikasi → uji end-to-end 1HSG + 20 ligan.
4. 2.5 grid box interaktif (paling rumit secara UI, boleh terakhir di Tahap 2).
5. Tahap 3 berurutan 3.1 → 3.2 → 3.3 → 3.6 → 3.4 → 3.5.
6. Tahap 4.

Perkiraan beban: Tahap 2 ≈ 1–2 sesi, Tahap 3 ≈ 2 sesi, Tahap 4 ≈ 1 sesi (tergantung model & panjang percakapan; mulai **sesi baru** tiap tahap agar hemat kuota).

---

# LAMPIRAN A — Perluasan: platform "satu aplikasi" (hasil riset web, 8 Okt 2026)

Tujuan pengguna: VirmoDock jadi **satu tempat** dari preparasi → docking → analisis → visualisasi → statistik → laporan, untuk semua orang (pemula sampai peneliti). **Prinsip:** setiap fitur canggih punya nilai bawaan aman + penjelasan singkat di UI ("Apa ini? Kapan dipakai?").

Riset dasar: GNINA 1.0 (J Cheminform 2021), PoseBusters (Chem Sci 2024), ProLIF, PLIP (NAR 2015/2021), ADMET-AI (Bioinformatics 2024), P2Rank (J Cheminform 2018), Boltz-2 (bioRxiv 2025), Boltzina (arXiv 2025), benchmark 8 program docking gratis (Front Bioinform 2025).

## A1. Asisten Alur (fitur utama untuk pemula)
Panel samping berisi checklist alur yang dianjurkan; tiap langkah hijau bila selesai, tombol "Kerjakan" membuka dialog terkait:
1. Siapkan protein & ligan; tentukan kantong dari struktur yang andal.
2. **Validasi dulu**: redocking ligan kristal (RMSD ≤ 2 Å); bila ada, uji aktif vs decoy.
3. Docking (AD-GPU / Vina).
4. Rescoring opsional (A4).
5. **Kontrol kualitas pose** (PoseBusters) sebelum meranking.
6. Analisis interaksi, filter ADMET/drug-likeness, statistik, laporan.

## A2. Deteksi kantong otomatis (Tahap 2+)
- **P2Rank** (ML, <1 s/protein, lebih akurat dari fpocket menurut penulisnya; lisensi MIT; butuh JRE minimal dibundel). Hasil: daftar kantong berperingkat + skor + residu → bola berwarna di viewport; klik → grid box otomatis ke kantong.
- **fpocket** sebagai cadangan/pembanding bila build Windows tersedia.
- Tombol "Cari kantong otomatis" di panel Grid. Untuk protein tanpa ligan kristal: cari kantong → docking terfokus (benchmark: dua tahap ini lebih baik dari blind docking langsung).

## A3. Kontrol kualitas pose — PoseBusters (Tahap 3, prioritas tinggi)
- `posebusters` (berbasis RDKit, jalan di Windows): cek panjang ikatan/sudut, bentrok sterik dengan protein, stereokimia, planaritas aromatik, energi internal.
- Kolom "QC" di tabel hasil (lulus / n masalah) + filter sembunyikan pose tidak valid. Alasan: RMSD saja tidak cukup menilai pose.

## A4. Rescoring & konsensus (Tahap 3)
- **Konsensus skor** (ringan, semua laptop): Vina + Vinardo + AD4 (+ AD-GPU) → normalisasi z-score/peringkat → peringkat rata-rata; tandai ligan yang konsisten di atas.
- **GNINA CNN rescoring** (Top1 redocking 58%→73% vs Vina menurut paper). Kendala: tak ada build Windows resmi → mode lanjutan via WSL bila tersedia, selain itu disembunyikan.
- **Boltz-2 / Boltzina** (afinitas AI, lisensi permisif): ~20 s/ligan, VRAM besar → hanya "Rescoring AI untuk 10–50 teratas" bila GPU NVIDIA ≥ 8 GB. Riset kelayakan dulu.
- DiffDock tidak dijadikan mesin utama: benchmark menunjukkan docking klasik dengan kantong diketahui masih lebih baik; deep learning lebih berguna untuk mencari kantong.

## A5. Interaksi & sidik jari interaksi (Tahap 3)
- **ProLIF** (Apache-2.0, baca PDBQT/SDF/MOL2): sidik jari interaksi per pose → **heatmap residu × ligan**, **kemiripan IFP dengan ligan asli** (Tanimoto) sebagai kolom tabel. Pertimbangkan sebagai mesin interaksi utama; kode buatan sendiri jadi cadangan.
- **PLIP** sebagai pembanding (termasuk *water bridge*) bila bisa dipasang di Windows.
- Jembatan air hanya jika air kristal dipertahankan (opsi preparasi reseptor).

## A6. Drug-likeness & ADMET (panel "Sifat Ligan")
- Langsung dari RDKit: Lipinski Ro5, Veber, Ghose, Egan, QED, PAINS & Brenk (FilterCatalog), SA score, Fsp3, stereocenter.
- **BOILED-Egg** (WLOGP vs TPSA): plot absorpsi usus & penetrasi otak ala SwissADME, offline.
- **ADMET-AI** (Chemprop, 41 dataset TDC, cepat untuk batch): kelarutan, hERG, toksisitas, CYP, BBB → komponen opsional saat instalasi ("Paket ADMET").
- Radar chart per ligan + kolom ringkas di tabel ("Lolos Ro5", "PAINS", "risiko hERG").

## A7. Statistik & grafik (tab "Statistik")
Grafik siap jurnal (PNG/SVG 300–600 dpi), palet konsisten, plus kalimat interpretasi otomatis dalam bahasa awam.
- Distribusi skor: histogram + KDE; garis untuk ligan acuan/obat pembanding.
- Konvergensi: ukuran klaster vs energi (bubble), heatmap RMSD antar pose, energi per run.
- **Korelasi eksperimen**: impor CSV IC50/Ki → scatter ΔG vs pIC50, Pearson r, Spearman ρ, Kendall τ, R², p-value, regresi + CI 95%.
- **Evaluasi screening** (label aktif/decoy, mis. DUD-E/DEKOIS): ROC + AUC, EF1%/EF5%, BEDROC, logAUC, kurva enrichment, bootstrap CI.
- Uji beda kelompok: Mann–Whitney / t-test / ANOVA + post-hoc + ukuran efek.
- Ruang kimia: PCA / t-SNE / UMAP dari fingerprint Morgan diwarnai skor; klaster scaffold Murcko.
- Metrik efisiensi: LE, LLE (pIC50 − LogP), BEI, SEI.

## A7b. Modul Grafik & Statistik kualitas publikasi (permintaan pengguna: "sangat bagus, sangat detail, seperti GraphPad Prism")
Ambil inspirasi alur kerja Prism (Data → Analisis → Grafik → Tata letak), **jangan** salin nama, ikon, atau branding-nya.

### Struktur (panel kiri "Navigator", seperti Prism)
- **Tabel Data**: lembar seperti spreadsheet dengan jenis tabel: *Kolom* (grup + replikat), *XY* (x + beberapa Y dengan replikat/SD/SEM), *Grup* (2 faktor), *Kontingensi*. Bisa diisi otomatis dari hasil docking (ΔG, LE, interaksi) atau tempel/impor CSV/Excel (IC50, % inhibisi, dll).
- **Hasil Analisis**: lembar hasil tiap uji (statistik uji, df, p, CI, ukuran efek, asumsi) — tertaut ke tabel data; ubah data → hasil & grafik ikut diperbarui.
- **Grafik**: tertaut ke data & analisis.
- **Tata Letak**: susun beberapa grafik + gambar 3D/2D menjadi satu figur panel (A, B, C…) ukuran jurnal.

### Jenis grafik
Dot/scatter per grup (mean ± SD/SEM/CI95, median ± IQR), bar + titik individu, box & whisker (Tukey / min–max / persentil), violin, before–after (berpasangan), XY garis/titik dengan error bar, regresi linear + pita CI/prediksi, **kurva dosis–respons (4PL/3PL, log x) dengan IC50/EC50 ± CI 95%**, ROC + AUC, kurva enrichment, histogram + KDE, heatmap (residu × ligan, korelasi), bubble (klaster vs energi), radar (ADMET), PCA/UMAP scatter, forest plot (ukuran efek).

### Kendali detail (panel "Format" saat elemen grafik diklik — klik sumbu, judul, titik, legenda langsung di grafik)
- **Sumbu**: rentang min/max/otomatis, skala linear/log10/log2/ln, tick mayor/minor (interval, jumlah, panjang, arah dalam/luar/silang, ketebalan), format angka (desimal, pemisah ribuan, notasi ilmiah, persen, koma desimal Indonesia/titik internasional), **potongan sumbu (axis break)**, sumbu kedua kanan, sumbu mulai dari nol/offset (gaya Prism: sumbu terpisah dari titik asal), ketebalan & warna garis sumbu.
- **Judul & label**: font (Arial/Helvetica/Times), ukuran, tebal/miring, superskrip/subskrip & huruf Yunani (ΔG, kcal·mol⁻¹, IC₅₀, µM) lewat editor teks kaya atau mathtext.
- **Titik & garis**: simbol (lingkaran, kotak, segitiga, berlian…), ukuran, isi/kosong, warna isi & tepi, transparansi, jitter/scatter otomatis untuk titik replikat, gaya garis.
- **Error bar**: SD/SEM/CI95/rentang, satu arah atau dua arah, lebar tutup, ketebalan.
- **Tanda signifikansi**: braket otomatis antar grup + format **ns / * / ** / *** / ****** (ambang dapat diatur, mis. 0.05/0.01/0.001/0.0001) atau p-value eksak (p = 0.012), posisi otomatis bertingkat agar tidak tumpang tindih.
- **Legenda**, garis acuan horizontal/vertikal (mis. ΔG ligan asli), anotasi teks/panah, area bayangan.
- **Warna**: palet ramah buta warna (Okabe–Ito, viridis), mode skala abu-abu untuk cetak, warna per grup tersimpan.
- **Ukuran figur jurnal**: preset 1 kolom (85 mm), 1,5 kolom (120 mm), 2 kolom (180 mm), atau kustom mm/inci; font minimal 6–8 pt dicek otomatis.
- **Tema/templat grafik**: simpan gaya ("Gaya Jurnal Saya") lalu terapkan ke semua grafik; salin format dari satu grafik ke grafik lain.
- **Ekspor**: PNG/TIFF (300/600/1200 dpi, LZW), SVG, PDF, EPS (vektor, font tertanam), salin ke clipboard (tempel ke Word/PowerPoint), latar transparan.

### Analisis statistik (pemilihan otomatis + bisa dipilih manual, semua asumsi dilaporkan)
- **Deskriptif**: n, mean, SD, SEM, median, IQR, min–max, CI95, CV%.
- **Uji asumsi**: normalitas Shapiro–Wilk, D'Agostino–Pearson, Kolmogorov–Smirnov; Q–Q plot; kesamaan varians Levene/Brown–Forsythe; deteksi pencilan (ROUT/Grubbs) dengan pilihan buang atau tandai.
- **Dua grup**: t-test tidak berpasangan (Student/Welch), berpasangan, Mann–Whitney, Wilcoxon.
- **Banyak grup**: ANOVA satu arah (biasa/Welch/Brown–Forsythe), ANOVA dua arah, repeated measures; Kruskal–Wallis, Friedman.
- **Post-hoc**: Tukey, Dunnett (vs kontrol, mis. vs obat standar), Šidák, Bonferroni, Holm, Games–Howell, Dunn; koreksi FDR (Benjamini–Hochberg) untuk banyak perbandingan.
- **Korelasi & regresi**: Pearson, Spearman, Kendall; regresi linear (slope, intercept, R², CI, uji residual), regresi nonlinear (4PL/3PL, eksponensial) dengan perbandingan model (extra sum-of-squares F test / AICc).
- **Kontingensi**: chi-square, Fisher exact.
- **Screening**: ROC/AUC (DeLong CI), EF, BEDROC, logAUC.
- **Ukuran efek**: Cohen's d, Hedges' g, η², r.
- Setiap hasil: tabel rapi + **paragraf interpretasi bahasa Indonesia** + paragraf siap tempel ke bagian Metode & Hasil naskah (mis. "Data dianalisis dengan ANOVA satu arah diikuti uji Dunnett…").
- Peringatan cerdas: n terlalu kecil, asumsi tidak terpenuhi → sarankan uji nonparametrik, perbandingan berganda tanpa koreksi.

### Teknologi
- Render: **matplotlib** (kualitas publikasi, vektor, mathtext) disematkan di Qt (`FigureCanvasQTAgg`) + lapisan interaksi sendiri (klik elemen → panel Format, drag label/braket). Dipertimbangkan **pyqtgraph** hanya untuk grafik besar interaktif (UMAP ribuan titik).
- Statistik: **SciPy** + **statsmodels** (ANOVA, post-hoc Tukey, regresi), **scikit-posthocs** (Dunn, dll.), **pingouin** bila kompatibel (Welch ANOVA, Games–Howell, ukuran efek); semua hasil divalidasi terhadap contoh referensi (nilai buku teks / keluaran R) dalam tes otomatis `tests/test_statistik.py`.
- Lembar data: `QTableView` + model sendiri (salin–tempel dari Excel, undo).
- Format proyek menyimpan data, analisis, dan gaya grafik → grafik bisa diedit ulang kapan saja.

### Kriteria selesai
- Figur dosis–respons dan bar + titik + braket signifikansi bisa dibuat dalam < 1 menit dari data contoh, hasil ekspor 600 dpi lolos syarat jurnal umum (font tertanam, ukuran kolom benar).
- Angka statistik sama dengan R/SciPy referensi sampai 4 desimal.
- Semua elemen grafik dapat diatur lewat klik langsung; gaya bisa disimpan & dipakai ulang.

## A8a. MD adaptif: aplikasi menilai kemampuan laptop & memberi saran (DISETUJUI pengguna)
Syarat pengguna: aplikasi **menyesuaikan sendiri** dan **menyarankan** apakah laptop sanggup MD.
- **Uji kecepatan otomatis** (10–20 detik) saat modul MD dibuka pertama kali dan setiap ganti perangkat: OpenMM jalankan sistem uji kecil (mis. 1HSG + ligan, pelarut implisit dan eksplisit) di platform terbaik yang ada (CUDA → OpenCL → CPU) → ukur ns/hari → simpan per perangkat (deteksi ulang otomatis saat pindah laptop, sama seperti GPU).
- **Tiga tingkat**, ditampilkan sebagai kartu dengan status Disarankan / Bisa (lama) / Tidak disarankan berdasarkan hasil uji:
  1. **Ringan** — minimisasi kompleks + MM/GBSA satu frame (menit; semua laptop).
  2. **Sedang** — MD 1–2 ns pelarut implisit (GB/OBC2) + RMSD ligan + MM/GBSA rata-rata (puluhan menit–jam; semua laptop).
  3. **Lengkap** — MD 10–100 ns air eksplisit + RMSD/RMSF, ikatan H per waktu (ProLIF), MM/GBSA banyak frame (butuh GPU; standar publikasi).
- **Perkiraan waktu** sebelum mulai, dari ukuran sistem (jumlah atom setelah solvasi) × kecepatan terukur: "Perkiraan selesai 3 j 20 mnt di CPU — disarankan tingkat Sedang."
- Aturan saran (awal, kalibrasi setelah benchmark nyata): perkiraan < 2 jam → Disarankan; 2–12 jam → Bisa (lama, jalankan malam hari); > 12 jam → Tidak disarankan + tawarkan tingkat lebih ringan atau ekspor.
- **Checkpoint** tiap ~5 menit → bisa dijeda/lanjut, aman bila laptop dimatikan; peringatan bila laptop pakai baterai (sarankan colok listrik) dan cek suhu/throttling tidak perlu.
- **Ekspor paket input** (OpenMM XML / GROMACS) untuk dijalankan di komputer lab/server bila laptop tidak sanggup; impor trajektori hasilnya kembali untuk dianalisis di VirmoDock.
- Perkiraan kasar (BELUM diukur, dari benchmark OpenMM umum; verifikasi di laptop pengguna): RTX 3060 laptop ratusan ns/hari, GPU terintegrasi puluhan ns/hari, CPU saja ~5–20 ns/hari untuk ~30–50 rb atom.

## A8. Penyempurnaan pasca-docking (Tahap 5, lanjutan)
- Minimisasi kompleks + **MM/GBSA** dengan OpenMM (Windows, GPU OpenCL/CUDA) untuk 10–20 teratas.
- **MD singkat** (1–10 ns, OpenMM + OpenFF) + RMSD/RMSF ligan, stabilitas ikatan H (ProLIF di trajektori). Riset dulu waktu komputasi di GPU laptop.
- Docking fleksibel (flexres dipilih di viewport), kovalen, makrosiklik (didukung Meeko).

## A9. Kemudahan (lintas tahap)
- Mode **Pemula / Ahli**; tooltip ilmiah + tautan panduan di setiap parameter.
- **Templat proyek**: docking 1 ligan, virtual screening, validasi redocking, perbandingan dengan obat standar.
- **Contoh data bawaan** (1HSG + 10 inhibitor HIV protease) untuk latihan offline.
- Command palette (Ctrl+K), undo untuk tampilan & grid box.
- **Reproducibility**: setiap job mencatat versi software, parameter, seed, perangkat → masuk laporan.
- Bahasa Indonesia/Inggris (`QTranslator`, semua teks lewat `self.tr()`).

## A10. Laporan publikasi
- PDF/Word (`python-docx`): paragraf Metode otomatis (versi, parameter, kriteria interaksi, sitasi), Tabel hasil, Gambar 3D + 2D + statistik, lampiran validasi & QC.
- Ekspor paket Supplementary: semua pose, CSV, parameter JSON.

## A11. Urutan prioritas (setelah Tahap 2 inti)
1. PoseBusters QC + drug-likeness RDKit + statistik dasar (histogram, korelasi) — murah, dampak besar.
2. ProLIF (heatmap + kemiripan IFP) + diagram 2D RDKit.
3. P2Rank + Asisten Alur.
4. ROC/EF/BEDROC + konsensus skor.
5. ADMET-AI (opsional).
6. Laporan publikasi + bahasa Inggris.
7. Tahap 5: OpenMM MM/GBSA & MD, flexres, kovalen; GNINA/Boltz-2 eksperimental.

## A12. Dependensi tambahan (minta izin unduh ke pengguna dulu)
`posebusters`, `prolif`, `admet-ai` (+ model), `openpyxl`, `python-docx`, `scikit-learn`, `umap-learn`, `matplotlib`, `openmm` (+ `openff-toolkit`), P2Rank + JRE minimal. Cek dukungan Python 3.14 tiap paket; bila tidak ada, pakai venv Python 3.12 khusus build.

## A13. Sumber
- GNINA: https://www.emergentmind.com/topics/gnina · https://doaj.org/article/0acbd65d6e0e448cb2dda39d3167906b
- PoseBusters: https://pubs.rsc.org/en/Content/ArticleLanding/2024/SC/D3SC04185A
- Benchmark 8 program docking gratis: https://public-pages-files-2025.frontiersin.org/journals/bioinformatics/articles/10.3389/fbinf.2025.1536504/text
- ProLIF: https://prolif.readthedocs.io/en/stable/notebooks/docking.html · https://pmc.ncbi.nlm.nih.gov/articles/PMC8466659
- PLIP: https://academic.oup.com/nar/article/49/W1/W530/6282136
- ADMET-AI: https://pmc.ncbi.nlm.nih.gov/articles/PMC11226862 · https://github.com/swansonk14/admet_ai
- P2Rank: https://jcheminf.biomedcentral.com/track/pdf/10.1186/s13321-018-0285-8
- Boltz-2: https://www.biorxiv.org/content/10.1101/2025.06.14.659707.full.pdf · Boltzina: https://arxiv.org/abs/2508.17555v1

---

# LAMPIRAN B — Prinsip "100% gratis" & fitur tambahan gratis

## B1. Aturan gratis (permintaan pengguna: "semua harus gratis, no bayar")
- VirmoDock **gratis untuk semua orang**, tanpa akun, tanpa langganan, tanpa iklan, tanpa telemetri; bekerja offline (internet hanya untuk unduh RCSB/PubChem/ChEMBL dll.).
- **Hanya** memakai komponen open-source / gratis. Sebelum menambah paket baru: cek lisensinya dan catat di `LISENSI_PIHAK_KETIGA.md` (dibuat di Tahap 4, ikut dibundel dan tampil di Help › Lisensi).
- Software berbayar (Discovery Studio, PyMOL Incentive, Schrödinger, MOE) **tidak pernah dibundel**; hanya tombol "Buka di…" bila pengguna sudah memasangnya sendiri. Utamakan alternatif gratis: PyMOL open-source, ChimeraX (gratis untuk akademik/nonkomersial — cek syaratnya), Discovery Studio Visualizer (freeware).
- Layanan web berbayar / perlu API key berbayar: dilarang.

## B2. Kepatuhan lisensi (WAJIB dicek sebelum rilis — ini catatan teknis, bukan nasihat hukum)
| Komponen | Lisensi (verifikasi ulang) | Cara pakai |
|---|---|---|
| PySide6 / Qt | LGPL-3 | pustaka dinamis (onedir, jangan link statis) |
| RDKit | BSD-3 | dalam proses |
| Meeko | LGPL-2.1 | dalam proses |
| gemmi | MPL-2.0 | dalam proses |
| Open Babel | GPL-2.0 | **lihat catatan di bawah** |
| AutoDock-GPU | GPL-2.0 (+ bagian LGPL) | program terpisah (subprocess) |
| AutoDock4/AutoGrid4 | GPL-2.0 | program terpisah |
| AutoDock Vina | Apache-2.0 | program terpisah |
| 3Dmol.js | BSD-3 | viewer |
| Ikon Lucide | ISC | aset |
| ProLIF / PoseBusters / P2Rank / ADMET-AI / OpenMM | Apache-2.0 / BSD-3 / MIT / MIT / MIT+LGPL | cek saat ditambahkan |

**Catatan penting:** Open Babel (GPL-2.0) saat ini di-*import* langsung di Python (`openbabel-wheel`). Menggabungkan GPL-2.0 dalam satu proses dengan pustaka Apache-2.0 (mis. ProLIF) berisiko tidak kompatibel. Solusi yang disarankan:
1. Panggil Open Babel sebagai **program terpisah** (`obabel.exe` lewat subprocess), bukan import — atau ganti fungsinya dengan RDKit/Meeko/gemmi bila bisa (protonasi pH: pertimbangkan Dimorphite-DL, Apache-2.0).
2. Rilis VirmoDock sebagai open-source **GPL-3.0-or-later** (kompatibel dengan Apache-2.0 & LGPL), kode sumber di GitHub, dan sertakan teks lisensi semua komponen. Program GPL-2.0 yang dipanggil sebagai proses terpisah dianggap agregasi.
3. `libomp` dari Visual Studio tidak boleh dibundel (sudah diganti `vcomp140.dll`, redistributable resmi).
4. Data latih model (ADMET-AI/TDC) dan basis data (ChEMBL CC-BY-SA, COCONUT CC0/CC-BY, ZINC) punya syarat atribusi masing-masing → tampilkan atribusi di laporan/ekspor.

## B3. Distribusi & pemeliharaan tanpa biaya
- **GitHub** (repo publik): kode sumber, Releases (installer & portable), Issues (laporan bug), Discussions (forum pengguna), **GitHub Pages** (situs dokumentasi).
- **GitHub Actions** (gratis untuk repo publik, ada runner Windows): build otomatis installer + jalankan tes setiap rilis.
- **Pemeriksaan pembaruan** di dalam aplikasi: baca rilis terbaru dari GitHub API (tanpa server sendiri); pengguna memilih kapan memperbarui.
- **Tanda tangan kode** (agar Windows SmartScreen tidak memperingatkan): sertifikat komersial berbayar → hindari; cek program gratis untuk proyek open-source (mis. SignPath Foundation) — verifikasi syaratnya.
- **DOI gratis** via Zenodo (terhubung ke GitHub Releases) → pengguna bisa mengutip VirmoDock di naskah.
- **Publikasi software gratis**: Journal of Open Source Software (JOSS) tidak memungut biaya — target setelah Tahap 4 + benchmark (B5).

## B4. Fitur tambahan, semuanya gratis (urut dari dampak terbesar)
1. **PDBFixer** (OpenMM, MIT): lengkapi atom/residu/loop yang hilang, ganti residu nonstandar, tambah H pada pH tertentu → memenuhi syarat "perbaiki atom hilang" di preparasi reseptor.
2. **PROPKA + PDB2PQR** (LGPL/BSD): keadaan protonasi residu (His, Asp, Glu, Lys) sesuai pH → reseptor lebih akurat dari sekadar "tambah H polar".
3. **Pencarian protein**: cari RCSB berdasarkan nama protein/organisme/ligan (Search API gratis), daftar struktur dengan resolusi, metode, ligan → pilih yang terbaik (saran otomatis: resolusi terkecil + ada ligan kristal).
4. **AlphaFold DB** (gratis, via ID UniProt) untuk protein tanpa struktur kristal + tampilkan skor pLDDT (warna kepercayaan) dan peringatan bila kantong di daerah pLDDT rendah.
5. **ChEMBL** (gratis): ambil senyawa aktif yang sudah diketahui untuk target + nilai IC50/Ki → otomatis jadi **set validasi** (aktif vs decoy) dan data **korelasi** untuk modul statistik.
6. **Pustaka bahan alam** untuk peneliti tanaman obat: **COCONUT** (bahan alam terbuka), ekspor subset per spesies/famili; juga KNApSAcK (cek syarat penggunaan). Penapisan ligan bahan alam langsung dari nama tanaman.
7. **Penggambar molekul** di dalam aplikasi: **Ketcher** (Apache-2.0, berbasis web → disematkan di QWebEngine) untuk menggambar/mengedit ligan, langsung jadi 3D.
8. **Pustaka screening gratis**: subset ZINC (in-stock / drug-like), obat FDA (repurposing) — unduh terkelola dengan filter drug-likeness.
9. **Kemiripan & farmakofor**: pencarian kemiripan (Tanimoto Morgan) dari ligan terbaik, farmakofor dari pose terbaik (fitur RDKit) untuk menyaring pustaka sebelum docking.
10. **Konservasi residu** (opsional): BLAST NCBI / UniProt → tandai residu kantong yang terkonservasi.
11. **Mode "Repurposing obat"**: templat yang men-dock semua obat FDA ke target lalu memberi peringkat + data ChEMBL pembanding.
12. **Contoh & tutorial interaktif** di dalam aplikasi (data bawaan, panduan langkah per langkah yang menyorot tombol).
13. **Lapor bug dari aplikasi**: tombol yang menyiapkan log + info sistem → pengguna yang memutuskan mengirim ke GitHub Issues (tidak otomatis).

## B5. Bukti mutu (supaya dipercaya peneliti & reviewer)
- **Benchmark terbuka** dijalankan otomatis dan hasilnya dipublikasikan di dokumentasi:
  - Akurasi pose: redocking pada set publik (mis. PDBbind core/CASF-2016 atau Astex Diverse Set — cek syarat unduh), metrik: % RMSD ≤ 2 Å.
  - Screening: DUD-E/DEKOIS/LIT-PCBA subset → AUC, EF1%.
  - Bandingkan AD-GPU vs Vina vs konsensus di dalam VirmoDock.
- **Tes otomatis** (`tests/`): impor format, preparasi, parser hasil, statistik (vs nilai referensi R/SciPy), interaksi (vs PLIP/ProLIF pada kompleks contoh).
- **Reproducibility**: hasil sama untuk seed sama; laporan mencatat versi semua komponen.

## B6. Urutan masuk ke tahap
- Tahap 2: B4-1 PDBFixer, B4-2 PROPKA (bagian preparasi reseptor), B4-3 pencarian RCSB.
- Tahap 3: B4-5 ChEMBL (validasi & korelasi), B4-7 Ketcher, B4-9 kemiripan.
- Tahap 4: B1–B3 (lisensi, GitHub, Actions, Zenodo), B5 benchmark & tes.
- Tahap 5: B4-4 AlphaFold, B4-6 bahan alam, B4-8/11 pustaka & repurposing, B4-10 konservasi.

---

# LAMPIRAN C — Pusat Ekspor & keluaran docking (permintaan pengguna: "sangat sangat baik", gambar beragam format & DPI)

## C1. Pusat Ekspor (satu dialog untuk semua ekspor)
- Menu **File › Ekspor… (Ctrl+E)** + tombol ekspor di setiap panel/grafik membuka dialog yang sama, tab sesuai konteks.
- Kiri: kategori (Gambar 3D, Diagram 2D, Grafik, Struktur molekul, Tabel, Laporan, Paket lengkap, Animasi). Tengah: opsi. Kanan: **pratinjau langsung** + perkiraan ukuran berkas & dimensi akhir.
- **Preset** tersimpan ("Jurnal 1 kolom 600 dpi TIFF", "Slide PowerPoint", "Poster A0", "Web"), ingat pilihan terakhir.
- **Ekspor batch**: banyak ligan/pose/grafik sekaligus dengan pengaturan sama; **pola nama berkas** `{proyek}_{ligan}_{pose}_{energi}_{tanggal}` dapat diubah; pilihan timpa / beri nomor / lewati.
- Semua ekspor berjalan di latar (tidak membekukan UI) + progres di panel Antrean.

## C2. Gambar (3D, 2D, grafik)
- **Format**: PNG, TIFF (tanpa kompresi / LZW / ZIP; 8/16-bit; RGB atau CMYK untuk cetak), JPEG (kualitas 60–100), WebP, BMP; **vektor**: SVG, PDF, EPS (untuk diagram 2D, grafik, tata letak figur; font tertanam/dikonversi ke path).
- **Resolusi**: 72 / 150 / 300 / 600 / 1200 dpi / kustom; ukuran dalam **px, mm, cm, inci** (dpi × ukuran fisik → piksel otomatis); kunci rasio; preset jurnal (85/120/180 mm), slide 16:9 (1920×1080, 3840×2160), poster (A3/A2/A1/A0), persegi media sosial.
- Metadata DPI ditulis benar di berkas (PNG pHYs, TIFF XResolution) supaya Word/jurnal membaca ukuran fisik dengan tepat; metadata teks opsional (proyek, ligan, energi, versi VirmoDock).
- **Latar**: putih, hitam, warna bebas, atau **transparan** (PNG/TIFF/WebP/SVG).
- **Gambar 3D resolusi sangat tinggi**: render offscreen pada kanvas besar dengan **tile rendering** (gabungkan petak) agar bisa melewati batas tekstur GPU (target ≥ 8000 px), **supersampling 2–4×** untuk tepi halus, label/garis interaksi diskalakan proporsional (tidak mengecil di resolusi besar), kamera dikunci sama untuk semua ligan batch (perbandingan adil).
- Opsi kualitas 3D: anti-aliasing, outline/siluet, ambient occlusion & bayangan bila didukung renderer; ekspor ke skrip PyMOL/ChimeraX untuk ray-tracing di software gratis tersebut (C3).
- **Pemeriksa publikasi** sebelum simpan: peringatan bila < 300 dpi untuk jurnal, font < 6 pt pada ukuran fisik akhir, atau warna tidak ramah buta warna.
- **Salin ke clipboard** (gambar & vektor EMF/SVG) untuk tempel langsung ke Word/PowerPoint.
- **Tata letak figur** (komposer): gabungkan 3D + diagram 2D + grafik jadi satu figur panel dengan label A/B/C, perataan & jarak otomatis, ukuran jurnal, ekspor vektor/raster.

## C3. Struktur molekul & hasil docking
- **Kompleks** reseptor + pose: PDB (rantai ligan terpisah, HETATM, CONECT, REMARK berisi energi/mesin/parameter), **mmCIF**, PDBQT.
- **Pose**: SDF dengan **tag properti** (ΔG, Ki, LE, klaster, RMSD, QC PoseBusters, jumlah interaksi, SMILES) — langsung terbaca di DataWarrior/KNIME/Excel; MOL2; PDBQT; satu berkas multi-pose atau satu berkas per pose; pose terbaik saja / top-N / semua.
- **Sesi untuk software lain**: skrip PyMOL `.pml` dan ChimeraX `.cxc` yang memuat berkas + mengulang gaya/warna/label/interaksi persis seperti di VirmoDock; berkas kompatibel Discovery Studio Visualizer (PDB + SDF).
- **Input untuk reproduksi**: `reseptor.pdbqt`, ligan PDBQT, GPF/DPF, `config.txt` Vina, peta grid (opsional, besar) → bisa dijalankan ulang di luar VirmoDock.
- **Interaksi**: CSV/JSON per pose (jenis, residu, atom, jarak, sudut), serta sidik jari interaksi (ProLIF) sebagai matriks.

## C4. Tabel & data
- **CSV** dengan pilihan pemisah (`,` / `;` / tab) dan **desimal koma** (Excel berbahasa Indonesia) atau titik; UTF-8 BOM agar Excel membaca karakter khusus (Δ, µ, Å).
- **Excel .xlsx** terformat (openpyxl): lembar Ringkasan, Semua pose, Interaksi, Sifat ligan/ADMET, Statistik, Parameter, Info software & perangkat; header beku, filter otomatis, format angka (2–3 desimal), pewarnaan bersyarat (skala warna energi), lebar kolom otomatis.
- **Word .docx** & **LaTeX**: tabel siap naskah (Tabel 1 hasil docking, Tabel interaksi) dengan gaya jurnal; **salin sebagai tabel** ke clipboard.
- JSON lengkap (untuk analisis lanjutan di Python/R).

## C5. Laporan
- **PDF** dan **Word (.docx, dapat diedit)**: sampul (judul, penulis, institusi, logo — diisi pengguna), Metode otomatis, tabel, gambar 3D + 2D, statistik, validasi, QC, lampiran parameter & versi.
- **Laporan HTML interaktif** satu berkas (offline, 3Dmol.js tertanam): penerima bisa memutar molekul & membuka tiap ligan di browser tanpa memasang apa pun — cocok dikirim ke pembimbing/kolaborator.
- Templat laporan dapat dipilih/diubah (bahasa Indonesia/Inggris).

## C6. Paket lengkap & animasi
- **Paket Supplementary** (.zip): struktur folder rapi + `README.txt` otomatis (isi tiap folder, cara membuka), semua pose, tabel, gambar, parameter, daftar versi software, **checksum SHA-256** untuk integritas.
- **Arsip proyek** (.vmd) untuk dipindah ke laptop lain / dibagikan.
- **Animasi**: putar 360°, transisi antar pose, (Tahap 5) trajektori MD → **MP4 / WebM / GIF**, resolusi hingga 4K, fps 24/30/60, durasi & arah putar diatur; bingkai PNG berurutan sebagai alternatif. Encoder: ffmpeg build LGPL (gratis) dibundel atau `imageio-ffmpeg` (cek lisensi build).

## C7. Keluaran docking yang rapi (otomatis setiap job)
```
hasil/<tanggal>_<nama_job>/
  README.txt                ← ringkasan job: mesin, perangkat, parameter, seed, versi, durasi
  ringkasan.csv / .xlsx     ← peringkat semua ligan
  pose/<ligan>/             ← pose_1..n.sdf/.pdbqt, kompleks_terbaik.pdb, log mesin asli (.dlg / vina log)
  interaksi/                ← CSV per ligan + heatmap
  gambar/                   ← (opsional) gambar 3D & 2D otomatis top-N dengan preset terakhir
  qc/                       ← laporan PoseBusters
  parameter.json            ← salinan beku semua pengaturan (untuk reproduksi)
```
- Nama ligan aman untuk berkas, tidak ada yang tertimpa antar job.
- Log asli mesin selalu disimpan apa adanya (untuk reviewer yang meminta).

## C8. Kriteria selesai
- Gambar 3D 600 dpi ukuran 180 mm (≈ 4252 px) dan 1200 dpi tersimpan dengan DPI benar, label tetap terbaca, latar transparan berfungsi.
- Diagram 2D & grafik terbuka sebagai vektor yang dapat diedit di Inkscape/Illustrator/Word.
- SDF hasil terbaca dengan tag properti di DataWarrior/KNIME; skrip PyMOL/ChimeraX mereproduksi tampilan.
- CSV terbuka benar di Excel berbahasa Indonesia; XLSX rapi tanpa penyesuaian manual.
- Laporan HTML interaktif terbuka offline di browser biasa.

---

# LAMPIRAN D — Fitur terinspirasi software profesional (SAMSON, ChimeraX, MOE, Maestro, SeeSAR, Nanome)
Ambil **ide alur kerjanya saja** (gratis, dibuat sendiri), tanpa menyalin nama, desain, atau kode. Sumber: Wikipedia & blog OneAngstrom (SAMSON), ulasan Nanome (vendor, anggap promosi), ChimeraX. Fitur SeeSAR ditulis dari ingatan — **verifikasi** sebelum dijadikan acuan.

## D1. Dari SAMSON (OneAngstrom): platform modular
- **Sistem ekstensi/plugin**: folder `plugins/` + API Python sederhana (`virmodock.api`) untuk menambah mesin docking, jenis analisis, atau format ekspor tanpa mengubah inti. Pengelola ekstensi di menu Tools (aktif/nonaktif, versi).
- **Konsol & skrip Python** di dalam aplikasi (dock "Konsol"): otomatisasi alur (mis. loop 500 ligan dengan filter khusus), rekam aksi UI menjadi skrip (macro recorder) agar bisa diulang.
- **Asisten**: SAMSON memakai asisten AI berbasis LLM. Versi VirmoDock yang gratis & offline: asisten berbasis aturan + pencarian di dokumentasi lokal ("Kenapa energi saya positif?", "Kotak terlalu besar?"); opsi lanjutan terhubung ke LLM lokal gratis (mis. lewat Ollama) bila pengguna memasangnya sendiri — tidak dibundel, tidak wajib.
- **Pembangun & animasi molekul**: editor in-situ (tambah/hapus atom, ubah gugus) + animasi presentasi (lihat C6).

## D2. Dari ChimeraX: kualitas grafis & baris perintah
- **Pencahayaan ambient occlusion & bayangan lembut**, siluet/outline untuk gambar publikasi (cek kemampuan 3Dmol; bila kurang, pertimbangkan Mol* atau renderer WebGL2 sendiri untuk mode "Gambar Publikasi").
- **Baris perintah** di bawah viewport dengan perintah singkat gaya PyMOL/ChimeraX (`show sticks chain A`, `color hydrophobicity`, `select resi 45-60`, `zoom ligand`) + autocomplete — kekuatan bagi pengguna mahir, setara klik bagi pemula.
- Kinerja untuk struktur besar (ribuan residu, kompleks multi-rantai, mode level-of-detail).
- Integrasi prediksi struktur (AlphaFold DB, lihat B4-4).

## D3. Dari MOE / Maestro: preparasi & kimia medisinal
- **Wizard Preparasi Protein** satu layar: masalah struktur terdeteksi (atom hilang, altloc, residu nonstandar, bentrok, tutup ujung rantai) dalam daftar dengan tombol "Perbaiki semua"/per item; **optimasi jaringan ikatan hidrogen** (orientasi Asn/Gln/His, rotasi OH/SH) + protonasi pH (PROPKA, B4-2); minimisasi terbatas.
- **Ligand Interaction Diagram** kualitas tinggi (A5/3.3) dengan permukaan paparan pelarut ligan dan sel residu berwarna.
- **Lembar kerja proyek (project table)**: semua ligan + properti + skor + gambar 2D kecil dalam satu tabel yang bisa difilter, diwarnai, dan diurutkan, pusat seluruh analisis (seperti spreadsheet kimia).
- Alat **medchem**: penggantian gugus/bioisostere sederhana, enumerasi R-group dari scaffold → docking batch otomatis.

## D4. Dari SeeSAR (verifikasi): visual kontribusi per atom
- **Pewarnaan kontribusi per atom**: tiap atom ligan diberi halo hijau (menguntungkan) / merah (merugikan) dari suku energi per atom (Vina `--score_only` per-atom / AD4 per-atom di .dlg) → langsung terlihat bagian molekul mana yang perlu diubah.
- **Edit ligan di dalam kantong + skor ulang cepat**: ubah gugus di pose (mis. ganti -OH jadi -NH₂), minimisasi lokal (Vina `--local_only`), energi diperbarui dalam hitungan detik.
- Indikator kualitas pose: bentrok sterik, torsi tidak wajar, ikatan H tak terpenuhi (digabung dengan PoseBusters, A3).

## D5. Dari Nanome: kolaborasi
- Berbagi sesi lewat berkas proyek/laporan HTML interaktif (C5) — gratis, tanpa server.
- Tampilan "Presentasi": layar penuh, langkah adegan tersimpan (kamera + gaya) yang bisa diputar berurutan saat seminar/ujian.

## D6. Prioritas Lampiran D
1. Lembar kerja proyek (D3) — inti pengalaman pengguna, masuk Tahap 3.
2. Wizard preparasi protein + optimasi ikatan H (D3) — Tahap 2.
3. Pewarnaan kontribusi per atom (D4) — Tahap 3.
4. Baris perintah + konsol Python (D1/D2) — Tahap 3–4.
5. Ambient occlusion / mode gambar publikasi (D2) — Tahap 3 (bersama C2).
6. Edit ligan dalam kantong + skor ulang, plugin/API, asisten offline, presentasi — Tahap 5.

## D7. Sumber
- SAMSON: https://en.wikipedia.org/wiki/SAMSON · https://blog.samson-connect.net/transforming-molecular-design-oneangstrom-integrates-nvidia-bionemo-into-samson · https://www.samson-connect.net/extensions/0a53a840-a147-12f8-29b1-b074a4041978
- Perbandingan perangkat lunak (vendor Nanome): https://nanome.ai/blog/software-for-molecular-docking-visualization · https://nanome.ai/blog/the-best-molecular-visualization-tools
- ChimeraX: https://pmc.ncbi.nlm.nih.gov/articles/pmid/32881101

---

# LAMPIRAN E — Fondasi mutu, MVP v1.0, dan peta versi (RENCANA DITUTUP di sini)
Disepakati pengguna (8 Okt 2026): tidak menambah fitur baru lagi; mulai membangun. Ide baru berikutnya dicatat di `IDE_BARU.md`, bukan di dokumen ini, dan baru dikerjakan setelah v1.0 rilis.

## E1. Keamanan data
- Simpan otomatis proyek setiap 2–5 menit + setelah setiap aksi besar (preparasi selesai, job selesai) ke berkas sementara, lalu tukar atomik (tulis `proyek.json.tmp` → ganti) agar tidak rusak bila listrik mati.
- **Pemulihan crash**: saat dibuka, jika ada sesi yang tidak ditutup normal → dialog "Pulihkan pekerjaan terakhir?".
- Job docking terputus otomatis berstatus "dijeda" dan bisa dilanjutkan (2.7).
- Cadangan otomatis 5 versi terakhir `proyek.json` di `proyek/.cadangan/`.
- Log galat ke `%LOCALAPPDATA%\VirmoDock\log\` (rotasi 10 berkas) untuk dilampirkan saat lapor bug.

## E2. Laptop spek rendah
- Target minimum: Windows 10 64-bit, RAM 4 GB, tanpa GPU, layar 1366×768.
- **Mode hemat** (otomatis bila RAM < 8 GB atau tanpa GPU, bisa diubah): kualitas kartun lebih rendah, permukaan dihitung hanya di sekitar kantong, animasi/putar otomatis mati, jumlah pekerja paralel dibatasi.
- Protein besar (> 20 rb atom): peringatan + tampilkan hanya rantai terpilih/kantong; batas memori untuk tabel hasil (paging).
- Tata letak layar kecil: panel bisa ditumpuk sebagai tab, toolbar bisa diciutkan ke ikon saja.
- Uji kinerja: waktu buka aplikasi < 5 s (SSD) / < 10 s (HDD), putar molekul ≥ 30 fps untuk protein 5 rb atom pada grafis terintegrasi.

## E3. MVP v1.0 (inti yang wajib ada sebelum rilis pertama)
1. Impor (berkas, RCSB, PubChem, SMILES) + viewer 3D + gaya tampilan (sudah).
2. Preparasi reseptor (gemmi + Meeko + PDBFixer/PROPKA bila sempat) dan ligan batch.
3. Grid box: otomatis dari ligan asli + angka + pusat ke residu (drag mouse boleh menyusul v1.1).
4. Docking AutoDock-GPU (OpenCL) + Vina, fallback CPU otomatis, antrean job (jeda/lanjut/batal), notifikasi.
5. Validasi redocking + RMSD.
6. Tabel hasil + lembar kerja proyek dasar + interaksi 3D + diagram 2D.
7. Ekspor: gambar PNG/TIFF/SVG dengan DPI pilihan, kompleks PDB, SDF bertag, CSV/XLSX, laporan PDF sederhana.
8. Simpan/buka proyek, simpan otomatis, pemulihan crash.
9. Installer + portable, deteksi GPU otomatis, first-run wizard, panduan dasar Bahasa Indonesia.
10. Lisensi pihak ketiga & atribusi lengkap (B2).

## E4. Peta versi
| Versi | Isi |
|---|---|
| **v1.0** | MVP (E3) |
| v1.1 | Grid box drag mouse, PoseBusters QC, drug-likeness RDKit + BOILED-Egg, statistik dasar (histogram, korelasi, LE), ekspor Excel penuh — **SELESAI 8 Okt 2026**, dikerjakan sebelum rilis 1.0 atas permintaan pengguna (rincian CATATAN_TAHAP2.md §4e) |
| v1.2 | Modul grafik & statistik ala Prism (A7b) bertahap, ProLIF heatmap + kemiripan IFP, pewarnaan kontribusi per atom — **SELESAI (0.9.0–0.9.2)** |
| v1.3 | P2Rank deteksi kantong, Asisten Alur, wizard preparasi protein penuh + optimasi ikatan H, ChEMBL validasi & korelasi — **SELESAI (0.9.0–0.9.2)** |
| v1.4 | Konsensus skor + ROC/EF/BEDROC, laporan Word & HTML interaktif, komposer figur, animasi |
| v1.5 | ADMET-AI (paket opsional), Ketcher, kemiripan/farmakofor, pustaka ZINC/obat FDA/COCONUT, bahasa Inggris — **SELESAI 9 Okt 2026 (0.9.2)**; ZINC hanya tautan situs (anti-bot) |
| v2.0 | MD adaptif + MM/GBSA (OpenMM, A8a), flexres/kovalen, plugin & konsol Python, baris perintah, AlphaFold DB — **flexres, baris perintah (VirmoDock-cli), AlphaFold DB SELESAI 9 Okt 2026 (0.9.3)**; sisa: MD/MM-GBSA, kovalen, plugin/konsol |
| v2.x | Eksperimental: GNINA (WSL), Boltz-2, edit ligan dalam kantong, asisten LLM lokal |

## E5. Uji di banyak laptop (sebelum setiap rilis)
- Minimal 3–5 penguji relawan dengan perangkat berbeda: Intel iGPU, AMD (CPU/GPU), NVIDIA, tanpa GPU; Windows 10 & 11; DPI 100–150%.
- Daftar uji (`docs/DAFTAR_UJI.md`): pasang dari installer → wizard → impor 1HSG → preparasi → 10 ligan → docking → hasil → ekspor gambar 600 dpi & Excel → tutup/buka proyek → copot pemasangan. Catat waktu & masalah.
- Uji otomatis di GitHub Actions (Windows) untuk logika non-GUI setiap commit.

## E6. Masukan pengguna
- Menu Help › Kirim saran / Lapor masalah: menyusun teks + info sistem + log (pengguna melihat & menyetujui isinya) → membuka GitHub Issues atau email; tidak ada pengiriman otomatis.
- `CHANGELOG.md` + dialog "Apa yang baru" setelah pembaruan.

## E7. Etika ilmiah
- Pengingat di tabel hasil & laporan: "Hasil docking adalah prediksi komputasi, bukan bukti aktivitas biologis; konfirmasi dengan uji eksperimen."
- Ki dari ΔG diberi label "perkiraan".
- Sitasi otomatis semua mesin & pustaka yang dipakai (AutoDock-GPU, Vina, Meeko, RDKit, Open Babel, dll.) di laporan dan di Help › Cara mengutip, termasuk sitasi VirmoDock (DOI Zenodo, B3).
- Peringatan bila validasi redocking belum dilakukan atau gagal (RMSD > 2 Å) saat membuat laporan.

## E8. Status rencana
**Rencana selesai.** Langkah berikutnya: sesi baru → baca `CATATAN_TAHAP2.md` + dokumen ini → kerjakan Tahap 2 dengan fokus MVP v1.0 (E3).
