# Rencana rilis VirmoLab 1.8.0 — rilis publik pertama

Disusun 25 Okt 2026. Dokumen ini adalah satu-satunya acuan untuk sesi-sesi berikutnya sampai 1.8.0 dirilis.
Kerjakan berurutan; tiap bagian punya **gerbang** yang wajib lulus sebelum lanjut. Jangan menyatakan selesai dari
uji yang lulus saja: lihat tangkapan layar, buka berkasnya, cek angkanya (pelajaran 13–25 Okt).

---

## 0. Ringkasan

**Apa yang dirilis.** VirmoLab 1.8.0 untuk Windows 10/11 64-bit: installer dan portable, pertama kali dapat diunduh
publik, dengan pemasang alat lanjutan (WSL) di dalam aplikasi, kriteria keyakinan penargetan balik yang sahih, dan
saluran pembaruan yang benar-benar bekerja.

**"Rilis tahap akhir" berarti seluruh butir ini benar:**
1. Orang lain bisa mengunduh, memeriksa SHA-256, memasang, dan menjalankan docking pertama tanpa bantuan.
2. Fitur yang butuh alat tambahan menunjukkan cara memasangnya dari dalam aplikasi (tidak ada pesan buntu).
3. Tidak ada keluaran ilmiah yang dikenal salah atau menyesatkan di versi ini.
4. Diuji di sedikitnya dua laptop selain laptop pengembang, termasuk satu tanpa GPU NVIDIA.
5. Kewajiban lisensi terpenuhi (GPL: kode sumber yang sesuai tersedia).
6. Aplikasi lama (1.7.0) mendeteksi rilis baru lewat cek pembaruan.
7. Ada cara mengutip perangkat lunak (CITATION, idealnya DOI).

**Perkiraan waktu.** Hari 1–2 kerja aktif (±10–12 jam), hari 3–9 uji beta oleh penguji (menunggu), hari 10 rilis.
Butir berjangka panjang (sertifikat, penguji, keputusan repo publik) **dimulai hari 1**.

---

## 1. Kondisi sekarang (25 Okt 2026)

| Hal | Status |
|---|---|
| Versi kode | 1.7.0, di-push (`14f1029`); `main` = `origin/main` |
| Build | `rilis/VirmoLab-Setup-1.7.0.exe` 505,2 MB, Portable 724,6 MB; uji mandiri **57/57** di folder biasa, folder non-ASCII, dan aplikasi terpasang |
| Uji pemasangan | portable PATH minimal, folder `VirmoLab Rizkí`, tiruan tanpa OpenCL, installer per-pengguna tanpa admin, uninstall bersih — semua lulus (lihat memori `virmolab-uji-pemasangan`) |
| Regresi | 117/120 penuh; 3 sisanya masalah uji, lulus setelah diperbaiki |
| Program inti | dibundel (AutoDock4, AutoGrid4, AutoDock-GPU, Vina, Open Babel, P2Rank + Java, xtb, RDKit, Meeko, OpenMM, PoseBusters) |
| Alat WSL (Uni-Dock, OpenFE, GNINA, Boltz) | **tidak dibundel; 6 pesan aplikasi menunjuk `build_tools/pasang_*.sh` yang tidak ikut installer** |
| Penargetan balik | **kriteria keyakinan masih "10 besar kedua jalur"**, tidak bermakna pada panel kecil (Artikel 1) |
| Repo | `rizkirahmadip-dev/virmolab` **privat**; cek pembaruan menunjuk ke sana → di aplikasi pengguna selalu "belum ada rilis" |
| Tanda tangan kode | jalur siap (`build_tools/tanda_tangan.ps1`, `--wajib-tanda-tangan`), **sertifikat belum ada** |
| Lisensi pihak ketiga | `LISENSI_PIHAK_KETIGA.txt` + folder `licenses/` lengkap; tawaran kode sumber GPL menyebut "rilis kode sumber VirmoLab" yang belum ada secara publik |
| Rahasia di repo | pemindaian cepat: tidak ada kunci/token; berkas terbesar xtb.exe 59 MB (di bawah batas 100 MB) |
| `CITATION.cff` | `url: https://virmolab.org` — kepemilikan domain belum jelas |

---

## 2. Keputusan yang dibutuhkan (tanyakan di awal sesi pertama)

| # | Keputusan | Pilihan | Usulan | Kenapa |
|---|---|---|---|---|
| K1 | Nomor versi | 1.8.0 / 1.7.1 | **1.8.0** | ada fitur baru (dialog pemasang) dan perubahan perilaku ilmiah |
| K2 | Saluran rilis | (a) repo utama dijadikan publik, (b) repo publik khusus rilis `virmolab-rilis`, (c) tetap privat | **(a) publik** | GPL-3.0 mewajibkan kode sumber tersedia bagi penerima biner; repo publik juga syarat DOI Zenodo dan SignPath gratis. (b) sah bila ingin kode tetap privat, tetapi tawaran kode sumber tertulis harus dilayani 3 tahun |
| K3 | Tanda tangan kode | Certum OSS (berbayar, ±€25–69/th, verifikasi identitas beberapa hari–minggu) / SignPath Foundation (gratis, butuh repo publik + build CI GitHub Actions) / tanpa tanda tangan dulu | **Rilis 1.8.0 tanpa tanda tangan + pesan Certum sekarang; tandatangani mulai 1.8.1** | sertifikat makan waktu; SmartScreen sudah dijelaskan di panduan instalasi |
| K4 | WSL belum ada di laptop pengguna | tombol pasang lewat UAC / hanya tampilkan perintah | **Tombol UAC**, lalu instruksi restart dan buka Ubuntu sekali | pengguna tetap menyetujui di jendela Windows |
| K5 | Laptop tanpa GPU NVIDIA | izinkan OpenFE & Boltz di CPU dengan peringatan / matikan semua | **Izinkan dengan peringatan "sangat lambat"**; Uni-Dock & GNINA dimatikan | tetap berguna untuk uji kecil |
| K6 | Uji pemasangan WSL dari nol di distro terpisah | ya / tidak | **Ya, di latar** | satu-satunya bukti pemasang bekerja di laptop orang lain |
| K7 | Kriteria keyakinan penargetan balik | perbaiki sebelum rilis / sembunyikan label & tandai eksperimental / biarkan | **Perbaiki sebelum rilis**; pendekatannya dibahas di awal Bagian B | label "tinggi" yang tidak bermakna adalah keluaran ilmiah menyesatkan |
| K8 | DOI dan publikasi | Zenodo saat rilis / nanti; makalah perangkat lunak (SoftwareX, JOSS) | **Zenodo saat rilis** (butuh K2=a) | penelitian yang memakai VirmoLab bisa mengutip versi persis |
| K9 | Penguji beta | 2–3 orang dengan laptop berbeda | **minta hari 1**: satu Windows 11, satu tanpa GPU NVIDIA (Intel/AMD), satu RAM 8 GB / layar 1366×768 | konfigurasi yang tidak bisa ditiru di laptop pengembang |
| K10 | Domain `virmolab.org` di CITATION | beli / hapus dari CITATION | **hapus** kecuali sudah dimiliki | jangan menunjuk domain milik orang lain |

**Diputuskan pengguna 25 Okt 2026:** K1 = 1.8.0 · K2 = repo utama dijadikan publik (setelah audit C1; tindakan
membuka repo tetap dikonfirmasi saat dijalankan) · K3 = rilis tanpa tanda tangan, pengguna memesan Certum OSS · K4 =
tombol pasang WSL lewat UAC · K5 = OpenFE & Boltz boleh di CPU dengan peringatan, Uni-Dock & GNINA dimatikan tanpa
NVIDIA · K6 = uji dari nol di distro terpisah, ya · K7 = perbaiki sebelum rilis · K8 = DOI Zenodo saat rilis · K9 =
**belum ada penguji**: rilis dengan catatan "diuji di 1 laptop pengembang + tiruan (folder non-ASCII, tanpa OpenCL,
distro WSL bersih)", pengumuman luas ditunda sampai ada laporan pengguna · K10 = `url` virmolab.org dihapus.

---

## 3. Jalur kerja

### A. Pemasang alat lanjutan (WSL) di dalam aplikasi

Masalah: empat alat Linux + CUDA tidak dibundel (±23 GB), dan pesannya menunjuk skrip yang tidak ikut installer.

| Alat | Fitur | Skrip | Ukuran |
|---|---|---|---|
| Uni-Dock 1.2 | docking batch GPU | `pasang_openfe_unidock_wsl.sh` | ±14 GB bersama OpenFE |
| OpenFE 1.13 | RBFE | (sama) | |
| GNINA 1.3.3 | skor ulang CNN | `pasang_gnina_boltz_wsl.sh` | ±2 GB |
| Boltz-2 2.2.1 | co-folding, peptida | `pasang_gnina_boltz_wsl.sh` + `unduh_bobot_boltz.py` | ±7 GB + bobot |

Pesan buntu yang diganti: `core/lanjutan.py:62` (GNINA), `:73` (Boltz), `core/rbfe_openfe.py:114`, `core/unidock.py:42`,
`ui/mainwindow.py:3000`, `ui/panel_docking.py:548`; docstring `rbfe_openfe.py:4`, `unidock.py:5`.

**A1. Skrip ikut installer (±30 mnt).** `virmolab.spec` → `datas` ke `virmolab/alat_wsl/`; `paths.ALAT_WSL`; LF
dijaga `.gitattributes`. Uji mandiri butir "Skrip alat WSL": berkas ada, tanpa `\r\n`, `bash -n` lolos bila WSL ada.

**A2. Modul `core/alat_wsl.py` (±1,5 jam, tanpa Qt).** `periksa_prasyarat()`:

| Kunci | Periksa | Perbaikan |
|---|---|---|
| windows | build ≥ 19041 | jelaskan butuh Win 10 2004+ / 11 |
| wsl | `wsl.exe` ada, `wsl -l -q` punya distro | K4 |
| wsl2 | `wsl -l -v` versi 2 | `wsl --set-version <distro> 2` |
| pengguna | `whoami` di WSL bukan root | buka Ubuntu sekali untuk membuat pengguna |
| gpu | `/usr/lib/wsl/lib/nvidia-smi` | perbarui driver NVIDIA; K5 |
| disk | `df` ≥ 30 GB bebas | kosongkan C:; `wsl --manage <distro> --set-sparse true` |
| alat_dasar | `curl tar bzip2` ada | tampilkan `sudo apt install -y curl bzip2` + buka terminal Ubuntu (aplikasi tidak menjalankan sudo) |
| internet | `curl -sI https://conda.anaconda.org` | periksa koneksi; sebut `HTTPS_PROXY` |

Wajib: dekoder UTF-16 wsl.exe dipakai bersama (`antrean._teks_keluaran` → `lanjutan`); **isi skrip dikirim lewat
stdin (`wsl -e bash -s`), bukan jalur** — folder aplikasi bisa berspasi dan ber-huruf non-ASCII; pesan khusus
`ERROR_NO_SYSTEM_RESOURCES` (tutup aplikasi kamera); `segarkan_semua()` memanggil `status(segar=True)` di
`unidock` dan `rbfe_openfe`. `PAKET` berisi alat, skrip, ukuran, lisensi, butuh NVIDIA, dan peta penanda
(`UNDUH_*`, `ULANG_UNDUH n`, `PYTHON_312`, `BOBOT_SELESAI`, `PASANG_SELESAI`) → label manusiawi.
`urai_kemajuan(baris, paket)` murni. Uji `dev/uji_alat_wsl.py` dengan keluaran palsu (UTF-16, tanpa distro, WSL1,
tanpa NVIDIA, disk kurang, bzip2 hilang, penanda lengkap, keluaran rusak).

**A3. Dialog `ui/dialog_alat_wsl.py` (±2 jam).** Menu **Alat › Pasang alat lanjutan (WSL)…** (+ tautan dari
Bantuan). Paragraf penjelasan (apa, kenapa tidak dibundel, unduh dari mana, tidak ada data proyek yang dikirim);
daftar prasyarat ✓/✗ + tombol perbaikan + **Periksa ulang**; dua kartu paket (A: Docking GPU & RBFE, B: Co-folding &
skor CNN) dengan status/versi/ukuran/lisensi + Pasang/Pasang ulang; kemajuan per langkah, waktu, progress bar, log
(juga ke `data/log/alat_wsl_<paket>.log`), **Hentikan**; proses `QProcess`; sukses → segarkan status + kabari
jendela utama.

**A4. Ganti pesan buntu (±30 mnt).** "… belum terpasang di WSL. Pasang lewat Alat › Pasang alat lanjutan (WSL)." +
tombol **Pasang…** yang membuka dialog dengan paketnya terpilih (panel Uni-Dock, RBFE, co-folding/peptida, GNINA).

**A5. Terjemahan & dokumentasi (±45 mnt).** Kamus (CRLF!) + `buat_kamus.py`; audit bahasa & label untuk dialog baru;
`instalasi.html` bagian "Alat lanjutan (opsional, WSL)" dan perbaiki kalimat lead ("tanpa perlu ... WSL");
`troubleshooting.html` (sumber daya WSL, disk penuh, driver lama, unduhan putus, lupa sandi Ubuntu).

**A6. Uji nyata dari nol (K6, 1–3 jam di latar).** `wsl --import VirmoLabUji` dari rootfs Ubuntu resmi; modul
menerima `distro=`; pasang paket A lalu B dari build beku; catat durasi/unduhan/ukuran sungguhan dan masukkan ke
`PAKET` + dokumentasi; uji fungsi (docking Uni-Dock 1 ligan, `openfe --version`, GNINA `--score_only`, Boltz
`predict --help`); `wsl --unregister VirmoLabUji` **setelah konfirmasi pengguna**.

**Gerbang A:** `git grep "build_tools/pasang" -- virmolab` kosong; `uji_alat_wsl.py` lulus; dialog terang/gelap/EN
tanpa teks terpotong; skrip palsu menggerakkan semua langkah dan Hentikan bekerja; (K6) pemasangan dari nol sukses.

### B. Kebenaran ilmiah

**B1. Kriteria keyakinan penargetan balik (K7).** Bahas pendekatan bersama pengguna di awal: kriteria yang dipakai
dan disepakati di Artikel 1 (lihat memori `artikel1-tanaman-obat-docking`), cara melaporkan alasan per target, dan
paragraf metode. Lalu kerjakan di `core/target_balik.py` + `ui/dialog_target_balik.py` + `dev/uji_target_balik.py`
(uji lama mengunci kriteria lama: perbarui harapannya), terjemahan, CHANGELOG ("hasil penargetan balik dari versi
sebelumnya perlu dibaca ulang").

**B2. Sapuan cepat keluaran lain yang berlabel kualitatif.** Cari label "tinggi/sedang/rendah", "disarankan", "layak"
di modul inti; pastikan masing-masing berdasar ambang yang terdokumentasi di `docs/_sumber/metode.html`, bukan
peringkat relatif. Catat temuan; perbaiki yang menyesatkan, sisanya masuk 1.8.x.

**Gerbang B:** uji penargetan balik lulus dengan kriteria baru; dialog menampilkan alasan; metode.html diperbarui;
tidak ada label kualitatif tanpa ambang terdokumentasi.

### C. Kesiapan distribusi

| # | Tugas | Catatan |
|---|---|---|
| C1 | Audit repo sebelum publik (K2=a) | gitleaks/trufflehog atas **seluruh riwayat**; cari data pribadi (nama mahasiswa, berkas proyek, surel) di `dev/`; pastikan `dev/uji/`, `branding/promosi/` tidak terlacak; hasil QSAR/artikel tidak ikut |
| C2 | README publik | dua bahasa (ID utama, EN ringkas): apa VirmoLab, tangkapan layar, unduh + verifikasi SHA-256, kebutuhan sistem, cara mengutip, lisensi, laporan bug |
| C3 | Templat issue & kebijakan | `.github/ISSUE_TEMPLATE/bug.yml` (versi, Windows, GPU, langkah, log `data/log`), `SECURITY.md` singkat |
| C4 | Cek pembaruan | `core/pembaruan.py` `REPO` sesuai K2; uji: aplikasi 1.7.0 terpasang mendeteksi 1.8.0 dan menautkan halaman rilis |
| C5 | Lisensi | perbarui tawaran kode sumber GPL di `LISENSI_PIHAK_KETIGA.txt` ke tautan tag `v1.8.0`; cocokkan daftar komponen dengan isi `_internal/bin` dan paket Python yang dibundel (otomatis: skrip kecil yang membandingkan); lisensi skrip WSL & alat yang diunduhnya disebut di dialog A3 |
| C6 | CITATION & DOI | `CITATION.cff` versi/tanggal; K10 (`url`); Zenodo: hubungkan repo, rilis memicu DOI; tambah badge DOI di README dan paragraf "cara mengutip" di Bantuan |
| C7 | Privasi | satu paragraf di README & Bantuan: VirmoLab tidak mengirim data proyek; yang terhubung internet hanya unduhan struktur/data atas perintah pengguna, cek pembaruan (GET ke GitHub, bisa dimatikan), dan pemasang WSL |
| C8 | Catatan rilis | CHANGELOG [1.8.0] + versi ringkas untuk halaman rilis (ID + EN) + "Apa yang baru" di aplikasi (`versi_dilihat`) |
| C9 | Tanda tangan (K3) | pesan sertifikat hari 1 bila Certum; bila SignPath, rencanakan CI terpisah (bukan untuk 1.8.0) |

**Gerbang C:** pemindaian rahasia bersih; README & templat siap; pembaruan teruji dari 1.7.0; daftar lisensi cocok
dengan isi build.

### D. Uji

**D1. Otomatis (laptop pengembang).** `dev/siapkan_contoh.py` → regresi penuh `dev/regresi.py` (target 100 % lulus atau
tiap kegagalan dijelaskan sebagai masalah uji) → audit `uji_label_terpotong.py` & `--en` → `uji_bahasa_lanjut.py`.

**D2. Pemasangan (memori `virmolab-uji-pemasangan`, wajib).** Portable di folder berspasi + non-ASCII dengan PATH
minimal (`--uji-mandiri`); tiruan tanpa OpenCL (singkirkan `clinfo.exe` di salinan); installer `/VERYSILENT
/CURRENTUSER` → uji mandiri → copot bersih; **buka GUI dan tangkap jendela dengan PrintWindow, lalu lihat
gambarnya** (terang, gelap, EN, dialog baru); pemutakhiran di tempat: pasang 1.7.0 dulu, lalu 1.8.0 di atasnya →
proyek & pengaturan tetap, versi baru berjalan.

**D3. Matriks laptop (K9, penguji beta).**

| Konfigurasi | Yang diuji |
|---|---|
| Windows 11, GPU NVIDIA | pasang, wizard, docking AD-GPU & Vina, pemasang WSL paket A |
| Tanpa GPU NVIDIA (Intel/AMD) | mode bawaan, docking Vina, AD-GPU lewat OpenCL Intel/AMD bila ada, dialog WSL menolak paket yang butuh NVIDIA dengan alasan |
| RAM 8 GB, layar 1366×768, skala 125–150 % | tata letak, MD tingkat Ringan, tidak ada teks terpotong |
| Nama pengguna Windows berhuruf aksen / berspasi (bila ada) | seluruh alur |

Bahan untuk penguji: satu halaman langkah uji (unduh, verifikasi SHA-256, pasang, tutorial docking 1HSG, kirim
log `data/log/virmolab.log` + tangkapan layar), formulir umpan balik sederhana, batas waktu 5–7 hari.

**D4. Keamanan biner.** Pindai `rilis/` dengan Microsoft Defender (`MpCmdRun -Scan -ScanType 3 -File ...`) dan catat
hasilnya. Mengunggah ke VirusTotal = membagikan biner ke pihak ketiga: **tanya pengguna dulu**.

**Gerbang D:** regresi & audit bersih; D2 semua lulus dengan tangkapan layar diperiksa; setiap penguji menyelesaikan
docking pertama; semua laporan bug kritis ditutup.

### E. Build dan publikasi

1. **RC1:** versi `1.8.0` dengan label `rc1` di catatan, build, D2 lengkap, bagikan ke penguji (tautan privat).
2. Perbaiki temuan beta → RC2 bila ada perubahan kode → ulang D2.
3. **Final:** versi bersih 1.8.0; bila ada sertifikat, `rilis.py --wajib-tanda-tangan`; D2 sekali lagi pada artefak
   final; Defender scan.
4. Commit rilis, tag `v1.8.0`, push (sesuai K2), **GitHub Release** dengan Setup, Portable, `SHA256SUMS-1.8.0.txt`,
   catatan rilis. Unduh ulang dari halaman rilis dan cocokkan SHA-256.
5. Zenodo DOI terbit → perbarui README/CITATION/Bantuan (commit kecil).
6. Uji cek pembaruan dari 1.7.0 terpasang → menautkan 1.8.0.
7. Pengumuman (teks siap salin ID/EN): untuk siapa, fitur utama, tautan unduh, cara mengutip.

Semua langkah keluar (push, tag, release, Zenodo, pengumuman, VirusTotal) **dikonfirmasi pengguna satu per satu**.

### F. Pasca-rilis

- Pantau issue 2 minggu pertama; label `kritis` → hotfix 1.8.1 (prosedur sama: D2 wajib).
- Simpan artefak rilis sebelumnya (`C:\VirmoLab-rilis-lama`) dan biarkan rilis 1.7.0 tetap ada sebagai cadangan.
- Bila rilis bermasalah berat: tandai rilis sebagai pre-release, pasang pemberitahuan di README, rilis 1.8.1.
- Catat pelajaran ke memori.

---

## 4. Jadwal

| Hari | Kerja | Gerbang |
|---|---|---|
| 1 | Keputusan K1–K10; pesan sertifikat (K3) & minta penguji (K9); A1–A5; A6 dimulai di latar | A (kecuali A6) |
| 2 | B1–B2; C1–C8; D1; RC1 build + D2; kirim ke penguji | B, C, D1–D2 |
| 3–9 | Penguji bekerja; perbaiki temuan; RC2 bila perlu | — |
| 10 | Final build, D2, publikasi E1–E7 | D, E |

## 5. Risiko

| Risiko | Penanganan |
|---|---|
| Penguji tidak tersedia | rilis tetap sebagai 1.8.0 dengan catatan "diuji di 1 laptop + tiruan", tunda pengumuman luas |
| Sertifikat lama terbit | rilis tanpa tanda tangan (K3), panduan SmartScreen sudah ada |
| Data pribadi/riwayat tidak layak dipublikasikan | K2=(b): repo rilis terpisah + kode sumber pada tag diunggah sebagai arsip; atau bersihkan riwayat (`git filter-repo`) dengan persetujuan |
| Pemasang WSL gagal di jaringan kampus | skrip mengulang & melanjutkan; dokumentasi proksi; alat WSL tetap opsional |
| Perubahan kriteria B1 mengubah hasil lama pengguna | CHANGELOG eksplisit + catatan di dialog |
| Regresi besar di menit akhir | tidak ada perubahan kode setelah RC final kecuali perbaikan kritis; tiap perubahan → D2 ulang |
| Disk E: sempit untuk build | pindahkan rilis lama ke `C:\VirmoLab-rilis-lama` sebelum build |

## 6. Kemajuan (diisi tiap sesi)

**25 Okt 2026 — jalur A SELESAI.** Dialog `Alat › Pasang alat lanjutan (WSL)` + `core/alat_wsl.py` jadi dan diuji
(`dev/uji_alat_wsl.py` 42 OK; `dev/uji_alat_wsl_gui.py` LULUS; audit label & bahasa 0 temuan). A4 lulus gerbang:
`git grep "build_tools/pasang" -- virmolab` kosong. A6 (pemasangan sungguhan di distro bersih `VirmoLabUji`)
membongkar empat bug nyata — `bzip2` tidak ada di Ubuntu 26.04, `~/.boltz` belum dibuat saat mengunduh bobot,
ukuran paket jauh di atas perkiraan (kini 15/17 GB, puncak 19 GB, arsip `.conda` dihapus sesudah sukses), dan
**Boltz-2 dihentikan OOM killer pada VM WSL 4 GB** (kini ada prasyarat memori + pesan jelas). Uji fungsi di distro
uji: Uni-Dock 6 detik (RMSD pose-3 2,12 Å), GNINA 5 detik, OpenFE 1.13 + OpenMM 8.4 melihat CUDA.
Catatan terbuka: mode pencarian Uni-Dock `detail` memberi hasil identik dengan `balance` — perlu diperiksa.

**25 Okt 2026 — jalur C SELESAI (kecuali langkah keluar).** C1 pemindaian seluruh riwayat (66 commit, 2.055 blob)
bersih: tidak ada token, kunci, atau data pihak ketiga; yang muncul hanya nama pengembang sendiri dan surel
`noreply` GitHub. C2 README ditulis ulang; C3 `SECURITY.md` + templat issue; C4 `core/pembaruan.py` sudah
menunjuk repo rilis dan uji 1.7.0 → 1.8.0 ditambahkan (uji sungguhan baru bisa sesudah rilis terbit);
C5 tawaran kode sumber GPL menunjuk tag rilis, alat WSL dicatat lisensinya, `dev/cek_lisensi.py` membandingkan
catatan dengan isi build (bersih; ulangi pada build 1.8.0); C6 `CITATION.cff` memakai nama penulis sebenarnya,
`url` dihapus (K10) — Zenodo menyusul saat rilis; C7 paragraf privasi di README dan panduan; C8 CHANGELOG 1.8.0
dan draf catatan rilis `CATATAN_RILIS_1.8.0.md`. Tangkapan layar dokumentasi dibuat ulang dari folder kerja
netral `C:\VirmoLab-dokumentasi` (sebelumnya memperlihatkan jalur folder pengembangan).

**Jalur B (K7) belum dikerjakan**: suntingan `core/target_balik.gabung()` dihentikan pengklasifikasi keamanan
dua kali; dikerjakan pengguna sendiri.

**Sebelum publikasi (dikonfirmasi pengguna satu per satu):** jadikan repo publik, aktifkan Discussions (dirujuk
templat issue), hubungkan Zenodo, push + tag `v1.8.0`, terbitkan Release, lalu perbarui badge DOI.

## 7. Kalimat pembuka untuk sesi berikutnya

> Kerjakan `dev/dokumen/RENCANA_RILIS_1.8.0.md`. Mulai dengan keputusan K1–K10 (tanyakan dengan AskUserQuestion,
> rekomendasi di urutan pertama), lalu jalur A → B → C → D → E sesuai jadwal, cek gerbang tiap jalur sebelum lanjut.
> Untuk D2 ikuti memori `virmolab-uji-pemasangan`. Semua langkah keluar dikonfirmasi satu per satu.
