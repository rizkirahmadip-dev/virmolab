# Catatan rilis 1.9.2 (draf untuk halaman GitHub Release)

Teks di bawah siap disalin ke halaman rilis. Ganti `<SHA>` dengan sidik jari dari `SHA256SUMS-1.9.2.txt`
sebelum diterbitkan. Badge DOI tidak perlu ditambahkan tangan: webhook Zenodo sudah aktif.

---

## VirmoLab 1.9.2 — siap dipakai di luar Indonesia, dan bantuan yang menemukan Anda

Rilis ini lahir dari dua hal: menyiapkan VirmoLab untuk pengguna yang tidak berbahasa Indonesia, dan empat
laporan dari pengguna pertama di luar laptop pengembang.

### Antarmuka Inggris yang benar-benar Inggris

Antarmuka Inggris sudah ada sejak lama, tetapi **100 teks masih berbahasa Indonesia** di dalamnya — termasuk
**seluruh modul farmakologi jaringan**, fitur terbesar 1.9. Penyebabnya tiga, dan dua di antaranya struktural:

- Teks yang diberikan lewat **konstruktor** widget tidak pernah melewati lapisan terjemahan; hanya setter
  yang dibungkus. Nama objek di panel Objek, bilah viewport, dan seluruh panel langkah farmakologi lolos.
- Sepuluh entri kamus berisi **terjemahan setengah jadi** — "Impor Analog ke Proyek…" menjadi "Import Analog
  ke Proyek…", yang lebih membingungkan daripada tidak diterjemahkan sama sekali.
- **Label figur siap publikasi tidak memakai i18n sama sekali.** Figur yang Anda tempel ke naskah berbahasa
  Inggris keluar dengan sumbu "Rasio gen" dan legenda "1 (paling sentral)". Ini yang paling merugikan,
  karena figurnya masuk ke jurnal.

Audit ulang setelah perbaikan: **0 temuan** dari 1.770 teks jendela utama.

### Memilih bahasa, tiga lapis

- **Tombol ID | EN di bilah alat**, di sebelah tombol tema. Menggantinya menawarkan *Mulai ulang sekarang* —
  yang menutup jendela lewat pemeriksaan biasa, jadi docking atau MD yang sedang berjalan tetap ditanyakan
  dan dijeda dengan rapi.
- **Installer meneruskan bahasa yang Anda pilih** ke aplikasi. Sebelumnya installer berbahasa Inggris tetap
  membuka aplikasi berbahasa Indonesia: Anda ditanya, lalu jawabannya dibuang.
- **Pemasangan baru mengikuti bahasa Windows** bila belum pernah disetel — terutama untuk versi portable,
  yang memang tidak melewati installer.

### Bantuan yang menemukan Anda

Panduan sudah memuat penjelasan rinci tiap alat, tetapi tidak ada jalan dari dialog ke sana: F1 selalu
membuka halaman awal dokumen 25 bagian.

- **F1 di dialog mana pun** kini membuka bagian panduan untuk fitur itu.
- **Bantuan › Panduan fitur** mendaftar 38 alat dengan tautan langsung ke bagiannya.
- **66 tooltip parameter baru di 22 dialog.** Isinya menjawab pertanyaan yang sebenarnya: bukan mengulang
  rentang yang sudah tertulis di label, melainkan nilai mana yang wajar dan apa akibatnya bila salah.
  Contohnya SAScore — *"1 mudah, 10 sangat sulit. Di bawah 4 biasanya dapat disintesis rutin; di atas 6
  perlu jalur khusus. Tidak ada kaitannya dengan afinitas."*
- Dokumen **instalasi berbahasa Inggris**. Panduan utama dan dokumen metode masih berbahasa Indonesia:
  isinya kriteria ilmiah, dan terjemahan yang salah istilah di sana lebih berbahaya daripada dokumen
  Indonesia yang jelas.

### Empat perbaikan dari laporan pengguna

- **Setelah docking selesai, visualisasinya seolah belum ada.** Pose terbaik memang sudah dimuat, tetapi
  tab yang aktif adalah Tabel hasil, sehingga viewport tersembunyi di belakangnya. Satu-satunya hal yang
  terasa seperti "membuka" adalah klik dua kali pada baris. Kini viewport dibawa ke depan, **satu klik**
  pada baris sudah memuat posenya, dan panel kerja Hasil mendapat tombol *Lihat pose di Viewport 3D* yang
  sebelumnya tidak ada.
- **Tab Diagram 2D tidak punya cara mengganti senyawa.** Berganti ligan menuntut kembali ke tab Hasil,
  mengklik baris lain, lalu kembali lagi. Kini ada pemilih ligan di bilah atas tab itu sendiri, lengkap
  dengan ΔG tiap senyawa.
- **Catatan "Belum divalidasi (redocking)." terbaca seperti galat.** Ia menyebut kekurangan tanpa menyebut
  tindakannya dan tanpa mengatakan bahwa validasi itu opsional. Sekarang: *"Protokol belum divalidasi —
  Analisis › Validasi redocking (opsional, disarankan sebelum publikasi)."*
- **Dialog Sunting di kantong (3D) gagal dibuka sama sekali** untuk ligan dengan nitrogen terprotonasi —
  lazim pada pH fisiologis, termasuk ligan contoh MK1 pada 1HSG.

### Unduh dan periksa

| Berkas | Untuk |
|---|---|
| `VirmoLab-Setup-1.9.2.exe` | pemasangan biasa (per pengguna, tanpa hak administrator) |
| `VirmoLab-Portable-1.9.2.zip` | dijalankan dari folder mana saja |
| `SHA256SUMS-1.9.2.txt` | sidik jari kedua berkas di atas |

```powershell
Get-FileHash .\VirmoLab-Setup-1.9.2.exe -Algorithm SHA256
```

Installer **belum ditandatangani sertifikat berbayar**, jadi SmartScreen menampilkan "Windows protected your
PC" — klik *More info › Run anyway* setelah sidik jarinya cocok.

### Yang perlu diketahui

- Hasil docking adalah prediksi komputasi, bukan bukti aktivitas biologis.
- VirmoLab tidak mengirim proyek, struktur, atau hasil Anda ke mana pun.
- Mengutip: Pratama RR. VirmoLab (versi 1.9.2) [perangkat lunak]. 2026. doi:10.5281/zenodo.23978036

---

## VirmoLab 1.9.2 — ready outside Indonesia, and help that finds you (English)

This release came out of two things: preparing VirmoLab for users who do not read Indonesian, and four
reports from the first users outside the developer's own laptop.

**An English interface that is actually English.** The English interface had existed for a long time, but
**100 strings inside it were still Indonesian** — including the whole network pharmacology module, the
largest feature of 1.9. Three causes, two of them structural: text passed through widget *constructors*
never reached the translation layer; ten dictionary entries held half-finished translations; and the
publication-figure modules did not use i18n at all, so figures pasted into an English manuscript came out
with Indonesian axes. A re-audit after the fix found **0 remaining** out of 1,770 main-window strings.

**Choosing the language, in three layers.** An **ID | EN** toggle in the toolbar (with a *Restart now*
offer that closes the window through the usual checks, so running docking or MD is still asked about); the
installer now passes your chosen language to the application; and a fresh install follows your Windows
locale — which matters most for the portable build, since it never runs the installer.

**Help that finds you.** **F1** in any dialog opens the guide section for that feature, **Help › Feature
guide** lists 38 tools with direct links, and **66 new parameter tooltips across 22 dialogs** explain which
values are sensible and what happens when they are not — rather than repeating the range already printed on
the label. Installation documentation is now available in English; the main guide and the methods document
remain in Indonesian, because they carry scientific criteria where a mistranslated term would be more
harmful than a clear Indonesian page.

**Four fixes from user reports.** After docking finished the visualisation appeared to be missing (the best
pose was loaded, but behind the Results tab); the 2D diagram tab had no way to switch compounds; the
"not yet validated" note read like an error; and the Edit-in-pocket (3D) dialog failed to open at all for
ligands with a protonated nitrogen — common at physiological pH.

Docking results are computational predictions, not evidence of biological activity. Cite as: Pratama RR.
VirmoLab (version 1.9.2) [software]. 2026. doi:10.5281/zenodo.23978036
