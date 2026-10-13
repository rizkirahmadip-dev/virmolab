"""Wizard preparasi reseptor: 1 Periksa struktur → 2 Pembersihan → 3 Protonasi & hidrogen → 4 Ringkasan."""
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QRadioButton,
                               QStackedWidget, QTextBrowser, QVBoxLayout, QWidget)

from ..core.prep_reseptor import OpsiReseptor
from . import kit

LANGKAH = ["Periksa struktur", "Pembersihan", "Protonasi dan hidrogen", "Ringkasan"]
TINGKAT_TOKEN = {"ok": "ok", "info": "ink2", "peringatan": "warn", "masalah": "bad"}


def warna_tingkat(tingkat):
    """Warna tingkat pemeriksaan menurut tema aktif, bukan nilai tetap tema terang."""
    return kit.hx(TINGKAT_TOKEN.get(tingkat, "ink2"))
SIMBOL = {"ok": "✓", "info": "•", "peringatan": "!", "masalah": "✕"}


class DialogReseptor(QDialog):
    def __init__(self, protein, ada_logam, parent=None, aktif=None, teks_sumber=None):
        """protein: daftar Objek protein; ada_logam: {id protein: [nama ion logam]};
        teks_sumber(o): teks PDB protein + ion + ligan asli dari sumber yang sama (untuk pemeriksaan)."""
        super().__init__(parent)
        self.setWindowTitle("Siapkan reseptor")
        self.resize(820, 600)
        self.protein = protein
        self.ada_logam = ada_logam
        self.teks_sumber = teks_sumber or (lambda o: o.teks)
        self._cek = {}
        utama = QHBoxLayout(self)
        self.l_langkah = QListWidget()
        self.l_langkah.setFixedWidth(200)
        self.l_langkah.setFocusPolicy(Qt.NoFocus)
        for i, t in enumerate(LANGKAH, 1):
            self.l_langkah.addItem(QListWidgetItem(f"{i}  {t}"))
        self.l_langkah.currentRowChanged.connect(self._ke)
        utama.addWidget(self.l_langkah)
        kanan = QVBoxLayout()
        self.judul = QLabel()
        self.judul.setObjectName("h2")
        self.judul.setStyleSheet("font-size: 15px; font-weight: 600;")
        kanan.addWidget(self.judul)
        self.stak = QStackedWidget()
        kanan.addWidget(self.stak, 1)
        self.stak.addWidget(self._hal_periksa(aktif))
        self.stak.addWidget(self._hal_bersih())
        self.stak.addWidget(self._hal_proton())
        self.stak.addWidget(self._hal_ringkas())
        bawah = QHBoxLayout()
        bawah.addStretch(1)
        self.b_batal = QPushButton("✕ Batal")
        self.b_kembali = QPushButton("‹ Kembali")
        self.b_lanjut = QPushButton("Lanjut ›")
        self.b_lanjut.setObjectName("primary")
        self.b_batal.clicked.connect(self.reject)
        self.b_kembali.clicked.connect(lambda: self.l_langkah.setCurrentRow(self.stak.currentIndex() - 1))
        self.b_lanjut.clicked.connect(self._lanjut)
        for b in (self.b_batal, self.b_kembali, self.b_lanjut):
            bawah.addWidget(b)
        kanan.addLayout(bawah)
        utama.addLayout(kanan, 1)
        self.cek_rantai = {}
        self._isi_rantai()
        self.l_langkah.setCurrentRow(0)

    # ------------------------------------------------------------------ halaman
    def _hal_periksa(self, aktif):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        f = QFormLayout()
        self.cmb = QComboBox()
        for o in self.protein:
            self.cmb.addItem(f"{o.nama}  ·  {o.info.get('atom', '')} atom", o.id)
        if aktif:
            self.cmb.setCurrentIndex(max(0, self.cmb.findData(aktif)))
        self.cmb.currentIndexChanged.connect(self._isi_rantai)
        f.addRow("Protein", self.cmb)
        self.w_rantai = QWidget()
        self.l_rantai = QHBoxLayout(self.w_rantai)
        self.l_rantai.setContentsMargins(0, 0, 0, 0)
        f.addRow("Rantai", self.w_rantai)
        v.addLayout(f)
        self.t_periksa = QTextBrowser()
        self.t_periksa.setOpenLinks(False)
        v.addWidget(self.t_periksa, 1)
        return w

    def _hal_bersih(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        g = QGroupBox("Yang dibuang")
        gv = QVBoxLayout(g)
        self.c_air = QCheckBox("Hapus molekul air")
        self.c_air.setChecked(True)
        self.c_air.setToolTip("Air kristal biasanya dibuang; pertahankan hanya air penjembatan yang terbukti penting")
        self.c_lig = QCheckBox("Hapus ligan asli, aditif, dan ion non-logam")
        self.c_lig.setChecked(True)
        self.c_jembatan = QCheckBox("Pertahankan air yang menjembatani protein dan ligan (≤ 3,5 Å)")
        self.c_jembatan.setToolTip("Hanya air yang dekat ke N/O protein sekaligus ke ligan asli. "
                                   "Ditulis ke PDBQT sebagai akseptor. Meeko sendiri membuang HOH, "
                                   "jadi atomnya ditambahkan kembali setelah preparasi.")
        self.c_kof = QCheckBox("Pertahankan kofaktor (HEM, NAD, dan HET lain selain ligan utama)")
        self.c_kof.setToolTip("Bukan aditif kristalisasi dan bukan ligan terbesar. "
                              "Bila Meeko menolak residunya, preparasi beralih ke Open Babel.")
        h = QHBoxLayout()
        self.c_logam = QCheckBox("Pertahankan ion logam (Zn, Mg, Ca, Mn, Fe, Cu, Co, Ni) dalam radius")
        self.c_logam.setChecked(True)
        self.sp_rad = QDoubleSpinBox()
        self.sp_rad.setRange(0, 50)
        self.sp_rad.setValue(8.0)
        self.sp_rad.setSuffix(" Å")
        self.sp_rad.setToolTip("Jarak dari ligan asli. 0 = semua ion logam dipertahankan.")
        h.addWidget(self.c_logam)
        h.addWidget(self.sp_rad)
        h.addStretch(1)
        for x in (self.c_air, self.c_jembatan, self.c_lig, self.c_kof):
            gv.addWidget(x)
        gv.addLayout(h)
        self.l_logam = QLabel()
        self.l_logam.setObjectName("muted")
        gv.addWidget(self.l_logam)
        v.addWidget(g)
        g2 = QGroupBox("Konformasi alternatif")
        f2 = QFormLayout(g2)
        self.cmb_alt = QComboBox()
        self.cmb_alt.addItem("Okupansi tertinggi", "tertinggi")
        self.cmb_alt.addItem("Selalu altloc A", "A")
        f2.addRow("Pilih", self.cmb_alt)
        v.addWidget(g2)
        v.addStretch(1)
        return w

    def _hal_proton(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        g = QGroupBox("Keadaan protonasi residu")
        gv = QVBoxLayout(g)
        self.r_baku = QRadioButton("Baku (templat Meeko): Asp/Glu bermuatan −, Lys/Arg +, His netral")
        self.r_propka = QRadioButton("Berdasarkan pKa (PROPKA 3 + PDB2PQR) - disarankan")
        self.r_propka.setChecked(True)
        self._grup = QButtonGroup(self)
        self._grup.addButton(self.r_baku)
        self._grup.addButton(self.r_propka)
        gv.addWidget(self.r_propka)
        hp = QHBoxLayout()
        hp.setContentsMargins(24, 0, 0, 0)
        hp.addWidget(QLabel("pH"))
        self.sp_ph = QDoubleSpinBox()
        self.sp_ph.setRange(0.0, 14.0)
        self.sp_ph.setSingleStep(0.1)
        self.sp_ph.setDecimals(1)
        self.sp_ph.setValue(7.4)
        self.sp_ph.setToolTip("pH fisiologis 7,4; lisosom ±4,5-5; lambung ±2")
        hp.addWidget(self.sp_ph)
        hp.addStretch(1)
        gv.addLayout(hp)
        self.c_opt = QCheckBox("Optimasi jaringan ikatan hidrogen (rotasi OH/SH/NH₃⁺, flip His/Asn/Gln)")
        self.c_opt.setChecked(True)
        self.c_opt.setContentsMargins(24, 0, 0, 0)
        self.c_opt.setStyleSheet("margin-left: 24px;")
        gv.addWidget(self.c_opt)
        ket = QLabel("PDB2PQR juga melengkapi atom berat yang hilang (residu tidak lagi dibuang) dan menempatkan semua "
                     "hidrogen; posisi H hasil optimasi dipertahankan saat menulis PDBQT. His diberi HID/HIE/HIP, "
                     "Asp/Glu terkubur bisa netral (ASH/GLH) sesuai pKa.")
        ket.setWordWrap(True)
        ket.setObjectName("muted")
        ket.setStyleSheet("margin-left: 24px;")
        gv.addWidget(ket)
        gv.addWidget(self.r_baku)
        v.addWidget(g)
        self.r_baku.toggled.connect(self._atur_proton)
        g2 = QGroupBox("Muatan parsial")
        f3 = QFormLayout(g2)
        self.cmb_q = QComboBox()
        self.cmb_q.addItem("Gasteiger (dihitung Meeko)", "gasteiger")
        self.cmb_q.addItem("Muatan templat residu Meeko", "templat")
        self.cmb_q.addItem("Kollman (tidak tersedia)", "kollman")
        item = self.cmb_q.model().item(2)
        item.setEnabled(False)
        item.setToolTip("Muatan Kollman hanya ada di MGLTools (Python 2, tidak dibundel). "
                        "Gasteiger adalah standar Meeko untuk AutoDock-GPU dan Vina.")
        f3.addRow("Model", self.cmb_q)
        lh = QLabel("PDBQT AutoDock hanya menyimpan H polar; H non-polar digabung ke atom beratnya.")
        lh.setObjectName("muted")
        lh.setWordWrap(True)
        f3.addRow(lh)
        v.addWidget(g2)
        v.addStretch(1)
        return w

    def _hal_ringkas(self):
        self.t_ringkas = QTextBrowser()
        return self.t_ringkas

    # ------------------------------------------------------------------ logika
    def _atur_proton(self, *_):
        on = self.r_propka.isChecked()
        self.sp_ph.setEnabled(on)
        self.c_opt.setEnabled(on)

    def _ke(self, i):
        if i < 0:
            return
        self.stak.setCurrentIndex(i)
        self.judul.setText(f"Langkah {i + 1} dari {len(LANGKAH)} · {LANGKAH[i]}")
        self.b_kembali.setEnabled(i > 0)
        self.b_lanjut.setText("Siapkan reseptor" if i == len(LANGKAH) - 1 else "Lanjut ›")
        if i == len(LANGKAH) - 1:
            self._isi_ringkas()

    def _lanjut(self):
        i = self.stak.currentIndex()
        if i == 0 and not any(cb.isChecked() for cb in self.cek_rantai.values()):
            self.t_periksa.setHtml(f"<p style='color:{kit.hx('bad')}'>Pilih minimal satu rantai.</p>")
            return
        if i < len(LANGKAH) - 1:
            self.l_langkah.setCurrentRow(i + 1)
        else:
            self.accept()

    def _isi_rantai(self):
        while self.l_rantai.count():
            w = self.l_rantai.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.cek_rantai = {}
        o = self.objek()
        for c, rs in (o.rantai if o else {}).items():
            cb = QCheckBox(f"{c} ({len(rs)})")
            cb.setChecked(True)
            self.l_rantai.addWidget(cb)
            self.cek_rantai[c] = cb
        self.l_rantai.addStretch(1)
        logam = self.ada_logam.get(o.id, []) if o else []
        self.l_logam.setText("Ion logam di struktur: " + (", ".join(logam) if logam else "tidak ada"))
        self._periksa()

    def _periksa(self):
        o = self.objek()
        if not o:
            return
        if o.id not in self._cek:
            from ..core import periksa_protein
            try:
                self._cek[o.id] = periksa_protein.periksa(self.teks_sumber(o), o.fmt if o.fmt in ("pdb", "cif") else "pdb")
            except Exception as e:
                self._cek[o.id] = str(e)
        info = self._cek[o.id]
        if isinstance(info, str):
            self.t_periksa.setHtml(f"<p>Pemeriksaan tidak dapat dijalankan: {escape(info)}</p>")
            return
        from ..core.periksa_protein import skor
        s = skor(info)
        warna = kit.hx({"baik": "ok", "peringatan": "warn", "masalah": "bad"}[s])
        kepala = {"baik": "Struktur layak untuk docking", "peringatan": "Layak dengan catatan",
                  "masalah": "Ada masalah - periksa sebelum docking"}[s]
        o_ = [f"<p style='font-size:14px;font-weight:600;color:{warna}'>{kepala}</p>",
              f"<p style='color:#5b6b82'>{escape(info['metode'] or 'Metode tidak tercantum')} · {info['residu']} residu "
              f"· {info['atom']} atom · {len(info['ligan'])} ligan/aditif · {info['air']} air</p><table cellspacing=4>"]
        for t, teks in info["temuan"]:
            o_.append(f"<tr><td style='color:{warna_tingkat(t)};font-weight:700' valign=top>{SIMBOL[t]}</td>"
                      f"<td>{escape(teks)}</td></tr>")
        o_.append("</table>")
        self.t_periksa.setHtml("".join(o_))
        # saran otomatis: ada atom hilang -> PROPKA/PDB2PQR (melengkapi)
        if info["hilang"]:
            self.r_propka.setChecked(True)

    def _isi_ringkas(self):
        op = self.opsi()
        o = self.objek()
        b = [("Protein", o.nama if o else "-"),
             ("Rantai", ", ".join(op.rantai) if op.rantai else "semua"),
             ("Air", "dihapus" if op.hapus_air else "dipertahankan"),
             ("Ligan asli & aditif", "dihapus" if op.hapus_ligan else "dipertahankan"),
             ("Ion logam", (f"dipertahankan ≤ {op.radius_logam:g} Å dari ligan asli" if op.radius_logam else
                            "semua dipertahankan") if op.pertahankan_logam else "dibuang"),
             ("Konformasi alternatif", "okupansi tertinggi" if op.altloc == "tertinggi" else "altloc A"),
             ("Protonasi", f"PROPKA 3 + PDB2PQR, pH {op.ph:.1f}".replace(".", ",") if op.protonasi == "propka"
              else "baku templat Meeko"),
             ("Optimasi ikatan H", ("ya" if op.optimasi_h else "tidak") if op.protonasi == "propka" else " - "),
             ("Atom hilang", "dilengkapi PDB2PQR" if op.protonasi == "propka" else "residu tak lengkap dibuang"),
             ("Muatan parsial", self.cmb_q.currentText())]
        self.t_ringkas.setHtml("<table cellspacing=6>" + "".join(
            f"<tr><td style='color:#5b6b82'>{escape(k)}</td><td><b>{escape(v)}</b></td></tr>" for k, v in b)
            + "</table><p style='color:#5b6b82'>Hasil: reseptor PDBQT + PDB bersih + laporan preparasi (dengan tabel "
              "pKa bila PROPKA dipakai) di folder proyek <code>reseptor/</code>.</p>")

    def objek(self):
        oid = self.cmb.currentData()
        return next((o for o in self.protein if o.id == oid), None)

    def opsi(self):
        rantai = [c for c, cb in self.cek_rantai.items() if cb.isChecked()]
        return OpsiReseptor(rantai=rantai if len(rantai) < len(self.cek_rantai) else None,
                            hapus_air=self.c_air.isChecked(), hapus_ligan=self.c_lig.isChecked(),
                            pertahankan_logam=self.c_logam.isChecked(), radius_logam=self.sp_rad.value(),
                            altloc=self.cmb_alt.currentData(), muatan=self.cmb_q.currentData(),
                            protonasi="propka" if self.r_propka.isChecked() else "templat", ph=self.sp_ph.value(),
                            optimasi_h=self.c_opt.isChecked(), air_jembatan=self.c_jembatan.isChecked(),
                            kofaktor=self.c_kof.isChecked())

    def accept(self):
        if not any(cb.isChecked() for cb in self.cek_rantai.values()):
            self.l_langkah.setCurrentRow(0)
            return
        super().accept()
