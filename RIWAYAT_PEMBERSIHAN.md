# Riwayat pembersihan folder (10 Oktober 2026)

Folder besar di dalam `VirmoLab` dihapus karena hanya hasil generate. Aplikasi pengembangan tidak membaca folder itu.

Yang menjalankan aplikasi tetap `Jalankan VirmoLab (dev).bat`: kode sumber, `.venv`, dan `vendor`. Tiga itu tidak dihapus.

Kode pada saat pembersihan: commit `47ca59c` (VirmoLab 0.9.5) di cabang `main`, hanya lokal.

## Yang dihapus

| Folder | Perkiraan | Isi | Cara kembali |
|---|---|---|---|
| `rilis` | 2,2 GB | Installer dan portable 0.9.3 serta 0.9.4 | `.venv\Scripts\python.exe build_tools\rilis.py` |
| `dist` | 1,6 GB | Hasil PyInstaller (aplikasi beku) | Terbentuk lagi saat build yang sama |
| `build` | 209 MB | Sisa antara PyInstaller | Terbentuk lagi saat build |
| `dev\uji` | 1,5 GB | Tangkapan layar, proyek uji `.vmd`, log docking, grid, trajektori | Skrip `dev\uji_*.py` menulis ulang ke sana saat dijalankan |

Build installer **0.9.5 belum pernah dibuat**. Yang hilang dari `rilis` hanya paket 0.9.3 dan 0.9.4.

Checksum paket yang dihapus (berkas `SHA256SUMS-0.9.3.txt` dan `SHA256SUMS-0.9.4.txt`):

```
94e3742ca0a6724bba78a3f00204cd886116f61250c5d9feb92a3b52c094fc0d  VirmoLab-Setup-0.9.3.exe
6903ec6e9f5b5501ccb5fb1dfbd28744dc50f40c17330a922e10071764c5d66b  VirmoLab-Portable-0.9.3.zip
642830ed7bb7e85cf323e7771e1ddfa1389c23d8f170e9e75c0f1d9530dd41bb  VirmoLab-Setup-0.9.4.exe
fc89728f5deca49c076557e6b65648d9ab8cc16c3c5898368d699c2278a5a71b  VirmoLab-Portable-0.9.4.zip
```

Rilis 0.9.0–0.9.2 sudah dipindah ke Recycle Bin pada 9 Oktober 2026 (sekitar 2,5 GB), sebelum pembersihan ini.

## Yang sengaja disisakan di `dev\uji`

Hanya masukan kecil yang dibaca skrip uji, bukan keluaran:

- `1HSG.pdb`, `1ITB.pdb`, `3HS4.pdb`, `3KS3.pdb`
- `MK1.sdf`, `MK1.pdbqt`, `aspirin.pdbqt`
- `kovalen\6OIM.pdb` dan `kovalen\eksperimen.py`

`eksperimen.py` tidak ikut Git (seluruh `dev/uji/` ada di `.gitignore`). Itu skrip validasi docking kovalen 6OIM (KRAS G12C–sotorasib, Cys12): konformer awal 21 Å dari kristal, pose peringkat 1 RMSD **1,11 Å**. Lewat alur aplikasi (SMILES, ETKDG+MMFF) catatannya **1,34 Å**. Berkas grid, DLG, dan PDBQT hasil eksperimen ikut terhapus; struktur 6OIM dan skripnya tetap.

Plugin percobaan di `dev\uji\v095\plugin\` tidak disimpan. `dev\uji_konsol_plugin.py` menulis ulang berkas itu sendiri setiap kali dijalankan.

Log regresi lengkap disalin ke `dev\riwayat\` sebelum folder uji dibersihkan:

- `regresi_ringkas.txt` — 40/40 lulus (rangkaian lebih awal).
- `regresi_093.txt` — ada satu gagal: `uji_cli` (pesan: area docking belum ditentukan lewat `--pusat`, `--acuan`, atau `--kantong`).
- `regresi_094.txt` — 48/49 lulus; yang gagal: `uji_md_gui`.

Uji 0.9.5 yang dicatat di `CATATAN_TAHAP2.md` §4m, bukan di tiga log itu: GUI `dev\uji_095_gui.py` 15/15, konsol dan plugin 9/9, RCSB 3/3, docking kovalen GUI `dev\uji_kovalen.py` 20/20.

## Kalau nanti terasa seperti bug

Jendela aplikasi yang dibuka dari `Jalankan VirmoLab (dev).bat` tidak bergantung pada `rilis`, `dist`, `build`, atau keluaran `dev\uji`. Hilangnya folder itu bukan penyebab docking, viewer, atau menu rusak.

Yang memang membuat aplikasi tidak jalan:

- `.venv` hilang atau rusak — Python pengembangan tidak ada.
- `vendor` hilang — `autodock_gpu.exe`, `vina.exe`, Open Babel, P2Rank, atau Java tidak ketemu.

Kalau yang gagal skrip di `dev\uji_*.py`, biasanya karena proyek contoh `.vmd` ikut terhapus. Skrip itu sering membuka hasil uji sebelumnya, misalnya `dev\uji\kerja\*.vmd` atau `dev\uji\kerja_docs\*.vmd`. Jalankan ulang skrip yang membuat proyek itu (seringnya `dev\uji_alur.py` untuk `kerja`, lalu skrip GUI yang lebih hilir). Struktur PDB yang disisakan di atas cukup untuk memulai rantai itu.

`dev\uji_kovalen.py` masih mengarah ke `dev\uji\kovalen\6OIM.pdb` dan `dev\uji\aspirin.pdbqt`. Kedua berkas itu ada.
