# Ide baru (dikerjakan setelah v1.0 rilis)

Catat ide baru di sini, jangan langsung masuk rencana. Format: tanggal — ide — alasan/sumber.

- 10 Okt 2026 — Konservasi residu kantong (rencana B4 #10): sekuens rantai -> homolog -> % identitas per posisi, warna ConSurf di viewer. DITUNDA karena layanan tidak bisa diuji hari itu: NCBI BLAST URL API memberi RTOE ±29 000 s, EBI HMMER v1 (api/v1/search/phmmer, JSON {input, database}) hanya mengaktifkan pdb & mgnify (swissprot/uniprot/refprot 'paused'). Kerjakan saat salah satu layanan normal; alternatif offline: anggota klaster UniRef50 (UniProt REST) + penjajaran Needleman–Wunsch/BLOSUM62 sendiri.
