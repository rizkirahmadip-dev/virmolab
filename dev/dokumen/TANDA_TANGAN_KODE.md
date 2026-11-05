# Tanda tangan kode (Authenticode) untuk rilis VirmoLab

Tanpa tanda tangan, Windows menampilkan "Windows protected your PC / Unknown publisher" saat installer dibuka,
dan sebagian antivirus kampus memblokir exe hasil PyInstaller. Jalur penandatanganan sudah ada di
`build_tools/rilis.py`; yang belum ada hanya sertifikatnya, karena sertifikat harus diajukan atas nama
pengembang sendiri.

## Yang sudah disiapkan

- `build_tools/tanda_tangan.ps1` menandatangani berkas dengan `signtool` (Windows SDK) bila ada, atau
  `Set-AuthenticodeSignature` bila tidak. Hash SHA-256, cap waktu RFC 3161 wajib, diulang 3× bila server cap
  waktu sibuk, lalu tanda tangan dibaca ulang. Gagal = rilis berhenti.
- `rilis.py` menandatangani `VirmoLab.exe` dan `VirmoLab-cli.exe` **sebelum** uji mandiri (yang diuji adalah
  biner yang dirilis), lalu meneruskan penanda ke Inno Setup sehingga installer **dan** uninstaller ikut
  ditandatangani (`SignTool=virmolab`, `SignedUninstaller=yes` di `installer/virmolab.iss`).
- Biner pihak ketiga (Vina, AutoDock-GPU, Open Babel, xtb, dll.) tidak ditandatangani ulang: itu bukan karya
  VirmoLab.
- Tanpa sertifikat, rilis tetap jalan seperti sebelumnya dan mencetak peringatan. `--wajib-tanda-tangan`
  menghentikan rilis bila sertifikat belum diatur (pakai untuk rilis resmi).

Diuji 16 Okt 2026 dengan sertifikat swa-tanda sekali pakai (openssl, tidak masuk certificate store):
`VirmoLab-cli.exe` dan installer Inno mini bertanda tangan dan bercap waktu DigiCert. Status Windows
`UnknownError` memang hasil yang benar untuk sertifikat swa-tanda (akarnya tidak dipercaya).

## Cara memakai

Atur salah satu, hanya di sesi terminal build (jangan ditulis ke berkas di repositori):

```powershell
# A. Berkas .pfx
$env:VIRMOLAB_TANDA_PFX = "D:\rahasia\virmolab.pfx"
$env:VIRMOLAB_TANDA_SANDI = "<sandi pfx>"
# B. Sertifikat di Windows certificate store (kartu pintar / Certum SimplySign)
$env:VIRMOLAB_TANDA_SHA1 = "<sidik jari SHA-1 sertifikat>"
# Opsional: server cap waktu lain
$env:VIRMOLAB_TANDA_TSA = "http://time.certum.pl"

.venv\Scripts\python.exe build_tools\rilis.py --wajib-tanda-tangan
```

Periksa hasil: `Get-AuthenticodeSignature rilis\VirmoLab-Setup-<versi>.exe` harus berstatus `Valid` dengan
sertifikat sungguhan.

## Memperoleh sertifikat (diperiksa ulang 5 November 2026)

| Pilihan | Untuk perorangan di Indonesia | Biaya | Catatan |
|---|---|---|---|
| **Certum Open Source Code Signing (SimplySign/cloud)** | Ya | dari €49 (harga tertera di toko Certum) | Paling realistis dari Indonesia: tidak ada kartu fisik dan pembaca kartu yang harus dikirim. Kunci di kartu kripto virtual; pakai opsi B. Batas 5.000 tanda tangan/bulan. |
| Certum Open Source Code Signing (set kartu) | Ya, tetapi perlu kiriman fisik | dari €69 | Berisi sertifikat + pembaca kartu + kartu kripto Certum. Perlu proCertum CardManager dan driver pembaca kartu. |
| **SignPath Foundation** | Ya (proyek, bukan orang) | Gratis | Syarat: semua komponen berlisensi OSI, kebijakan tanda tangan di halaman proyek, dan **build otomatis dari repositori**. Terhalang untuk VirmoLab: `vendor/innosetup`, `vendor/bin/jre`, `vendor/bin/p2rank`, `vendor/opencl`, dan `vendor/ketcher` di-gitignore, dan `.github/workflows` sendiri sudah mencatat bahwa pelari CI tidak bisa menirukan lingkungan build. Penerbit yang tertera: SignPath Foundation. |
| Azure Artifact Signing (dulu Trusted Signing) | **Tidak** | US$9,99/bulan | Perorangan hanya Amerika Serikat dan Kanada. |
| Sertifikat OV/EV komersial | Ya | ± US$100–400/tahun | Mahal untuk proyek gratis. |

### Langkah Certum SimplySign

1. Siapkan tiga hal yang diminta halaman resminya:
   - Foto diri sedang memegang dokumen identitas (KTP, paspor, SIM, atau kartu izin tinggal tetap).
     *"Photos should present the complete document (both sides)."* Dokumen harus masih berlaku pada hari
     sertifikat diterbitkan.
   - Tagihan utilitas atas nama sendiri (listrik, air, gas, atau telepon).
   - Alamat proyek open source yang sedang berjalan. *"The project must be publicly available and indicate
     clearly the subscriber's relationship with the project. If Certum is unable to identify the project based
     on publicly available information, the certificate will not be issued."* Untuk VirmoLab, nama pengembang
     sudah tertera di README, `CITATION.cff`, dan baris hak cipta.
2. Beli di toko Certum (lihat tabel di atas).
3. Unggah dokumen lewat akun Certum Store, bukan email atau faks: *"The fastest and recommended way to submit
   documents is to upload them directly through your Certum Store account."* Jalurnya: masuk akun ›
   *Data security products* › pilih sertifikatnya › unggah.
4. Pilih *automatic identity verification* yang ditandai "(recommended)". Pilihan lain (titik registrasi fisik,
   konfirmasi notaris) tidak praktis dari Indonesia.
5. Pasang *SimplySign Desktop* di PC dan aplikasi *SimplySign* di ponsel Android/iOS (pembangkit kode akses).
   Akun SimplySign dibuat saat aktivasi sertifikat.
6. Ambil sidik jari SHA-1 sertifikat, lalu jalankan rilis dengan opsi B di bagian "Cara memakai" di atas.

### Yang belum pasti — tanyakan ke Certum sebelum membayar

- **Masa berlaku sertifikat tidak disebut** di kedua halaman produk. Catatan versi lama dokumen ini menulis
  "beli baru tiap tahun"; itu tidak terbukti dari sumber resmi. Angka "1 year / 2 years" di halaman kartu
  adalah garansi perangkat keras, bukan masa berlaku sertifikat.
- **Lama penerbitan** setelah dokumen lengkap juga tidak dinyatakan di halaman mana pun.
- **Stok**: 5 November 2026 halaman SimplySign memuat *"Product is out of stock"*, dan halaman kartu memuat
  "out of stock" sekaligus "In stock".
- **Hanya non-komersial**, dan klausulnya bergigi: *"If Certum determines that the certificate is being used to
  sign software distributed commercially, the certificate will be revoked."* VirmoLab gratis dan GPL, jadi
  memenuhi syarat — tetapi ini mengunci model distribusinya.

Sumber: [SignPath Foundation](https://signpath.org/), [SignPath untuk open source](https://about.signpath.io/product/open-source),
[Certum Open Source Code Signing di SimplySign](https://shop.certum.eu/open-source-code-signing-on-simplysign.html),
[Certum Open Source Code Signing (set kartu)](https://shop.certum.eu/open-source-code-signing.html),
[Certum – dokumen yang diperlukan](https://support.certum.eu/en/code-signing-required-documents/),
[Microsoft – pilihan code signing](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options).

## Batasan yang perlu diketahui

- Tanda tangan menghapus "Unknown publisher" dan mengurangi blokir antivirus, tetapi reputasi SmartScreen
  dibangun dari riwayat unduhan; rilis pertama dengan sertifikat baru masih bisa memunculkan peringatan.
- Bila antivirus tetap menandai exe PyInstaller sebagai ancaman palsu, kirim berkasnya ke
  <https://www.microsoft.com/wdsi/filesubmission> (dilakukan pengembang sendiri).
- Kunci privat jangan pernah masuk repositori, log, atau tangkapan layar.
