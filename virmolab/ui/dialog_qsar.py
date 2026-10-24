"""Wizard QSAR & model pembelajaran mesin (F5): Data -> Kurasi -> Model -> Validasi -> Prediksi."""
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import grafik, qsar
from .. import i18n
from . import kerja, kit

LANGKAH = ("Data", "Kurasi", "Model", "Validasi", "Prediksi")


class DialogQSAR(QDialog):
    """Membangun model QSAR dari data aktivitas pengguna dan memprediksi ligan proyek."""

    def __init__(self, parent=None, proyek=None):
        super().__init__(parent)
        self.jw = parent
        self.proyek = proyek if proyek is not None else getattr(parent, "proyek", None)
        self.setWindowTitle("QSAR & model prediksi")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1150, 780)

        self.langkah = 0
        self.baris_mentah: List[Dict[str, Any]] = []
        self.hasil_kurasi: Dict[str, Any] = {}
        self.data: List[Dict[str, Any]] = []
        self.sumber_data = ""
        self.model: Dict[str, Any] = {}
        self.model_lain: Dict[str, Dict[str, Any]] = {}      # metode_bagi -> hasil
        self.y_acak: Dict[str, Any] = {}
        self.prediksi: List[Dict[str, Any]] = []
        self._penting: Any = None          # hasil kepentingan permutasi (None = belum dihitung)
        self._ligan_prediksi: List[Dict[str, Any]] = []
        self._sibuk = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul(
            "QSAR & model prediksi",
            "Membangun model dari data aktivitas Anda sendiri dan memprediksi ligan proyek. "
            "Mengikuti lima prinsip OECD: hanya metrik yang benar-benar dihitung yang ditampilkan."))

        self.l_langkah = QLabel()
        self.l_langkah.setObjectName("subjudul")
        lay.addWidget(self.l_langkah)

        self.tumpuk = QStackedWidget()
        for h in (self._halaman_data(), self._halaman_kurasi(), self._halaman_model(),
                  self._halaman_validasi(), self._halaman_prediksi()):
            self.tumpuk.addWidget(h)
        lay.addWidget(self.tumpuk, 1)

        h = QHBoxLayout()
        self.l_status = QLabel("")
        self.l_status.setObjectName("subjudul")
        self.l_status.setWordWrap(True)
        self.prog = QProgressBar()
        self.prog.setFixedWidth(200)
        self.prog.setRange(0, 0)
        self.prog.setVisible(False)
        h.addWidget(self.l_status, 1)
        h.addWidget(self.prog)
        lay.addLayout(h)

        self.b_mundur = kit.tombol("‹ Kembali", lambda: self._ke(self.langkah - 1))
        self.b_maju = kit.tombol("Lanjut ›", lambda: self._ke(self.langkah + 1), utama=True)
        lay.addLayout(kit.bar_bawah(self, kiri=[self.b_mundur], kanan=[self.b_maju]))
        self._ke(0)

    # ------------------------------------------------------------------ 1. data
    def _halaman_data(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(kit.catatan(
            "Sumber data: tabel aktivitas ChEMBL yang sudah diambil di proyek, atau berkas CSV berkolom "
            "smiles dan nilai (satuan nM/uM/M) atau smiles dan pIC50. Nilai bertanda > atau < tidak dipakai "
            "karena bukan pengukuran pasti.", "muted"))
        h = QHBoxLayout()
        self.b_chembl = kit.tombol("Ambil dari ChEMBL proyek", self._muat_chembl)
        h.addWidget(self.b_chembl)
        self.b_lab = kit.tombol("Ambil dari uji lab proyek", self._muat_eksperimen_lab)
        h.addWidget(self.b_lab)
        h.addWidget(kit.tombol("Impor CSV…", self._muat_csv))
        h.addStretch(1)
        v.addLayout(h)

        self.l_kartu = QLabel("Belum ada data.")
        self.l_kartu.setWordWrap(True)
        v.addWidget(self.l_kartu)
        self.tabel_data = kit.tabel(["SMILES", "Nama", "pIC50", "Catatan"], regang=3, urut=True)
        v.addWidget(self.tabel_data, 1)
        return w

    def _muat_chembl(self):
        eks = getattr(self.proyek, "eksperimen", None) or {}
        akt = eks.get("aktivitas") or []
        if not akt:
            self.l_status.setText("Proyek belum memuat data aktivitas ChEMBL. Ambil lebih dulu lewat menu ChEMBL.")
            return
        self.baris_mentah = qsar.muat_chembl(akt)
        self.sumber_data = f"ChEMBL target {eks.get('target', '')}".strip()
        self._tampil_data()

    def _muat_eksperimen_lab(self):
        eks = getattr(self.proyek, "eksperimen", None) or {}
        entri = eks.get("entri") or []
        # Entri ligan proyek tidak selalu berkunci 'smiles'; smiles_ligan membaca cache sifat / SDF sumber
        smi_map = {}
        for l in getattr(self.proyek, "ligan", []):
            smi = self.proyek.smiles_ligan(l) if hasattr(self.proyek, "smiles_ligan") else str(l.get("smiles") or "")
            smi_map[str(l.get("id"))] = smi
            if l.get("nama"):
                smi_map[str(l["nama"])] = smi
        baris = []
        for e in entri:
            p = e.get("pIC50")
            if p is not None:
                lid = str(e.get("ligan_id", "")).strip()
                smi = smi_map.get(lid, "")
                ent = {"smiles": smi, "nama": lid, "pic50": float(p)}
                if not smi:
                    ent["galat"] = "SMILES ligan tidak ditemukan di proyek"
                baris.append(ent)
        if not baris:
            self.l_status.setText("Belum ada entri uji laboratorium dengan pIC50 terukur di proyek.")
            return
        self.baris_mentah = baris
        self.sumber_data = "Uji laboratorium proyek"
        self._tampil_data()

    def _muat_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Pilih berkas CSV", "", "CSV (*.csv *.tsv *.txt)")
        if not path:
            return
        try:
            self.baris_mentah = qsar.muat_csv(path)
        except qsar.GalatQSAR as e:
            self.l_status.setText(str(e))
            return
        self.sumber_data = Path(path).name
        self._tampil_data()

    def _tampil_data(self):
        b = self.baris_mentah
        gagal = [x for x in b if x.get("galat")]
        nilai = [x["pic50"] for x in b if "pic50" in x]
        self.l_kartu.setText(
            f"{len(b)} baris dari {self.sumber_data}; {len(b) - len(gagal)} terbaca, {len(gagal)} bermasalah."
            + (f" Rentang pIC50 {min(nilai):.2f}–{max(nilai):.2f}.".replace(".", ",") if nilai else ""))
        self.tabel_data.setSortingEnabled(False)
        self.tabel_data.setRowCount(len(b))
        for r, x in enumerate(b):
            self.tabel_data.setItem(r, 0, kit.sel(x.get("smiles", "")))
            self.tabel_data.setItem(r, 1, kit.sel(x.get("nama", "")))
            self.tabel_data.setItem(r, 2, kit.sel_angka(x.get("pic50")))
            self.tabel_data.setItem(r, 3, kit.sel(x.get("galat", "")))
        self.tabel_data.setSortingEnabled(True)
        self.l_status.setText("")

    # ---------------------------------------------------------------- 2. kurasi
    def _halaman_kurasi(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(kit.catatan(
            "Struktur distandarkan (fragmen terbesar, netralisasi), pengukuran ganda digabung sebagai median, "
            "dan senyawa bermasalah ditandai. Centang baris yang ingin dibuang sebelum melatih model.", "muted"))
        self.l_kurasi = QLabel("")
        self.l_kurasi.setWordWrap(True)
        v.addWidget(self.l_kurasi)

        h = QHBoxLayout()
        self.tabel_peringatan = kit.tabel(["Buang", "Jenis", "Senyawa", "Catatan"], regang=3, urut=False)
        h.addWidget(self.tabel_peringatan, 3)
        self.svg_histogram = kit.GambarSvg()
        self.svg_histogram.setMinimumWidth(380)
        h.addWidget(self.svg_histogram, 2)
        v.addLayout(h, 1)
        return w

    def _jalankan_kurasi(self):
        """Kurasi di thread latar: pencarian activity cliff membandingkan semua pasangan, lambat pada ratusan senyawa."""
        if not self.baris_mentah:
            return
        self._mulai_sibuk("Membakukan struktur dan mencari activity cliff…")
        baris = self.baris_mentah
        kerja.jalankan(lambda lapor=None: qsar.kurasi(baris), selesai=self._kurasi_selesai, galat=self._galat)

    def _kurasi_selesai(self, hasil):
        self._selesai_sibuk()
        self.hasil_kurasi = hasil
        self.data = self.hasil_kurasi["data"]
        d, buang, per = self.data, self.hasil_kurasi["dibuang"], self.hasil_kurasi["peringatan"]
        ganda = sum(1 for x in d if x["n_ukur"] > 1)
        self.l_kurasi.setText(
            f"{len(d)} senyawa unik; {ganda} punya lebih dari satu pengukuran (digabung median); "
            f"{len(buang)} baris dibuang; {len(per)} peringatan.")
        self.tabel_peringatan.setRowCount(len(per))
        for r, p in enumerate(per):
            c = QCheckBox()
            self.tabel_peringatan.setCellWidget(r, 0, c)
            self.tabel_peringatan.setItem(r, 1, kit.sel("Rentang besar" if p["jenis"] == "rentang" else "Activity cliff"))
            self.tabel_peringatan.setItem(r, 2, kit.sel(p.get("nama") or p["smiles"][:40]))
            self.tabel_peringatan.setItem(r, 3, kit.sel(p["pesan"]))
            self.tabel_peringatan.item(r, 2).setData(Qt.UserRole, p["smiles"])
        if d:
            nilai = [x["pic50"] for x in d]
            self.svg_histogram.atur_pembuat(
                lambda l, t: grafik.histogram(nilai, label_x="pIC50", judul="Sebaran pIC50",
                                              gelap=kit.mode() == "gelap", lebar=l, tinggi=t))

    def _buang_tercentang(self):
        buang = set()
        for r in range(self.tabel_peringatan.rowCount()):
            c = self.tabel_peringatan.cellWidget(r, 0)
            if c and c.isChecked():
                it = self.tabel_peringatan.item(r, 2)
                if it:
                    buang.add(it.data(Qt.UserRole))
        if buang:
            self.data = [x for x in self.data if x["smiles"] not in buang]
            self.l_status.setText(f"{len(buang)} senyawa dibuang atas permintaan; tersisa {len(self.data)}.")

    # ----------------------------------------------------------------- 3. model
    def _halaman_model(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        g = QGroupBox("Pengaturan model")
        gl = QHBoxLayout(g)

        kol1 = QVBoxLayout()
        kol1.addWidget(QLabel("Jenis tugas:"))
        self.cb_tugas = QComboBox()
        self.cb_tugas.addItem("Regresi (pIC50)", False)
        self.cb_tugas.addItem("Klasifikasi (aktif / tidak)", True)
        self.cb_tugas.currentIndexChanged.connect(self._perbarui_ambang)
        kol1.addWidget(self.cb_tugas)
        kol1.addWidget(QLabel("Ambang aktif (pIC50):"))
        self.sp_ambang = QDoubleSpinBox()
        self.sp_ambang.setRange(0.0, 15.0)
        self.sp_ambang.setSingleStep(0.5)
        self.sp_ambang.setValue(qsar.AMBANG_AKTIF)
        self.sp_ambang.setEnabled(False)
        kol1.addWidget(self.sp_ambang)
        kol1.addStretch(1)
        gl.addLayout(kol1)

        kol2 = QVBoxLayout()
        kol2.addWidget(QLabel("Fitur:"))
        self.cb_fitur = QComboBox()
        for k, n in qsar.FITUR.items():
            self.cb_fitur.addItem(n, k)
        kol2.addWidget(self.cb_fitur)
        kol2.addWidget(QLabel("Algoritma:"))
        self.cb_alg = QComboBox()
        for k, n in qsar.ALGORITMA.items():
            self.cb_alg.addItem(n, k)
        kol2.addWidget(self.cb_alg)
        kol2.addStretch(1)
        gl.addLayout(kol2)

        kol3 = QVBoxLayout()
        kol3.addWidget(QLabel("Pembagian data:"))
        self.chk_acak = QCheckBox("Acak")
        self.chk_acak.setChecked(True)
        self.chk_kerangka = QCheckBox("Kerangka Bemis-Murcko")
        self.chk_kerangka.setChecked(True)
        self.chk_kerangka.setToolTip("Pembagian kerangka menguji kemampuan model pada kerangka kimia yang belum pernah dilihat")
        kol3.addWidget(self.chk_acak)
        kol3.addWidget(self.chk_kerangka)
        self.chk_yacak = QCheckBox("Y-randomization (50×)")
        self.chk_yacak.setChecked(True)
        self.chk_yacak.setToolTip("Melatih ulang dengan label diacak; model yang sahih harus jauh lebih baik daripada ini")
        kol3.addWidget(self.chk_yacak)
        kol3.addStretch(1)
        gl.addLayout(kol3)

        kol4 = QVBoxLayout()
        kol4.addWidget(QLabel("Benih acak:"))
        self.sp_benih = QSpinBox()
        self.sp_benih.setRange(0, 999999)
        self.sp_benih.setValue(42)
        kol4.addWidget(self.sp_benih)
        self.b_latih = kit.tombol("Latih model", self._latih, utama=True)
        kol4.addWidget(self.b_latih)
        kol4.addStretch(1)
        gl.addLayout(kol4)
        gl.addStretch(1)
        v.addWidget(g)

        self.l_latih = QLabel("")
        self.l_latih.setWordWrap(True)
        v.addWidget(self.l_latih)
        v.addStretch(1)
        return w

    def _mulai_sibuk(self, pesan: str):
        self._sibuk = True
        self.prog.setVisible(True)
        self.b_maju.setEnabled(False)
        self.b_mundur.setEnabled(False)
        self.l_status.setText(pesan)

    def _selesai_sibuk(self):
        self._sibuk = False
        self.prog.setVisible(False)
        self.b_maju.setEnabled(self.langkah < len(LANGKAH) - 1)
        self.b_mundur.setEnabled(self.langkah > 0)

    def _perbarui_ambang(self):
        self.sp_ambang.setEnabled(bool(self.cb_tugas.currentData()))

    def _latih(self):
        if len(self.data) < 20:
            self.l_status.setText(f"Data terlalu sedikit untuk melatih model ({len(self.data)} senyawa, minimal 20).")
            return
        if not (self.chk_acak.isChecked() or self.chk_kerangka.isChecked()):
            self.l_status.setText("Pilih setidaknya satu cara pembagian data.")
            return
        self.b_latih.setEnabled(False)
        self._mulai_sibuk("Melatih model…")
        opsi = {"alg": self.cb_alg.currentData(), "fitur": self.cb_fitur.currentData(),
                "klasifikasi": bool(self.cb_tugas.currentData()), "ambang": self.sp_ambang.value(),
                "benih": self.sp_benih.value(),
                "bagi": [m for m, c in (("acak", self.chk_acak), ("kerangka", self.chk_kerangka)) if c.isChecked()],
                "yacak": self.chk_yacak.isChecked()}

        def tugas(lapor=None):
            log = (lambda s: lapor.log.emit(s)) if lapor else (lambda s: None)
            hasil = {}
            for m in opsi["bagi"]:
                hasil[m] = qsar.latih(self.data, opsi["alg"], opsi["fitur"], m, klasifikasi=opsi["klasifikasi"],
                                      ambang_aktif=opsi["ambang"], benih=opsi["benih"], lapor=log)
            ya = {}
            if opsi["yacak"]:
                log("Y-randomization 50×…")
                ya = qsar.y_acak(self.data, opsi["alg"], opsi["fitur"], n=50, benih=opsi["benih"],
                                 klasifikasi=opsi["klasifikasi"], ambang_aktif=opsi["ambang"], lapor=log)
            return hasil, ya

        kerja.jalankan(tugas, selesai=self._latih_selesai, galat=self._galat, log=self.l_status.setText)

    def _latih_selesai(self, keluaran):
        hasil, ya = keluaran
        self._selesai_sibuk()
        self.b_latih.setEnabled(True)
        self.model_lain = hasil
        self.model = hasil.get("acak") or next(iter(hasil.values()))
        self._penting = None
        self.y_acak = ya
        self.l_latih.setText(f"Selesai: {len(hasil)} pembagian dilatih"
                             + (f", Y-randomization {ya['n']}×" if ya else "") + ".")
        self.l_status.setText("Model terlatih. Lanjut ke Validasi.")
        self._isi_validasi()

    def _galat(self, e):
        self._selesai_sibuk()
        self.b_latih.setEnabled(True)
        self.l_status.setText(str(e))

    # -------------------------------------------------------------- 4. validasi
    def _halaman_validasi(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        self.tabel_metrik = kit.tabel(["Pembagian", "n latih", "n uji", "Metrik internal", "Metrik set uji",
                                       "Golbraikh-Tropsha"], regang=4, urut=False)
        self.tabel_metrik.setMaximumHeight(96)
        v.addWidget(self.tabel_metrik)

        self.l_peringatan_val = QLabel("")
        self.l_peringatan_val.setWordWrap(True)
        v.addWidget(self.l_peringatan_val)

        h = QHBoxLayout()
        h.addWidget(QLabel("Grafik:"))
        self.cb_grafik = QComboBox()
        for n, k in (("Prediksi vs terukur", "sebar"), ("Williams (domain)", "williams"),
                     ("Y-randomization", "yacak"), ("Kepentingan fitur", "fitur")):
            self.cb_grafik.addItem(n, k)
        self.cb_grafik.currentIndexChanged.connect(self._gambar_validasi)
        h.addWidget(self.cb_grafik)
        h.addStretch(1)
        h.addWidget(kit.tombol("Kirim ke komposer", self._kirim_komposer))
        h.addWidget(kit.tombol("Salin paragraf metode", self._salin_metode))
        v.addLayout(h)

        self.svg_validasi = kit.GambarSvg()
        v.addWidget(self.svg_validasi, 1)
        return w

    def _isi_validasi(self):
        self.tabel_metrik.setRowCount(len(self.model_lain))
        tinggi = self.tabel_metrik.horizontalHeader().height() + 26 * len(self.model_lain) + 4
        self.tabel_metrik.setFixedHeight(tinggi)
        for r, (metode, h) in enumerate(self.model_lain.items()):
            i, e = h.get("internal", {}), h.get("eksternal", {})
            if h["klasifikasi"]:
                t_i = f"BA {kit.f(i.get('ba'))}, MCC {kit.f(i.get('mcc'))}"
                t_e = f"BA {kit.f(e.get('ba'))}, MCC {kit.f(e.get('mcc'))}" + (
                    f", ROC-AUC {kit.f(e.get('roc_auc'))}" if "roc_auc" in e else "")
                gt = "–"
            else:
                t_i = f"Q² {kit.f(i.get('q2'))}, RMSE {kit.f(i.get('rmse_cv'))}"
                t_e = f"R² {kit.f(e.get('r2'))}, RMSE {kit.f(e.get('rmse'))}, MAE {kit.f(e.get('mae'))}"
                g = h.get("golbraikh_tropsha") or {}
                gt = ("lulus" if g.get("lulus") else "tidak lulus") if g else "–"
            self.tabel_metrik.setItem(r, 0, kit.sel("Acak" if metode == "acak" else "Kerangka"))
            self.tabel_metrik.setItem(r, 1, kit.sel_angka(h["n_latih"], d=0))
            self.tabel_metrik.setItem(r, 2, kit.sel_angka(h["n_uji"], d=0))
            self.tabel_metrik.setItem(r, 3, kit.sel(t_i))
            self.tabel_metrik.setItem(r, 4, kit.sel(t_e))
            self.tabel_metrik.setItem(r, 5, kit.sel(gt))

        pesan = []
        a, k = self.model_lain.get("acak"), self.model_lain.get("kerangka")
        if a and k and not a["klasifikasi"]:
            beda = a["eksternal"]["r2"] - k["eksternal"]["r2"]
            if beda > 0.2:
                pesan.append(f"R² pembagian kerangka {kit.f(k['eksternal']['r2'])} jauh di bawah pembagian acak "
                             f"{kit.f(a['eksternal']['r2'])}: model kemungkinan besar hanya mengenali kerangka yang "
                             "sudah dilihat, bukan hubungan struktur-aktivitas yang dapat dialihkan.")
        if self.y_acak and not self.model["klasifikasi"]:
            nyata = self.model["eksternal"]["r2"]
            if self.y_acak["maks"] >= nyata:
                pesan.append(f"Y-randomization mencapai R² {kit.f(self.y_acak['maks'])}, setara model sebenarnya "
                             f"({kit.f(nyata)}): model tidak dapat dibedakan dari korelasi kebetulan.")
        kon = self.model.get("konformal") or {}
        if kon.get("n_kalibrasi", 0) < 50 and kon.get("cakupan_uji") is not None:
            pesan.append(f"Set kalibrasi konformal hanya {kon['n_kalibrasi']} senyawa, sehingga lebar intervalnya "
                         "kasar; cakupan empiris dapat jauh dari taraf nominal.")
        self.l_peringatan_val.setText("  ".join(pesan))
        self.l_peringatan_val.setVisible(bool(pesan))
        self._gambar_validasi()

    def _gambar_validasi(self):
        """Pasang pembuat grafik; SVG digambar ulang mengikuti ukuran panel agar tidak teregang."""
        if not self.model:
            return
        jenis = self.cb_grafik.currentData()
        if jenis == "fitur" and self._penting is None:
            # permutasi pada ribuan fitur makan puluhan detik: hitung di thread latar, sekali saja per model
            self.svg_validasi.atur_pembuat(None)
            self._mulai_sibuk("Menghitung kepentingan fitur (permutasi)…")
            model, data = self.model, self.data
            kerja.jalankan(lambda lapor=None: qsar.kepentingan_permutasi(model, data, n_ulang=3, n_teratas=15),
                           selesai=self._penting_selesai, galat=self._galat)
            return
        pembuat = self._pembuat_grafik(jenis)
        self.svg_validasi.atur_pembuat(pembuat)

    def _pembuat_grafik(self, jenis):
        """Kembalikan fn(lebar, tinggi) -> SVG untuk grafik terpilih, atau None bila datanya belum ada."""
        gelap = kit.mode() == "gelap"
        pred = self.model.get("prediksi_uji") or []
        d = self.model.get("domain") or {}
        if jenis == "sebar" and pred:
            x = [p["y"] for p in pred]
            y = [p["p"] for p in pred]
            nama = [p["nama"] or p["smiles"][:24] for p in pred]
            return lambda l, t: grafik.sebar(
                x, y, nama=nama, label_x="pIC50 terukur", label_y="pIC50 prediksi",
                judul="Set uji: prediksi vs terukur", gelap=gelap, lebar=l, tinggi=t, diagonal=True,
                catatan="Garis putus-putus = prediksi sempurna; jarak tegak titik ke garis itu adalah galat prediksi.")
        if jenis == "williams":
            if not pred:
                self.l_status.setText("Plot domain hanya tersedia untuk model regresi.")
                return None
            sisa = [(p["y"] - p["p"]) for p in pred]
            nama = [p["nama"] or p["smiles"][:24] for p in pred]
            sd = (sum(v * v for v in sisa) / len(sisa)) ** 0.5 if sisa else 0.0
            garis_y = [(3 * sd, "+3 RMSE"), (-3 * sd, "−3 RMSE")] if sd else []
            if d.get("leverage"):
                h = list(d["leverage"])
                return lambda l, t: grafik.sebar(
                    h, sisa, nama=nama, label_x="Leverage (h)", label_y="Residu (terukur − prediksi)",
                    judul="Plot Williams", gelap=gelap, lebar=l, tinggi=t,
                    garis_x=[(d["h_bintang"], f"h* = {kit.f(d['h_bintang'], 3)}")], garis_y=garis_y,
                    catatan="Titik di kanan h* berada di luar domain; titik di luar garis ±3 RMSE adalah pencilan "
                            "prediksi.")
            tan = list(d.get("tanimoto") or [])
            return lambda l, t: grafik.sebar(
                tan, sisa, nama=nama, label_x="Kemiripan Tanimoto ke 5 tetangga terdekat set latih",
                label_y="Residu (terukur − prediksi)", judul="Domain aplikabilitas", gelap=gelap, lebar=l, tinggi=t,
                garis_y=garis_y, garis_x=[(d.get("ambang_tanimoto", 0), f"ambang {kit.f(d.get('ambang_tanimoto'))}")],
                catatan="Leverage tidak dapat dihitung karena jumlah fitur melebihi jumlah senyawa, sehingga domain "
                        "dinilai dari kemiripan struktur. Titik di kiri garis ambang berada di luar domain.")
        if jenis == "yacak" and self.y_acak:
            skor = list(self.y_acak["skor"])
            klas = self.model["klasifikasi"]
            nyata = kit.f(self.model["eksternal"].get("ba" if klas else "r2"))
            return lambda l, t: grafik.histogram(
                skor, label_x="Akurasi seimbang (label diacak)" if klas else "R² (label diacak)",
                judul="Y-randomization", gelap=gelap, lebar=l, tinggi=t, catatan=f"Model sebenarnya: {nyata}")
        if jenis == "fitur" and self._penting:
            label = [p.get("label") or p["fitur"] for p in self._penting]
            nilai = [p["rata"] for p in self._penting]
            # batang horizontal: tinggi minimumnya ditentukan jumlah batang, tetapi panel yang lebih tinggi diisi penuh
            return lambda l, t: grafik.batang(
                label, nilai, label_x="Penurunan skor saat fitur diacak", judul="Kepentingan fitur (permutasi)",
                gelap=gelap, lebar=l, tinggi=max(t, 70 + 22 * len(label) + 44),
                catatan="Bit Morgan ditulis bersama contoh substruktur yang menyalakannya.")
        if jenis == "fitur":
            self.l_status.setText("Tidak ada fitur dengan kepentingan positif pada set uji.")
        return None

    def _penting_selesai(self, penting):
        self._selesai_sibuk()
        self._penting = penting or []
        self.l_status.setText(f"Kepentingan fitur: {len(self._penting)} fitur dengan kontribusi positif.")
        self._gambar_validasi()

    def _salin_metode(self):
        if not self.model:
            self.l_status.setText("Latih model dulu.")
            return
        teks = qsar.susun_paragraf_metode(self.model, self.data, self.sumber_data, self.y_acak or None)
        kit.salin(teks, status=self.l_status, pesan="Paragraf metode QSAR disalin ke papan klip.")

    def _kirim_komposer(self):
        if not self.model:
            self.l_status.setText("Belum ada grafik untuk dikirim.")
            return
        nama = self.cb_grafik.currentText()
        pembuat = self._pembuat_grafik(self.cb_grafik.currentData())
        svg = pembuat(1100, 720) if pembuat else ""
        if not svg:
            self.l_status.setText("Grafik ini belum dapat dikirim ke komposer.")
            return
        if not getattr(self.jw, "komposer", None):
            self.jw.buka_komposer()
        self.jw.komposer.tambah({"nama": f"QSAR · {nama}", "jenis": "svg", "isi": svg, "w": 1100, "h": 720})
        self.l_status.setText("Grafik ditambahkan ke Komposer Figur.")

    # -------------------------------------------------------------- 5. prediksi
    def _halaman_prediksi(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(kit.catatan(
            "Prediksi untuk ligan proyek. Senyawa di luar domain aplikabilitas ditandai: angkanya tetap ditampilkan "
            "tetapi tidak boleh ditafsirkan sebagai nilai kuantitatif.", "muted"))
        h = QHBoxLayout()
        h.addWidget(kit.tombol("Prediksi ligan proyek", self._prediksi_ligan, utama=True))
        h.addWidget(kit.tombol("Tulis ke panel Hasil", self._ke_panel_hasil))
        h.addWidget(kit.tombol("Simpan model…", self._simpan_model))
        h.addWidget(kit.tombol("Ekspor CSV…", self._ekspor_csv))
        h.addStretch(1)
        v.addLayout(h)
        # Peringatan cakupan domain: muncul hanya setelah prediksi, bila banyak senyawa di luar domain.
        self.l_domain = kit.catatan("", "peringatan")
        self.l_domain.setMinimumHeight(3 * self.l_domain.fontMetrics().lineSpacing() + 4)
        self.l_domain.setAlignment(Qt.AlignTop)
        self.l_domain.setVisible(False)
        v.addWidget(self.l_domain)
        self.tabel_prediksi = kit.tabel(["Ligan", "pIC50 prediksi", "Interval 90 %", "Kemiripan kNN", "Domain"],
                                        regang=0, urut=True)
        v.addWidget(self.tabel_prediksi, 1)
        return w

    def _ligan_proyek(self) -> List[Dict[str, Any]]:
        try:
            return kit.ligan_proyek(self.jw) if self.jw else []
        except Exception:
            return []

    def _prediksi_ligan(self):
        if not self.model:
            self.l_status.setText("Latih model dulu.")
            return
        ligan = self._ligan_proyek()
        if not ligan:
            self.l_status.setText("Proyek belum memuat ligan yang dapat diprediksi.")
            return
        self._ligan_prediksi = ligan
        self._mulai_sibuk(f"Memprediksi {len(ligan)} ligan proyek…")
        model, smiles = self.model, [lg["smiles"] for lg in ligan]
        kerja.jalankan(lambda lapor=None: qsar.prediksi(model, smiles),
                       selesai=self._prediksi_selesai, galat=self._galat)

    def _prediksi_selesai(self, prediksi):
        self._selesai_sibuk()
        self.prediksi = prediksi
        for p, lg in zip(self.prediksi, self._ligan_prediksi):
            p["nama"] = lg["nama"]
            p["kunci"] = lg.get("kunci")
        rd = qsar.ringkas_domain(self.prediksi)
        self.tabel_prediksi.setSortingEnabled(False)
        self.tabel_prediksi.setRowCount(len(self.prediksi))
        # Senyawa di dalam domain di atas (urut prediksi), senyawa di luar domain di bawah dan diredupkan: angkanya
        # tetap terlihat, tetapi tidak tampil seolah ikut peringkat.
        kunci_nilai = "peluang_aktif" if self.model["klasifikasi"] else "pic50"
        urut = sorted(self.prediksi, key=lambda p: (not p["dalam_domain"],
                                                   -(p.get(kunci_nilai) if p.get(kunci_nilai) is not None else 0)))
        redup = kit.warna("mut")
        for r, p in enumerate(urut):
            sel = [kit.sel(p["nama"])]
            if self.model["klasifikasi"]:
                sel += [kit.sel("aktif" if p["kelas"] else "tidak aktif"), kit.sel_angka(p.get("peluang_aktif"))]
            else:
                iv = (f"{kit.f(p['bawah'])} – {kit.f(p['atas'])}" if p.get("bawah") is not None else "–")
                sel += [kit.sel_angka(p["pic50"]), kit.sel(iv)]
            sel += [kit.sel_angka(p["tanimoto"]), kit.sel("di dalam" if p["dalam_domain"] else "di luar")]
            for c, it in enumerate(sel):
                if not p["dalam_domain"]:
                    it.setForeground(redup)
                    it.setToolTip(i18n.t("Di luar domain aplikabilitas: angka ini tidak boleh ditafsirkan atau "
                                         "diperingkat."))
                self.tabel_prediksi.setItem(r, c, it)
        # Tanpa ini, mengaktifkan kembali pengurutan menerapkan ulang kolom urut sebelumnya dan urutan di atas hilang.
        self.tabel_prediksi.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        self.tabel_prediksi.setSortingEnabled(True)
        n_luar = rd["n"] - rd["n_dalam"]
        self.l_status.setText(f"{len(self.prediksi)} ligan diprediksi; {n_luar} di luar domain aplikabilitas.")
        self._tampilkan_peringatan_domain(rd)

    def _tampilkan_peringatan_domain(self, rd):
        t = i18n.t
        persen = kit.f(100 * rd["fraksi"], 0)
        med = kit.f(rd["median_tanimoto"], 2) if rd["median_tanimoto"] is not None else "–"
        ambang = kit.f((self.model.get("domain") or {}).get("ambang_tanimoto"), 2)
        if rd["tingkat"] == "baik":
            self.l_domain.setVisible(False)
            return
        if rd["tingkat"] == "terbatas":
            teks = t(f"Hanya {rd['n_dalam']} dari {rd['n']} ligan ({persen} %) berada di dalam domain aplikabilitas. "
                     "Peringkatkan hanya senyawa di dalam domain (bagian atas tabel); senyawa yang diredupkan berada "
                     "di luar domain.")
            self.l_domain.setObjectName("info")
        else:
            teks = t(f"Model ini tidak cocok untuk seri ligan ini: {rd['n_dalam']} dari {rd['n']} ligan ({persen} %) "
                     f"berada di dalam domain aplikabilitas, dengan median kemiripan kNN {med} terhadap set latih "
                     f"(ambang {ambang}). Prediksinya tidak boleh dipakai untuk memeringkat atau memilih senyawa. "
                     "Latih model dari data yang kerangkanya mirip dengan seri ini.")
            self.l_domain.setObjectName("peringatan")
        self.l_domain.style().unpolish(self.l_domain)
        self.l_domain.style().polish(self.l_domain)
        self.l_domain.setText(teks)
        self.l_domain.setVisible(True)

    def _ke_panel_hasil(self):
        if not self.prediksi:
            self.l_status.setText("Jalankan prediksi dulu.")
            return
        panel = getattr(self.jw, "hasil", None)
        if panel is None or not hasattr(panel, "set_qsar"):
            self.l_status.setText("Panel Hasil tidak tersedia pada jendela ini.")
            return
        peta = {p["nama"]: p for p in self.prediksi}
        panel.set_qsar(peta, klasifikasi=self.model["klasifikasi"])
        rd = qsar.ringkas_domain(self.prediksi)
        if rd["tingkat"] == "tidak_cocok":
            self.l_status.setText(f"{len(peta)} prediksi ditulis ke kolom panel Hasil, tetapi hanya {rd['n_dalam']} "
                                  "yang berada di dalam domain; jangan dipakai untuk memeringkat ligan.")
        else:
            self.l_status.setText(f"{len(peta)} prediksi ditulis ke kolom panel Hasil.")

    def _simpan_model(self):
        if not self.model:
            self.l_status.setText("Latih model dulu.")
            return
        bawaan = str(self.proyek.p("model")) if self.proyek else ""
        path = QFileDialog.getExistingDirectory(self, "Pilih folder penyimpanan model", bawaan)
        if not path:
            return
        h = dict(self.model)
        h["y_acak"] = self.y_acak
        jalur = qsar.simpan(h, self.data, path, "model_qsar", self.sumber_data)
        self.l_status.setText(f"Model dan kartu model disimpan: {jalur['model'].name}, {jalur['kartu'].name}")

    def _ekspor_csv(self):
        if not self.prediksi:
            self.l_status.setText("Jalankan prediksi dulu.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan prediksi", "prediksi_qsar.csv", "CSV (*.csv)")
        if not path:
            return
        import csv
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if self.model["klasifikasi"]:
                w.writerow(["nama", "smiles", "kelas", "peluang_aktif", "tanimoto_knn", "dalam_domain"])
                for p in self.prediksi:
                    w.writerow([p["nama"], p["smiles"], p["kelas"], p.get("peluang_aktif"), p["tanimoto"],
                                int(p["dalam_domain"])])
            else:
                w.writerow(["nama", "smiles", "pic50_prediksi", "bawah_90", "atas_90", "tanimoto_knn", "dalam_domain"])
                for p in self.prediksi:
                    w.writerow([p["nama"], p["smiles"], p["pic50"], p.get("bawah"), p.get("atas"), p["tanimoto"],
                                int(p["dalam_domain"])])
        self.l_status.setText(f"Prediksi diekspor ke {Path(path).name}")

    # ----------------------------------------------------------- infrastruktur
    def _ke(self, n):
        if self._sibuk:
            return
        n = max(0, min(len(LANGKAH) - 1, n))
        if n == 1 and self.langkah == 0:
            if not self.baris_mentah:
                self.l_status.setText("Muat data lebih dulu.")
                return
            if not self.data:
                self._jalankan_kurasi()
        if n == 2 and self.langkah == 1:
            self._buang_tercentang()
        if n >= 3 and not self.model:
            self.l_status.setText("Latih model dulu di langkah Model.")
            return
        self.langkah = n
        self.tumpuk.setCurrentIndex(n)
        nama = [i18n.t(t) for t in LANGKAH]       # per langkah; teks gabungan tidak ada di kamus
        self.l_langkah.setText("  ›  ".join(f"<b>{i + 1}. {t}</b>" if i == n else f"{i + 1}. {t}"
                                            for i, t in enumerate(nama)))
        self.b_mundur.setEnabled(n > 0)
        self.b_maju.setEnabled(n < len(LANGKAH) - 1)
