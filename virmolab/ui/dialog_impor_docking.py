"""Dialog Berkas › Impor hasil eksternal › Hasil docking…

Pose dan skor dari program docking lain dibaca, ditinjau per ligan, lalu disimpan sebagai job proyek sehingga
tabel hasil, interaksi, diagram 2D, PoseBusters, MD, dan ekspor bekerja seperti pada docking VirmoLab.
"""
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QProgressBar, QSpinBox, QSplitter,
                               QVBoxLayout, QWidget)

from ..core import impor_docking as I
from . import kerja, kit

FILTER_POSE = ("Hasil docking (*.pdbqt *.dlg *.sdf *.sd *.mol2 *.pdb *.ent);;"
               "Vina, QuickVina, Smina, GNINA, Uni-Dock (*.pdbqt);;AutoDock4, AutoDock-GPU (*.dlg);;"
               "GNINA, GOLD, Glide, rDock, MOE, DiffDock (*.sdf *.sd);;MOL2 (*.mol2);;PDB (*.pdb *.ent);;Semua (*.*)")
FILTER_RESEPTOR = "Reseptor (*.pdbqt *.pdb *.ent *.cif *.mmcif *.mol2);;Semua (*.*)"
KOLOM = ["Ligan", "Program", "Pose", "Skor pose 1", "Berkas", "Catatan"]


class DialogImporDocking(QDialog):
    selesai = Signal(object)          # dict job yang baru ditambahkan ke proyek

    def __init__(self, jw, berkas=()):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Impor hasil docking")
        self.setAcceptDrops(True)
        self.resize(1040, 760)
        self._cache = {}              # jalur -> (daftar LiganImpor, teks reseptor kompleks, galat)
        self._antre = []              # jalur yang sedang dibaca
        self.daftar = []
        self.f_reseptor = ""
        self._jalan = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul(
            "Impor hasil docking dari program lain",
            "Pose dan skor AutoDock Vina, QuickVina, Smina, GNINA, Uni-Dock, AutoDock4, AutoDock-GPU, GOLD, Glide, "
            "rDock, MOE, Discovery Studio, dan DiffDock dianalisis seperti hasil docking VirmoLab: tabel hasil, "
            "interaksi, diagram 2D, PoseBusters, MD, dan ekspor."))

        bagi = QSplitter(Qt.Horizontal)
        kiri = QWidget()
        vk = QVBoxLayout(kiri)
        vk.setContentsMargins(0, 0, 0, 0)
        vk.setSpacing(10)

        g = QGroupBox("Berkas pose")
        gv = QVBoxLayout(g)
        self.l_berkas = QListWidget()
        self.l_berkas.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.l_berkas.setMinimumHeight(140)
        gv.addWidget(self.l_berkas, 1)
        hb = QHBoxLayout()
        hb.addWidget(kit.tombol("Tambah berkas…", self._pilih_berkas))
        hb.addWidget(kit.tombol("Tambah folder…", self._pilih_folder))
        hb.addStretch(1)
        hb.addWidget(kit.tombol("Hapus", self._hapus_berkas, tip="Hapus berkas terpilih dari daftar"))
        gv.addLayout(hb)
        gv.addWidget(kit.catatan("PDBQT multi-MODEL, DLG, SDF/MOL2 multi-pose, atau PDB kompleks. Berkas boleh "
                                 "diseret ke jendela ini. Pose ligan bernama sama dari beberapa berkas digabung."))
        vk.addWidget(g, 1)

        g = QGroupBox("Reseptor")
        gv = QVBoxLayout(g)
        self.cb_rec = QComboBox()
        self.cb_rec.currentIndexChanged.connect(self._segarkan_tombol)
        gv.addWidget(self.cb_rec)
        hr = QHBoxLayout()
        hr.addWidget(kit.tombol("Pilih berkas reseptor…", self._pilih_reseptor))
        hr.addStretch(1)
        gv.addLayout(hr)
        gv.addWidget(kit.catatan("Pakai protein yang sama dengan yang dipakai saat docking. Air dan aditif dibuang; "
                                 "ion logam dan kofaktor dipertahankan."))
        vk.addWidget(g)

        g = QGroupBox("Skor")
        f = QFormLayout(g)
        self.cb_urut = QComboBox()
        self.cb_energi = QComboBox()
        self.sp_pose = QSpinBox()
        self.sp_pose.setRange(1, 50)
        self.sp_pose.setValue(20)
        self.sp_pose.setSuffix(" pose")
        self._manual = set()          # combobox skor yang sudah dipilih sendiri oleh pengguna
        for nama, w in (("urut", self.cb_urut), ("energi", self.cb_energi)):
            w.currentIndexChanged.connect(self._arti)
            w.activated.connect(lambda *_, n=nama: self._manual.add(n))
        f.addRow("Urutan pose", self.cb_urut)
        f.addRow("Kolom ΔG diisi dari", self.cb_energi)
        f.addRow("Maksimum per ligan", self.sp_pose)
        vk.addWidget(g)
        self.l_arti = kit.catatan("", "info")
        vk.addWidget(self.l_arti)
        bagi.addWidget(kiri)

        kanan = QWidget()
        vn = QVBoxLayout(kanan)
        vn.setContentsMargins(0, 0, 0, 0)
        g = QGroupBox("Ligan terbaca")
        gv = QVBoxLayout(g)
        self.tabel = kit.tabel(KOLOM, regang=5, urut=False)
        self.tabel.setSelectionMode(QAbstractItemView.NoSelection)
        gv.addWidget(self.tabel, 1)
        hp = QHBoxLayout()
        hp.addWidget(kit.tombol("Pilih semua", lambda: self._centang(True)))
        hp.addWidget(kit.tombol("Kosongkan", lambda: self._centang(False)))
        hp.addStretch(1)
        self.l_ringkas = QLabel()
        self.l_ringkas.setObjectName("muted")
        hp.addWidget(self.l_ringkas)
        gv.addLayout(hp)
        vn.addWidget(g, 1)
        self.l_galat = kit.catatan("", "peringatan")
        self.l_galat.setVisible(False)
        vn.addWidget(self.l_galat)
        bagi.addWidget(kanan)
        bagi.setSizes([400, 640])
        lay.addWidget(bagi, 1)

        self.prog = QProgressBar()
        self.prog.setRange(0, 100)
        self.prog.setTextVisible(False)
        self.prog.setFixedHeight(6)
        self.prog.setVisible(False)
        lay.addWidget(self.prog)
        self.l_status = kit.catatan("")
        self.b_impor = kit.tombol("Impor ke proyek", self._impor, utama=True,
                                  tip="Simpan ligan tercentang sebagai job hasil di proyek")
        lay.addWidget(self.l_status)
        lay.addLayout(kit.bar_bawah(self, kanan=[self.b_impor]))

        self._isi_reseptor()
        self._isi_skor()
        self._segarkan_tombol()
        if berkas:
            self.tambah(berkas)

    # ------------------------------------------------------------ berkas
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        fs = []
        for u in e.mimeData().urls():
            if not u.isLocalFile():
                continue
            p = Path(u.toLocalFile())
            fs += sorted(str(x) for x in p.rglob("*") if x.suffix.lower() in I.EKSTENSI) if p.is_dir() else [str(p)]
        self.tambah(fs)

    def _dir(self):
        return self.jw.st.value("dir_impor_docking", self.jw.st.value("dir_terakhir", ""))

    def _pilih_berkas(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Berkas hasil docking", self._dir(), FILTER_POSE)
        if fs:
            self.jw.st.setValue("dir_impor_docking", str(Path(fs[0]).parent))
            self.tambah(fs)

    def _pilih_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Folder hasil docking", self._dir())
        if d:
            self.jw.st.setValue("dir_impor_docking", d)
            fs = sorted(str(x) for x in Path(d).rglob("*") if x.suffix.lower() in I.EKSTENSI)
            if not fs:
                self.l_status.setText("Tidak ada berkas hasil docking di folder itu.")
            self.tambah(fs)

    def tambah(self, fs):
        """Tambah berkas: protein tanpa ligan dijadikan reseptor, sisanya dibaca sebagai pose di latar."""
        baru = []
        for f in fs:
            f = str(Path(f))
            if f in self._cache or f in self._antre or f in baru:
                continue
            if I.tampak_reseptor(f):
                self._set_reseptor(f)
                continue
            if Path(f).suffix.lower() in I.EKSTENSI:
                baru.append(f)
        if not baru:
            return
        self._antre += baru
        for f in baru:
            it = QListWidgetItem(Path(f).name)
            it.setData(Qt.UserRole, f)
            it.setToolTip(f)
            it.setForeground(kit.warna("ink2"))
            self.l_berkas.addItem(it)
        self.prog.setVisible(True)
        self.prog.setValue(0)
        self.l_status.setText(f"Membaca {len(baru)} berkas…")
        self._segarkan_tombol()

        def baca(lapor, daftar=list(baru)):
            out = {}
            for i, f in enumerate(daftar, 1):
                lapor.progres.emit(int(100 * (i - 1) / len(daftar)), 100, Path(f).name)
                try:
                    lg, rec = I.baca_berkas(f)
                    out[f] = (lg, rec, "")
                except Exception as e:
                    out[f] = ([], "", str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__)
            return out

        kerja.jalankan(baca, selesai=self._terbaca, galat=self._gagal_baca,
                       progres=lambda a, b, t: (self.prog.setValue(int(100 * a / max(1, b))),
                                                self.l_status.setText(f"Membaca {t}…")))

    def _terbaca(self, hasil):
        for f, isi in hasil.items():
            if f in self._antre:
                self._antre.remove(f)
            self._cache[f] = isi
        for i in range(self.l_berkas.count()):
            it = self.l_berkas.item(i)
            f = it.data(Qt.UserRole)
            if f in hasil:
                lg, _, gal = hasil[f]
                it.setForeground(kit.warna("bad" if gal else "ink"))
                it.setText(f"{Path(f).name}  ·  " + (f"gagal: {gal}" if gal else
                                                      f"{len(lg)} ligan, {sum(len(x.pose) for x in lg)} pose"))
        if not self._antre:
            self.prog.setVisible(False)
        self._susun()

    def _gagal_baca(self, pesan):
        self._antre.clear()
        self.prog.setVisible(False)
        self.l_status.setText("Pembacaan berkas gagal: " + pesan.splitlines()[0])
        self._segarkan_tombol()

    def _hapus_berkas(self):
        for it in self.l_berkas.selectedItems():
            f = it.data(Qt.UserRole)
            self._cache.pop(f, None)
            self.l_berkas.takeItem(self.l_berkas.row(it))
        self._isi_reseptor()
        self._susun()

    # ------------------------------------------------------------ reseptor
    def _set_reseptor(self, f):
        self.f_reseptor = f
        self.jw.st.setValue("dir_impor_docking", str(Path(f).parent))
        self._isi_reseptor(pilih="berkas")

    def _pilih_reseptor(self):
        f, _ = QFileDialog.getOpenFileName(self, "Berkas reseptor", self._dir(), FILTER_RESEPTOR)
        if f:
            self._set_reseptor(f)

    def _isi_reseptor(self, pilih=None):
        lama = pilih or self.cb_rec.currentData()
        self.cb_rec.blockSignals(True)
        self.cb_rec.clear()
        if self.f_reseptor:
            self.cb_rec.addItem(f"Berkas: {Path(self.f_reseptor).name}", "berkas")
        for f, (_, rec, _) in self._cache.items():
            if rec:
                self.cb_rec.addItem(f"Protein di berkas kompleks: {Path(f).name}", f"kompleks:{f}")
        pr = self.jw.proyek
        if pr and (pr.reseptor or {}).get("pdbqt") and pr.p(pr.reseptor["pdbqt"]).exists():
            self.cb_rec.addItem(f"Reseptor proyek: {(pr.reseptor or {}).get('nama') or 'reseptor.pdbqt'}", "proyek")
        for o in self.jw.objek.values():
            if o.jenis == "protein" and not o.info.get("siap_docking") and not o.info.get("reseptor_job"):
                self.cb_rec.addItem(f"Protein di viewport: {o.nama}", f"objek:{o.id}")
        if not self.cb_rec.count():
            self.cb_rec.addItem("Belum ada reseptor - pilih berkas reseptor", None)
        i = self.cb_rec.findData(lama) if lama else -1
        self.cb_rec.setCurrentIndex(i if i >= 0 else 0)
        self.cb_rec.blockSignals(False)
        self._segarkan_tombol()

    def _bahan_reseptor(self):
        """(fungsi pembuat (pdb, pdbqt), keterangan sumber) untuk pilihan reseptor sekarang."""
        k = self.cb_rec.currentData()
        if not k:
            return None, ""
        if k == "berkas":
            f = self.f_reseptor
            return (lambda: I.siapkan_reseptor(f)), f
        if k.startswith("kompleks:"):
            f = k.split(":", 1)[1]
            teks = self._cache[f][1]
            return (lambda: I.siapkan_reseptor(teks=teks, fmt="pdb")), f"protein di {Path(f).name}"
        if k == "proyek":
            pr = self.jw.proyek
            fq = pr.p(pr.reseptor["pdbqt"])
            fb = next((pr.p(pr.reseptor[x]) for x in ("bersih", "meeko") if (pr.reseptor or {}).get(x)
                       and pr.p(pr.reseptor[x]).exists()), None)

            def dari_proyek():
                pdb, pdbqt = I.siapkan_reseptor(fq)
                return (fb.read_text(encoding="utf-8", errors="replace") if fb else pdb), pdbqt
            return dari_proyek, "reseptor proyek"
        if k.startswith("objek:"):
            o = self.jw.objek.get(k.split(":", 1)[1])
            if o is None:
                return None, ""
            teks = o.teks
            return (lambda: I.siapkan_reseptor(teks=teks, fmt="pdb")), f"objek {o.nama}"
        return None, ""

    # ------------------------------------------------------------ tabel & skor
    def _susun(self):
        urut = [self.l_berkas.item(i).data(Qt.UserRole) for i in range(self.l_berkas.count())]
        kel = [self._cache[f][0] for f in urut if f in self._cache and self._cache[f][0]]
        centang = {self.tabel.item(r, 0).text(): self.tabel.item(r, 0).checkState() == Qt.Checked
                   for r in range(self.tabel.rowCount())}
        try:
            self.daftar = I.gabung(kel)
        except Exception as e:
            self.daftar = []
            self.l_status.setText(f"Penggabungan pose gagal: {e}")
        galat = [f"{Path(f).name}: {self._cache[f][2]}" for f in urut if f in self._cache and self._cache[f][2]]
        self.l_galat.setText("Tidak terbaca:\n" + "\n".join(galat[:6]) + (f"\n… dan {len(galat) - 6} lainnya"
                                                                           if len(galat) > 6 else ""))
        self.l_galat.setVisible(bool(galat))
        self._isi_skor()
        t = self.tabel
        t.setRowCount(len(self.daftar))
        utama = self.cb_urut.currentData()
        for r, lg in enumerate(self.daftar):
            it = kit.sel(lg.nama, rata_kanan=False)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if centang.get(lg.nama, True) else Qt.Unchecked)
            t.setItem(r, 0, it)
            t.setItem(r, 1, kit.sel(lg.program, rata_kanan=False))
            t.setItem(r, 2, kit.sel_angka(len(lg.pose), 0))
            skor = lg.pose[0].skor
            k = utama if utama in skor else next(iter(skor), None)
            t.setItem(r, 3, kit.sel(f"{I.jenis_skor(k).label} {kit.f(skor[k], 2)}" if k else "–", rata_kanan=False))
            t.setItem(r, 4, kit.sel(", ".join(Path(b).name for b in lg.berkas[:2])
                                    + (f" +{len(lg.berkas) - 2}" if len(lg.berkas) > 2 else ""), rata_kanan=False))
            t.item(r, 4).setToolTip("\n".join(lg.berkas))
            t.setItem(r, 5, kit.sel("; ".join(lg.catatan[:2]) if lg.catatan else "", rata_kanan=False))
            if lg.catatan:
                t.item(r, 5).setToolTip("\n".join(lg.catatan))
        t.resizeColumnsToContents()
        self._ringkas()
        self._isi_reseptor()
        if not self._antre:
            n = len(self.daftar)
            self.l_status.setText(f"{n} ligan siap ditinjau." if n else "")

    def _isi_skor(self):
        info = I.opsi_bawaan(self.daftar)
        lama_u, lama_e = self.cb_urut.currentData(), self.cb_energi.currentData()
        for cb in (self.cb_urut, self.cb_energi):
            cb.blockSignals(True)
            cb.clear()
        for tag in info["tag"]:
            s = I.jenis_skor(tag)
            arah = "kecil = baik" if s.rendah else "besar = baik"
            self.cb_urut.addItem(f"{I.label_skor(tag)} · {arah}", tag)
            if s.energi:
                self.cb_energi.addItem(f"{I.label_skor(tag)} (skor asli)", tag)
        self.cb_urut.addItem("Urutan di berkas", None)
        self.cb_energi.addItem("Skor ulang Vina di reseptor (--score_only)", "vina_ulang")
        # pilihan pengguna dipertahankan selama masih tersedia; selain itu ikut saran bawaan berkas
        u = lama_u if "urut" in self._manual and (lama_u is None or lama_u in info["tag"]) else info["skor_utama"]
        e = lama_e if "energi" in self._manual and (lama_e == "vina_ulang" or lama_e in info["tag"])             else info["energi"]
        i = self.cb_urut.findData(u)
        self.cb_urut.setCurrentIndex(i if i >= 0 else self.cb_urut.count() - 1)
        i = self.cb_energi.findData(e)
        self.cb_energi.setCurrentIndex(i if i >= 0 else self.cb_energi.count() - 1)
        for cb in (self.cb_urut, self.cb_energi):
            cb.blockSignals(False)
        self._arti()

    def _arti(self):
        u, e = self.cb_urut.currentData(), self.cb_energi.currentData()
        if not self.daftar:
            self.l_arti.setText("Tambahkan berkas hasil docking untuk melihat skor yang tersedia.")
            return
        teks = []
        if u:
            s = I.jenis_skor(u)
            teks.append(f"Pose 1 = {I.label_skor(u)} terkecil; ligan tanpa skor ini diurutkan dengan skor utama "
                        "programnya sendiri." if s.rendah else
                        f"Pose 1 = {I.label_skor(u)} terbesar; ligan tanpa skor ini diurutkan dengan skor utama "
                        "programnya sendiri.")
        else:
            teks.append("Urutan pose mengikuti berkas asal.")
        if e == "vina_ulang":
            teks.append("ΔG dihitung ulang dengan fungsi skor Vina pada pose apa adanya, tanpa minimisasi. "
                        "Skor asli program tetap disimpan dan tampil di tooltip ΔG serta panel Properti.")
            if any(not I.jenis_skor(t).energi for t in I.opsi_bawaan(self.daftar)["tag"]):
                teks.append("Fitness atau probabilitas tidak berdimensi energi, jadi tidak dipakai sebagai ΔG.")
        elif e:
            s = I.jenis_skor(e)
            teks.append(f"ΔG = {I.label_skor(e)} dari program asal"
                        + (" (dikonversi dari kJ/mol)." if s.faktor != 1.0 else ".")
                        + " Pose tanpa skor ini diberi skor ulang Vina.")
        self.l_arti.setText(" ".join(teks))

    def _centang(self, on):
        for r in range(self.tabel.rowCount()):
            self.tabel.item(r, 0).setCheckState(Qt.Checked if on else Qt.Unchecked)
        self._ringkas()

    def _terpilih(self):
        nama = {self.tabel.item(r, 0).text() for r in range(self.tabel.rowCount())
                if self.tabel.item(r, 0).checkState() == Qt.Checked}
        return [lg for lg in self.daftar if lg.nama in nama]

    def _ringkas(self):
        p = self._terpilih()
        self.l_ringkas.setText(f"{len(p)} dari {len(self.daftar)} ligan · "
                               f"{sum(min(len(x.pose), self.sp_pose.value()) for x in p)} pose")
        self._segarkan_tombol()

    def _segarkan_tombol(self, *_):
        ok = bool(self.daftar) and self.cb_rec.currentData() is not None and not self._antre and not self._jalan
        self.b_impor.setEnabled(ok)

    # ------------------------------------------------------------ impor
    def _impor(self):
        pilih = self._terpilih()
        buat_rec, sumber_rec = self._bahan_reseptor()
        if not pilih or buat_rec is None:
            self.l_status.setText("Centang minimal satu ligan dan pilih reseptor.")
            return
        pr = self.jw._pastikan_proyek()
        program = ", ".join(dict.fromkeys(lg.program for lg in pilih))
        opsi = {"skor_utama": self.cb_urut.currentData(), "urut": "skor" if self.cb_urut.currentData() else "berkas",
                "energi": self.cb_energi.currentData(), "program": program, "sumber_reseptor": sumber_rec,
                "sumber_berkas": [b for lg in pilih for b in lg.berkas]}
        maks = self.sp_pose.value()
        self._jalan = True
        self._segarkan_tombol()
        self.prog.setVisible(True)
        self.prog.setValue(0)
        self.l_status.setText("Menyiapkan reseptor…")

        def kerjakan(lapor):
            lapor.progres.emit(2, 100, "Menyiapkan reseptor")
            pdb, pdbqt = buat_rec()
            return I.simpan_ke_proyek(pr, pilih, pdb, pdbqt, opsi, lapor, maks_pose=maks)

        kerja.jalankan(kerjakan, selesai=self._selesai, galat=self._gagal,
                       progres=lambda a, b, t: (self.prog.setValue(int(100 * a / max(1, b))),
                                                self.l_status.setText(t + "…")))

    def _selesai(self, job):
        self._jalan = False
        self.prog.setVisible(False)
        self.selesai.emit(job)
        self.accept()

    def _gagal(self, pesan):
        self._jalan = False
        self.prog.setVisible(False)
        self.l_status.setText("Impor gagal: " + pesan.strip().splitlines()[0])
        self._segarkan_tombol()
