"""Dialog Saluran akses ligan (Analisis › Saluran akses ligan…).

Memindai jalur lurus dari pusat grid box (atau pusat pose aktif) ke pelarut, melaporkan jari-jari leher,
residu penjaga, dan bisa menggambar garis tengah saluran di viewport 3D.
"""
import csv

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDoubleSpinBox, QGroupBox, QHBoxLayout, QLabel, QSplitter, QTextBrowser,
                               QFileDialog, QVBoxLayout, QWidget)

from ..core import terowongan
from . import kerja, kit

KOLOM = ["Saluran", "Leher (Å)", "Rerata (Å)", "Panjang (Å)", "Residu penjaga"]
WARNA_JALUR = ["#2f8fd6", "#c98a12", "#7b5cd6", "#1aa3a3", "#cf3f3f", "#2e9e5b"]


class DialogTerowongan(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.daftar = []
        self.setWindowTitle("Saluran akses ligan")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1100, 700)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul(
            "Saluran akses ligan dari sisi aktif ke pelarut",
            "Dari titik awal dipancarkan 64 sinar; sepanjang tiap sinar dihitung celah bebas ke permukaan van der "
            "Waals. Sinar yang menembus ke pelarut dilaporkan sebagai saluran, beserta titik tersempitnya."))

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Jari-jari pemeriksa minimum"))
        self.s_probe = QDoubleSpinBox()
        self.s_probe.setRange(0.5, 3.0)
        self.s_probe.setSingleStep(0.1)
        self.s_probe.setValue(1.2)
        self.s_probe.setSuffix(" Å")
        self.s_probe.setToolTip("Saluran dengan leher lebih sempit dari 0,7 × nilai ini tidak ditampilkan. "
                                "1,2 Å ≈ ukuran molekul air; 1,4–1,8 Å untuk molekul obat kecil.")
        bar.addWidget(self.s_probe)
        bar.addSpacing(16)
        self.l_awal = QLabel()
        self.l_awal.setObjectName("muted")
        bar.addWidget(self.l_awal, 1)
        self.b_pindai = kit.tombol("Pindai ulang", self.pindai)
        bar.addWidget(self.b_pindai)
        lay.addLayout(bar)

        sp = QSplitter(Qt.Horizontal)
        self.tabel = kit.tabel(KOLOM, regang=4, urut=True)
        self.tabel.itemSelectionChanged.connect(self.pilih)
        sp.addWidget(self.tabel)
        kanan = QWidget()
        v = QVBoxLayout(kanan)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        g = QGroupBox("Rincian saluran terpilih")
        gv = QVBoxLayout(g)
        self.rincian = QTextBrowser()
        gv.addWidget(self.rincian)
        v.addWidget(g, 1)
        v.addWidget(kit.tombol("Gambar garis tengah di viewport", self.tampil_viewer, utama=True))
        v.addWidget(kit.tombol("Hapus gambar saluran", self.hapus_viewer))
        kanan.setMaximumWidth(400)
        sp.addWidget(kanan)
        sp.setStretchFactor(0, 3)
        sp.setStretchFactor(1, 2)
        lay.addWidget(sp, 1)

        self.l_info = kit.catatan("")
        lay.addWidget(self.l_info)
        lay.addWidget(kit.catatan(
            "Hanya jalur lurus yang diperiksa, jadi lorong berkelok tidak akan muncul dan panjangnya adalah jarak "
            "lurus. Untuk analisis saluran definitif (jalur melengkung, dinamika pintu gerbang) gunakan CAVER atau "
            "MOLE pada trajektori MD."))
        self.l_status = kit.catatan("")
        lay.addLayout(kit.bar_bawah(self, kiri=[kit.tombol("Salin ringkasan", self.salin),
                                                kit.tombol("Simpan CSV…", self.simpan_csv), self.l_status]))
        self.pindai()

    # ------------------------------------------------------------------ data
    def _titik_awal(self):
        """Pusat grid box; bila belum ada, pusat pose/ligan aktif; bila tidak ada juga, None (pusat protein)."""
        p = kit.pusat_kotak(self.jw)
        if p:
            return p, "pusat grid box"
        o = kit.pose_aktif(self.jw)
        if o is not None:
            xyz, n = [0.0, 0.0, 0.0], 0
            for b in o.teks.splitlines():
                if b.startswith(("ATOM  ", "HETATM")):
                    try:
                        xyz = [xyz[0] + float(b[30:38]), xyz[1] + float(b[38:46]), xyz[2] + float(b[46:54])]
                        n += 1
                    except ValueError:
                        pass
            if n:
                return [v / n for v in xyz], f"pusat {o.info.get('ligan', o.nama)}"
        return None, "pusat massa protein (grid box belum diatur)"

    def pindai(self):
        teks, nama, _ = kit.reseptor_proyek(self.jw)
        if not teks:
            self.l_info.setText("Belum ada reseptor yang bisa dipindai.")
            return
        awal, asal = self._titik_awal()
        self.l_awal.setText(f"Titik awal: {asal}")
        self.b_pindai.setEnabled(False)
        self.l_info.setText(f"Memindai saluran pada {nama}…")
        probe = self.s_probe.value()
        kerja.jalankan(lambda lapor: terowongan.cari_terowongan(teks, titik_awal=awal, radius_probe=probe),
                       selesai=self._isi,
                       galat=lambda g: (self.l_info.setText("Pemindaian gagal."), self.jw._galat(g),
                                        self.b_pindai.setEnabled(True)))

    def _isi(self, daftar):
        self.b_pindai.setEnabled(True)
        self.daftar = daftar
        t = self.tabel
        t.setSortingEnabled(False)
        t.setRowCount(len(daftar))
        for r, s in enumerate(daftar):
            t.setItem(r, 0, kit.sel(f"Saluran {s['id']}", s["id"]))
            it = kit.sel_angka(s["bottleneck_radius"], 2)
            it.setForeground(kit.warna("ok" if s["bottleneck_radius"] >= 1.4 else
                                       "warn" if s["bottleneck_radius"] >= 1.0 else "bad"))
            t.setItem(r, 1, it)
            t.setItem(r, 2, kit.sel_angka(s["avg_radius"], 2))
            t.setItem(r, 3, kit.sel_angka(s["panjang"], 1))
            t.setItem(r, 4, kit.sel(", ".join(s["gatekeeper"]) or "–", rata_kanan=False))
        t.setSortingEnabled(True)
        t.sortItems(1, Qt.DescendingOrder)      # saluran terlebar di atas
        if daftar:
            lebar = daftar[0]["bottleneck_radius"]
            self.l_info.setText(
                f"{len(daftar)} saluran terdeteksi. Leher terlebar {kit.f(lebar)} Å — "
                + ("cukup untuk molekul obat kecil lewat tanpa pembukaan sisi rantai."
                   if lebar >= 1.4 else "sempit; ligan kemungkinan butuh gerak rantai samping untuk masuk."))
            t.selectRow(0)
        else:
            self.l_info.setText("Tidak ada saluran lurus yang menembus ke pelarut pada ambang ini. "
                                "Coba turunkan jari-jari pemeriksa, atau pastikan grid box ada di kantong.")
            self.rincian.clear()

    def terpilih(self):
        r = self.tabel.currentRow()
        if r < 0:
            return None
        n = self.tabel.item(r, 0).data(Qt.UserRole)
        return next((s for s in self.daftar if s["id"] == n), None)

    def pilih(self):
        s = self.terpilih()
        if not s:
            return
        self.rincian.setHtml(
            f"<h3 style='margin:0'>Saluran {s['id']}</h3>"
            f"<p><b>Leher tersempit</b> {kit.f(s['bottleneck_radius'])} Å · "
            f"<b>rerata</b> {kit.f(s['avg_radius'])} Å<br>"
            f"<b>Panjang</b> {kit.f(s['panjang'], 1)} Å ({len(s['jalur_titik'])} titik garis tengah)</p>"
            f"<p><b>Residu penjaga (di leher)</b><br>{', '.join(s['gatekeeper']) or '–'}</p>"
            f"<p><b>Residu dinding ({len(s['residu_dinding'])})</b><br>{', '.join(s['residu_dinding'])}</p>")

    # ------------------------------------------------------------------ aksi
    def tampil_viewer(self):
        s = self.terpilih()
        if not s:
            return
        warna = WARNA_JALUR[(s["id"] - 1) % len(WARNA_JALUR)]
        self.jw.viewer.js("terowongan", [{"titik": s["jalur_titik"], "radius": s["jalur_radius"],
                                          "warna": warna, "leher": "#cf3f3f"}])
        self.l_status.setText(f"Garis tengah saluran {s['id']} digambar; bola merah = titik tersempit.")

    def hapus_viewer(self):
        self.jw.viewer.js("terowongan", [])
        self.l_status.setText("Gambar saluran dihapus dari viewport.")

    def salin(self):
        if not self.daftar:
            return
        baris = ["Saluran\tLeher (A)\tRerata (A)\tPanjang (A)\tResidu penjaga"]
        for s in self.daftar:
            baris.append(f"{s['id']}\t{s['bottleneck_radius']}\t{s['avg_radius']}\t{s['panjang']}\t"
                         + ", ".join(s["gatekeeper"]))
        kit.salin("\n".join(baris), self.l_status, f"{len(self.daftar)} saluran disalin sebagai tabel.")

    def simpan_csv(self):
        if not self.daftar:
            return
        f, _ = QFileDialog.getSaveFileName(self, "Simpan daftar saluran", "saluran_akses.csv", "CSV (*.csv)")
        if not f:
            return
        with open(f, "w", newline="", encoding="utf-8-sig") as h:
            w = csv.writer(h)
            w.writerow(["saluran", "leher_A", "rerata_A", "panjang_A", "residu_penjaga", "residu_dinding"])
            for s in self.daftar:
                w.writerow([s["id"], s["bottleneck_radius"], s["avg_radius"], s["panjang"],
                            "; ".join(s["gatekeeper"]), "; ".join(s["residu_dinding"])])
        self.l_status.setText(f"Tersimpan: {f}")
