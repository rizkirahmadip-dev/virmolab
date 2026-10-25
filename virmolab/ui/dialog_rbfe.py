"""Energi bebas relatif alkimia (F9, eksperimental): susun jaringan perturbasi, jalankan, dan analisis hasil.

Simulasi memakai OpenFE di WSL (core/rbfe_openfe.py): OpenFE hanya berjalan di Linux/macOS, jadi tanpa WSL
dialog ini hanya menyusun jaringan dan memperkirakan beban, dan mengatakannya terus terang. Simulasi dijalankan
terlepas dari aplikasi (bisa berhari-hari untuk protokol bawaan) dan dapat dilanjutkan; dialog membaca
kemajuannya dari log dan berkas analisis OpenFE.
"""
import csv
import json
from datetime import datetime

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QGroupBox,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QSpinBox,
                               QSplitter, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from .. import i18n
from ..core import rbfe, rbfe_openfe
from . import kerja, kit

KOLOM = ["Dari", "Ke", "Atom berubah", "ΔΔG (kkal/mol)", "Galat", "Catatan"]
KOLOM_LIGAN = ["Ligan", "ΔG relatif (kkal/mol)", "Galat", "ΔG docking (kkal/mol)"]
PROTOKOL = {"bawaan": ("Protokol bawaan OpenFE (5 ns × 3 repeat)", 11, 3, 5.0),
            "cepat": ("Uji cepat (0,5 ns × 1 repeat)", 11, 1, 0.5)}


class DialogRbfe(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.jw = parent
        self.proyek = getattr(parent, "proyek", None)
        self.setWindowTitle("Energi bebas relatif (eksperimental)")
        self.setMinimumSize(1060, 680)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self._jaringan = None
        self._kerja = None
        self._run = None              # folder run OpenFE aktif (proyek/rbfe/<waktu>)
        self._hasil_openfe = None     # keluaran rbfe_openfe.kumpulkan() untuk run aktif, bila sudah dimuat
        self._wsl = {"ada": False}
        self._t_pantau = QTimer(self)
        self._t_pantau.setInterval(20000)
        self._t_pantau.timeout.connect(self._pantau)
        self._bangun()
        self._muat_ligan()
        self._muat_run_terakhir()
        kerja.jalankan(lambda lapor: rbfe_openfe.status(), selesai=self._status_wsl,
                       galat=lambda g: self._status_wsl({"ada": False, "pesan": g.split("\n")[0]}))

    def _bangun(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul("Energi bebas relatif (eksperimental)",
                                "Susun jaringan perturbasi untuk seri senyawa kongenerik"))

        h = QHBoxLayout()
        self.l_mesin = kit.catatan("Memeriksa OpenFE di WSL…", "muted")
        h.addWidget(self.l_mesin, 1)
        self.b_pasang_openfe = kit.tombol("Pasang OpenFE…", self._pasang_openfe,
                                          tip="Alat › Pasang alat lanjutan (WSL), paket Docking GPU & RBFE")
        self.b_pasang_openfe.setVisible(False)
        h.addWidget(self.b_pasang_openfe, 0, Qt.AlignTop)
        lay.addLayout(h)

        split = QSplitter(Qt.Horizontal, self)
        split.setChildrenCollapsible(False)

        kiri = QWidget()
        vk = QVBoxLayout(kiri)
        vk.setContentsMargins(0, 0, 8, 0)
        vk.setSpacing(8)

        g_seri = QGroupBox("Seri senyawa")
        v_seri = QVBoxLayout(g_seri)
        self.daftar = QListWidget()
        self.daftar.setSelectionMode(QListWidget.NoSelection)
        v_seri.addWidget(self.daftar)
        h_p = QHBoxLayout()
        h_p.addWidget(kit.tombol("Pilih semua", lambda: self._centang(True)))
        h_p.addWidget(kit.tombol("Kosongkan", lambda: self._centang(False)))
        v_seri.addLayout(h_p)
        vk.addWidget(g_seri, 1)

        g_par = QGroupBox("Protokol yang direncanakan")
        v_par = QVBoxLayout(g_par)
        self.cb_protokol = QComboBox()
        for k, (teks, *_r) in PROTOKOL.items():
            self.cb_protokol.addItem(teks, k)
        self.cb_protokol.addItem("Atur sendiri", "sendiri")
        self.cb_protokol.currentIndexChanged.connect(self._terapkan_protokol)
        v_par.addWidget(self.cb_protokol)
        h_mode = QHBoxLayout()
        h_mode.addWidget(QLabel("Jaringan:"))
        self.cb_mode = QComboBox()
        self.cb_mode.addItem("Pohon rentang minimum", "mst")
        self.cb_mode.addItem("Bintang", "bintang")
        h_mode.addWidget(self.cb_mode, 1)
        v_par.addLayout(h_mode)

        h_l = QHBoxLayout()
        h_l.addWidget(QLabel("Jendela λ:"))
        self.s_lambda = QSpinBox()
        self.s_lambda.setRange(5, 25)
        self.s_lambda.setValue(11)
        h_l.addWidget(self.s_lambda)
        h_l.addWidget(QLabel("Replika:"))
        self.s_replika = QSpinBox()
        self.s_replika.setRange(1, 5)
        self.s_replika.setValue(3)
        h_l.addWidget(self.s_replika)
        v_par.addLayout(h_l)

        h_ns = QHBoxLayout()
        h_ns.addWidget(QLabel("ns per jendela:"))
        self.s_ns = QDoubleSpinBox()
        self.s_ns.setRange(0.5, 50.0)
        self.s_ns.setValue(5.0)
        self.s_ns.setSingleStep(0.5)
        h_ns.addWidget(self.s_ns)
        h_ns.addStretch(1)
        v_par.addLayout(h_ns)
        vk.addWidget(g_par)

        self.b_susun = kit.tombol("Susun jaringan", self._susun, utama=True)
        vk.addWidget(self.b_susun)
        self.l_status = QLabel("")
        self.l_status.setWordWrap(True)
        self.l_status.setObjectName("muted")
        vk.addWidget(self.l_status)

        g_sim = QGroupBox("Simulasi (OpenFE di WSL)")
        v_sim = QVBoxLayout(g_sim)
        h_sim = QHBoxLayout()
        self.b_jalan = kit.tombol("Jalankan", self._jalankan, utama=True,
                                  tip="Pose docking terbaik tiap ligan + reseptor proyek dikirim ke OpenFE di WSL")
        self.b_henti = kit.tombol("Hentikan", self._hentikan)
        self.b_muat = kit.tombol("Muat hasil", self._muat_hasil)
        for b in (self.b_jalan, self.b_henti, self.b_muat):
            b.setEnabled(False)
            h_sim.addWidget(b)
        v_sim.addLayout(h_sim)
        self.l_sim = QLabel("Susun jaringan dulu, lalu jalankan. Simulasi tetap berjalan walau dialog atau "
                            "VirmoLab ditutup, dan dapat dilanjutkan.")
        self.l_sim.setWordWrap(True)
        self.l_sim.setObjectName("muted")
        # status run sampai 4 baris di kolom 360 px; tanpa tinggi minimum QGroupBox memangkasnya atas-bawah
        self.l_sim.setMinimumHeight(4 * self.l_sim.fontMetrics().lineSpacing() + 4)
        self.l_sim.setAlignment(Qt.AlignTop)
        v_sim.addWidget(self.l_sim)
        vk.addWidget(g_sim)
        kiri.setFixedWidth(360)
        split.addWidget(kiri)

        kanan = QWidget()
        vn = QVBoxLayout(kanan)
        vn.setContentsMargins(8, 0, 0, 0)
        vn.setSpacing(8)
        self.tab = QTabWidget()
        self.tabel = kit.tabel(KOLOM, urut=True)
        self.tab.addTab(self.tabel, "Tepi jaringan")
        self.tabel_ligan = kit.tabel(KOLOM_LIGAN, urut=True)
        self.tab.addTab(self.tabel_ligan, "ΔG relatif per ligan")
        vn.addWidget(self.tab, 1)

        g_beban = QGroupBox("Perkiraan beban")
        v_beban = QVBoxLayout(g_beban)
        self.l_beban = QLabel("Susun jaringan untuk melihat perkiraan beban perhitungan.")
        self.l_beban.setWordWrap(True)
        # teksnya 3-4 baris dan panjangnya berubah menurut protokol: beri ruang tetap supaya tidak terpotong
        self.l_beban.setMinimumHeight(64)
        self.l_beban.setAlignment(Qt.AlignTop)
        v_beban.addWidget(self.l_beban)
        self.l_siklus = QLabel("")
        self.l_siklus.setWordWrap(True)
        self.l_siklus.setObjectName("muted")
        v_beban.addWidget(self.l_siklus)
        vn.addWidget(g_beban)
        split.addWidget(kanan)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, 1)

        lay.addWidget(kit.catatan(rbfe.LABEL_EKSPERIMENTAL, "peringatan"))
        self.b_csv = kit.tombol("Ekspor jaringan CSV…", self._ekspor)
        self.b_metode = kit.tombol("Salin paragraf metode", self._salin_metode)
        lay.addLayout(kit.bar_bawah(self, kiri=[self.b_csv, self.b_metode], tutup=True))

    def _muat_ligan(self):
        self.daftar.clear()
        self._seri = []
        for item in (kit.ligan_proyek(self.jw, dengan_mol=False) if self.jw else []):
            smi = item.get("smiles") if isinstance(item, dict) else ""
            nama = item.get("nama") if isinstance(item, dict) else str(item)
            if not smi:
                continue
            self._seri.append((nama, smi))
            li = QListWidgetItem(nama)
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Checked)
            self.daftar.addItem(li)
        if len(self._seri) < 2:
            self.l_status.setText("Butuh sedikitnya dua ligan proyek ber-SMILES untuk menyusun jaringan.")
            self.b_susun.setEnabled(False)

    def _centang(self, nyala):
        for i in range(self.daftar.count()):
            self.daftar.item(i).setCheckState(Qt.Checked if nyala else Qt.Unchecked)

    def _terpilih(self):
        nama = {self.daftar.item(i).text() for i in range(self.daftar.count())
                if self.daftar.item(i).checkState() == Qt.Checked}
        return [(n, s) for n, s in self._seri if n in nama]

    # ------------------------------------------------------------------ susun
    def _susun(self):
        seri = self._terpilih()
        if len(seri) < 2:
            self.l_status.setText("Centang sedikitnya dua senyawa.")
            return
        mode = self.cb_mode.currentData()
        self.b_susun.setEnabled(False)
        self.l_status.setText(f"Memetakan atom {len(seri)} senyawa…")

        def kerjakan(lapor=None):
            pasangan = rbfe.pasangan_dari_mmp(seri)
            return rbfe.jaringan(pasangan, mode), pasangan

        self._kerja = kerja.jalankan(kerjakan, selesai=self._selesai, galat=self._galat)

    def _galat(self, teks):
        self.b_susun.setEnabled(True)
        self.l_status.setText(f"Gagal: {teks.splitlines()[0]}")

    def _selesai(self, hasil):
        self.b_susun.setEnabled(True)
        j, semua_pasangan = hasil
        self._jaringan = j
        tepi = j.get("tepi") or []
        ditolak = [p for p in semua_pasangan if p.pesan]
        self._isi_tabel(tepi + ditolak)

        if not tepi:
            self.l_status.setText(
                f"Tidak ada pasangan yang layak diperturbasi dari {len(semua_pasangan)} pasangan MMP. "
                "RBFE hanya cocok untuk seri kongenerik dengan perubahan kecil.")
            self.l_beban.setText("")
            return

        self.l_status.setText(f"{len(tepi)} tepi tersusun atas {len(j['simpul'])} senyawa."
                              + (f" {j['pesan']}" if j.get("pesan") else ""))
        self._tulis_beban()
        self.b_jalan.setEnabled(self._wsl.get("ada", False))

        siklus = rbfe.tutup_siklus(tepi)
        if siklus:
            n_ok = sum(1 for s in siklus if s["konsisten"])
            self.l_siklus.setText(f"{n_ok} dari {len(siklus)} siklus konsisten.")
        else:
            self.l_siklus.setText("Penutupan siklus baru dapat diperiksa setelah ΔΔG tiap tepi terisi.")

    def _tulis_beban(self):
        tepi = (self._jaringan or {}).get("tepi") or []
        if not tepi:
            return
        # dua kaki per tepi (pelarut + kompleks); kaki kompleks yang dominan dipakai untuk perkiraan
        ns_hari = rbfe_openfe.NS_PER_HARI_TERUKUR if self._wsl.get("ada") else None
        e = rbfe.estimasi_waktu(len(tepi), n_lambda=self.s_lambda.value(), n_replika=self.s_replika.value(),
                                ns_per_lambda=self.s_ns.value(), ns_per_hari=ns_hari)
        # Kalimat diterjemahkan satu per satu: lapisan terjemahan hanya mencocokkan kalimat utuh yang semuanya dikenal.
        t = i18n.t
        beban = t(f"{len(tepi)} tepi × {self.s_lambda.value()} jendela λ × {self.s_replika.value()} replika "
                  f"× {kit.f(self.s_ns.value(), 1)} ns = {kit.f(e['total_ns'], 0)} ns simulasi kaki kompleks.")
        if e["hari"] is None:
            beban += " " + t("Lama perhitungan belum dapat diperkirakan karena kecepatan mesin ini belum diukur; "
                             "jalankan tolok ukur di dialog MD terlebih dahulu.")
        else:
            beban += (" " + t(f"Sekitar {kit.f(e['hari'], 1)} hari pada ±{rbfe_openfe.NS_PER_HARI_TERUKUR:g} ns/hari "
                              "(terukur di RTX 3060 Laptop, sistem TYK2); GPU dan ukuran protein lain mengubah "
                              "angka ini.") + " " + t("Kaki pelarut menambah ±15-20 %."))
        self.l_beban.setText(beban)

    def _terapkan_protokol(self, *_):
        k = self.cb_protokol.currentData()
        if k in PROTOKOL:
            _t, jendela, repeat, ns = PROTOKOL[k]
            self.s_lambda.setValue(jendela)
            self.s_replika.setValue(repeat)
            self.s_ns.setValue(ns)
        for w in (self.s_lambda, self.s_replika, self.s_ns):
            w.setEnabled(k == "sendiri")
        self._tulis_beban()

    # ------------------------------------------------------------------ simulasi OpenFE (WSL)
    def _status_wsl(self, st):
        self._wsl = st
        self.l_mesin.setText(st.get("pesan", ""))
        kit.ganti_jenis(self.l_mesin, "muted" if st.get("ada") else "peringatan")     # gaya kit.catatan
        self.b_pasang_openfe.setVisible(not st.get("ada") and hasattr(self.jw, "buka_alat_wsl"))
        ada_jaringan = bool((self._jaringan or {}).get("tepi"))
        self.b_jalan.setEnabled(bool(st.get("ada")) and ada_jaringan)
        if not st.get("ada"):
            self.l_sim.setText("Tanpa OpenFE di WSL, simulasi tidak dapat dijalankan di komputer ini. Jaringan dan "
                               "perkiraan beban tetap dapat disusun; hasil OpenFE dari mesin Linux lain dapat dimuat.")
        self._tulis_beban()

    def _pasang_openfe(self):
        d = self.jw.buka_alat_wsl("gpu_rbfe")
        d.alatBerubah.connect(lambda: kerja.jalankan(
            lambda lapor: rbfe_openfe.status(segar=True), selesai=self._status_wsl,
            galat=lambda g: self._status_wsl({"ada": False, "pesan": g.split("\n")[0]})))

    def _folder_rbfe(self):
        pr = self.proyek
        return pr.p("rbfe") if pr else None

    def _muat_run_terakhir(self):
        f = self._folder_rbfe()
        if not f or not f.exists():
            return
        runs = sorted((p.parent for p in f.glob("*/run.json")), key=lambda p: p.name)
        if not runs:
            return
        self._run = runs[-1]
        self.b_muat.setEnabled(True)
        self.b_henti.setEnabled(True)
        self._pantau()
        self._t_pantau.start()

    def _jalankan(self):
        tepi = (self._jaringan or {}).get("tepi") or []
        if not tepi or not self.proyek:
            return
        baris = {l["nama"]: l.get("baris") for l in kit.ligan_proyek(self.jw, dengan_mol=False)}
        nama = sorted({t.a for t in tepi} | {t.b for t in tepi})
        tanpa = [n for n in nama if not baris.get(n)]
        if tanpa:
            self.l_sim.setText(i18n.t("Belum di-docking, jadi tidak punya pose awal: ") + ", ".join(tanpa[:6])
                               + i18n.t(". Docking seri ini dulu dengan kotak yang sama."))
            return
        try:
            ligan = [(n, rbfe_openfe.pose_dari_baris(self.proyek, baris[n])) for n in nama]
            protein, catatan = rbfe_openfe.reseptor_untuk_rbfe(self.proyek)
        except Exception as e:
            self.l_sim.setText(f"Bahan simulasi tidak dapat disiapkan: {e}")
            return
        folder = self._folder_rbfe() / datetime.now().strftime("%Y%m%d_%H%M%S")
        rbfe_openfe.siapkan_run(folder, ligan, protein, [(t.a, t.b) for t in tepi],
                                ns_produksi=self.s_ns.value(), ns_ekuilibrasi=min(1.0, self.s_ns.value() / 5),
                                repeat=self.s_replika.value(), jendela=self.s_lambda.value())
        cmd = rbfe_openfe.perintah_jalan_terlepas(folder)
        ok = QProcess.startDetached(cmd[0], cmd[1:])
        if not (ok[0] if isinstance(ok, tuple) else ok):
            self.l_sim.setText("WSL tidak dapat dijalankan.")
            return
        self._run = folder
        self.b_henti.setEnabled(True)
        self.b_muat.setEnabled(True)
        self.l_sim.setText(i18n.t(f"Simulasi dimulai ({len(tepi)} tepi, {2 * len(tepi)} kaki). Folder: rbfe/{folder.name}")
                           + (f". {i18n.t('Catatan')}: " + "; ".join(i18n.t(c) for c in catatan) if catatan else "."))
        self._t_pantau.start()

    def _hentikan(self):
        if not self._run:
            return
        info = json.loads((self._run / "run.json").read_text(encoding="utf-8"))
        kerja.jalankan(lambda lapor: rbfe_openfe.hentikan(info["run"]),
                       selesai=lambda _h: self.l_sim.setText("Simulasi dihentikan. Jalankan lagi untuk melanjutkan "
                                                            "kaki yang belum selesai."),
                       galat=lambda g: self.l_sim.setText("Gagal menghentikan: " + g.split("\n")[0]))
        self._t_pantau.stop()

    def _pantau(self):
        if not self._run:
            return
        teks_log = ""
        f = self._run / "jalan.log"
        if f.exists():
            teks_log = f.read_text(encoding="utf-8", errors="replace")
        selesai = teks_log.count("SELESAI ") - teks_log.count("SEMUA_SELESAI")
        total = 2 * len(json.loads((self._run / "run.json").read_text(encoding="utf-8")).get("tepi", []))

        def tampil(kem):
            berjalan = [(n, v) for n, v in kem.items() if not v.get("selesai") and "persen" in v]
            n_hasil = sum(1 for v in kem.values() if v.get("selesai"))
            t = i18n.t
            teks = t(f"Run rbfe/{self._run.name}: {max(n_hasil, selesai)} dari {total} kaki selesai.")
            for n, v in berjalan[:2]:
                a, b, kaki = (n.split("__") + ["", "", ""])[:3]
                teks += " " + t(f"Berjalan: {a} → {b} · {kaki} {v['persen']:.0f} %")
                teks += (", " + t(f"sisa ±{v['sisa']}") + ".") if v.get("sisa") else "."
            if "GAGAL siapkan" in teks_log:
                teks += " " + t("Penyiapan transformasi gagal; lihat log/siapkan.log di WSL.")
            if "SEMUA_SELESAI" in teks_log:
                teks += " " + t("Semua kaki selesai.")
                self._t_pantau.stop()
                self._muat_hasil()
            self.l_sim.setText(teks)

        kerja.jalankan(lambda lapor: rbfe_openfe.kemajuan(self._run), selesai=tampil, galat=lambda g: None)

    def _muat_hasil(self):
        if not self._run:
            return
        try:
            h = rbfe_openfe.kumpulkan(self._run)
        except Exception as e:
            self.l_sim.setText(f"Hasil belum dapat dibaca: {e}")
            return
        self._hasil_openfe = h
        peta = {(t["a"], t["b"]): t for t in h["tepi"]}
        tepi = (self._jaringan or {}).get("tepi") or []
        if not tepi:      # dialog dibuka ulang: tabel diisi dari run
            tepi = [rbfe.Perturbasi(a=t["a"], b=t["b"]) for t in h["tepi"]]
            self._jaringan = {"tepi": tepi, "simpul": sorted({t.a for t in tepi} | {t.b for t in tepi}),
                              "mode": "run"}
        for t in tepi:
            r = peta.get((t.a, t.b))
            if r and r["ddg"] is not None:
                t.ddg, t.galat = round(r["ddg"], 2), round(r["galat"], 2)
                t.pesan = "OpenFE"
        self._isi_tabel(tepi)
        dock = {l["nama"]: l.get("dg") for l in kit.ligan_proyek(self.jw, dengan_mol=False)} if self.jw else {}
        self.tabel_ligan.setSortingEnabled(False)
        self.tabel_ligan.setRowCount(len(h["ligan"]))
        for r, (n, (g, e)) in enumerate(h["ligan"].items()):
            self.tabel_ligan.setItem(r, 0, QTableWidgetItem(n))
            self.tabel_ligan.setItem(r, 1, kit.sel_angka(g, d=2))
            self.tabel_ligan.setItem(r, 2, kit.sel_angka(e, d=2))
            self.tabel_ligan.setItem(r, 3, kit.sel_angka(dock.get(n), d=2))
        self.tabel_ligan.setSortingEnabled(True)
        siklus = rbfe.tutup_siklus([t for t in tepi if t.ddg is not None])
        if siklus:
            n_ok = sum(1 for s in siklus if s["konsisten"])
            self.l_siklus.setText(f"{n_ok} dari {len(siklus)} siklus konsisten (|Σ ΔΔG| ≤ 1 kkal/mol).")

    def _isi_tabel(self, tepi):
        self.tabel.setSortingEnabled(False)
        self.tabel.setRowCount(len(tepi))
        for r, t in enumerate(tepi):
            self.tabel.setItem(r, 0, QTableWidgetItem(str(t.a)))
            self.tabel.setItem(r, 1, QTableWidgetItem(str(t.b)))
            self.tabel.setItem(r, 2, kit.sel_angka(t.n_berubah, d=0))
            self.tabel.setItem(r, 3, kit.sel_angka(t.ddg, d=2))
            self.tabel.setItem(r, 4, kit.sel_angka(t.galat, d=2))
            self.tabel.setItem(r, 5, QTableWidgetItem(t.pesan))
        self.tabel.setSortingEnabled(True)

    # ------------------------------------------------------------------ keluaran
    def _ekspor(self):
        if not self._jaringan or not self._jaringan.get("tepi"):
            self.l_status.setText("Susun jaringan terlebih dahulu.")
            return
        p, _ = QFileDialog.getSaveFileName(self, "Simpan jaringan perturbasi", "jaringan_rbfe.csv",
                                           "CSV (*.csv)")
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["# catatan", rbfe.LABEL_EKSPERIMENTAL])
            w.writerow(["dari", "ke", "atom_berubah", "ddg_kkal_mol", "galat", "catatan"])
            for t in self._jaringan["tepi"]:
                w.writerow([t.a, t.b, t.n_berubah, t.ddg, t.galat, t.pesan])
        self.l_status.setText(f"Jaringan disimpan ke {p}")

    def _salin_metode(self):
        # Setelah simulasi nyata, paragraf metode dibaca dari hasil run (versi OpenFE, medan gaya, protokol yang
        # benar-benar dipakai), bukan dari rencana di dialog.
        teks = rbfe_openfe.paragraf_metode(self._hasil_openfe) if self._hasil_openfe else ""
        if teks:
            kit.salin(teks)
            self.l_status.setText("Paragraf metode run OpenFE disalin ke papan klip.")
            return
        if not self._jaringan:
            self.l_status.setText("Susun jaringan terlebih dahulu.")
            return
        teks = rbfe.paragraf_metode(self._jaringan, n_lambda=self.s_lambda.value(),
                                    n_replika=self.s_replika.value(), ns_per_lambda=self.s_ns.value())
        if not teks:
            self.l_status.setText("Belum ada tepi jaringan untuk ditulis di paragraf metode.")
            return
        kit.salin(teks)
        self.l_status.setText("Paragraf metode disalin ke papan klip.")
