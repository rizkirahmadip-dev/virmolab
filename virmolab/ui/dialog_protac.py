from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QTextEdit
)

from ..core import protac
from .. import i18n
from . import kit


class DialogPROTAC(QDialog):
    """Dialog interaktif perakitan dan evaluasi molekul PROTAC."""

    protacDiimpor = Signal(str, str)  # nama, smiles

    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.proyek = jw.proyek
        self.hasil_saat_ini = {}

        self.setWindowTitle("Perancang PROTAC")
        self.resize(720, 560)
        self._bangun_ui()
        self._perbarui_rakitan()

    def _bangun_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)

        # Header
        lbl_head = QLabel("Perancang Molekul PROTAC & Modalitas TPD")
        lbl_head.setObjectName("judulDialog")
        root.addWidget(lbl_head)

        lbl_desc = QLabel(
            "Rancang molekul chimera penarget degradasi protein: [Warhead Target] - [Linker] - [E3 Ligase Binder]. "
            "Evaluasi sifat fisiko-kimia Beyond Rule of 5 (bRo5), rentang linker spasial, dan impor langsung ke proyek."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setObjectName("subjudul")
        root.addWidget(lbl_desc)

        # Form Perakitan
        box_form = QGroupBox("Komposisi Bivalen")
        lyt_f = QVBoxLayout(box_form)

        # 1. Warhead
        lyt_w = QHBoxLayout()
        lyt_w.addWidget(QLabel("Warhead (Ligan Target):"))
        self.cmb_warhead = QComboBox()
        for l in kit.ligan_proyek(self.jw, dengan_mol=False):
            self.cmb_warhead.addItem(l["nama"], l["smiles"])
        else:
            self.cmb_warhead.addItem("Inhibitor Contoh (JQ1 analogue)", "Cc1c(sc2c1-c1ccc(Cl)cc1C(=NC2)C)C")
        self.cmb_warhead.currentIndexChanged.connect(self._perbarui_rakitan)
        lyt_w.addWidget(self.cmb_warhead)
        lyt_f.addLayout(lyt_w)

        # 2. E3 Binder
        lyt_e = QHBoxLayout()
        lyt_e.addWidget(QLabel("E3 Ligase Binder:"))
        self.cmb_e3 = QComboBox()
        for k, v in protac.daftar_e3_binders().items():
            self.cmb_e3.addItem(f"{v['nama']}", k)
        self.cmb_e3.currentIndexChanged.connect(self._perbarui_rakitan)
        lyt_e.addWidget(self.cmb_e3)
        lyt_f.addLayout(lyt_e)

        # 3. Linker
        lyt_l = QHBoxLayout()
        lyt_l.addWidget(QLabel("Jenis & Panjang Linker:"))
        self.cmb_linker = QComboBox()
        for k, v in protac.daftar_linkers().items():
            self.cmb_linker.addItem(f"{v['nama']} (~{v['panjang_est']} Å)", k)
        self.cmb_linker.currentIndexChanged.connect(self._perbarui_rakitan)
        lyt_l.addWidget(self.cmb_linker)
        lyt_f.addLayout(lyt_l)

        root.addWidget(box_form)

        # Hasil Analisis
        box_res = QGroupBox("Profil Fisikokimia bRo5 PROTAC")
        lyt_r = QVBoxLayout(box_res)

        self.lbl_status = QLabel("...")
        self.lbl_status.setObjectName("judulDialog")
        lyt_r.addWidget(self.lbl_status)

        self.txt_res = QTextEdit()
        self.txt_res.setReadOnly(True)
        self.txt_res.setFixedHeight(120)
        self.txt_res.setObjectName("mono")
        lyt_r.addWidget(self.txt_res)

        root.addWidget(box_res)

        # Tombol
        lyt_b = QHBoxLayout()

        btn_impor = QPushButton("Impor Molekul PROTAC ke Proyek")
        btn_impor.setObjectName("primary")
        btn_impor.clicked.connect(self._impor_ke_proyek)
        lyt_b.addWidget(btn_impor)

        lyt_b.addStretch()
        btn_tutup = QPushButton("✕ Tutup")
        btn_tutup.clicked.connect(self.close)
        lyt_b.addWidget(btn_tutup)

        root.addLayout(lyt_b)

    def _perbarui_rakitan(self):
        smi_w = self.cmb_warhead.currentData()
        if not smi_w:
            smi_w = "Cc1c(sc2c1-c1ccc(Cl)cc1C(=NC2)C)C"
        k_e3 = self.cmb_e3.currentData()
        k_l = self.cmb_linker.currentData()

        try:
            self.hasil_saat_ini = protac.rakit_protac(smi_w, kunci_e3=k_e3, kunci_linker=k_l)
            h = self.hasil_saat_ini
            self.lbl_status.setText(f"Status bRo5: {h['evaluasi_bro5']}")
            teks = (
                f"Massa molekul (MW)      : {kit.f(h['mw'], 1, 'Da')}\n"
                f"LogP (lipofilisitas)    : {kit.f(h['logp'])}\n"
                f"Luas permukaan polar    : {kit.f(h['tpsa'], 1, 'Å²')}\n"
                f"Donor / akseptor H      : {h['hbd']} HBD / {h['hba']} HBA\n"
                f"Ikatan berputar         : {h['n_rot']}\n"
                f"Bentangan linker        : {kit.f(h['panjang_linker_est'], 1, 'Å')} (rantai terentang penuh, bukan hasil pemodelan)\n"
                f"SMILES                  : {h['smiles']}"
            )
            self.txt_res.setPlainText(i18n.t_baris(teks))
        except Exception as e:
            self.txt_res.setPlainText(f"Gagal merakit PROTAC: {e}")

    def _impor_ke_proyek(self):
        if not self.hasil_saat_ini:
            return
        smi = self.hasil_saat_ini.get("smiles", "")
        if not smi:
            return
        nama = f"PROTAC_{self.cmb_e3.currentData()[:5]}_{self.cmb_linker.currentData()}"
        self.protacDiimpor.emit(nama, smi)
        self.lbl_status.setText(f"'{nama}' dikirim ke daftar objek. Konformasi 3D-nya hasil penyematan cepat; "
                                "perlu pencarian konformer sebelum dipakai untuk docking.")
