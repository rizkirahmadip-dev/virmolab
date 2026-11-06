"""Satu jendela untuk alat penelitian yang melengkapi docking: konservasi, energi residu,
umpan, enumerasi, mutasi, naskah, dan program luar yang tidak dibundel."""
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QPlainTextEdit, QPushButton, QSpinBox, QStackedWidget, QTextEdit,
                               QVBoxLayout, QWidget)

from .. import i18n
from ..core import (air, kampanye, konservasi, lanjutan, mutasi, naskah, senyawa, syarat)


class DialogPenelitian(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Penelitian lanjutan")
        self.resize(920, 640)
        akar = QHBoxLayout(self)
        self.menu = QListWidget()
        self.menu.setFixedWidth(210)
        self.tumpuk = QStackedWidget()
        self.keluar = QPlainTextEdit()
        self.keluar.setReadOnly(True)
        self.keluar.setPlaceholderText("Hasil muncul di sini.")
        kanan = QVBoxLayout()
        kanan.addWidget(self.tumpuk, 2)
        kanan.addWidget(self.keluar, 1)
        akar.addWidget(self.menu)
        akar.addLayout(kanan, 1)
        halaman = [
            ("Konservasi residu", self._hal_konservasi()),
            ("Energi per residu", self._hal_energi()),
            ("Ensemble & selektivitas", self._hal_kampanye()),
            ("Umpan (decoy)", self._hal_umpan()),
            ("Regangan ligan", self._hal_regangan()),
            ("Bentuk 3D", self._hal_bentuk()),
            ("Tautomer & isomer", self._hal_enumerasi()),
            ("Gugus R & bioisoster", self._hal_gugus()),
            ("Air & kofaktor", self._hal_air()),
            ("Syarat interaksi", self._hal_syarat()),
            ("Mutasi", self._hal_mutasi()),
            ("Sunting di kantong", self._hal_sunting()),
            ("Film trajektori & server", self._hal_film()),
            ("Draf skripsi & figur", self._hal_naskah()),
            ("GNINA & Boltz", self._hal_luar()),
        ]
        for judul, w in halaman:
            self.menu.addItem(judul)
            self.tumpuk.addWidget(w)
        self.menu.currentRowChanged.connect(self.tumpuk.setCurrentIndex)
        self.menu.setCurrentRow(0)
        self._muat_rid()

    def _muat_rid(self):
        pr = getattr(self.jw, "proyek", None)
        b = getattr(pr, "blast", None) or {}
        if b.get("rid"):
            self._rid_blast = str(b["rid"])
            if b.get("rantai") and hasattr(self, "e_rantai"):
                self.e_rantai.setText(str(b["rantai"])[:1])
            self._tulis(f"Nomor BLAST tersimpan di proyek: {self._rid_blast}. Tombol ambil hasil masih bisa dipakai.")

    def _simpan_rid(self, rid):
        self._rid_blast = rid
        pr = getattr(self.jw, "proyek", None)
        if not pr or not rid:
            return
        rantai = self.e_rantai.text().strip()[:1] if hasattr(self, "e_rantai") else "A"
        pr.blast = {"rid": rid, "rantai": rantai or "A"}
        if hasattr(self.jw, "minta_simpan"):
            self.jw.minta_simpan()

    def _tulis(self, teks):
        self.keluar.setPlainText(teks)
        self.jw.log.tulis(teks.splitlines()[0][:180] if teks else "")

    def _protein(self):
        return self.jw._reseptor_objek()

    def _pose(self):
        o = self.jw.objek.get(self.jw.aktif)
        if o and o.jenis in ("pose", "ligan"):
            return o
        return next((x for x in self.jw.objek.values() if x.jenis == "pose"), None)

    def _pdbqt_reseptor(self):
        pr = self.jw.proyek
        if not pr or not pr.reseptor or not pr.reseptor.get("pdbqt"):
            return ""
        f = pr.p(pr.reseptor["pdbqt"])
        return f.read_text(encoding="utf-8", errors="replace") if f.exists() else ""

    def _pdbqt_pose(self):
        o = self._pose()
        if not o or not o.info.get("pdbqt"):
            return ""
        return o.info["pdbqt"]

    def _mol(self):
        o = self._pose()
        if not o:
            raise ValueError("Pilih pose atau ligan di panel Objek.")
        return self.jw._mol_objek(o)

    def _tambah_smiles(self, pasangan):
        from ..core import molekul, prep_ligan
        daftar = []
        for nama, smi in pasangan:
            h = prep_ligan.siapkan_satu(nama, smi, "smiles", prep_ligan.OpsiLigan(protonasi=False))
            if h.status == "gagal":
                continue
            asal = molekul.Objek(nama=nama, jenis="ligan", teks=smi, fmt="smiles", sumber="penelitian")
            daftar.append((asal, h))
        if daftar:
            self.jw._ligan_siap(daftar)
        return len(daftar)

    # ---------------------------------------------------------------- halaman
    def _hal_konservasi(self):
        w, v = self._wadah()
        self.e_rantai = QLineEdit("A")
        self.e_fasta = QTextEdit()
        self.e_fasta.setPlaceholderText(">homolog_1\nMTEYK...\n\nTempel FASTA. Baris pertama boleh sekuens rantai; "
                                        "bila kosong, sekuens diambil dari protein yang sedang terbuka.")
        self.e_uniprot = QLineEdit()
        self.e_uniprot.setPlaceholderText("Nama protein untuk dicari di UniProt (opsional)")
        v.addWidget(QLabel("Rantai"))
        v.addWidget(self.e_rantai)
        v.addWidget(self.e_fasta, 1)
        v.addWidget(self.e_uniprot)
        lab = QLabel("BLAST Swiss-Prot mengirim sekuens rantai ke NCBI. Bila NCBI masih antre, "
                     "VirmoLab mencoba UniProt lalu EBI. Bila keduanya tidak menjawab, homolog diambil "
                     "dari pencarian sekuens di RCSB PDB. Identitas tetap dihitung di komputer ini.")
        lab.setWordWrap(True)
        v.addWidget(lab)
        self._tombol(v, "Hitung & warnai B-faktor", self._konservasi)
        self._tombol(v, "Ambil FASTA dari UniProt", self._uniprot)
        self._tombol(v, "BLAST Swiss-Prot (NCBI)", self._blast)
        self._tombol(v, "Cari homolog (UniProt, EBI, atau RCSB)", self._blast_uniprot)
        self._tombol(v, "Ambil hasil BLAST yang tertunda", self._blast_ambil)
        return w

    def _hal_energi(self):
        w, v = self._wadah()
        v.addWidget(QLabel("Sumbangan Vina per residu pada pose aktif, plus pemindaian alanin "
                           "(menghapus rantai samping pada fungsi skor, bukan MM/GBSA)."))
        self._tombol(v, "Hitung", self._energi)
        v.addStretch(1)
        return w

    def _hal_kampanye(self):
        w, v = self._wadah()
        v.addWidget(QLabel("Menggabungkan job yang sudah selesai. Ensemble = skor terbaik tiap ligan "
                           "di antara bentuk reseptor. Selektivitas = tabel ligan × protein. "
                           "Docking silang: siapkan protein kedua, docking ligan yang sama, lalu buka lagi halaman ini. "
                           "Skor kovalen tidak dibandingkan sebagai ΔG."))
        self._tombol(v, "Gabungkan job proyek", self._kampanye)
        v.addStretch(1)
        return w

    def _hal_umpan(self):
        w, v = self._wadah()
        self.n_umpan = QSpinBox()
        self.n_umpan.setToolTip("Jumlah senyawa umpan (decoy) per senyawa aktif. Nisbah yang lebih besar membuat uji pengayaan lebih ketat dan angkanya lebih bermakna, tetapi docking berjalan lebih lama secara sebanding.")
        self.n_umpan.setRange(5, 40)
        self.n_umpan.setValue(15)
        v.addWidget(QLabel("Umpan berpadanan sifat dari ligan yang sudah disiapkan (SMILES). "
                           "Tanimoto ECFP4 terhadap aktif dijaga di bawah 0,40."))
        v.addWidget(self.n_umpan)
        self._tombol(v, "Buat umpan dan tambahkan sebagai ligan", self._umpan)
        v.addStretch(1)
        return w

    def _hal_regangan(self):
        w, v = self._wadah()
        v.addWidget(QLabel("Regangan MMFF: energi pose sekarang dikurangi energi setelah minimisasi bebas."))
        self._tombol(v, "Hitung regangan pose aktif", self._regangan)
        v.addStretch(1)
        return w

    def _hal_bentuk(self):
        w, v = self._wadah()
        v.addWidget(QLabel("Kemiripan bentuk 3D pose aktif terhadap ligan lain yang sedang terbuka."))
        self._tombol(v, "Bandingkan bentuk", self._bentuk)
        v.addStretch(1)
        return w

    def _hal_enumerasi(self):
        w, v = self._wadah()
        v.addWidget(QLabel("Tautomer dan stereoisomer ligan aktif. Makrosiklus (≥ 7 atom) sudah fleksibel di Meeko "
                           "kecuali kotak “Makrosiklik kaku” pada persiapan ligan; koordinat 3D memakai torsi makrosiklus."))
        self._tombol(v, "Enumerasi dan tambahkan", self._enumerasi)
        v.addStretch(1)
        return w

    def _hal_gugus(self):
        w, v = self._wadah()
        self.e_inti = QLineEdit("*c1ccccc1")
        self.e_gugus = QTextEdit()
        self.e_gugus.setPlainText("Cl\nF\nOC\nC")
        self.e_gugus.setFixedHeight(80)
        v.addWidget(QLabel("Inti dengan tanda *"))
        v.addWidget(self.e_inti)
        v.addWidget(QLabel("Substituen, satu SMILES per baris"))
        v.addWidget(self.e_gugus)
        self._tombol(v, "Pasang gugus", self._gugus)
        self._tombol(v, "Bioisoster dari ligan aktif", self._bio)
        v.addStretch(1)
        return w

    def _hal_air(self):
        w, v = self._wadah()
        v.addWidget(QLabel("Melihat air penjembatan dan kofaktor pada protein yang terbuka. "
                           "Agar ikut docking, centang pilihan yang sama di wizard Siapkan reseptor."))
        self._tombol(v, "Telaah struktur", self._air)
        v.addStretch(1)
        return w

    def _hal_syarat(self):
        w, v = self._wadah()
        self.e_syarat = QTextEdit()
        self.e_syarat.setPlaceholderText("ASP 25 A\nASP 25 A hbond")
        self.e_syarat.setFixedHeight(80)
        v.addWidget(QLabel("Satu syarat per baris: nama residu persis seperti di tabel interaksi, "
                           "opsional diikuti jenis (hbond, hidrofobik, pi, garam, halogen, logam)."))
        v.addWidget(self.e_syarat)
        self._tombol(v, "Periksa pose aktif", self._syarat)
        v.addStretch(1)
        return w

    def _hal_mutasi(self):
        w, v = self._wadah()
        self.e_mut_rantai = QLineEdit("A")
        self.e_mut_resi = QLineEdit("25")
        self.e_mut_aa = QLineEdit("A")
        v.addWidget(QLabel("Rantai, nomor residu, asam amino baru (satu huruf). "
                           "Alanin memotong rantai samping. Residu lain memakai PDBFixer, tanpa relaksasi."))
        for wdg in (self.e_mut_rantai, self.e_mut_resi, self.e_mut_aa):
            v.addWidget(wdg)
        self._tombol(v, "Buat objek protein termutasi", self._mutasi)
        v.addStretch(1)
        return w

    def _hal_sunting(self):
        w, v = self._wadah()
        self.e_reaksi = QLineEdit("[c:1][H]>>[c:1]O")
        v.addWidget(QLabel("Reaksi SMARTS pada ligan aktif. Pose disejajarkan, lalu Vina meminimisasi "
                           "di tempat bila reseptor PDBQT sudah ada. Energi yang muncul adalah skor Vina."))
        v.addWidget(self.e_reaksi)
        self._tombol(v, "Sunting dan skor ulang", self._sunting)
        v.addStretch(1)
        return w

    def _hal_film(self):
        w, v = self._wadah()
        v.addWidget(QLabel("Film membaca frames.npy hasil MD. Paket server menulis XML OpenMM, GRO, dan topologi GROMACS vakum."))
        self._tombol(v, "Putar trajektori…", self._film)
        self._tombol(v, "Tulis paket server dari pose aktif…", self._server)
        v.addStretch(1)
        return w

    def _hal_naskah(self):
        w, v = self._wadah()
        self.e_dpi = QSpinBox()
        self.e_dpi.setToolTip("Resolusi gambar yang diekspor. Banyak jurnal meminta minimal 300 dpi untuk foto dan 600 dpi untuk gambar garis; di atas 600 ukuran berkas naik tanpa perbaikan yang terlihat saat dicetak.")
        self.e_dpi.setRange(72, 1200)
        self.e_dpi.setValue(300)
        self.e_mm = QSpinBox()
        self.e_mm.setToolTip("Lebar cetak gambar dalam milimeter. 85 mm memenuhi satu kolom jurnal, 174 mm memenuhi dua kolom; menyetelnya di sini membuat ukuran huruf di gambar sesuai saat dicetak.")
        self.e_mm.setRange(40, 400)
        self.e_mm.setValue(85)
        self.e_pt = QSpinBox()
        self.e_pt.setToolTip("Ukuran huruf di dalam gambar, dalam poin pada lebar cetak di atas. 7–9 pt lazim diminta jurnal; huruf di bawah 6 pt sering ditolak karena tidak terbaca.")
        self.e_pt.setRange(4, 24)
        self.e_pt.setValue(8)
        self.e_warna = QLineEdit("#2B6FD6, #d4594a")
        v.addWidget(QLabel("Pemeriksa figur: dpi, lebar mm, huruf pt, daftar warna hex."))
        for wdg in (self.e_dpi, self.e_mm, self.e_pt, self.e_warna):
            v.addWidget(wdg)
        self._tombol(v, "Periksa figur", self._figur)
        self._tombol(v, "Simpan draf skripsi…", self._skripsi)
        self._tombol(v, "Simpan BibTeX…", self._bib)
        v.addStretch(1)
        return w

    def _hal_luar(self):
        w, v = self._wadah()
        lab = QLabel(
            "GNINA menilai ulang pose dengan CNN. Boltz memprediksi posisi protein dan ligan. "
            "Keduanya biner Linux di WSL (beberapa gigabita) dan tidak ikut installer Windows. "
            "Affinity GNINA dalam kcal/mol, CNNscore antara 0 dan 1, CNNaffinity dalam pK (bukan kcal/mol). "
            "RMSD Boltz hanya sah setelah disejajarkan ke kristal. "
            "Skor pada reseptor tanpa hidrogen, atau Boltz tanpa MSA, jangan ditulis sebagai hasil skripsi.")
        lab.setWordWrap(True)
        v.addWidget(lab)
        self.c_msa = QCheckBox("Minta MSA ke ColabFold (sekuens terkirim; prediksi lebih layak dibanding kristal)")
        v.addWidget(self.c_msa)
        self.c_penuh = QCheckBox("Pengaturan penuh: 3 daur ulang, 200 langkah, semua rantai protein yang terbuka. "
                                 "Pada GPU 6 GB ini sering kehabisan memori.")
        self.c_penuh.setToolTip("Tanpa centang ini, Boltz memakai 1 daur ulang dan 50 langkah supaya muat di GPU 6 GB.")
        v.addWidget(self.c_penuh)
        self._tombol(v, "Periksa pemasangan", self._luar)
        self._tombol(v, "Skor ulang pose (GNINA)", self._gnina)
        self._tombol(v, "Prediksi Boltz di GPU", lambda _=False: self._boltz(True))
        self._tombol(v, "Prediksi Boltz di CPU", lambda _=False: self._boltz(False))
        v.addStretch(1)
        return w

    def _wadah(self):
        w = QWidget()
        v = QVBoxLayout(w)
        return w, v

    def _tombol(self, v, teks, fn):
        b = QPushButton(teks)
        b.clicked.connect(fn)
        v.addWidget(b)

    # ---------------------------------------------------------------- aksi
    def _konservasi(self):
        prot = self._protein()
        if not prot:
            self._tulis("Tidak ada protein di proyek.")
            return
        rantai = self.e_rantai.text().strip()[:1] or "A"
        fasta = konservasi.baca_fasta(self.e_fasta.toPlainText())
        urut = konservasi.sekuens_rantai(prot.teks, rantai)
        if not urut:
            self._tulis(f"Rantai {rantai} tidak berisi asam amino standar.")
            return
        query = "".join(aa for _, aa, _, _ in urut)
        if fasta and fasta[0][1] == query:
            fasta = fasta[1:]
        if not fasta:
            self._tulis("Tempel minimal satu homolog FASTA, atau ambil dari UniProt.")
            return
        try:
            hasil = konservasi.skor(query, [s for _, s in fasta])
        except Exception as e:
            self._tulis(str(e))
            return
        prot.teks = konservasi.terapkan_bfaktor(prot.teks, rantai, hasil)
        prot.gaya["warna"] = {"mode": "bfactor"}
        self.jw.viewer.muat(prot)
        self.jw.viewer.tampil(prot, __import__("virmolab.core.molekul", fromlist=["spek_viewer"]).spek_viewer(prot))
        rendah = [f"{urut[i][2]}{urut[i][3]} {h['aa']} {h['identitas']:.0%}"
                  for i, h in enumerate(hasil) if h["n"] and h["identitas"] < 0.5][:12]
        # Diterjemahkan per bagian: lapisan terjemahan hanya mencocokkan string utuh, dan teks ini disambung.
        teks = i18n.t(f"Konservasi {len(hasil)} posisi pada rantai {rantai}, {len(fasta)} homolog. "
                      f"Protein diwarnai menurut B-faktor (100 = utuh terkonservasi).\n"
                      f"Posisi < 50%: {', '.join(rendah) or 'tidak ada'}")
        # Ringkasan kantong: yang dipakai untuk argumen selektivitas adalah residu di sekitar ligan, bukan seluruh rantai.
        pose = self._pose()
        kantong = konservasi.ringkas_kantong(prot.teks, rantai, hasil,
                                             konservasi.koordinat_ligan(pose.teks if pose else ""))
        if kantong and kantong["rata_kantong"] is not None:
            paling = ", ".join(f"{r[0]} {r[2]:.0%}" for r in kantong["residu"][:6])
            teks += "\n\n" + i18n.t(
                f"Kantong ({kantong['n']} residu ≤ {kantong['jarak']:g} Å dari {pose.nama}): identitas rata-rata "
                f"{kantong['rata_kantong']:.0%}, seluruh rantai {kantong['rata_rantai']:.0%}.") + "\n" + i18n.t(
                f"Residu kantong paling kurang terkonservasi: {paling}")
        else:
            teks += "\n\n" + i18n.t("Pilih pose atau ligan di panel Objek untuk ringkasan konservasi residu kantong.")
        self._tulis(teks)

    def _uniprot(self):
        k = self.e_uniprot.text().strip()
        if not k:
            self._tulis("Isi nama protein pada kotak UniProt.")
            return
        try:
            teks = konservasi.unduh_fasta(k)
        except Exception as e:
            self._tulis(str(e))
            return
        self.e_fasta.setPlainText(teks)
        self._tulis(f"FASTA UniProt untuk “{k}” ditempel. Periksa isinya, lalu hitung konservasi. "
                    "Ini pencarian nama, bukan BLAST.")

    def _energi(self):
        rec, lig = self._pdbqt_reseptor(), self._pdbqt_pose()
        if not rec or not lig:
            self._tulis("Butuh reseptor yang sudah disiapkan dan pose hasil docking yang dipilih.")
            return
        from ..core import energi_residu
        residu, total = energi_residu.per_residu(rec, lig)
        ala = energi_residu.alanin(rec, lig)
        baris = [f"Total Vina antarmolekul (per residu): {total:.2f} kkal/mol", ""]
        baris += [f"{r['residu']:12} {r['energi']:8.2f}" for r in residu[:25]]
        baris += ["", "Pemindaian alanin (delta > 0 = residu menguntungkan):"]
        baris += [f"{a['residu']:12} Δ {a['delta_alanin']:7.2f}  {a['makna']}" for a in ala]
        self._tulis("\n".join(baris))

    def _kampanye(self):
        pr = self.jw.proyek
        if not pr or not pr.job:
            self._tulis("Belum ada job docking.")
            return
        baris = kampanye.dari_job(pr.job)
        ens = kampanye.ensemble(baris)
        tab = kampanye.selektivitas(baris)
        kov = kampanye.banding_kovalen(baris)
        o = ["Ensemble (skor terbaik tiap ligan):"]
        o += [f"  {b['ligan']}  {b['energi']:.2f}  pada {b['reseptor']}" + ("  [kovalen]" if b["kovalen"] else "")
              for b in ens[:20]]
        o += ["", "Selektivitas:", kampanye.teks_tabel(tab), "", "Kovalen lawan non-kovalen:"]
        o += [f"  {p['ligan']}: kovalen {p['kovalen']:.2f} ({p['warhead'] or 'aduk'}), "
              f"non-kovalen {p['nonkovalen']:.2f} - jangan dibaca sebagai selisih ΔG"
              for p in kov] or ["  Tidak ada ligan yang punya kedua jenis job."]
        self._tulis("\n".join(o))

    def _umpan(self):
        pr = self.jw.proyek
        smiles = []
        if pr:
            for l in pr.ligan_siap():
                smi = ""
                f = pr.p(l["sdf"]) if l.get("sdf") else None
                if f and f.exists():
                    from rdkit import Chem
                    m = Chem.MolFromMolBlock(f.read_text(encoding="utf-8", errors="replace"))
                    if m:
                        smi = Chem.MolToSmiles(Chem.RemoveHs(m))
                if smi:
                    smiles.append(smi)
        if not smiles:
            self._tulis("Belum ada ligan siap dengan struktur 3D.")
            return
        try:
            daftar = senyawa.umpan(smiles[:8], self.n_umpan.value())
        except Exception as e:
            self._tulis(str(e))
            return
        n = self._tambah_smiles([(f"umpan {i + 1}", s) for i, s in enumerate(daftar)])
        self._tulis(f"{n} umpan ditambahkan dari {len(smiles[:8])} ligan aktif. "
                    "Mereka lolos saringan sifat dan Tanimoto < 0,40. Jalankan docking yang sama, "
                    "lalu hitung ROC di tab Uji dengan umpan sebagai negatif.")

    def _regangan(self):
        try:
            e = senyawa.regangan(self._mol())
        except Exception as ex:
            self._tulis(str(ex))
            return
        makna = "kecil" if e < 3 else ("sedang" if e < 8 else "besar - pose mungkin meregang")
        self._tulis(f"Regangan MMFF pose aktif: {e:.2f} kkal/mol ({makna}).")

    def _bentuk(self):
        try:
            acuan = self._mol()
        except Exception as e:
            self._tulis(str(e))
            return
        baris = []
        for o in self.jw.objek.values():
            if o.jenis not in ("ligan", "pose") or o is self._pose():
                continue
            try:
                lain = self.jw._mol_objek(o)
                baris.append(f"{o.nama}: {senyawa.bentuk(acuan, lain):.3f}")
            except Exception:
                continue
        self._tulis("\n".join(baris) or "Tidak ada ligan lain untuk dibandingkan.")

    def _enumerasi(self):
        try:
            mol = self._mol()
        except Exception as e:
            self._tulis(str(e))
            return
        nama = self._pose().nama
        makro = senyawa.ada_makrosiklus(mol)
        tau = senyawa.tautomer(mol)
        ste = senyawa.stereoisomer(mol)
        pasangan = [(f"{nama} tautomer {i + 1}", s) for i, s in enumerate(tau)]
        pasangan += [(f"{nama} isomer {i + 1}", s) for i, s in enumerate(ste)]
        n = self._tambah_smiles(pasangan[:16])
        self._tulis(f"Makrosiklus: {'ya (≥ 7)' if makro else 'tidak'}. {n} bentuk ditambahkan sebagai ligan.")

    def _gugus(self):
        try:
            hasil = senyawa.enumerasi_gugus(self.e_inti.text().strip(), self.e_gugus.toPlainText().splitlines())
        except Exception as e:
            self._tulis(str(e))
            return
        baik = [(f"gugus {g}", s) for g, s, galat in hasil if s and not galat]
        n = self._tambah_smiles(baik)
        gagal = [f"{g}: {galat}" for g, _s, galat in hasil if galat]
        self._tulis(f"{n} analog ditambahkan.\n" + ("\n".join(gagal) if gagal else ""))

    def _bio(self):
        try:
            mol = self._mol()
        except Exception as e:
            self._tulis(str(e))
            return
        hasil = senyawa.bioisoster(mol)
        n = self._tambah_smiles([(nama.split("→")[-1].strip()[:24], smi) for nama, smi in hasil])
        self._tulis("\n".join(f"{a}: {b}" for a, b in hasil) + f"\n\n{n} bioisoster ditambahkan."
                    if hasil else "Tidak ada pengganti dari tabel yang mengenai ligan ini.")

    def _air(self):
        prot = self._protein()
        if not prot:
            self._tulis("Tidak ada protein.")
            return
        h = air.telaah(prot.teks)
        lig = h["ligan"]
        o = [f"Ligan asli: {lig['resn']} {lig['rantai']}{lig['resi']} ({lig['atom']} atom)" if lig else
             "Ligan asli tidak dikenali (tidak ada HET selain aditif).",
             f"Air penjembatan: {len(h['jembatan'])}",
             *[f"  HOH {j['rantai']}{j['resi']}" for j in h["jembatan"][:20]],
             f"Kofaktor: {len(h['kofaktor'])}",
             *[f"  {k['resn']} {k['rantai']}{k['resi']} ({k['atom']} atom)" for k in h["kofaktor"][:20]],
             "",
             "Centang pilihan yang sama pada Siapkan reseptor bila ingin mereka ikut ke PDBQT."]
        self._tulis("\n".join(o))

    def _syarat(self):
        wajib = [b.strip() for b in self.e_syarat.toPlainText().splitlines() if b.strip()]
        a = self.jw._aktif_inter
        if not a or not a.get("interaksi"):
            self._tulis("Pilih pose dulu agar interaksinya terhitung (klik pose di tab Hasil).")
            return
        ok, gagal = syarat.periksa(a["interaksi"], wajib)
        self._tulis("Pose memenuhi semua syarat." if ok else "Syarat yang tidak terpenuhi:\n" + "\n".join(gagal))

    def _mutasi(self):
        prot = self._protein()
        if not prot:
            self._tulis("Tidak ada protein.")
            return
        try:
            teks, catatan = mutasi.mutasi(prot.teks, self.e_mut_rantai.text().strip()[:1],
                                          self.e_mut_resi.text().strip(), self.e_mut_aa.text().strip())
        except Exception as e:
            self._tulis(str(e))
            return
        from ..core import molekul
        o = molekul.Objek(nama=f"{prot.nama} mutasi", jenis="protein", teks=teks, fmt="pdb", sumber="mutasi")
        self.jw.tambah_objek([o], fokus=True)
        self._tulis(catatan + "\nObjek baru ditambahkan. Siapkan sebagai reseptor bila akan didocking.")

    def _sunting(self):
        try:
            mol = self._mol()
            prot = self._protein()
            baru, smi, n = senyawa.sunting_kantong(mol, self.e_reaksi.text().strip(), prot.teks if prot else "")
        except Exception as e:
            self._tulis(str(e))
            return
        self._tambah_smiles([("suntingan", smi)])
        rec = self._pdbqt_reseptor()
        if not rec:
            self._tulis(f"SMILES {smi}\nAtom berat yang menabrak protein (< 1,7 Å): {n}. "
                        "Siapkan reseptor dulu bila skor Vina lokal ingin dihitung.")
            return
        self._tulis(f"SMILES {smi}. Tabrakan sebelum minimisasi: {n}. Vina sedang meminimisasi di tempat.")
        from . import kerja
        kerja.jalankan(lambda lapor, m=baru, r=rec, s=smi, nt=n: self._skor_suntingan(m, r, s, nt),
                       selesai=self._tulis, galat=self._tulis)

    def _skor_suntingan(self, mol, rec, smi, n):
        from ..core import lokal
        energi = lokal.minimisasi_lokal(rec, lokal.pdbqt_pose(mol))
        return (f"SMILES {smi}\nAtom berat yang menabrak protein sebelum minimisasi (< 1,7 Å): {n}\n"
                f"Skor Vina setelah minimisasi lokal: {energi:.2f} kcal/mol")

    def _blast(self):
        prot = self._protein()
        if not prot:
            self._tulis("Tidak ada protein di proyek.")
            return
        rantai = self.e_rantai.text().strip()[:1] or "A"
        urut = konservasi.sekuens_rantai(prot.teks, rantai)
        seq = "".join(aa for _, aa, _, _ in urut)
        if len(seq) < 10:
            self._tulis("Sekuens rantai terlalu pendek untuk BLAST.")
            return
        self._tulis("Sekuens dikirim ke NCBI (Swiss-Prot). Antrean bisa beberapa menit.")
        from . import kerja

        def kerja_blast(lapor, s=seq):
            try:
                return konservasi.blast_fasta(s, tunggu=300)
            except TimeoutError as e:
                return ("tunggu", str(e))

        def selesai(hasil):
            if isinstance(hasil, tuple) and hasil and hasil[0] == "tunggu":
                rid = hasil[1].split("RID ", 1)[-1].strip().rstrip(".")
                self._simpan_rid(rid)
                self._tulis(hasil[1] + "\nNCBI masih antre. Sekuens dikirim ke UniProt, lalu EBI, lalu pencarian sekuens RCSB bila perlu.")
                kerja.jalankan(lambda lapor, s=seq: konservasi.blast_pengganti(s),
                               selesai=lambda h: self._isi_homolog(h[0], (h[1], h[2])), galat=self._tulis)
                return
            rid, daftar = hasil
            self._simpan_rid(rid)
            self._isi_homolog(f"NCBI {rid}", (rid, daftar))

        kerja.jalankan(kerja_blast, selesai=selesai, galat=self._tulis)

    def _isi_homolog(self, sumber, hasil):
        _nomor, daftar = hasil
        self.e_fasta.setPlainText("".join(f">{j}\n{s}\n" for j, s in daftar))
        self._tulis(f"BLAST {sumber}: {len(daftar)} homolog. Tekan Hitung & warnai B-faktor. "
                    "Angka ini persen identitas, bukan skor ConSurf.")

    def _blast_uniprot(self):
        prot = self._protein()
        if not prot:
            self._tulis("Tidak ada protein di proyek.")
            return
        rantai = self.e_rantai.text().strip()[:1] or "A"
        urut = konservasi.sekuens_rantai(prot.teks, rantai)
        seq = "".join(aa for _, aa, _, _ in urut)
        if len(seq) < 10:
            self._tulis("Sekuens rantai terlalu pendek untuk BLAST.")
            return
        self._tulis("Sekuens dikirim ke UniProt. Bila layanan itu tidak menjawab, EBI, lalu pencarian sekuens RCSB PDB.")
        from . import kerja
        kerja.jalankan(lambda lapor, s=seq: konservasi.blast_pengganti(s),
                       selesai=lambda h: self._isi_homolog(h[0], (h[1], h[2])), galat=self._tulis)

    def _blast_ambil(self):
        rid = getattr(self, "_rid_blast", "") or str(
            ((getattr(getattr(self.jw, "proyek", None), "blast", None) or {}).get("rid") or ""))
        if not rid:
            self._tulis("Belum ada nomor BLAST. Kirim dulu, atau tunggu sampai baris RID muncul.")
            return
        self._tulis(f"Memeriksa BLAST {rid}…")
        from . import kerja

        def ambil(lapor, r=rid):
            st = konservasi.status_blast(r)
            if st != "READY":
                return ("tunggu", st)
            return ("siap", konservasi.urai_blast_xml(konservasi.ambil_blast_xml(r)))

        def selesai(hasil):
            if hasil[0] == "tunggu":
                self._tulis(f"BLAST {rid} masih {hasil[1]}.")
                return
            daftar = hasil[1]
            if not daftar:
                self._tulis(f"BLAST {rid} selesai tanpa homolog di atas ambang.")
                return
            self.e_fasta.setPlainText("".join(f">{j}\n{s}\n" for j, s in daftar))
            self._tulis(f"BLAST {rid}: {len(daftar)} homolog. Tekan Hitung & warnai B-faktor.")

        kerja.jalankan(ambil, selesai=selesai, galat=self._tulis)

    def _film(self):
        folder = QFileDialog.getExistingDirectory(self, "Folder hasil MD")
        if not folder:
            return
        try:
            teks, n = lanjutan.film_pdb(folder)
        except Exception as e:
            self._tulis(str(e))
            return
        self.jw.viewer.js("film", "film-md", teks)
        self._tulis(f"{n} bingkai diputar di viewport. Analisis › tutup film lewat memuat ulang protein "
                    "bila tampilan terasa menumpuk.")

    def _server(self):
        rec, lig = self._pdbqt_reseptor(), self._pdbqt_pose()
        if not rec or not lig:
            self._tulis("Butuh reseptor siap dan pose aktif.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Folder paket server")
        if not folder:
            return
        try:
            mol = self._mol()
            tujuan = lanjutan.paket_server(folder, self._protein().teks if self._protein() else rec, rec, mol)
        except Exception as e:
            self._tulis(str(e))
            return
        self._tulis(f"Paket ditulis ke {tujuan}: sistem_obc2.xml, kompleks.pdb, kompleks.gro, "
                    "kompleks.top bila ParmEd berhasil, dan BACA.txt.")

    def _figur(self):
        warna = [w.strip() for w in self.e_warna.text().split(",") if w.strip()]
        pesan = naskah.periksa_figur(self.e_dpi.value(), self.e_mm.value(), self.e_pt.value(), warna)
        self._tulis("\n".join(pesan) if pesan else "Tidak ada peringatan untuk angka ini.")

    def _skripsi(self):
        pr = self.jw.proyek
        baris = []
        if pr:
            for j in reversed(pr.job):
                for l in j.get("ligan") or []:
                    if l.get("energi") is not None and l.get("status") == "selesai":
                        baris.append((l.get("nama"), f"{l['energi']:.2f}", l.get("ki") or ""))
                if baris:
                    break
        info = {"nama": pr.nama if pr else "", "reseptor": (pr.reseptor or {}).get("nama", "") if pr else "",
                "mesin": pr.job[-1]["mesin"] if pr and pr.job else "",
                "baris": baris[:15],
                "validasi": "Lihat Docking › Validasi redocking bila RMSD kristal sudah dihitung."}
        teks = naskah.draf_skripsi(info)
        f, _ = QFileDialog.getSaveFileName(self, "Simpan draf", "draf_skripsi.md", "Markdown (*.md)")
        if f:
            open(f, "w", encoding="utf-8").write(teks)
            self._tulis(f"Draf ditulis ke {f}.\n\n" + teks[:1200])
        else:
            self._tulis(teks[:1500])

    def _bib(self):
        teks = naskah.bibtex()
        f, _ = QFileDialog.getSaveFileName(self, "Simpan BibTeX", "virmolab.bib", "BibTeX (*.bib)")
        if f:
            open(f, "w", encoding="utf-8").write(teks)
        self._tulis(teks[:1500])

    def _sdf_pose(self):
        from rdkit import Chem
        mol = self._mol()
        if mol.GetNumConformers() == 0:
            raise ValueError("Pose tidak punya koordinat 3D.")
        return Chem.MolToMolBlock(mol)

    def _gnina(self):
        prot = self._protein()
        if not prot:
            self._tulis("Tidak ada protein di proyek.")
            return
        try:
            sdf = self._sdf_pose()
        except Exception as e:
            self._tulis(str(e))
            return
        folder = QFileDialog.getExistingDirectory(self, "Folder hasil GNINA")
        if not folder:
            return
        self._tulis("GNINA sedang menilai pose. Pemuatan pertama model CNN bisa beberapa menit.")
        from . import kerja
        kerja.jalankan(lambda lapor: lanjutan.skor_gnina(prot.teks, sdf, folder),
                       selesai=self._tulis, galat=self._tulis)

    def _sekuens(self, teks):
        from ..core import konservasi
        rantai = []
        for b in teks.splitlines():
            if b.startswith("ATOM") and len(b) > 21:
                c = b[21].strip()
                if c and c not in rantai:
                    rantai.append(c)
        hasil = []
        for c in rantai or ["A"]:
            urut = konservasi.sekuens_rantai(teks, c)
            seq = "".join(x[1] for x in urut)
            if seq:
                hasil.append((c, seq))
        return hasil

    def _boltz(self, gpu):
        prot = self._protein()
        if not prot:
            self._tulis("Tidak ada protein di proyek.")
            return
        try:
            mol = self._mol()
        except ValueError as e:
            self._tulis(str(e))
            return
        from rdkit import Chem
        smi = Chem.MolToSmiles(Chem.RemoveHs(mol))
        seq = self._sekuens(prot.teks)
        folder = QFileDialog.getExistingDirectory(self, "Folder hasil Boltz")
        if not folder:
            return
        msa = self.c_msa.isChecked()
        penuh = self.c_penuh.isChecked()
        self._tulis("Boltz sedang berjalan di " + ("GPU" if gpu else "CPU") + ". "
                    + (f"{len(seq)} rantai. " if seq else "")
                    + ("Pengaturan penuh: 3 daur ulang, 200 langkah. " if penuh
                       else "Pengaturan diringkas: 1 daur ulang, 50 langkah. ")
                    + ("Sekuens dikirim ke ColabFold untuk MSA." if msa
                       else "MSA satu sekuens: hasilnya tidak untuk dibanding kristal."))
        from . import kerja
        kerja.jalankan(lambda lapor: lanjutan.prediksi_boltz(
                           seq, smi, folder, gpu=gpu, msa_server=msa, penuh=penuh),
                       selesai=self._tulis, galat=self._tulis)

    def _luar(self):
        g, b = lanjutan.status_gnina(), lanjutan.status_boltz()
        self._tulis(g["pesan"] + "\n\n" + b["pesan"])
