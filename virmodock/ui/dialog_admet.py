"""Dialog Prediksi ADMET (Analisis › Prediksi ADMET (ADMET-AI)…).

Tabel ligan × 30 sifat ADMET (dikelompokkan Absorpsi/Distribusi/Metabolisme/Ekskresi/Toksisitas), sel probabilitas
diwarnai (hijau = menguntungkan, merah = berisiko); panel kanan = profil ligan terpilih. Hasil disimpan di
proyek.ligan[*]['admet'] (cache per SMILES). Prediksi berjalan di proses terpisah (core.admet).
"""
import csv
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QSplitter, QTableWidget,
                               QTableWidgetItem, QTextBrowser, QVBoxLayout)

from ..core import admet as AD
from . import kerja


class DialogAdmet(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Prediksi ADMET — ADMET-AI")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1280, 760)
        self.lig = []          # [{nama, smiles, lig (dict proyek | None), hasil}]
        lay = QVBoxLayout(self)
        ket = QLabel("Prediksi model pembelajaran mesin (Chemprop-RDKit, 41 dataset TDC). Angka 0–1 = probabilitas "
                     "kelas; warna hijau = menguntungkan, merah = berisiko. Ini skrining awal, bukan pengganti uji "
                     "in vitro/in vivo.")
        ket.setWordWrap(True)
        ket.setObjectName("muted")
        lay.addWidget(ket)
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
        lay.addWidget(bagi, 1)
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
        b_tutup = QPushButton("Tutup")
        b_tutup.clicked.connect(self.close)
        for b in (self.b_hitung, b_ulang, b_csv, b_tutup):
            h.addWidget(b)
        lay.addLayout(h)
        self.muat()

    def muat(self):
        from rdkit import Chem
        from ..core import kemiripan as K
        from ..core.sifat import netralkan
        self.lig = []
        for _k, nama, teks, fmt, l in self.jw._sumber_sifat():
            try:
                # bentuk netral (fragmen terbesar, tanpa protonasi pH): model dilatih pada struktur netral
                smi = Chem.MolToSmiles(netralkan(K.mol_dari(teks, fmt)))
            except Exception:
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
                    w = AD.warna(k, v) or "#465263"
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
        self.l_status.setText(f"Memprediksi {len(target)} ligan (memuat model ±10–20 s)…")

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
