"""Paket validasi protokol docking untuk naskah (F11): wizard 4 langkah.

1. Redocking ligan ko-kristal: hasil validasi proyek yang sudah ada, atau dari berkas PDB kompleks.
2. Cross-docking antar-struktur PDB dari target yang sama (disuperposisikan lewat Cα).
3. Pengayaan: aktif ChEMBL + decoy bergaya DUD-E, docking nyata ke reseptor dan kotak proyek, lalu ROC/BEDROC/EF.
4. Ringkasan: kartu, paragraf metode, laporan HTML, figur ke komposer.

Aturan dialog ini: tidak ada angka bawaan. Langkah yang belum dijalankan tampil "–" dan tidak masuk paragraf
metode maupun laporan; semua pekerjaan berat berjalan di utas latar dan dapat dibatalkan.
"""
import csv
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QDialog, QDoubleSpinBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QProgressBar, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from ..core import catat, decoy, grafik_uji, mesin, validasi_protokol
from ..core.laporan import id_angka
from . import kerja, kit
from .. import i18n
from .panel_interaksi import KanvasSvg

LANGKAH = ("Redocking", "Cross-docking", "Pengayaan", "Ringkasan")
_AMBANG_RMSD = 2.0


class DialogValidasiProtokol(QDialog):
    """Wizard validasi protokol docking."""

    def __init__(self, parent=None, proyek=None):
        super().__init__(parent)
        self.jw = parent
        self.proyek = proyek if proyek is not None else getattr(parent, "proyek", None)
        self.setWindowTitle("Paket validasi protokol docking")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1100, 720)

        self.langkah = 0
        self.hasil_redocking: Optional[Dict[str, Any]] = None
        self.hasil_cross: Optional[validasi_protokol.HasilCrossDocking] = None
        self.senyawa_aktif: List[Dict[str, Any]] = []
        self.hasil_decoy: Optional[Dict[str, Any]] = None
        self.hasil_enrich: Optional[validasi_protokol.HasilEnrichment] = None
        self.hasil_pb: Optional[Dict[str, Any]] = None
        self.berkas_cross: List[Path] = []
        self._batal = threading.Event()
        self._sibuk = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul(
            "Paket validasi protokol docking",
            "Bukti bahwa protokol Anda layak dipercaya: redocking kristal, cross-docking, kemampuan memisahkan aktif dari "
            "decoy, dan validitas fisik pose. Hanya uji yang benar-benar dijalankan yang masuk ke laporan."))

        self.l_langkah = QLabel()
        self.l_langkah.setObjectName("subjudul")
        lay.addWidget(self.l_langkah)

        self.tumpuk = QStackedWidget()
        for halaman in (self._halaman_redocking(), self._halaman_cross(), self._halaman_pengayaan(),
                        self._halaman_ringkasan()):
            self.tumpuk.addWidget(halaman)
        lay.addWidget(self.tumpuk, 1)

        # Bilah status & progres
        h = QHBoxLayout()
        self.l_status = QLabel("")
        self.l_status.setObjectName("subjudul")
        self.l_status.setWordWrap(True)
        self.prog = QProgressBar()
        self.prog.setFixedWidth(220)
        self.prog.setVisible(False)
        self.b_batal = kit.tombol("Batal", self._minta_batal)
        self.b_batal.setVisible(False)
        h.addWidget(self.l_status, 1)
        h.addWidget(self.prog)
        h.addWidget(self.b_batal)
        lay.addLayout(h)

        self.b_mundur = kit.tombol("‹ Kembali", lambda: self._ke(self.langkah - 1))
        self.b_maju = kit.tombol("Lanjut ›", lambda: self._ke(self.langkah + 1), utama=True)
        lay.addLayout(kit.bar_bawah(self, kiri=[self.b_mundur], kanan=[self.b_maju]))

        self._muat_validasi_proyek()
        self._muat_pb_proyek()
        self._ke(0)

    # ------------------------------------------------------------------ halaman 1: redocking
    def _halaman_redocking(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(kit.catatan(
            "Redocking menilai apakah protokol dapat mereproduksi pose kristal (RMSD simetri ≤ 2,0 Å). "
            "Pilihan A memakai pengaturan proyek Anda sendiri; pilihan B memakai berkas PDB kompleks lain.", "muted"))

        v.addWidget(QLabel("<b>A. Validasi redocking proyek</b>"))
        self.l_redock_proyek = kit.catatan("", "muted")
        v.addWidget(self.l_redock_proyek)
        h = QHBoxLayout()
        h.addWidget(kit.tombol("Jalankan validasi di proyek…", self._jalankan_validasi_proyek,
                               tip="Memakai reseptor, kotak, dan mesin proyek (Docking › Validasi redocking)"))
        h.addWidget(kit.tombol("Muat ulang dari proyek", self._muat_validasi_proyek))
        h.addStretch(1)
        v.addLayout(h)

        v.addWidget(QLabel("<b>B. Dari berkas PDB kompleks</b>"))
        h = QHBoxLayout()
        self.e_pdb = QLineEdit()
        self.e_pdb.setPlaceholderText("Berkas PDB berisi protein dan ligan kristal")
        self.e_pdb.setReadOnly(True)
        h.addWidget(self.e_pdb, 1)
        h.addWidget(kit.tombol("Pilih…", self._pilih_pdb_redock))
        v.addLayout(h)
        h = QHBoxLayout()
        h.addWidget(QLabel("Kode residu ligan (opsional):"))
        self.e_resn = QLineEdit()
        self.e_resn.setMaximumWidth(70)
        self.e_resn.setMaxLength(3)
        self.e_resn.setPlaceholderText("mis. MK1")
        h.addWidget(self.e_resn)
        h.addWidget(QLabel("Exhaustiveness:"))
        self.s_exh_redock = QSpinBox()
        self.s_exh_redock.setToolTip("Exhaustiveness pencarian saat redocking. Nilai ini harus sama dengan yang akan Anda pakai pada docking sungguhan — validasi dengan pencarian yang lebih teliti tidak mewakili protokol Anda.")
        self.s_exh_redock.setRange(1, 32)
        self.s_exh_redock.setValue(8)
        h.addWidget(self.s_exh_redock)
        self.b_redock = kit.tombol("Jalankan redocking", self._jalankan_redocking_berkas, utama=True)
        h.addWidget(self.b_redock)
        h.addStretch(1)
        v.addLayout(h)

        self.k_rmsd = kit.Kartu("RMSD pose terbaik", "–", "terhadap kristal")
        self.k_energi = kit.Kartu("Energi docking", "–", "kcal/mol")
        self.k_status = kit.Kartu("Status", "Belum dijalankan", f"kriteria RMSD ≤ {id_angka('2.0')} Å")
        v.addLayout(kit.baris_kartu(self.k_rmsd, self.k_energi, self.k_status))
        self.l_info_redock = kit.catatan("", "muted")
        v.addWidget(self.l_info_redock)
        v.addStretch(1)
        return w

    def _muat_validasi_proyek(self):
        """Ambil validasi redocking yang sudah ada di proyek (jika ada) sebagai hasil langkah 1."""
        val = getattr(self.proyek, "validasi", None) or {}
        if val.get("rmsd") is None:
            self.l_redock_proyek.setText("Proyek ini belum punya validasi redocking.")
            return
        self.hasil_redocking = {
            "rmsd": float(val["rmsd"]), "sukses": float(val["rmsd"]) <= _AMBANG_RMSD,
            "energi": val.get("energi"), "ligan": val.get("ligan") or "ligan kristal",
            "reseptor": (self.proyek.reseptor or {}).get("nama", "") if getattr(self.proyek, "reseptor", None) else "",
            "mesin": val.get("mesin") or "", "sumber": "proyek", "tanggal": val.get("tanggal"),
        }
        self.l_redock_proyek.setText(
            f"Validasi proyek: {val.get('ligan', '')} · mesin {val.get('mesin', '?')} · {val.get('tanggal') or 'tanggal tak tercatat'}.")
        self._segarkan_redocking()

    def _jalankan_validasi_proyek(self):
        if self.jw is None or not hasattr(self.jw, "validasi_redocking"):
            self.l_status.setText("Validasi proyek hanya tersedia dari jendela utama.")
            return
        self.jw.validasi_redocking()
        self.l_status.setText("Validasi dijalankan di jendela utama; setelah selesai, klik “Muat ulang dari proyek”.")

    def _pilih_pdb_redock(self):
        f, _ = QFileDialog.getOpenFileName(self, "PDB kompleks kristal", "", "PDB (*.pdb *.ent)")
        if f:
            self.e_pdb.setText(f)

    def _jalankan_redocking_berkas(self):
        if not self.e_pdb.text():
            self.l_status.setText("Pilih berkas PDB kompleks dulu.")
            return
        path = Path(self.e_pdb.text())
        self._mulai(f"Redocking {path.name}…", lambda lapor: validasi_protokol.jalankan_redocking_mandiri(
            path, nama_ligan=self.e_resn.text().strip().upper(), exhaustiveness=self.s_exh_redock.value(), lapor=lapor),
            self._redocking_selesai, tombol=[self.b_redock], tak_tentu=True)

    def _redocking_selesai(self, r):
        self.hasil_redocking = {
            "rmsd": r.rmsd, "sukses": r.sukses, "energi": r.energi, "ligan": r.ligan, "reseptor": r.reseptor,
            "mesin": "AutoDock Vina", "sumber": "berkas", "waktu": r.waktu_detik}
        self._segarkan_redocking()
        self.l_status.setText(f"Redocking selesai: RMSD {id_angka(f'{r.rmsd:.2f}')} Å.")

    def _segarkan_redocking(self):
        r = self.hasil_redocking
        if not r:
            return
        ok = bool(r["sukses"])
        self.k_rmsd.isi(f"{kit.f(r['rmsd'])} Å", "terhadap kristal", "ok" if ok else "bad")
        self.k_energi.isi(kit.f(r["energi"], 1) if r.get("energi") is not None else "–", "kcal/mol")
        self.k_status.isi("Lolos" if ok else "Di luar ambang", f"kriteria RMSD ≤ {kit.f(_AMBANG_RMSD, 1)} Å",
                          "ok" if ok else "bad")
        self.l_info_redock.setText(f"Ligan: {r['ligan']} · Reseptor: {r['reseptor'] or '–'} · Sumber: "
                                   f"{'proyek' if r['sumber'] == 'proyek' else 'berkas PDB'}")

    # ------------------------------------------------------------------ halaman 2: cross-docking
    def _halaman_cross(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(kit.catatan(
            "Cross-docking: ligan tiap struktur di-docking ke semua struktur lain dari target yang sama, setelah struktur "
            "disuperposisikan lewat Cα. Butuh ≥ 2 berkas PDB kompleks (protein + ligan kristal), mis. beberapa entri PDB "
            "target yang sama.", "muted"))
        h = QHBoxLayout()
        self.daftar_cross = QListWidget()
        self.daftar_cross.setMaximumHeight(130)
        h.addWidget(self.daftar_cross, 1)
        k = QVBoxLayout()
        k.addWidget(kit.tombol("Tambah berkas…", self._tambah_cross))
        k.addWidget(kit.tombol("Hapus terpilih", self._hapus_cross))
        k.addStretch(1)
        h.addLayout(k)
        v.addLayout(h)
        h = QHBoxLayout()
        h.addWidget(QLabel("Exhaustiveness:"))
        self.s_exh_cross = QSpinBox()
        self.s_exh_cross.setToolTip("Exhaustiveness untuk cross-docking. Biasanya disamakan dengan redocking supaya kedua angka dapat dibandingkan langsung.")
        self.s_exh_cross.setRange(1, 32)
        self.s_exh_cross.setValue(4)
        h.addWidget(self.s_exh_cross)
        self.b_cross = kit.tombol("Jalankan cross-docking", self._jalankan_cross, utama=True)
        h.addWidget(self.b_cross)
        self.l_est_cross = QLabel("")
        self.l_est_cross.setObjectName("subjudul")
        h.addWidget(self.l_est_cross, 1)
        v.addLayout(h)
        self.l_cross = kit.catatan("Belum dijalankan.", "muted")
        v.addWidget(self.l_cross)
        self.kanvas_cross = KanvasSvg()
        v.addWidget(self.kanvas_cross, 1)
        self.l_catatan_cross = kit.catatan("", "peringatan")
        self.l_catatan_cross.setVisible(False)
        v.addWidget(self.l_catatan_cross)
        return w

    def _tambah_cross(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "PDB kompleks target yang sama", "", "PDB (*.pdb *.ent)")
        for f in fs:
            p = Path(f)
            if p not in self.berkas_cross:
                self.berkas_cross.append(p)
        self._segarkan_daftar_cross()

    def _hapus_cross(self):
        for it in self.daftar_cross.selectedItems():
            self.berkas_cross.pop(self.daftar_cross.row(it))
        self._segarkan_daftar_cross()

    def _segarkan_daftar_cross(self):
        self.daftar_cross.clear()
        for p in self.berkas_cross:
            self.daftar_cross.addItem(p.stem)
        n = len(self.berkas_cross)
        self.b_cross.setEnabled(n >= 2 and not self._sibuk)
        self.l_est_cross.setText(f"{n} struktur → {n * n} docking (±{n * n * 1}–{n * n * 3} menit)" if n >= 2
                                 else "Butuh ≥ 2 berkas.")

    def _jalankan_cross(self):
        label = []
        for p in self.berkas_cross:
            t = p.stem[:8]
            label.append(t if t not in label else f"{t}_{len(label) + 1}")
        daftar = list(zip(label, self.berkas_cross))
        self._mulai("Cross-docking…", lambda lapor: validasi_protokol.jalankan_cross_docking(
            daftar, exhaustiveness=self.s_exh_cross.value(), lapor=lapor),
            self._cross_selesai, tombol=[self.b_cross], tak_tentu=True)

    def _cross_selesai(self, r):
        self.hasil_cross = r
        if not r.tersedia:
            self.l_cross.setText(r.alasan)
            return
        mat = [x for baris in r.matriks_rmsd for x in baris if x is not None]
        ok = sum(1 for x in mat if x <= _AMBANG_RMSD)
        self.l_cross.setText(f"{ok} dari {len(mat)} pasangan terhitung ber-RMSD ≤ {kit.f(_AMBANG_RMSD, 1)} Å "
                             f"(baris = reseptor, kolom = ligan).")
        self.kanvas_cross.latar = kit.warna("panel")
        self.kanvas_cross.set_svg(validasi_protokol.svg_matriks_cross_docking(
            r.label_struktur, r.matriks_rmsd, gelap=kit.mode() == "gelap"))
        self.l_catatan_cross.setVisible(bool(r.catatan))
        self.l_catatan_cross.setText("\n".join("• " + c for c in r.catatan))
        self.l_status.setText("Cross-docking selesai.")

    # ------------------------------------------------------------------ halaman 3: pengayaan
    def _halaman_pengayaan(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        self.l_syarat = kit.catatan("", "muted")
        v.addWidget(self.l_syarat)

        h = QHBoxLayout()
        h.addWidget(QLabel("Target ChEMBL:"))
        self.e_target = QLineEdit()
        self.e_target.setPlaceholderText("mis. CHEMBL243 (protease HIV-1)")
        self.e_target.setMaximumWidth(220)
        h.addWidget(self.e_target)
        h.addWidget(QLabel("pChEMBL ≥"))
        self.s_pchembl = QDoubleSpinBox()
        self.s_pchembl.setToolTip("Ambang pChEMBL untuk menyaring senyawa aktif dari ChEMBL. 7 (100 nM) memberi himpunan aktif yang jelas; menurunkannya menambah jumlah tetapi memasukkan senyawa berafinitas lemah.")
        self.s_pchembl.setRange(5.0, 10.0)
        self.s_pchembl.setSingleStep(0.5)
        self.s_pchembl.setValue(7.0)
        h.addWidget(self.s_pchembl)
        h.addWidget(QLabel("Maks aktif:"))
        self.s_maks_aktif = QSpinBox()
        self.s_maks_aktif.setToolTip("Banyaknya senyawa aktif yang dipakai dalam uji pengayaan. 20 sudah cukup untuk angka yang stabil; menambahnya memperpanjang waktu docking secara linier.")
        self.s_maks_aktif.setRange(5, 50)
        self.s_maks_aktif.setValue(20)
        h.addWidget(self.s_maks_aktif)
        self.b_aktif = kit.tombol("Ambil aktif dari ChEMBL", self._ambil_aktif)
        h.addWidget(self.b_aktif)
        self.b_csv_aktif = kit.tombol("Dari CSV…", self._impor_aktif_csv, tip="Kolom: smiles[,nama[,pchembl]]")
        h.addWidget(self.b_csv_aktif)
        h.addStretch(1)
        v.addLayout(h)
        self.l_aktif = kit.catatan("Belum ada senyawa aktif.", "muted")
        v.addWidget(self.l_aktif)

        h = QHBoxLayout()
        h.addWidget(QLabel("Decoy per aktif:"))
        self.s_per_aktif = QSpinBox()
        self.s_per_aktif.setToolTip("Jumlah decoy per senyawa aktif. Nisbah 1:20 adalah praktik umum (mengikuti DUD-E); nisbah lebih kecil membuat nilai pengayaan tampak lebih baik daripada sebenarnya.")
        self.s_per_aktif.setRange(5, 100)
        self.s_per_aktif.setValue(20)
        h.addWidget(self.s_per_aktif)
        h.addWidget(QLabel("Exhaustiveness:"))
        self.s_exh_enrich = QSpinBox()
        self.s_exh_enrich.setToolTip("Exhaustiveness untuk uji pengayaan. Samakan dengan protokol produksi Anda agar angkanya bermakna.")
        self.s_exh_enrich.setRange(1, 32)
        self.s_exh_enrich.setValue(4)
        h.addWidget(self.s_exh_enrich)
        self.b_decoy = kit.tombol("Buat decoy", self._buat_decoy)
        h.addWidget(self.b_decoy)
        self.b_enrich = kit.tombol("Docking & hitung pengayaan", self._jalankan_enrichment, utama=True)
        h.addWidget(self.b_enrich)
        h.addStretch(1)
        v.addLayout(h)
        self.l_est_enrich = QLabel("")
        self.l_est_enrich.setObjectName("subjudul")
        v.addWidget(self.l_est_enrich)

        self.tab_sifat = kit.tabel(["Sifat", "Aktif (rata ± SD)", "Decoy (rata ± SD)", "KS D", "KS p", "Penilaian"], regang=0)
        v.addWidget(self.tab_sifat, 1)
        self.l_peringatan_decoy = kit.catatan("", "peringatan")
        self.l_peringatan_decoy.setVisible(False)
        v.addWidget(self.l_peringatan_decoy)
        return w

    def _syarat_enrichment(self):
        """(ok, pesan, receptor_pdbqt, kotak) dari proyek aktif."""
        pr = self.proyek
        if not pr or not getattr(pr, "reseptor", None) or not pr.reseptor.get("pdbqt"):
            return False, "Siapkan reseptor di proyek dulu: pengayaan memakai reseptor dan kotak proyek Anda.", None, None
        f = pr.p(pr.reseptor["pdbqt"])
        if not f.exists():
            return False, f"Berkas reseptor PDBQT tidak ditemukan: {f.name}.", None, None
        box = getattr(self.jw, "box", None) or {}
        if not box.get("pusat"):
            return False, "Tentukan kotak docking di proyek dulu (Siapkan › Langkah 3 · Area docking).", None, None
        k = mesin.Kotak(pusat=list(box["pusat"]), ukuran=list(box["ukuran"]), spasi=box.get("spasi", 0.375))
        return True, (f"Reseptor proyek: {pr.reseptor.get('nama', f.stem)} · kotak pusat "
                      f"{', '.join(kit.f(x, 1) for x in k.pusat)} Å, ukuran {', '.join(kit.f(x, 1) for x in k.ukuran)} Å."), f, k

    def _segarkan_syarat(self):
        ok, pesan, _, _ = self._syarat_enrichment()
        self.l_syarat.setText(pesan)
        n_a, n_d = len(self.senyawa_aktif), len((self.hasil_decoy or {}).get("decoy", []))
        self.b_enrich.setEnabled(ok and n_a >= 3 and n_d >= 3 and not self._sibuk)
        self.b_decoy.setEnabled(n_a >= 3 and not self._sibuk)
        if n_a and n_d:
            self.l_est_enrich.setText(f"{n_a + n_d} ligan akan di-docking (±{(n_a + n_d) // 3}–{(n_a + n_d)} menit di CPU).")
        else:
            self.l_est_enrich.setText("")

    def _ambil_aktif(self):
        target = self.e_target.text().strip().upper()
        if not target:
            self.l_status.setText("Isi ID target ChEMBL dulu (mis. CHEMBL243).")
            return
        self._mulai(f"Mengambil aktif {target} dari ChEMBL…", lambda lapor: decoy.pilih_aktif(
            target, pchembl_min=self.s_pchembl.value(), maks=self.s_maks_aktif.value(), lapor=lapor),
            self._aktif_selesai, tombol=[self.b_aktif], tak_tentu=True)

    def _aktif_selesai(self, daftar):
        if not daftar:
            self.l_status.setText("Tidak ada senyawa aktif yang memenuhi syarat; turunkan ambang pChEMBL atau cek ID target.")
            return
        self.senyawa_aktif = daftar
        self.hasil_decoy = self.hasil_enrich = None
        self.l_aktif.setText(f"{len(daftar)} aktif beragam kerangka (Butina 0,6), pChEMBL ≥ {kit.f(self.s_pchembl.value(), 1)}.")
        self.tab_sifat.setRowCount(0)
        self._segarkan_syarat()
        self.l_status.setText(f"{len(daftar)} aktif terpilih.")

    def _impor_aktif_csv(self):
        f, _ = QFileDialog.getOpenFileName(self, "Aktif dari CSV", "", "CSV (*.csv *.txt)")
        if not f:
            return
        daftar = []
        try:
            with open(f, newline="", encoding="utf-8-sig") as fh:
                for i, baris in enumerate(csv.reader(fh)):
                    if not baris or not baris[0].strip() or baris[0].strip().lower() == "smiles":
                        continue
                    smi = baris[0].strip()
                    item = {"id": f"CSV{len(daftar) + 1}", "nama": baris[1].strip() if len(baris) > 1 else f"aktif_{len(daftar) + 1}",
                            "smiles": smi}
                    res = decoy.hitung_sifat(smi, nama=item["nama"], cid=item["id"])
                    if res is None:
                        continue
                    daftar.append(item)
        except (OSError, UnicodeDecodeError, csv.Error) as e:
            self.l_status.setText(f"CSV tidak terbaca: {e}")
            return
        if len(daftar) < 3:
            self.l_status.setText("CSV berisi < 3 SMILES valid.")
            return
        self._aktif_selesai(daftar)

    def _buat_decoy(self):
        aktif = list(self.senyawa_aktif)
        per = self.s_per_aktif.value()
        self._mulai("Membuat decoy…", lambda lapor: decoy.buat_decoy(aktif, per_aktif=per, lapor=lapor),
                    self._decoy_selesai, tombol=[self.b_decoy], tak_tentu=True)

    def _decoy_selesai(self, res):
        self.hasil_decoy = res
        self.hasil_enrich = None
        self._tabel_sifat(res.get("statistik_sifat") or {})
        pe = res.get("peringatan") or []
        self.l_peringatan_decoy.setVisible(bool(pe))
        self.l_peringatan_decoy.setText("\n".join("• " + x for x in pe))
        self._segarkan_syarat()
        self.l_status.setText(f"{res['n_decoy']} decoy untuk {res['n_aktif']} aktif.")

    def _tabel_sifat(self, stat: Dict[str, Any]):
        t = self.tab_sifat
        t.setRowCount(0)
        for k_, d in stat.items():
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, kit.sel(d["label"], rata_kanan=False))
            t.setItem(r, 1, kit.sel(f"{kit.f(d['aktif_rerata'], 1)} ± {kit.f(d['aktif_sd'], 1)}", rata_kanan=True))
            t.setItem(r, 2, kit.sel(f"{kit.f(d['decoy_rerata'], 1)} ± {kit.f(d['decoy_sd'], 1)}", rata_kanan=True))
            t.setItem(r, 3, kit.sel(kit.f(d["ks_d"], 3), d["ks_d"]))
            t.setItem(r, 4, kit.sel(kit.f(d["ks_p"], 4), d["ks_p"]))
            it = kit.sel("Bias (p < 0,05)" if d["bias"] else "Seimbang", rata_kanan=False)
            it.setForeground(kit.warna("warn" if d["bias"] else "ok"))
            t.setItem(r, 5, it)

    def _jalankan_enrichment(self):
        ok, pesan, rec, kotak = self._syarat_enrichment()
        if not ok:
            self.l_status.setText(pesan)
            return
        aktif = list(self.senyawa_aktif)
        dec = list((self.hasil_decoy or {}).get("decoy", []))
        exh = self.s_exh_enrich.value()
        self._batal.clear()
        self._mulai(f"Docking {len(aktif) + len(dec)} ligan…", lambda lapor: validasi_protokol.jalankan_enrichment(
            rec, kotak, aktif, dec, exhaustiveness=exh, lapor=lapor, batal=self._batal.is_set),
            self._enrichment_selesai, tombol=[self.b_enrich, self.b_decoy, self.b_aktif], dapat_batal=True)

    def _enrichment_selesai(self, r):
        self.hasil_enrich = r
        self._segarkan_ringkasan()
        self.l_status.setText(f"Pengayaan selesai: AUC {kit.f(r.auc, 3)}. Lihat tab Ringkasan.")
        self._ke(3)

    # ------------------------------------------------------------------ halaman 4: ringkasan
    def _halaman_ringkasan(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        self.k_rmsd2 = kit.Kartu("Redocking RMSD", "–", "belum dijalankan")
        self.k_auc = kit.Kartu("ROC-AUC", "–", "belum dijalankan")
        self.k_bedroc = kit.Kartu("BEDROC (α=20)", "–", "")
        self.k_ef1 = kit.Kartu("EF 1%", "–", "")
        self.k_pb = kit.Kartu("PoseBusters", "–", "dari hasil docking proyek")
        v.addLayout(kit.baris_kartu(self.k_rmsd2, self.k_auc, self.k_bedroc, self.k_ef1, self.k_pb))
        h = QHBoxLayout()
        self.kanvas_roc = KanvasSvg()
        self.kanvas_enrich = KanvasSvg()
        h.addWidget(self.kanvas_roc, 1)
        h.addWidget(self.kanvas_enrich, 1)
        v.addLayout(h, 1)
        self.l_catatan_ringkas = kit.catatan("", "peringatan")
        self.l_catatan_ringkas.setVisible(False)
        v.addWidget(self.l_catatan_ringkas)
        h = QHBoxLayout()
        h.addWidget(kit.tombol("Salin paragraf metode", self._salin_metode))
        h.addWidget(kit.tombol("Laporan HTML…", self._ekspor_html))
        h.addWidget(kit.tombol("Kirim ROC ke komposer", self._kirim_komposer))
        h.addStretch(1)
        v.addLayout(h)
        return w

    def _muat_pb_proyek(self):
        """PoseBusters dari QC yang sudah tercatat pada hasil docking proyek (tidak menghitung ulang)."""
        pr = self.proyek
        if not pr:
            return
        nilai = [l["qc"] for j in pr.job for l in j["ligan"] if l.get("status") == "selesai" and l.get("qc")]
        if not nilai:
            return
        lulus = sum(1 for q in nilai if q.get("lulus"))
        self.hasil_pb = {"tersedia": True, "total_pose": len(nilai), "lulus_valid": lulus,
                         "persen_valid": round(100.0 * lulus / len(nilai), 1)}

    def _segarkan_ringkasan(self):
        r = self.hasil_redocking
        if r:
            ok = bool(r["sukses"])
            self.k_rmsd2.isi(f"{kit.f(r['rmsd'])} Å", "lolos (≤ 2,0 Å)" if ok else "di luar ambang", "ok" if ok else "bad")
        e = self.hasil_enrich
        if e:
            self.k_auc.isi(kit.f(e.auc, 3), f"{e.n_aktif} aktif · {e.n_decoy} decoy", "ok" if e.auc >= 0.7 else "warn")
            self.k_bedroc.isi(kit.f(e.bedroc, 3), "pengayaan dini")
            self.k_ef1.isi(f"{kit.f(e.ef1, 1)}×", "dibanding acak")
            gelap = kit.mode() == "gelap"
            try:
                for kv, mode in ((self.kanvas_roc, "roc"), (self.kanvas_enrich, "enrich")):
                    kv.latar = kit.warna("panel")
                    svg, _ = grafik_uji.grafik_roc(e.kurva_roc, judul="Kurva ROC" if mode == "roc" else "Kurva pengayaan",
                                                   gelap=gelap, mode=mode)
                    kv.set_svg(svg)
            except Exception as err:
                catat.log.debug(f"Gagal render grafik ringkasan: {err}")
            pe = list(e.peringatan) + list((self.hasil_decoy or {}).get("peringatan", []))
            self.l_catatan_ringkas.setVisible(bool(pe))
            self.l_catatan_ringkas.setText("\n".join("• " + x for x in pe))
        pb = self.hasil_pb
        if pb:
            self.k_pb.isi(f"{kit.f(pb['persen_valid'], 1)}%", f"{pb['lulus_valid']}/{pb['total_pose']} pose proyek",
                          "ok" if pb["persen_valid"] >= 70 else "warn")
        else:
            self.k_pb.isi("–", "belum ada QC PoseBusters di proyek")

    def _ringkasan_dict(self) -> Dict[str, Any]:
        """Hanya langkah yang benar-benar dijalankan; tidak ada nilai bawaan."""
        d: Dict[str, Any] = {}
        if self.hasil_redocking:
            d["redocking"] = dict(self.hasil_redocking)
        if self.hasil_cross and self.hasil_cross.tersedia:
            c = self.hasil_cross
            d["cross_docking"] = {"tersedia": True, "label_struktur": c.label_struktur, "matriks_rmsd": c.matriks_rmsd,
                                  "catatan": c.catatan}
        if self.hasil_enrich:
            e = self.hasil_enrich
            d["enrichment"] = {
                "n_aktif": e.n_aktif, "n_decoy": e.n_decoy, "auc": e.auc, "bedroc": e.bedroc, "ef1": e.ef1,
                "ef5": e.ef5, "logauc": e.logauc, "p_nilai": e.p_nilai, "potong_youden": e.potong_youden,
                "sensitivitas": e.sensitivitas, "spesifisitas": e.spesifisitas, "kurva_roc": e.kurva_roc,
                "n_gagal_aktif": e.n_gagal_aktif, "n_gagal_decoy": e.n_gagal_decoy, "peringatan": e.peringatan}
        if self.hasil_pb:
            d["posebusters"] = dict(self.hasil_pb)
        if self.hasil_decoy:
            d["decoy"] = {"peringatan": self.hasil_decoy.get("peringatan", [])}
        return d

    def _salin_metode(self):
        teks = validasi_protokol.susun_paragraf_metode(self._ringkasan_dict(), bahasa=i18n.BAHASA)
        if not teks:
            self.l_status.setText("Belum ada uji yang dijalankan; paragraf metode kosong.")
            return
        QApplication.clipboard().setText(teks)
        self.l_status.setText("Paragraf metode disalin ke papan klip.")

    def _ekspor_html(self):
        d = self._ringkasan_dict()
        if not d:
            self.l_status.setText("Belum ada uji yang dijalankan.")
            return
        f, _ = QFileDialog.getSaveFileName(self, "Simpan laporan validasi", "Validasi_Protokol.html", "HTML (*.html)")
        if f:
            Path(f).write_text(validasi_protokol.buat_halaman_laporan_html(d), encoding="utf-8")
            self.l_status.setText(f"Laporan disimpan: {Path(f).name}")

    def _kirim_komposer(self):
        e = self.hasil_enrich
        if not e or not e.kurva_roc:
            self.l_status.setText("Jalankan pengayaan dulu: belum ada kurva ROC.")
            return
        svg, _ = grafik_uji.grafik_roc(e.kurva_roc, judul="Validasi protokol · ROC", mode="roc")
        if not getattr(self.jw, "komposer", None):
            self.jw.buka_komposer()
        self.jw.komposer.tambah({"nama": "Validasi protokol · ROC", "jenis": "svg", "isi": svg, "w": 760, "h": 480})
        self.l_status.setText("Kurva ROC ditambahkan ke Komposer Figur.")

    # ------------------------------------------------------------------ infrastruktur
    def _ke(self, n):
        self.langkah = max(0, min(len(LANGKAH) - 1, n))
        self.tumpuk.setCurrentIndex(self.langkah)
        self.l_langkah.setText("  ›  ".join(f"<b>{i + 1}. {t}</b>" if i == self.langkah else f"{i + 1}. {t}"
                                           for i, t in enumerate(LANGKAH)))
        self.b_mundur.setEnabled(self.langkah > 0)
        self.b_maju.setEnabled(self.langkah < len(LANGKAH) - 1)
        if self.langkah == 1:
            self._segarkan_daftar_cross()
        elif self.langkah == 2:
            self._segarkan_syarat()
        elif self.langkah == 3:
            self._muat_pb_proyek()
            self._segarkan_ringkasan()

    def _mulai(self, pesan, fn, selesai, tombol=(), tak_tentu=False, dapat_batal=False):
        if self._sibuk:
            return
        self._sibuk = True
        self._tombol_kerja = [b for b in tombol if b is not None]
        for b in self._tombol_kerja:
            b.setEnabled(False)
        self.l_status.setText(pesan)
        self.prog.setVisible(True)
        self.prog.setRange(0, 0 if tak_tentu else 100)
        self.b_batal.setVisible(dapat_batal)

        def _progres(i, total, teks):
            self.prog.setRange(0, max(1, total))
            self.prog.setValue(i)
            self.l_status.setText(teks)

        def _akhir():
            self._sibuk = False
            self.prog.setVisible(False)
            self.b_batal.setVisible(False)
            for b in self._tombol_kerja:
                b.setEnabled(True)
            self._segarkan_daftar_cross()
            self._segarkan_syarat()

        def _ok(hasil):
            _akhir()
            try:
                selesai(hasil)
            except Exception as e:  # galat tampilan tidak boleh membuat dialog macet
                catat.log.error(f"Validasi protokol: {e}")
                self.l_status.setText(f"Hasil diterima tetapi gagal ditampilkan: {e}")

        def _gagal(teks):
            _akhir()
            utama = teks.split("\n", 1)[0]
            self.l_status.setText("Dibatalkan." if "Dibatalkan" in utama else f"Gagal: {utama}")
            catat.log.error(f"Validasi protokol gagal: {teks}")

        kerja.jalankan(fn, selesai=_ok, galat=_gagal, progres=_progres)

    def _minta_batal(self):
        self._batal.set()
        self.l_status.setText("Membatalkan setelah docking yang sedang berjalan selesai…")

    def closeEvent(self, e):
        self._batal.set()
        super().closeEvent(e)
