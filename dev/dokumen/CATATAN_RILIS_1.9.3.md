# Catatan rilis 1.9.3 (draf untuk halaman GitHub Release)

Teks di bawah siap disalin ke halaman rilis. Ganti `<SHA>` dengan sidik jari dari `SHA256SUMS-1.9.3.txt`
sebelum diterbitkan. Badge DOI tidak perlu ditambahkan tangan: webhook Zenodo sudah aktif.

---

## VirmoLab 1.9.3 — pembaruan yang memasang dirinya sendiri, dan tiga bug yang gagalnya diam

Rilis ini membereskan satu hal yang selama ini dikerjakan pengguna dengan tangan, dan tiga cacat yang
tidak pernah memunculkan pesan galat apa pun.

### Pembaruan selesai di dalam aplikasi

Sampai 1.9.2, memperbarui VirmoLab berarti enam langkah manual: membuka peramban, mengunduh installer
500 MB, menyalin sidik jari SHA-256, mencocokkannya dengan tangan, menjalankan installer, lalu melewati
seluruh wizard. Pemberitahuannya sendiri hanya satu baris abu-abu di pojok bilah status yang hilang
sesudah 15 detik — praktis tidak pernah terlihat.

Sekarang: rilis baru **membuka dialog pembaruan sendiri**, sekali untuk tiap nomor versi, bukan setiap
kali aplikasi dibuka. Tombol **Unduh dan pasang** mengerjakan sisanya — unduh, cocokkan sidik jari,
pasang tanpa satu pertanyaan pun, lalu buka aplikasi lagi.

Yang sengaja **tidak** dilakukan:

- Tidak mengunduh sendiri tanpa diminta. Berkasnya ratusan megabita; pada koneksi berbayar itu keputusan
  penggunanya.
- Tidak memasang diam-diam di latar. Mengganti berkas program saat docking atau MD berjalan merusak
  pekerjaan yang mungkin sudah berjam-jam, jadi aplikasi selalu ditutup lebih dulu dan pekerjaan yang
  berjalan ditanyakan.
- Tidak pernah menjalankan berkas yang sidik jarinya tidak cocok. Berkas yang gagal verifikasi dihapus,
  bukan disimpan untuk "dicoba lagi".

Unduhan yang terputus dilanjutkan lewat header Range, bukan diulang dari nol, dan dapat dibatalkan kapan
saja. Pembaruan dari dalam aplikasi juga **tidak memicu peringatan SmartScreen**: berkas yang diunduh
aplikasi sendiri tidak ditandai Windows sebagai unduhan internet.

### Tiga bug yang tidak pernah bersuara

**Tombol "Pilih 6 terdekat" di dialog residu fleksibel tidak mencentang apa pun** — justru mengosongkan
seluruh daftar. Seorang pengguna melaporkannya dan mengira dirinya salah langkah. Dia tidak.

Sinyal `clicked` Qt mengirim satu argumen bool. Menyambungkannya langsung ke metode yang punya parameter
dengan nilai bawaan membuat bool itu mengisi parameter pertama:

```python
b_auto.clicked.connect(self._pilih_otomatis)   # _pilih_otomatis(self, n=6)
```

Qt mengirim `False`, `n` menjadi 0, dan `r < n` tidak pernah benar. Tidak ada galat, tidak ada apa pun di
log — tombolnya hanya mengerjakan kebalikan dari yang seharusnya.

Sapuan atas seluruh sambungan sinyal menemukan satu bug lagi dengan sebab yang persis sama: **tombol
putar/jeda pemutar trajektori MD selalu menjeda, tidak pernah memutar.** Yang ketiga belum menggigit,
tetapi ikut dibereskan.

Uji untuk tombol residu fleksibel sudah ada sejak lama dan selalu lulus, karena ia memanggil metodenya
langsung alih-alih menekan tombolnya. Ujinya kini menekan `QPushButton` yang sungguhan, dan
`dev/cek_sinyal_qt.py` memeriksa pola ini di seluruh aplikasi pada setiap regresi.

**Pemutakhiran memasang versi baru di folder yang salah.** Pengguna yang dulu memilih folder sendiri
mendapat dua salinan: versi baru di folder bawaan, versi lama ditinggalkan utuh, dan entri uninstall ikut
pindah — sehingga folder lama tidak lagi dikenal Windows dan tidak dapat dibuang lewat Apps & features.
Setengah gigabita nyangkut di tempat yang tidak akan dicari siapa pun.

Perbaikan ini berlaku **langsung** untuk pengguna 1.9.2: yang menentukan adalah installer versi baru,
bukan yang sudah terpasang.

### Dokumentasi berbahasa Inggris

Tujuh dokumen kini tersedia dalam bahasa Inggris: panduan pengguna, instalasi, pindah laptop, setup GPU,
mengatasi masalah, metode & kriteria, dan validasi.

Yang paling berarti: **`F1` di antarmuka Inggris kini mendarat di halaman Inggris.** Sebelumnya pengguna
berantarmuka Inggris yang menekan F1 dibawa ke halaman berbahasa Indonesia. 42 tujuan bantuan kontekstual
tersedia di kedua bahasa.

Halaman metode itu yang dicari peninjau — parameter tiap mesin, kriteria interaksi beserta ambangnya,
rumus besaran turunan, dan 39 sitasi. Selama ini pembaca luar bisa memakai aplikasinya tetapi tidak bisa
memeriksa apa yang dihitungnya.

Tutorial 50 halaman masih berbahasa Indonesia dan menyusul di rilis berikutnya.

### Lainnya

- Judul diagram 2D memakai gaya angka yang sama dengan seluruh aplikasi. Judul itu ikut terbawa ke
  diagram yang diekspor ke SVG/PDF, jadi gambar yang masuk jurnal tidak lagi membawa gaya angka yang
  berbeda dari tabelnya.
- Tanda `&` pada dua label tombol tidak lagi dimakan Qt sebagai penanda tombol pintas.
- Panduan dan tutorial tidak lagi menyuruh klik dua kali baris hasil; satu klik sudah cukup sejak 1.9.2.
  Pemilih ligan di tab Diagram 2D akhirnya terdokumentasi.
- Daftar privasi di panduan, README, dan `SECURITY.md` menyebut unduhan installer. Daftar yang mengaku
  lengkap harus benar-benar lengkap.
- Lisensi repositori kini terbaca GPL-3.0 di GitHub, bukan "Other": berkas `LICENSE` memuat teks GPL apa
  adanya dan kepala hak ciptanya pindah ke `COPYRIGHT`.
- Impor banyak senyawa dari PubChem tidak lagi ditolak 503.
- Seluruh 28 tangkapan layar dokumentasi dibuat ulang; 18 berubah.

### Memperbarui dari 1.9.2

Sekali ini masih manual: unduh installer di bawah, cocokkan sidik jarinya, lalu pasang di atas versi yang
ada. Tombol **Unduh dan pasang** ada di 1.9.3, jadi mulai rilis berikutnya pembaruan berjalan sendiri.

### Berkas

| Berkas | Untuk |
|---|---|
| `VirmoLab-Setup-1.9.3.exe` | pemasangan biasa (per pengguna, tanpa hak administrator) |
| `VirmoLab-Portable-1.9.3.zip` | dijalankan dari folder mana saja, termasuk flashdisk |
| `SHA256SUMS-1.9.3.txt` | sidik jari untuk memeriksa keaslian unduhan |

Periksa sebelum dijalankan (PowerShell, di folder unduhan):

```powershell
Get-FileHash .\VirmoLab-Setup-*.exe -Algorithm SHA256
```

Installer belum ditandatangani sertifikat berbayar, jadi Windows SmartScreen menampilkan "Windows
protected your PC" — klik *More info › Run anyway* setelah sidik jarinya cocok.

### Yang belum terbukti

`uji_al_gui` tidak pernah selesai dijalankan sendirian: dua kali ia menggantung sampai batas 40 menit pada
regresi penuh. Fitur penapisan bertahap tetap ada dan uji lainnya lulus, tetapi jalur GUI-nya belum
diverifikasi pada rilis ini.
