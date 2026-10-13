# Prompt Pengembangan VirmoDock 1.2 – 1.6 (siap salin)

Pasangan berkas: `RENCANA_PENGEMBANGAN.md` (isi ilmiah & teknis rinci).
Dibuat 13 Oktober 2026.

---

## Cara pakai

1. **Satu prompt = satu sesi baru.** Jangan menggabungkan dua prompt fitur dalam satu sesi — konteks membengkak
   dan token terbuang.
2. Kerjakan berurutan sesuai nomor. Prompt yang bertanda *(bergantung: Pn)* butuh prompt itu selesai dulu.
3. Model yang disarankan:
   - **Opus** — prompt yang banyak keputusan ilmiah: P3 (F1), P6 (F3a), P7 (F3b), P8 (F5), P14 (F8), P15 (F9).
   - **Sonnet** — prompt yang lebih mekanis: P0, P1, P4 (F2), P5 (F11), P9–P13, P-RILIS.
4. Bila sesi terputus di tengah: buka sesi baru, tempel prompt yang sama, tambahkan satu baris
   `Lanjutkan: periksa git status dan CHANGELOG, kerjakan langkah yang belum selesai.`
5. Setiap prompt melarang commit/build. Commit setelah Anda periksa: tempel **P-COMMIT**.
6. Semua prompt merujuk **Lampiran UI** di akhir berkas ini — jangan dihapus.

Ringkasan urutan:

| No | Isi | Rilis | Bergantung |
|---|---|---|---|
| P0 | Persiapan & verifikasi butir [cek] | — | — |
| P1 | Fondasi: `sumber_data`, jejak proyek, graf | 1.2 | P0 |
| P3 | F1 Tanaman → senyawa | 1.2 | P1 |
| P4 | F2 Analisis MD lengkap | 1.2 | — |
| P5 | F11 Paket validasi protokol | 1.2 | P1 |
| P-RILIS | Rilis 1.2 | 1.2 | P1–P5 |
| P6 | F3a Penargetan balik | 1.3 | P1, P3 |
| P7 | F3b Jaringan & pengayaan | 1.3 | P6 |
| P8 | F5 QSAR | 1.4 | P1 |
| P9 | F4 Farmakofor & bentuk | 1.4 | — |
| P10 | F12 Pelacak hipotesis | 1.4 | P8 |
| P11 | F6 Konsensus co-folding | 1.5 | — |
| P12 | F10 Peptida | 1.5 | P11 |
| P13 | F7 xTB | 1.5 | izin unduh |
| P14 | F8 Generatif | 1.6 | izin unduh |
| P15 | F9 RBFE (eksperimental) | 1.6 | izin unduh |

(P2 sengaja kosong — dicadangkan bila Fondasi perlu dipecah.)

---

## P0 — Persiapan & verifikasi

```text
Sesi persiapan pengembangan VirmoDock 1.2. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python proyek: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

1. Pindahkan E:\Bikin Docking Simpel\RENCANA_PENGEMBANGAN.md dan PROMPT_PENGEMBANGAN.md ke folder VirmoDock\
   (pastikan tidak ada build yang sedang berjalan: cek proses python/pyinstaller dulu; bila ada, berhenti dan lapor).
2. Verifikasi butir bertanda [cek] yang dipakai rilis 1.2, dengan sumber resmi (situs resmi, GitHub, Zenodo,
   dokumentasi API) — bukan ingatan:
   a. Wikidata: properti SMILES yang dipakai LOTUS saat ini (P233 canonical / P2017 isomeric; apakah ada perubahan
      model SMILES), properti "found in taxon" P703, taxon name P225. Uji satu kueri kecil ke query.wikidata.org
      untuk Andrographis paniculata dan catat jumlah hasil.
   b. COCONUT 2.0: lisensi dump terbaru, apakah CSV/SDF penuh memuat kolom organisme, ukuran unduhan, URL tetap.
   c. RDKit di .venv: versi; apakah rdkit.Chem.rdFreeSASA dan rdkit.Chem.rdShapeAlign tersedia (impor saja).
   d. InChIKey andrografolida dan kurkumin (PubChem) untuk dipakai sebagai jawaban uji.
3. Tulis hasil ke RENCANA_PENGEMBANGAN.md: ganti tanda [cek] yang sudah pasti menjadi [terverifikasi 2026-xx-xx,
   sumber: URL]; yang ternyata salah, koreksi isinya dan tulis catatan singkat.
4. Laporkan ringkas (≤ 15 baris): apa yang berubah dari rencana.
Aturan: jangan ubah kode di virmodock/. Jangan unduh paket. Jangan commit.
```

---

## P1 — Fondasi bersama *(bergantung: P0)*

```text
Kerjakan Fondasi bersama VirmoDock 1.2. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

Baca dulu (secukupnya): RENCANA_PENGEMBANGAN.md §0 (konvensi) dan §2 (fondasi); PROMPT_PENGEMBANGAN.md
"Lampiran UI"; contoh klien internet yang sudah ada: core/chembl.py, core/rcsb.py (hanya bagian requests);
core/proyek.py (setdefault ±baris 52, simpan/muat); core/laporan.py bagian metode; core/grafik.py (cara membuat SVG).

Tugas:
1. core/sumber_data.py
   - dataclass Jejak(sumber, versi, diambil, kueri, lisensi) + to_dict/from_dict.
   - ambil_json(url, params=None, data=None, batas=30, coba=3, cache_jam=168) -> (dict, Jejak)
   - ambil_teks(...) untuk TSV/CSV/GMT; sparql(endpoint, kueri, ...) -> (list[dict], Jejak)
   - cache berkas di paths.APPDATA/"cache_http" (kunci sha256 url+params+data; simpan isi + waktu + status).
   - mode luring: gagal jaringan + ada cache -> pakai cache, Jejak.versi = "cache <tanggal>".
   - batas laju per domain (min. 0,5 s antar-permintaan; Wikidata 1 s); User-Agent "VirmoDock/<versi> (akademik)".
   - pesan galat ramah dalam Bahasa Indonesia (tanpa internet / batas waktu / server sibuk 429/503).
   - fungsi hapus_cache() dan ukuran_cache().
   JANGAN mengubah chembl.py/rcsb.py sekarang — cukup sediakan modul; migrasi klien lama dicatat sebagai pekerjaan nanti.
2. Jejak proyek: Proyek.jejak (setdefault []), Proyek.catat_jejak(jejak) tanpa duplikat (kunci sumber+kueri),
   ikut disimpan/dimuat. Proyek lama tanpa kunci harus tetap terbuka.
3. Laporan: bagian "Sumber data" (tabel sumber, versi, tanggal ambil, lisensi) di laporan HTML & Word bila
   proyek.jejak tidak kosong. Fungsi naskah.paragraf_sumber_data(proyek) -> teks metode Bahasa Indonesia.
4. core/graf.py: tata_letak(G, metode="spring"|"kk", benih=1) ; svg_graf(G, warna_simpul, ukuran_simpul, label,
   lebar, tinggi, tema) memakai token tema (bukan warna tetap) ; ekspor_graphml(G, path) ; ekspor_csv_tepi(G, path).
5. Pengaturan: di dialog pengaturan yang sudah ada tambahkan baris "Cache data internet: <ukuran> [Hapus cache]".
6. Uji:
   - dev/uji_sumber_data.py: server http.server lokal di utas (respons JSON, 503 lalu 200, timeout) -> cek coba ulang,
     cache, mode luring, Jejak terisi. Tanpa internet.
   - dev/uji_graf.py: graf 10 simpul -> SVG valid (xml.etree parse), GraphML bisa dibaca ulang networkx.
   - uji_proyek.py: tambahkan pemeriksaan jejak pulang-pergi simpan/buka.
7. Penutup sesuai RENCANA §0.6 (pyflakes, i18n untuk teks UI baru, CHANGELOG bagian Baru di versi [1.2.0] -
   buat bagian baru bila belum ada, CATATAN_TAHAP2.md peta berkas).
Aturan: jangan commit, jangan build, jangan jalankan dev/regresi.py. Keluaran uji tampilkan ringkasan saja.
Laporan akhir ≤ 15 baris.
```

---

## P3 — F1 Tanaman obat → senyawa *(bergantung: P1)*

```text
Kerjakan fitur F1 "Senyawa dari tanaman" VirmoDock 1.2. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

Baca dulu: RENCANA_PENGEMBANGAN.md §0 dan §3 F1 (termasuk hasil verifikasi P0); PROMPT_PENGEMBANGAN.md
"Lampiran UI" + "UI F1" di bawah prompt ini; core/sumber_data.py (dari P1); core/pustaka.py (skema COCONUT,
KOLOM, cari_coconut); core/sifat.py; ui/dialog_pustaka.py (contoh dialog impor ligan); cara impor ligan ke proyek
yang dipakai dialog_pustaka/dialog_chembl.

Tugas:
1. data/nama_tanaman_id.csv (kolom: nama_lokal,nama_ilmiah,famili,sumber). Mulai dengan ±60 tanaman obat Indonesia
   yang paling sering diteliti (sambiloto, kunyit, temulawak, jahe, sirih, kumis kucing, meniran, mahkota
   dewa, daun salam, brotowali, pegagan, kayu manis, sereh, kelor, binahong, mengkudu, sirsak, jambu biji, …).
   Nama ilmiah HARUS dicek di Wikidata (P225) lewat sparql; baris yang tidak cocok jangan dimasukkan.
   Kolom sumber = "Wikidata Qxxxx". Pengguna akan menambah dari Farmakope Herbal Indonesia nanti.
2. core/tanaman.py
   - cari_takson(nama) -> [{qid, nama_ilmiah, peringkat, sinonim, nama_lokal, sumber}]:
     nama lokal (CSV, tanpa beda huruf besar/kecil & aksen) -> nama ilmiah; lalu Wikidata (P225 + sinonim P1420).
   - senyawa_takson(qid, turunan=False, batas=5000, batal=None) -> (list[dict], Jejak) memakai sparql LOTUS
     (properti sesuai verifikasi P0). Tiap baris: qid_senyawa, nama, smiles, inchikey, rujukan [DOI/QID], tahun.
   - gabung_coconut(daftar) bila COCONUT lokal tersedia (kunci 14 huruf InChIKey).
   - standarisasi(daftar): rdMolStandardize (fragmen terbesar, netralisasi, tautomer kanonik), pertahankan stereo,
     hitung sifat (core/sifat.py), PAINS; baris gagal ditandai, tidak dibuang diam-diam.
   - semua fungsi tanpa Qt; galat jaringan -> pesan dari sumber_data.
3. ui/dialog_tanaman.py sesuai "UI F1". Pekerjaan jaringan via kerja.jalankan + kit.sibuk; tombol Batal aktif.
4. Impor ke proyek: l["asal"] = {"sumber": "LOTUS (Wikidata)", "takson": nama_ilmiah, "qid": ..., "rujukan": [...]}
   + proyek.catat_jejak(jejak). Ligan duplikat (InChIKey sama) tidak diimpor dua kali — beri tahu jumlahnya.
5. Pembuka buka_tanaman di mainwindow_dialog.py; menu Siapkan › Langkah 2 · Ligan, setelah "Pustaka ligan":
   A("Senyawa dari tanaman obat…", "lig", self.buka_tanaman, None, "Cari senyawa yang dilaporkan dari suatu
   tanaman (LOTUS/Wikidata), lengkap dengan rujukan, lalu impor ke proyek"). Tambahkan juga ke palet perintah
   (dict nama -> fungsi ±baris 431) dan ubin halaman awal bila ada ubin ligan.
6. Uji:
   - dev/data/lotus_*.json: simpan 2 respons SPARQL nyata (Andrographis paniculata, Curcuma longa) untuk uji luring.
   - dev/uji_tanaman.py: luring -> andrografolida & kurkumin ada (InChIKey dari P0), standarisasi tidak menghapus
     stereo, duplikat tergabung, nama lokal "sambiloto"/"kunyit" teresolusi. Bagian daring di belakang bendera
     --daring (dilewati regresi, seperti uji_chembl).
   - tambahkan "tanaman" ke DIALOG di dev/uji_dialog_lanjut_gui.py dan jalankan hanya itu.
7. Dokumen: docs/panduan.html bagian "Senyawa dari tanaman obat" (langkah + batasan data);
   docs/metode.html paragraf metode + sitasi LOTUS (Rutz et al. 2022, eLife, DOI diverifikasi) dan Wikidata.
8. Penutup RENCANA §0.6.
Aturan: jangan scrape KNApSAcK/IMPPAT (hanya tautan "Buka di situs"). Jangan commit/build/regresi penuh.
Laporan akhir ≤ 15 baris.
```

### UI F1

```
┌ Senyawa dari tanaman obat ─────────────────────────────────────────────────────────────┐
│ [kit.judul] Senyawa dari tanaman obat                                                   │
│ Senyawa yang dilaporkan dari suatu tanaman menurut LOTUS (Wikidata), lengkap dengan     │
│ rujukan. Kehadiran senyawa di basis data belum tentu berarti kadarnya bermakna.         │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ Tanaman [ sambiloto________________ ] [Cari]   ☐ sertakan seluruh genus                 │
│ Hasil takson: ( ) Andrographis paniculata (Burm.f.) Nees — spesies — Q…                 │
├──────────────────────────────────────────────┬──────────────────────────────────────────┤
│ Saring: MW [0]–[900]  ☐ Lipinski ≤1 langgar   │  [pratinjau 2D senyawa terpilih]         │
│ QED ≥ [0,3]  ☐ hanya yang punya rujukan        │                                          │
│ ☐ stereo lengkap   Cari nama [_______]        │  Nama, rumus, MW, logP, QED              │
│ ┌──┬─────────────────┬─────┬────┬────┬──────┐ │  Rujukan (klik = buka DOI):              │
│ │☑ │ Nama            │ MW  │QED │Ruj.│Tahun │ │   • 10.xxxx/… (2019)                     │
│ │☑ │ andrografolida  │350,4│0,61│ 12 │ 2021 │ │  Lencana: PAINS / di luar Lipinski       │
│ └──┴─────────────────┴─────┴────┴────┴──────┘ │  [Buka di KNApSAcK] [Buka di Wikidata]   │
│ 214 senyawa · 37 dipilih                       │                                          │
├──────────────────────────────────────────────┴──────────────────────────────────────────┤
│ [Pilih semua] [Kosongkan] [Ekspor CSV…]          [Impor 37 ke proyek] (utama) [✕ Tutup] │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```
- Ukuran awal 1180×720, bisa dimaksimalkan.
- Tabel `kit.tabel(urut=True)`, kolom angka `kit.sel_angka`. Lencana peringatan `kit.lencana(.., "warn")`.
- Kosong/galat: pesan di tengah tabel ("Tidak ada senyawa berujuk untuk takson ini.") bukan kotak pesan.
- Mode pemula: saringan lanjut (stereo, genus) dilipat di bawah tombol "Saringan lain ▾".

---

## P4 — F2 Analisis MD lengkap

```text
Kerjakan fitur F2 "Analisis lintasan MD lengkap" VirmoDock 1.2. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

Baca dulu: RENCANA_PENGEMBANGAN.md §0 dan §3 F2; PROMPT_PENGEMBANGAN.md "Lampiran UI" + "UI F2";
core/md.py fungsi analisis_trajektori, _interaksi_frame, kabsch, rmsd, jalankan_tugas, tulis_dcd (cara frame
disimpan); ui/dialog_md.py (struktur tab hasil yang ada); core/grafik.py (cara membuat grafik).
PENTING: okupansi interaksi SUDAH ada (_interaksi_frame) — jangan buat ulang; perluas agar juga menyimpan
matriks residu×frame.

Tugas:
1. core/md_analisis.py (NumPy/SciPy saja, tanpa paket baru):
   radius_girasi(frames, massa, idx) ; sasa(frames, jari, idx, titik=92) Shrake–Rupley dengan cKDTree
   (pakai rdFreeSASA bila tersedia untuk validasi silang di uji) ; ikatan_h_per_frame(...) ;
   barcode_interaksi(...) -> {residu, matriks (RLE)} ; jarak_kunci(frames, i, j) ;
   pca(frames_ca) -> {proyeksi, varians_rasio, vektor} ; fel(proyeksi, T=300, bin=50) -> {G (kJ/mol), x, y, n_frame} ;
   klaster_ligan(frames, idx_ligan, ambang=2.0) -> [{anggota, medoid, ukuran}] ; blok_rata(nilai, n_blok=5) -> (rata, gs).
   Setiap fungsi mengembalikan peringatan teks bila datanya terlalu sedikit (mis. FEL < 500 frame).
2. md.jalankan_tugas: setelah analisis lama, panggil md_analisis dan simpan ke proyek.md[i]["analisis"] dengan
   "versi": 2; barcode RLE. MD lama (tanpa versi 2): tombol "Hitung analisis lanjutan" yang membaca DCD tersimpan.
3. Replika: opsi "Jumlah replika" (1–5, bawaan 1; saran 3) di pengaturan MD → benih acak berbeda → hasil per replika
   + rata-rata ± SD di tab Replika. Estimasi waktu dikali jumlah replika (pakai uji_kecepatan yang ada).
4. Ekspor klaster: medoid tiap klaster → PDB kompleks → tombol "Pakai sebagai reseptor ensemble" (masuk objek proyek).
5. UI sesuai "UI F2". Semua grafik bisa "Kirim ke komposer" dan "Simpan SVG/PNG".
6. Laporan: 5 figur standar (RMSD, RMSF, Rg, ikatan H, FEL) + tabel ringkas (rata ± SD) + kalimat konvergensi.
7. Uji dev/uji_md_analisis.py: lintasan sintetis (Rg konstan ± 0,01 Å; PCA PC1 > 90 % untuk gerak satu sumbu;
   SASA bola = 4πr² ± 2 %; FEL minimum di pusat; klaster 2 kelompok terpisah terdeteksi 2; RLE pulang-pergi).
   Lalu satu lintasan nyata dari dev/uji/md_gui/proyek_md.vmd (bila ada; bila tidak, LEWAT dengan pesan).
8. Penutup RENCANA §0.6.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

### UI F2 (tab hasil di dialog MD)

```
Tab: [Ringkasan] [Stabilitas] [Interaksi] [PCA & FEL] [Klaster] [Replika]

Ringkasan  — baris kartu (kit.baris_kartu):
  ┌RMSD ligan┐┌RMSD Cα┐┌Rg┐┌Ikatan H┐┌ΔG MM/GBSA┐   nilai = rata ± SD paruh kedua lintasan,
  └──────────┘└───────┘└──┘└────────┘└──────────┘   lencana: stabil / bergeser (> 3 Å) / belum konvergen
  kit.catatan(peringatan): "Satu replika 10 ns menunjukkan kestabilan lokal, bukan afinitas."

Stabilitas — pilihan [RMSD ▾ | RMSF | Rg | SASA] + grafik besar + garis rata-rata bergerak;
            sumbu waktu ns; RMSF dengan pita residu kantong diwarnai acc.
Interaksi  — kiri: tabel okupansi (residu, jenis, %) urut turun; kanan: barcode residu × waktu
            (baris = residu ≥ 10 % okupansi, warna per jenis interaksi dari token tema).
            Klik baris → sorot residu di viewer 3D.
PCA & FEL  — kiri: sebar PC1–PC2 diwarnai waktu; kanan: peta FEL 2D (kontur) + titik minimum;
            label % varians PC1/PC2; peringatan bila < 500 frame.
Klaster    — tabel klaster (ukuran %, RMSD rata-rata ke medoid) + tombol [Tampilkan medoid] [Pakai sebagai reseptor ensemble].
Replika    — tabel per replika + baris rata ± SD; grafik RMSD tumpuk semua replika (warna kategori tema).
Bawah      — [Kirim ke komposer] [Simpan figur…] [Ekspor CSV…]               [✕ Tutup]
```

---

## P5 — F11 Paket validasi protokol *(bergantung: P1)*

```text
Kerjakan fitur F11 "Paket validasi protokol" VirmoDock 1.2. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

Baca dulu: RENCANA_PENGEMBANGAN.md §0 dan §3 F11; PROMPT_PENGEMBANGAN.md "Lampiran UI" + "UI F11";
fungsi validasi redocking yang ada (cari "validasi_redocking" di ui/ dan core/); core/uji.py (AUC, BEDROC, EF,
logAUC, bootstrap); core/qc.py (PoseBusters); core/chembl.py; core/pustaka.py (COCONUT lokal); ui/tab_uji.py.

Tugas:
1. core/decoy.py — pembuat decoy gaya DUD-E lokal:
   pilih_aktif(target_chembl, pchembl_min=7, maks=50) -> beragam kerangka (Butina 0,6 pada Morgan2);
   buat_decoy(aktif, kumpulan, per_aktif=50) -> cocokkan MW ±25, logP ±0,5, HBD ±1, HBA ±1, rotatable ±1,
   muatan bersih sama; Tanimoto Morgan2 maks ke SEMUA aktif < 0,3; kumpulan = COCONUT lokal + ChEMBL lokal bila ada,
   jika tidak ada: unduh sampel ZINC/ChEMBL lewat sumber_data dengan izin pengguna (tanya di UI, jangan diam-diam).
   Laporkan "kemiripan sifat aktif vs decoy" (uji KS per sifat) agar decoy terbukti tidak bias.
2. core/validasi_protokol.py — orkestrasi: redocking (pakai yang ada) → cross-docking bila ≥ 2 struktur PDB
   target yang sama ada di proyek → enrichment (job docking aktif+decoy lewat antrean yang ada) → PoseBusters →
   ringkasan dict + paragraf metode + daftar figur.
3. UI sesuai "UI F11": wizard di tab Uji (tombol "Paket validasi protokol…").
4. Keluaran: satu halaman ringkasan (HTML & Word lewat laporan yang ada) + figur ROC, enrichment semilog,
   overlay redocking, matriks cross-docking; paragraf metode menyebut jumlah aktif/decoy, kriteria, nilai.
5. Uji dev/uji_validasi_protokol.py: decoy dari himpunan sintetis memenuhi semua batas; tidak ada decoy dengan
   Tanimoto ≥ 0,3; KS tidak signifikan untuk MW; orkestrasi berjalan pada proyek 1HSG mini dengan 5 aktif × 5 decoy
   (exhaustiveness 4) dan menghasilkan semua kunci ringkasan.
6. Penutup RENCANA §0.6.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

### UI F11 (wizard 4 langkah)

```
Langkah 1 Redocking     : status ✓/✗ + RMSD + gambar overlay  [Jalankan ulang]
Langkah 2 Cross-docking : daftar struktur PDB target di proyek (centang) → matriks RMSD (peta panas)
                          lencana info bila < 2 struktur: "Dilewati — butuh ≥ 2 struktur."
Langkah 3 Enrichment    : Target ChEMBL [CHEMBL___] [Ambil aktif] · aktif: 42 · decoy per aktif [50]
                          tabel sifat aktif vs decoy (rata ± SD, p KS) → [Jalankan docking N ligan]
                          (estimasi waktu dari kemampuan laptop yang sudah ada)
Langkah 4 Ringkasan     : kartu RMSD · AUC · BEDROC · EF1% · % lolos PoseBusters, masing-masing lencana
                          ok/warn/bad dengan ambang tertulis; [Salin paragraf metode] [Laporan…] [Kirim figur ke komposer]
Navigasi bawah: [‹ Kembali] [Lanjut ›] (utama)                                         [✕ Tutup]
```

---

## P6 — F3a Penargetan balik *(bergantung: P1, P3)*

```text
Kerjakan F3 tahap a "Penargetan balik" VirmoDock 1.3. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

Baca dulu: RENCANA_PENGEMBANGAN.md §0, §3 F3 (termasuk peringatan ilmiah), §5; PROMPT_PENGEMBANGAN.md
"Lampiran UI" + "UI F3"; core/antrean.py (cara membuat job massal); core/chembl.py; core/rcsb.py;
core/prep_reseptor.py; fungsi redocking yang ada; core/konsensus.py (peringkat gabungan).

Sebelum mulai, TANYA pengguna (AskUserQuestion) bila belum diputuskan: 2 kelas penyakit untuk panel pertama
(bawaan bila tak dijawab: antibakteri + antiinflamasi) dan izin unduh ChEMBL ringkas (±1–2 GB mentah).

Tugas:
1. dev/susun_panel.py (alat pengembang, bukan fitur aplikasi): daftar PDB ID per kelas (≥ 25 target/kelas,
   resolusi ≤ 2,5 Å, ligan ko-kristal mirip obat) → unduh → bersihkan (prep_reseptor) → redocking → simpan hanya
   RMSD ≤ 2 Å ke data/panel_target/<kelas>.json: {uniprot, gen, nama, pdb, rantai, ligan_kristal, pusat, ukuran,
   rmsd_redocking, resolusi, tanggal}. Juga 50 umpan acak per target (docking skor) untuk z-skor → disimpan di JSON
   yang sama (rata, sd). Tulis berkas PDBQT reseptor siap pakai ke data/panel_target/<kelas>/.
2. core/target_balik.py:
   jalur_ligan(smiles, sumber="chembl_lokal"|"chembl_api", k=5) -> [{target, skor_max, skor_knn, contoh_ligan}] ;
   jalur_struktur(lig, kelas, exhaustiveness=8) -> buat job di antrean (satu per target) ;
   kumpulkan(proyek, kelas) -> z-skor per target ; gabung(peringkat_ligan, peringkat_struktur) Borda + label
   kepercayaan (tinggi bila keduanya ≤ 10 besar).
3. UI sesuai "UI F3" (tab Penargetan balik). Docking massal memakai antrean yang ada (bisa jeda/lanjut).
4. Data: proyek.target_balik = [{ligan_id, kelas, hasil: [...], parameter, jejak}].
5. Uji dev/uji_target_balik.py: panel mini 5 target (dibuat skrip dari panel nyata) ; z-skor benar pada data sintetis ;
   Borda benar ; ibuprofen → PTGS1/PTGS2 masuk 2 teratas jalur ligan (luring dengan data ChEMBL mini tersimpan).
6. Dokumen + paragraf metode dengan peringatan "hipotesis, butuh validasi eksperimen".
7. Penutup RENCANA §0.6.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

### UI F3 (satu dialog, dua tab — tab Jaringan diisi P7)

```
┌ Penargetan balik & jaringan ───────────────────────────────────────────────────────────┐
│ [kit.judul] Mencari target protein untuk senyawa                                       │
│ kit.catatan(peringatan): "Hasil adalah hipotesis. Klaim mekanisme memerlukan uji       │
│ eksperimen (pedoman BCPT 2025)."                                                        │
├ [Penargetan balik] [Jaringan & jalur] ──────────────────────────────────────────────────┤
│ Senyawa: [☑ kurkumin ☑ demetoksikurkumin …]   Kelas panel: [Antiinflamasi ▾] (28 target)│
│ Jalur: ☑ berbasis ligan (ChEMBL)  ☑ berbasis struktur (docking panel)                   │
│ Estimasi: 2 senyawa × 28 target ≈ 45 menit            [Mulai] (utama)  [Jeda]           │
│ ┌───┬──────────┬─────────┬────────────┬────────────┬─────────┬──────────┐               │
│ │ # │ Target   │ Gen     │ Ligan(Tan.)│ Struktur z │ Borda   │ Keyakinan│               │
│ │ 1 │ COX-2    │ PTGS2   │ 0,62       │ −2,4       │ 1       │ [tinggi] │               │
│ └───┴──────────┴─────────┴────────────┴────────────┴─────────┴──────────┘               │
│ Klik baris → buka pose di viewer + interaksi; kanan: ligan ChEMBL paling mirip (2D).    │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ [Ekspor CSV…] [Salin paragraf metode]      [Kirim target terpilih ke Jaringan ›] [✕ Tutup]│
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## P7 — F3b Jaringan & pengayaan *(bergantung: P6)*

```text
Kerjakan F3 tahap b "Jaringan & pengayaan jalur" VirmoDock 1.3. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

Baca dulu: RENCANA_PENGEMBANGAN.md §3 F3 + §5; PROMPT_PENGEMBANGAN.md "Lampiran UI" + "UI F3b";
core/graf.py dan core/sumber_data.py (P1); core/target_balik.py dan ui/dialog_target_balik.py (P6).

Verifikasi dulu (sumber resmi, catat ke RENCANA): lisensi & endpoint Open Targets Platform GraphQL, berkas GMT
Reactome (lisensi CC BY 4.0?), GO GMT manusia, API STRING (lisensi, batas laju). KEGG HANYA tautan luar.
Unduhan GMT ke data/gmt/: minta izin pengguna dulu (AskUserQuestion) dengan ukuran.

Tugas:
1. core/pengayaan.py: baca_gmt(path) ; hipergeometrik(gen, set_gen, latar) + Benjamini–Hochberg ;
   keluaran [{jalur, n_overlap, n_set, p, q, gen}]. Latar = gen panel / anotasi (jelaskan di laporan).
2. core/jaringan.py: bangun(senyawa→target dari P6, target→jalur dari pengayaan, target↔target STRING ambang s,
   target→penyakit Open Targets skor ≥ 0,5) -> networkx.Graph berlapis atribut jenis ;
   metrik (derajat, betweenness, closeness) ; sensitivitas(ambang_STRING=[0.4,0.7,0.9], ambang_target=[…]) ->
   simpul inti stabil (muncul di ≥ 80 % kombinasi) ; semua permintaan via sumber_data (Jejak tercatat).
3. UI tab "Jaringan & jalur" sesuai "UI F3b".
4. Ekspor GraphML + CSV tepi (Cytoscape) + SVG/PNG (komposer).
5. Uji dev/uji_jaringan.py: pengayaan pada set gen sintetis dengan jawaban diketahui (q terkecil benar) ;
   BH benar vs scipy/statsmodels manual ; graf sintetis → simpul inti stabil sesuai harapan ; GraphML pulang-pergi.
6. Paragraf metode WAJIB memuat: basis data + versi + tanggal, ambang tiap tepi, hasil uji sensitivitas, latar
   pengayaan, kalimat "hipotesis".
7. Penutup RENCANA §0.6.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

### UI F3b

```
Tab [Jaringan & jalur]
Atas   : Ambang STRING [0,7 ▾]  Skor penyakit ≥ [0,5]  Lapisan: ☑ senyawa ☑ target ☑ jalur ☑ penyakit
         [Bangun jaringan] (utama)   [Uji sensitivitas]
Tengah : kiri 65 % kanvas graf (SVG, zoom gulir, geser seret; warna simpul per lapisan dari token kategori,
         ukuran ∝ derajat; simpul inti stabil bertepi tebal acc) ;
         kanan 35 % tab kecil [Jalur] tabel pengayaan (jalur, overlap, q) · [Simpul] tabel metrik ·
         [Sensitivitas] daftar simpul inti + % kemunculan.
Klik simpul target → tampil pose docking target itu; klik jalur → sorot gen anggota.
Bawah  : [Ekspor GraphML…] [Ekspor CSV…] [Kirim ke komposer] [Salin paragraf metode]      [✕ Tutup]
Kosong : "Belum ada target. Jalankan penargetan balik di tab sebelah atau tempel daftar gen [Tempel…]".
```

---

## P8 — F5 QSAR *(bergantung: P1)*

```text
Kerjakan F5 "QSAR & model ML" VirmoDock 1.4. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).
scikit-learn 1.9.1 dan chemprop 2.3.1 SUDAH terpasang — jangan pasang paket lain.

Baca dulu: RENCANA_PENGEMBANGAN.md §0, §3 F5, §5; PROMPT_PENGEMBANGAN.md "Lampiran UI" + "UI F5";
core/chembl.py (format data aktivitas); core/mmp.py (activity cliff); core/kontribusi.py (peta atom);
core/admet.py (cara memanggil chemprop di proses terpisah); ui/panel_hasil.py (cara menambah kolom).

Tugas:
1. core/qsar.py: muat_data(csv|chembl) dengan konversi satuan → pIC50 ; kurasi (standarisasi seperti F1,
   gabung duplikat median, tandai rentang > 1 log, tandai activity cliff) ; fitur(deskriptor RDKit 2D tersaring,
   Morgan2 2048, MACCS, gabungan) ; bagi(acak|kerangka, uji=0.2, benih) ; latih(model, fitur, penyetelan CV5
   di dalam set latih) untuk RF, SVR, kNN, GP, Ridge (+ klasifikasi) ; validasi(): Q², R²_pred, RMSE, MAE,
   Golbraikh–Tropsha, ROC-AUC/MCC/BA ; y_acak(n=50) ; domain(leverage h*, kNN Tanimoto) ; kepentingan_permutasi ;
   simpan/muat model joblib + kartu_model.json (data hash, fitur, metrik, versi paket, tanggal).
2. core/konformal.py: split conformal regresi & klasifikasi (90 %), ±40 baris, tanpa paket baru.
3. Opsi Chemprop D-MPNN: pelatihan di proses terpisah (pola admet), batas waktu & batal; dinonaktifkan bila
   data < 200 senyawa (pesan jelas).
4. UI wizard sesuai "UI F5". Pelatihan > 5 s di proses/utas dengan kit.sibuk.
5. Prediksi ligan proyek → kolom panel Hasil "pIC50 prediksi" (± interval, ikon "di luar domain").
6. Uji dev/uji_qsar.py: data publik kecil berlisensi terbuka disimpan di dev/data/ (verifikasi lisensi) →
   RF R²_uji ≥ 0,7 (pembagian acak); Y-acak R² rata < 0,2; cakupan konformal 0,85–0,95; domain menandai
   senyawa sintetis yang jauh; simpan-muat model menghasilkan prediksi identik.
7. Laporan: tabel metrik kedua pembagian, plot prediksi vs terukur, plot Williams, Y-acak, kartu model; kalimat
   prinsip OECD.
8. Penutup RENCANA §0.6.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

### UI F5 (wizard 5 langkah)

```
1 Data      : [Dari ChEMBL proyek ▾ | Impor CSV…] → pratinjau tabel (SMILES, nilai, satuan, pIC50)
              kartu: n senyawa · rentang pIC50 · duplikat digabung · baris gagal [lihat]
2 Kurasi    : daftar peringatan (activity cliff, rentang duplikat besar) dengan centang "buang"
              histogram pIC50
3 Model     : Jenis [Regresi ▾]  Fitur [Morgan2 ▾]  Algoritma ☑RF ☐SVR ☐kNN ☑GP ☐Ridge ☐Chemprop
              Pembagian ☑ acak ☑ kerangka   Benih [42]       [Latih] (utama)
4 Validasi  : tabel model × metrik (dua pembagian) – terbaik ditandai ok; grafik [Prediksi vs terukur ▾ |
              Williams | Y-acak | Kepentingan fitur]; catatan peringatan bila R²_kerangka ≪ R²_acak
5 Prediksi  : ligan proyek → tabel (pIC50 ± interval, domain ✓/✗) [Tulis ke panel Hasil] [Simpan model…]
              [Salin paragraf metode] [Laporan…]
```

---

## P9 — F4 Farmakofor & bentuk

```text
Kerjakan F4 "Penapisan berbasis ligan 3D" VirmoDock 1.4. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

Baca dulu: RENCANA_PENGEMBANGAN.md §0, §3 F4; PROMPT_PENGEMBANGAN.md "Lampiran UI" + "UI F4";
core/kemiripan.py (fitur farmakofor yang sudah ditampilkan); core/uji.py (AUC/BEDROC/EF);
viewer.js (cara menambah bentuk 3D, cari fungsi VM.*); core/pustaka.py.
Cek: rdkit.Chem.rdShapeAlign tersedia? (hasil P0). Bila tidak, pakai rdMolAlign.O3A + rdShapeHelpers.

Tugas:
1. core/farmakofor.py: kueri_dari_pose(mol, protein=None, fitur_aktif, toleransi=1.0, eksklusi=True) ;
   konformer(mol, n=30, prune=0.5) ETKDGv3 ; cocokkan(kueri, mol) -> {n_cocok, rmsd_fitur, konformer_terbaik} ;
   saring_pustaka(kueri, daftar, n_proses, batal, progres) di proses terpisah per kelompok 500.
2. core/bentuk.py: skor_bentuk(ref, mol) -> {tanimoto_bentuk, tanimoto_warna, gabungan} + mol terselaraskan.
3. Skor akhir = 0,5·farmakofor ternormalisasi + 0,5·bentuk-warna (bobot dapat diatur).
4. Validasi bawaan: bila tab Uji punya aktif/decoy → AUC, BEDROC, EF1 % untuk kueri saat ini.
5. viewer.js: VM.tampilFarmakofor(fitur) bola transparan per jenis (warna token: donor, akseptor, aromatik,
   hidrofobik, ion+, ion−) + bola eksklusi abu-abu; VM.hapusFarmakofor().
6. UI sesuai "UI F4". Hasil teratas → [Kirim N teratas ke docking] (buat job di antrean).
7. Uji dev/uji_farmakofor.py: kueri dari MK1 (1HSG) → MK1 sendiri skor maksimum; molekul acak skor rendah;
   10 000 senyawa sintetis (dari COCONUT lokal bila ada) < 15 menit atau LEWAT dengan pesan; skor bentuk molekul
   ke dirinya = 1 ± 0,01.
8. Penutup RENCANA §0.6.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

### UI F4

```
Kiri 30 %  : Sumber kueri [Pose aktif ▾ | Ligan ko-kristal | Ligan proyek…]
             daftar fitur (centang, jenis, koordinat ringkas, toleransi spin 0,5–2,0 Å)
             ☑ volume eksklusi protein (4 Å)   Bobot farmakofor/bentuk [slider 0–1]
             Pustaka [COCONUT lokal ▾ | Ligan proyek | Berkas SDF/SMI…]  Konformer/senyawa [30]
             [Saring] (utama)  [Batal]   bilah progres + estimasi
Tengah     : viewer 3D (kueri bola fitur + senyawa terpilih terselaraskan)
Kanan 35 % : tabel hasil (rank, nama, n fitur cocok, RMSD fitur, bentuk, warna, gabungan) urut;
             kotak validasi (bila ada aktif/decoy): AUC · BEDROC · EF1% dengan lencana
Bawah      : [Ekspor SDF terselaraskan…] [Kirim 100 teratas ke docking] [Salin paragraf metode]  [✕ Tutup]
```

---

## P10 — F12 Pelacak hipotesis *(bergantung: P8)*

```text
Kerjakan F12 "Pelacak hipotesis → uji lab" VirmoDock 1.4. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

Baca dulu: RENCANA_PENGEMBANGAN.md §3 F12; "Lampiran UI"; core/proyek.py (eksperimen); core/labplanner.py;
ui/dialog_labplanner.py; core/statistik.py; core/qsar.py (P8).

Tugas:
1. Perluas proyek.eksperimen: entri {id, ligan_id, assay, nilai, satuan, pIC50, tanggal, catatan, status_hipotesis
   (diajukan|diuji|didukung|ditolak)}. Migrasi data lama tanpa kehilangan isi.
2. core/hipotesis.py: bandingkan(prediksi: ΔG, MM/GBSA, pIC50_pred, konsensus) vs terukur → Spearman ρ, Kendall τ
   (+ CI bootstrap 1000×), n; peringatan bila n < 8.
3. UI: tab "Hipotesis" di dialog Rencana lab: tabel ligan × (prediksi, terukur, status) ; impor hasil plate reader
   CSV ; grafik prediksi vs terukur per jenis prediksi ; tombol [Latih ulang QSAR dengan data baru] (memanggil P8).
4. Uji dev/uji_hipotesis.py: korelasi sintetis diketahui; migrasi proyek lama.
5. Penutup RENCANA §0.6.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 10 baris.
```

---

## P11 — F6 Konsensus docking × co-folding

```text
Kerjakan F6 "Konsensus docking × co-folding" VirmoDock 1.5. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

Baca dulu: RENCANA_PENGEMBANGAN.md §3 F6 + §5; "Lampiran UI" + "UI F6"; core/lanjutan.py (Boltz lewat WSL:
status, perintah, folder keluaran); core/qc.py (PoseBusters); core/konsensus.py; md.kabsch; analisis IFP.
Verifikasi di WSL: versi Boltz terpasang dan NAMA KUNCI keluaran afinitas (mis. affinity_pred_value,
affinity_probability_binary) dari berkas keluaran nyata — jangan dari ingatan.

Tugas:
1. core/kofolding.py: jalankan(seq_reseptor, smiles, n_sampel=5, afinitas=True) via lanjutan (WSL) ;
   baca_keluaran(folder) ; sejajarkan_ke_reseptor(struktur, reseptor_proyek, residu_kantong) Kabsch Cα ;
   banding(pose_docking, pose_cofold) -> {rmsd, ifp_tanimoto, posebusters_docking, posebusters_cofold} ;
   label(…) -> Sepakat | Sebagian | Bertentangan dengan aturan tertulis ;
   kebaruan(smiles) -> Tanimoto maks ke ligan PDB (RCSB chemical search via sumber_data, cache) + peringatan < 0,3.
2. Kolom baru di konsensus: "Boltz-2 afinitas" dan "Kesepakatan".
3. UI sesuai "UI F6" (tab di Properti pose + kolom konsensus).
4. Uji dev/uji_kofolding.py: keluaran Boltz tersimpan (dev/data/boltz_1hsg/) → pembacaan, penyelarasan, label;
   bagian WSL nyata di belakang --daring.
5. Dokumen: jelaskan kebocoran data latih (1HSG ada di PDB → kesepakatan tinggi bukan bukti).
6. Penutup RENCANA §0.6.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

### UI F6

```
Panel Properti, tab baru [Co-folding]:
  status Boltz (terpasang/tidak + tautan petunjuk) · [Jalankan co-folding untuk ligan ini] (utama)
  kartu: RMSD docking↔co-folding · IFP Tanimoto · PoseBusters (docking / co-folding) · afinitas Boltz-2
  lencana besar: Sepakat (ok) / Sebagian (warn) / Bertentangan (bad)
  kit.catatan(peringatan) kebaruan: "Ligan mirip ≤ 0,3 dengan ligan PDB — keyakinan co-folding rendah."
  sakelar viewer: ☑ pose docking (warna ligan) ☑ pose co-folding (warna acc, transparan)
Dialog Konsensus: kolom tambahan + saringan "hanya Sepakat".
```

---

## P12 — F10 Docking peptida *(bergantung: P11)*

```text
Kerjakan F10 "Docking peptida" VirmoDock 1.5. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

Baca dulu: RENCANA_PENGEMBANGAN.md §3 F10; "Lampiran UI"; core/kofolding.py (P11); core/md.py (minimisasi,
mmgbsa_pose); core/ppi.py (analisis antarmuka).
Cek lisensi AutoDock CrankPep (ADCP) dari sumber resmi; bila tidak jelas/bukan open-source, JANGAN dipakai.

Tugas:
1. core/peptida.py: validasi_sekuens (≤ 30 residu, 20 standar + daftar non-standar yang didukung Boltz) ;
   cofold_peptida(seq_reseptor, seq_peptida, n=5) via kofolding ; pemurnian(minimisasi + 100 ps implisit OpenMM) ;
   mmgbsa ; antarmuka via ppi.
2. UI: Siapkan › Langkah 2 · Ligan › "Peptida dari sekuens…": kotak sekuens (huruf satu), validasi langsung
   (residu tak dikenal disorot merah), [Jalankan] → hasil sebagai objek kompleks + tabel antarmuka.
3. Uji dev/uji_peptida.py: validasi sekuens; keluaran Boltz tersimpan MDM2–p53 (1YCR) → RMSD Cα peptida < 3 Å
   setelah penyelarasan (luring); nyata di belakang --daring.
4. Penutup RENCANA §0.6.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 10 baris.
```

---

## P13 — F7 Sifat elektronik xTB *(butuh izin unduh)*

```text
Kerjakan F7 "Sifat elektronik kuantum (xTB)" VirmoDock 1.5. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

Langkah 0 (wajib): verifikasi dari GitHub resmi grimme-lab/xtb versi rilis terbaru, lisensi (LGPL-3.0?), ukuran
biner Windows; juga status g-xTB (ada rilis resmi? lisensi?). Tanya izin unduh ke pengguna (AskUserQuestion) dengan
nama berkas, sumber, ukuran. Pasang ke vendor/bin/xtb/ ; tambahkan ke LISENSI_PIHAK_KETIGA dan spec PyInstaller.

Baca dulu: RENCANA_PENGEMBANGAN.md §3 F7; "Lampiran UI" + "UI F7"; core/lanjutan.cari_program; pola proses
terpisah di core/md.py; core/metabolisme.py; viewer.js (permukaan).

Tugas:
1. core/xtb.py: tersedia() ; hitung(mol, pelarut="water", fukui=True, esp=True, batas=300, batal) di proses
   terpisah, folder kerja sementara ; urai xtbout.json / fukui / charges / esp ; deskriptor: HOMO, LUMO, celah,
   η, μ, ω, dipol ; paralel per inti CPU untuk banyak ligan.
2. UI sesuai "UI F7"; atom diwarnai Fukui di viewer; permukaan ESP; korelasi otomatis dengan SoM CYP.
3. Kalimat wajib di dialog & laporan: "GFN2-xTB semi-empiris; celah HOMO–LUMO cenderung lebih kecil dari DFT,
   pakai untuk tren antar-ligan, bukan nilai absolut. Bukan DFT."
4. Uji dev/uji_xtb.py: benzena > anilin dalam celah HOMO–LUMO; f⁻ anilin terbesar di orto/para; LEWAT bila xtb absen.
5. Penutup RENCANA §0.6 (+ uji mandiri aplikasi: tambah butir "xTB" di core/ujimandiri.py).
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

### UI F7

```
Analisis › Sifat ligan dan desain › "Sifat elektronik (xTB)…"
Kiri  : daftar ligan (centang) · Pelarut [air ▾ | vakum | DMSO] · ☑ Fukui ☑ ESP · [Hitung] (utama) [Batal]
Tengah: tabel ligan × HOMO (eV) · LUMO · celah · η · ω · dipol (D), urut; kartu ligan terpilih
Kanan : viewer — mode [ESP permukaan | Fukui f⁻ | Fukui f⁺ | muatan]; skala warna divergen dari token tema + legenda
Bawah : kit.catatan(peringatan) kalimat wajib · [Ekspor CSV…] [Kirim ke komposer] [Salin paragraf metode] [✕ Tutup]
```

---

## P14 — F8 Desain generatif *(butuh izin unduh)*

```text
Kerjakan F8 "Desain generatif terpandu docking" VirmoDock 1.6. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

Langkah 0: verifikasi CReM (lisensi BSD-3?, versi, ukuran DB fragmen yang tersedia, cara membuat DB kecil sendiri
dari ChEMBL lokal). Tanya izin pengguna untuk paket crem + DB (sebut ukuran). Bila DB terlalu besar, buat DB kecil
dari COCONUT/ChEMBL lokal dengan alat CReM.

Baca dulu: RENCANA_PENGEMBANGAN.md §3 F8; "Lampiran UI" + "UI F8"; core/fbdd.py; core/mpo.py; core/sascore.py;
core/antrean.py; core/graf.py.

Tugas:
1. core/generatif.py: generasi(induk, operasi=mutate|grow|link, radius=2, maks=500) ; saring(PAINS, Brenk,
   SA ≤ 4, QED ≥ 0,4, MPO, kebaruan < 0,8) ; docking_cepat (exh 4) → 20 teratas docking penuh ;
   pareto(ΔG, QED, SA) ; siklus(n_generasi=3, batal, progres) di proses terpisah ; silsilah (graf induk→anak).
2. UI sesuai "UI F8". Semua kandidat bisa diimpor sebagai ligan proyek dengan l["asal"]={"sumber":"generatif",…}.
3. Uji dev/uji_generatif.py: dari MK1 generasi 1 ≥ 50 analog valid, tanpa duplikat InChIKey, semua lolos sanitasi;
   pareto benar pada data sintetis.
4. Penutup RENCANA §0.6.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

### UI F8

```
Kiri  : Induk [pose aktif ▾] · Operasi ☑ mutate ☑ grow ☐ link · Radius [2] · Generasi [3] · Kandidat/gen [500]
        Saringan: SA ≤ [4] QED ≥ [0,4] ☑ PAINS ☑ Brenk · kebaruan Tanimoto < [0,8]   [Mulai] (utama) [Batal]
Tengah: grafik front Pareto (ΔG × QED, ukuran titik = SA, warna = generasi); klik titik → pratinjau 2D + pose
Kanan : pohon silsilah (graf) + tabel kandidat (generasi, ΔG, QED, SA, perubahan dari induk)
Bawah : [Impor terpilih ke proyek] [Ekspor SDF…] [Salin paragraf metode]                       [✕ Tutup]
```

---

## P15 — F9 RBFE eksperimental *(butuh izin unduh, butuh GPU)*

```text
Kerjakan F9 "Energi bebas relatif (RBFE) eksperimental" VirmoDock 1.6. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

Langkah 0: verifikasi OpenFE (versi terbaru, lisensi MIT?, dependensi: kartograf/lomap, gufe, openmmtools) dan
kecocokan dengan openmm 8.6.1 + tumpukan OpenFF yang SUDAH terpasang (daftar di CATATAN_TAHAP2 §4l). Simpan daftar
paket sebelum pemasangan (pip freeze > build/pip_sebelum_rbfe.txt). Tanya izin pengguna (daftar paket + ukuran).
Bila konflik versi dengan tumpukan MD yang ada → BERHENTI dan laporkan; jangan memaksa upgrade.

Baca dulu: RENCANA_PENGEMBANGAN.md §3 F9; "Lampiran UI"; core/md.py (platform_terbaik, uji_kecepatan, pola tugas);
core/mmp.py (pasangan kongenerik).

Tugas:
1. core/rbfe.py: pasangan_dari_mmp(seri) (perubahan ≤ 10 atom berat) ; peta_atom ; jaringan(bintang|MST) ;
   jalankan_tepi(λ=11, replika=3, ns_per_λ) di proses terpisah dengan jeda/lanjut ; analisis MBAR ; ΔΔG ± galat ;
   siklus tertutup (cycle closure) sebagai cek konsistensi.
2. UI: dialog "Energi bebas relatif (eksperimental)": pilih seri dari MMP → graf perturbasi → estimasi waktu
   (wajib tampil sebelum mulai, dari uji_kecepatan) → jalankan → tabel ΔΔG + plot vs ΔΔG docking/terukur.
   Mode CPU dinonaktifkan dengan pesan jelas.
3. Uji dev/uji_rbfe.py: pemetaan atom pada pasangan benzena→toluena; jaringan benar; analisis MBAR pada data
   sintetis; simulasi nyata di belakang --daring --gpu.
4. Penutup RENCANA §0.6, label "eksperimental" di menu, dokumen, dan laporan.
Aturan: jangan commit/build/regresi penuh. Laporan akhir ≤ 15 baris.
```

---

## P-RILIS — Rilis versi (pakai ulang untuk 1.2, 1.3, …)

```text
Siapkan rilis VirmoDock <VERSI>. Folder: E:\Bikin Docking Simpel\VirmoDock.
Python: .venv/Scripts/python.exe (PYTHONIOENCODING=utf-8, PYTHONPATH=.).

1. Naikkan versi di virmodock/__init__.py; rapikan CHANGELOG.md bagian [<VERSI>] (tanggal hari ini, Baru/Diperbaiki/
   Diubah, tanpa duplikat).
2. pyflakes virmodock bersih.
3. i18n: dev/ekstrak_teks.py → terjemahkan sisa → dev/buat_kamus.py → dev/cek_mutu_i18n.py = 0.
4. Dokumen docs/*.html sesuai fitur baru; tutorial PDF hanya bila alur dasar berubah.
5. dev/siapkan_contoh.py lalu dev/regresi.py SEKALI. Tampilkan hanya ringkasan + nama uji gagal. Bila gagal:
   bedakan bug aplikasi vs bug uji; perbaiki; ulangi HANYA uji yang gagal.
6. Tambahkan uji fitur baru ke core/ujimandiri.py bila relevan (uji mandiri dalam aplikasi beku).
7. Perbarui CATATAN_TAHAP2.md (status versi, peta berkas) dan RENCANA_PENGEMBANGAN.md (tandai fitur selesai).
8. Laporkan ringkas; JANGAN commit dan JANGAN build — pengguna yang memutuskan.
```

## P-COMMIT

```text
Periksa git status di E:\Bikin Docking Simpel\VirmoDock. Tampilkan ringkasan berkas berubah (jumlah per folder).
Berkas tak terlacak yang tampak sementara (scratch/, *.tmp, keluaran uji) jangan ikut — tanyakan bila ragu.
Commit satu commit dengan pesan Conventional Commits Bahasa Indonesia: feat(<area>): <ringkasan versi>,
badan berupa poin per fitur. Jangan push. Laporkan hash.
```

## P-BUILD

```text
Build rilis VirmoDock dari commit terakhir. Folder: E:\Bikin Docking Simpel\VirmoDock.
Pastikan git status bersih (kecuali berkas tak terlacak yang memang diabaikan). Jalankan di latar belakang:
.venv/Scripts/python.exe build_tools/rilis.py > build/rilis_<versi>.log 2>&1
Setelah selesai: laporkan ukuran Setup & Portable, hasil uji mandiri, dan SHA256SUMS. Jangan ubah berkas sumber
selama build berjalan.
```

---

## Lampiran UI — aturan tampilan untuk semua fitur

### Penempatan menu

| Jenis fitur | Menu | Submenu yang sudah ada |
|---|---|---|
| Mendapatkan ligan (tanaman, peptida) | **Siapkan** | judul "Langkah 2 · Ligan" |
| Menilai pose/interaksi (co-folding) | **Analisis** | "Telaah pose dan interaksi" |
| Validasi (F11) | **Analisis** | "Validasi dan mutu" + tombol di tab Uji |
| Sifat & desain (xTB, generatif, QSAR) | **Analisis** | "Sifat ligan dan desain" |
| Penapisan (farmakofor, penargetan balik) | **Analisis** | "Penapisan banyak ligan" |
| MD, RBFE, jaringan | **Analisis** | "Simulasi dan penelitian lanjut" |

Format aksi: `A("Nama alat…", "<ikon>", self.buka_<nama>, None, "Tooltip satu–dua kalimat: apa yang dihitung
dan batasnya")`. Ikon yang tersedia (`ui/icons.py`): `lig rec target similar search chart table diagram cube
cpu gpu grid log microscope puzzle award link report water` dsb. — jangan menambah ikon kecuali perlu; bila perlu,
gambar sendiri dengan gaya garis yang sama (lihat `bentuk_organ.py`).
Tambahkan juga ke **palet perintah** (dict nama→fungsi di `mainwindow.py` ±baris 431).

### Tata letak dialog

- Kepala `kit.judul(judul, satu kalimat)`. Judul = kata benda ("Senyawa dari tanaman obat"), bukan perintah.
- Margin 14/12/14/12, jarak 10 (seperti `dialog_kantong.py`). Ukuran awal 1100–1280 × 700–760, dapat dimaksimalkan
  (`Qt.WindowMinMaxButtonsHint`). Uji pada mode ringkas (< 800 px tinggi): `dev/uji_tata_letak.py`.
- Struktur: **masukan kiri → hasil tengah/kanan → aksi bawah**. Wizard: langkah bernomor + [‹ Kembali] [Lanjut ›].
- Tombol bawah: `kit.bar_bawah(self, kiri=[ekspor/salin], kanan=[aksi utama])`; satu tombol utama saja.
- Setiap alat perkiraan: `kit.catatan("…batas metode…", "peringatan")` terlihat tanpa menggulir.
- Keadaan kosong & galat ditulis di dalam area hasil (teks muted, kalimat petunjuk langkah berikut), bukan kotak pesan.
- Proses: `kit.sibuk` (singkat) atau bilah progres + estimasi waktu + [Batal] (panjang). Tidak ada UI yang beku > 0,3 s.

### Angka, warna, teks

- Angka: `kit.f(v, d)` → koma desimal, minus asli. Satuan dengan spasi ("2,1 Å", "−7,4 kcal/mol").
- Warna: token tema saja (`kit.warna`, `kit.hx`); kategori grafik dari palet `grafik.py`; uji mode gelap.
- Teks antarmuka Bahasa Indonesia baku, kalimat pendek. Istilah asing baku dimiringkan hanya di dokumen, tidak di UI.
- Semua teks baru masuk kamus Inggris sebelum rilis (P-RILIS langkah 3).

### Mode pemula / ahli

- Pemula: tampilkan pilihan bawaan saja; pengaturan lanjut dilipat di "Pengaturan lain ▾".
- Ahli: semua parameter terlihat.
- Alat yang sangat lanjut (RBFE, generatif) hanya tampil di menu pada mode ahli, atau diberi lencana "lanjut".

### Viewer 3D

- Fungsi baru di `viewer.js` memakai awalan `VM.` dan selalu punya pasangan penghapus (`VM.hapus…`).
- Warna objek 3D dari token tema yang diteruskan Python (jangan heksadesimal di JS kecuali palet molekul).

### Figur & laporan

- Setiap grafik: [Simpan SVG/PNG] dan [Kirim ke komposer]; ukuran ekspor bawaan 2400 px @ 300 dpi.
- Setiap alat yang menghasilkan angka: [Salin paragraf metode] dengan sitasi ber-DOI terverifikasi.
- Data internet: jejak sumber otomatis masuk laporan (Fondasi P1).
