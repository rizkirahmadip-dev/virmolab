"""Dialog Ekspor video/animasi viewport (putar / goyang / zoom masuk): MP4 H.264 Full HD-4K, GIF, WebP,
atau folder PNG."""
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QSpinBox,
                               QVBoxLayout)

from ..core import animasi as AN
from ..core import paths
from .perekam_video import RESOLUSI, bitrate


class DialogAnimasi(QDialog):
    def __init__(self, parent, rasio):
        super().__init__(parent)
        self.setWindowTitle("Ekspor video / animasi 3D")
        self.rasio = rasio            # tinggi / lebar viewport (GIF/WebP/PNG mengikuti viewport)
        self.st = paths.settings()
        lay = QVBoxLayout(self)
        ket = QLabel("Merekam viewport seperti tampil sekarang (gaya, warna, label ikut) pada resolusi penuh - "
                     "setiap bingkai dirender ulang, bukan direkam dari layar. Atur pandangan dulu, lalu rekam.")
        ket.setWordWrap(True)
        ket.setObjectName("muted")
        lay.addWidget(ket)
        f = QFormLayout()
        self.c_jenis = QComboBox()
        for k, t in AN.JENIS.items():
            self.c_jenis.addItem(t, k)
        self.c_fmt = QComboBox()
        for k, t in AN.FORMAT.items():
            self.c_fmt.addItem(t, k)
        self.c_res = QComboBox()
        for k, (_w, _h, t) in RESOLUSI.items():
            self.c_res.addItem(t, k)
        self.s_durasi = QDoubleSpinBox()
        self.s_durasi.setRange(1, 60)
        self.s_durasi.setSuffix(" detik")
        self.s_durasi.setDecimals(1)
        self.c_fps = QComboBox()
        self.s_lebar = QSpinBox()
        self.s_lebar.setRange(320, 1920)
        self.s_lebar.setSingleStep(80)
        self.s_lebar.setSuffix(" px")
        self.c_latar = QComboBox()
        self.c_latar.addItem("Putih", "putih")
        self.c_latar.addItem("Mengikuti tema", "tema")
        self.c_latar.addItem("Hitam", "hitam")
        self.l_info = QLabel()
        self.l_info.setObjectName("muted")
        self.l_info.setWordWrap(True)
        f.addRow("Gerakan", self.c_jenis)
        f.addRow("Format", self.c_fmt)
        f.addRow("Resolusi", self.c_res)
        f.addRow("Lebar", self.s_lebar)
        f.addRow("Durasi", self.s_durasi)
        f.addRow("Kehalusan", self.c_fps)
        f.addRow("Latar", self.c_latar)
        f.addRow("", self.l_info)
        self.form = f
        lay.addLayout(f)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Rekam…")
        bb.button(QDialogButtonBox.Cancel).setText("Batal")
        bb.accepted.connect(self._simpan)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        d = self.st.value("animasi", {}) or {}
        d = d if isinstance(d, dict) else {}
        self.c_jenis.setCurrentIndex(max(0, self.c_jenis.findData(d.get("jenis", "putar"))))
        self.c_fmt.setCurrentIndex(max(0, self.c_fmt.findData(d.get("fmt", "mp4"))))
        self.c_res.setCurrentIndex(max(0, self.c_res.findData(d.get("resolusi", "fhd"))))
        self.s_durasi.setValue(float(d.get("durasi", 8)))
        self.s_lebar.setValue(int(d.get("lebar", 800)))
        self.c_latar.setCurrentIndex(max(0, self.c_latar.findData(d.get("latar", "putih"))))
        self._fps_awal = int(d.get("fps", 30))
        self._isi_fps()
        for w in (self.s_durasi, self.s_lebar):
            w.valueChanged.connect(self._info)
        for w in (self.c_fps, self.c_jenis, self.c_res):
            w.currentIndexChanged.connect(self._info)
        self.c_jenis.currentIndexChanged.connect(self._saran_durasi)
        self.c_fmt.currentIndexChanged.connect(self._isi_fps)

    def _saran_durasi(self, *_):
        # presentasi sinematik punya banyak babak: durasi pendek terasa terburu-buru
        if self.c_jenis.currentData() == "sinema" and self.s_durasi.value() < 16:
            self.s_durasi.setValue(22)

    def _isi_fps(self, *_):
        video = self.c_fmt.currentData() == "mp4"
        lama = self.c_fps.currentData() or self._fps_awal
        self.c_fps.blockSignals(True)
        self.c_fps.clear()
        for v in ((24, 30, 60) if video else (10, 15, 20, 25, 30)):
            self.c_fps.addItem(f"{v} bingkai/detik" + (" (sinematik)" if v == 24 else " (sangat halus)" if v == 60 else ""),
                               v)
        i = self.c_fps.findData(lama)
        self.c_fps.setCurrentIndex(i if i >= 0 else self.c_fps.findData(30 if video else 20))
        self.c_fps.blockSignals(False)
        self.form.setRowVisible(self.c_res, video)
        self.form.setRowVisible(self.s_lebar, not video)
        self.adjustSize()
        self._info()

    def data(self):
        return {"jenis": self.c_jenis.currentData(), "fmt": self.c_fmt.currentData(), "durasi": self.s_durasi.value(),
                "fps": self.c_fps.currentData(), "lebar": self.s_lebar.value(), "latar": self.c_latar.currentData(),
                "resolusi": self.c_res.currentData()}

    def _info(self, *_):
        d = self.data()
        if not d["fps"]:
            return
        n = max(2, round(d["durasi"] * d["fps"]))
        if d["fmt"] == "mp4":
            w, h = RESOLUSI[d["resolusi"]][:2]
            mbps = bitrate(w, h, d["fps"]) / 1e6
            mb = mbps * d["durasi"] / 8
            detik = n * (0.25 if w * h > 4e6 else 0.12)
            self.l_info.setText(f"{n} bingkai · {w} × {h} px · H.264 ± {mbps:.0f} Mbps · berkas ± {mb:.0f} MB · "
                                f"perekaman ± {max(5, detik):.0f} detik")
        else:
            tinggi = round(d["lebar"] * self.rasio)
            mb = n * d["lebar"] * tinggi * (0.35 if d["fmt"] == "gif" else 0.08 if d["fmt"] == "webp" else 1.2) / 1e6
            self.l_info.setText(f"{n} bingkai · {d['lebar']} × {tinggi} px · perkiraan ± {mb:.0f} MB")

    def _simpan(self):
        self.st.setValue("animasi", self.data())
        self.accept()
