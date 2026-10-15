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

## Memperoleh sertifikat (keadaan per Oktober 2026)

| Pilihan | Untuk perorangan di Indonesia | Biaya | Catatan |
|---|---|---|---|
| **Certum Open Source Code Signing** | Ya | ± €25–69/tahun (laporan pihak ketiga; cek toko Certum) | Paling realistis. Kunci di kartu pintar atau SimplySign (cloud); pakai opsi B. Tidak bisa diperpanjang, beli baru tiap tahun. |
| **SignPath Foundation** | Ya (proyek, bukan orang) | Gratis | Syarat: semua komponen berlisensi OSI, kebijakan tanda tangan di halaman proyek, dan **build otomatis dari repositori** (CI, mis. GitHub Actions). VirmoLab kini dibangun lokal dengan biner `vendor/` di luar git, jadi perlu pipeline CI dulu. Penerbit yang tertera: SignPath Foundation. |
| Azure Artifact Signing (dulu Trusted Signing) | **Tidak** | US$9,99/bulan | Perorangan hanya Amerika Serikat dan Kanada. |
| Sertifikat OV/EV komersial | Ya | ± US$100–400/tahun | Mahal untuk proyek gratis. |

Sumber: [SignPath Foundation](https://signpath.org/), [SignPath untuk open source](https://about.signpath.io/product/open-source),
[Certum Code Signing](https://shop.certum.eu/code-signing.html),
[Microsoft – pilihan code signing](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options).

## Batasan yang perlu diketahui

- Tanda tangan menghapus "Unknown publisher" dan mengurangi blokir antivirus, tetapi reputasi SmartScreen
  dibangun dari riwayat unduhan; rilis pertama dengan sertifikat baru masih bisa memunculkan peringatan.
- Bila antivirus tetap menandai exe PyInstaller sebagai ancaman palsu, kirim berkasnya ke
  <https://www.microsoft.com/wdsi/filesubmission> (dilakukan pengembang sendiri).
- Kunci privat jangan pernah masuk repositori, log, atau tangkapan layar.
