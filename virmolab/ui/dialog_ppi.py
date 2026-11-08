"""Dialog Docking Protein-Protein (PPI) & Analisis Antarmuka.

Memprediksi residu antarmuka pengikatan protein (SASA),
menilai kontak non-kovalen antar-rantai kompleks (H-Bond, Salt Bridge, ΔSASA),
dan visualisasi model kompleks di viewer 3D.
"""
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
)

from ..core import ppi
from . import kit


def _sel(t, angka=None, align_right=False):
    it = QTableWidgetItem(str(t) if t is not None else "-")
    if angka is not None:
        it.setData(Qt.UserRole, angka)
    if align_right or angka is not None:
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return it


class DialogPPI(QDialog):
    muatKompleks = Signal(str)

    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.proyek = jw.proyek
        self.viewer = jw.viewer
        self.setWindowTitle("Antarmuka protein–protein (PPI)")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1200, 740)

        self.pdb_teks_p1 = ""
        self.pdb_teks_p2 = ""
        self.pdb_teks_kompleks = ""
        self.data_antarmuka = []
        self.skor_kompleks = {}

        lay_utama = QVBoxLayout(self)
        lay_utama.setContentsMargins(12, 12, 12, 12)
        lay_utama.setSpacing(8)
        lay_utama.addWidget(kit.judul(
            "Antarmuka protein–protein",
            "Residu kontak, ikatan hidrogen, jembatan garam, dan luas permukaan terkubur di antarmuka dua "
            "rantai protein."))

        # Bilah Masukan Berkas Protein
        gb_input = QGroupBox("Pemilihan Struktur Protein (PDB)")
        lay_in = QHBoxLayout(gb_input)

        # Protein 1
        lay_p1 = QVBoxLayout()
        lay_p1.addWidget(QLabel("Protein 1 (Reseptor / Rantai A):"))
        self.l_p1 = kit.lencana("Belum dipilih", "warn")
        self.l_p1.setObjectName("muted")
        lay_p1.addWidget(self.l_p1)
        bar_b1 = QHBoxLayout()
        b_p1_proyek = QPushButton("Ambil dari Proyek")
        # lambda: clicked mengirim bool yang akan mengisi parameter `diam`. Kebetulan nilainya
        # sama dengan bawaannya sekarang, tetapi mengubah bawaan itu akan membungkam dialognya.
        b_p1_proyek.clicked.connect(lambda: self._ambil_p1_proyek())
        bar_b1.addWidget(b_p1_proyek)
        b_p1_berkas = QPushButton("Pilih PDB…")
        b_p1_berkas.clicked.connect(self._pilih_p1_berkas)
        bar_b1.addWidget(b_p1_berkas)
        lay_p1.addLayout(bar_b1)
        lay_in.addLayout(lay_p1)

        lay_in.addSpacing(20)

        # Protein 2 / Kompleks
        lay_p2 = QVBoxLayout()
        lay_p2.addWidget(QLabel("Protein 2 (Mitra / Rantai B) atau Kompleks PDB:"))
        self.l_p2 = kit.lencana("Belum dipilih", "warn")
        self.l_p2.setObjectName("muted")
        lay_p2.addWidget(self.l_p2)
        bar_b2 = QHBoxLayout()
        b_p2_berkas = QPushButton("Pilih Berkas PDB…")
        b_p2_berkas.clicked.connect(self._pilih_p2_berkas)
        bar_b2.addWidget(b_p2_berkas)
        b_kompleks = QPushButton("Muat Kompleks PDB Utuh…")
        b_kompleks.setObjectName("subjudul")
        b_kompleks.clicked.connect(self._pilih_kompleks_berkas)
        bar_b2.addWidget(b_kompleks)
        lay_p2.addLayout(bar_b2)
        lay_in.addLayout(lay_p2)

        lay_utama.addWidget(gb_input)

        # Tabs: Tab 1 (Prediksi Residu Antarmuka) vs Tab 2 (Analisis Kompleks Antarmuka)
        self.tabs = QTabWidget()

        # =====================================================================
        # TAB 1: Prediksi Residu Antarmuka (SASA)
        # =====================================================================
        w_tab1 = QWidget()
        lay_t1 = QVBoxLayout(w_tab1)
        lay_t1.setContentsMargins(6, 6, 6, 6)

        bar_t1_atas = QHBoxLayout()
        self.l_info_sasa = QLabel("Prediksi residu permukaan yang terekspos pelarut (kandidat sisi aktif PPI)")
        bar_t1_atas.addWidget(self.l_info_sasa, 1)
        b_hitung_sasa = QPushButton("Hitung Prediksi SASA")
        b_hitung_sasa.clicked.connect(self._hitung_prediksi_sasa)
        bar_t1_atas.addWidget(b_hitung_sasa)
        lay_t1.addLayout(bar_t1_atas)

        self.tabel_sasa = QTableWidget()
        self.tabel_sasa.setColumnCount(6)
        self.tabel_sasa.setHorizontalHeaderLabels([
            "Residu", "Rantai", "No. Residu", "SASA (Å²)", "Relatif (%)", "Kandidat Antarmuka"
        ])
        self.tabel_sasa.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabel_sasa.setSortingEnabled(True)
        self.tabel_sasa.setAlternatingRowColors(True)
        h1 = self.tabel_sasa.horizontalHeader()
        h1.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 6):
            h1.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        lay_t1.addWidget(self.tabel_sasa)

        self.tabs.addTab(w_tab1, "1. Prediksi Residu Antarmuka (SASA)")

        # =====================================================================
        # TAB 2: Penilaian Kompleks Antarmuka
        # =====================================================================
        w_tab2 = QWidget()
        lay_t2 = QVBoxLayout(w_tab2)
        lay_t2.setContentsMargins(6, 6, 6, 6)

        sp_tab2 = QSplitter(Qt.Horizontal)

        # Kiri: Panel Metrik Antarmuka
        w_metrik = QWidget()
        lay_m = QVBoxLayout(w_metrik)
        lay_m.setContentsMargins(0, 0, 0, 0)
        lay_m.setSpacing(8)

        gb_skor = QGroupBox("Metrik Kualitas Kompleks PPI")
        lay_gs = QVBoxLayout(gb_skor)
        self.l_m_kontak = QLabel("Kontak Atom Berat: -")
        self.l_m_hbond = QLabel("Ikatan Hidrogen Antar-Rantai: -")
        self.l_m_garam = QLabel("Jembatan Garam: -")
        self.l_m_bsa = QLabel("Buried Surface Area (ΔSASA): -")
        self.l_m_sc = QLabel("Skor Komplementaritas: -")
        for lbl in (self.l_m_kontak, self.l_m_hbond, self.l_m_garam, self.l_m_bsa, self.l_m_sc):
            lbl.setObjectName("kartuNilai")
            lay_gs.addWidget(lbl)
        lay_m.addWidget(gb_skor)

        b_analisis_kompleks = QPushButton("Evaluasi Kompleks Antarmuka")
        b_analisis_kompleks.setObjectName("primary")
        b_analisis_kompleks.clicked.connect(self._evaluasi_kompleks)
        lay_m.addWidget(b_analisis_kompleks)

        lay_m.addStretch(1)
        w_metrik.setMaximumWidth(340)
        sp_tab2.addWidget(w_metrik)

        # Kanan: Daftar Residu Interaksi
        w_res = QWidget()
        lay_r = QVBoxLayout(w_res)
        lay_r.setContentsMargins(0, 0, 0, 0)
        lay_r.addWidget(QLabel("Rincian Residu Terlibat Antarmuka:"))
        self.txt_residu_antarmuka = QTextEdit()
        self.txt_residu_antarmuka.setReadOnly(True)
        lay_r.addWidget(self.txt_residu_antarmuka)

        bar_aksi_t2 = QHBoxLayout()
        b_salin_lap = QPushButton("Salin Laporan Skor")
        b_salin_lap.clicked.connect(self._salin_laporan)
        bar_aksi_t2.addWidget(b_salin_lap)

        b_tampil_viewer = QPushButton("Tampilkan Kompleks di Viewer 3D")
        b_tampil_viewer.clicked.connect(self._tampilkan_di_viewer)
        bar_aksi_t2.addWidget(b_tampil_viewer)

        b_tutup = QPushButton("✕ Tutup")
        b_tutup.clicked.connect(self.close)
        bar_aksi_t2.addWidget(b_tutup)
        lay_r.addLayout(bar_aksi_t2)

        sp_tab2.addWidget(w_res)
        sp_tab2.setStretchFactor(1, 2)
        lay_t2.addWidget(sp_tab2)

        self.tabs.addTab(w_tab2, "2. Evaluasi Kompleks Antarmuka (ΔSASA && Kontak)")

        lay_utama.addWidget(self.tabs)

        # Coba muat dari proyek saat ini bila ada reseptor
        self._ambil_p1_proyek(diam=True)

    def _ambil_p1_proyek(self, diam=False):
        if not self.proyek:
            if not diam:
                QMessageBox.information(self, "Proyek Kosong", "Belum ada proyek yang terbuka.")
            return

        teks_p, nm, _ = kit.reseptor_proyek(self.jw)

        if teks_p:
            self.pdb_teks_p1 = teks_p
            self.l_p1.setText(f"Dari proyek: {nm} ({len(teks_p.splitlines())} baris)")
            kit.atur_nada(self.l_p1, "ok")
        elif not diam:
            QMessageBox.warning(self, "PDB Belum Ada", "Berkas PDB reseptor belum ditemukan di dalam proyek.")

    def _pilih_p1_berkas(self):
        jalur, _ = QFileDialog.getOpenFileName(self, "Pilih PDB Protein 1", "", "PDB (*.pdb *.ent)")
        if not jalur:
            return
        p = Path(jalur)
        teks = p.read_text(encoding="utf-8", errors="replace")
        self.pdb_teks_p1 = teks
        self.l_p1.setText(f"{p.name} ({len(teks.splitlines())} baris)")
        kit.atur_nada(self.l_p1, "ok")

    def _pilih_p2_berkas(self):
        jalur, _ = QFileDialog.getOpenFileName(self, "Pilih PDB Protein 2", "", "PDB (*.pdb *.ent)")
        if not jalur:
            return
        p = Path(jalur)
        teks = p.read_text(encoding="utf-8", errors="replace")
        self.pdb_teks_p2 = teks
        self.l_p2.setText(f"{p.name} ({len(teks.splitlines())} baris)")
        kit.atur_nada(self.l_p2, "ok")

    def _pilih_kompleks_berkas(self):
        jalur, _ = QFileDialog.getOpenFileName(self, "Pilih PDB Kompleks PPI (Multi-Rantai)", "", "PDB (*.pdb *.ent)")
        if not jalur:
            return
        p = Path(jalur)
        teks = p.read_text(encoding="utf-8", errors="replace")
        self.pdb_teks_kompleks = teks
        self.l_p2.setText(f"Kompleks: {p.name} ({len(teks.splitlines())} baris)")
        kit.atur_nada(self.l_p2, "info")
        # Auto-evaluasi tab 2
        self.tabs.setCurrentIndex(1)
        self._evaluasi_kompleks()

    def _hitung_prediksi_sasa(self):
        with kit.sibuk(self.l_info_sasa, "Menghitung SASA permukaan…"):
            teks = self.pdb_teks_p1 or self.pdb_teks_kompleks
            if not teks:
                QMessageBox.warning(self, "Pilih PDB", "Silakan pilih struktur PDB Protein 1 terlebih dahulu.")
                return

            self.data_antarmuka = ppi.prediksi_antarmuka(teks)
            self.tabel_sasa.setSortingEnabled(False)
            self.tabel_sasa.setRowCount(len(self.data_antarmuka))

            n_kandidat = 0
            for r, item in enumerate(self.data_antarmuka):
                is_k = item.get("kandidat", False)
                if is_k:
                    n_kandidat += 1

                self.tabel_sasa.setItem(r, 0, _sel(item["label"]))
                self.tabel_sasa.setItem(r, 1, _sel(item["rantai"]))
                self.tabel_sasa.setItem(r, 2, _sel(str(item["resi"]), item["resi"], True))
                self.tabel_sasa.setItem(r, 3, kit.sel_angka(item["sasa"], 1))

                pct_rel = item["rel_sasa"] * 100.0
                it_rel = kit.sel_angka(pct_rel, 1, "%")
                if is_k:
                    it_rel.setForeground(QColor("#16a34a"))
                self.tabel_sasa.setItem(r, 4, it_rel)

                it_kan = _sel("Ya (Terekspos)" if is_k else "Terkubur")
                if is_k:
                    it_kan.setForeground(QColor("#16a34a"))
                self.tabel_sasa.setItem(r, 5, it_kan)

            self.tabel_sasa.setSortingEnabled(True)
            self.l_info_sasa.setText(f"Selesai: {n_kandidat} dari {len(self.data_antarmuka)} residu diprediksi sebagai kandidat antarmuka (SASA Relatif ≥ 25%).")

    def _evaluasi_kompleks(self):
        with kit.sibuk(self.l_info_sasa, "Mengevaluasi antarmuka kompleks…"):
            teks = self.pdb_teks_kompleks
            # Jika belum ada kompleks utuh, gabungkan P1 dan P2 dengan penyesuaian rantai
            if not teks:
                if self.pdb_teks_p1 and self.pdb_teks_p2:
                    baris_gabung = []
                    for b in self.pdb_teks_p1.splitlines():
                        if b.startswith("ATOM  ") or b.startswith("HETATM"):
                            baris_gabung.append(b[:21] + "A" + b[22:])
                    baris_gabung.append("TER")
                    for b in self.pdb_teks_p2.splitlines():
                        if b.startswith("ATOM  ") or b.startswith("HETATM"):
                            baris_gabung.append(b[:21] + "B" + b[22:])
                    baris_gabung.append("END")
                    teks = "\n".join(baris_gabung)
                    self.pdb_teks_kompleks = teks

            if not teks:
                QMessageBox.warning(self, "PDB Belum Lengkap", "Silakan muat Berkas Kompleks PDB atau pilih kedua Protein 1 dan 2.")
                return

            res = ppi.skor_antarmuka(teks)
            if "error" in res:
                QMessageBox.critical(self, "Galat Evaluasi", res["error"])
                return

            self.skor_kompleks = res
            self.l_m_kontak.setText(f"Kontak atom berat: {res['kontak_total']}")
            self.l_m_hbond.setText(f"Ikatan hidrogen antar-rantai: {res['ikatan_h']}")
            self.l_m_garam.setText(f"Jembatan garam: {res['jembatan_garam']}")
            self.l_m_bsa.setText(f"Luas permukaan terkubur (ΔSASA): {kit.f(res['bsa_luas'], 1, 'Å²')}")
            self.l_m_sc.setText(f"Skor komplementaritas: {kit.f(res['skor_komplementaritas'])}")

            # Tampilkan residu
            teks_r = f"""### Residu Antarmuka Rantai {res['rantai_a']} ({res['jumlah_residu_a']} residu):
    {', '.join(res['residu_a']) if res['residu_a'] else 'Tidak ada kontak langsung'}

    ### Residu Antarmuka Rantai {res['rantai_b']} ({res['jumlah_residu_b']} residu):
    {', '.join(res['residu_b']) if res['residu_b'] else 'Tidak ada kontak langsung'}

    ---
    *Kontak dihitung untuk atom berat dalam batas jarak ≤ 4.5 Å.
    Ikatan hidrogen diperkirakan untuk pasangan donor/akseptor N, O ≤ 3.5 Å.*
    """
            self.txt_residu_antarmuka.setMarkdown(teks_r)

    def _salin_laporan(self):
        if not self.skor_kompleks:
            return
        res = self.skor_kompleks
        t = f"""HASIL EVALUASI ANTARMUKA PPI (VIRMOLAB):
- Rantai Interaksi: {res.get('rantai_a')} ↔ {res.get('rantai_b')}
- Kontak Atom Berat: {res.get('kontak_total')}
- Ikatan Hidrogen: {res.get('ikatan_h')}
- Jembatan Garam: {res.get('jembatan_garam')}
- Buried Surface Area (ΔSASA): {res.get('bsa_luas')} Å²
- Skor Komplementaritas: {res.get('skor_komplementaritas')}
- Residu Rantai {res.get('rantai_a')}: {', '.join(res.get('residu_a', []))}
- Residu Rantai {res.get('rantai_b')}: {', '.join(res.get('residu_b', []))}
"""
        QGuiApplication.clipboard().setText(t)
        QMessageBox.information(self, "Disalin", "Ringkasan skor antarmuka PPI berhasil disalin ke clipboard.")

    def _tampilkan_di_viewer(self):
        teks = self.pdb_teks_kompleks or self.pdb_teks_p1
        if not teks:
            QMessageBox.warning(self, "Kosong", "Belum ada struktur PDB yang dimuat.")
            return

        if self.viewer:
            try:
                self.viewer.muat_pdb(teks, nama="Kompleks_PPI")
                QMessageBox.information(self, "Viewer 3D", "Kompleks PPI berhasil dikirim ke jendela 3D Viewer.")
            except Exception as e:
                QMessageBox.critical(self, "Galat Viewer", f"Gagal memuat di viewer: {e}")
        else:
            self.muatKompleks.emit(teks)
