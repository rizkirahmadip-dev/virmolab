"""Energi bebas relatif alkimia (F9, eksperimental): susun jaringan perturbasi dan analisis hasil.

Dialog ini sengaja tidak menyediakan tombol untuk menjalankan simulasi di Windows: mesin RBFE sumber
terbuka yang matang hanya berjalan di Linux dan macOS. Yang disediakan adalah perencanaan jaringan,
estimasi beban, dan analisis hasil yang dihitung di tempat lain. Menyembunyikan batasan ini akan
membuat pengguna menunggu sesuatu yang tidak akan pernah berjalan.
"""
import csv

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QGroupBox,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QSpinBox,
                               QSplitter, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import rbfe
from . import kerja, kit

KOLOM = ["Dari", "Ke", "Atom berubah", "ΔΔG (kkal/mol)", "Galat", "Catatan"]


class DialogRbfe(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.jw = parent
        self.proyek = getattr(parent, "proyek", None)
        self.setWindowTitle("Energi bebas relatif (eksperimental)")
        self.setMinimumSize(1060, 680)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self._jaringan = None
        self._kerja = None
        self._bangun()
        self._muat_ligan()

    def _bangun(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul("Energi bebas relatif (eksperimental)",
                                "Susun jaringan perturbasi untuk seri senyawa kongenerik"))

        st = rbfe.status_mesin()
        lay.addWidget(kit.catatan(st["pesan"], "muted" if st["ada"] else "peringatan"))

        split = QSplitter(Qt.Horizontal, self)
        split.setChildrenCollapsible(False)

        kiri = QWidget()
        vk = QVBoxLayout(kiri)
        vk.setContentsMargins(0, 0, 8, 0)
        vk.setSpacing(8)

        g_seri = QGroupBox("Seri senyawa")
        v_seri = QVBoxLayout(g_seri)
        self.daftar = QListWidget()
        self.daftar.setSelectionMode(QListWidget.NoSelection)
        v_seri.addWidget(self.daftar)
        h_p = QHBoxLayout()
        h_p.addWidget(kit.tombol("Pilih semua", lambda: self._centang(True)))
        h_p.addWidget(kit.tombol("Kosongkan", lambda: self._centang(False)))
        v_seri.addLayout(h_p)
        vk.addWidget(g_seri, 1)

        g_par = QGroupBox("Protokol yang direncanakan")
        v_par = QVBoxLayout(g_par)
        h_mode = QHBoxLayout()
        h_mode.addWidget(QLabel("Jaringan:"))
        self.cb_mode = QComboBox()
        self.cb_mode.addItem("Pohon rentang minimum", "mst")
        self.cb_mode.addItem("Bintang", "bintang")
        h_mode.addWidget(self.cb_mode, 1)
        v_par.addLayout(h_mode)

        h_l = QHBoxLayout()
        h_l.addWidget(QLabel("Jendela λ:"))
        self.s_lambda = QSpinBox()
        self.s_lambda.setRange(5, 25)
        self.s_lambda.setValue(11)
        h_l.addWidget(self.s_lambda)
        h_l.addWidget(QLabel("Replika:"))
        self.s_replika = QSpinBox()
        self.s_replika.setRange(1, 5)
        self.s_replika.setValue(3)
        h_l.addWidget(self.s_replika)
        v_par.addLayout(h_l)

        h_ns = QHBoxLayout()
        h_ns.addWidget(QLabel("ns per jendela:"))
        self.s_ns = QDoubleSpinBox()
        self.s_ns.setRange(0.5, 50.0)
        self.s_ns.setValue(5.0)
        self.s_ns.setSingleStep(0.5)
        h_ns.addWidget(self.s_ns)
        h_ns.addStretch(1)
        v_par.addLayout(h_ns)
        vk.addWidget(g_par)

        self.b_susun = kit.tombol("Susun jaringan", self._susun, utama=True)
        vk.addWidget(self.b_susun)
        self.l_status = QLabel("")
        self.l_status.setWordWrap(True)
        self.l_status.setObjectName("muted")
        vk.addWidget(self.l_status)
        kiri.setFixedWidth(340)
        split.addWidget(kiri)

        kanan = QWidget()
        vn = QVBoxLayout(kanan)
        vn.setContentsMargins(8, 0, 0, 0)
        vn.setSpacing(8)
        self.tabel = kit.tabel(KOLOM, urut=True)
        vn.addWidget(self.tabel, 1)

        g_beban = QGroupBox("Perkiraan beban")
        v_beban = QVBoxLayout(g_beban)
        self.l_beban = QLabel("Susun jaringan untuk melihat perkiraan beban perhitungan.")
        self.l_beban.setWordWrap(True)
        v_beban.addWidget(self.l_beban)
        self.l_siklus = QLabel("")
        self.l_siklus.setWordWrap(True)
        self.l_siklus.setObjectName("muted")
        v_beban.addWidget(self.l_siklus)
        vn.addWidget(g_beban)
        split.addWidget(kanan)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, 1)

        lay.addWidget(kit.catatan(rbfe.LABEL_EKSPERIMENTAL, "peringatan"))
        self.b_csv = kit.tombol("Ekspor jaringan CSV…", self._ekspor)
        self.b_metode = kit.tombol("Salin paragraf metode", self._salin_metode)
        lay.addLayout(kit.bar_bawah(self, kiri=[self.b_csv, self.b_metode], tutup=True))

    def _muat_ligan(self):
        self.daftar.clear()
        self._seri = []
        for item in (kit.ligan_proyek(self.jw, dengan_mol=False) if self.jw else []):
            smi = item.get("smiles") if isinstance(item, dict) else ""
            nama = item.get("nama") if isinstance(item, dict) else str(item)
            if not smi:
                continue
            self._seri.append((nama, smi))
            li = QListWidgetItem(nama)
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Checked)
            self.daftar.addItem(li)
        if len(self._seri) < 2:
            self.l_status.setText("Butuh sedikitnya dua ligan proyek ber-SMILES untuk menyusun jaringan.")
            self.b_susun.setEnabled(False)

    def _centang(self, nyala):
        for i in range(self.daftar.count()):
            self.daftar.item(i).setCheckState(Qt.Checked if nyala else Qt.Unchecked)

    def _terpilih(self):
        nama = {self.daftar.item(i).text() for i in range(self.daftar.count())
                if self.daftar.item(i).checkState() == Qt.Checked}
        return [(n, s) for n, s in self._seri if n in nama]

    # ------------------------------------------------------------------ susun
    def _susun(self):
        seri = self._terpilih()
        if len(seri) < 2:
            self.l_status.setText("Centang sedikitnya dua senyawa.")
            return
        mode = self.cb_mode.currentData()
        self.b_susun.setEnabled(False)
        self.l_status.setText(f"Memetakan atom {len(seri)} senyawa…")

        def kerjakan(lapor=None):
            pasangan = rbfe.pasangan_dari_mmp(seri)
            return rbfe.jaringan(pasangan, mode), pasangan

        self._kerja = kerja.jalankan(kerjakan, selesai=self._selesai, galat=self._galat)

    def _galat(self, teks):
        self.b_susun.setEnabled(True)
        self.l_status.setText(f"Gagal: {teks.splitlines()[0]}")

    def _selesai(self, hasil):
        self.b_susun.setEnabled(True)
        j, semua_pasangan = hasil
        self._jaringan = j
        tepi = j.get("tepi") or []
        ditolak = [p for p in semua_pasangan if p.pesan]
        self._isi_tabel(tepi + ditolak)

        if not tepi:
            self.l_status.setText(
                f"Tidak ada pasangan yang layak diperturbasi dari {len(semua_pasangan)} pasangan MMP. "
                "RBFE hanya cocok untuk seri kongenerik dengan perubahan kecil.")
            self.l_beban.setText("")
            return

        self.l_status.setText(f"{len(tepi)} tepi tersusun atas {len(j['simpul'])} senyawa."
                              + (f" {j['pesan']}" if j.get("pesan") else ""))
        e = rbfe.estimasi_waktu(len(tepi), n_lambda=self.s_lambda.value(),
                                n_replika=self.s_replika.value(), ns_per_lambda=self.s_ns.value())
        beban = (f"{len(tepi)} tepi × {self.s_lambda.value()} jendela λ × {self.s_replika.value()} replika "
                 f"× {kit.f(self.s_ns.value(), 1)} ns = {kit.f(e['total_ns'], 0)} ns simulasi.")
        if e["hari"] is None:
            beban += (" Lama perhitungan belum dapat diperkirakan karena kecepatan mesin ini belum diukur; "
                      "jalankan tolok ukur di dialog MD terlebih dahulu.")
        else:
            beban += f" Sekitar {kit.f(e['hari'], 1)} hari pada kecepatan terukur."
        self.l_beban.setText(beban)

        siklus = rbfe.tutup_siklus(tepi)
        if siklus:
            n_ok = sum(1 for s in siklus if s["konsisten"])
            self.l_siklus.setText(f"{n_ok} dari {len(siklus)} siklus konsisten.")
        else:
            self.l_siklus.setText("Penutupan siklus baru dapat diperiksa setelah ΔΔG tiap tepi terisi.")

    def _isi_tabel(self, tepi):
        self.tabel.setSortingEnabled(False)
        self.tabel.setRowCount(len(tepi))
        for r, t in enumerate(tepi):
            self.tabel.setItem(r, 0, QTableWidgetItem(str(t.a)))
            self.tabel.setItem(r, 1, QTableWidgetItem(str(t.b)))
            self.tabel.setItem(r, 2, kit.sel_angka(t.n_berubah, d=0))
            self.tabel.setItem(r, 3, kit.sel_angka(t.ddg, d=2))
            self.tabel.setItem(r, 4, kit.sel_angka(t.galat, d=2))
            self.tabel.setItem(r, 5, QTableWidgetItem(t.pesan))
        self.tabel.setSortingEnabled(True)

    # ------------------------------------------------------------------ keluaran
    def _ekspor(self):
        if not self._jaringan or not self._jaringan.get("tepi"):
            self.l_status.setText("Susun jaringan terlebih dahulu.")
            return
        p, _ = QFileDialog.getSaveFileName(self, "Simpan jaringan perturbasi", "jaringan_rbfe.csv",
                                           "CSV (*.csv)")
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["# catatan", rbfe.LABEL_EKSPERIMENTAL])
            w.writerow(["dari", "ke", "atom_berubah", "ddg_kkal_mol", "galat", "catatan"])
            for t in self._jaringan["tepi"]:
                w.writerow([t.a, t.b, t.n_berubah, t.ddg, t.galat, t.pesan])
        self.l_status.setText(f"Jaringan disimpan ke {p}")

    def _salin_metode(self):
        if not self._jaringan:
            self.l_status.setText("Susun jaringan terlebih dahulu.")
            return
        teks = rbfe.paragraf_metode(self._jaringan, n_lambda=self.s_lambda.value(),
                                    n_replika=self.s_replika.value(), ns_per_lambda=self.s_ns.value())
        if not teks:
            self.l_status.setText("Belum ada tepi jaringan untuk ditulis di paragraf metode.")
            return
        kit.salin(teks)
        self.l_status.setText("Paragraf metode disalin ke papan klip.")
