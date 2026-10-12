"""Dialog Prediksi Kinetika Pengikatan & Waktu Tinggal (Residence Time & k_off Estimator)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QSpinBox, QGroupBox, QComboBox, QTextEdit
)

from ..core import kinetika
from . import kit


def _ilmiah(v, d=2):
    """Angka besar/kecil dalam notasi ilmiah gaya Indonesia (mis. 2,76 × 10⁻⁶)."""
    from ..core.laporan import id_angka
    if v == 0:
        return "0"
    pangkat = int(f"{v:.{d}e}".split("e")[1])
    if -2 <= pangkat <= 4:
        return id_angka(f"{v:,.{d}f}".replace(",", " "))
    mantis = id_angka(f"{v / (10 ** pangkat):.{d}f}")
    naik = str(pangkat).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
    return f"{mantis} × 10{naik}"


class DialogKinetika(QDialog):
    """Dialog interaktif estimasi waktu tinggal obat (residence time)."""

    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.proyek = jw.proyek
        self.energi_awal, self.hb_awal, self.hf_awal, self.sumber = self._dari_pose()

        self.setWindowTitle("Kinetika & waktu tinggal")
        self.resize(650, 520)
        self._bangun_ui()
        self._hitung()

    def _dari_pose(self):
        """(ΔG, ikatan H terlindung, kontak hidrofobik, keterangan sumber) dari pose yang sedang dianalisis."""
        o = kit.pose_aktif(self.jw)
        a = getattr(self.jw, "_aktif_inter", None) or {}
        if o is None:
            return -9.0, 2, 12, "Belum ada pose aktif — angka di bawah contoh; buka pose di tab Hasil agar terisi."
        dg = o.info.get("energi")
        hb = sum(1 for x in a.get("daftar", []) if x.get("jenis") == "hbond")
        hf = sum(1 for x in a.get("daftar", []) if x.get("jenis") == "hidrofobik")
        nama = o.info.get("ligan", o.nama)
        return (float(dg) if dg is not None else -9.0), hb, hf,             f"Terisi dari pose aktif: {nama} · {o.nama} ({hb} ikatan H, {hf} kontak hidrofobik)."

    def _bangun_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)

        # Header
        lbl_head = QLabel("Estimator Kinetika Disosiasi & Waktu Tinggal (Residence Time)")
        lbl_head.setObjectName("judulDialog")
        root.addWidget(lbl_head)

        lbl_desc = QLabel(
            "Mengestimasi laju disosiasi k_off, residence time (tau), dan half-life (t_1/2) kompleks obat-target "
            "berdasarkan afinitas termodinamika, ikatan hidrogen terlindung dari pelarut, dan kontak hidrofobik."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setObjectName("subjudul")
        root.addWidget(lbl_desc)

        # Parameter Input
        box_param = QGroupBox("Parameter Pengikatan Kompleks")
        lyt_p = QVBoxLayout(box_param)

        lyt_1 = QHBoxLayout()
        lyt_1.addWidget(QLabel("Energi Docking ΔG (kcal/mol):"))
        self.spn_dg = QDoubleSpinBox()
        self.spn_dg.setRange(-20.0, -1.0)
        self.spn_dg.setSingleStep(0.2)
        self.spn_dg.setValue(self.energi_awal)
        self.spn_dg.valueChanged.connect(self._hitung)
        lyt_1.addWidget(self.spn_dg)
        lyt_p.addLayout(lyt_1)

        lyt_2 = QHBoxLayout()
        lyt_2.addWidget(QLabel("Ikatan Hidrogen Terkubur (Shielded H-Bonds):"))
        self.spn_hb = QSpinBox()
        self.spn_hb.setRange(0, 10)
        self.spn_hb.setValue(self.hb_awal)
        self.spn_hb.valueChanged.connect(self._hitung)
        lyt_2.addWidget(self.spn_hb)
        lyt_p.addLayout(lyt_2)

        lyt_3 = QHBoxLayout()
        lyt_3.addWidget(QLabel("Kontak Atom Hidrofobik Terkubur:"))
        self.spn_hphob = QSpinBox()
        self.spn_hphob.setRange(0, 35)
        self.spn_hphob.setValue(min(35, self.hf_awal))
        self.spn_hphob.valueChanged.connect(self._hitung)
        lyt_3.addWidget(self.spn_hphob)
        lyt_p.addLayout(lyt_3)

        root.addWidget(box_param)
        root.addWidget(kit.catatan(self.sumber))

        # Hasil Kinetik
        box_hasil = QGroupBox("Parameter Kinetika Terprediksi")
        lyt_h = QVBoxLayout(box_hasil)

        self.lbl_ringkas = QLabel("...")
        self.lbl_ringkas.setObjectName("judulDialog")
        lyt_h.addWidget(self.lbl_ringkas)

        self.txt_detail = QTextEdit()
        self.txt_detail.setReadOnly(True)
        self.txt_detail.setFixedHeight(130)
        self.txt_detail.setObjectName("mono")
        lyt_h.addWidget(self.txt_detail)

        root.addWidget(box_hasil)
        root.addWidget(kit.catatan(
            "Perkiraan kasar berbasis aturan: k_on ditebak dari jumlah ikatan berputar, k_off dari Kd lalu "
            "diperlambat oleh ikatan H terlindung dan kontak hidrofobik. Skor docking tidak memodelkan keadaan "
            "transisi, jadi waktu tinggal bisa meleset beberapa orde besaran. Pakailah untuk membandingkan "
            "ligan satu seri, bukan sebagai nilai k_off yang dikutip.", "peringatan"))

        # Tombol
        lyt_b = QHBoxLayout()
        btn_salin = QPushButton("Salin Parameter Kinetika")
        def _salin():
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText(self.txt_detail.toPlainText())
            self.lbl_ringkas.setText("Parameter kinetika berhasil disalin ke papan klip!")
        btn_salin.clicked.connect(_salin)
        lyt_b.addWidget(btn_salin)

        lyt_b.addStretch()
        btn_tutup = QPushButton("✕ Tutup")
        btn_tutup.clicked.connect(self.close)
        lyt_b.addWidget(btn_tutup)
        root.addLayout(lyt_b)

    def _hitung(self):
        hasil = kinetika.estimasi_kinetika(
            energi_vina=self.spn_dg.value(),
            jum_hbond_terkubur=self.spn_hb.value(),
            jum_kontak_hidrofobik=self.spn_hphob.value(),
        )

        self.lbl_ringkas.setText(
            f"Kategori: {hasil['kategori']}  |  Residence Time (τ): {hasil['tau_teks']}  |  t₁/₂: {hasil['t_setengah_teks']}"
        )

        teks = (
            f"• Kd Termodinamika     : {hasil['Kd_nM']:.2f} nM ({hasil['dG']} kcal/mol)\n"
            f"• Laju Asosiasi (k_on)  : {hasil['k_on']} M⁻¹ s⁻¹\n"
            f"• Laju Disosiasi (k_off): {hasil['k_off']} s⁻¹\n"
            f"• Waktu Tinggal (τ)    : {hasil['tau_detik']:.1f} detik (~ {hasil['tau_teks']})\n"
            f"• Waktu Paruh (t₁/₂)   : {hasil['t_setengah_detik']:.1f} detik (~ {hasil['t_setengah_teks']})\n\n"
            f"Wawasan PK/PD: {hasil['penjelasan']}"
        )
        self.txt_detail.setPlainText(teks)
