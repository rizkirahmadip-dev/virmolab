# Rencana Pengembangan Fitur VirmoLab 1.2 – 1.6

Status: **draf untuk diskusi**, belum diputuskan.
Disusun: 13 Oktober 2026, sesudah commit `585ab9f` (1.1.2).
Lokasi sementara: di luar `VirmoLab/` selama build berjalan — pindahkan ke `VirmoLab/RENCANA_PENGEMBANGAN.md`
setelah disepakati.

Cara membaca:
- **[ada]** = sudah ada di kode 1.1.2 (dicek dengan grep, bukan ingatan).
- **[cek]** = fakta eksternal (versi, lisensi, alamat API) yang **wajib diverifikasi ulang saat implementasi**;
  pencarian web 13 Okt 2026 tidak menemukan sumber resmi 2026 untuk butir itu.
- **[izin]** = butuh unduhan/paket baru → minta izin pengguna dulu (aturan proyek, `CATATAN_TAHAP2.md` §2).
- Ukuran: **S** ≈ 1 sesi kerja, **M** ≈ 2–3 sesi, **L** ≈ 4+ sesi.

---

## Daftar isi

0. Konvensi coding wajib (berlaku untuk semua fitur)
1. Peta kondisi sekarang & celah
2. Fondasi bersama (dikerjakan sekali, dipakai banyak fitur)
3. Fitur F1 – F12 (rinci)
4. Peta rilis 1.2 – 1.6
5. Risiko ilmiah & cara jujur melaporkannya
6. Pertanyaan yang perlu diputuskan pengguna

---

## 0. Konvensi coding wajib

Diambil dari kode dan catatan yang sudah ada. Setiap fitur baru **harus** mengikuti ini.

### 0.1 Susunan berkas per fitur

| Lapisan | Lokasi | Isi | Contoh pola yang sudah ada |
|---|---|---|---|
| Logika ilmiah | `virmolab/core/<nama>.py` | fungsi murni: masukan data → keluaran dict/list. **Tanpa impor Qt.** | `core/kantong.py`, `core/terowongan.py` |
| Dialog | `virmolab/ui/dialog_<nama>.py` | kelas `Dialog<Nama>(QDialog)` memakai `kit` | `ui/dialog_kantong.py`, `ui/dialog_terowongan.py` |
| Pembuka | `virmolab/ui/mainwindow_dialog.py` | metode `buka_<nama>(self)` di mixin `PembukaDialog` | `buka_kantong`, `buka_md` |
| Menu | `virmolab/ui/mainwindow.py` | `A("Label…", "ikon", self.buka_<nama>, None, …)` di submenu Analisis (±baris 947) + daftar nama di ±baris 431 (palet perintah) | `buka_kantong` |
| Uji inti | `dev/uji_<nama>.py` | uji tanpa GUI, pola `cek(kondisi, "pesan")` | `dev/uji_proyek.py` |
| Uji GUI | `dev/uji_dialog_lanjut_gui.py` | tambahkan `"<nama>"` ke `DIALOG` | — |
| Regresi | `dev/regresi.py` | tambahkan batas waktu bila > 120 s | `"uji_md_gui": 1200` |

### 0.2 Aturan dialog (`ui/kit.py`)

- Kepala: `lay.addWidget(kit.judul("Judul", "Satu kalimat penjelasan."))`.
- Bawah: `lay.addLayout(kit.bar_bawah(self, kiri=[…], kanan=[kit.tombol("Hitung", fn, utama=True)]))`.
- Tabel: `kit.tabel(kolom, regang=…, urut=True)`; angka: `kit.sel_angka(v, d=2, satuan="kcal/mol")`.
- Angka tampil: **selalu** `kit.f(v, d)` (koma desimal, minus asli U+2212).
- Warna: **hanya** token tema `kit.warna("ok"|"warn"|"bad"|"acc"|…)` / `kit.hx(...)` — tidak ada heksadesimal tetap.
- Hitungan > 0,3 s: `with kit.sibuk(self.l_status, "Menghitung …"):` atau `kit.bilah_sibuk()`.
- Data proyek: `kit.ligan_proyek(jw)`, `kit.reseptor_proyek(jw)`, `kit.pose_aktif(jw)`, `kit.pusat_kotak(jw)`.
- Catatan batas metode: `kit.catatan("…", "peringatan")` — setiap alat perkiraan **wajib** punya satu.

### 0.3 Pekerjaan berat

- Utas (I/O, internet, hitungan < 1 menit): `kerja.jalankan(fn, *arg, selesai=…, galat=…, log=…, progres=…)`.
- Proses terpisah (CPU berat, pustaka yang bisa crash, > 1 menit): pola `md.jalankan_tugas(f_tugas)` —
  tulis berkas tugas JSON → jalankan `python -m virmolab.<modul> tugas.json` → baca hasil.
  Wajib untuk: MD, FEP, xTB, generatif, pelatihan QSAR besar.
- Setiap tugas panjang: dukung **batal** (`berhenti=` callable) dan **jeda/lanjut** bila > 10 menit.

### 0.4 Data & reprodusibilitas

- Hasil disimpan di `proyek.json` dengan kunci baru di tingkat proyek **atau** di dict ligan `l[...]`.
  Tambahkan `data.setdefault("<kunci>", …)` di `core/proyek.py` (±baris 52) agar proyek lama tetap terbuka.
- Naikkan `VERSI_FORMAT` hanya bila struktur lama berubah; sediakan migrasi (sudah ada pola migrasi).
- **Setiap** data dari internet dicatat: nama basis data, versi/rilis, tanggal ambil, URL kueri
  → masuk paragraf metode laporan (lihat Fondasi §2.2).

### 0.5 Jebakan yang pernah terjadi (jangan diulang)

- Jangan menamai variabel lokal sama dengan modul yang diimpor (`kerja`, `kit`, `theme`, `md`, …).
  Pernah mematikan geser ligan dan GNINA tanpa pesan. `pyflakes` di CI menangkapnya — jalankan sebelum selesai.
- Logika tidak boleh membandingkan **teks** widget (rusak di mode Inggris) — pakai `itemData`/`property`.
- `RWMol.RemoveAtom` menggeser indeks; kumpulkan dulu, hapus terakhir.
- Heredoc Git Bash mengubah `\\n` — tulis skrip penyunting dengan alat Write.

### 0.6 Penutup setiap fitur (Definition of Done)

1. `core` + dialog + pembuka + menu + palet perintah.
2. `dev/uji_<nama>.py` lulus; dialog masuk `uji_dialog_lanjut_gui.py` (terang & gelap) dan lulus.
3. `.venv/Scripts/python.exe -m pyflakes virmolab` bersih.
4. i18n: `dev/ekstrak_teks.py` → terjemahkan ke `dev/i18n_tambahan.json` → `dev/buat_kamus.py`
   → `dev/cek_mutu_i18n.py` = 0 masalah.
5. Dokumen: bagian baru di `docs/panduan.html` (+ `docs/metode.html` untuk metode ilmiah & sitasi).
6. `CHANGELOG.md` bagian **Baru**; peta berkas di `CATATAN_TAHAP2.md`.
7. Paragraf metode otomatis + sitasi (DOI diverifikasi, bukan dari ingatan).
8. Regresi penuh **hanya** sebelum rilis, bukan per fitur.

---

## 1. Peta kondisi sekarang & celah

### 1.1 Yang sudah ada [ada]

Docking Vina / AutoDock-GPU / GNINA (WSL) / kovalen / residu fleksibel / blind docking; kantong (LIGSITE +
P2Rank); MD OpenMM + MM/GBSA + RMSD/RMSF + **okupansi interaksi per frame** (`md._interaksi_frame`) +
energi per residu (`core/energi_residu.py`); Boltz co-folding (WSL, `core/lanjutan.py`); ADMET-AI; ChEMBL;
COCONUT lokal (tanpa data organisme di skema `pustaka.KOLOM`); konsensus; kemiripan + PCA ruang kimia + fitur
farmakofor; FBDD; PROTAC; MMP; PPI; SoM CYP450; saluran akses; air sisi aktif; komposer figur; laporan &
naskah; statistik; konservasi; mutasi; plugin; CLI.

Paket terpasang yang relevan (dicek di `.venv`): scikit-learn 1.9.1, networkx 3.7, torch 2.14 (CPU),
chemprop 2.3.1, openmm 8.6.1, scipy 1.18, pandas 3.0, gemmi 0.7.5, dimorphite_dl 2.1, posebusters 0.6.5.
**Tidak** terpasang: mdtraj, MDAnalysis, plotly, xtb, CReM, OpenFE.

### 1.2 Celah utama

| Celah | Fitur pengisi |
|---|---|
| Cari senyawa **berdasarkan nama tanaman** | F1 |
| Analisis MD lanjutan (Rg, SASA, ikatan H per waktu, PCA, FEL, klaster, garis waktu interaksi) | F2 |
| Penargetan balik & farmakologi jaringan | F3 |
| Penapisan berbasis ligan 3D (farmakofor + bentuk) | F4 |
| QSAR / model ML dari data pengguna | F5 |
| Konsensus docking × co-folding + validitas fisik | F6 |
| Sifat elektronik kuantum (HOMO–LUMO, Fukui, ESP) | F7 |
| Desain generatif terpandu docking | F8 |
| Energi bebas relatif alkimia (FEP/RBFE) | F9 |
| Docking peptida | F10 |
| Validasi protokol docking terstandar (decoy, enrichment) untuk naskah | F11 |
| Pelacak hipotesis → uji lab (umpan balik eksperimen ke model) | F12 |

---

## 2. Fondasi bersama

Dikerjakan **sebelum** F1/F3 karena keduanya bergantung padanya.

### 2.1 `core/sumber_data.py` — klien internet bersama (S)

Masalah sekarang: `chembl.py`, `pustaka.py`, `rcsb.py`, `alphafold.py` masing-masing menulis logika
`requests` + batas waktu + coba ulang sendiri.

```python
# core/sumber_data.py
@dataclass
class Jejak:                       # dicatat ke proyek untuk paragraf metode
    sumber: str                    # "LOTUS (Wikidata)"
    versi: str                     # rilis/dump bila diketahui, "langsung" bila API hidup
    diambil: str                   # ISO 8601
    kueri: str                     # URL / SPARQL ringkas
    lisensi: str                   # "CC0 1.0"

def ambil_json(url, *, params=None, data=None, batas=30, coba=3, cache_jam=24*7) -> tuple[dict, Jejak]: ...
def sparql(endpoint, kueri, **kw) -> tuple[list[dict], Jejak]: ...
def cache_dir() -> Path            # paths.APPDATA / "cache_http" ; kunci = sha256(url+params)
```

- Cache berkas di `APPDATA/cache_http/` (JSON + metadata waktu); tombol "Hapus cache" di Pengaturan.
- Mode luring: bila tanpa internet dan cache ada → pakai cache + tandai `Jejak.versi = "cache <tanggal>"`.
- Batasi laju (`time.sleep`) per domain sesuai ketentuan layanan.
- Uji: `dev/uji_sumber_data.py` dengan server palsu lokal (`http.server` di utas) — tidak butuh internet.

### 2.2 Jejak proyek & paragraf metode otomatis (S)

- `proyek.jejak: list[dict]` (setdefault `[]`). Setiap fitur yang mengambil data memanggil
  `proyek.catat_jejak(jejak)`.
- `core/laporan.py`: bagian **"Sumber data"** — tabel sumber, versi, tanggal ambil, lisensi.
- `core/naskah.py`: paragraf metode dirakit dari jejak + parameter alat (pola "Salin paragraf metode" yang sudah ada
  di konsensus).

### 2.3 Graf & figur jaringan (S)

- `core/graf.py`: tata letak networkx (`spring_layout`, `kamada_kawai_layout`) → SVG sendiri
  (pola `grafik.py`, tanpa plotly). Simpul diberi warna token tema, ukuran ∝ derajat.
- Ekspor: SVG/PNG (komposer figur), **GraphML** & **CSV tepi** agar bisa dibuka di Cytoscape.

---

## 3. Fitur rinci

---

### F1. Tanaman obat → senyawa  ★★★  (M)

**Tujuan.** Ketik nama tanaman (Latin atau nama lokal) → daftar senyawa dengan struktur, rujukan, dan sifat →
pilih → impor ke proyek. Topik bahan alam adalah jenis penelitian docking farmasi paling umum di Indonesia.

**Dasar ilmiah & sumber data 2026**

| Sumber | Isi | Akses | Lisensi | Catatan |
|---|---|---|---|---|
| **LOTUS** via Wikidata | ±750 ribu pasangan struktur–organisme **berujuk** (DOI) | SPARQL `query.wikidata.org` | CC0 | sumber utama; tiap pasangan punya rujukan |
| **COCONUT 2.0** | ±695 ribu molekul, ±53 ribu organisme (Zenodo 13897048) | unduhan CSV/SDF penuh | CC BY 4.0 [terverifikasi 2026-10-13, sumber: https://doi.org/10.5281/zenodo.13897048] | berkas `coconut_complete-10-2024.csv.zip` (197,5 MB) memuat kolom `organisms`; URL tetap Zenodo |
| KNApSAcK | spesies–metabolit, kuat untuk Asia | situs web, tanpa API resmi | akademik | **jangan di-scrape**; hanya tautan "buka di KNApSAcK" |
| IMPPAT 2.0 | tanaman obat India | situs web | [cek] | tautan saja |
| Daftar nama lokal | sambiloto → *Andrographis paniculata* | **dibundel**: `data/nama_tanaman_id.csv` disusun manual dari Farmakope Herbal Indonesia / MMI | buat sendiri | ±300 tanaman umum; sumber per baris |

**Alur & desain**

1. Masukan: nama → resolusi taksonomi:
   - cari di `nama_tanaman_id.csv` (nama lokal → Latin);
   - resolusi Wikidata (`wdt:P225` taxon name, ikut sinonim `wdt:P1420`), tampilkan pilihan bila > 1 cocok;
   - opsi "sertakan genus" (mis. semua *Curcuma*) dengan peringatan jumlah.
2. Kueri LOTUS SPARQL (sketsa):
   ```sparql
   SELECT ?senyawa ?nama ?smiles ?inchikey ?rujukan WHERE {
     ?senyawa wdt:P703 ?takson .            # found in taxon
     ?takson wdt:P171* wd:Qxxxx .            # takson atau turunannya (opsi)
     ?senyawa wdt:P233|wdt:P2017 ?smiles ;   # canonical / isomeric SMILES
              wdt:P235 ?inchikey .
     OPTIONAL { ?senyawa p:P703 [ ps:P703 ?takson ; prov:wasDerivedFrom/pr:P248 ?rujukan ] . }
     OPTIONAL { ?senyawa rdfs:label ?nama FILTER(lang(?nama)="en") }
   } LIMIT 5000
   ```
   [terverifikasi 2026-10-13, sumber: https://query.wikidata.org]: P2017 (isomeric SMILES, menjaga stereo) dan P233 (canonical SMILES); kueri SPARQL memakai `COALESCE(?isomericSmiles, ?canonicalSmiles)` agar stereo diutamakan. Uji *Andrographis paniculata* (Q1551608) menghasilkan 159 senyawa (100% P233, 81% P2017).
3. Gabung dengan COCONUT lokal (bila diunduh versi penuh) melalui **InChIKey 14 karakter pertama**
   (kerangka) → buang duplikat, simpan semua rujukan.
4. Standarisasi: `rdMolStandardize` (pecahan terbesar, netralisasi, tautomer kanonik) → hitung sifat yang sudah ada
   (`core/sifat.py`, SAScore, QED, Lipinski, PAINS).
5. Penyaringan cepat di dialog: MW, Lipinski, QED, "punya stereokimia lengkap", "punya rujukan".
6. Impor → `proyek.ligan` dengan `l["asal"] = {"sumber": "LOTUS", "takson": …, "rujukan": [DOI…]}`.

**Berkas**

- `core/tanaman.py`
  ```python
  def cari_takson(nama: str) -> list[dict]          # [{qid, nama_ilmiah, peringkat, sinonim, sumber}]
  def senyawa_takson(qid: str, turunan=False, batas=5000) -> tuple[list[dict], Jejak]
  def gabung_coconut(daftar) -> list[dict]
  def standarisasi(daftar) -> list[dict]            # tambah inchikey, smiles_std, sifat, peringatan
  ```
- `core/pustaka.py`: tambahkan kolom `organisme` ke `KOLOM` + migrasi sqlite (buat ulang tabel bila kolom absen).
- `ui/dialog_tanaman.py` — tiga panel: (a) pencarian & pilihan takson, (b) tabel senyawa + saringan,
  (c) pratinjau 2D + rujukan (tautan DOI dapat diklik).
- `data/nama_tanaman_id.csv` — kolom: `nama_lokal, nama_ilmiah, famili, sumber`.
- Pembuka `buka_tanaman`, menu **Ligan › Senyawa dari tanaman…**; juga tab baru di Pustaka ligan.

**Uji** — `dev/uji_tanaman.py`
- Luring: respons SPARQL tersimpan (`dev/data/lotus_andrographis.json`) → `senyawa_takson` menghasilkan
  andrografolida (InChIKey `BOJKULTULYSRAS-OTESTREVSA-N` [terverifikasi 2026-10-13, sumber: https://pubchem.ncbi.nlm.nih.gov/compound/5318517]; catatan: `BOFKYY…` di draf awal keliru); kurkumin (InChIKey `VFLDPWHFBUODDF-FCXRPNKRSA-N` [terverifikasi 2026-10-13, sumber: https://pubchem.ncbi.nlm.nih.gov/compound/969516]); standarisasi tidak menghapus stereo.
- Daring (dilewati regresi, seperti `uji_chembl`): *Curcuma longa* ≥ 50 senyawa, kurkumin ada.

**Kriteria selesai**: sambiloto, kunyit, temulawak, jahe, sirih → masing-masing menghasilkan senyawa penanda
yang dikenal dalam ≤ 15 s (internet normal); setiap senyawa punya ≥ 1 rujukan atau ditandai "tanpa rujukan".

**Risiko**: nama lokal ambigu (beberapa spesies); data LOTUS mengandung laporan lama yang tidak tervalidasi →
tampilkan jumlah rujukan dan tahun.

---

### F2. Analisis lintasan MD lengkap  ★★★  (M)

**Tujuan.** Menutup analisis yang biasanya diminta reviewer setelah MD, tanpa paket baru.

**Sudah ada [ada]**: RMSD Cα & ligan, RMSF Cα (`md.analisis_trajektori`), frekuensi interaksi
(`md._interaksi_frame`), MM/GBSA, energi per residu, DCD + PDB.

**Ditambahkan** (`core/md_analisis.py`, NumPy saja, membaca frame yang sudah tersimpan):

| Analisis | Metode | Catatan ilmiah |
|---|---|---|
| Radius girasi protein | `Rg = sqrt(Σ mᵢ‖rᵢ − r_cm‖² / Σ mᵢ)` | stabilitas lipatan |
| SASA protein & ligan, ΔSASA terkubur | Shrake–Rupley, 92 titik/atom, jari-jari Bondi; vektorisasi `scipy.spatial.cKDTree` | [terverifikasi 2026-10-13, sumber: RDKit 2026.03.6 di .venv]: `rdkit.Chem.rdFreeSASA` tersedia di Windows (`CalcSASA`, `ShrakeRupley`); dipakai untuk validasi silang |
| Jumlah ikatan H per frame | kriteria yang sama dengan `analisis.interaksi` | konsisten dengan diagram docking |
| **Garis waktu interaksi** | matriks residu×frame (0/1) → peta panas "barcode" | sudah ada datanya, tinggal disimpan per frame (sekarang hanya frekuensi) |
| Jarak kunci | pengguna memilih 2 atom/residu → jarak vs waktu | mis. ligan–ASP25 |
| PCA Cα | superposisi ke rata-rata → kovarians → `numpy.linalg.eigh`; proyeksi PC1/PC2; % varians | |
| Lanskap energi bebas (FEL) | `G = −k_BT ln P(PC1,PC2)`, histogram 2D 50×50, `G − G_min` (kJ/mol) | **peringatan** bila frame < 500: FEL tidak konvergen |
| Klaster konformasi | RMSD ligan berpasangan → `scipy.cluster.hierarchy` (average) ambang 2 Å; frame perwakilan = medoid | ekspor PDB perwakilan untuk docking ulang (ensemble) |
| Konvergensi | rata-rata blok (block averaging) MM/GBSA & RMSD; galat standar blok | menghindari klaim berlebihan dari 1 replika |
| Replika | 3 replika dengan benih berbeda → rata-rata ± SD | praktik standar 2024+ untuk MD singkat |

**UI** — tab baru di `dialog_md.py`: *Ringkasan* · *Stabilitas* (RMSD/RMSF/Rg/SASA) ·
*Interaksi* (barcode + okupansi) · *PCA & FEL* · *Klaster* · *Replika*.
Semua grafik via `core/grafik.py` → bisa dikirim ke komposer figur.

**Data**: `proyek.md[i]["analisis"] = {"rg": […], "sasa": {...}, "hb": […], "barcode": {"residu": [...],
"matriks_rle": ...}, "pca": {...}, "fel": {...}, "klaster": [...], "versi": 2}` — barcode disimpan
**run-length encoded** agar `proyek.json` tidak membengkak.

**Uji** — `dev/uji_md_analisis.py`
- Lintasan sintetis (protein kaku + ligan bergeser terkendali): Rg konstan ± 0,01 Å; PCA PC1 menangkap > 90 %
  varians gerak sinusoidal; FEL minimum di posisi rata-rata.
- SASA bola tunggal jari-jari r = 4πr²(…) ± 2 %.
- Lintasan nyata pendek dari `dev/uji/md_gui/proyek_md.vmd`.

**Kriteria selesai**: semua tab terisi untuk MD 1 ns dalam < 30 s analisis; laporan HTML/Word memuat
5 figur standar (RMSD, RMSF, Rg, ikatan H, FEL).

---

### F3. Penargetan balik & farmakologi jaringan  ★★★  (L, dua tahap)

**Tujuan.** Satu atau beberapa senyawa (mis. dari F1) → target protein yang mungkin → jalur/penyakit → graf.

**Peringatan ilmiah (wajib tampil di dialog).** Telaah 2025 (Frontiers in Pharmacology; J. Advanced Research;
pedoman BCPT DOI 10.1111/bcpt.70308) mengkritik farmakologi jaringan karena: basis data tak dicatat versinya,
ambang tepi tak dilaporkan, blind docking disalahgunakan, dan klaim mekanisme tanpa uji basah.
VirmoLab harus **mendorong praktik benar secara bawaan**: catat versi & tanggal (Fondasi §2.1),
uji sensitivitas ambang, docking ke situs yang divalidasi (bukan blind), dan label "hipotesis".

**Tahap 3a — Penargetan balik (M)**

Dua jalur yang saling melengkapi:

1. **Berbasis ligan (cepat)**: kemiripan ke ligan aktif ChEMBL (pChEMBL ≥ 6) per target
   - sidik jari Morgan2 + FCFP4; skor target = max Tanimoto & rata-rata k-tetangga;
   - basis lokal: unduhan ringkas ChEMBL aktif manusia [izin] (±1–2 GB mentah → ringkas ±100 MB sqlite);
     alternatif daring: API ChEMBL similarity (sudah ada klien `core/chembl.py`).
2. **Berbasis struktur (lambat, pembeda VirmoLab)**: docking ke **panel target terkurasi**
   - panel bawaan per kelas: antibakteri, antidiabetes, antiinflamasi, antikanker, antivirus, neuro;
     tiap entri: PDB ID, rantai, ligan ko-kristal, pusat & ukuran kotak, **RMSD redocking tervalidasi ≤ 2 Å**;
   - berkas `data/panel_target/<kelas>.json` disusun sekali oleh skrip `dev/susun_panel.py`
     (unduh PDB → bersihkan → redocking → simpan hanya yang lolos);
   - normalisasi skor per target (**z-skor terhadap 50 umpan/decoy acak** dari COCONUT/ChEMBL yang sudah didocking
     ke target itu) — mengatasi bias "target besar = skor tinggi";
   - jalankan lewat antrean yang sudah ada (`core/antrean.py`), satu job per target.
3. Gabungan: peringkat Borda dari kedua jalur + label kepercayaan.

**Tahap 3b — Jaringan & pengayaan (M)**

| Data | Sumber | Lisensi | Catatan |
|---|---|---|---|
| Target ↔ penyakit | **Open Targets Platform** GraphQL | [cek] (selama ini terbuka) | pengganti DisGeNET (kini berbayar) |
| Jalur | **Reactome** (berkas GMT / Analysis Service) | CC BY 4.0 [cek] | bawaan |
| Gene Ontology | GO + anotasi GOA manusia (GMT) | CC BY 4.0 | bawaan |
| KEGG | REST | **hanya akademik, tidak boleh didistribusikan** | tautan luar saja, tidak dibundel |
| Interaksi protein | STRING | CC BY 4.0 [cek] | API, ambang skor ≥ 0,7 bawaan |

- Uji pengayaan: hipergeometrik (`scipy.stats.hypergeom`) + koreksi **Benjamini–Hochberg**; latar = semua gen
  dalam panel/anotasi (bukan seluruh genom, dijelaskan di laporan).
- Graf (Fondasi §2.3): senyawa → target → jalur → penyakit; metrik networkx: derajat, betweenness;
  **uji sensitivitas**: ulangi dengan ambang STRING 0,4/0,7/0,9 dan ambang skor target, tampilkan simpul inti yang
  **stabil** di semua ambang.
- Ekspor GraphML + CSV untuk Cytoscape.

**Berkas**: `core/target_balik.py`, `core/jaringan.py`, `core/pengayaan.py`, `ui/dialog_target_balik.py`,
`ui/dialog_jaringan.py`, `data/panel_target/*.json`, `data/gmt/*.gmt` [izin].

**Uji**: panel mini 5 target; senyawa kontrol positif (mis. ibuprofen → PTGS1/PTGS2 harus di 2 teratas jalur
ligan; metformin tidak boleh "ditemukan" mengikat kuat AMPK lewat docking — mekanisme tidak langsung → contoh batas
metode di dokumen); pengayaan pada daftar gen sintetis dengan jawaban diketahui.

**Kriteria selesai**: kurkumin (dari F1) → peringkat target + graf + tabel pengayaan + paragraf metode lengkap
dengan versi basis data dalam < 30 menit di laptop (jalur struktur, panel 50 target, exhaustiveness 8).

---

### F4. Penapisan berbasis ligan 3D (farmakofor + bentuk)  ★★  (M)

**Tujuan.** Menyaring pustaka besar **sebelum** docking memakai ligan aktif yang diketahui.

**Sudah ada [ada]**: fitur farmakofor hanya ditampilkan (`core/kemiripan.py`).

**Desain**
1. **Kueri farmakofor**: dari pose terbaik / ligan ko-kristal → fitur RDKit (`Chem.Pharm3D`, definisi fitur
   `BaseFeatures.fdef`): donor, akseptor, aromatik, hidrofobik, ion positif/negatif; pengguna dapat
   menonaktifkan fitur, mengatur toleransi (bawaan 1,0 Å), dan menambah volume eksklusi dari atom protein
   dalam 4 Å.
2. **Pencocokan**: pustaka → konformer ETKDGv3 (bawaan 30/senyawa, pemangkasan RMSD 0,5 Å) →
   `EmbedLib.MatchPharmacophoreToMol` + `EmbedPharmacophore` → skor = jumlah fitur cocok, RMSD fitur.
3. **Kemiripan bentuk**: [terverifikasi 2026-10-13, sumber: RDKit 2026.03.6 di .venv]: `rdkit.Chem.rdShapeAlign` tersedia (AlignShapes, ScoreShape, ShapeInput) → Tanimoto bentuk + warna; cadangan: `rdShapeHelpers.ShapeTanimotoDist` setelah `rdMolAlign.O3A`.
4. Skor gabungan = 0,5·farmakofor + 0,5·bentuk-warna; urutkan; kirim N teratas ke docking.
5. **Validasi bawaan**: bila proyek punya aktif & decoy (tab Uji), hitung AUC/BEDROC/EF1% dari
   `core/uji.py` yang sudah ada → pengguna tahu apakah kueri berguna.

**Berkas**: `core/farmakofor.py`, `core/bentuk.py`, `ui/dialog_farmakofor.py` (tampilan 3D bola fitur di viewer:
fungsi JS baru `VM.tampilFarmakofor(fitur)` di `viewer.js`).
**Kinerja**: proses terpisah, `multiprocessing` per kelompok 500 senyawa; target 10 000 senyawa < 15 menit.
**Uji**: 1HSG — kueri dari MK1; indinavir/saquinavir/ritonavir harus di 5 % teratas dari 500 decoy DUD-E HIVPR [izin unduh decoy].

---

### F5. QSAR & model ML dari data sendiri  ★★  (M)

**Tujuan.** Data aktivitas pengguna (CSV atau ChEMBL yang sudah diambil) → model prediksi tervalidasi →
prediksi untuk ligan proyek, mengikuti **5 prinsip OECD** (titik akhir jelas, algoritma jelas, domain aplikabilitas,
ukuran kecocokan/ketahanan/prediktivitas, tafsir mekanistik bila mungkin).

**Paket**: scikit-learn 1.9.1 & chemprop 2.3.1 **sudah terpasang** — tidak perlu unduhan.

**Alur**
1. Impor: CSV (`smiles, nilai, [satuan]`) atau tabel ChEMBL; konversi otomatis IC₅₀/Ki → pIC₅₀ (= 9 − log₁₀ nM);
   gabung duplikat (median; tandai bila rentang > 1 log).
2. Kurasi: standarisasi (sama dengan F1), buang anorganik/campuran, tandai *activity cliff* (pakai `core/mmp.py`).
3. Fitur: deskriptor RDKit 2D (±210, buang varians nol & korelasi > 0,95), Morgan2 2048, MACCS,
   gabungan; opsi **D-MPNN Chemprop** (graf).
4. Pembagian data: **acak** dan **berbasis kerangka (Bemis–Murcko)** — laporkan keduanya; praktik 2024+ menunjukkan
   pembagian acak terlalu optimistis.
5. Model: Random Forest, SVR (RBF), kNN, Gaussian Process (memberi ketidakpastian), Ridge; regresi & klasifikasi
   (ambang aktif dapat diatur, bawaan pIC₅₀ 6).
   Penyetelan: `GridSearchCV` kecil, CV 5 lipatan **di dalam** set latih saja.
6. Validasi:
   - internal: Q²(CV), RMSE, MAE; klasifikasi: ROC-AUC, MCC, BA;
   - eksternal: R²_pred, RMSE set uji; kriteria Golbraikh–Tropsha;
   - **Y-randomization** 50× (R² acak harus ≪ R² asli);
   - **domain aplikabilitas**: leverage (plot Williams, h* = 3(p+1)/n) + jarak kNN Tanimoto;
   - **prediksi konformal** (split conformal, 90 %) → interval prediksi per senyawa (implementasi sendiri, ±40 baris).
7. Tafsir: kepentingan fitur permutasi; untuk sidik jari → peta atom kontribusi (pola `core/kontribusi.py` [ada]).
8. Prediksi ligan proyek → kolom baru di panel Hasil `pIC50_pred ± interval`, tanda "di luar domain".
9. Simpan model: `proyek/model/<nama>.joblib` + `kartu_model.json` (data, fitur, metrik, versi paket, tanggal) —
   *model card* untuk reprodusibilitas.

**Berkas**: `core/qsar.py`, `core/konformal.py`, `ui/dialog_qsar.py` (wizard 5 langkah: Data → Kurasi → Fitur
& model → Validasi → Prediksi).
**Uji**: data publik kecil (mis. ESOL kelarutan ~1100 senyawa, lisensi terbuka [cek]) → RF R²_uji ≥ 0,8; Y-acak
R² < 0,2; konformal cakupan 88–92 % pada set uji.

---

### F6. Konsensus docking × co-folding + validitas fisik  ★★  (M)

**Konteks 2026.**
- Co-folding (AlphaFold 3, Boltz-2, Chai-1, Protenix) mencapai ± 77 % RMSD < 2 Å di PoseBusters (AF3),
  tetapi studi 2025 menunjukkan akurasi turun pada target/ligan yang **jauh dari data latih** dan pose sering
  tidak valid fisik (bentrok, kiralitas) tanpa koreksi.
- Studi eLife 2025 (Mac1): AF3/Boltz-2/Chai-1 masing-masing > 50 % pose < 2 Å; **afinitas Boltz-2 berkorelasi
  terbaik dengan potensi terukur**, sedangkan keyakinan pose AF3 kalah dari skor docking dalam memisahkan aktif
  dari positif palsu.
- Kesimpulan desain: co-folding **pelengkap**, bukan pengganti; nilai tertinggi ada pada **kesepakatan** dua metode.

**Sudah ada [ada]**: Boltz lewat WSL (`core/lanjutan.py`), PoseBusters (`core/qc.py`).

**Desain**
1. Untuk ligan terpilih: jalankan Boltz-2 (WSL, GPU bila ada) dengan sekuens reseptor + SMILES →
   ambil 5 pose, `affinity_pred_value` dan `affinity_probability_binary` [cek nama kunci keluaran versi terpasang].
2. Sejajarkan struktur co-folding ke reseptor proyek (Cα kantong, Kabsch [ada] `md.kabsch`).
3. Hitung: RMSD pose docking terbaik ↔ pose co-folding; PoseBusters untuk keduanya; interaksi kunci yang sama
   (IFP Tanimoto [ada]).
4. **Label kesepakatan**: *Sepakat* (RMSD < 2 Å & keduanya lolos PoseBusters), *Sebagian*, *Bertentangan*.
5. **Peringatan kebaruan**: kemiripan ligan maks ke ligan PDB (dari indeks ringkas RCSB, atau kueri RCSB
   chemical search) — bila < 0,3, tampilkan "di luar data latih, keyakinan co-folding rendah".
6. Tabel konsensus diperluas dengan kolom Boltz-2 (masuk `core/konsensus.py` [ada] sebagai kolom skor tambahan).

**Berkas**: `core/kofolding.py` (bungkus + analisis), perluas `ui/dialog_konsensus.py` + tab baru di Properti.
**Uji**: 1HSG + MK1 (sudah di PDB → kesepakatan diharapkan, sekaligus contoh bias kebocoran data latih yang
harus dijelaskan di dokumen).

---

### F7. Sifat elektronik kuantum (xTB)  ★★  (M) [izin]

**Tujuan.** HOMO, LUMO, celah, kekerasan kimia η = (E_LUMO − E_HOMO)/2, potensial kimia μ, elektrofilisitas
ω = μ²/2η, momen dipol, muatan parsial, **indeks Fukui** (f⁺, f⁻, f⁰) untuk reaktivitas, peta ESP.

**Pilihan mesin** (verifikasi saat implementasi):
| Mesin | Lisensi | Bentuk | Catatan |
|---|---|---|---|
| **xtb** (GFN2-xTB) | LGPL-3.0 | biner Windows statis di rilis GitHub [cek versi terbaru] | `--vfukui`, `--esp`, `--alpb water`; paling teruji |
| dxtb | Apache-2.0 | Python/PyTorch (torch sudah ada) | tanpa biner, tetapi fitur Fukui/ESP [cek] |
| g-xTB | [cek] | tidak ditemukan sumber resmi lewat pencarian 13 Okt 2026 | jangan dirujuk sampai terverifikasi |

**Alur**: konformer terbaik (atau pose docking) → `xtb mol.xyz --opt --gfn 2 --alpb water` →
`xtb opt.xyz --vfukui` → `--esp` → baca `xtbout.json`, `fukui`, `charges`, `xtb_esp.dat`.
Proses terpisah, batas waktu per molekul 5 menit, paralel per inti CPU.

**Tampilan**: tabel deskriptor + permukaan ESP berwarna di viewer 3D (titik ESP dipetakan ke permukaan 3Dmol);
atom diwarnai Fukui; korelasikan otomatis dengan situs metabolisme CYP (`core/metabolisme.py` [ada]).

**Kejujuran wajib di laporan**: "GFN2-xTB adalah metode semi-empiris; celah HOMO–LUMO cenderung lebih kecil
daripada DFT dan hanya layak untuk perbandingan tren antar-ligan, bukan nilai absolut. Bukan DFT."
**Uji**: benzena/benzoquinon/anilin → urutan celah HOMO–LUMO sesuai literatur; f⁻ terbesar anilin di posisi
orto/para.

---

### F8. Desain generatif terpandu docking  ★★  (L) [izin]

**Tujuan.** Dari hit terbaik → analog baru yang dapat disintesis → saring → docking → iterasi.

**Pilihan 2026**
| Alat | Lisensi | Kelebihan | Kekurangan |
|---|---|---|---|
| **CReM** | BSD-3 | ringan, berbasis fragmen nyata ChEMBL, keluaran "mirip obat & dapat disintesis" | butuh DB fragmen (±1–10 GB) [izin] |
| REINVENT 4 | Apache-2.0 | RL generatif kuat | GPU & konfigurasi berat, tidak cocok laptop |
| FBDD [ada] | — | sudah ada growing/linking | pustaka fragmen terbatas |

**Desain (CReM)**: operasi *mutate / grow / link* dengan radius konteks 2–3 → filter (PAINS, Brenk, SAScore ≤ 4,
QED ≥ 0,4, MPO [ada], kebaruan Tanimoto < 0,8 ke induk) → docking cepat (exhaustiveness 4) → 20 teratas docking
penuh → **optimasi multi-objektif** (front Pareto ΔG × QED × SA) → ulangi n generasi (bawaan 3).
Riwayat silsilah disimpan → pohon silsilah (graf §2.3).

**Berkas**: `core/generatif.py`, `ui/dialog_generatif.py`. **Uji**: dari MK1, generasi 1 menghasilkan ≥ 50 analog
valid, semua lolos sanitasi RDKit, tidak ada duplikat InChIKey.

---

### F9. Energi bebas relatif alkimia (RBFE)  ★  (L, eksperimental) [izin]

**Konteks.** FEP/RBFE adalah standar emas industri untuk seri kongenerik (galat ± 1 kcal/mol). OpenFE
(MIT) membawa alur ini ke perangkat lunak terbuka berbasis OpenMM + OpenFF — **keduanya sudah terpasang**.

**Desain**: pasangan dari MMP [ada] (seri kongenerik, perubahan ≤ 10 atom berat) → pemetaan atom (Kartograf/LOMAP
[cek]) → jaringan perturbasi (bintang/minimal spanning) → protokol `RelativeHybridTopologyProtocol`
(11 jendela λ, 3 replika) → ΔΔG ± galat → peringkat.
**Realisme**: perlu GPU (CUDA/OpenCL); ± beberapa jam per tepi di GPU laptop. Mode CPU dinonaktifkan dengan pesan
jelas. Tampilkan estimasi waktu dari `md.uji_kecepatan` [ada] sebelum mulai.
**Rilis**: hanya bila pengguna punya GPU memadai; label "eksperimental".

---

### F10. Docking peptida  ★  (M)

**Konteks 2026.** Vina/AD-GPU lemah untuk peptida (> 20 ikatan rotasi). Co-folding (Boltz-2) menangani
peptida secara alami dan **sudah terintegrasi** lewat WSL.
**Desain**: masukan sekuens (≤ 30 residu, residu non-standar terbatas) → Boltz-2 co-folding dengan reseptor →
pemurnian singkat OpenMM (minimisasi + 100 ps) → MM/GBSA [ada] → analisis antarmuka pakai `core/ppi.py` [ada].
Opsional: AutoDock CrankPep (ADCP) bila lisensinya cocok [cek].
**Uji**: kompleks peptida–protein dikenal (mis. MDM2–p53 PDB 1YCR) → RMSD Cα peptida < 3 Å.

---

### F11. Paket validasi protokol untuk naskah  ★★★  (S–M)

**Tujuan.** Reviewer hampir selalu meminta bukti protokol docking valid. Satu tombol menghasilkan bagian
"Validasi metode" lengkap.

**Isi**
1. Redocking ligan ko-kristal [ada] → RMSD + figur tumpang-tindih.
2. **Cross-docking** (bila ada ≥ 2 struktur PDB target yang sama) → matriks RMSD.
3. **Enrichment**: aktif (ChEMBL, pChEMBL ≥ 7, maks 50, beragam kerangka) + decoy gaya DUD-E dibuat
   sendiri (cocokkan MW, logP, HBD, HBA, rotatable, muatan; Tanimoto ke aktif < 0,3; 50 decoy/aktif) →
   ROC-AUC, BEDROC (α = 20), EF1 %, logAUC [ada di `core/uji.py`].
   Pembuat decoy lokal dari COCONUT/ChEMBL lokal → tidak perlu server DUD-E.
4. Validitas fisik pose (PoseBusters [ada]) — % lolos.
5. Ringkasan satu halaman + paragraf metode + figur siap jurnal.

**Berkas**: `core/validasi_protokol.py`, `core/decoy.py`, tombol di tab Uji.
**Kriteria**: 1HSG → RMSD < 2 Å, AUC > 0,7 dengan decoy buatan sendiri.

---

### F12. Pelacak hipotesis → uji laboratorium  ★  (S)

**Tujuan.** Menutup siklus komputasi ↔ eksperimen. Rencana lab [ada] menghasilkan protokol; hasil IC₅₀
yang kembali dimasukkan ke proyek → dibandingkan dengan prediksi → (opsional) melatih ulang QSAR F5.
**Desain**: `proyek.eksperimen` [ada] diperluas: tautan ligan ↔ hasil assay; grafik prediksi vs terukur
(Spearman ρ, Kendall τ); status hipotesis (diajukan → diuji → didukung/ditolak).

---

## 4. Peta rilis

| Versi | Isi | Alasan urutan | Unduhan baru |
|---|---|---|---|
| **1.2** | Fondasi §2, **F1** tanaman, **F2** MD lengkap, **F11** validasi protokol | nilai tertinggi; F2 & F11 tanpa paket baru | daftar tanaman (dibuat sendiri), COCONUT penuh (opsional) |
| **1.3** | **F3** penargetan balik + jaringan | memakai F1 dan Fondasi | GMT Reactome/GO, ChEMBL ringkas, PDB panel target |
| **1.4** | **F5** QSAR, **F4** farmakofor & bentuk, **F12** | paket sudah ada | decoy DUD-E untuk uji (opsional) |
| **1.5** | **F6** konsensus co-folding, **F10** peptida, **F7** xTB | memakai Boltz (WSL) yang sudah ada | xtb |
| **1.6** | **F8** generatif, **F9** RBFE (eksperimental) | paling berat | DB fragmen CReM, OpenFE |

Alur utuh setelah 1.4:
**nama tanaman → senyawa → ADMET → target (balik) → validasi protokol → docking → MD → jaringan →
QSAR → rencana lab → laporan + naskah.**

Perkiraan beban: 1.2 ≈ 6–8 sesi, 1.3 ≈ 6 sesi, 1.4 ≈ 5 sesi, 1.5 ≈ 5 sesi, 1.6 ≈ 6+ sesi.

---

## 5. Risiko ilmiah & cara jujur melaporkannya

| Risiko | Penanganan di aplikasi |
|---|---|
| Skor docking ≠ afinitas | semua tampilan ΔG bertanda "perkiraan"; konsensus & MM/GBSA hanya peringkat relatif |
| Blind docking disalahgunakan (kritik 2025) | F3 memakai situs tervalidasi; blind docking memberi peringatan bila dipakai untuk klaim mekanisme |
| Farmakologi jaringan tidak reprodusibel | versi + tanggal + ambang otomatis di laporan; uji sensitivitas wajib |
| Co-folding hafal data latih | peringatan kebaruan (F6) |
| QSAR terlalu optimistis | pembagian kerangka, Y-acak, domain aplikabilitas, konformal (F5) |
| MD terlalu singkat / satu replika | konvergensi blok + replika (F2); peringatan bila < 3 replika |
| xTB dianggap DFT | kalimat wajib di laporan (F7) |
| Data tanaman lama/tak tervalidasi | jumlah rujukan & tahun ditampilkan (F1) |

Setiap fitur yang menghasilkan angka harus punya `kit.catatan(..., "peringatan")` yang menyebut batasnya —
sudah menjadi aturan sejak 1.1.1 ("Catatan batas di tiap alat perkiraan").

---

## 6. Pertanyaan yang perlu diputuskan

1. Setuju isi **1.2** = Fondasi + F1 + F2 + F11?
2. F1: tanaman/basis data apa yang paling sering Anda dan mahasiswa pakai? Boleh saya susun daftar nama lokal
   dari Farmakope Herbal Indonesia / MMI (Anda punya salinannya)?
3. F3: kelas penyakit untuk panel target pertama (pilih 2): antibakteri, antidiabetes, antiinflamasi,
   antikanker, antivirus, neuro?
4. F2: lama MD realistis di laptop pengguna Anda (10 / 50 / 100 ns)?
5. Izin unduh untuk 1.2: COCONUT penuh (dengan organisme, ± beberapa ratus MB) — ya/tidak?
6. F9 (RBFE) dan F8 (generatif) masih relevan bagi pengguna Anda, atau dicoret saja?

---

### Sumber pengecekan ilmu (13 Okt 2026)

- PoseBusters: AI-based docking methods fail to generate physically valid poses — https://arxiv.org/pdf/2308.05777
- Physically valid biomolecular interaction modeling (Gauss–Seidel projection, preprint 2025) — https://arxiv.org/pdf/2510.08946
- Co-folding pada Mac1: AF3, Boltz-2, Chai-1 (eLife reviewed preprint 2025) — https://elifesciences.org/reviewed-preprints/110475.pdf
- Co-folding dan generalisasi ke target baru — https://www.apheris.com/resources/why-co-folding-models-are-here-to-stay
- COCONUT 2.0 (Zenodo) — https://zenodo.org/records/13897048
- LOTUS (bioRxiv; Planta Medica 2021) — https://www.biorxiv.org/content/10.1101/2021.02.28.433265v2 ·
  https://www.thieme-connect.de/products/ejournals/html/10.1055/s-0041-1736777
- Kritik docking dalam farmakologi jaringan (Frontiers in Pharmacology 2025) —
  https://public-pages-files-2025.frontiersin.org/journals/pharmacology/articles/10.3389/fphar.2025.1566772/text
- Pedoman BCPT produk alam & farmakologi sistem (DOI 10.1111/bcpt.70308) —
  https://www.citedrive.com/en/discovery/the-2027-bcpt-perspectives-on-studies-involving-natural-products-traditional-chinese-medicine-and-systems-pharmacology/
- Sensitivitas konstruksi graf (network biology review) — https://arxiv.org/pdf/2309.08478
- xtb (Grimme lab), lisensi LGPL-3.0 — https://packages.fedoraproject.org/pkgs/xtb/xtb · dxtb (Apache-2.0) — https://pypi.org/project/dxtb

Butir bertanda [cek] **belum** terverifikasi dari sumber resmi 2026; verifikasi ulang saat fitur dikerjakan.
