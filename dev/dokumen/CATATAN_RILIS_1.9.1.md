# Catatan rilis 1.9.1 (draf untuk halaman GitHub Release)

Teks di bawah siap disalin ke halaman rilis. Ganti `<SHA-SETUP>` dan `<SHA-PORTABLE>` dengan sidik jari
dari `SHA256SUMS-1.9.1.txt` sebelum diterbitkan. Badge DOI tidak perlu ditambahkan tangan: webhook Zenodo
sudah aktif, jadi rilis ini terarsip sendiri dan mendapat DOI versinya begitu diterbitkan.

---

## VirmoLab 1.9.1 — rilis perbaikan

Rilis kecil di atas 1.9.0. Tidak ada fitur baru; yang diperbaiki adalah satu kriteria ilmiah yang dapat
menyesatkan pembacaan hasil, kepatuhan pada pedoman layanan NCBI, dan kelengkapan metadata sitasi.

### Yang berubah

- **Keyakinan konsensus penargetan balik tidak lagi dinilai dari peringkat.** Syarat lama "10 besar kedua
  jalur" tidak bermakna pada panel yang memang kecil — panel antibakteri berisi 9 target, antiinflamasi 8 —
  sehingga **setiap** target memenuhinya dan dilabeli berkeyakinan *tinggi*, termasuk target dengan z-skor
  −0,4 dan kemiripan Tanimoto 0,17. Keyakinan kini memakai ambang mutlak: *tinggi* bila z ≤ −2 sekaligus 3
  besar jalur struktur **dan** Tanimoto ≥ 0,40 pada jalur ligan, *sedang* bila hanya satu jalur memenuhi,
  *rendah* bila tidak satu pun.

  **Bila Anda sudah menjalankan penargetan balik dengan 1.9.0 atau sebelumnya, baca ulang hasilnya** —
  sebagian label *tinggi* akan turun, dan paragraf metodenya perlu disalin ulang karena kriterianya ikut
  berubah.

- **Pencarian homolog (konservasi kantong) mematuhi pedoman NCBI.** Pekerjaan BLAST tidak lagi diperiksa
  tiap 12 detik melainkan sekali semenit, dengan jeda awal 10 detik dan parameter `tool` di tiap permintaan.
  Pencarian jadi terasa lebih lambat, tetapi pemanggil yang melanggar pedoman dipindahkan NCBI ke antrean
  lambat atau diblokir sama sekali — jadi ini justru membuat fiturnya tetap bisa dipakai.

- **Metadata sitasi memuat DOI.** Tiap rilis diarsipkan di Zenodo. Kutip DOI konsep
  [10.5281/zenodo.23978036](https://doi.org/10.5281/zenodo.23978036) untuk perangkat lunaknya secara umum,
  atau DOI versi untuk build yang benar-benar Anda pakai. Dialog **Bantuan › Lisensi dan cara mengutip**
  kini menampilkan DOI itu.

- **Catatan lisensi melengkapi layanan daring yang dipanggil aplikasi**: CTD, Wikidata/LOTUS, dan NCBI
  BLAST, beserta lisensi dan sitasinya — termasuk syarat CTD yang membatasi pemakaian komersial.

Daftar lengkap: [CHANGELOG.md](../../CHANGELOG.md).

### Unduh dan periksa

| Berkas | Untuk |
|---|---|
| `VirmoLab-Setup-1.9.1.exe` | pemasangan biasa (per pengguna, tanpa hak administrator) |
| `VirmoLab-Portable-1.9.1.zip` | dijalankan dari folder mana saja, termasuk flashdisk |
| `SHA256SUMS-1.9.1.txt` | sidik jari kedua berkas di atas |

```powershell
Get-FileHash .\VirmoLab-Setup-1.9.1.exe -Algorithm SHA256
```

Setup: `<SHA-SETUP>`
Portable: `<SHA-PORTABLE>`

Installer belum ditandatangani sertifikat berbayar, jadi Windows SmartScreen menampilkan "Windows protected
your PC" — klik *More info › Run anyway* setelah sidik jarinya cocok.

---

## VirmoLab 1.9.1 — maintenance release

A small release on top of 1.9.0. No new features. What changed: one scientific criterion that could mislead
how results are read, compliance with NCBI's service guidelines, and completeness of the citation metadata.

- **Reverse-targeting consensus confidence no longer comes from ranks.** The old rule — top 10 in both
  routes — says nothing on a panel that is genuinely small (9 antibacterial targets, 8 anti-inflammatory),
  so *every* target satisfied it and was labelled *high* confidence, including ones with a z-score of −0.4
  and a Tanimoto similarity of 0.17. Confidence now uses absolute thresholds: *high* when z ≤ −2 and within
  the top 3 of the structure-based route **and** Tanimoto ≥ 0.40 in the ligand-based route, *medium* when
  only one route qualifies, *low* when neither does.

  **If you ran reverse targeting with 1.9.0 or earlier, re-read those results** — some *high* labels will
  drop, and the methods paragraph needs copying again because the criterion itself changed.

- **Homologue search (pocket conservation) follows NCBI's guidelines**: one poll per minute instead of every
  12 seconds, a 10-second initial delay, and a `tool` parameter on every request. Searches feel slower, but
  callers that ignore these guidelines get moved to a slow queue or blocked outright.

- **Citation metadata carries a DOI.** Every release is archived on Zenodo. Cite the concept DOI
  [10.5281/zenodo.23978036](https://doi.org/10.5281/zenodo.23978036) for the software in general, or a
  version DOI for the exact build you used.

- **Third-party notices now cover the online services the application calls**: CTD, Wikidata/LOTUS and NCBI
  BLAST, with their licences and citations — including CTD's restriction on commercial use.
