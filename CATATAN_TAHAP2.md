# VirmoDock — Catatan Serah-Terima (per 8 Okt 2026)

Untuk sesi baru: baca seluruh file ini dulu. Pengguna berbahasa Indonesia; UI dan pesan aplikasi berbahasa Indonesia.
(Nama file historis — isinya mencakup semua tahap. Jangan diganti namanya: dirujuk dari `CLAUDE.md`.)

**Status singkat:** Tahap 1–4 (MVP v1.0, Lampiran E3) **selesai** + **v1.1 selesai** (§4e) + UI/UX & menu dirombak (§4f) + Kelompok A, Dimorphite, P2Rank (§4g) + **sisa fitur v1.x selesai** (§4h: Format grafik, patah sumbu, ROC, kontingensi, komposer figur, gaya tersimpan, laporan Word/HTML interaktif, animasi). Versi kode 0.9.0 (pra-rilis).
Versi kode 0.9.2 (§4j: v1.2–v1.5 E4 selesai — ProLIF heatmap, ChEMBL, wizard protein + PROPKA/PDB2PQR, ADMET-AI, Ketcher, kemiripan/farmakofor, pustaka ligan, bahasa Inggris). Berikutnya: v2.0 E4 atau §5 (relawan, GitHub, SignPath). Build 0.9.2 BELUM dibuat.

## 1. Tujuan proyek (ringkasan permintaan pengguna)
Aplikasi desktop Windows **VirmoDock** (.exe + installer + versi portable) untuk molecular docking, pengganti AutoDockTools.
- Tata letak profesional ala BIOVIA Discovery Studio: menu bar, toolbar padat, pohon hierarki kiri, viewport 3D tengah, properti/parameter kanan, log/antrean bawah. Semua panel dockable, resize, tersimpan.
- **Anti "AI slop"**: tanpa glow/glassmorphism/emoji/kartu bulat besar/tagline. Palet netral + **satu aksen biru** (menu bar boleh gradien biru navy halus). Ikon garis seragam (Lucide). Sudut 2–4 px. Angka monospace/tabular. Mode gelap & terang.
- Gaya tampilan & pewarnaan **ala PyMOL** (surface, mesh, warna per elemen/rantai/dll) — sudah ada dasarnya.
- **Harus bisa dipasang di semua laptop**, GPU terdeteksi & menyesuaikan otomatis; tanpa GPU → CPU (Vina) dengan pemberitahuan; panduan driver di dalam aplikasi.
- Semua kerja di dalam aplikasi ("jangan ke mana-mana"), tapi ada tombol "Buka di…" PyMOL/ChimeraX/Discovery Studio Visualizer.
- UI tidak boleh freeze; minimize tetap jalan + notifikasi Windows; DPI 100–200%, multi-monitor; jendela ingat ukuran/posisi/layout.
- Dokumentasi Bahasa Indonesia (instalasi, pindah laptop, setup GPU, troubleshooting, panduan pengguna).
- Mockup sudah DISETUJUI pengguna: `E:\Bikin Docking Simpel\mockup\mockup_terang.png`, `mockup_gelap.png`, `mockup.html`.

## 2. Keputusan teknis (sudah disetujui)
- UI: **PySide6 6.11.2** (Qt, native) + viewport **3Dmol.js** di `QWebEngineView` (QWebChannel untuk event).
- Kimia: **RDKit 2026.03**, **Meeko 0.8.0**, **openbabel-wheel 3.1.1**, **gemmi 0.7.5**.
- Mesin docking (dibundel di `vendor\bin`):
  - `autodock_gpu.exe` — **build sendiri, OpenCL, native Windows** (tanpa WSL). Teruji di RTX 3060: Casticin/1ITB −7.20 kcal/mol (CUDA-WSL −7.19), 1.6 s/50 run. Butuh `OpenCL.dll` (Khronos ICD loader, dibundel) + `vcomp140.dll` (redistributable resmi, dibundel).
  - `vina.exe` 1.2.7 (resmi, Windows), `autogrid4.exe`, `autodock4.exe` (dari instalasi ADT lama pengguna, build 2014 — belum dicek dependensi DLL-nya).
  - `clinfo.exe` (Khronos SDK) untuk deteksi OpenCL.
- Preparasi reseptor: **gemmi bersihkan PDB → Meeko `mk_prepare_receptor --read_pdb X -o Y -p -a`** (cadangan: Open Babel `-xr`). MGLTools TIDAK dibundel (Python 2).
- Packaging: PyInstaller onedir; installer: **Inno Setup 6.7.3** (terpasang di `vendor/innosetup`, lihat §4d).
- Pengguna sudah mengizinkan unduhan: PySide6, rdkit, meeko, openbabel-wheel, nuitka/pyinstaller, Vina, OpenCL SDK, Inno Setup, openpyxl, teks lisensi resmi, posebusters (+ pandas, PyYAML). Paket lain: minta izin dulu.

## 3. Struktur folder
```
E:\Bikin Docking Simpel\
  DockingSimpel.exe, app\        ← aplikasi LAMA (web UI + WSL). Masih jalan, bug GPU sudah diperbaiki.
  mockup\                        ← mockup yang disetujui
  VirmoDock\
    .venv\                       ← Python 3.14 venv (semua dependensi)
    Jalankan VirmoDock (dev).bat ← jalankan versi pengembangan
    VirmoDock.pyw                ← titik masuk PyInstaller
    LICENSE, LISENSI_PIHAK_KETIGA.txt, licenses\, README.md, requirements.txt
    virmodock\
      app.py, __main__.py        ← titik masuk (python -m virmodock); argumen --uji-mandiri, --qc-pekerja, --disable-gpu
      aset\                      ← ikon aplikasi
      core\  (tanpa GUI kecuali antrean.py yang memakai QProcess)
        paths.py                 ← lokasi bin/viewer/appdata, mode portable, paths.settings()
        env.py                   ← deteksi GPU (WMI + nvidia-smi + clinfo), CPU/RAM, PyMOL/ChimeraX/DSV, panduan driver
        molekul.py               ← Objek, impor PDB/PDBQT/CIF/SDF/MOL2/SMILES, RCSB, PubChem, gaya_bawaan, spek_viewer
        obabel.py                ← Open Babel sebagai program terpisah
        proyek.py                ← model proyek .vmd (simpan atomik, cadangan)
        prep_reseptor.py, prep_ligan.py  ← preparasi (gemmi, Meeko, RDKit)
        mesin.py                 ← GPF/DPF, perintah AD-GPU/Vina/AD4, parser hasil
        antrean.py               ← Pelaksana (QProcess per ligan, jeda/lanjut, QC otomatis)
        analisis.py              ← pose_mol, interaksi, RMSD simetri, ringkasan per ligan, analisis_ulang
        diagram2d.py             ← diagram interaksi 2D (SVG)
        ekspor.py, laporan.py    ← CSV/XLSX/PDB/SDF/gambar, laporan PDF
        sifat.py                 ← drug-likeness, PAINS/Brenk, BOILED-Egg (v1.1)
        statistik.py, grafik.py  ← statistik + grafik SVG umum (v1.1)
        qc.py                    ← PoseBusters + proses pekerja (v1.1)
        catat.py, pindah.py, ujimandiri.py  ← log berkas, pindah laptop, uji mandiri
      ui\
        mainwindow.py            ← JendelaUtama: menu, toolbar, dock, tab tengah, semua aksi
        theme.py, icons.py, logo.py, kerja.py (QThreadPool), viewer_widget.py (QWebEngineView + QWebChannel)
        panels.py                ← Hierarki (dock "Objek"), Properti, Tampilan (ala PyMOL), Log
        panel_alur.py            ← DaftarLangkah + PanelLangkah (alur 5 langkah, §4f)
        panel_docking.py, panel_antrean.py, panel_hasil.py, panel_interaksi.py (+ TabDiagram)
        tab_banding.py, tab_sifat.py, tab_statistik.py   ← tab tengah
        dialogs.py (Ambil, Wizard), dialog_reseptor.py, dialog_ligan.py, dialog_ekspor.py, dialog_bantuan.py
      viewer\viewer.html, viewer.js, 3Dmol-min.js  ← API JS "VM.*"
    vendor\bin\                  ← autodock_gpu.exe, vina.exe, autogrid4.exe, autodock4.exe, clinfo.exe, OpenCL.dll, vcomp140.dll, openbabel\
    vendor\adgpu_src\            ← source AutoDock-GPU + vcxproj yang sudah dimodifikasi
    vendor\opencl\, vendor\innosetup\  ← Khronos OpenCL SDK, Inno Setup (tidak ikut git)
    docs\                        ← dokumentasi HTML (sumber docs\_sumber\*.html) + Tutorial PDF
    branding\                    ← logo resmi
    build_tools\                 ← virmodock.spec, rilis.py, logo\
    installer\                   ← virmodock.iss, Indonesian.isl, gambar wizard
    dev\                         ← skrip uji & pembuat docs/screenshot (lihat §6); keluaran uji di dev\uji\
    dist\, build\, rilis\        ← hasil build (tidak ikut git)
```
Kode lama yang bisa dipakai ulang: `E:\Bikin Docking Simpel\app\analysis.py` (deteksi interaksi H-bond/hidrofobik/π-π/vdW + proyeksi 2D), `app\engine\dockgpu.py` (parser .dlg, ringkasan, Ki, LE), `app\ui\viewer.js` fungsi `diagram2D` (diagram interaksi 2D SVG).

## 4. SUDAH SELESAI (Tahap 1)
- [x] Perbaikan bug "GPU tidak terbaca" di DockingSimpel.exe lama (race condition cek WSL) + rebuild.
- [x] Mockup jendela utama (terang & gelap) — disetujui.
- [x] Build AutoDock-GPU OpenCL native Windows + bundel runtime legal.
- [x] Deteksi perangkat otomatis tiap start (tanpa WSL), status bar GPU/VRAM/driver, pilihan perangkat GPU/CPU di toolbar (otomatis CPU jika tak ada OpenCL).
- [x] Jendela PySide6: menu (File/Edit/View/Prepare/Dock/Analyze/Tools/Help), toolbar, dock Hierarki/Properti/Tampilan/Antrean/Log/Pesan, simpan geometri+layout (QSettings), mode gelap/terang, menu bar gradien biru.
- [x] Viewport 3D: muat objek, tooltip atom, klik pilih atom → Properti, mode ukur jarak, gizmo sumbu, putar otomatis, fokus.
- [x] Impor: PDB/PDBQT/CIF/SDF/MOL2/SMILES, drag-drop file & folder, RCSB (PDB→cadangan mmCIF), PubChem (3D→cadangan 2D+embed), SMILES (RDKit embed + MMFF). Struktur dipecah: protein / ligan asli / air / ion.
- [x] Hierarki: objek → rantai → residu (lazy), centang tampil/sembunyi, filter, menu klik kanan (Tampilkan/Sembunyikan/Warnai/Fokus/Ganti nama/Ekspor/Hapus; residu: stick, fokus).
- [x] Panel Tampilan ala PyMOL: representasi kartun/pita/stick/garis/bola-stick/bola/permukaan/mesh (multi), warna elemen(+karbon pilihan)/rantai/pelangi/SS/B-faktor/hidrofobisitas/muatan/tunggal, palet cepat, transparansi, permukaan SES/SAS/vdW + warna + opasitas.
- [x] Grid box otomatis berpusat di ligan asli saat impor (digambar di viewport).
- [x] First-run wizard (cek sistem, panduan driver per vendor, software pendukung, folder kerja).
- [x] "Buka di…" PyMOL/ChimeraX/DSV (deteksi otomatis + atur lokasi manual).

## 4b. SUDAH SELESAI (Tahap 2, 8 Okt 2026) — semua teruji otomatis
File baru: `core/proyek.py`, `core/prep_reseptor.py`, `core/prep_ligan.py`, `core/mesin.py`, `core/antrean.py`,
`ui/dialog_reseptor.py`, `ui/dialog_ligan.py`, `ui/panel_docking.py`, `ui/panel_antrean.py` (PanelAntrean; PanelHasil kemudian pindah ke `ui/panel_hasil.py` di Tahap 3).
- [x] **Proyek** `.vmd` (proyek.json atomik + 5 cadangan, objek viewer disimpan di `objek/`), simpan otomatis (debounce 1 s + tiap 3 menit), Simpan/Buka/Proyek baru, proyek dibuat otomatis saat preparasi pertama, **pemulihan crash** (`QSettings sesi_terbuka`). Buka ulang → objek, kotak, parameter, job kembali persis (teruji).
- [x] **Reseptor**: gemmi (altloc okupansi tertinggi/A, buang H, rantai, air, ligan, aditif) → Meeko `Polymer.from_pdb_string(allow_bad_res=True)` Gasteiger/templat → cadangan Open Babel. Ion logam (Zn, Mg, Ca, Mn, Fe, Cu, Co, Ni) dalam radius dari ligan asli ditambahkan dengan tipe AD4 + muatan formal. Residu cacat dilaporkan. Kollman: tidak tersedia (dinonaktifkan + tooltip). 1ITB: 4556 atom vs MGLTools 4559 (0,07 %). 3KS3: Zn dipertahankan, AutoGrid & Vina menerima.
- [x] **Ligan batch**: fragmen terbesar, protonasi pH (Open Babel), ETKDG bila 2D/datar, MMFF94 (cadangan UFF), Meeko → PDBQT; tanda >32 torsi / >256 atom / tipe tak didukung; gagal tidak menghentikan yang lain. 20 PubChem: unduh 14 s (paralel 6) + preparasi 1 s.
- [x] **Panel Parameter** (dock kanan, tab dengan Tampilan): mesin AD-GPU/Vina/AD4 (nonaktif bila program hilang), perangkat, preset Cepat/Standar/Teliti + preset kustom, pencarian per mesin, seed, grid box angka + npts + peringatan >126 titik/>30 Å, tombol pusat ligan asli / residu terpilih / ligan +8 Å / blind (spasi otomatis). Sinkron dua arah dengan combo toolbar.
- [x] **Grid box interaktif**: Shift+seret = geser (akurasi diuji: 60,−25 px → 60,−25 px), Shift+gulir = ukuran, Alt+gulir = satu sumbu (tombol X/Y/Z). Sinkron ke panel (`py.kotak`). Grid otomatis memakai ligan asli terbesar (aditif seperti GOL/EDO/SO4 dikecualikan — `molekul.ADITIF`).
- [x] **Mesin**: GPF (union tipe ligan, CG*→C, G* dilewati, pakai ulang bila GPF identik) → autogrid4; AD-GPU (`--heuristics`, `--nev` hanya bila heuristik mati); Vina; AD4 (DPF relatif `../../grid` karena autodock4 tak tahan spasi di jalur). Parser .dlg (pose wakil klaster + RMSD ke masukan) & Vina. Fallback otomatis AD-GPU → Vina bila galat OpenCL (`Error: cl*()`, kode keluar DLL hilang).
- [x] **Antrean** (QProcess per ligan): progres per ligan (AD-GPU dari tabel evaluasi, Vina dari bintang, AD4 dari .dlg), ETA, jeda (setelah ligan berjalan), lanjut, batal (kill), hapus selesai, buka folder/log, ligan >batas GPU dilewati dengan alasan. Tutup aplikasi → job "dijeda", dilanjutkan tanpa mengulang ligan selesai. Notifikasi tray Windows + `QApplication.alert`. Minimize tidak menghentikan job.
- [x] **Tab Hasil** (ringkas): ΔG terbaik, Ki perkiraan, RMSD ref, jumlah pose, catatan etika; klik dua kali → pose ke grup "Hasil · …" di Hierarki. Properti pose (ΔG, Ki, klaster, RMSD).
- [x] Dependensi `autogrid4.exe`/`autodock4.exe`: hanya kernel32 + msvcrt (tanpa cygwin) — aman dibundel.
- [x] Hasil uji 1HSG/MK1: AD-GPU 10 run −12,1…−13,3 kcal/mol (~4 s/ligan), Vina exh 8 −11,15 (~49 s), AD4 jalan.

## 4c. SUDAH SELESAI (Tahap 3, 8 Okt 2026) — teruji otomatis (`dev/uji_tahap3.py`)
File baru: `core/analisis.py`, `core/diagram2d.py`, `core/ekspor.py`, `core/laporan.py`, `ui/panel_hasil.py`,
`ui/panel_interaksi.py` (PanelInteraksi, TabDiagram), `ui/tab_banding.py`, `ui/dialog_ekspor.py`. Paket baru: **openpyxl 3.1.5** (MIT, izin pengguna 8 Okt 2026).
- [x] **Molekul pose**: `analisis.pose_mol` membangun RDKit Mol (H, orde ikatan, muatan) dari blok pose + REMARK SMILES PDBQT masukan (Meeko `PDBQTMolecule` + `RDKitMolCreate`).
- [x] **Interaksi** (numpy + fitur RDKit BaseFeatures.fdef): ikatan H (sudut bila ada H), hidrofobik (C hanya bertetangga C/H, 1 kontak per residu), π–π tumpuk/T, π–kation (offset ≤ 2 Å), jembatan garam, halogen, logam, vdW. Kriteria di `analisis.KRITERIA` (tercantum di panel & laporan). ~0,07 s/pose.
- [x] **Ringkasan otomatis per ligan** setelah docking (di `Pelaksana`): LE, jumlah interaksi per jenis, residu kontak (peta panas), **RMSD ke kristal** semua pose (graf tanpa orde ikatan → cocok lintas protonasi, minimum atas simetri, tanpa penjajaran). Proyek lama dilengkapi otomatis saat dibuka (`analisis_ulang`).
- [x] **Tab Hasil**: pohon ligan → pose, sortir numerik, filter teks & ΔG, kolom LE/klaster/RMSD kristal (hijau ≤ 2 Å)/H/HF/π/lain, centang 2–4 → Bandingkan, Peta interaksi, Ekspor.
- [x] **Panel Interaksi** (dock kanan) + interaksi 3D (saklar per jenis, label jarak/residu, residu kontak stick) + klik → fokus residu.
- [x] **Diagram 2D** (tab tengah): ligan RDKit CoordGen, residu di sinar keluar dari atom jangkar + relaksasi; lingkaran tak pernah menutupi ligan; legenda; terang/gelap; simpan SVG/PDF (vektor, ukuran mm) / PNG/TIFF ber-DPI.
- [x] **Validasi redocking** (Analyze): ligan kristal disiapkan ulang **tanpa minimisasi** (nama "<ligan> (kristal)") → job dengan parameter sama → RMSD, simpan ke `proyek.validasi`, tumpang-tindih kristal (karbon magenta) vs pose (biru). 1HSG/MK1 AD-GPU: 1,21 Å (valid); Vina 0,48 Å.
- [x] **Bandingkan** 2–4 ligan: viewport 2×2 (Viewer terpisah), samakan sudut pandang, residu bersama, peta panas residu × ligan. **Peta interaksi** semua hasil (≤ 200 ligan).
- [x] **Pusat Ekspor** (File › Ekspor, Ctrl+E): gambar 3D PNG/TIFF(LZW/raw)/JPEG/WebP, preset jurnal/slide/poster, DPI tertulis benar, latar putih/tema/transparan/hitam, render ulang resolusi penuh (`VM.gambar`: devicePixelRatio sementara, maks 8192 px); diagram 2D; kompleks PDB (rantai L, CONECT, REMARK), kompleks semua ligan (folder), SDF bertag (terbaik/semua pose), PDBQT; CSV (pemisah ; , tab, desimal koma, BOM); XLSX (Ringkasan berskala warna, Semua pose, Interaksi, Parameter, Info).
- [x] **Laporan PDF** (A4, QTextDocument): validasi, reseptor & preparasi, parameter & perangkat, 15 teratas, gambar 3D + diagram 2D ligan terbaik, tabel interaksi, metode + kriteria, sitasi (AD-GPU, AD4, Vina, Meeko, RDKit, Open Babel, gemmi, 3Dmol.js), catatan etika; peringatan bila belum validasi.

### Ditunda ke v1.x (sesuai Lampiran C/E4, bukan MVP)
~~Tile rendering, salin ke clipboard, skrip PyMOL/ChimeraX, sematkan pose, IFP~~ (selesai, §4g). Sisa: (semua selesai, §4h). (PoseBusters sudah dikerjakan di v1.1, §4e.)

## 4d. SUDAH SELESAI (Tahap 4, 8 Okt 2026)
Versi: `virmodock/__init__.py` `__version__ = "0.9.0"` (pra-rilis; jadi 1.0 setelah uji relawan E5).
- [x] **Lisensi (B2)**: VirmoDock **GPL-3.0-or-later** (`LICENSE`, disetujui pengguna). **Open Babel kini program terpisah** (`core/obabel.py` → `bin/openbabel/obabel.exe`, dari wheel + `msvcp140.dll`); tidak ada lagi `import openbabel`/`pybel` di proses Python. `LISENSI_PIHAK_KETIGA.txt` + folder `licenses/` (teks resmi; GPL-3/LGPL-3 dari gnu.org, Vina/3Dmol/Lucide dari GitHub — izin pengguna) + tawaran kode sumber GPL (AD-GPU, AD4, Open Babel). Help › Lisensi & cara mengutip.
- [x] **Ikon** `virmodock/aset/virmodock.ico` (16–256 px, logo garis putih di kotak aksen biru; `dev/buat_ikon.py`).
- [x] **Mode portable**: `portable.flag` di samping exe → pengaturan `data/pengaturan.ini`, log `data/log`, proyek `Proyek/`. Pengaturan selalu lewat `paths.settings()`.
- [x] **Log berkas** `core/catat.py` (rotasi 10 × 1 MB, excepthook). Panel Log/Pesan ikut ditulis.
- [x] **Pindah laptop** `core/pindah.py`: File › Pindah laptop › Ekspor/Impor `.vmdbackup` (zip: pengaturan JSON termasuk layout biner, proyek opsional; jalur yang tak ada diabaikan + dicatat; GPU dideteksi ulang). Teruji bolak-balik.
- [x] **Jendela & DPI**: ukuran awal mengikuti layar, geometri di monitor yang hilang → dipusatkan. Diuji 100 % (1366×768), 150 % (asli), 200 % (`QT_SCALE_FACTOR`).
- [x] **Help**: Panduan (F1) & Dokumentasi (HTML offline di `docs/`), Lapor masalah (teks + info sistem + log, pengguna menyalin sendiri — tidak ada pengiriman otomatis), Buka folder log, Lisensi & sitasi, Tools › Uji mandiri komponen.
- [x] **Uji mandiri** `core/ujimandiri.py` + `VirmoDock.exe --uji-mandiri hasil.json` (awalnya 11 uji: 4 mesin, obabel, RDKit+Meeko, gemmi, fitur kimia, docking Vina mini, GPU, openpyxl; kini 14 — lihat §4e). Argumen lain: `--disable-gpu`, berkas/folder `.vmd`/`.vmdbackup` dari Explorer, `VD_TANGKAP` (uji: simpan grab jendela lalu keluar).
- [x] **Dokumentasi** `docs/` (sumber `docs/_sumber/*.html` → `dev/buat_docs.py`): panduan pengguna, instalasi, pindah laptop, setup GPU, troubleshooting, metode & kriteria; 15 tangkapan (`dev/buat_screenshot.py`).
- [x] **PyInstaller onedir** `build_tools/virmodock.spec` (titik masuk `VirmoDock.pyw`; Qt debug pak/devtools/qml/terjemahan non-ID dibuang) → **579 MB**, start ± 2–3 s; exe beku lulus uji mandiri & GUI (WebGL, impor, GPU).
- [x] **Installer** Inno Setup 6.7.3 (dipasang di `vendor/innosetup`, izin pengguna; tanda tangan valid) — `installer/virmodock.iss` + `installer/Indonesian.isl` (terjemahan sendiri; pesan jarang → Inggris). Per-pengguna tanpa admin (bisa pilih semua pengguna), shortcut Start/Desktop, asosiasi `.vmdbackup` (bawaan) & `.pdbqt` (opsional), uninstaller.
- [x] **Rilis satu perintah**: `.venv\Scripts\python.exe build_tools\rilis.py` → docs → build → uji mandiri (gagal = berhenti) → `rilis/VirmoDock-Setup-x.y.z.exe`, `rilis/VirmoDock-Portable-x.y.z.zip`, `SHA256SUMS`.

## 4e. v1.1 (dikerjakan sebelum rilis 1.0 atas permintaan pengguna, 8 Okt 2026)
- [x] **Sifat Ligan** `core/sifat.py` + `ui/tab_sifat.py` (tab tengah "Sifat Ligan", Analyze › Sifat ligan & BOILED-Egg). RDKit saja, tanpa paket baru: MW, WLOGP (Crippen), MR, TPSA (N,O), donor/akseptor, rotasi, cincin, Fsp3, QED; Lipinski (≤1 pelanggaran, NHOH/NO), Ghose, Veber, Egan, Muegge; PAINS A–C + Brenk (FilterCatalog); **BOILED-Egg** (elips Daina & Zoete — parameter diverifikasi terhadap poligon PyBOILEDegg, galat < 1 %). Struktur dinetralkan dulu (fragmen terbesar + Uncharger). Cache `proyek.ligan[*]["sifat"]` (`VERSI` → hitung ulang otomatis). Sumber: ligan proyek + ligan viewer yang belum disiapkan (nama sama = dilewati). Ekspor CSV, grafik SVG/PDF/PNG/TIFF (`JendelaUtama._simpan_svg` umum, dipakai juga diagram 2D), lembar XLSX "Sifat ligan", tabel + metode + sitasi di laporan PDF, `docs/metode.html`. Uji: `dev/uji_sifat.py` (aspirin/diazepam/kafein/indinavir/siklosporin/kurkumin), `dev/uji_sifat_gui.py` (6M2N 26 ligan → `dev/uji/sifat/`).
- [x] **Statistik** `core/statistik.py` + `core/grafik.py` (grafik SVG umum tanpa matplotlib: `Kanvas`, `histogram`, `sebar`, `batang`, `peta_korelasi`; angka koma desimal) + `ui/tab_statistik.py` (tab "Statistik", Analyze › Statistik & grafik). Pilih job (bawaan job terbaru; "Semua job" = ΔG terbaik per ligan). Histogram (Freedman–Diaconis), sebar + regresi OLS + pita CI 95 % + Pearson/Spearman + p (scipy.stats — scipy 1.18 sudah ikut sebagai dependensi Meeko, BSD), batang ΔG teratas, matriks korelasi Pearson/Spearman (* p < 0,05). Panel kanan: hasil korelasi + deskriptif semua variabel. Variabel: ΔG, LE, pKi, interaksi, RMSD kristal + sifat ligan. Ekspor grafik SVG/PDF/PNG/TIFF, data CSV, lembar XLSX "Statistik" (deskriptif per job). Jebakan: widget di `QToolBar` disembunyikan lewat QAction dari `addWidget`, bukan `setVisible` widget; teks "< 0,001" di rich text harus di-`escape`. Uji: `dev/uji_statistik.py`, `dev/uji_statistik_gui.py`.
- [x] **PoseBusters QC** (izin unduh pengguna 8 Okt 2026): `posebusters 0.6.5` (MIT) + `pandas 3.0.6` (BSD-3) + `PyYAML 6.0.3` (MIT) + turunan `python-dateutil`, `six`, `tzdata` — lisensi di `licenses/` & `LISENSI_PIHAK_KETIGA.txt`, `requirements.txt`, spec `collect_data_files("posebusters")`. `core/qc.py`: konfigurasi *dock* (22 uji biner, nama Indonesia), protein = `reseptor/bersih.pdb`. **Berjalan di proses pekerja terpisah** (`VirmoDock.exe --qc-pekerja ALAMAT KUNCI` / `python -m virmodock --qc-pekerja`, tersambung `multiprocessing.connection` AF_PIPE + authkey; dipakai ulang, `qc.tutup()` di closeEvent; gagal → jalan di proses sendiri). Alasan: ETKDG/UFF uji energi memegang GIL → thread biasa membuat GUI tersendat 422 ms; dengan proses: 93–100 ms. JANGAN pakai ProcessPoolExecutor/spawn: mengimpor ulang skrip `__main__` (skrip uji dev ikut jalan dua kali). Otomatis: `Pelaksana._qc_antre` (thread → proses) setelah tiap ligan selesai → sinyal `qcSelesai` → `l["qc"]`; proyek lama dilengkapi di `analisis_ulang` saat dibuka. Tampil: kolom "PoseBusters" tab Hasil (indeks 8, tooltip rincian), Properti pose 1, Analyze › Periksa pose aktif (PoseBusters) (dialog semua uji, pose mana pun), CSV/XLSX (PoseBusters + uji gagal), laporan PDF (kolom + metode + sitasi), Help › Cara mengutip, `docs/metode.html`. 6M2N: 52/55 pose lulus (curcumin, lopinavir: jarak minimum ke protein). Uji: `dev/uji_qc.py` (pose digeser ke protein & ikatan diregangkan harus gagal), `dev/uji_qc_antrean.py`, `dev/uji_qc_gui.py`, `dev/uji_responsif.py`.
- [x] Uji mandiri kini **14 uji** (+ sifat ligan, statistik/scipy, PoseBusters lewat proses pekerja). Build PyInstaller beku 8 Okt 2026: 14/14 lulus, 611 MB. `dev/uji_tahap3.py` lulus (regresi). `rilis/` belum dibuat ulang (menunggu keputusan pengguna). **v1.1 selesai.**

## 4f. Perombakan UI/UX untuk pemula (8 Okt 2026, permintaan pengguna: "kotak-kotak overlap, penuh, tombol docking di atas dan di kanan")
Cadangan kode sebelum perombakan: scratchpad sesi (tidak permanen) — pakai git `05b88f8` + diff bila perlu.
- [x] **Panel Langkah** (`ui/panel_alur.py`): kiri atas `DaftarLangkah` 1 Protein → 2 Ligan → 3 Area docking → 4 Jalankan → 5 Hasil (ikon nomor `icons.ikon_nomor` / centang, keterangan status), kanan dock "Panel kerja" = `PanelLangkah` (satu halaman per langkah: judul, 1 kalimat, tombol aksi, tombol utama biru, tautan "Berikutnya ›"). Status dihitung `JendelaUtama._segarkan_langkah` (debounce 150 ms; dipicu `minta_simpan`, `tambah/hapus_objek`, `_atur_kotak`, `_muat_hasil`, `_job_berubah`). Maju otomatis: reseptor siap → langkah 2; ligan siap → 3 (atau 4 bila area sudah ada); docking selesai → 5.
- [x] **Satu tempat untuk pengaturan docking**: combo Mesin/Perangkat + tombol Jalankan + Reseptor/Ligan/Grid box DIHAPUS dari toolbar (tetap di menu & F5). `PanelDocking` kini tidak tampil sendiri; menyediakan `hal_area` (langkah 3) dan `hal_jalan` (langkah 4: ringkasan masukan, mesin, perangkat, "Ketelitian" = preset langsung diterapkan, **Lanjutan ▸** terlipat berisi parameter rinci/seed/simpan preset, tombol "Jalankan docking (n ligan)" menempel di bawah). `d_param` = alias `d_kerja`.
- [x] **Ruang kerja** Siapkan / Docking / Analisis (tombol segmen di toolbar, juga View › Ruang kerja): `atur_ruang()` mengatur tab tengah (Siapkan: Viewport saja; Docking: + Hasil; Analisis: semua) dan dock Interaksi (hanya Analisis). Langkah 1–3 ↔ Siapkan, 4 ↔ Docking, 5 ↔ Analisis (sinkron dua arah).
- [x] **Antrean ringkas**: dock Antrean/Log/Pesan tersembunyi bawaan; tombol "Antrean: … ▴" di kanan bilah status (`b_antre`) membuka/menutup; terbuka otomatis saat docking/validasi dimulai, ditutup lagi bila semua job sukses. `_galat` kini membuka panel bawah + pesan di bilah status (dulu Pesan selalu terlihat).
- [x] **Bar gaya 3D** (Kartun/Stick/…) hanya di tab Viewport (`self.w_view` = bar + viewer; pakai `w_view` untuk `setCurrentWidget`, bukan `viewer`).
- [x] **Rapi**: tabel Hasil 7 kolom bawaan (#, Ligan, ΔG, LE, RMSD kristal, PoseBusters, H), kolom lain lewat klik kanan judul kolom (QSettings `kolom_hasil`); panel Interaksi hanya petunjuk sampai pose dipilih, opsi label dalam grid 2 kolom (dulu tumpuk); Properti di bawah Panel kerja (lebih kecil di layar < 850 px); dock "Hierarki" berganti nama "Objek".
- Layout tersimpan memakai kunci baru `layout_v2` (struktur dock berubah); View › Atur ulang layout langsung menerapkan susunan bawaan.
- Uji: `dev/uji_ux.py` (semua langkah, docking sungguhan dari langkah 4, maju otomatis, kolom, tema gelap; `VD_UKURAN=1366x768` untuk layar kecil) → `dev/uji/ux/`. Regresi `uji_tahap3.py`, `uji_kontrol.py` lulus.
- [x] **Polesan kedua** ("harus elegan, rapi, enak dipakai"): **halaman sambutan** `ui/halaman_awal.py` di tab Viewport saat belum ada objek (logo, "Mulai docking", kartu Ambil dari RCSB / Buka berkas / Buka proyek / Proyek terakhir, tautan Tutorial & Panduan; `stak_view` indeks 1; baru ditampilkan setelah `viewer._siap`); tombol panel langkah berikon (`_tombol(ikon=)`, diwarnai ulang `PanelLangkah.set_mode`); ikon baru `chart`, `smiles`; tab dock di ATAS (`setTabPosition North`) dan judul dock ganda dihapus untuk Panel kerja/Tampilan/Interaksi (`setTitleBarWidget(QWidget())`); tab Hasil kosong → petunjuk; teks "Hierarki" → "Objek".
- [x] **Bug kamera diperbaiki**: `VM.fokusSemua`/`ukurUlang` dulu `zoomTo({})` = ikut model tersembunyi (ligan SMILES di titik asal) → protein tampil di pojok. Kini `VM._terlihat()` hanya model terlihat. Plus `ResizeObserver` pada `#gl` dan `VM.segarkanKanvas` saat tab Viewport tampil lagi.
- Uji: `dev/uji_ux_awal.py` (sambutan → impor 1HSG; `VD_TEMA=gelap`).
- [x] **Menu atas dirombak** (8 Okt 2026): 8 menu Bahasa Indonesia — Berkas, Edit, Tampilan, Siapkan, Docking, Analisis, Alat, Bantuan; tiap item punya keterangan (`setStatusTip`, tampil di bilah status) dan banyak pintasan (35, tanpa bentrok; Ctrl+1/2/3 ruang kerja, Alt+1–5 langkah, Ctrl+/ daftar pintasan). Menu Siapkan berjudul kelompok "Langkah 1/2/3" (`_judul_menu`, QWidgetAction — `addSection` tidak tampil dengan QSS ini). Menu Docking: submenu Mesin & Ketelitian diisi dari panel langkah 4 (`_isi_menu_docking`), Jeda/Lanjut/Batal job. Bantuan › Pintasan keyboard (`pintasan()`, otomatis dari semua QAction). Helper `_a(teks, ikon, fn, kunci, tip, cek)` — urutan argumen berubah (tip sebelum cek). Uji: `dev/uji_menu.py` → `dev/uji/menu/`.
- [x] `_fokus(sel)`: semua pemusatan kamera lewat fungsi ini — bila tab Viewport tersembunyi, tampilkan dulu lalu fokus 250 ms kemudian (dulu validasi redocking/buka pose dari tab Hasil → viewport kosong/terpotong).
- [x] Tangkapan dokumentasi dibuat ulang dengan UI baru (`dev/buat_screenshot.py`: + `00_sambutan`, `06b_jalankan`, `16_sifat`, `17_statistik`; `dev/buat_screenshot_tutorial.py`). **PERIKSA** `docs/gambar/04_reseptor_siap.png`, `07_antrean.png`, `11_validasi.png`: sebelum perbaikan `_fokus` viewport terpotong/kosong — pastikan sudah benar.

### LANJUTKAN DI SESI BERIKUTNYA (urutan)
1. [x] **Bug kamera DIPERBAIKI** (sesi berikutnya): akar masalah `VM._terlihat()` mengembalikan `{model: [m1, m2]}` → `v.zoomTo` 3Dmol **macet tanpa akhir**, seluruh halaman JS beku (runJavaScript tak pernah kembali, kamera berhenti di posisi tengah animasi = terpotong/kosong). Kini selektor `{or: [{model: m}…]}`. Tambahan pengaman: `VM._bilaSiap()` (fokus/ukurUlang/segarkan hanya bila `#gl` > 0 px), ResizeObserver ditunda per frame & hanya bila ukuran berubah. Diagnostik: `dev/diag_kamera.py` (detak JS + jejak masuk/keluar semua `VM.*`).
2. [x] **Dokumentasi diperbarui ke UI baru**: `panduan.html` ditulis ulang (tampilan & ruang kerja, halaman sambutan, langkah 1–5, antrean ringkas, kolom Hasil klik kanan, PoseBusters, Sifat Ligan, Statistik, pintasan baru); `tutorial.html` disesuaikan (menu Berkas/Siapkan/Docking/Analisis/Alat/Bantuan, panel Objek, Panel kerja, Ketelitian + Lanjutan, gambar `00_sambutan`, `06b_jalankan`, `16_sifat`; 24 halaman); `gpu`, `instalasi`, `metode`, `pindah_laptop`, `troubleshooting` (judul kini "Mengatasi masalah" = nama menu). Struktur menu aktual dicetak oleh `dev/dump_menu.py` → `dev/menu.txt` (pakai ini saat menulis dokumen).
3. Rilis: `.venv/Scripts/python.exe build_tools/rilis.py` (docs → build → uji mandiri 14/14 → installer + portable + SHA256SUMS); uji pasang/copot seperti §5.
4. Commit lokal semua (v1.1 + UI/UX + menu) — tanya pengguna dulu.
5. Sesudah itu: v1.2 (Lampiran E4) atau sisa §5 (relawan E5, GitHub, SignPath).
- [x] Dokumentasi & tutorial PDF sesuai tampilan baru (lihat nomor 2).

## 4g. Kelompok A + Dimorphite-DL + v1.2 tahap 1 (8 Okt 2026, permintaan pengguna "semua kita selesaikan")
- **Pilih GPU** (>1 OpenCL): `env._opencl` hitung `devnum=(platform<<8)+perangkat+1`; combo data `gpu:N`; `Parameter.devnum` -> `--devnum`.
- **Salin gambar** Edit › Salin gambar (Ctrl+Shift+C) + tombol Salin di Diagram/Sifat/Statistik/Uji (`_salin_svg`, 2400 px @300 dpi; 3D = viewport ×2). Uji: `dev/uji_salin.py`.
- **Sesi PyMOL/ChimeraX** `core/sesi_eksternal.py` (.pml jalur absolut, .cxc relatif; residu kontak berlabel + garis interaksi warna diagram). Berkas › Ekspor › Sesi…; Buka di PyMOL/ChimeraX memakai sesi bila ada pose aktif. .pml diuji PyMOL headless; .cxc belum (ChimeraX tidak terpasang).
- **Gambar 3D > 4096 px per ubin** (`viewer.js ubinMulai/ubin/ubinSelesai`: matriks proyeksi diskalakan n× + geser, dpr sama -> garis/label konsisten; disatukan di `_render_ubin`). Maks 16384 px. 9000 px vs 3000 px: selisih rata 0,47/255, tanpa sambungan (`dev/uji_ubin.py`).
- **Bug kamera buka proyek** diperbaiki: `fokus` beranimasi ke protein mentah tersembunyi menimpa `ukurUlang` -> sesi kosong sekarang `fokusSemua` 1 s setelah muat.
- **Sematkan pose** (klik kanan pose › Sematkan; ikon pin; `o.info["sematkan"]`, tersimpan). `dev/uji_sematkan.py`.
- **IFP** `analisis.sidik_jari` (bit "residu|jenis", tanpa vdW) + `tanimoto`; `l["ifp"]`, `l["ifp_kristal"]`; kolom Hasil "IFP vs kristal"; Statistik › Kemiripan interaksi (matriks); lembar Excel "Sidik jari interaksi". Proyek lama dilengkapi lewat analisis_ulang (syarat "ifp" in l).
- **Dimorphite-DL 2.1.0** (Apache-2.0, + loguru MIT, colorama BSD-3, win32-setctime MIT; lisensi di licenses/, requirements, spec `collect_data_files("dimorphite_dl")`). Opsi metode protonasi + "varian ≤ N" (enumerasi pH ± 1 -> ligan "nama [vN]"; `HasilLigan.asal`). JEBAKAN: Dimorphite di dalam ThreadPool memberi hasil netral -> dihitung di thread utama (`_uraikan_varian`); `max_variants=1` memotong ke masukan netral -> pakai `[:1]`. Fenol/katekol dianggap terdeprotonasi (aturan pKa luas) -> Open Babel tetap bawaan. Uji mandiri kini 15/15.
- **Kontribusi energi per atom** (D4) `core/kontribusi.py`: suku Vina antarmolekul dihitung ulang (Vina 1.2 tak punya --atom_terms); MK1 kristal −19,281 vs vina −19,271. Analisis › Kontribusi energi per atom (K): atom pose diwarnai hijau–putih–merah, bola ∝ |E|.
- **Uji & Grafik** (A7b tahap 1) `core/uji.py`, `core/grafik_uji.py`, `ui/tab_uji.py`: lembar data (tempel Excel/CSV/ΔG docking), uji otomatis (Shapiro, Brown–Forsythe; Welch/MW/berpasangan; ANOVA+Tukey, Welch+Games–Howell, KW+Dunn-Holm, Dunnett), ukuran efek, paragraf interpretasi + Metode; grafik batang/titik/kotak/median + braket bertingkat; XY 4PL IC50 ± CI. Validasi PlantGrowth = R. Tersimpan di `proyek.uji_grafik`. `dev/uji_tab_uji.py`.
- A7b tahap berikut: selesai di §4h.
- **P2Rank 2.5.1** (izin pengguna 8 Okt 2026, ±320 MB unduhan): `vendor/bin/p2rank` (dipangkas: bin+config+model default/alphafold/_score_transform = 116 MB; test_data & model konservasi/rescore dibuang) + `vendor/bin/jre` Temurin 21.0.12.1 (zip SHA-256 d35f31e7…, 146 MB). `core/p2rank.py` (java -cp p2rank.jar;bin/lib/* … predict; JEBAKAN: cwd = folder P2Rank -> semua jalur harus absolut; lib ada di `bin/lib`). Tombol langkah 3 + Siapkan › Deteksi kantong; dialog tabel; bola+label #n di viewport; kotak = sebaran residu + 4 Å (16–30). 1HSG: 1 kantong, 0,8 Å dari pusat MK1, ±5–14 s. Uji mandiri 16/16 (struktur uji `virmodock/aset/uji_1hsg.pdb`). Lisensi: licenses/P2Rank_LICENSE.txt, P2Rank_pustaka.txt (Weka GPL-3, CDK/BioJava LGPL), Eclipse-Temurin-JRE_LICENSE.txt. Ukuran installer naik ±260 MB terpasang. `dev/uji_p2rank.py`.
- Bentuk transparan 3Dmol: halo seleksi -> bola kerangka (wireframe) biru; bola π/titik ukur/pusat kotak dibuat buram. Terverifikasi tangkapan layar.

## 4h. Sisa fitur v1.x (8 Okt 2026, permintaan pengguna "kerjakan semua berurutan… smooth rapi bagus")
Tanpa paket baru (Pillow, SciPy, 3Dmol sudah ada).
- **Panel Format klik-elemen** (`ui/tab_uji.py`: `KanvasKlik`, `PanelFormat`): grafik mengisi `daerah=[(kunci,x0,y0,x1,y1)]` (koordinat SVG) -> sorot saat hover, klik membuka halaman panel (grafik, judul, label_y, sumbu_y, sumbu_x, grup:i, braket, data). Gaya = dict `grafik_uji.GAYA` (None = otomatis; `gaya_lengkap()` membuang kunci asing), tersimpan di `uji_grafik["gaya"]`. `c_tanda/c_ns/c_palet/e_y/e_judul` dipindah ke panel (atribut tetap sama — `_uji_dari_docking` masih memakai `e_y`).
- **Sumbu Y**: `grafik_uji.SkalaY` (linear / log10 dengan tik minor / **patah sumbu** dua segmen; batang & galat dipotong `potong()` di celah, tanpa clipPath). Grafik dosis–respons ikut memakai SkalaY. `grafik.Kanvas.f_tik` = ukuran huruf tik.
- **ROC** `uji.roc` (AUC = U/n1n0, CI DeLong, p Mann–Whitney, Youden, EF1/5/10%) + `grafik_roc`; opsi arah "skor rendah = positif" (ΔG). **Kontingensi** `uji.kontingensi` (2×2: Fisher + Yates + OR Woolf + RR Katz, Haldane bila 0; r×c: χ², Fisher r×c SciPy ≥1.15 bila harapan kecil; Cramér V) + batang bertumpuk 100%. Validasi: tea tasting p 0,4857, OR 9. Sitasi DeLong 1988 & Youden 1950 dicek ke Crossref, ada di metode.html.
- **Gaya tersimpan**: QSettings `uji/gaya_tersimpan` (JSON {nama: gaya}); kunci = `G.KUNCI_PRESET` + palet; 4 bawaan (`PRESET_BAWAAN`). Terapkan tidak mengubah teks/rentang sumbu.
- **Komposer figur** `core/komposer.py` + `ui/dialog_komposer.py` (non-modal, Analisis › Komposer figur, Ctrl+Shift+F, tombol "＋ Komposer" di tab Uji). Panel SVG disisipkan sebagai `<g transform>` (QtSvg tidak mendukung `<svg>` bersarang), id diberi awalan `pN_`; PNG via `<image xlink:href=data:>`. Opsi "samakan skala huruf" (bawaan) = satu faktor skala untuk semua SVG. Tersimpan `proyek.komposer` (raster di `komposer/*.png`, dibersihkan otomatis). Uji `dev/uji_komposer.py`.
- **Laporan Word/HTML**: dialog Ekspor › Laporan punya Format (PDF/Word/HTML; diingat di QSettings `format_laporan`). `core/docx_ringan.py` = penulis OOXML sendiri dari HTML laporan (h1/h2/p/b/span kelas/table.t/img/ol). `core/laporan_interaktif.py` = satu berkas HTML (3Dmol disisipkan, BSD-3): pose 30 teratas + interaksi dihitung di latar (`_tulis_laporan_html`), residu kontak dikirim dari Python (`kontak`) — JEBAKAN: selektor `within` 3Dmol memilih SEMUA residu di sini, jangan dipakai. Uji `dev/uji_laporan.py`, tangkapan HTML `dev/lihat_html.py`.
- **Animasi** `viewer.js animMulai/animBingkai/animSelesai` (putar, goyang ±30°, zoom: interpolasi view + slerp kuaternion), `core/animasi.py` (GIF palet bersama tanpa dither, WebP q90, folder PNG), Berkas › Ekspor › Animasi 3D. JEBAKAN: di layar HiDPI kanvas keluar 2× -> bingkai diperkecil LANCZOS ke ukuran target di `animasi.simpan(ukuran=)`. Uji `dev/uji_animasi.py`.
- **Label 3D tajam (HiDPI)**: 3Dmol menggambar teks label di kanvas seukuran huruf CSS, sedangkan kanvas WebGL dirender DPR×2 (layar 150% -> 3×) -> label buram. `viewer.js labelTajam()` (juga di JS laporan HTML) membungkus `$3Dmol.Label.prototype.setContext`: huruf/padding/border ×k (k = 4–6), lalu `sprite.scale` 1/k. Bandingan: `dev/diag_label.py`, `dev/uji/dpi/banding_label.png`. Diagnostik DPR/kanvas: `dev/diag_dpi.py`. Panel 3D Komposer kini diambil 3600 px (dulu 2× viewport ≈ 1900 px -> kabur di figur 174 mm @ 600 dpi).
- **Label 3D kelas publikasi** `viewer/label_vm.js` (dimuat viewer.html sesudah 3Dmol; disisipkan juga ke laporan HTML): membungkus `$3Dmol.Label.setContext` — panggil asli dulu (material/tekstur/perataan dibuat 3Dmol; kelas Texture/SpriteMaterial TIDAK terekspos di `$3Dmol`), lalu kanvasnya digambar ulang: pil + bayangan + tepi, `vmGaya:'residu'` (nama 600 + nomor `warna2`), `aksen` (titik warna interaksi), `berat`, `bayang`, `padX/padY`, `radius`. k = rasio piksel kanvas sebenarnya (DPR, ×2 bila < 2 — 3Dmol menggandakan untuk antialias); `LabelVM.segarkan(v)` dipanggil di gambar/ubin/anim setelah DPR diubah -> label tajam juga di ekspor 4K.
- **Warna 3D pucat**: kabut kedalaman 3Dmol `fogStart` bawaan 0,4 memudarkan separuh belakang molekul ke warna latar; kini `v.fogStart = 0.75` (viewer.js & laporan HTML). Bandingan `dev/uji/dpi/banding_kabut.png`.
- **Render 3D** (menu Tampilan › Render 3D + tombol 'Render ▾' di toolbar viewport): sakelar Garis tepi (bawaan on, 3Dmol `setViewStyle` outline), Bayangan sekitar AO (bawaan off; AO bawaan 3Dmol), Kabut kedalaman Mati/Halus(0,75)/Kuat(0,4). QSettings `render_tepi/render_ao/render_kabut`; `VM.gayaRender({tepi, ao, kabut})`.
- **Anti-tabrakan label** `LabelVM.rapikan` (prioritas jarak/kantong, lalu residu; geser via material.screenOffset; dipanggil lewat viewChangeCallback -> rAF; render ulang HANYA bila ada yang bergeser, kalau tidak loop render tiap frame).
- **Presentasi sinematik** (jenis animasi 'sinema'): linimasa protein utuh -> zoom ke situs -> putar 360° -> sorot ≤ 4 interaksi (prioritas ikatan H, garam, π, halogen, logam, hidrofobik) dengan slab depan -7 Å agar pita protein tak menghalangi -> kembali. Bobot babak di `_linimasaSinema`; durasi disarankan ≥ 16 s.
- **9 Okt 2026**: commit `5932b34` (130 berkas; JRE/P2Rank di .gitignore, cara pasang di README). Build rilis 0.9.0 (Setup 319 MB, Portable 434 MB, terpasang 895 MB): uji mandiri dist 16/16; pasang diam-diam per-pengguna -> uji mandiri 16/16 + FFmpeg terbundel -> copot bersih (folder/shortcut/registry hilang); portable 16/16, data di folder sendiri. Laporan .docx diverifikasi via Microsoft Word (COM: 3 hlm, 5 tabel, 2 gambar, ekspor PDF rapi).
  Sesudah build: angka laporan gaya Indonesia (`laporan._id/_n`: koma desimal, minus U+2212; Ki di HTML juga); uji mandiri item 17 'Perekam video (MP4 H.264)'; perekam video tak lagi memancarkan 'selesai' saat dibatalkan/gagal (`_batal`); 4PL: galat bila respons datar + peringatan ekstrapolasi/CI lebar/tak sigmoid/R² rendah; ROC: peringatan AUC < 0,5 & n kecil. Format angka Indonesia juga di UI (tabel Hasil, Interaksi, Properti, Antrean, Bandingkan; `laporan.id_angka`; urutan tabel tetap numerik via UserRole). Statistik: bawaan 'Semua job' bila job terbaru < 3 ligan + petunjuk grafik kosong (IFP proyek lama -> Hitung ulang analisis). Gambar docs 00–20 & t04 diperbarui (+18_uji_format, 19_komposer, 20_video). Regresi total `dev/regresi.py` 38/38 (uji membaca proyek kerja_docs terbaru, bukan nama tetap). Build final: Setup 320 MB / Portable 436 MB, uji mandiri 17/17 di dist, terpasang, dan portable; copot bersih.
- **Video MP4 H.264** `ui/perekam_video.py` (Qt Multimedia: QVideoFrameInput -> QMediaCaptureSession -> QMediaRecorder; FFmpeg 7.1.5 LGPL bawaan PySide6 + encoder Media Foundation Windows; QtMultimedia dikeluarkan dari `excludes` spec, + ±21 MB). JEBAKAN: `QVideoFrameInput(format)` tak pernah siap -> pakai konstruktor polos; pompa bingkai lewat `QTimer.singleShot(0)` (panggilan langsung kirim->pompa->siap_lagi = stack overflow). Bingkai dialirkan (antre ≤ 3), JS mengirim JPEG q0,97 (`animBingkai(t, jpeg)`). Resolusi: fhd/qhd/uhd/kotak/tegak, 24/30/60 fps; 4K 120 bingkai ± 32 s. Lisensi: `licenses/FFmpeg_LICENSE_LGPL-2.1.txt`. Uji `dev/uji_video.py`, `dev/uji_animasi.py` (termasuk MP4 4K, resolusi dibaca balik).
- Uji: `dev/uji_grafik_lanjut.py` (klik elemen, patah sumbu, log, ROC, kontingensi, preset, simpan/muat). Docs: panduan (Format grafik, Komposer, Laporan 3 format, Animasi, pintasan), metode (ROC, kontingensi).

## 4i. Versi 0.9.1 (9 Okt 2026, permintaan pengguna: rencana E4 nomor 2 → 1 → 8 → 3 → 5 → 4)
- **BEDROC/logAUC** (`uji.bedroc`, `faktor_pengayaan`, `log_auc`, `_bootstrap_skrining`): BEDROC & EF identik RDKit (`rdkit.ML.Scoring`); skor seri diurutkan negatif dulu (konservatif, `_urutan`); CI bootstrap terstratifikasi 1000×. Grafik `grafik_roc(mode=roc|semilog|enrich)`, pilihan `c_kurva`. Sitasi Truchon & Bayly 2007, Mysinger & Shoichet 2010 (Crossref).
- **Konsensus skor** `core/konsensus.py` + `ui/dialog_konsensus.py` (Analisis › Konsensus skor…): kolom = job (bawaan: job dengan ligan selesai terbanyak per mesin) + rescoring Vina/Vinardo pose terbaik (`vina --score_only --autobox --scoring`, JEBAKAN: tanpa --autobox galat "ligand outside grid box"); disimpan `l["rescore"]` di job. Kunci ligan = `l["id"]`. Kendall W koreksi ties (= Friedman). Sitasi Vinardo (Quiroga 2016).
- **CHANGELOG.md** (ikut dibundel, spec) + `DialogApaBaru` non-modal: muncul sekali bila QSettings `versi_dilihat` != versi (pemasangan baru: diset tanpa dialog); Bantuan › Apa yang baru. Versi -> **0.9.1**.
- **Statistik lanjut** (`uji.py`): `koreksi_p` (holm/bonferroni/sidak/bh), `_anova_berulang` (GG ε), `_friedman`, `grubbs`, D'Agostino di deskriptif, `anova_dua_arah` (OLS kode efek, SS tipe III, uji lanjut per level B). UI: `c_koreksi`, jenis data `dua_faktor` (kolom 0 = faktor A), grafik `qq` & `grafik_dua_faktor`, legenda `_legenda`. JEBAKAN: teks '< 0,0001' di HTML harus di-escape (`_p_html`) — sebelumnya p kecil hilang dari tabel.
- **Model IC₅₀**: `dosis_respons(model=auto|4pl|3pl)`; uji F extra SS + AICc + bobot Akaike; pilihan di `c_uji` (data XY).
- **Grafik**: gaya `acuan` ('nilai=label; …'), `anotasi` ('|' = baris baru), `pos_anotasi`; `_hiasan()` dipanggil semua grafik. Sumbu kedua & EPS sengaja tidak dibuat (tak relevan / Qt tak menulis EPS).
- Uji baru: `dev/uji_statistik_lanjut.py` (13 validasi silang), `dev/uji_konsensus.py`.
- Regresi 40/40. Build 0.9.1 (Setup 320 MB, Portable 436 MB): uji mandiri 17/17 di dist, terpasang, portable; CHANGELOG ikut terbundel; copot bersih.

## 4j. Versi 0.9.2 (9 Okt 2026, permintaan pengguna: sisa E4 v1.2, v1.3, v1.5)
Izin unduh pengguna (9 Okt 2026): propka 3.5.1 (LGPL-2.1), pdb2pqr 3.7.1 (BSD-3) + mmcif-pdbx + docutils 0.17.1; admet-ai 2.0.1 (MIT) + torch 2.14.1 + chemprop + lightning + dependensi (sklearn, matplotlib, seaborn, descriptastorus, mordred, padelpy, …; DIBUNDEL, installer ±+500 MB); Ketcher 3.18.0 standalone (Apache-2.0, `vendor/ketcher`, tidak ikut git — README); data online ChEMBL/COCONUT + snapshot obat disetujui (`virmodock/aset/obat_disetujui.tsv.gz`, CC BY-SA, dibuat `dev/buat_pustaka_obat.py`). Lisensi: LISENSI_PIHAK_KETIGA.txt bagian 0.9.2.
- **Heatmap IFP ala ProLIF**: `grafik.peta_ifp` (ligan × residu|jenis, baris frekuensi, legenda) — tab Statistik jenis `peta_ifp` + saringan frekuensi `c_frek`. Tanpa paket ProLIF (butuh MDAnalysis).
- **Kemiripan/farmakofor** `core/kemiripan.py` + `ui/dialog_kemiripan.py` (Analisis › Kemiripan…): sidik jari morgan/featmorgan/maccs/atompair/gobbi, Butina, MDS/PCA (`grafik.sebar_kelompok` + `tempat_label` anti-tabrakan), cari mirip, farmakofor bersama (thread; pose dari `mesin.baca_hasil` + `analisis.pose_mol`). Farmakofor pose aktif: aksi `a_farma` (P), `viewer.js farmakofor()` bola kerangka (shapes 'farma'). Hidrofobik di cincin aromatik dibuang, ZnBinder dibuang.
- **Wizard reseptor** `ui/dialog_reseptor.py` (4 langkah, API lama `objek()/opsi()` tetap) + `core/periksa_protein.py`. **Protonasi** `core/protonasi.py`: `run_pdb2pqr` (--ff AMBER --ffout AMBER, propka, --pdb-output, --keep-chain, --drop-water) -> PDB bernama AMBER (ASH/GLH/HID/HIE/HIP/CYX/LYN) -> Meeko menerima & MEMPERTAHANKAN posisi H masukan (diverifikasi). `OpsiReseptor.protonasi='propka'|'templat'`, `ph`, `optimasi_h`; bawaan wizard propka (QSettings `prep/protonasi`, `prep/ph`). `sesuaikan_his_logam` (N pengikat logam ≤ 2,8 Å tanpa H). Simpan `reseptor/pka.csv`, `protonasi.pqr`, `pr.reseptor["protonasi"]`. 1HSG: ASH 25 B (pKa 9,1 — benar untuk HIV PR), Lys tak lengkap dilengkapi (Meeko dulu membuang).
  JEBAKAN: propka 3.5.1 `self.__annotations__` gagal di Python 3.14 (PEP 649) -> `protonasi.tambal_propka()` mengganti `Parameters.parse_line`. Logger PDB2PQR bernama `PDB2PQR3.7.1` (bukan `pdb2pqr`).
- **ChEMBL** `core/chembl.py` + `ui/dialog_chembl.py` (Berkas/Siapkan › Ligan dari ChEMBL; Analisis › Korelasi…): target dari PDB lewat RCSB (UniProt + taxid & kata khas nama entitas: `target.json?tax_id=…&pref_name__icontains=…` — UniProt PDB sering poliprotein), diurutkan jumlah aktivitas; aktivitas berhalaman; `ringkas_senyawa` median pChEMBL; cocok via InChIKey blok 1 (FragmentParent+Uncharger). Simpan `proyek.eksperimen` (field baru proyek) + `l["pchembl"]` -> variabel `pchembl` Statistik. Progres Kerja = Signal(int,int,str).
- **Pustaka** `core/pustaka.py` + `ui/dialog_pustaka.py`: obat (gzip TSV), COCONUT 2.0 lite CSV zip ±199 MB DIUNDUH STREAMING (zlib raw deflate + decoder UTF-8 inkremental, tidak menyimpan zip) -> SQLite `APPDATA/pustaka/coconut.sqlite`; server S3 Jena tanpa rantai sertifikat lengkap -> konteks SSL certifi (tetap terverifikasi). ZINC15/22 memakai verifikasi anti-bot -> hanya tombol buka situs (JANGAN otomatisasi). Uji parsial `unduh_coconut(maks_byte=3e6)`; hapus DB uji sesudahnya.
- **Ketcher** `ui/dialog_ketcher.py` (`paths.KETCHER`): QWebEngineView file://; API `window.ketcher` Promise -> `window._vm` lalu poll; runJavaScript mengembalikan None untuk objek -> pakai JSON.stringify. JEBAKAN: chunk `609.*.js` wajib (ChunkLoadError). Klik kanan ligan/pose › Edit struktur di Ketcher.
- **ADMET-AI** `core/admet.py` + `ui/dialog_admet.py`: proses terpisah `--admet MASUK KELUAR` (app.py; dev: PYTHONPATH=AKAR), `ADMETModel(drugbank_path=None)` (data DrugBank CC BY-NC tidak dibundel — spec `buang`), struktur dinetralkan (`sifat.netralkan`) — dulu MK1 terprotonasi +2 → HIA 0,0001 (salah). ±8–14 s; jeda GUI ≤ 73 ms. Cache `l["admet"]`.
- **Bahasa Inggris** `virmodock/i18n/__init__.py` + `en.json` (1483 teks, 291 pola): `pasang(app)` di app.main sebelum impor UI bila QSettings `bahasa`='en' — bungkus setter Qt, event Polish, subkelas item/QAction, data core (NAMA_JENIS, VARIABEL, …), `grafik.Kanvas.teks`; HTML diterjemahkan per potongan teks. Menu Tampilan › Bahasa / Language (restart). Kamus: `dev/ekstrak_teks.py` (teks baru) -> terjemahkan -> `dev/buat_kamus.py` (+ `dev/i18n_tambahan.json`). JEBAKAN: Polish QToolButton JANGAN memanggil `defaultAction()` (membuat pembungkus sementara -> QAction C++ terhapus). Logika tidak boleh membandingkan teks widget (preset ketelitian kini memakai itemData; status sematkan memakai data item). Laporan PDF/Word tetap Bahasa Indonesia.
- Spec: datas pdb2pqr/propka/admet_ai/chemprop/descriptastorus/lightning, ketcher, i18n; matplotlib tidak lagi di excludes; buang drugbank_approved.csv & padelpy/PaDEL. Uji mandiri 22/22. Uji baru: `uji_kemiripan`, `uji_wizard_reseptor`, `uji_chembl` (internet, dilewati regresi), `uji_pustaka`, `uji_ketcher`, `uji_admet`, `uji_bahasa`.

## 5. BELUM DIKERJAKAN

### Sisa Tahap 2 (tidak bisa diuji di laptop ini)
- [ ] Uji AD-GPU OpenCL di GPU AMD/Intel (relawan, E5). Jalur fallback ke Vina sudah ada.
- [x] Pilihan GPU bila ada >1 perangkat OpenCL: env hitung `devnum = (platform<<8)+perangkat+1` dari `clinfo -l`; combo data `gpu:N`, parameter job `devnum` diteruskan ke `--devnum` (Parameter.devnum).
- Catatan ilmiah: protonasi Open Babel kasar (indinavir jadi +2 pada pH 7.4). Opsi bisa dimatikan di dialog ligan. Alternatif lebih baik (Dimorphite-DL/molscrub) → cek lisensi & minta izin unduh dulu.

Uji akhir Tahap 4 (8 Okt 2026, build 0.9.0 di `rilis/`): installer dipasang diam-diam per-pengguna → uji mandiri 11/11 → uninstall bersih (tanpa shortcut/registry sisa); zip portable 11/11, data tersimpan di folder sendiri; responsif saat docking 20 ligan AD-GPU: jeda event loop terbesar 143 ms (`dev/uji_responsif.py`). Setelah v1.1 (build `dist/` saja): uji mandiri 14/14, jeda terbesar 93–100 ms. Installer/zip belum dibuat ulang.

**Tutorial PDF** (8 Okt 2026, permintaan pengguna): `docs/Tutorial_Docking_VirmoDock.pdf` (21 halaman A4) dari `docs/_sumber/tutorial.html` lewat `dev/buat_tutorial_pdf.py` (Chromium Qt `printToPdf`, tanpa paket baru); alur impor → reseptor → grid → validasi → ligan → docking → hasil → interaksi/2D → bandingkan → ekspor → laporan; contoh 1HSG/MK1. Tangkapan tambahan `dev/buat_screenshot_tutorial.py`. Menu Help › Tutorial docking (PDF); ikut dibuat ulang di `build_tools/rilis.py`.

**Logo resmi** (8 Okt 2026, permintaan pengguna): folder `branding/` (SVG vektor + PNG + `virmodock.ico` + `virmodock_panduan_logo.png`), dibuat oleh `build_tools/logo/produksi.py` (geometri dihitung; wordmark Bahnschrift SemiBold diubah jadi kurva + `simplified()`). Konsep: V = kantong pengikatan yang sisi dalamnya mengikuti setengah bawah heksagon-ligan (celah seragam). Warna: navy #173B6C, biru ligan #2B6FD6, biru terang #5B9AF0 (latar gelap), abu tagline #5B6B82. Ikon aplikasi `virmodock/aset/` kini dari logo ini (`dev/buat_ikon.py` menyalin dari branding). Catatan: Bahnschrift adalah font Microsoft — sebelum mendaftarkan merek dagang, periksa lisensinya atau ganti ke font OFL.

### Sisa sebelum v1.0 (butuh orang/perangkat lain)
- [ ] Uji relawan E5 (Intel iGPU, AMD, tanpa GPU; Windows 10 & 11; akun tanpa Python) memakai `docs/` + Tools › Uji mandiri.
- [ ] Repo GitHub publik + rilis kode sumber (termasuk `vendor/adgpu_src` yang dimodifikasi), Zenodo DOI, pemeriksaan pembaruan (B3). **Repo git lokal sudah siap** (8 Okt 2026: `git init`, `.gitignore`, `README.md`, `requirements.txt`, commit awal `05b88f8`; identitas commit noreply akun `rizkirahmadip-dev`). Belum di-push; pekerjaan v1.1 belum di-commit. Tidak ikut repo: `.venv`, build/dist/rilis, keluaran `dev/uji`, Inno Setup, OpenCL SDK, `adgpu_src/input` (data uji upstream), PDF tutorial (dibuat ulang).
- [ ] Tanda tangan kode gratis (SignPath Foundation) agar SmartScreen tidak memperingatkan.
- [x] Pemegang hak cipta: **apt. Rizki Rahmadi Pratama, M. Farm** (LICENSE, LISENSI_PIHAK_KETIGA, `AppPublisher` installer, dialog Tentang). Installer/zip 0.9.0 di `rilis/` dibuat sebelum ini — build ulang agar ikut.

## 6. Cara menjalankan & menguji
- Jalankan: `VirmoDock\Jalankan VirmoDock (dev).bat` atau `cd VirmoDock && .venv\Scripts\python.exe -m virmodock`.
- Uji visual otomatis (impor 1HSG, simpan tangkapan JENDELA SAJA):
  `cd VirmoDock && VD_SHOT=dev/shot.png PYTHONPATH=. .venv/Scripts/python.exe dev/uji_layar.py` (env: `VD_TEMA=gelap`, `VD_PDB=1ITB`, `VD_WAIT=14000`). Mencetak isi Log (termasuk galat JS `[viewer] ...`).
- Uji Tahap 2 (lihat docstring masing-masing): `dev/uji_prep.py 1HSG 1ITB 3KS3` (reseptor), `dev/uji_lig.py`, `dev/uji_mesin.py adgpu vina ad4`, `dev/uji_antrean.py` (tanpa GUI), `dev/uji_alur.py` (GUI alur penuh → `dev/alur*.png`, folder kerja uji `dev/uji/kerja`), `dev/uji_kontrol.py` (geser kotak, batal, jeda/lanjut, tema gelap), `dev/uji_pubchem.py`, `dev/uji_dialog.py`. Tahap 3: `dev/uji_interaksi.py`, `dev/uji_diagram.py`, `dev/uji_ekspor.py`, `dev/uji_tahap3.py` (GUI: analisis, diagram, semua ekspor, validasi, bandingkan, laporan → `dev/uji/ekspor/`), `dev/uji_protonasi.py`, `dev/uji_gelap3.py`. Tahap 4: `dev/uji_responsif.py` (jeda event loop saat docking 20 ligan), `--uji-mandiri`. v1.1: `dev/uji_sifat.py`, `dev/uji_sifat_gui.py` (membuat `dev/uji/sifat/proyek_uji.vmd`), `dev/uji_statistik.py`, `dev/uji_statistik_gui.py`, `dev/uji_qc.py` (butuh proyek dari `uji_statistik_gui`), `dev/uji_qc_antrean.py`, `dev/uji_qc_gui.py`. Jalankan dengan `PYTHONIOENCODING=utf-8 PYTHONPATH=.`.
- Build exe saja (tanpa installer): `.venv/Scripts/python.exe -m PyInstaller build_tools/virmodock.spec --noconfirm --distpath dist --workpath build --log-level WARN`, lalu `dist/VirmoDock/VirmoDock.exe --uji-mandiri hasil.json`. Rilis lengkap: `build_tools/rilis.py`.
- Reset pengaturan: `QSettings("VirmoDock","VirmoDock")` kunci `layout`, `geometri`, `wizard_selesai`, `tema`, `folder_kerja`, `eksternal`.

## 7. Jebakan yang sudah ditemui (jangan diulang)
- **Privasi:** JANGAN tangkap layar dengan `QScreen.grabWindow` — merekam jendela pribadi pengguna. Pakai `widget.grab()` (sudah dipakai di `dev\uji_layar.py`).
- 3Dmol: `addStyle` hanya ada di **viewer**, bukan di model → `this.v.addStyle({model: o.m, ...sel}, style)`. Seleksi `within` lintas model juga harus lewat viewer.
- PDB tanpa kolom elemen (mis. 1ITB lama) membuat Meeko/RDKit error "Element '' not found" → selalu bersihkan/tulis ulang dengan gemmi dulu.
- Ligan PDBQT (ada `ROOT`) dibaca via Open Babel → SDF → RDKit (sudah di `molekul.impor_berkas`).
- `libomp140.x86_64.dll` (OpenMP LLVM) TIDAK boleh diredistribusi → vcxproj sudah diubah: hapus `/openmp:llvm`, `OpenMPSupport=false`; hasil bergantung `vcomp140.dll` (boleh). Build: MSBuild VS 2026 BuildTools `/p:PlatformToolset=v145 /p:Configuration=Release /p:Platform=x64`; header kernel dibuat dengan `stringify_ocl_krnls.sh` (sudah ada di `host\inc\stringify.h`).
- PySide6 `setChecked()` menolak `None` → selalu `bool(...)`.
- `QDockWidget` ukuran awal: panggil `resizeDocks` lewat `QTimer.singleShot(0, ...)`; layout tersimpan dari uji sebelumnya bisa menimpa — hapus kunci `layout` saat uji.
- Kerja latar: simpan referensi `Kerja` sampai selesai (`kerja._aktif`), `setAutoDelete(False)`.

- ID job harus unik walau dibuat pada detik yang sama (`Proyek.job_baru_id` menambah akhiran `_2`).
- AD-GPU: kolom "Evaluations" adalah per run (bukan total); batas sebenarnya dibaca dari baris "or N evaluations". AutoStop sering berhenti < 100 %.
- Folder proyek harus jalur absolut (`Path.resolve()`) karena QProcess memakai cwd berbeda.
- AD4 tidak tahan spasi di jalur DPF → map dirujuk relatif `../../grid/`.
- Wheel openbabel menunjuk BABEL_DATADIR ke folder kosong → `app.siapkan_kimia()` mengarahkannya ke `openbabel/bin/data`.
- Ligan "asli" bisa berupa aditif kristal (GOL di 3KS3) → selalu saring dengan `molekul.ADITIF`.
- **Redocking: jangan minimisasi ligan kristal** — MMFF mengubah konformasi cincin (kaku saat docking); MK1 AD-GPU 3,9 Å → 1,2–1,5 Å tanpa minimisasi (diuji 3 seed).
- WebGL tidak merender benar saat tab viewport tersembunyi → `_ekspor_gambar3d` menampilkan tab Viewport dulu; ukuran akhir dipastikan oleh Pillow.
- QtSvg tidak mendukung `paint-order` → latar label pakai `<rect>`.
- Pose objek dari versi lama (tanpa `info["pdbqt"]`) dibuat ulang otomatis di `buka_pose`.
- Bash heredoc di tool ini mengubah `\\n` menjadi baris baru sungguhan → skrip Python berisi backslash ditulis dengan Write, bukan heredoc.
- Inno Setup: pesan `NameAndVersion`, `CreateDesktopIcon`, `AssocFileExtension`, dll. adalah **[CustomMessages]**, bukan [Messages].
- Bash heredoc besar di tool ini bisa gagal; tulis skrip ke scratchpad dengan Write lalu jalankan.
- Widget di `QToolBar` disembunyikan lewat QAction hasil `addWidget`, bukan `widget.setVisible`.
- Teks seperti "< 0,001" di rich text Qt harus di-`escape`, kalau tidak terbaca sebagai tag.
- Pekerjaan berat RDKit di thread tetap memegang GIL (GUI tersendat) → pakai proses pekerja (`core/qc.py`). Jangan ProcessPoolExecutor/spawn: mengimpor ulang skrip `__main__`.
- `__main__.py` wajib ber-guard `if __name__ == "__main__"`.
- 3Dmol `zoomTo({})` menghitung SEMUA model termasuk yang tersembunyi → selalu pakai `VM._terlihat()` untuk memusatkan.
- 3Dmol: **jangan** `zoomTo({model: [m1, m2]})` (daftar) — macet tanpa akhir & membekukan halaman. Pakai `{or: [{model: m1}, {model: m2}]}`. Gejala halaman JS beku: `runJavaScript` tak pernah memanggil callback.

- 3Dmol: bentuk (addSphere/addCylinder) dengan alpha/opacity < 1 TIDAK tergambar sama sekali di setup ini (bukan fog). Pakai warna buram atau `wireframe: true` (sudah diterapkan).
- Instrumentasi JS (membungkus VM.*) dengan `JSON.stringify(fungsi).slice` melempar galat dan mematahkan alur -> bungkus `String(...)`.

## 8. Lingkungan laptop pengguna
Windows 10, Ryzen 7 5800H, 16 GB RAM, RTX 3060 Laptop 6 GB (driver 610.74), Python 3.14 (C:\Python314), VS 2026 Build Tools, Git, WSL Ubuntu (AutoDock-GPU CUDA lama di ~/AutoDock-GPU — tidak dipakai lagi oleh VirmoDock), MGLTools 1.5.6/1.5.7, Open Babel 2.4.1, Discovery Studio Visualizer 2021. Data docking lama: `D:\16. Data Penelitian Tambahan\Semua Data Docking` (contoh uji: `1ITBCasticin\` berisi maps + Casticin.pdbqt + dock.dlg).
