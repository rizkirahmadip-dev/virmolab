# Induced fit docking: eksperimen yang tidak jadi dirilis

**Ringkasan: protokol induced fit gaya Glide/Prime yang dibangun dengan program bebas tidak
memperbaiki ketepatan pose pada lima kasus cross-docking acuan, bahkan memburuk pada empat di
antaranya, sambil membuat skor docking tampak jauh lebih baik. Karena itu fitur ini tidak
dipasang di VirmoLab.** Kode eksperimennya disimpan di `dev/eksperimen/induced_fit.py`
(tidak ikut terpasang) dan skrip validasinya di `dev/uji_induced_fit.py`.

Ditulis 16 Oktober 2026 setelah seluruh kasus dijalankan di RTX 3060 Laptop.

## Yang dicoba

Mengikuti alur Induced Fit Docking Glide/Prime (Sherman W, Day T, Jacobson MP, Friesner RA,
Farid R. *J Med Chem.* 2006;49(2):534-553) dengan program bebas:

1. **Docking lunak** — rantai samping besar di sekitar kotak docking dipangkas menjadi alanina
   (hanya CB yang disisakan), lalu ligan didocking ke kantong yang dilunakkan itu dengan Vina.
   Residu dipilih dari kotak docking, bukan dari pose docking kaku: pada kantong yang tertutup,
   pose kaku sering mendarat di cekungan lain sehingga residu yang dipangkas pun ikut salah.
2. **Relaksasi** — beberapa pose awal terbaik (dari reseptor utuh maupun kantong terpangkas)
   dibawa terus: rantai samping dikembalikan utuh, kompleks protein–ligan diminimisasi dengan
   OpenMM (Amber14 + OpenFF/NAGL, pelarut implisit OBC2), rantai samping kantong bebas bergerak,
   atom berat lain dikekang harmonik, ligan ditahan di tempatnya. Anil singkat 10–20 ps pada
   300 K ditambahkan supaya rantai samping bisa berpindah rotamer, karena minimisasi saja tidak
   dapat melewati penghalang rotamer.
3. **Docking ulang** — ligan didocking ulang pada tiap reseptor hasil relaksasi (kaku), lalu pose
   dengan skor docking ulang terbaik dipilih.

## Hasil validasi

Kasus cross-docking diambil dari Tabel 1 makalah Sherman dkk.: ligan kristal struktur B
didocking ke reseptor struktur A (struktur B disuperposisikan ke kerangka A lewat Cα bersama
sebelum RMSD dihitung). RMSD dalam ångström, pose peringkat 1, atom berat, simetri ligan
diperhitungkan.

| Kasus (reseptor ← ligan) | Docking kaku | Docking lunak | Induced fit | Acuan makalah (kaku → IFD) | ΔG kaku | ΔG induced fit | Rantai samping bergeser | Waktu |
|---|---|---|---|---|---|---|---|---|
| 1KIM ← 1KI4 (thymidine kinase) | 4,88 | 8,81 | **8,01** | 4,7 → 0,4 | −2,62 | −8,78 | 2,18 | 23 menit |
| 2ACR ← 1AH3 (aldose reductase) | 7,01 | 6,57 | **7,54** | 6,5 → 0,9 | −8,01 | −8,48 | 1,56 | 10 menit |
| 1DM2 ← 1AQ1 (CDK2) | 7,13 | 4,66 | **6,62** | 6,2 → 0,8 | −8,16 | −12,56 | 1,21 | 6 menit |
| 1ERR ← 3ERT (estrogen receptor) | 5,11 | 9,53 | **8,87** | 5,3 → 1,0 | −9,12 | −10,72 | 2,23 | 17 menit |
| 1NSC ← 1A4Q (neuraminidase) | 5,65 | 11,36 | **7,90** | 3,9 → 0,8 | −7,31 | −9,20 | 2,07 | 28 menit |

RMSD ≤ 2 Å: induced fit 0/5, docking kaku 0/5 (makalah: 5/5 untuk IFD Glide/Prime).

Pemeriksaan kewarasan: redocking ligan ke strukturnya sendiri berjalan baik dengan pipeline yang
sama — 1KIM/THM 0,47 Å dan 1KI4/BTD 0,45 Å — jadi kegagalan di atas memang kegagalan
cross-docking, bukan kesalahan preparasi, kotak, atau perhitungan RMSD.

## Mengapa gagal

- **Pemangkasan menghilangkan mitra ikatan hidrogen.** Setelah Gln/Arg/Tyr kantong menjadi
  alanina, yang tersisa hanyalah rongga hidrofobik: Vina menempatkan ligan dengan orientasi
  apa saja yang mengisi rongga. Pada 1KIM seluruh 20 pose docking lunak berjarak 8–11 Å dari
  pose kristal, sehingga relaksasi berangkat dari titik yang salah.
- **Skor docking memburuk sebagai penentu.** Pada 1KIM pose benar (2,2 Å) muncul di peringkat 4
  docking kaku, tetapi peringkat 1 tetap pose yang salah; setelah relaksasi, pose yang salah itu
  justru mendapat skor paling baik. Glide/Prime memakai GlideScore + Prime energy untuk memilih,
  dan kualitas pemeringkatan itulah yang tidak bisa ditiru dengan fungsi skor Vina.
- **Kantong yang direlaksasi menggelembungkan skor.** Semua kasus memberi ΔG lebih negatif
  setelah relaksasi (contoh ekstrem CDK2: −8,16 → −12,56 kkal/mol) tanpa pose yang lebih benar.
  Fitur yang membuat angka tampak membaik sementara posenya memburuk justru berbahaya bagi
  pengguna.

## Yang dipakai sebagai gantinya

Vina mendukung rantai samping fleksibel (`--flex`), dan VirmoLab sudah punya dialog **Residu
fleksibel**. Pada lima kasus yang sama, enam rantai samping kantong terdekat dibuat fleksibel
(exhaustiveness 16, pose peringkat 1; angka dalam kurung = RMSD terbaik di antara lima pose
teratas):

| Kasus | Kaku | Fleksibel 6 residu | ΔG kaku | ΔG fleksibel |
|---|---|---|---|---|
| 1KIM ← 1KI4 | 4,88 (2,18) | **4,85 (1,31)** | −2,62 | −8,92 |
| 2ACR ← 1AH3 | 7,01 (5,15) | **7,00 (4,54)** | −8,01 | −7,94 |
| 1DM2 ← 1AQ1 | 7,13 (3,92) | **6,98 (3,88)** | −8,16 | −8,16 |
| 1ERR ← 3ERT | 5,11 (1,46) | **1,71 (1,62)** | −9,12 | −9,48 |
| 1NSC ← 1A4Q | 5,65 (4,78) | **6,19 (5,12)** | −7,31 | −6,92 |

Hasilnya sederhana: 1 dari 5 kasus mencapai RMSD ≤ 2 Å (estrogen receptor) dibanding 0 dari 5
untuk docking kaku dan 0 dari 5 untuk protokol induced fit penuh, dan skornya tidak menggelembung
karena bentuk reseptor tidak diubah. Pose yang benar sering ada di lima teratas, jadi memeriksa
beberapa pose teratas tetap penting pada cross-docking. Angka ini bukan kemenangan besar, tetapi
jujur dan dapat diulang.

Karena itu yang ditambahkan ke VirmoLab hanyalah kemudahan nyata: tombol **Pilih 6 terdekat** dan
**Kosongkan** pada dialog Residu fleksibel, sehingga residu kantong dapat dicentang sekaligus
tanpa memilih satu per satu.

## Bila ingin dilanjutkan

Yang paling mungkin menutup selisihnya, dengan urutan dampak:

1. **Pemeringkatan ulang yang lebih baik**: nilai pose akhir dengan MM/GBSA (`core/md.py` sudah
   ada) atau GNINA CNN, bukan skor Vina. Ini menyerang penyebab utamanya.
2. **Pemangkasan selektif**: hanya pangkas rantai samping yang benar-benar bertabrakan dengan
   pose awal, bukan seluruh dinding kantong, supaya mitra ikatan hidrogen tetap ada.
3. **Pencarian rotamer eksplisit** (pustaka rotamer Dunbrack) menggantikan anil MD singkat.
4. **Ensemble reseptor**: beberapa struktur kristal/konformasi MD lalu docking ensemble — pada
   banyak kasus ini lebih murah dan lebih dapat diandalkan daripada induced fit satu struktur.

Jalankan ulang validasinya dengan:

```
PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_induced_fit.py
```
