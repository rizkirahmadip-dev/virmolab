"""Dialog Deteksi kantong pengikatan (Analisis › Deteksi kantong pengikatan…).

Memindai rongga pada reseptor proyek (atau protein di viewer), memeringkat menurut volume dan kelayakan,
menampilkan residu dinding, dan bisa langsung dijadikan grid box docking.
"""
import csv

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QSplitter, QTextBrowser,
                               QVBoxLayout, QWidget)

from ..core import kantong
from . import kerja, kit

KOLOM = ["Kantong", "Volume (Å³)", "Kelayakan", "Pusat X, Y, Z", "Kotak (Å)", "Residu"]


class DialogKantong(QDialog):
    kotakDipilih = Signal(dict)

    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.daftar = []
        self.setWindowTitle("Deteksi kantong pengikatan")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1120, 700)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul(
            "Deteksi kantong pengikatan otomatis",
            "Rongga dicari dengan kisi geometri dan uji keterkepungan pelarut, lalu diperingkat. Berguna untuk "
            "struktur apo atau model AlphaFold yang belum punya ligan ko-kristal."))

        bar = QHBoxLayout()
        self.l_info = QLabel("Memindai…")
        self.l_info.setObjectName("subjudul")
        bar.addWidget(self.l_info, 1)
        self.b_pindai = kit.tombol("Pindai ulang", self.pindai)
        bar.addWidget(self.b_pindai)
        lay.addLayout(bar)

        sp = QSplitter(Qt.Horizontal)
        self.tabel = kit.tabel(KOLOM, regang=3, urut=True)
        self.tabel.itemSelectionChanged.connect(self.pilih)
        sp.addWidget(self.tabel)

        kanan = QWidget()
        v = QVBoxLayout(kanan)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        g = QGroupBox("Rincian kantong terpilih")
        gv = QVBoxLayout(g)
        self.rincian = QTextBrowser()
        gv.addWidget(self.rincian)
        v.addWidget(g, 1)
        self.b_kotak = kit.tombol("Jadikan grid box docking", self.jadikan_kotak, utama=True,
                                  tip="Pusat dan ukuran kantong ini dipakai sebagai kotak pencarian docking proyek")
        v.addWidget(self.b_kotak)
        v.addWidget(kit.tombol("Tampilkan pusat kantong di viewport", self.tampil_viewer))
        kanan.setMaximumWidth(400)
        sp.addWidget(kanan)
        sp.setStretchFactor(0, 3)
        sp.setStretchFactor(1, 2)
        lay.addWidget(sp, 1)

        lay.addWidget(kit.catatan(
            "Pencari rongga bawaan (kisi geometri gaya LIGSITE), berjalan tanpa Java. Kelayakan (0–1) hanya "
            "memadukan volume, kedalaman, dan jumlah residu dinding — bukan skor druggability terlatih. Untuk "
            "peringkat berbasis pembelajaran mesin, pakai Siapkan › Deteksi kantong (P2Rank). Pastikan kantong "
            "teratas memang sisi aktif yang Anda maksud sebelum dipakai sebagai grid box."))
        self.l_status = kit.catatan("")
        lay.addLayout(kit.bar_bawah(self, kiri=[kit.tombol("Salin koordinat", self.salin),
                                                kit.tombol("Simpan CSV…", self.simpan_csv), self.l_status]))
        self.pindai()

    # ------------------------------------------------------------------ data
    def pindai(self):
        teks, nama, _ = kit.reseptor_proyek(self.jw)
        if not teks:
            self.l_info.setText("Belum ada reseptor yang bisa dipindai.")
            return
        self.b_pindai.setEnabled(False)
        self.l_info.setText(f"Memindai rongga pada {nama}…")
        kerja.jalankan(lambda lapor: kantong.deteksi_kantong(teks), selesai=self._isi,
                       galat=lambda g: (self.l_info.setText("Pemindaian gagal."), self.jw._galat(g),
                                        self.b_pindai.setEnabled(True)))

    def _isi(self, daftar):
        self.b_pindai.setEnabled(True)
        self.daftar = daftar
        t = self.tabel
        t.setSortingEnabled(False)
        t.setRowCount(len(daftar))
        for r, k in enumerate(daftar):
            p, u = k["pusat"], k["ukuran"]
            t.setItem(r, 0, kit.sel(f"Kantong {k['peringkat']}", k["peringkat"]))
            t.setItem(r, 1, kit.sel_angka(k["volume"], 0))
            it = kit.sel_angka(k["skor_druggability"], 2)
            it.setForeground(kit.warna("ok" if k["skor_druggability"] >= 0.7 else
                                       "warn" if k["skor_druggability"] >= 0.5 else "mut"))
            t.setItem(r, 2, it)
            t.setItem(r, 3, kit.sel(f"{kit.f(p['x'], 1)}  {kit.f(p['y'], 1)}  {kit.f(p['z'], 1)}", rata_kanan=True))
            t.setItem(r, 4, kit.sel(f"{kit.f(u['x'], 0)} × {kit.f(u['y'], 0)} × {kit.f(u['z'], 0)}", rata_kanan=True))
            t.setItem(r, 5, kit.sel_angka(k["jumlah_residu"], 0))
        t.setSortingEnabled(True)
        if daftar:
            self.l_info.setText(f"{len(daftar)} kandidat kantong, diurutkan menurut kelayakan.")
            t.selectRow(0)
        else:
            self.l_info.setText("Tidak ada rongga tertutup yang memenuhi syarat volume minimum (80 Å³).")
            self.rincian.clear()

    def terpilih(self):
        r = self.tabel.currentRow()
        if r < 0:
            return None
        n = self.tabel.item(r, 0).data(Qt.UserRole)
        return next((k for k in self.daftar if k["peringkat"] == n), None)

    def pilih(self):
        k = self.terpilih()
        if not k:
            return
        p, u = k["pusat"], k["ukuran"]
        res = ", ".join(k["residu_pelapis"]) or "–"
        self.rincian.setHtml(
            f"<h3 style='margin:0'>Kantong {k['peringkat']}</h3>"
            f"<p><b>Volume</b> {kit.f(k['volume'], 0)} Å³ · <b>kelayakan</b> {kit.f(k['skor_druggability'])}<br>"
            f"<b>Pusat</b> {kit.f(p['x'])}, {kit.f(p['y'])}, {kit.f(p['z'])}<br>"
            f"<b>Ukuran kotak usulan</b> {kit.f(u['x'], 1)} × {kit.f(u['y'], 1)} × {kit.f(u['z'], 1)} Å</p>"
            f"<p><b>Residu dinding ({k['jumlah_residu']})</b><br>{res}</p>")

    # ------------------------------------------------------------------ aksi
    def jadikan_kotak(self):
        k = self.terpilih()
        if not k:
            self.l_status.setText("Pilih salah satu kantong dulu.")
            return
        p, u = k["pusat"], k["ukuran"]
        self.kotakDipilih.emit({"pusat": [p["x"], p["y"], p["z"]], "ukuran": [u["x"], u["y"], u["z"]], "spasi": 0.375})
        self.l_status.setText(f"Grid box proyek diarahkan ke kantong {k['peringkat']}.")

    def tampil_viewer(self):
        if not self.daftar:
            return
        self.jw.viewer.js("kantong", [{"pusat": [k["pusat"]["x"], k["pusat"]["y"], k["pusat"]["z"]],
                                       "nomor": k["peringkat"]} for k in self.daftar])
        self.l_status.setText(f"{len(self.daftar)} pusat kantong digambar di viewport.")

    def salin(self):
        k = self.terpilih()
        if not k:
            return
        p, u = k["pusat"], k["ukuran"]
        kit.salin(f"center_x = {p['x']:.2f}\ncenter_y = {p['y']:.2f}\ncenter_z = {p['z']:.2f}\n"
                  f"size_x = {u['x']:.1f}\nsize_y = {u['y']:.1f}\nsize_z = {u['z']:.1f}", self.l_status,
                  f"Koordinat kantong {k['peringkat']} disalin (format konfigurasi Vina).")

    def simpan_csv(self):
        if not self.daftar:
            return
        f, _ = QFileDialog.getSaveFileName(self, "Simpan daftar kantong", "kantong.csv", "CSV (*.csv)")
        if not f:
            return
        with open(f, "w", newline="", encoding="utf-8-sig") as h:
            w = csv.writer(h)
            w.writerow(["peringkat", "volume_A3", "kelayakan", "pusat_x", "pusat_y", "pusat_z",
                        "ukuran_x", "ukuran_y", "ukuran_z", "jumlah_residu", "residu_dinding"])
            for k in self.daftar:
                p, u = k["pusat"], k["ukuran"]
                w.writerow([k["peringkat"], k["volume"], k["skor_druggability"], p["x"], p["y"], p["z"],
                            u["x"], u["y"], u["z"], k["jumlah_residu"], "; ".join(k["residu_pelapis"])])
        self.l_status.setText(f"Tersimpan: {f}")
