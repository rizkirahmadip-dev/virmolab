"""Docking peptida (F10): masukkan sekuens, jalankan co-folding Boltz-2, nilai antarmukanya.

Vina dan AutoDock-GPU lemah untuk peptida karena ikatan berputarnya banyak, jadi kompleks dibangun
dengan Boltz-2 lalu dimurnikan singkat dengan OpenMM (lihat `core/peptida.py`).
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QGroupBox, QHBoxLayout, QHeaderView,
                               QLabel, QPlainTextEdit, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import catat, molekul, peptida
from . import kerja, kit


class DialogPeptida(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.jw = parent
        self.proyek = getattr(parent, "proyek", None)
        self.setWindowTitle("Docking peptida")
        self.setMinimumSize(980, 640)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self._hasil = None
        self._kerja = None
        self._bangun()
        self._periksa_sekuens()

    # ------------------------------------------------------------------ tata letak
    def _bangun(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul("Docking peptida",
                                "Bangun kompleks peptida dan reseptor dengan co-folding Boltz-2"))
        lay.addWidget(kit.catatan(
            "Fungsi skor docking dirancang untuk molekul kecil dan kurang dapat dipercaya bagi peptida. "
            "Alur ini memakai Boltz-2, lalu memurnikan kompleksnya dan menilai antarmukanya.",
            "peringatan"))

        isi = QHBoxLayout()
        isi.setSpacing(12)

        # Kiri: masukan
        kiri = QWidget()
        vk = QVBoxLayout(kiri)
        vk.setContentsMargins(0, 0, 0, 0)
        vk.setSpacing(8)

        g_seq = QGroupBox("Sekuens peptida")
        v_seq = QVBoxLayout(g_seq)
        self.t_seq = QPlainTextEdit()
        self.t_seq.setPlaceholderText("Kode satu huruf, misalnya ETFSDLWKLLP")
        self.t_seq.setFont(QFont("Consolas", 11))
        self.t_seq.setFixedHeight(84)
        self.t_seq.textChanged.connect(self._periksa_sekuens)
        v_seq.addWidget(self.t_seq)
        self.l_periksa = QLabel("")
        self.l_periksa.setWordWrap(True)
        v_seq.addWidget(self.l_periksa)
        vk.addWidget(g_seq)

        g_rec = QGroupBox("Reseptor")
        v_rec = QVBoxLayout(g_rec)
        self.l_reseptor = QLabel("")
        self.l_reseptor.setWordWrap(True)
        v_rec.addWidget(self.l_reseptor)
        vk.addWidget(g_rec)

        g_opsi = QGroupBox("Pemurnian")
        v_opsi = QVBoxLayout(g_opsi)
        self.c_murni = QCheckBox("Minimisasi kompleks di pelarut implisit")
        self.c_murni.setChecked(True)
        self.c_murni.toggled.connect(lambda v: self.s_ps.setEnabled(v))
        v_opsi.addWidget(self.c_murni)
        h_ps = QHBoxLayout()
        h_ps.addWidget(QLabel("Dinamika singkat:"))
        self.s_ps = QDoubleSpinBox()
        self.s_ps.setRange(0.0, 500.0)
        self.s_ps.setValue(0.0)
        self.s_ps.setSingleStep(10.0)
        self.s_ps.setDecimals(0)
        self.s_ps.setSuffix(" ps")
        self.s_ps.setToolTip("0 berarti minimisasi saja. Dinamika memakan waktu jauh lebih lama.")
        h_ps.addWidget(self.s_ps)
        h_ps.addStretch(1)
        v_opsi.addLayout(h_ps)
        self.c_gpu = QCheckBox("Pakai GPU untuk Boltz-2")
        self.c_gpu.setChecked(True)
        v_opsi.addWidget(self.c_gpu)
        vk.addWidget(g_opsi)

        self.b_jalan = kit.tombol("Jalankan", self._jalankan, utama=True)
        vk.addWidget(self.b_jalan)
        self.l_status = QLabel("")
        self.l_status.setWordWrap(True)
        self.l_status.setObjectName("muted")
        vk.addWidget(self.l_status)
        vk.addStretch(1)
        kiri.setFixedWidth(360)
        isi.addWidget(kiri)

        # Kanan: hasil
        kanan = QWidget()
        vn = QVBoxLayout(kanan)
        vn.setContentsMargins(0, 0, 0, 0)
        vn.setSpacing(8)

        self.k_plddt = kit.Kartu("PLDDT KOMPLEKS", "–", "Keyakinan model")
        self.k_rmsd = kit.Kartu("GESERAN MINIMISASI", "–", "Perpindahan peptida")
        vn.addLayout(kit.baris_kartu(self.k_plddt, self.k_rmsd))
        self.k_mmgbsa = kit.Kartu("MM/GBSA", "–", "Perkiraan kkal/mol")
        self.k_bsa = kit.Kartu("LUAS TERKUBUR", "–", "ΔSASA antarmuka")
        vn.addLayout(kit.baris_kartu(self.k_mmgbsa, self.k_bsa))

        self.l_antarmuka = QLabel("")
        self.l_antarmuka.setWordWrap(True)
        self.l_antarmuka.setObjectName("muted")
        vn.addWidget(self.l_antarmuka)

        g_tab = QGroupBox("Residu antarmuka")
        v_tab = QVBoxLayout(g_tab)
        self.tabel = kit.tabel(["Rantai", "Residu", "Nomor"], urut=True)
        # Tiga kolom pendek: dibagi rata supaya tidak ada kolom kosong selebar setengah tabel
        self.tabel.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        v_tab.addWidget(self.tabel)
        vn.addWidget(g_tab, 1)
        isi.addWidget(kanan, 1)
        lay.addLayout(isi, 1)

        self.b_muat = kit.tombol("Muat kompleks ke penampil", self._muat_ke_penampil)
        self.b_muat.setEnabled(False)
        lay.addLayout(kit.bar_bawah(self, kiri=[self.b_muat], tutup=True))
        self._isi_reseptor()

    # ------------------------------------------------------------------ masukan
    def _isi_reseptor(self):
        teks, nama, _ = kit.reseptor_proyek(self.jw) if self.jw else ("", "", None)
        self._rantai_reseptor = []
        if not teks:
            self.l_reseptor.setText("Belum ada reseptor di proyek. Siapkan protein pada langkah 1.")
            return
        for ch, seq in peptida.sekuens_dari_pdb(teks):
            if seq.strip("X"):
                self._rantai_reseptor.append((ch, seq))
        rinci = ", ".join(f"{ch} ({len(seq)} residu)" for ch, seq in self._rantai_reseptor)
        self.l_reseptor.setText(f"{nama}: {rinci}" if rinci else f"{nama}: tanpa rantai protein yang terbaca.")

    def _periksa_sekuens(self):
        v = peptida.validasi_sekuens(self.t_seq.toPlainText())
        self._tandai_galat(v["posisi_galat"])
        if v["sah"]:
            pesan = f"{v['panjang']} residu."
            if v["peringatan"]:
                pesan += " " + v["peringatan"]
                self.l_periksa.setStyleSheet(f"color: {kit.warna('warn').name()};")
            else:
                self.l_periksa.setStyleSheet(f"color: {kit.warna('mut').name()};")
        else:
            pesan = v["pesan"]
            self.l_periksa.setStyleSheet(f"color: {kit.warna('bad').name()};")
        self.l_periksa.setText(pesan)
        self.b_jalan.setEnabled(bool(v["sah"] and getattr(self, "_rantai_reseptor", None)))

    def _tandai_galat(self, posisi):
        """Sorot huruf yang tidak dikenal; pemformatan tidak boleh memicu textChanged lagi."""
        self.t_seq.blockSignals(True)
        kursor = self.t_seq.textCursor()
        simpan = kursor.position()
        polos = QTextCharFormat()
        kursor.select(QTextCursor.Document)
        kursor.setCharFormat(polos)
        if posisi:
            merah = QTextCharFormat()
            merah.setForeground(kit.warna("bad"))
            merah.setFontUnderline(True)
            teks = self.t_seq.toPlainText()
            peta = [i for i, c in enumerate(teks) if not c.isspace()]
            for p in posisi:
                if p < len(peta):
                    kursor.setPosition(peta[p])
                    kursor.setPosition(peta[p] + 1, QTextCursor.KeepAnchor)
                    kursor.setCharFormat(merah)
        kursor.setPosition(min(simpan, len(self.t_seq.toPlainText())))
        self.t_seq.setTextCursor(kursor)
        self.t_seq.blockSignals(False)

    # ------------------------------------------------------------------ jalankan
    def _jalankan(self):
        from ..core import lanjutan

        v = peptida.validasi_sekuens(self.t_seq.toPlainText())
        if not v["sah"] or not self._rantai_reseptor:
            return
        st = lanjutan.status_boltz()
        if not st.get("ada"):
            kit.pesan_peringatan(self, st.get("pesan", "Boltz-2 belum terpasang di WSL."))
            return
        if not self.proyek:
            kit.pesan_peringatan(self, "Buka atau buat proyek dulu supaya hasilnya dapat disimpan.")
            return

        folder = Path(self.proyek.p("peptida", v["sekuens"][:12]))
        folder.mkdir(parents=True, exist_ok=True)
        rantai = list(self._rantai_reseptor)
        gpu = self.c_gpu.isChecked()
        murni = self.c_murni.isChecked()
        ps = self.s_ps.value() if murni else 0.0

        self.b_jalan.setEnabled(False)
        self.l_status.setText("Menjalankan Boltz-2. Prediksi peptida memakan waktu beberapa menit.")

        def kerjakan(lapor=None):
            if lapor:
                lapor.log.emit("Menjalankan Boltz-2 untuk peptida…")
            peptida.cofold_peptida(rantai, v["sekuens"], folder, gpu=gpu)
            if lapor:
                lapor.log.emit("Prediksi selesai. Memurnikan kompleks dan menilai antarmuka…")
            return peptida.analisis_peptida(folder, v["sekuens"], ps_dinamika=ps, murni=murni,
                                            lapor=(lapor.log.emit if lapor else None))

        self._kerja = kerja.jalankan(kerjakan, selesai=self._selesai, galat=self._galat,
                                     log=self.l_status.setText)

    def _galat(self, teks):
        self.b_jalan.setEnabled(True)
        self.l_status.setText(f"Gagal: {teks.splitlines()[0]}")

    def _selesai(self, hasil):
        self.b_jalan.setEnabled(True)
        self._hasil = hasil
        if not hasil.tersedia:
            self.l_status.setText(hasil.pesan or "Prediksi tidak menghasilkan kompleks.")
            return

        self.k_plddt.isi(kit.f(hasil.plddt, 1) if hasil.plddt is not None else "–")
        self.k_rmsd.isi(kit.f(hasil.rmsd_minimisasi, 2, "Å") if hasil.rmsd_minimisasi is not None else "–")
        if hasil.mmgbsa and hasil.mmgbsa.get("dG") is not None:
            self.k_mmgbsa.isi(kit.f(hasil.mmgbsa["dG"], 1))
        else:
            self.k_mmgbsa.isi("–")

        ant = hasil.antarmuka or {}
        if ant.get("error"):
            self.k_bsa.isi("–", ant["error"][:60])
        else:
            self.k_bsa.isi(kit.f(ant.get("bsa_luas"), 0, "Å²") if ant.get("bsa_luas") is not None else "–")
        self._isi_tabel(ant)
        if not ant.get("error"):
            self.l_antarmuka.setText(
                f"{ant.get('kontak_total', 0)} kontak atom berat, {ant.get('ikatan_h', 0)} ikatan hidrogen, "
                f"{ant.get('jembatan_garam', 0)} jembatan garam antara rantai {ant.get('rantai_a', '')} "
                f"dan {ant.get('rantai_b', '')}.")
        else:
            self.l_antarmuka.setText(ant["error"])

        self.b_muat.setEnabled(bool(hasil.pdb_kompleks_murni or hasil.pdb_kompleks))
        bagian = [f"rantai peptida {hasil.rantai_peptida}"]
        if hasil.rincian.get("pemurnian_galat"):
            bagian.append(f"pemurnian gagal: {hasil.rincian['pemurnian_galat']}")
        self.l_status.setText("Selesai: " + "; ".join(bagian) + ".")
        self._simpan_ke_proyek(hasil)

    def _isi_tabel(self, ant):
        """ppi.skor_antarmuka memberi residu sebagai teks "RESN RESI" per rantai."""
        baris_data = []
        for kunci, rantai in (("residu_a", ant.get("rantai_a", "")), ("residu_b", ant.get("rantai_b", ""))):
            for teks in (ant.get(kunci) or []):
                bagian = teks.split()
                baris_data.append((rantai, bagian[0] if bagian else teks,
                                   bagian[1] if len(bagian) > 1 else ""))
        self.tabel.setRowCount(len(baris_data))
        for i, (rantai, resn, resi) in enumerate(baris_data):
            self.tabel.setItem(i, 0, QTableWidgetItem(rantai))
            self.tabel.setItem(i, 1, QTableWidgetItem(resn))
            self.tabel.setItem(i, 2, kit.sel_angka(resi, d=0) if resi.isdigit() else QTableWidgetItem(resi))

    def _simpan_ke_proyek(self, hasil):
        if not self.proyek:
            return
        daftar = getattr(self.proyek, "peptida", None)
        if daftar is None:
            daftar = []
            self.proyek.peptida = daftar
        daftar.append(hasil.to_dict())
        if self.jw and hasattr(self.jw, "minta_simpan"):
            self.jw.minta_simpan()

    def _muat_ke_penampil(self):
        if not self._hasil or not self.jw:
            return
        teks = self._hasil.pdb_kompleks_murni or self._hasil.pdb_kompleks
        if not teks:
            return
        try:
            o = molekul.Objek(nama=f"Kompleks peptida {self._hasil.sekuens[:12]}", jenis="kompleks",
                              teks=teks, fmt="pdb", sumber="Boltz-2 peptida")
            o.gaya = {"reps": ["cartoon"], "warna": {"mode": "chain"}, "opacity": 1.0,
                      "permukaan": None, "khusus": [
                          {"sel": {"chain": self._hasil.rantai_peptida}, "rep": "sticks",
                           "warna": {"mode": "solid", "val": "#e8590c"}}]}
            self.jw.tambah_objek([o], fokus=True)
            self.l_status.setText("Kompleks dimuat ke penampil; peptida ditandai jingga.")
        except Exception as e:
            catat.log.warning(f"Gagal memuat kompleks peptida: {e}")
            self.l_status.setText(f"Gagal memuat ke penampil: {e}")


__all__ = ["DialogPeptida"]
