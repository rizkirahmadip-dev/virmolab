"""Dialog Konsensus skor (Analisis › Konsensus skor…): pilih kolom skor (job/mesin berbeda + rescoring Vina/Vinardo
pose terbaik), hitung peringkat konsensus, Kendall W, ekspor CSV, salin paragraf metode."""
import csv
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
                               QTextBrowser, QVBoxLayout, QWidget)

from ..core import konsensus as K
from ..core import mesin as M
from . import kit
from ..core.laporan import id_angka
from . import kerja, theme


class DialogKonsensus(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Konsensus skor")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1180, 720)
        self.hasil = None
        lay = QVBoxLayout(self)
        lay.addWidget(kit.judul(
            "Konsensus beberapa fungsi skor",
            "Peringkat yang bertahan di beberapa fungsi skor lebih dapat dipercaya daripada skor satu mesin. "
            "Pilih kolom skor (job dengan mesin berbeda dan/atau rescoring pose terbaik), lalu Hitung."))
        bagi = QSplitter(Qt.Horizontal)
        kiri = QWidget()
        kl = QVBoxLayout(kiri)
        kl.setContentsMargins(0, 0, 0, 0)
        kl.addWidget(QLabel("<b>Kolom skor</b>"))
        self.daftar = QListWidget()
        kl.addWidget(self.daftar, 1)
        f = QFormLayout()
        self.c_pose = QComboBox()
        self.c_pose.setToolTip("Pose terbaik dari job ini yang di-rescoring dengan Vina/Vinardo")
        self.s_atas = QDoubleSpinBox()
        self.s_atas.setRange(5, 50)
        self.s_atas.setDecimals(0)
        self.s_atas.setSuffix(" % teratas")
        self.s_atas.setValue(20)
        self.s_atas.setToolTip("Ligan 'konsisten' = masuk persentil ini di semua kolom skor")
        self.c_filter_sepakat = QCheckBox("Hanya pose yang Sepakat")
        self.c_filter_sepakat.setToolTip("Tampilkan hanya ligan yang pose dockingnya sepakat dengan Boltz-2")
        self.c_filter_sepakat.toggled.connect(lambda: self._tampil())
        f.addRow("Pose rescoring", self.c_pose)
        f.addRow("Konsisten bila", self.s_atas)
        f.addRow("", self.c_filter_sepakat)
        kl.addLayout(f)
        b = QPushButton("Hitung konsensus")
        b.setObjectName("primary")
        b.clicked.connect(self.hitung)
        kl.addWidget(b)
        bagi.addWidget(kiri)
        kanan = QSplitter(Qt.Vertical)
        self.tabel = QTableWidget(0, 0)
        self.tabel.setSortingEnabled(False)
        self.tabel.verticalHeader().setVisible(False)
        kanan.addWidget(self.tabel)
        self.info = QTextBrowser()
        kanan.addWidget(self.info)
        kanan.setSizes([460, 180])
        bagi.addWidget(kanan)
        bagi.setSizes([330, 850])
        lay.addWidget(bagi, 1)
        bawah = QHBoxLayout()
        bawah.addStretch(1)
        for t, fn in (("Salin paragraf metode", self.salin), ("Ekspor CSV…", self.ekspor), ("✕ Tutup", self.close)):
            x = QPushButton(t)
            x.clicked.connect(fn)
            bawah.addWidget(x)
        lay.addLayout(bawah)
        self.isi_daftar()

    # ------------------------------------------------------------ sumber
    def isi_daftar(self):
        pr = self.jw.proyek
        self.daftar.clear()
        self.c_pose.clear()
        jobs = [j for j in (pr.job if pr else []) if any(l.get("status") == "selesai" for l in j["ligan"])]
        terakhir = {}            # per mesin: job dengan ligan selesai terbanyak (seri: yang terbaru)
        for j in jobs:
            n = sum(1 for l in j["ligan"] if l.get("status") == "selesai")
            if n >= terakhir.get(j["mesin"], (0, ""))[0]:
                terakhir[j["mesin"]] = (n, j["id"])
        terakhir = {k: v[1] for k, v in terakhir.items()}
        for j in jobs:
            n = sum(1 for l in j["ligan"] if l.get("status") == "selesai")
            it = QListWidgetItem(f"{M.MESIN.get(j['mesin'], j['mesin'])} · {j['id'][-13:]} · {n} ligan")
            it.setData(Qt.UserRole, ("job", j["id"]))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if terakhir.get(j["mesin"]) == j["id"] and n >= 3 else Qt.Unchecked)
            self.daftar.addItem(it)
            self.c_pose.addItem(f"{M.MESIN.get(j['mesin'], j['mesin'])} · {j['id'][-13:]} · {n} ligan", j["id"])
        for k, t in K.FUNGSI_RESCORE.items():
            it = QListWidgetItem(t)
            it.setData(Qt.UserRole, ("rescore", k))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            self.daftar.addItem(it)
        if jobs:                       # bawaan: job dengan ligan terbanyak
            self.c_pose.setCurrentIndex(max(range(len(jobs)), key=lambda i: (
                sum(1 for l in jobs[i]["ligan"] if l.get("status") == "selesai"), i)))

    def _pilihan(self):
        return [self.daftar.item(i).data(Qt.UserRole) for i in range(self.daftar.count())
                if self.daftar.item(i).checkState() == Qt.Checked]

    # ------------------------------------------------------------ hitung
    def hitung(self):
        pr = self.jw.proyek
        if not pr:
            return
        pilih = self._pilihan()
        jid_pose = self.c_pose.currentData()
        perlu = [k for jenis, k in pilih if jenis == "rescore"]
        j_pose = self.jw.pelaksana.cari(jid_pose) if jid_pose else None
        rec = pr.p(pr.reseptor["pdbqt"]) if pr.reseptor and pr.reseptor.get("pdbqt") else None
        tugas = []
        if perlu and j_pose and rec:
            for l in j_pose["ligan"]:
                if l.get("status") == "selesai" and any(k not in (l.get("rescore") or {}) for k in perlu):
                    tugas.append(l)

        def kerjakan(lapor):
            gagal = 0
            for i, l in enumerate(tugas, 1):
                try:
                    p = M.baca_hasil(j_pose["mesin"], pr.p(l["keluaran"]))[0]
                    rs = dict(l.get("rescore") or {})
                    for k in perlu:
                        if k not in rs:
                            rs[k] = K.rescore(rec, p.pdbqt, k)
                    l["rescore"] = rs
                except Exception as e:      # satu ligan gagal tidak menghentikan yang lain
                    gagal += 1
                    lapor.log.emit(f"Rescoring {l.get('nama')} gagal: {e}")
                lapor.log.emit(f"Rescoring {i}/{len(tugas)}")
            return gagal

        def selesai(gagal):
            if tugas:
                self.jw.minta_simpan()
            self._susun(pilih, j_pose, perlu)
            if gagal:
                self.info.append(f"<p style='color:{kit.hx('warn')}'>⚠ Rescoring gagal untuk {gagal} ligan (lihat Log).</p>")

        if tugas:
            self.info.setHtml(f"<p>Rescoring {len(tugas)} pose dengan {', '.join(perlu)}…</p>")
            kerja.jalankan(kerjakan, selesai=selesai, galat=lambda g: self.info.setHtml(f"<p>Gagal: {escape(g)}</p>"),
                           log=self.jw.log.tulis)
        else:
            self._susun(pilih, j_pose, perlu)

    def _susun(self, pilih, j_pose, perlu):
        kolom, nama = {}, {}
        for jenis, k in pilih:
            if jenis == "job":
                j = self.jw.pelaksana.cari(k)
                if not j:
                    continue
                d = {}
                for l in j["ligan"]:
                    if l.get("status") == "selesai" and l.get("energi") is not None:
                        lid = l["id"]
                        d[lid] = min(d.get(lid, 1e9), l["energi"])
                        nama[lid] = l.get("nama", lid)
                kolom[f"{M.MESIN.get(j['mesin'], j['mesin'])} ·{j['id'][-6:]}"] = d
        if j_pose:
            for k in perlu:
                d = {}
                for l in j_pose["ligan"]:
                    v = (l.get("rescore") or {}).get(k)
                    if v is not None:
                        lid = l["id"]
                        d[lid] = v
                        nama[lid] = l.get("nama", lid)
                kolom[K.FUNGSI_RESCORE[k]] = d
        self.hasil = K.hitung(kolom, nama, self.s_atas.value())
        peta_kofold = {}
        if j_pose:
            for l in j_pose.get("ligan", []):
                lid = l["id"]
                kf = l.get("kofolding") or {}
                peta_kofold[lid] = {
                    "afinitas": kf.get("afinitas_pred_value"),
                    "prob": kf.get("afinitas_probabilitas"),
                    "kesepakatan": kf.get("kesepakatan", "–"),
                }
        self.hasil["peta_kofold"] = peta_kofold
        self._tampil()

    def _tampil(self):
        h = self.hasil
        if not h:
            return
        t = theme.TOKEN[getattr(self.jw, "mode", "terang")]
        if h.get("galat"):
            self.tabel.setRowCount(0)
            self.info.setHtml(f"<p style='color:{t['warn']}'>{escape(h['galat'])}</p>")
            return
        kol = h["kolom"]
        peta_kofold = h.get("peta_kofold") or {}
        judul = ["#", "Ligan"] + [f"{k}\nΔG (peringkat)" for k in kol] + [
            "Rata-rata\nperingkat", "z rata-rata", "Konsisten", "Boltz-2 afinitas", "Kesepakatan"
        ]
        self.tabel.clear()
        self.tabel.setColumnCount(len(judul))
        self.tabel.setHorizontalHeaderLabels(judul)

        baris_sumber = h["baris"]
        if self.c_filter_sepakat.isChecked():
            baris_sumber = [b for b in baris_sumber if peta_kofold.get(b["kunci"], {}).get("kesepakatan") == "Sepakat"]

        self.tabel.setRowCount(len(baris_sumber))
        for r, b in enumerate(baris_sumber):
            sel = [str(b["peringkat"]), b["ligan"]]
            sel += [f"{id_angka(f'{s:.2f}')}  ({id_angka(f'{k:g}')})" for s, k in zip(b["skor"], b["rank"])]
            sel += [id_angka(f"{b['rata_rank']:.2f}"), id_angka(f"{b['rata_z']:.2f}"), "✓" if b["konsisten"] else ""]

            # Info Boltz-2
            info_kf = peta_kofold.get(b["kunci"]) or {}
            aff = info_kf.get("afinitas")
            prob = info_kf.get("prob")
            if aff is not None:
                persen = f" ({id_angka(f'{prob * 100:.0f}')} %)" if prob is not None else ""
                t_aff = f"{id_angka(f'{aff:.2f}')}{persen}"
            else:
                t_aff = "–"
            kes = info_kf.get("kesepakatan", "–")
            sel += [t_aff, kes]

            for c, v in enumerate(sel):
                it = QTableWidgetItem(v)
                if c != 1 and c != len(sel) - 1:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if c < len(sel) - 3 else Qt.AlignCenter)
                else:
                    it.setTextAlignment(Qt.AlignCenter if c == len(sel) - 1 else Qt.AlignLeft | Qt.AlignVCenter)
                if b["konsisten"]:
                    it.setBackground(QColor(t["accs"]))
                    if c == len(sel) - 3:
                        it.setForeground(QColor(t["ok"]))
                if c == len(sel) - 1:
                    if kes == "Sepakat":
                        it.setForeground(QColor(t["ok"]))
                    elif kes == "Sebagian":
                        it.setForeground(QColor(t["warn"]))
                    elif kes == "Bertentangan":
                        it.setForeground(QColor(t["bad"]))
                self.tabel.setItem(r, c, it)
        self.tabel.resizeColumnsToContents()
        w = h.get("W")
        tafsir = ("sangat kuat" if w and w[0] >= 0.7 else "sedang" if w and w[0] >= 0.5 else "lemah") if w else "-"
        o = [f"<p><b>{h['n_konsisten']} dari {h['n']} ligan konsisten</b> (masuk {h['teratas']:g} % teratas di semua "
             f"{len(kol)} kolom skor; baris disorot).</p>"]
        if w:
            o.append(f"<p>Kesepakatan antar fungsi skor: Kendall W = {id_angka(f'{w[0]:.3f}')} ({tafsir}); "
                     f"χ²({w[2]}) = {id_angka(f'{w[1]:.2f}')}, p {'&lt; 0,0001' if w[3] < 1e-4 else '= ' + id_angka(f'{w[3]:.4f}')}.</p>")
        rho = h["spearman"]
        pas = [f"{kol[a]} vs {kol[b]}: ρ = {id_angka(f'{rho[a][b]:.2f}')}" for a in range(len(kol))
               for b in range(a + 1, len(kol))]
        o.append("<p style='color:%s'>Spearman: %s</p>" % (t["mut"], escape(" · ".join(pas))))
        if w and w[0] < 0.5:
            o.append(f"<p style='color:{t['warn']}'>⚠ Fungsi skor kurang sepakat: tafsirkan peringkat satu mesin dengan "
                     "hati-hati dan utamakan ligan yang konsisten.</p>")
        self.info.setHtml("".join(o))

    # ------------------------------------------------------------ keluaran
    def _kalimat_kofolding(self):
        """Kalimat metode co-folding, hanya bila ada ligan yang benar-benar sudah dianalisis.

        Disusun dari jumlah nyata per label, bukan kalimat tetap, dan menyebut keterbatasannya."""
        peta = (self.hasil or {}).get("peta_kofold") or {}
        label = [v.get("kesepakatan") for v in peta.values()
                 if v.get("kesepakatan") in ("Sepakat", "Sebagian", "Bertentangan")]
        if not label:
            return ""
        n = len(label)
        from .. import i18n
        if i18n.inggris():
            nama = {"Sepakat": "agree", "Sebagian": "partly agree", "Bertentangan": "disagree"}
            rinci = ", ".join(f"{label.count(k)} {nama[k]}" for k in ("Sepakat", "Sebagian", "Bertentangan")
                              if label.count(k))
            return (f" As a cross-check, {n} ligands were also predicted with the Boltz-2 co-folding model; the "
                    "output structures were superimposed on the receptor using Cα atoms before the ligand RMSD was "
                    "calculated, and agreement was assessed from the ligand RMSD, the Tanimoto similarity of the "
                    f"interaction fingerprints, and PoseBusters checks of both poses ({rinci}). Boltz-2 was trained "
                    "on PDB structures, so agreement on targets or ligands already in the PDB may reflect training-"
                    "data leakage rather than predictive ability.")
        rinci = ", ".join(f"{label.count(k)} {k.lower()}" for k in ("Sepakat", "Sebagian", "Bertentangan")
                          if label.count(k))
        return (f" Sebagai pemeriksaan silang, {n} ligan juga diprediksi dengan model co-folding Boltz-2; "
                "struktur keluarannya disuperposisikan ke reseptor memakai atom Cα sebelum RMSD ligan dihitung, "
                "dan kesepakatan dinilai dari RMSD ligan, kemiripan Tanimoto sidik jari interaksi, serta "
                f"PoseBusters kedua pose ({rinci}). Boltz-2 dilatih pada struktur PDB, sehingga kesepakatan pada "
                "target atau ligan yang sudah ada di PDB dapat mencerminkan kebocoran data latih dan bukan "
                "kemampuan prediksi.")

    def salin(self):
        t = K.teks_metode(self.hasil)
        if any(k.startswith("Vinardo") for k in (self.hasil or {}).get("kolom", [])):
            from .. import i18n
            t += (" Rescoring used AutoDock Vina 1.2 (--score_only) with the Vina and Vinardo scoring functions."
                  if i18n.inggris() else
                  " Rescoring memakai AutoDock Vina 1.2 (--score_only) dengan fungsi skor Vina dan Vinardo.")
        t += self._kalimat_kofolding()
        QGuiApplication.clipboard().setText(t)
        self.jw.statusBar().showMessage("Paragraf metode konsensus disalin.", 4000)

    def ekspor(self):
        h = self.hasil
        if not h or h.get("galat"):
            return
        dasar = Path(self.jw.proyek.p("ekspor", "konsensus_skor.csv"))
        dasar.parent.mkdir(exist_ok=True)
        f, _ = QFileDialog.getSaveFileName(self, "Ekspor konsensus", str(dasar), "CSV (*.csv)")
        if not f:
            return
        with open(f, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["Peringkat", "Ligan"] + [f"{k} dG" for k in h["kolom"]] + [f"{k} peringkat" for k in h["kolom"]]
                       + ["Rata-rata peringkat", "z rata-rata", "Konsisten", "Boltz-2 afinitas", "Kesepakatan"])
            peta_kofold = h.get("peta_kofold") or {}
            for b in h["baris"]:
                info_kf = peta_kofold.get(b["kunci"]) or {}
                aff = info_kf.get("afinitas")
                t_aff = id_angka(f"{aff:.3f}") if aff is not None else ""
                w.writerow([b["peringkat"], b["ligan"]] + [id_angka(f"{s:.3f}") for s in b["skor"]]
                           + [id_angka(f"{r:g}") for r in b["rank"]]
                           + [id_angka(f"{b['rata_rank']:.3f}"), id_angka(f"{b['rata_z']:.3f}"),
                              "ya" if b["konsisten"] else "tidak", t_aff, info_kf.get("kesepakatan", "–")])
        self.jw.log.tulis(f"Konsensus skor diekspor: {f}")
