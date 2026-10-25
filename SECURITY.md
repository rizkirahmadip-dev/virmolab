# Kebijakan keamanan · Security policy

## Versi yang didukung

Perbaikan keamanan dibuat untuk rilis terbaru saja. Perbarui ke versi terakhir di halaman
[Releases](https://github.com/rizkirahmadip-dev/virmolab/releases/latest) sebelum melapor.

## Melaporkan celah keamanan

**Jangan membuat issue publik.** Pakai
[GitHub Security Advisory](https://github.com/rizkirahmadip-dev/virmolab/security/advisories/new)
(Security › Report a vulnerability) — laporannya hanya terlihat oleh Anda dan pengembang.

Sertakan: versi VirmoLab, versi Windows, langkah untuk memunculkannya, dan dampaknya. Jangan melampirkan
data penelitian yang tidak boleh dibagikan — potongan kecil yang sudah dianonimkan sudah cukup.

Laporan dibalas dalam 7 hari. VirmoLab dikembangkan satu orang di luar jam kerja, jadi perbaikan bisa
makan waktu; Anda akan dikabari saat perbaikannya dirilis dan disebut di catatan rilis bila bersedia.

## Yang termasuk dan tidak

**Termasuk:** kode VirmoLab sendiri — penanganan berkas proyek (`.vmd`, `.vmdbackup`) dan struktur dari luar,
pemanggilan program bantu, skrip pemasang alat WSL, pemeriksaan pembaruan, dan penyimpanan pengaturan.

**Tidak termasuk:** celah di komponen pihak ketiga yang dibundel (AutoDock-GPU, Vina, Open Babel, RDKit,
OpenMM, P2Rank, Java, dan lainnya — laporkan ke proyeknya masing-masing, lihat
[`LISENSI_PIHAK_KETIGA.txt`](LISENSI_PIHAK_KETIGA.txt)); peringatan SmartScreen karena installer belum
ditandatangani (diketahui, lihat README); dan hasil ilmiah yang keliru — itu bug biasa, laporkan lewat
[Issues](https://github.com/rizkirahmadip-dev/virmolab/issues).

---

## In English

Security fixes target the latest release only. Please **do not open a public issue**: report through
[GitHub Security Advisory](https://github.com/rizkirahmadip-dev/virmolab/security/advisories/new) with the
VirmoLab version, Windows version, reproduction steps, and impact. You will get a reply within 7 days.

In scope: VirmoLab's own code (project and structure file handling, helper-process invocation, the WSL tool
installer, update checks, settings storage). Out of scope: bundled third-party components (report upstream),
the SmartScreen warning from the unsigned installer (known), and incorrect scientific output (ordinary bug —
use Issues).
