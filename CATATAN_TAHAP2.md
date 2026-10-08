# VirmoDock — Catatan Serah-Terima (per 8 Okt 2026)

Untuk sesi baru: baca seluruh file ini dulu. Pengguna berbahasa Indonesia; UI dan pesan aplikasi berbahasa Indonesia.

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
- Packaging: PyInstaller (sudah terpasang di venv); installer: **Inno Setup 6** (belum diunduh; izin unduh sudah diberikan pengguna).
- Pengguna sudah mengizinkan unduhan: PySide6, rdkit, meeko, openbabel-wheel, nuitka/pyinstaller, Vina, OpenCL SDK, Inno Setup.

## 3. Struktur folder
```
E:\Bikin Docking Simpel\
  DockingSimpel.exe, app\        ← aplikasi LAMA (web UI + WSL). Masih jalan, bug GPU sudah diperbaiki.
  mockup\                        ← mockup yang disetujui
  VirmoDock\
    .venv\                       ← Python 3.14 venv (semua dependensi)
    Jalankan VirmoDock (dev).bat ← jalankan versi pengembangan
    virmodock\
      app.py, __main__.py        ← titik masuk (python -m virmodock)
      core\paths.py              ← lokasi bin/viewer/appdata (%LOCALAPPDATA%\VirmoDock)
      core\env.py                ← deteksi GPU (WMI + nvidia-smi + clinfo), CPU/RAM, PyMOL/ChimeraX/DSV, panduan driver
      core\molekul.py            ← Objek, impor PDB/PDBQT/CIF/SDF/MOL2/SMILES, RCSB, PubChem, gaya_bawaan, spek_viewer
      ui\theme.py                ← token warna terang/gelap + QSS
      ui\icons.py                ← ikon Lucide (SVG → QIcon berwarna)
      ui\kerja.py                ← pekerja QThreadPool (Kerja/jalankan)
      ui\viewer_widget.py        ← Viewer(QWebEngineView), Jembatan QWebChannel, log console JS
      ui\panels.py               ← PanelHierarki, PanelProperti, PanelTampilan (ala PyMOL), PanelLog, PanelAntrean
      ui\dialogs.py              ← DialogAmbil (RCSB/PubChem/SMILES), Wizard pertama kali
      ui\mainwindow.py           ← JendelaUtama: menu, toolbar, dock, aksi, impor, grid box dasar
      viewer\viewer.html, viewer.js, 3Dmol-min.js  ← API JS "VM.*"
    vendor\bin\                  ← autodock_gpu.exe, vina.exe, autogrid4.exe, autodock4.exe, clinfo.exe, OpenCL.dll, vcomp140.dll
    vendor\adgpu_src\            ← source AutoDock-GPU + vcxproj yang sudah dimodifikasi
    vendor\opencl\               ← Khronos OpenCL SDK
    dev\uji_layar.py             ← uji visual otomatis (lihat §6)
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
`ui/dialog_reseptor.py`, `ui/dialog_ligan.py`, `ui/panel_docking.py`, `ui/panel_antrean.py` (PanelAntrean + PanelHasil).
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
Tile rendering > 8192 px, salin ke clipboard, skrip PyMOL/ChimeraX, laporan Word/HTML interaktif, komposer figur, animasi, sematkan pose, ProLIF/PoseBusters.

## 4d. SUDAH SELESAI (Tahap 4, 8 Okt 2026)
Versi: `virmodock/__init__.py` `__version__ = "0.9.0"` (pra-rilis; jadi 1.0 setelah uji relawan E5).
- [x] **Lisensi (B2)**: VirmoDock **GPL-3.0-or-later** (`LICENSE`, disetujui pengguna). **Open Babel kini program terpisah** (`core/obabel.py` → `bin/openbabel/obabel.exe`, dari wheel + `msvcp140.dll`); tidak ada lagi `import openbabel`/`pybel` di proses Python. `LISENSI_PIHAK_KETIGA.txt` + folder `licenses/` (teks resmi; GPL-3/LGPL-3 dari gnu.org, Vina/3Dmol/Lucide dari GitHub — izin pengguna) + tawaran kode sumber GPL (AD-GPU, AD4, Open Babel). Help › Lisensi & cara mengutip.
- [x] **Ikon** `virmodock/aset/virmodock.ico` (16–256 px, logo garis putih di kotak aksen biru; `dev/buat_ikon.py`).
- [x] **Mode portable**: `portable.flag` di samping exe → pengaturan `data/pengaturan.ini`, log `data/log`, proyek `Proyek/`. Pengaturan selalu lewat `paths.settings()`.
- [x] **Log berkas** `core/catat.py` (rotasi 10 × 1 MB, excepthook). Panel Log/Pesan ikut ditulis.
- [x] **Pindah laptop** `core/pindah.py`: File › Pindah laptop › Ekspor/Impor `.vmdbackup` (zip: pengaturan JSON termasuk layout biner, proyek opsional; jalur yang tak ada diabaikan + dicatat; GPU dideteksi ulang). Teruji bolak-balik.
- [x] **Jendela & DPI**: ukuran awal mengikuti layar, geometri di monitor yang hilang → dipusatkan. Diuji 100 % (1366×768), 150 % (asli), 200 % (`QT_SCALE_FACTOR`).
- [x] **Help**: Panduan (F1) & Dokumentasi (HTML offline di `docs/`), Lapor masalah (teks + info sistem + log, pengguna menyalin sendiri — tidak ada pengiriman otomatis), Buka folder log, Lisensi & sitasi, Tools › Uji mandiri komponen.
- [x] **Uji mandiri** `core/ujimandiri.py` + `VirmoDock.exe --uji-mandiri hasil.json` (11 uji: 4 mesin, obabel, RDKit+Meeko, gemmi, fitur kimia, docking Vina mini, GPU, openpyxl). Argumen lain: `--disable-gpu`, berkas/folder `.vmd`/`.vmdbackup` dari Explorer, `VD_TANGKAP` (uji: simpan grab jendela lalu keluar).
- [x] **Dokumentasi** `docs/` (sumber `docs/_sumber/*.html` → `dev/buat_docs.py`): panduan pengguna, instalasi, pindah laptop, setup GPU, troubleshooting, metode & kriteria; 15 tangkapan (`dev/buat_screenshot.py`).
- [x] **PyInstaller onedir** `build_tools/virmodock.spec` (titik masuk `VirmoDock.pyw`; Qt debug pak/devtools/qml/terjemahan non-ID dibuang) → **579 MB**, start ± 2–3 s; exe beku lulus uji mandiri & GUI (WebGL, impor, GPU).
- [x] **Installer** Inno Setup 6.7.3 (dipasang di `vendor/innosetup`, izin pengguna; tanda tangan valid) — `installer/virmodock.iss` + `installer/Indonesian.isl` (terjemahan sendiri; pesan jarang → Inggris). Per-pengguna tanpa admin (bisa pilih semua pengguna), shortcut Start/Desktop, asosiasi `.vmdbackup` (bawaan) & `.pdbqt` (opsional), uninstaller.
- [x] **Rilis satu perintah**: `.venv\Scripts\python.exe build_tools\rilis.py` → docs → build → uji mandiri (gagal = berhenti) → `rilis/VirmoDock-Setup-x.y.z.exe`, `rilis/VirmoDock-Portable-x.y.z.zip`, `SHA256SUMS`.

## 5. BELUM DIKERJAKAN

### Sisa Tahap 2 (tidak bisa diuji di laptop ini)
- [ ] Uji AD-GPU OpenCL di GPU AMD/Intel (relawan, E5). Jalur fallback ke Vina sudah ada.
- [ ] Pilihan GPU bila ada >1 perangkat OpenCL (saat ini perangkat pertama; `perintah_adgpu(devnum=)` sudah siap).
- Catatan ilmiah: protonasi Open Babel kasar (indinavir jadi +2 pada pH 7.4). Opsi bisa dimatikan di dialog ligan. Alternatif lebih baik (Dimorphite-DL/molscrub) → cek lisensi & minta izin unduh dulu.

Uji akhir 8 Okt 2026: installer dipasang diam-diam per-pengguna → uji mandiri 11/11 → uninstall bersih (tanpa shortcut/registry sisa); zip portable 11/11, data tersimpan di folder sendiri; responsif saat docking 20 ligan AD-GPU: jeda event loop terbesar 143 ms (`dev/uji_responsif.py`).

**Tutorial PDF** (8 Okt 2026, permintaan pengguna): `docs/Tutorial_Docking_VirmoDock.pdf` (21 halaman A4) dari `docs/_sumber/tutorial.html` lewat `dev/buat_tutorial_pdf.py` (Chromium Qt `printToPdf`, tanpa paket baru); alur impor → reseptor → grid → validasi → ligan → docking → hasil → interaksi/2D → bandingkan → ekspor → laporan; contoh 1HSG/MK1. Tangkapan tambahan `dev/buat_screenshot_tutorial.py`. Menu Help › Tutorial docking (PDF); ikut dibuat ulang di `build_tools/rilis.py`.

**Logo resmi** (8 Okt 2026, permintaan pengguna): folder `branding/` (SVG vektor + PNG + `virmodock.ico` + `virmodock_panduan_logo.png`), dibuat oleh `build_tools/logo/produksi.py` (geometri dihitung; wordmark Bahnschrift SemiBold diubah jadi kurva + `simplified()`). Konsep: V = kantong pengikatan yang sisi dalamnya mengikuti setengah bawah heksagon-ligan (celah seragam). Warna: navy #173B6C, biru ligan #2B6FD6, biru terang #5B9AF0 (latar gelap), abu tagline #5B6B82. Ikon aplikasi `virmodock/aset/` kini dari logo ini (`dev/buat_ikon.py` menyalin dari branding). Catatan: Bahnschrift adalah font Microsoft — sebelum mendaftarkan merek dagang, periksa lisensinya atau ganti ke font OFL.

### Sisa sebelum v1.0 (butuh orang/perangkat lain)
- [ ] Uji relawan E5 (Intel iGPU, AMD, tanpa GPU; Windows 10 & 11; akun tanpa Python) memakai `docs/` + Tools › Uji mandiri.
- [ ] Repo GitHub publik + rilis kode sumber — **repo git lokal sudah siap** (8 Okt 2026: `git init`, `.gitignore`, `README.md`, `requirements.txt`, commit awal; identitas commit noreply akun `rizkirahmadip-dev`). Belum di-push. Tidak ikut repo: `.venv`, build/dist/rilis, keluaran `dev/uji`, Inno Setup, OpenCL SDK, `adgpu_src/input` (data uji upstream), PDF tutorial (dibuat ulang). (termasuk `vendor/adgpu_src` yang dimodifikasi), Zenodo DOI, pemeriksaan pembaruan (B3).
- [ ] Tanda tangan kode gratis (SignPath Foundation) agar SmartScreen tidak memperingatkan.
- [x] Pemegang hak cipta: **apt. Rizki Rahmadi Pratama, M. Farm** (LICENSE, LISENSI_PIHAK_KETIGA, `AppPublisher` installer, dialog Tentang). Installer/zip 0.9.0 di `rilis/` dibuat sebelum ini — build ulang agar ikut.

## 6. Cara menjalankan & menguji
- Jalankan: `VirmoDock\Jalankan VirmoDock (dev).bat` atau `cd VirmoDock && .venv\Scripts\python.exe -m virmodock`.
- Uji visual otomatis (impor 1HSG, simpan tangkapan JENDELA SAJA):
  `cd VirmoDock && VD_SHOT=dev/shot.png PYTHONPATH=. .venv/Scripts/python.exe dev/uji_layar.py` (env: `VD_TEMA=gelap`, `VD_PDB=1ITB`, `VD_WAIT=14000`). Mencetak isi Log (termasuk galat JS `[viewer] ...`).
- Uji Tahap 2 (lihat docstring masing-masing): `dev/uji_prep.py 1HSG 1ITB 3KS3` (reseptor), `dev/uji_lig.py`, `dev/uji_mesin.py adgpu vina ad4`, `dev/uji_antrean.py` (tanpa GUI), `dev/uji_alur.py` (GUI alur penuh → `dev/alur*.png`, folder kerja uji `dev/uji/kerja`), `dev/uji_kontrol.py` (geser kotak, batal, jeda/lanjut, tema gelap), `dev/uji_pubchem.py`, `dev/uji_dialog.py`. Tahap 3: `dev/uji_interaksi.py`, `dev/uji_diagram.py`, `dev/uji_ekspor.py`, `dev/uji_tahap3.py` (GUI: analisis, diagram, semua ekspor, validasi, bandingkan, laporan → `dev/uji/ekspor/`), `dev/uji_protonasi.py`, `dev/uji_gelap3.py`. Jalankan dengan `PYTHONIOENCODING=utf-8 PYTHONPATH=.`.
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

## 8. Lingkungan laptop pengguna
Windows 10, Ryzen 7 5800H, 16 GB RAM, RTX 3060 Laptop 6 GB (driver 610.74), Python 3.14 (C:\Python314), VS 2026 Build Tools, Git, WSL Ubuntu (AutoDock-GPU CUDA lama di ~/AutoDock-GPU — tidak dipakai lagi oleh VirmoDock), MGLTools 1.5.6/1.5.7, Open Babel 2.4.1, Discovery Studio Visualizer 2021. Data docking lama: `D:\16. Data Penelitian Tambahan\Semua Data Docking` (contoh uji: `1ITBCasticin\` berisi maps + Casticin.pdbqt + dock.dlg).
