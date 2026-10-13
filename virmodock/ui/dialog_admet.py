"""Dialog Prediksi ADMET (Analisis › Prediksi ADMET (ADMET-AI)…).

Tabel ligan × 30 sifat ADMET (dikelompokkan Absorpsi/Distribusi/Metabolisme/Ekskresi/Toksisitas), sel probabilitas
diwarnai (hijau = menguntungkan, merah = berisiko); panel kanan = profil ligan terpilih. Hasil disimpan di
proyek.ligan[*]['admet'] (cache per SMILES). Prediksi berjalan di proses terpisah (core.admet).
"""
import csv
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QSplitter,
                               QTabWidget, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget)

from ..core import admet as AD
from ..core import catat
from ..core import peta_tubuh as PT
from . import kerja, kit
from .peta_tubuh import PetaTubuh


class DialogAdmet(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Prediksi ADMET - ADMET-AI")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1280, 760)
        self.lig = []          # [{nama, smiles, lig (dict proyek | None), hasil}]
        lay = QVBoxLayout(self)
        lay.addWidget(kit.judul(
            "Prediksi ADMET dengan ADMET-AI",
            "Prediksi model pembelajaran mesin (Chemprop-RDKit, 41 dataset TDC). Angka 0-1 = probabilitas "
            "kelas; warna hijau = menguntungkan, merah = berisiko. Ini skrining awal, bukan pengganti uji "
            "in vitro/in vivo."))
        self.tab = QTabWidget()
        lay.addWidget(self.tab, 1)
        w_tabel = QWidget()
        lay_tabel = QVBoxLayout(w_tabel)
        lay_tabel.setContentsMargins(0, 6, 0, 0)
        bagi = QSplitter(Qt.Horizontal)
        self.tabel = QTableWidget(0, 0)
        self.tabel.verticalHeader().setVisible(False)
        self.tabel.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabel.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabel.currentCellChanged.connect(lambda r, *_: self.profil(r))
        bagi.addWidget(self.tabel)
        self.info = QTextBrowser()
        self.info.setMinimumWidth(360)
        bagi.addWidget(self.info)
        bagi.setSizes([880, 400])
        lay_tabel.addWidget(bagi, 1)
        self.tab.addTab(w_tabel, "Tabel 30 parameter")
        self.tab.addTab(self._tab_peta(), "Peta organ")
        self.tab.currentChanged.connect(lambda _i: self.profil(self.tabel.currentRow()))
        h = QHBoxLayout()
        self.l_status = QLabel()
        self.l_status.setObjectName("muted")
        h.addWidget(self.l_status, 1)
        self.b_hitung = QPushButton("Prediksi ligan yang belum dihitung")
        self.b_hitung.setObjectName("primary")
        self.b_hitung.clicked.connect(lambda: self.hitung(False))
        b_ulang = QPushButton("Hitung ulang semua")
        b_ulang.clicked.connect(lambda: self.hitung(True))
        b_csv = QPushButton("Ekspor CSV…")
        b_csv.clicked.connect(self.ekspor)
        b_tutup = QPushButton("✕ Tutup")
        b_tutup.clicked.connect(self.close)
        for b in (self.b_hitung, b_ulang, b_csv, b_tutup):
            h.addWidget(b)
        lay.addLayout(h)
        self.muat()

    def _tab_peta(self):
        """Peta organ: siluet tubuh di kiri, rincian endpoint organ terpilih di kanan."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(8)
        atas = QHBoxLayout()
        self.l_peta_ligan = QLabel("—")
        self.l_peta_ligan.setObjectName("judulDialog")
        atas.addWidget(self.l_peta_ligan, 1)
        self.c_alur = QCheckBox("Animasi perjalanan obat")
        self.c_alur.setChecked(True)
        self.c_alur.setToolTip("Titik berjalan saluran cerna → hati → ginjal; kecepatannya mengikuti waktu paruh "
                               "prediksi. Matikan bila mengganggu atau untuk menghemat daya.")
        atas.addWidget(self.c_alur)
        lay.addLayout(atas)
        self.l_peta_ringkas = kit.catatan("")
        lay.addWidget(self.l_peta_ringkas)

        bagi = QSplitter(Qt.Horizontal)
        self.peta = PetaTubuh()
        self.c_alur.toggled.connect(self.peta.atur_alur)
        self.peta.organDipilih.connect(self._organ_dipilih)
        bagi.addWidget(self.peta)
        self.info_organ = QTextBrowser()
        self.info_organ.setMinimumWidth(360)
        bagi.addWidget(self.info_organ)
        bagi.setSizes([620, 520])
        lay.addWidget(bagi, 1)

        bawah = QHBoxLayout()
        b_png = QPushButton("Simpan gambar PNG…")
        b_png.clicked.connect(lambda: self._simpan_peta("png"))
        b_svg = QPushButton("Simpan gambar SVG…")
        b_svg.clicked.connect(lambda: self._simpan_peta("svg"))
        bawah.addWidget(b_png)
        bawah.addWidget(b_svg)
        bawah.addStretch(1)
        lay.addLayout(bawah)
        lay.addWidget(kit.catatan(
            "Skor organ adalah rata-rata endpoint ADMET-AI yang relevan, dibatasi oleh endpoint terburuknya; "
            "organ tanpa model (paru, pankreas, tiroid) sengaja tidak digambar. Angka ini prediksi pembelajaran "
            "mesin untuk menyaring kandidat — bukan pengganti uji toksisitas in vitro atau in vivo."))
        return w

    def _peta_muat(self, x):
        """Isi peta dari satu baris ligan ({nama, hasil, …})."""
        if not hasattr(self, "peta"):
            return
        self.l_peta_ligan.setText(x["nama"] if x else "—")
        self.peta.muat((x or {}).get("hasil") or {}, (x or {}).get("nama", ""))
        self.l_peta_ringkas.setText(PT.ringkas(self.peta.organ))
        pilih = self.peta.terpilih or next((o["kunci"] for o in self.peta.organ
                                            if o["status"] == "risiko"), None)
        if pilih is None:
            pilih = next((o["kunci"] for o in self.peta.organ if o["skor"] is not None), None)
        if pilih:
            self.peta.pilih(pilih)
        else:
            self.info_organ.setHtml("<p>Belum ada prediksi ADMET untuk ligan ini.</p>")

    def _organ_dipilih(self, kunci):
        o = self.peta.organ_kunci(kunci)
        if not o:
            return
        warna = kit.hx({"baik": "ok", "sedang": "warn", "risiko": "bad", "kosong": "mut"}[o["status"]])
        skor = "tidak dinilai" if o["skor"] is None else f"{o['skor']:.0f} / 100"
        baris = []
        for e in o["endpoint"]:
            nilai = AD.teks_nilai(e["kunci"], e["nilai"])
            if e["netral"]:
                ket, w = "tidak dipakai menilai (netral)", kit.hx("mut")
            elif e["skor"] is None:
                ket, w = "belum ada nilai", kit.hx("mut")
            else:
                pct = int(round(e["skor"] * 100))
                w = kit.hx("ok" if pct >= 70 else ("warn" if pct >= 40 else "bad"))
                lebar = max(2, pct)
                ket = (f"<span style='background:{w};color:{w}'>{'&nbsp;' * (lebar // 6)}</span> {pct}")
            baris.append(f"<tr><td width='58%'>{escape(e['label'])}</td>"
                         f"<td align=right style='font-weight:600'>{escape(nilai)}</td>"
                         f"<td style='color:{w}'>&nbsp;{ket}</td></tr>")
        tanpa = ", ".join(n for _k, n in PT.TANPA_MODEL)
        self.info_organ.setHtml(
            f"<p style='font-size:14px;font-weight:600;color:{warna}'>{escape(o['nama'])} — {skor}</p>"
            f"<p>{escape(o['keterangan'])}</p>"
            f"<table cellspacing=3 width='100%'>{''.join(baris)}</table>"
            f"<p style='color:{kit.hx('mut')};font-size:9pt;margin-top:10px'>Kolom kanan = skor kelayakan 0–100 tiap "
            f"endpoint. Organ tanpa model di VirmoDock: {escape(tanpa)}.</p>"
            f"<p style='color:{kit.hx('mut')};font-size:9pt'>Sitasi: {escape(AD.SITASI)}</p>")

    def _simpan_peta(self, fmt):
        x = self.lig[self.tabel.currentRow()] if 0 <= self.tabel.currentRow() < len(self.lig) else None
        dasar = (x["nama"] if x else "peta_organ").replace(" ", "_")
        f = self.jw._path("Simpan peta organ ADMET", f"{dasar}_admet.{fmt}",
                          "PNG (*.png)" if fmt == "png" else "SVG (*.svg)")
        if not f:
            return
        ok = self.peta.simpan_png(f) if fmt == "png" else self.peta.simpan_svg(f)
        self.l_status.setText(f"Peta organ disimpan: {f}" if ok else "Gagal menyimpan peta organ.")

    def muat(self):
        from rdkit import Chem
        from ..core import kemiripan as K
        from ..core.sifat import netralkan
        self.lig = []
        for _k, nama, teks, fmt, l in self.jw._sumber_sifat():
            o = self.jw.objek.get(_k)
            if o is not None and o.info.get("aditif"):
                continue          # pelarut/ion kristalografi (DMS, GOL, SO4): bukan kandidat obat
            try:
                # bentuk netral (fragmen terbesar, tanpa protonasi pH): model dilatih pada struktur netral
                mol = netralkan(K.mol_dari(teks, fmt))
                if mol.GetNumHeavyAtoms() < 6:      # serpihan kecil: prediksi ADMET tidak bermakna
                    continue
                smi = Chem.MolToSmiles(mol)
            except Exception as e:
                catat.log.warning(f"ADMET dilewati untuk '{nama}': {e}")
                continue
            c = (l or {}).get("admet") or {}
            hasil = c.get("hasil") if c.get("smiles") == smi and c.get("v") == AD.VERSI else None
            self.lig.append({"nama": nama, "smiles": smi, "lig": l, "hasil": hasil})
        self.isi()
        sisa = sum(1 for x in self.lig if x["hasil"] is None)
        self.l_status.setText(f"{len(self.lig)} ligan · {sisa} belum diprediksi")
        self.b_hitung.setEnabled(sisa > 0)

    def isi(self):
        t = self.tabel
        kol = ["Ligan"] + [AD.LABEL[k] for k, *_ in AD.SIFAT]
        t.setColumnCount(len(kol))
        t.setRowCount(len(self.lig))
        for c, (k, label, kel, jenis, _a) in enumerate(AD.SIFAT, 1):
            it = QTableWidgetItem(f"{kel}\n{_pendek(label)}")
            it.setToolTip(f"{kel}: {label}")
            t.setHorizontalHeaderItem(c, it)
        t.setHorizontalHeaderItem(0, QTableWidgetItem("Ligan"))
        tebal = QFont()
        tebal.setBold(True)
        for r, x in enumerate(self.lig):
            it = QTableWidgetItem(x["nama"])
            t.setItem(r, 0, it)
            for c, (k, *_r) in enumerate(AD.SIFAT, 1):
                v = (x["hasil"] or {}).get(k) if x["hasil"] else None
                it = QTableWidgetItem(AD.teks_nilai(k, v) if x["hasil"] else "")
                it.setTextAlignment(Qt.AlignCenter)
                w = AD.warna(k, v)
                if w:
                    it.setForeground(QColor(w))
                    it.setFont(tebal)
                t.setItem(r, c, it)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        t.horizontalHeader().setMinimumHeight(44)
        if self.lig:
            t.selectRow(0)
            self.profil(0)

    def profil(self, r):
        if r < 0 or r >= len(self.lig):
            return
        x = self.lig[r]
        self._peta_muat(x)
        o = [f"<p style='font-size:14px;font-weight:600'>{escape(x['nama'])}</p>"
             f"<p style='color:#5b6b82;font-family:Consolas'>{escape(x['smiles'][:120])}</p>"]
        if not x["hasil"]:
            o.append("<p>Belum diprediksi. Klik <b>Prediksi</b>.</p>")
        else:
            for kel in AD.KELOMPOK:
                o.append(f"<p style='margin-top:8px'><b>{kel}</b></p><table cellspacing=2 width='100%'>")
                for k, label, kk, jenis, _a in AD.SIFAT:
                    if kk != kel:
                        continue
                    v = x["hasil"].get(k)
                    w = AD.warna(k, v) or kit.hx("ink2")
                    o.append(f"<tr><td width='70%'>{escape(label)}</td><td align=right style='color:{w};font-weight:600'>"
                             f"{escape(AD.teks_nilai(k, v))}</td><td style='color:#5b6b82'>"
                             f"{'' if jenis == 'p' else escape(jenis)}</td></tr>")
                o.append("</table>")
        o.append(f"<p style='color:#5b6b82;font-size:9pt;margin-top:10px'>Sitasi: {escape(AD.SITASI)}</p>")
        self.info.setHtml("".join(o))

    def hitung(self, semua):
        if not AD.tersedia():
            self.jw._galat("Paket ADMET-AI tidak terpasang di instalasi ini.")
            return
        target = [x for x in self.lig if semua or x["hasil"] is None]
        if not target:
            return
        self.b_hitung.setEnabled(False)
        self.l_status.setText(f"Memprediksi {len(target)} ligan (memuat model ±10-20 s)…")

        def selesai(hasil):
            for x, h in zip(target, hasil):
                x["hasil"] = h
                if x["lig"] is not None:
                    x["lig"]["admet"] = {"v": AD.VERSI, "smiles": x["smiles"], "hasil": h}
            self.jw.minta_simpan()
            self.isi()
            self.l_status.setText(f"{len(target)} ligan diprediksi")
            self.jw.log.tulis(f"ADMET-AI: {len(target)} ligan diprediksi")

        def galat(g):
            self.b_hitung.setEnabled(True)
            self.l_status.setText("")
            self.jw._galat("Prediksi ADMET gagal:\n" + str(g).strip()[-800:])

        kerja.jalankan(AD.prediksi, [x["smiles"] for x in target], selesai=selesai, galat=galat,
                       log=self.l_status.setText)

    def ekspor(self):
        f = self.jw._path("Ekspor ADMET", "admet_ai.csv", "CSV (*.csv)")
        if not f:
            return
        with open(f, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["Ligan", "SMILES"] + [f"{kel}: {label}" for _k, label, kel, *_ in AD.SIFAT])
            for x in self.lig:
                w.writerow([x["nama"], x["smiles"]] + [AD.teks_nilai(k, (x["hasil"] or {}).get(k)) if x["hasil"]
                                                       else "" for k, *_ in AD.SIFAT])
        self.jw.log.tulis(f"ADMET diekspor: {f}")


def _pendek(label):
    t = label.split(" (")[0]
    return t if len(t) <= 22 else t[:21] + "…"
