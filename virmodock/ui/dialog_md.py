"""Dialog MD & MM/GBSA (Analisis › MD & MM/GBSA…) - rencana A8a: aplikasi menilai kemampuan laptop dan menyarankan.

Tiga tingkat: Ringan (minimisasi + MM/GBSA), Sedang (MD pelarut implisit OBC2), Lengkap (MD air eksplisit TIP3P).
Kecepatan diukur otomatis pada kompleks pengguna sendiri (per perangkat & reseptor, disimpan) -> perkiraan waktu dan
status Disarankan / Bisa (lama) / Tidak disarankan. Perhitungan berjalan di proses terpisah (VirmoDock.exe --md),
bisa dijeda (checkpoint) dan dilanjutkan, juga setelah aplikasi dibuka ulang.
"""
import ctypes
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QRadioButton, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QToolButton, QVBoxLayout, QWidget)

from ..core import grafik, paths
from ..core.laporan import id_angka
from . import kit
from .panel_interaksi import KanvasSvg

TINGKAT = [("ringan", "Ringan", "Minimisasi kompleks + MM/GBSA satu titik (menit; semua laptop)"),
           ("sedang", "Sedang", "MD pelarut implisit (OBC2) + RMSD/RMSF + MM/GBSA rata-rata (puluhan menit-jam)"),
           ("lengkap", "Lengkap", "MD air eksplisit (TIP3P, PME) + MM/GBSA banyak frame (butuh GPU; standar publikasi)")]
# (label, token tema) — warnanya diambil saat dipakai supaya ikut mode gelap
STATUS = {"disarankan": ("Disarankan", "ok"), "bisa": ("Bisa (lama)", "warn"),
          "tidak": ("Tidak disarankan", "bad"), "": ("", "mut")}


def pakai_baterai():
    """True bila laptop berjalan dengan baterai (Windows GetSystemPowerStatus)."""
    if sys.platform != "win32":
        return False

    class SPS(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
    s = SPS()
    try:
        return bool(ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s))) and s.ACLineStatus == 0
    except Exception:
        return False


def _jam(j):
    if j < 1 / 60:
        return "< 1 mnt"
    if j < 1:
        return f"± {max(1, round(j * 60))} mnt"
    return f"± {int(j)} j {round((j - int(j)) * 60)} mnt"


class DialogMD(QDialog):
    selesai = Signal(dict, dict)          # (hasil.json, catatan proses)

    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.proyek_awal = jw.proyek
        self.setWindowTitle("MD & MM/GBSA - OpenMM")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1180, 820)
        self.proses = None
        self.run = None              # {id, folder, mode, tugas, ligan}
        self.kecepatan = None        # {platform, implisit, eksplisit, atom_i, atom_e}
        self._buf = ""
        lay = QVBoxLayout(self)
        lay.addWidget(kit.judul(
            "Dinamika molekul dan MM/GBSA",
            "Penyempurnaan pasca-docking: kompleks diminimisasi atau disimulasikan dengan OpenMM (protein "
            "Amber ff14SB, ligan OpenFF Sage 2.3 dengan muatan NAGL setara AM1-BCC). ΔG MM/GBSA berguna untuk "
            "membandingkan ligan secara relatif (entropi tidak dihitung), bukan sebagai afinitas absolut."))
        bagi = QSplitter(Qt.Horizontal)
        # ---- kiri: ligan + tingkat + opsi
        kiri = QWidget()
        vk = QVBoxLayout(kiri)
        vk.setContentsMargins(0, 0, 0, 0)
        vk.addWidget(QLabel("<b>Ligan (pose terbaik tiap ligan)</b>"))
        self.tabel = QTableWidget(0, 4)
        self.tabel.setHorizontalHeaderLabels(["Ligan", "ΔG docking", "MM/GBSA", "Job"])
        self.tabel.verticalHeader().setVisible(False)
        self.tabel.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabel.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabel.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabel.itemChanged.connect(lambda *_: self._perkiraan())
        vk.addWidget(self.tabel, 1)
        hp = QHBoxLayout()
        for t, n in (("Pilih 5 teratas", 5), ("Pilih semua", -1), ("Kosongkan", 0)):
            b = QToolButton()
            b.setText(t)
            b.clicked.connect(lambda _=False, n=n: self._pilih(n))
            hp.addWidget(b)
        hp.addStretch(1)
        vk.addLayout(hp)
        vk.addWidget(QLabel("<b>Tingkat</b>"))
        g = QGridLayout()
        self.grp = QButtonGroup(self)
        self.l_est, self.l_stat = {}, {}
        for i, (k, nama, des) in enumerate(TINGKAT):
            r = QRadioButton(nama)
            r.setToolTip(des)
            self.grp.addButton(r, i)
            g.addWidget(r, i * 2, 0)
            self.l_stat[k] = QLabel()
            g.addWidget(self.l_stat[k], i * 2, 1)
            self.l_est[k] = QLabel()
            self.l_est[k].setObjectName("mono")
            g.addWidget(self.l_est[k], i * 2, 2)
            d = QLabel(des)
            d.setObjectName("muted")
            d.setWordWrap(True)
            g.addWidget(d, i * 2 + 1, 0, 1, 3)
        g.setColumnStretch(2, 1)
        self.grp.idToggled.connect(lambda *_: self._perkiraan())
        vk.addLayout(g)
        f = QFormLayout()
        self.sp_ns_i = QDoubleSpinBox()
        self.sp_ns_i.setRange(0.1, 100)
        self.sp_ns_i.setValue(2.0)
        self.sp_ns_i.setSuffix(" ns")
        self.sp_ns_e = QDoubleSpinBox()
        self.sp_ns_e.setRange(0.1, 1000)
        self.sp_ns_e.setValue(10.0)
        self.sp_ns_e.setSuffix(" ns")
        self.sp_interval = QDoubleSpinBox()
        self.sp_interval.setRange(1, 1000)
        self.sp_interval.setValue(10)
        self.sp_interval.setSuffix(" ps")
        self.sp_frame = QSpinBox()
        self.sp_frame.setRange(5, 500)
        self.sp_frame.setValue(25)
        self.cb_plat = QComboBox()
        for t, v in (("Otomatis (GPU bila ada)", "auto"), ("CPU", "CPU")):
            self.cb_plat.addItem(t, v)
        for w in (self.sp_ns_i, self.sp_ns_e):
            w.valueChanged.connect(lambda *_: self._perkiraan())
        f.addRow("Lama MD (Sedang)", self.sp_ns_i)
        f.addRow("Lama MD (Lengkap)", self.sp_ns_e)
        f.addRow("Simpan frame tiap", self.sp_interval)
        f.addRow("Frame MM/GBSA", self.sp_frame)
        f.addRow("Perangkat", self.cb_plat)
        self.cb_plat.currentIndexChanged.connect(lambda *_: self._muat_kecepatan(ukur=True))
        vk.addLayout(f)
        hk = QHBoxLayout()
        self.l_kec = QLabel()
        self.l_kec.setWordWrap(True)
        self.l_kec.setObjectName("muted")
        hk.addWidget(self.l_kec, 1)
        self.b_ukur = QPushButton("Ukur kecepatan")
        self.b_ukur.setToolTip("Uji 10-30 detik pada kompleks ligan terpilih pertama (implisit & eksplisit)")
        self.b_ukur.clicked.connect(lambda: self._mulai("uji"))
        hk.addWidget(self.b_ukur)
        vk.addLayout(hk)
        self.l_baterai = QLabel()
        self.l_baterai.setWordWrap(True)
        self.l_baterai.setStyleSheet(f"color:{kit.hx('warn')};")
        vk.addWidget(self.l_baterai)
        bagi.addWidget(kiri)
        # ---- kanan: hasil
        self.tab = QTabWidget()
        self.t_hasil = QTableWidget(0, 8)
        self.t_hasil.setHorizontalHeaderLabels(["Ligan", "ΔG docking", "MM/GBSA min", "MM/GBSA MD", "SD", "ΔE vdW",
                                                "Elek + GB", "RMSD ligan"])
        for c, tip in ((2, "ΔG MM/GBSA setelah minimisasi kompleks (kcal/mol)"),
                       (3, "Rerata ΔG MM/GBSA atas frame MD (kcal/mol)"), (4, "Simpangan baku antar-frame"),
                       (5, "Komponen van der Waals"), (6, "ΔE elektrostatik + ΔG solvasi polar (GB) - sering saling "
                                                         "mengimbangi"),
                       (7, "Rerata RMSD atom berat ligan selama MD (Å); > 3 Å = pose tidak stabil")):
            self.t_hasil.horizontalHeaderItem(c).setToolTip(tip)
        self.t_hasil.horizontalHeader().setMinimumSectionSize(70)
        self.t_hasil.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.t_hasil.verticalHeader().setVisible(False)
        self.t_hasil.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t_hasil.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.t_hasil.currentCellChanged.connect(lambda r, *_: self._grafik_ligan(r))
        self.tab.addTab(self.t_hasil, "Ringkasan")
        self.k = {}
        for kunci, judul in (("rmsd", "RMSD"), ("rmsf", "RMSF"), ("energi", "MM/GBSA per waktu")):
            self.k[kunci] = KanvasSvg()
            self.tab.addTab(self.k[kunci], judul)
        self.t_inter = QTableWidget(0, 2)
        self.t_inter.setHorizontalHeaderLabels(["Interaksi (residu | jenis)", "Frekuensi"])
        self.t_inter.verticalHeader().setVisible(False)
        self.t_inter.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tab.addTab(self.t_inter, "Interaksi persisten")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("mono")
        self.tab.addTab(self.log, "Log")
        bagi.addWidget(self.tab)
        bagi.setSizes([470, 710])
        lay.addWidget(bagi, 1)
        self.prog = QProgressBar()
        self.prog.setRange(0, 1000)
        self.prog.setTextVisible(False)
        lay.addWidget(self.prog)
        hb = QHBoxLayout()
        self.l_status = QLabel()
        self.l_status.setObjectName("muted")
        hb.addWidget(self.l_status, 1)
        self.b_jalan = QPushButton("Jalankan")
        self.b_jalan.setObjectName("primary")
        self.b_jalan.clicked.connect(lambda: self._mulai(None))
        self.b_jeda = QPushButton("⏸ Jeda")
        self.b_jeda.setToolTip("Simpan checkpoint lalu berhenti; bisa dilanjutkan kapan saja")
        self.b_jeda.clicked.connect(self.jeda)
        self.b_lanjut = QPushButton("Lanjutkan")
        self.b_lanjut.clicked.connect(self.lanjutkan)
        self.b_grafik = QPushButton("Simpan grafik…")
        self.b_grafik.clicked.connect(self._simpan_grafik)
        self.b_folder = QPushButton("Buka folder")
        self.b_folder.clicked.connect(self._buka_folder)
        b_tutup = QPushButton("✕ Tutup")
        b_tutup.clicked.connect(self.close)
        for b in (self.b_jalan, self.b_jeda, self.b_lanjut, self.b_grafik, self.b_folder, b_tutup):
            hb.addWidget(b)
        lay.addLayout(hb)
        self.hasil = None
        self.muat()

    # ------------------------------------------------------------- data
    def muat(self):
        from ..core import ekspor as eksmod
        pr = self.jw.proyek
        self.baris = eksmod.baris_hasil(pr) if pr else []
        self.tabel.blockSignals(True)
        self.tabel.setRowCount(0)
        for b in self.baris:
            r = self.tabel.rowCount()
            self.tabel.insertRow(r)
            it = QTableWidgetItem(b["ligan"])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if r < 5 else Qt.Unchecked)
            it.setData(Qt.UserRole, (b["job"], b["lid"]))
            self.tabel.setItem(r, 0, it)
            self.tabel.setItem(r, 1, QTableWidgetItem(id_angka(f"{b['energi']:.2f}")))
            self.tabel.setItem(r, 2, QTableWidgetItem(id_angka(f"{b['mmgbsa']:.2f}") if b.get("mmgbsa") is not None
                                                      else ""))
            self.tabel.setItem(r, 3, QTableWidgetItem(b["job"]))
        self.tabel.blockSignals(False)
        self.tabel.resizeColumnsToContents()
        if self.grp.checkedId() < 0:
            self.grp.button(0).setChecked(True)
        self.l_baterai.setText("Laptop memakai baterai - colok ke listrik untuk MD (simulasi panjang menguras baterai "
                               "dan bisa diperlambat mode hemat daya)." if pakai_baterai() else "")
        dijeda = next((r for r in reversed(pr.md) if r.get("status") == "dijeda"), None) if pr else None
        if dijeda and not self.proses:
            self.run = dict(dijeda)
            self.l_status.setText(f"MD {dijeda['id']} dijeda - klik Lanjutkan untuk meneruskan dari checkpoint.")
        terakhir = next((r for r in reversed(pr.md) if r.get("status") == "selesai"), None) if pr else None
        if terakhir and not self.hasil:
            f = pr.p(terakhir["folder"], "hasil.json")
            if f.exists():
                self.run = self.run or dict(terakhir)
                self._tampil_hasil(json.loads(f.read_text(encoding="utf-8")), pr.p(terakhir["folder"]))
        self._muat_kecepatan()
        self._tombol()

    def _segarkan_mmgbsa(self):
        """Perbarui kolom MM/GBSA tabel ligan setelah hasil diterapkan ke proyek (centang tidak berubah)."""
        from ..core import ekspor as eksmod
        nilai = {(b["job"], b["lid"]): b.get("mmgbsa") for b in eksmod.baris_hasil(self.jw.proyek)}
        for r in range(self.tabel.rowCount()):
            v = nilai.get(self.tabel.item(r, 0).data(Qt.UserRole))
            self.tabel.item(r, 2).setText(id_angka(f"{v:.2f}") if v is not None else "")
            self.baris[r]["mmgbsa"] = v

    def _pilih(self, n):
        for r in range(self.tabel.rowCount()):
            self.tabel.item(r, 0).setCheckState(Qt.Checked if n < 0 or r < n else Qt.Unchecked)

    def terpilih(self):
        out = []
        for r in range(self.tabel.rowCount()):
            it = self.tabel.item(r, 0)
            if it.checkState() == Qt.Checked:
                out.append(self.baris[r])
        return out

    def tingkat(self):
        return TINGKAT[max(0, self.grp.checkedId())][0]

    # ------------------------------------------------------------- kecepatan & saran
    def _kunci_kecepatan(self):
        pr = self.jw.proyek
        gpu = ""
        try:
            g = self.jw.env.gpu_utama
            gpu = g.nama if g else "CPU"
        except Exception:
            pass
        return f"{gpu}|{self.cb_plat.currentData()}|{(pr.reseptor or {}).get('pdbqt', '') if pr else ''}|{pr.folder if pr else ''}"

    def _muat_kecepatan(self, ukur=False):
        try:
            semua = json.loads(paths.settings().value("md/kecepatan", "{}") or "{}")
        except (TypeError, ValueError):
            semua = {}
        self.kecepatan = semua.get(self._kunci_kecepatan())
        if self.kecepatan:
            k = self.kecepatan
            atom = f"{k.get('atom_e', 0):,}".replace(",", ".")
            imp, eks = id_angka(f"{k['implisit']:.1f}"), id_angka(f"{k['eksplisit']:.1f}")
            self.l_kec.setText(f"Kecepatan terukur ({k['platform']}, kompleks ini): implisit {imp} ns/hari, "
                               f"eksplisit {eks} ns/hari ({atom} atom dengan air).")
        else:
            self.l_kec.setText("Kecepatan laptop belum diukur untuk perangkat & reseptor ini. Pengukuran otomatis "
                               "(±30 detik) saat dialog dibuka.")
            if (ukur or not getattr(self, "_sudah_ukur", False)) and self.terpilih() and not self.proses:
                self._sudah_ukur = True
                QTimer.singleShot(300, lambda: self._mulai("uji"))
        self._perkiraan()

    def _perkiraan(self):
        from ..core.md import saran
        n = max(1, len(self.terpilih()))
        k = self.kecepatan
        gpu = bool(k and k.get("platform") in ("CUDA", "OpenCL"))
        est = {"ringan": (n * (25 if gpu or not k else 60)) / 3600.0}
        st = {"ringan": "disarankan"}
        if k:
            for kunci, ns, kec in (("sedang", self.sp_ns_i.value(), k["implisit"]),
                                   ("lengkap", self.sp_ns_e.value(), k["eksplisit"])):
                s, jam = saran(kec, ns, n)
                est[kunci] = jam + n * (40 if kunci == "lengkap" else 25) / 3600.0
                st[kunci] = "disarankan" if est[kunci] < 2 else "bisa" if est[kunci] <= 12 else "tidak"
        for kunci, *_ in TINGKAT:
            t, tok = STATUS[st.get(kunci, "")]
            w = kit.hx(tok)
            self.l_stat[kunci].setText(f"<span style='color:{w}; font-weight:600'>{t}</span>" if t else "")
            self.l_est[kunci].setText(_jam(est[kunci]) if kunci in est else "belum diukur")
        if k and st.get("lengkap") == "tidak" and self.tingkat() == "lengkap":
            self.l_status.setText("Tingkat Lengkap diperkirakan > 12 jam di laptop ini - pilih Sedang, kurangi ns/ligan, "
                                  "atau jalankan di komputer ber-GPU.")

    # ------------------------------------------------------------- proses
    def _tombol(self):
        jalan = self.proses is not None
        self.b_jalan.setEnabled(not jalan)
        self.b_ukur.setEnabled(not jalan)
        self.b_jeda.setEnabled(jalan and bool(self.run) and self.run.get("mode") == "md")
        self.b_lanjut.setEnabled(not jalan and bool(self.run) and self.run.get("status") == "dijeda")
        self.b_folder.setEnabled(bool(self.run))

    def _item_ligan(self, b):
        from ..core import mesin as M
        pr = self.jw.proyek
        j = self.jw.pelaksana.cari(b["job"])
        l = next(x for x in j["ligan"] if x["id"] == b["lid"])
        pose = M.baca_hasil(j["mesin"], pr.p(l["keluaran"]))[0]
        return {"nama": b["ligan"], "lid": b["lid"], "job": b["job"], "peringkat": 1, "energi_docking": b["energi"],
                "pdbqt_masukan": str(pr.p(l["pdbqt"])), "pose_pdbqt": pose.pdbqt, "flex": pose.flex}

    def _mulai(self, mode):
        pr = self.jw.proyek
        if self.proses:
            return
        pilih = self.terpilih()
        if not pr or not pilih:
            self.l_status.setText("Pilih minimal satu ligan hasil docking.")
            return
        rec = pr.reseptor or {}
        sumber = rec.get("meeko") or rec.get("bersih")
        if not sumber or not pr.p(sumber).exists():
            QMessageBox.warning(self, "MD & MM/GBSA", "Berkas reseptor bersih tidak ditemukan. Siapkan ulang reseptor.")
            return
        mode = mode or ("mmgbsa" if self.tingkat() == "ringan" else "md")
        if mode != "uji" and self.jw.pelaksana.sibuk():
            if QMessageBox.question(self, "MD & MM/GBSA", "Docking sedang berjalan dan memakai GPU/CPU yang sama. "
                                    "Tetap jalankan bersamaan (keduanya melambat)?") != QMessageBox.Yes:
                return
        try:
            ligan = [self._item_ligan(b) for b in (pilih[:1] if mode == "uji" else pilih)]
        except Exception as e:
            QMessageBox.warning(self, "MD & MM/GBSA", f"Pose docking tidak terbaca: {e}")
            return
        if mode == "uji":
            rid = "uji_kecepatan"
            import shutil
            shutil.rmtree(pr.p("md", rid), ignore_errors=True)     # hasil ukur lama tidak boleh terbaca ulang
        else:
            # ID unik (dua proses dalam detik yang sama tidak boleh berbagi folder/hasil)
            dasar = datetime.now().strftime("MD%Y%m%d_%H%M%S")
            rid, k = dasar, 2
            while pr.p("md", rid).exists() or any(r.get("id") == rid for r in pr.md):
                rid, k = f"{dasar}_{k}", k + 1
        folder = pr.p("md", rid)
        folder.mkdir(parents=True, exist_ok=True)
        pelarut = "eksplisit" if self.tingkat() == "lengkap" else "implisit"
        opsi = {"pelarut": pelarut, "ns": self.sp_ns_e.value() if pelarut == "eksplisit" else self.sp_ns_i.value(),
                "interval_ps": self.sp_interval.value(), "frame_mmgbsa": self.sp_frame.value(),
                "platform": self.cb_plat.currentData()}
        tugas = {"mode": mode, "folder": str(folder), "ligan": ligan, "opsi": opsi,
                 "reseptor": {"pdb": str(pr.p(sumber)), "pdbqt": str(pr.p(rec["pdbqt"]))}}
        (folder / "tugas.json").write_text(json.dumps(tugas, ensure_ascii=False, indent=1), encoding="utf-8")
        self.run = {"id": rid, "folder": pr.rel(folder), "mode": mode, "tingkat": self.tingkat() if mode != "uji" else "",
                    "tanggal": datetime.now().isoformat(timespec="seconds"), "status": "berjalan", "opsi": opsi,
                    "ligan": [{"nama": x["nama"], "lid": x["lid"], "job": x["job"]} for x in ligan]}
        if mode != "uji":
            pr.md = [r for r in pr.md if r.get("id") != rid] + [dict(self.run)]
            self.jw.minta_simpan()
        self._proses(folder / "tugas.json")

    def lanjutkan(self):
        if not self.run or self.proses:
            return
        f = self.jw.proyek.p(self.run["folder"], "tugas.json")
        if not f.exists():
            self.l_status.setText("Berkas tugas MD tidak ditemukan.")
            return
        self.run["status"] = "berjalan"
        self._simpan_run()
        self._proses(f)

    def jeda(self):
        if self.proses and self.run:
            self.jw.proyek.p(self.run["folder"], "BERHENTI").write_text("1", encoding="utf-8")
            self.l_status.setText("Menyimpan checkpoint lalu menjeda…")
            self.b_jeda.setEnabled(False)

    def _proses(self, f_tugas):
        self.log.clear()
        self.prog.setValue(0)
        self.proses = QProcess(self)
        self.proses.setProcessChannelMode(QProcess.MergedChannels)
        self.proses.readyReadStandardOutput.connect(self._baca)
        self.proses.finished.connect(self._akhir)
        from PySide6.QtCore import QProcessEnvironment
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        self.proses.setProcessEnvironment(env)
        if getattr(sys, "frozen", False):
            prog, arg = str(paths.EXE_UTAMA), ["--md", str(f_tugas)]
        else:
            prog, arg = sys.executable, ["-m", "virmodock", "--md", str(f_tugas)]
            self.proses.setWorkingDirectory(str(paths.AKAR))
        self.t0 = time.time()
        self.proses.start(prog, arg)
        self.l_status.setText("Menyiapkan OpenMM…" if self.run["mode"] != "uji" else "Mengukur kecepatan laptop…")
        self.jw.log.tulis(f"MD/MM-GBSA dimulai: {self.run['id']} ({self.run['mode']})")
        self._tombol()

    def _baca(self):
        self._buf += bytes(self.proses.readAllStandardOutput()).decode("utf-8", "replace")
        *baris, self._buf = self._buf.split("\n")
        for b in baris:
            b = b.rstrip("\r")
            if b.startswith("PROGRES "):
                _, p, *t = b.split(" ", 2)
                try:
                    self.prog.setValue(int(float(p) * 10))
                except ValueError:
                    pass
                self.l_status.setText(t[0] if t else "")
            elif b.startswith("LOG "):
                self.log.appendPlainText(b[4:])
            elif b.strip() and "Warning" not in b and "warn(" not in b:
                self.log.appendPlainText(b)

    def _akhir(self, kode, _status):
        self.proses = None
        pr = self.jw.proyek
        folder = pr.p(self.run["folder"])
        f = folder / "hasil.json"
        h = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        if self.run["mode"] == "uji":
            L = (h.get("ligan") or [{}])[0]
            if L.get("uji_implisit") and L.get("uji_eksplisit"):
                try:
                    semua = json.loads(paths.settings().value("md/kecepatan", "{}") or "{}")
                except (TypeError, ValueError):
                    semua = {}
                semua[self._kunci_kecepatan()] = {
                    "platform": L["uji_implisit"]["platform"], "implisit": L["uji_implisit"]["ns_hari"],
                    "eksplisit": L["uji_eksplisit"]["ns_hari"], "atom_i": L["uji_implisit"]["atom"],
                    "atom_e": L["uji_eksplisit"]["atom"], "tanggal": datetime.now().isoformat(timespec="seconds")}
                paths.settings().setValue("md/kecepatan", json.dumps(semua))
                self.l_status.setText("Kecepatan laptop terukur.")
            else:
                self.l_status.setText(f"Uji kecepatan gagal: {L.get('galat') or f'kode {kode}'} - lihat tab Log.")
            self.run = next((r for r in reversed(pr.md) if r.get("status") in ("dijeda", "selesai")), None)
            self._muat_kecepatan()
            self._tombol()
            return
        if kode == 3 or h.get("dijeda"):
            self.run["status"] = "dijeda"
            self.l_status.setText("Dijeda - checkpoint tersimpan. Klik Lanjutkan kapan saja (juga setelah aplikasi "
                                  "dibuka ulang).")
        elif any(x.get("selesai") for x in h.get("ligan", [])):
            self.run["status"] = "selesai"
            gagal = [x for x in h["ligan"] if x.get("galat")]
            self.l_status.setText(f"Selesai dalam {(time.time() - self.t0) / 60:.1f} menit"
                                  + (f"; {len(gagal)} ligan gagal (lihat Log)" if gagal else "") + ".")
            self.selesai.emit(h, dict(self.run))
            self._tampil_hasil(h, folder)
            self._segarkan_mmgbsa()
        else:
            self.run["status"] = "gagal"
            g = next((x.get("galat") for x in h.get("ligan", []) if x.get("galat")), None)
            self.l_status.setText(f"Gagal: {g or f'proses berakhir dengan kode {kode}'} - lihat tab Log.")
            self.tab.setCurrentWidget(self.log)
        self._simpan_run()
        self.jw.log.tulis(f"MD/MM-GBSA {self.run['id']}: {self.run['status']}")
        self._tombol()

    def _simpan_run(self):
        pr = self.jw.proyek
        if not pr or not self.run or self.run.get("mode") == "uji":
            return
        pr.md = [r for r in pr.md if r.get("id") != self.run["id"]] + [dict(self.run)]
        self.jw.minta_simpan()

    def proses_berjalan(self):
        return self.proses is not None

    def hentikan_untuk_keluar(self, tunggu_ms=20000):
        """Dipanggil saat aplikasi ditutup: jeda dengan checkpoint (MD) atau hentikan (lainnya)."""
        if not self.proses:
            return
        if self.run and self.run.get("mode") == "md":
            self.jeda()
            if self.proses.waitForFinished(tunggu_ms):
                return
        self.proses.kill()
        self.proses.waitForFinished(3000)

    # ------------------------------------------------------------- hasil
    def _tampil_hasil(self, h, folder):
        self.hasil, self.folder_hasil = h, Path(folder)
        L = [x for x in h.get("ligan", []) if x.get("selesai")]
        self.t_hasil.setRowCount(0)
        for x in L:
            r = self.t_hasil.rowCount()
            self.t_hasil.insertRow(r)
            mn, md_ = x.get("mmgbsa_min") or {}, x.get("mmgbsa") or {}
            tr = x.get("trajektori") or {}
            rm = tr.get("rmsd_ligan") or []
            nilai = [x["nama"], x.get("energi_docking"), mn.get("dG"), md_.get("dG"), md_.get("sd"),
                     (md_ or mn).get("vdw"), ((md_ or mn).get("elek") or 0) + ((md_ or mn).get("gb") or 0) if (md_ or mn) else None,
                     sum(rm) / len(rm) if rm else None]
            for c, v in enumerate(nilai):
                t = v if isinstance(v, str) else ("" if v is None else id_angka(f"{v:.2f}"))
                it = QTableWidgetItem(t)
                if c:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    it.setData(Qt.UserRole, v)
                self.t_hasil.setItem(r, c, it)
            if rm and sum(rm) / len(rm) > 3.0:
                self.t_hasil.item(r, 7).setForeground(kit.warna("bad"))
                self.t_hasil.item(r, 7).setToolTip("RMSD rerata > 3 Å: pose tidak stabil selama MD")
        self.t_hasil.resizeColumnsToContents()
        if L:
            self.t_hasil.setCurrentCell(0, 0)
            self._grafik_ligan(0)
        self._tombol()

    def _ligan_hasil(self, r=None):
        L = [x for x in (self.hasil or {}).get("ligan", []) if x.get("selesai")]
        r = self.t_hasil.currentRow() if r is None else r
        return L[r] if 0 <= r < len(L) else None

    def _svg(self, kunci, x, gelap=False):
        tr = x.get("trajektori") or {}
        dt = (self.hasil.get("opsi") or {}).get("interval_ps", 10) / 1000.0
        if kunci == "rmsd":
            n = len(tr.get("rmsd_ligan") or [])
            t = [(i + 1) * dt for i in range(n)]
            return grafik.garis([("Ligan (berat)", t, tr.get("rmsd_ligan") or []), ("Protein Cα", t, tr.get("rmsd_ca") or [])],
                                "Waktu (ns)", "RMSD (Å)", f"RMSD - {x['nama']}", gelap=gelap, y_nol=True,
                                catatan="Superposisi pada Cα protein frame pertama produksi; RMSD > 3 Å = pose bergeser")
        if kunci == "rmsf":
            v = tr.get("rmsf") or []
            return grafik.garis([("Cα", list(range(1, len(v) + 1)), v)], "Residu (urutan)", "RMSF (Å)",
                                f"RMSF Cα - {x['nama']}", gelap=gelap, y_nol=True,
                                catatan=(f"Residu 1 = {tr['residu'][0]}, terakhir = {tr['residu'][-1]}" if tr.get("residu") else ""))
        e = x.get("mmgbsa_frame") or []
        acuan = [(x["mmgbsa"]["dG"], f"rerata {grafik.fmt(x['mmgbsa']['dG'])}")] if x.get("mmgbsa") else None
        return grafik.garis([("ΔG MM/GBSA", [f["t_ns"] for f in e], [f["dG"] for f in e])], "Waktu (ns)",
                            "ΔG MM/GBSA (kcal/mol)", f"MM/GBSA per frame - {x['nama']}", gelap=gelap, acuan=acuan,
                            catatan="OBC2 (igb 5), satu-trajektori, tanpa entropi")

    def _grafik_ligan(self, r):
        x = self._ligan_hasil(r)
        if not x:
            return
        g = getattr(self.jw, "mode", "terang") == "gelap"
        for kunci in self.k:
            self.k[kunci].latar = QColor("#14171c" if g else "#ffffff")
            self.k[kunci].set_svg(self._svg(kunci, x, g) if x.get("trajektori") or kunci == "energi" else "")
        self.t_inter.setRowCount(0)
        for k_, v in list((x.get("interaksi_frek") or {}).items())[:60]:
            r_ = self.t_inter.rowCount()
            self.t_inter.insertRow(r_)
            self.t_inter.setItem(r_, 0, QTableWidgetItem(k_.replace("|", "  |  ")))
            it = QTableWidgetItem(f"{v * 100:.0f} %")
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.t_inter.setItem(r_, 1, it)

    def _simpan_grafik(self):
        x = self._ligan_hasil()
        w = self.tab.currentWidget()
        kunci = next((k for k, v in self.k.items() if v is w), None)
        if not x or not kunci:
            self.l_status.setText("Pilih ligan di Ringkasan lalu buka tab RMSD, RMSF, atau MM/GBSA per waktu.")
            return
        s = self._svg(kunci, x)
        f = self.jw._path("Simpan grafik", f"{kunci}_{x['nama']}.svg", "SVG (*.svg);;PDF (*.pdf);;PNG (*.png);;TIFF (*.tif)")
        if f:
            ext = f.lower().rsplit(".", 1)[-1]
            self.jw._simpan_svg(s, f, {"pdf": "pdf", "png": "png", "tif": "tif", "tiff": "tif"}.get(ext, "svg"),
                                760, 480, mm=160, dpi=600)

    def _buka_folder(self):
        if self.run:
            os.startfile(str(self.jw.proyek.p(self.run["folder"])))

    def closeEvent(self, e):
        # proses tetap berjalan di latar; dialog dibuka lagi lewat menu yang sama
        e.accept()
