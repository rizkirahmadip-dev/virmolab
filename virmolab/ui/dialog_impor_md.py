"""Dialog Berkas › Impor hasil eksternal › Trajektori MD…

Topologi + trajektori dari GROMACS, AMBER, NAMD/CHARMM, atau OpenMM dibaca di proses terpisah (crash pustaka
native tidak menjatuhkan aplikasi), diutuhkan dari efek kotak periodik, lalu dianalisis dengan pipa MD VirmoLab.
Hasilnya tersimpan sebagai hasil MD proyek dan dibuka di jendela analisis trajektori.
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QProgressBar, QRadioButton, QSpinBox, QVBoxLayout)

from ..core import impor_md as I
from ..core import paths
from ..core.laporan import id_angka
from . import kerja, kit

FILTER_TOP = ("Topologi (*.gro *.pdb *.ent *.prmtop *.parm7 *.psf *.cif *.mmcif);;GROMACS (*.gro *.pdb);;"
              "AMBER (*.prmtop *.parm7);;CHARMM/NAMD (*.psf);;Semua (*.*)")
FILTER_TRAJ = ("Trajektori (*.xtc *.trr *.dcd *.nc *.ncdf *.netcdf *.mdcrd *.crd *.pdb *.gro);;"
               "GROMACS (*.xtc *.trr);;NAMD/CHARMM/OpenMM (*.dcd);;AMBER (*.nc *.ncdf *.netcdf *.mdcrd *.crd);;"
               "Semua (*.*)")


def _ns(ps):
    return "–" if ps is None else id_angka(f"{ps / 1000:.3f}".rstrip("0").rstrip(".") or "0")


class DialogImporMD(QDialog):
    selesai = Signal(str)          # id run di proyek.md

    def __init__(self, jw, berkas=()):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Impor trajektori MD")
        self.setAcceptDrops(True)
        self.resize(860, 760)
        self.f_top = ""
        self.info_top = None          # {n_atom, calon, ringkas}
        self.info_traj = {}           # jalur -> info dict | galat str
        self.proses = None
        self._buf = ""
        self.folder = None
        self.rid = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul(
            "Impor trajektori dinamika molekul",
            "Trajektori GROMACS (XTC, TRR), AMBER (NetCDF, MDCRD), NAMD/CHARMM/OpenMM (DCD), atau PDB/GRO multi-frame "
            "dianalisis dengan pipa MD VirmoLab: RMSD, RMSF, Rg, SASA, ikatan H, okupansi interaksi, PCA, FEL, "
            "klaster ligan, dan pemutar 3D."))

        g = QGroupBox("Berkas")
        f = QFormLayout(g)
        h = QHBoxLayout()
        self.l_top = QLineEdit()
        self.l_top.setReadOnly(True)
        self.l_top.setPlaceholderText("GRO, PDB, PRMTOP, PSF, atau CIF dari simulasi yang sama")
        h.addWidget(self.l_top, 1)
        h.addWidget(kit.tombol("Pilih…", self._pilih_top))
        f.addRow("Topologi", h)
        self.l_info_top = kit.catatan("")
        f.addRow("", self.l_info_top)
        self.daftar = QListWidget()
        self.daftar.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.daftar.setMaximumHeight(130)
        f.addRow("Trajektori", self.daftar)
        h = QHBoxLayout()
        h.addWidget(kit.tombol("Tambah…", self._pilih_traj))
        h.addWidget(kit.tombol("Hapus", self._hapus_traj))
        h.addWidget(kit.tombol("Naik", lambda: self._geser(-1)))
        h.addWidget(kit.tombol("Turun", lambda: self._geser(1)))
        h.addStretch(1)
        f.addRow("", h)
        h = QHBoxLayout()
        self.r_sambung = QRadioButton("Bagian berurutan satu simulasi")
        self.r_replika = QRadioButton("Replika independen")
        self.r_sambung.setChecked(True)
        self.r_sambung.setToolTip("md.part0001.xtc, md.part0002.xtc, …: disambung menurut waktu; frame ulang di batas "
                                  "bagian dilewati")
        self.r_replika.setToolTip("Tiap berkas satu replika dengan topologi sama; hasil diringkas rerata ± SD")
        grp = QButtonGroup(self)
        for r in (self.r_sambung, self.r_replika):
            grp.addButton(r)
            h.addWidget(r)
        h.addStretch(1)
        f.addRow("Beberapa berkas", h)
        lay.addWidget(g)

        g = QGroupBox("Sistem")
        f = QFormLayout(g)
        self.cb_ligan = QComboBox()
        f.addRow("Ligan", self.cb_ligan)
        self.e_smiles = QLineEdit()
        self.e_smiles.setPlaceholderText("Opsional: SMILES ligan agar orde ikatan pasti (selain itu dari geometri)")
        f.addRow("Templat ligan", self.e_smiles)
        h = QHBoxLayout()
        self.c_pbc = QCheckBox("Perbaiki PBC")
        self.c_pbc.setChecked(True)
        self.c_pbc.setToolTip("Utuhkan molekul yang terpotong batas kotak dan hapus lompatan antarframe "
                              "(setara gmx trjconv -pbc mol lalu -pbc nojump). Aman untuk trajektori yang sudah "
                              "diproses.")
        self.c_ion = QCheckBox("Sertakan ion logam")
        self.c_ion.setChecked(True)
        self.c_ion.setToolTip("Zn, Mg, Ca, Fe, dll. Ion lawan Na⁺/Cl⁻/K⁺ dan air selalu dibuang")
        self.c_lipid = QCheckBox("Sertakan lipid membran")
        for w in (self.c_pbc, self.c_ion, self.c_lipid):
            h.addWidget(w)
        h.addStretch(1)
        f.addRow("", h)
        lay.addWidget(g)

        g = QGroupBox("Frame")
        f = QFormLayout(g)
        h = QHBoxLayout()
        self.sp_mulai = QDoubleSpinBox()
        self.sp_akhir = QDoubleSpinBox()
        for sp in (self.sp_mulai, self.sp_akhir):
            sp.setDecimals(3)
            sp.setRange(0, 1e6)
            sp.setSuffix(" ns")
        self.sp_akhir.setSpecialValueText("akhir")
        h.addWidget(QLabel("dari"))
        h.addWidget(self.sp_mulai)
        h.addWidget(QLabel("sampai"))
        h.addWidget(self.sp_akhir)
        h.addStretch(1)
        f.addRow("Rentang waktu", h)
        self.sp_maks = QSpinBox()
        self.sp_maks.setRange(20, 20000)
        self.sp_maks.setValue(1000)
        self.sp_maks.setSingleStep(100)
        self.sp_maks.setSuffix(" frame")
        self.sp_maks.setToolTip("Frame dicuplik merata bila trajektori lebih panjang. 500–2000 frame cukup untuk "
                                "RMSD/RMSF/PCA; FEL butuh ≥ 500 frame.")
        f.addRow("Maksimum dianalisis", self.sp_maks)
        self.sp_dt = QDoubleSpinBox()
        self.sp_dt.setRange(0, 1e6)
        self.sp_dt.setDecimals(3)
        self.sp_dt.setSuffix(" ps")
        self.sp_dt.setSpecialValueText("dari berkas")
        self.sp_dt.setToolTip("Isi hanya bila berkas tidak menyimpan waktu yang benar (mis. MDCRD, DCD tanpa "
                              "langkah waktu)")
        f.addRow("Jarak antarframe", self.sp_dt)
        self.e_nama = QLineEdit()
        f.addRow("Nama hasil", self.e_nama)
        lay.addWidget(g)

        self.l_ringkas = kit.catatan("", "info")
        lay.addWidget(self.l_ringkas)
        lay.addStretch(1)
        self.prog = QProgressBar()
        self.prog.setRange(0, 1000)
        self.prog.setTextVisible(False)
        self.prog.setFixedHeight(6)
        self.prog.setVisible(False)
        lay.addWidget(self.prog)
        self.l_status = kit.catatan("")
        self.b_jalan = kit.tombol("Analisis", self._jalankan, utama=True,
                                  tip="Baca trajektori dan hitung analisis MD di proses terpisah")
        self.b_batal = kit.tombol("Batalkan", self._batalkan)
        self.b_batal.setVisible(False)
        lay.addWidget(self.l_status)
        lay.addLayout(kit.bar_bawah(self, kanan=[self.b_batal, self.b_jalan]))
        self._segarkan()
        if berkas:
            self.tambah(berkas)

    # ------------------------------------------------------------ berkas
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.tambah([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    def _dir(self):
        return self.jw.st.value("dir_impor_md", self.jw.st.value("dir_terakhir", ""))

    def tambah(self, fs):
        """Pisahkan berkas topologi dan trajektori; topologi dicari otomatis bila hanya trajektori yang diberikan."""
        traj, top = [], []
        for f in fs:
            ext = Path(f).suffix.lower()
            if ext in I.EKSTENSI_TRAJEKTORI:
                traj.append(f)
            elif ext in I.EKSTENSI_TOPOLOGI:
                top.append(f)
        if top and not self.f_top:
            self._set_top(top[0])
            top = top[1:]
        # PDB/GRO tambahan (atau satu-satunya) dianggap trajektori multi-frame
        traj += [f for f in top if Path(f).suffix.lower() in I.EKSTENSI_TRAJEKTORI_TEKS]
        for f in traj:
            if not any(self.daftar.item(i).data(Qt.UserRole) == f for i in range(self.daftar.count())):
                it = QListWidgetItem(Path(f).name)
                it.setData(Qt.UserRole, f)
                it.setToolTip(f)
                self.daftar.addItem(it)
                self._info_traj(f)
        if traj and not self.e_nama.text():
            self.e_nama.setText(Path(traj[0]).stem)
        if fs:
            self.jw.st.setValue("dir_impor_md", str(Path(fs[0]).parent))
        self._segarkan()

    def _pilih_top(self):
        f, _ = QFileDialog.getOpenFileName(self, "Topologi", self._dir(), FILTER_TOP)
        if f:
            self.jw.st.setValue("dir_impor_md", str(Path(f).parent))
            self._set_top(f)

    def _pilih_traj(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Trajektori", self._dir(), FILTER_TRAJ)
        if fs:
            self.tambah(fs)

    def _hapus_traj(self):
        for it in self.daftar.selectedItems():
            self.info_traj.pop(it.data(Qt.UserRole), None)
            self.daftar.takeItem(self.daftar.row(it))
        self._segarkan()

    def _geser(self, d):
        r = self.daftar.currentRow()
        if r < 0 or not 0 <= r + d < self.daftar.count():
            return
        it = self.daftar.takeItem(r)
        self.daftar.insertItem(r + d, it)
        self.daftar.setCurrentRow(r + d)
        self._segarkan()

    def _set_top(self, f):
        self.f_top = f
        self.l_top.setText(f)
        self.info_top = None
        self.l_info_top.setText("Membaca topologi…")
        self._segarkan()

        def baca(lapor, f=f):
            tp = I.baca_topologi(f)
            kelas = I.kelas_atom(tp.top)
            calon = I.calon_ligan(tp.top, kelas)
            rantai = sum(1 for c in tp.top.chains() if any(I._kelas_residu(r.name, 2) == "protein"
                                                          for r in c.residues()))
            n_res = sum(1 for r in tp.top.residues() if I._kelas_residu(r.name, 2) == "protein")
            return {"n_atom": tp.n_atom, "calon": calon, "rantai": rantai, "residu": n_res,
                    "air": sum(1 for r in tp.top.residues() if I._kelas_residu(r.name, 3) == "air"),
                    "ion": kelas.count("ion_lawan") + kelas.count("ion"), "lipid": kelas.count("lipid"),
                    "kotak": tp.kotak is not None}

        def jadi(info, f=f):
            if f != self.f_top:
                return
            self.info_top = info
            bag = [f"{info['n_atom']:,} atom".replace(",", "."), f"{info['rantai']} rantai protein ({info['residu']} residu)"]
            if info["calon"]:
                bag.append(f"{len(info['calon'])} calon ligan")
            if info["air"]:
                bag.append(f"{info['air']:,} air".replace(",", "."))
            if info["ion"]:
                bag.append(f"{info['ion']} ion")
            if info["lipid"]:
                bag.append(f"{info['lipid']:,} atom lipid".replace(",", "."))
            self.l_info_top.setText(" · ".join(bag))
            self.cb_ligan.clear()
            for c in info["calon"]:
                self.cb_ligan.addItem(f"{c['label']} · {c['berat']} atom berat", c["kunci"])
            self.cb_ligan.addItem("Tanpa ligan (protein saja)", None)
            self.cb_ligan.setCurrentIndex(0)
            self.c_lipid.setEnabled(bool(info["lipid"]))
            for i in range(self.daftar.count()):
                self._info_traj(self.daftar.item(i).data(Qt.UserRole))
            self._segarkan()

        def gagal(e, f=f):
            if f == self.f_top:
                self.l_info_top.setText("Topologi tidak terbaca: " + e.strip().splitlines()[0])
                self._segarkan()
        kerja.jalankan(baca, selesai=jadi, galat=gagal)

    def _info_traj(self, f):
        n_top = (self.info_top or {}).get("n_atom")

        def baca(lapor, f=f, n=n_top):
            return I.info_trajektori(f, n)

        def jadi(info, f=f):
            self.info_traj[f] = info
            if not self.f_top:
                cocok = I.cari_topologi(f, info["atom"])
                if cocok:
                    self._set_top(cocok)
                    self.l_status.setText(f"Topologi dipilih otomatis: {Path(cocok).name} ({info['atom']} atom).")
            self._tulis_item(f)
            self._segarkan()

        def gagal(e, f=f):
            self.info_traj[f] = e.strip().splitlines()[0]
            self._tulis_item(f)
            self._segarkan()
        kerja.jalankan(baca, selesai=jadi, galat=gagal)

    def _tulis_item(self, f):
        for i in range(self.daftar.count()):
            it = self.daftar.item(i)
            if it.data(Qt.UserRole) != f:
                continue
            info = self.info_traj.get(f)
            if isinstance(info, str):
                it.setText(f"{Path(f).name}  ·  gagal: {info}")
                it.setForeground(kit.warna("bad"))
            elif info:
                n_top = (self.info_top or {}).get("n_atom")
                beda = n_top and info["atom"] != n_top
                it.setText(f"{Path(f).name}  ·  {info['format']}, {info['frame']} frame, {info['atom']} atom, "
                           f"{_ns(info['t0'])}–{_ns(info['t1'])} ns"
                           + (f", Δt {id_angka(format(info['dt'], 'g'))} ps" if info.get("dt") else "")
                           + (f"  ·  topologi {n_top} atom" if beda else ""))
                it.setForeground(kit.warna("warn" if beda else "ink"))

    # ------------------------------------------------------------ ringkasan
    def _berkas_traj(self):
        return [self.daftar.item(i).data(Qt.UserRole) for i in range(self.daftar.count())]

    def _segarkan(self):
        traj = self._berkas_traj()
        info = [self.info_traj.get(f) for f in traj]
        ok_info = [x for x in info if isinstance(x, dict)]
        n_top = (self.info_top or {}).get("n_atom")
        pesan = []
        if self.f_top and n_top and ok_info:
            beda = {x["atom"] for x in ok_info if x["atom"] != n_top}
            if beda:
                pesan.append(f"Trajektori berisi {', '.join(map(str, sorted(beda)))} atom, topologi {n_top}. "
                             "Bila trajektori ditulis untuk grup awal (mis. Protein_LIG tanpa air) atom pertama "
                             "dicocokkan; selain itu pakai topologi dari grup yang sama.")
        if ok_info:
            total = sum(x["frame"] for x in ok_info)
            t0 = min(x["t0"] for x in ok_info if x["t0"] is not None) if any(x["t0"] is not None for x in ok_info) else None
            t1 = max(x["t1"] for x in ok_info if x["t1"] is not None) if any(x["t1"] is not None for x in ok_info) else None
            pesan.insert(0, f"{len(ok_info)} berkas, {total:,} frame".replace(",", ".")
                         + (f", {_ns(t0)}–{_ns(t1)} ns" if t0 is not None and t1 is not None else "")
                         + f". Dianalisis paling banyak {self.sp_maks.value()} frame.")
            if any(not x.get("waktu_ada") and not x.get("dt") for x in ok_info):
                pesan.append("Sebagian berkas tidak menyimpan waktu: isi Jarak antarframe agar sumbu waktu benar.")
        self.l_ringkas.setText(" ".join(pesan) if pesan else
                               "GROMACS: pakai .gro atau .pdb dari simulasi yang sama sebagai topologi dan .xtc/.trr "
                               "sebagai trajektori. AMBER: .prmtop + .nc. NAMD/CHARMM: .psf + .dcd.")
        self.l_ringkas.setVisible(True)
        self.r_replika.setEnabled(len(traj) > 1)
        self.r_sambung.setEnabled(len(traj) > 1)
        jalan = self.proses is not None
        self.b_jalan.setEnabled(bool(self.f_top) and self.info_top is not None and bool(ok_info)
                                and len(ok_info) == len(traj) and not jalan)

    # ------------------------------------------------------------ proses
    def _opsi(self):
        akhir = self.sp_akhir.value()
        return {"nama": self.e_nama.text().strip() or Path(self._berkas_traj()[0]).stem,
                "mode": "replika" if self.r_replika.isChecked() and len(self._berkas_traj()) > 1 else "sambung",
                "ligan": self.cb_ligan.currentData(), "mulai_ps": self.sp_mulai.value() * 1000 or None,
                "akhir_ps": akhir * 1000 if akhir > 0 else None, "maks_frame": self.sp_maks.value(),
                "dt_ps": self.sp_dt.value() or None, "pbc": self.c_pbc.isChecked(),
                "ion_logam": self.c_ion.isChecked(), "lipid": self.c_lipid.isChecked(),
                "smiles": self.e_smiles.text().strip()}

    def _jalankan(self):
        pr = self.jw._pastikan_proyek()
        dasar = datetime.now().strftime("MDimpor%Y%m%d_%H%M%S")
        rid, k = dasar, 2
        while pr.p("md", rid).exists() or any(r.get("id") == rid for r in pr.md):
            rid, k = f"{dasar}_{k}", k + 1
        self.rid, self.folder = rid, pr.p("md", rid)
        self.folder.mkdir(parents=True, exist_ok=True)
        opsi = self._opsi()
        tugas = {"topologi": self.f_top, "trajektori": self._berkas_traj(), "folder": str(self.folder), "opsi": opsi}
        f_tugas = self.folder / "tugas_impor.json"
        f_tugas.write_text(json.dumps(tugas, ensure_ascii=False, indent=1), encoding="utf-8")
        self.proses = QProcess(self)
        self.proses.setProcessChannelMode(QProcess.MergedChannels)
        self.proses.readyReadStandardOutput.connect(self._baca)
        self.proses.finished.connect(self._akhir)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        self.proses.setProcessEnvironment(env)
        if getattr(sys, "frozen", False):
            prog, arg = str(paths.EXE_UTAMA), ["--impor-md", str(f_tugas)]
        else:
            prog, arg = sys.executable, ["-m", "virmolab", "--impor-md", str(f_tugas)]
            self.proses.setWorkingDirectory(str(paths.AKAR))
        self._galat = ""
        self.t0 = time.time()
        self.prog.setValue(0)
        self.prog.setVisible(True)
        self.b_batal.setVisible(True)
        self.l_status.setText("Memulai…")
        self.proses.start(prog, arg)
        self.jw.log.tulis(f"Impor trajektori MD dimulai: {opsi['nama']} → {self.folder}")
        self._segarkan()

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
                if t:
                    self.l_status.setText(t[0])
            elif b.startswith("GALAT "):
                self._galat = b[6:]

    def _batalkan(self):
        if self.proses:
            self.proses.kill()

    def _akhir(self, kode, _status):
        self.proses = None
        self.prog.setVisible(False)
        self.b_batal.setVisible(False)
        f = self.folder / "hasil.json" if self.folder else None
        if kode != 0 or not f or not f.exists():
            pesan = self._galat or ("dibatalkan" if kode != 0 and not self._galat else "hasil tidak tertulis")
            if kode not in (0, 1) and not self._galat:
                pesan = f"proses berhenti tak terduga (kode {kode}); detail di log aplikasi"
            self.l_status.setText("Impor gagal: " + pesan)
            self.jw.log.tulis(f"Impor trajektori MD gagal: {pesan}")
            self._segarkan()
            return
        h = json.loads(f.read_text(encoding="utf-8"))
        pr = self.jw.proyek
        x = h["ligan"][0]
        run = {"id": self.rid, "folder": pr.rel(self.folder), "mode": "md", "tingkat": "impor", "impor": True,
               "tanggal": datetime.now().isoformat(timespec="seconds"), "status": "selesai", "opsi": h.get("opsi"),
               "ligan": [{"nama": x["nama"], "lid": None, "job": None}]}
        pr.md = [r for r in pr.md if r.get("id") != self.rid] + [run]
        self.jw.minta_simpan()
        im = x.get("impor") or {}
        self.jw.log.tulis(f"Impor trajektori MD selesai ({time.time() - self.t0:.0f} s): {im.get('frame')} frame, "
                          f"{im.get('atom_disimpan')} atom, ligan {im.get('ligan') or '-'}.")
        self.selesai.emit(self.rid)
        self.accept()

    def closeEvent(self, e):
        if self.proses:
            self.proses.kill()
            self.proses.waitForFinished(3000)
        super().closeEvent(e)
