"""Dialog Farmakologi Jaringan: satu jendela untuk seluruh alur senyawa - target - jalur - penyakit.

Tujuh tahap, satu tab masing-masing, dikerjakan berurutan dari kiri ke kanan:

  1 Senyawa          kumpulkan senyawa (tanaman obat, pustaka, proyek, atau berkas) beserta SMILES
  2 Saring ADMET     buang kandidat yang sifat fisikokimia dan prediksi ADMET-nya tidak memenuhi syarat
  3 Target senyawa   target dugaan dari kemiripan ligan ChEMBL dan/atau interaksi terkurasi CTD
  4 Gen penyakit     gen penyakit dari Open Targets atau impor CSV, lalu irisan (diagram Venn)
  5 Jaringan PPI     tepi STRING antar target irisan, graf interaktif, peringkat protein hub
  6 Jalur            pengayaan jalur Reactome / GO-BP (hipergeometrik + Benjamini-Hochberg)
  7 Laporan          ringkasan tiap tahap, paragraf metode siap tempel, dan ekspor

Perhitungan ada di core.farmakologi, core.jaringan, core.ctd, core.pengayaan, core.venn, dan core.graf;
berkas ini hanya antarmuka. Setiap tahap yang menyentuh internet dijalankan di thread pool (ui.kerja)
agar jendela utama tidak pernah membeku.
"""
from typing import Any, Dict, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QProgressBar, QSpinBox, QSplitter, QTabWidget,
                               QVBoxLayout, QWidget)

from ..core import ctd, farmakologi as F, figur_jaringan as FG, graf as M_graf, jaringan, venn
from . import kerja, kit
from .widget_graf import WARNA_JENIS, TampilanGraf

PERINGATAN = ("Hasil farmakologi jaringan adalah hipotesis komputasi hasil penambangan basis data, bukan bukti "
              "aktivitas biologis. Tepi STRING memuat bukti penambangan teks dan ko-ekspresi — bukan hanya "
              "interaksi fisik — dan dosis, metabolisme, serta waktu dan lokasi di tubuh tidak diperhitungkan. "
              "Klaim mekanisme memerlukan validasi eksperimental.")


class DialogFarmakologi(QDialog):
    """Jendela alur farmakologi jaringan."""

    keadaanBerubah = Signal(dict)

    def __init__(self, parent=None, proyek=None):
        super().__init__(parent)
        self.jw = parent
        self.proyek = proyek if proyek is not None else getattr(parent, "proyek", None)
        self.setWindowTitle("Farmakologi jaringan")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.resize(1180, 780)

        tersimpan = getattr(self.proyek, "farmakologi", None) if self.proyek else None
        self.k: Dict[str, Any] = F.migrasi(tersimpan)
        self._jejak: List[Dict[str, Any]] = []
        self._graf = None
        self._sibuk = False
        self._hasil_cari_penyakit: List[Dict[str, Any]] = []

        self._bangun_ui()
        self._muat_keadaan()

    # ================================================================ kerangka
    def _bangun_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul("Farmakologi jaringan",
                                "Satu senyawa bekerja lewat banyak target dan banyak jalur — "
                                "alur ini menelusuri rantai senyawa › target › jalur › penyakit"))
        lay.addWidget(kit.catatan(PERINGATAN, jenis="peringatan"))

        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        for judul, bangun in (("1 · Senyawa", self._tab_senyawa),
                              (kit.amp("2 · Saring ADMET"), self._tab_admet),
                              ("3 · Target senyawa", self._tab_target),
                              (kit.amp("4 · Gen penyakit & irisan"), self._tab_penyakit),
                              ("5 · Jaringan PPI", self._tab_jaringan),
                              ("6 · Jalur", self._tab_jalur),
                              ("7 · Figur", self._tab_figur),
                              ("8 · Laporan", self._tab_laporan)):
            w = QWidget()
            bangun(w)
            self.tabs.addTab(w, judul)

        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setVisible(False)
        self.bar.setMaximumHeight(4)
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar)

        self.l_status = QLabel("")
        self.l_status.setObjectName("subjudul")
        self.l_status.setWordWrap(True)
        lay.addWidget(self.l_status)
        lay.addLayout(kit.bar_bawah(self, kiri=(self.l_status,),
                                    kanan=(kit.tombol("Simpan ke proyek", self._simpan, utama=True,
                                                      tip="Simpan keadaan alur ini ke dalam berkas proyek"),)))

    def _mulai(self, teks: str):
        self._sibuk = True
        self.bar.setVisible(True)
        self.l_status.setText(teks)

    def _henti(self, teks: str = ""):
        self._sibuk = False
        self.bar.setVisible(False)
        if teks:
            self.l_status.setText(teks)

    def _galat(self, pesan: str):
        self._henti("")
        kit.pesan_peringatan(self, str(pesan).split("\n")[0], "Tahap gagal")
        self.l_status.setText(str(pesan).split("\n")[0])

    def _catat(self, teks: str):
        self.l_status.setText(teks)
        if self.jw is not None and hasattr(self.jw, "log"):
            self.jw.log.tulis(f"Farmakologi jaringan: {teks}")

    # ================================================================ 1. senyawa
    def _tab_senyawa(self, w):
        v = QVBoxLayout(w)
        v.setSpacing(8)
        baris = QHBoxLayout()
        baris.addWidget(QLabel("Sumber senyawa:"))
        self.e_tanaman = QLineEdit()
        self.e_tanaman.setPlaceholderText("mis. Curcuma longa (kunyit) — dicatat di paragraf metode")
        baris.addWidget(self.e_tanaman, 1)
        v.addLayout(baris)

        aksi = QHBoxLayout()
        aksi.addWidget(kit.tombol("Senyawa tanaman obat…", self._dari_tanaman,
                                  tip="Cari senyawa bahan alam dari takson tanaman (LOTUS/Wikidata, COCONUT)"))
        aksi.addWidget(kit.tombol("Ambil ligan proyek", self._dari_proyek,
                                  tip="Pakai ligan yang sudah ada di proyek docking ini"))
        aksi.addWidget(kit.tombol("Impor CSV/TSV…", self._impor_senyawa,
                                  tip="Berkas dengan kolom nama dan SMILES, mis. ekspor KNApSAcK yang sudah "
                                      "dilengkapi SMILES dari PubChem"))
        aksi.addWidget(kit.tombol("Kosongkan", self._kosongkan_senyawa))
        aksi.addStretch(1)
        v.addLayout(aksi)

        self.t_senyawa = kit.tabel(["Nama", "SMILES", "Sumber"], regang=1, urut=True)
        v.addWidget(self.t_senyawa, 1)
        self.l_senyawa = kit.catatan("Belum ada senyawa.")
        v.addWidget(self.l_senyawa)

    def _dari_tanaman(self):
        """Pinjam dialog senyawa tanaman yang sudah ada; hasilnya masuk ke daftar alur ini."""
        if self.jw is None:
            return
        try:
            from .dialog_tanaman import DialogTanaman
        except Exception as e:
            kit.pesan_peringatan(self, f"Dialog senyawa tanaman tidak bisa dibuka: {e}")
            return
        d = DialogTanaman(self.jw)
        # DialogTanaman menambahkan senyawa terpilih ke proyek; setelah ditutup, ambil dari proyek.
        d.exec()
        self._dari_proyek()

    def _dari_proyek(self):
        baris = []
        for lig in (kit.ligan_proyek(self.jw, dengan_mol=False) if self.jw is not None else []):
            baris.append({"nama": lig.get("nama"), "smiles": lig.get("smiles"), "sumber": "proyek"})
        if not baris:
            kit.pesan_peringatan(self, "Proyek ini belum punya ligan dengan SMILES.")
            return
        self._tambah_senyawa(F.senyawa_dari_daftar(baris))

    def _impor_senyawa(self):
        path, _ = QFileDialog.getOpenFileName(self, "Impor daftar senyawa", "",
                                              "Tabel senyawa (*.csv *.tsv *.txt);;Semua berkas (*)")
        if not path:
            return
        try:
            baru = F.impor_senyawa_csv(path)
        except F.GalatFarmakologi as e:
            kit.pesan_peringatan(self, str(e))
            return
        self._tambah_senyawa(baru)

    def _tambah_senyawa(self, baru: List[Dict[str, Any]]):
        ada = {s["smiles"] for s in self.k["senyawa"]}
        tambah = [s for s in baru if s["smiles"] not in ada]
        # Nama tetap unik walau ditambahkan dari beberapa sumber berurutan (peta target berkunci nama).
        dipakai = {s["nama"] for s in self.k["senyawa"]}
        for s in tambah:
            if s["nama"] in dipakai:
                n = 2
                while f"{s['nama']} ({n})" in dipakai:
                    n += 1
                s["nama"] = f"{s['nama']} ({n})"
            dipakai.add(s["nama"])
        self.k["senyawa"].extend(tambah)
        self._isi_tabel_senyawa()
        self._catat(f"{len(tambah)} senyawa baru ditambahkan ({len(baru) - len(tambah)} duplikat dilewati).")

    def _kosongkan_senyawa(self):
        self.k["senyawa"] = []
        self._isi_tabel_senyawa()

    def _isi_tabel_senyawa(self):
        t = self.t_senyawa
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for s in self.k["senyawa"]:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, kit.sel(s["nama"]))
            t.setItem(r, 1, kit.sel(s["smiles"]))
            t.setItem(r, 2, kit.sel(s.get("sumber") or "–"))
        t.setSortingEnabled(True)
        n = len(self.k["senyawa"])
        self.l_senyawa.setText(f"{n} senyawa siap disaring." if n else "Belum ada senyawa.")

    # ================================================================ 2. saring ADMET
    def _tab_admet(self, w):
        v = QVBoxLayout(w)
        v.setSpacing(8)
        kotak = QGroupBox("Kriteria penyaringan")
        form = QFormLayout(kotak)
        self.sp_lipinski = QSpinBox()
        self.sp_lipinski.setRange(0, 4)
        self.sp_lipinski.setValue(F.KRITERIA_BAWAAN["lipinski_maks"])
        form.addRow(F.LABEL_KRITERIA["lipinski_maks"], self.sp_lipinski)
        self.sp_admet: Dict[str, QDoubleSpinBox] = {}
        for kunci in ("hia_min", "bioavailability_min", "dili_maks", "herg_maks", "ames_maks"):
            sp = QDoubleSpinBox()
            sp.setRange(0.0, 1.0)
            sp.setSingleStep(0.05)
            sp.setDecimals(2)
            sp.setValue(float(F.KRITERIA_BAWAAN[kunci]))
            self.sp_admet[kunci] = sp
            form.addRow(F.LABEL_KRITERIA[kunci], sp)
        self.cb_pains = QCheckBox("Buang senyawa yang kena peringatan PAINS")
        self.cb_pains.setChecked(bool(F.KRITERIA_BAWAAN["pains"]))
        form.addRow("", self.cb_pains)
        v.addWidget(kotak)

        aksi = QHBoxLayout()
        aksi.addWidget(kit.tombol("Hitung sifat && saring", self._jalankan_saring, utama=True,
                                  tip="Hitung sifat fisikokimia RDKit lalu terapkan kriteria di atas"))
        self.b_admet = kit.tombol("Prediksi ADMET (ADMET-AI)…", self._jalankan_admet,
                                  tip="Prediksi HIA, bioavailabilitas, DILI, hERG, dan Ames untuk senyawa yang ada")
        aksi.addWidget(self.b_admet)
        aksi.addStretch(1)
        v.addLayout(aksi)

        self.t_admet = kit.tabel(["Senyawa", "MW", "WLOGP", "TPSA", "Lipinski", "HIA", "DILI", "hERG",
                                  "Status", "Alasan"], regang=9, urut=True)
        v.addWidget(self.t_admet, 1)
        self.l_admet = kit.catatan("Senyawa yang nilai ADMET-nya belum ada tidak digugurkan karena itu — "
                                   "ketiadaan data bukan bukti buruk, hanya penyaringan yang belum lengkap.")
        v.addWidget(self.l_admet)

    def _kriteria(self) -> Dict[str, Any]:
        k = {"lipinski_maks": self.sp_lipinski.value(), "pains": self.cb_pains.isChecked()}
        k.update({kunci: sp.value() for kunci, sp in self.sp_admet.items()})
        return k

    def _jalankan_saring(self):
        if not self.k["senyawa"]:
            kit.pesan_peringatan(self, "Belum ada senyawa. Isi tahap 1 dulu.")
            return
        self._mulai("Menghitung sifat fisikokimia…")

        def kerjakan(lapor=None):
            F.hitung_sifat(self.k["senyawa"], lapor=lapor)
            return F.saring(self.k["senyawa"], self._kriteria())

        kerja.jalankan(kerjakan, selesai=self._saring_selesai, galat=self._galat,
                       progres=lambda i, n, t: self.l_status.setText(f"{t} {i}/{n}…"))

    def _saring_selesai(self, hasil):
        # hitung_sifat() dan saring() menyunting dict senyawa di tempat, jadi tidak ada yang perlu disalin.
        self._isi_tabel_admet()
        self._henti(f"{hasil['lolos']} senyawa lolos, {hasil['gagal']} gugur"
                    + (f"; {hasil['tanpa_admet']} belum punya nilai ADMET." if hasil["tanpa_admet"] else "."))

    def _jalankan_admet(self):
        from ..core import admet
        if not admet.tersedia():
            kit.pesan_peringatan(self, "ADMET-AI belum terpasang di lingkungan ini. Penyaringan tetap bisa "
                                       "dijalankan dengan aturan Lipinski dan PAINS saja.")
            return
        senyawa = [s for s in self.k["senyawa"] if s.get("smiles")]
        if not senyawa:
            return
        self._mulai(f"Memprediksi ADMET untuk {len(senyawa)} senyawa (proses terpisah)…")

        def kerjakan(lapor=None):
            nilai = admet.prediksi([s["smiles"] for s in senyawa], lapor=lapor)
            return nilai

        def selesai(nilai):
            if isinstance(nilai, dict):
                for s in senyawa:
                    s["admet"] = nilai.get(s["smiles"]) or {}
            elif isinstance(nilai, list):
                for s, n in zip(senyawa, nilai):
                    s["admet"] = n or {}
            F.saring(self.k["senyawa"], self._kriteria())
            self._isi_tabel_admet()
            self._henti("Prediksi ADMET selesai.")

        kerja.jalankan(kerjakan, selesai=selesai, galat=self._galat, log=self.l_status.setText)

    def _isi_tabel_admet(self):
        t = self.t_admet
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for s in self.k["senyawa"]:
            sf, ad = s.get("sifat") or {}, s.get("admet") or {}
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, kit.sel(s["nama"]))
            t.setItem(r, 1, kit.sel_angka(sf.get("mw"), 1))
            t.setItem(r, 2, kit.sel_angka(sf.get("wlogp"), 2))
            t.setItem(r, 3, kit.sel_angka(sf.get("tpsa"), 1))
            t.setItem(r, 4, kit.sel_angka(sf.get("lipinski"), 0))
            t.setItem(r, 5, kit.sel_angka(ad.get("HIA_Hou"), 2))
            t.setItem(r, 6, kit.sel_angka(ad.get("DILI"), 2))
            t.setItem(r, 7, kit.sel_angka(ad.get("hERG"), 2))
            t.setItem(r, 8, kit.sel("Lolos" if s.get("lolos") else "Gugur"))
            t.setItem(r, 9, kit.sel("; ".join(s.get("alasan") or []) or "–"))
        t.setSortingEnabled(True)

    # ================================================================ 3. target senyawa
    def _tab_target(self, w):
        v = QVBoxLayout(w)
        v.setSpacing(8)
        kotak = QGroupBox("Sumber target")
        form = QFormLayout(kotak)
        self.cb_kemiripan = QCheckBox("Kemiripan ligan ChEMBL (ECFP4, pChEMBL ≥ 6)")
        self.cb_kemiripan.setChecked(True)
        self.cb_kemiripan.setToolTip("Target yang terikat senyawa berstruktur mirip — padanan terbuka untuk "
                                     "SwissTargetPrediction")
        form.addRow(self.cb_kemiripan)
        self.cb_ctd = QCheckBox("Interaksi terkurasi CTD (berbasis literatur)")
        self.cb_ctd.setToolTip("Hubungan senyawa-gen yang dikurasi dari publikasi; dicari dengan nama senyawa")
        form.addRow(self.cb_ctd)
        self.sp_k = QSpinBox()
        self.sp_k.setRange(1, 50)
        self.sp_k.setValue(10)
        form.addRow("Target teratas per senyawa (kemiripan)", self.sp_k)
        v.addWidget(kotak)

        aksi = QHBoxLayout()
        aksi.addWidget(kit.tombol("Cari target", self._jalankan_target, utama=True))
        aksi.addWidget(kit.tombol("Impor CSV target…", self._impor_target,
                                  tip="Berkas dengan kolom nama senyawa dan simbol gen, mis. unduhan "
                                      "SwissTargetPrediction atau CTD yang Anda ambil sendiri"))
        aksi.addStretch(1)
        v.addLayout(aksi)

        self.t_target = kit.tabel(["Senyawa", "Jumlah target", "Gen"], regang=2, urut=True)
        v.addWidget(self.t_target, 1)
        self.l_target = kit.catatan("Belum ada target.")
        v.addWidget(self.l_target)

    def _jalankan_target(self):
        senyawa = F.yang_lolos(self.k["senyawa"]) or self.k["senyawa"]
        if not senyawa:
            kit.pesan_peringatan(self, "Belum ada senyawa. Isi tahap 1 dulu.")
            return
        if not (self.cb_kemiripan.isChecked() or self.cb_ctd.isChecked()):
            kit.pesan_peringatan(self, "Pilih setidaknya satu sumber target.")
            return
        pakai_kemiripan, pakai_ctd = self.cb_kemiripan.isChecked(), self.cb_ctd.isChecked()
        k_atas = self.sp_k.value()

        # Jalur kemiripan memakai beberapa permintaan ChEMBL per senyawa (kemiripan, aktivitas, target):
        # rata-rata 2,8 permintaan dan 5,9 detik per senyawa saat cache dingin, diukur pada 108 senyawa
        # Curcuma zedoaria. Untuk daftar panjang — satu takson mudah memberi ratusan senyawa —
        # perkiraannya ditunjukkan dulu supaya pengguna tidak terlanjur menunggu belasan menit.
        if pakai_kemiripan and len(senyawa) > 20:
            menit = max(1, round(len(senyawa) * 6 / 60))
            jawab = QMessageBox.question(
                self, "Daftar senyawa panjang",
                f"{len(senyawa)} senyawa akan ditanyakan ke ChEMBL satu per satu, perkiraan sekitar "
                f"{menit} menit saat pertama kali (berikutnya lebih cepat karena ada cache).\n\n"
                f"Banyak alur farmakologi jaringan cukup memakai senyawa utama saja. Lanjutkan?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if jawab != QMessageBox.Yes:
                return

        self._mulai(f"Mencari target untuk {len(senyawa)} senyawa…")

        def kerjakan(lapor=None):
            from ..core import target_balik
            peta: Dict[str, List[str]] = {}
            jejak: List[Dict[str, Any]] = []
            sumber: List[str] = []
            if pakai_kemiripan:
                sumber.append("kemiripan")
                for i, s in enumerate(senyawa, 1):
                    if lapor is not None:
                        lapor.progres.emit(i, len(senyawa), f"ChEMBL: {s['nama']}")
                    try:
                        hasil, j = target_balik.jalur_ligan(s["smiles"], k=k_atas,
                                                            lapor=lambda t: lapor and lapor.log.emit(t))
                    except Exception as e:
                        if lapor is not None:
                            lapor.log.emit(f"{s['nama']}: {e}")
                        continue
                    jejak += list(j or [])
                    gen = [h["gen"].upper() for h in hasil if h.get("gen")]
                    if gen:
                        peta.setdefault(s["nama"], [])
                        peta[s["nama"]] += [g for g in gen if g not in peta[s["nama"]]]
            if pakai_ctd:
                sumber.append("ctd")
                nama = [s["nama"] for s in senyawa if s.get("nama")]
                try:
                    baris, j = ctd.interaksi_senyawa(nama, lapor=lapor)
                    jejak += list(j or [])
                    for s_nama, gen in ctd.per_senyawa(baris).items():
                        cocok = next((s["nama"] for s in senyawa if s["nama"].lower() == str(s_nama).lower()), s_nama)
                        peta.setdefault(cocok, [])
                        peta[cocok] += [g for g in gen if g not in peta[cocok]]
                except ctd.GalatCtd as e:
                    if lapor is not None:
                        lapor.log.emit(f"CTD dilewati: {e}")
            return peta, jejak, sumber

        def selesai(hasil):
            peta, jejak, sumber = hasil
            self.k["target_senyawa"] = peta
            self.k["sumber_target"] = sumber
            self._jejak += jejak
            self._isi_tabel_target()
            n = len({g for d in peta.values() for g in d})
            self._henti(f"{n} gen target unik dari {len(peta)} senyawa."
                        if n else "Tidak ada target yang ditemukan untuk senyawa ini.")

        kerja.jalankan(kerjakan, selesai=selesai, galat=self._galat, log=self.l_status.setText,
                       progres=lambda i, n, t: self.l_status.setText(f"{t} ({i}/{n})"))

    def _impor_target(self):
        path, _ = QFileDialog.getOpenFileName(self, "Impor target senyawa", "",
                                              "Tabel target (*.csv *.tsv *.txt);;Semua berkas (*)")
        if not path:
            return
        import csv as _csv
        from pathlib import Path
        teks = Path(path).read_text(encoding="utf-8-sig", errors="replace")
        contoh = teks[:4096]
        pemisah = "\t" if contoh.count("\t") > max(contoh.count(";"), contoh.count(",")) \
            else (";" if contoh.count(";") > contoh.count(",") else ",")
        peta: Dict[str, List[str]] = {}
        for baris in _csv.DictReader(teks.splitlines(), delimiter=pemisah):
            nama = gen = ""
            for kolom, nilai in (baris or {}).items():
                kecil = (kolom or "").strip().lower()
                if not nama and kecil in ("senyawa", "compound", "chemical", "chemicalname", "nama", "input"):
                    nama = (nilai or "").strip()
                if not gen and kecil in ("gen", "gene", "gene symbol", "genesymbol", "symbol", "target", "common name"):
                    gen = (nilai or "").strip().upper()
            if gen:
                nama = nama or "Senyawa"
                peta.setdefault(nama, [])
                if gen not in peta[nama]:
                    peta[nama].append(gen)
        if not peta:
            kit.pesan_peringatan(self, "Tidak ada kolom simbol gen yang bisa dibaca dari berkas itu.")
            return
        self.k["target_senyawa"] = peta
        self.k["sumber_target"] = ["impor"]
        self._isi_tabel_target()
        self._catat(f"{len({g for d in peta.values() for g in d})} gen target diimpor.")

    def _isi_tabel_target(self):
        t = self.t_target
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for nama, gen in (self.k.get("target_senyawa") or {}).items():
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, kit.sel(nama))
            t.setItem(r, 1, kit.sel_angka(len(gen), 0))
            t.setItem(r, 2, kit.sel(", ".join(gen)))
        t.setSortingEnabled(True)
        n = len({g for d in (self.k.get("target_senyawa") or {}).values() for g in d})
        self.l_target.setText(f"{n} gen target unik." if n else "Belum ada target.")

    # ================================================================ 4. gen penyakit & irisan
    def _tab_penyakit(self, w):
        v = QVBoxLayout(w)
        v.setSpacing(8)
        cari = QHBoxLayout()
        self.e_penyakit = QLineEdit()
        self.e_penyakit.setPlaceholderText("Nama penyakit, mis. colorectal cancer")
        self.e_penyakit.returnPressed.connect(self._cari_penyakit)
        cari.addWidget(self.e_penyakit, 1)
        cari.addWidget(kit.tombol("Cari di Open Targets", self._cari_penyakit))
        cari.addWidget(kit.tombol("Impor CSV gen…", self._impor_gen_penyakit,
                                  tip="Ekspor GeneCards, DisGeNET, atau OMIM milik Anda sendiri. "
                                      "GeneCards berlisensi berbayar dan melarang pengambilan otomatis, "
                                      "jadi VirmoLab tidak menghubunginya."))
        v.addLayout(cari)

        self.lw_penyakit = QListWidget()
        self.lw_penyakit.setMaximumHeight(110)
        self.lw_penyakit.itemDoubleClicked.connect(lambda _: self._ambil_gen_penyakit())
        v.addWidget(self.lw_penyakit)

        baris = QHBoxLayout()
        baris.addWidget(QLabel("Skor asosiasi minimum:"))
        self.sp_skor = QDoubleSpinBox()
        self.sp_skor.setRange(0.0, 1.0)
        self.sp_skor.setSingleStep(0.05)
        self.sp_skor.setDecimals(2)
        self.sp_skor.setValue(0.10)
        baris.addWidget(self.sp_skor)
        baris.addWidget(QLabel("Batas gen:"))
        self.sp_maks_gen = QSpinBox()
        self.sp_maks_gen.setRange(10, 500)
        self.sp_maks_gen.setSingleStep(50)
        self.sp_maks_gen.setValue(500)
        self.sp_maks_gen.setToolTip("Jumlah gen teratas yang diminta dari Open Targets (batas layanan 500). "
                                    "Bila hasilnya pas sebanyak ini, daftarnya kemungkinan terpotong.")
        baris.addWidget(self.sp_maks_gen)
        baris.addWidget(kit.tombol("Ambil gen penyakit", self._ambil_gen_penyakit, utama=True))
        baris.addStretch(1)
        v.addLayout(baris)

        pisah = QSplitter(Qt.Horizontal)
        kiri = QWidget()
        kv = QVBoxLayout(kiri)
        kv.setContentsMargins(0, 0, 0, 0)
        self.t_penyakit = kit.tabel(["Gen", "Skor", "Sumber"], regang=2, urut=True)
        kv.addWidget(self.t_penyakit, 1)
        pisah.addWidget(kiri)

        kanan = QWidget()
        kn = QVBoxLayout(kanan)
        kn.setContentsMargins(0, 0, 0, 0)
        self.g_venn = kit.GambarSvg()
        kn.addWidget(self.g_venn, 1)
        self.t_irisan = kit.tabel(["Target potensial"], urut=True)
        self.t_irisan.setMaximumHeight(170)
        kn.addWidget(self.t_irisan)
        pisah.addWidget(kanan)
        pisah.setSizes([420, 620])
        v.addWidget(pisah, 1)

        self.l_irisan = kit.catatan("Irisan target senyawa dengan gen penyakit disebut potential therapeutic target.")
        v.addWidget(self.l_irisan)

    def _cari_penyakit(self):
        nama = self.e_penyakit.text().strip()
        if not nama:
            return
        self._mulai(f"Mencari penyakit '{nama}' di Open Targets…")

        def kerjakan(lapor=None):
            return jaringan.cari_penyakit(nama)

        def selesai(hasil):
            daftar, jejak = hasil
            self._jejak += list(jejak or [])
            self._hasil_cari_penyakit = daftar
            self.lw_penyakit.clear()
            for d in daftar:
                it = QListWidgetItem(f"{d['nama']}  ·  {d['id']}")
                it.setToolTip(d.get("keterangan") or "")
                it.setData(Qt.UserRole, d)
                self.lw_penyakit.addItem(it)
            if daftar:
                self.lw_penyakit.setCurrentRow(0)
            self._henti(f"{len(daftar)} penyakit cocok." if daftar else "Tidak ada penyakit yang cocok.")

        kerja.jalankan(kerjakan, selesai=selesai, galat=self._galat)

    def _ambil_gen_penyakit(self):
        it = self.lw_penyakit.currentItem()
        if it is None:
            kit.pesan_peringatan(self, "Pilih dulu salah satu penyakit dari hasil pencarian.")
            return
        d = it.data(Qt.UserRole)
        ambang = self.sp_skor.value()
        maks = int(self.sp_maks_gen.value())
        self._mulai(f"Mengambil gen yang berasosiasi dengan {d['nama']}…")

        def kerjakan(lapor=None):
            return jaringan.target_penyakit(d["id"], maks=maks, ambang=ambang)

        def selesai(hasil):
            baris, jejak = hasil
            self._jejak += list(jejak or [])
            self.k["penyakit"] = {"id": d["id"], "nama": d["nama"], "sumber": "Open Targets Platform"}
            self.k["gen_penyakit"] = [{"gen": b["gen"], "skor": b["skor"], "sumber": "Open Targets"} for b in baris]
            self._hitung_irisan()
            pesan = f"{len(baris)} gen penyakit (skor ≥ {ambang:g})."
            # Open Targets memulangkan daftar terurut skor; bila jumlahnya pas batas, daftarnya terpotong
            # dan gen di bawah batas itu tidak pernah diadu dengan target senyawa. Diberitahukan di tempat
            # (bukan kotak dialog) supaya tidak memotong alur kerja saat pengguna memang sengaja membatasi.
            if len(baris) >= maks:
                pesan += f" Daftar terpotong di batas {maks}."
                kit.ganti_jenis(self.l_irisan, "peringatan")
                self.l_irisan.setText(
                    f"{self.l_irisan.text()}  Daftar gen penyakit mencapai batas {maks} dan kemungkinan "
                    f"terpotong: gen dengan skor di bawah yang terakhir diambil tidak ikut diiriskan. "
                    f"Naikkan 'Batas gen' atau 'Skor asosiasi minimum'.")
            self._henti(pesan)

        kerja.jalankan(kerjakan, selesai=selesai, galat=self._galat)

    def _impor_gen_penyakit(self):
        path, _ = QFileDialog.getOpenFileName(self, "Impor gen penyakit", "",
                                              "Tabel gen (*.csv *.tsv *.txt);;Semua berkas (*)")
        if not path:
            return
        try:
            baris = F.impor_gen_penyakit(path)
        except F.GalatFarmakologi as e:
            kit.pesan_peringatan(self, str(e))
            return
        from pathlib import Path
        self.k["gen_penyakit"] = baris
        if not (self.k.get("penyakit") or {}).get("nama"):
            self.k["penyakit"] = {"id": "", "nama": self.e_penyakit.text().strip() or "penyakit yang diteliti",
                                  "sumber": Path(path).name}
        self._hitung_irisan()
        self._catat(f"{len(baris)} gen penyakit diimpor dari {Path(path).name}.")

    def _hitung_irisan(self):
        hasil = F.irisan(self.k.get("target_senyawa") or {}, self.k.get("gen_penyakit") or [])
        self.k["irisan"] = hasil["irisan"]

        t = self.t_penyakit
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for b in self.k["gen_penyakit"]:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, kit.sel(b["gen"]))
            t.setItem(r, 1, kit.sel_angka(b.get("skor"), 3))
            t.setItem(r, 2, kit.sel(b.get("sumber") or "–"))
        t.setSortingEnabled(True)

        t2 = self.t_irisan
        t2.setSortingEnabled(False)
        t2.setRowCount(0)
        for g in hasil["irisan"]:
            r = t2.rowCount()
            t2.insertRow(r)
            t2.setItem(r, 0, kit.sel(g))
        t2.setSortingEnabled(True)

        himpunan = {"Target senyawa": hasil["target"], "Gen penyakit": hasil["penyakit"]}
        self.g_venn.atur_pembuat(lambda l, t_, h=himpunan: venn.svg(h, lebar=max(240, l), tinggi=max(180, t_),
                                                                    mode=kit.mode(), judul="Irisan target"))
        kit.ganti_jenis(self.l_irisan, "muted")
        self.l_irisan.setText(f"{len(hasil['irisan'])} target terapi potensial dari "
                              f"{len(hasil['target'])} target senyawa dan {len(hasil['penyakit'])} gen penyakit.")

    # ================================================================ 5. jaringan PPI
    def _tab_jaringan(self, w):
        v = QVBoxLayout(w)
        v.setSpacing(8)
        baris = QHBoxLayout()
        baris.addWidget(QLabel("Skor gabungan STRING minimum:"))
        self.sp_string = QDoubleSpinBox()
        self.sp_string.setRange(0.15, 0.99)
        self.sp_string.setSingleStep(0.05)
        self.sp_string.setDecimals(2)
        self.sp_string.setValue(jaringan.AMBANG_STRING)
        self.sp_string.setToolTip("0,40 medium; 0,70 high — ambang yang lazim dipakai publikasi; 0,90 highest")
        baris.addWidget(self.sp_string)
        self.cb_lapisan = QCheckBox("Sertakan lapisan senyawa, jalur, dan penyakit")
        self.cb_lapisan.setChecked(True)
        baris.addWidget(self.cb_lapisan)
        baris.addWidget(kit.tombol("Bangun jaringan", self._bangun_jaringan, utama=True))
        self.cb_label = QCheckBox("Label")
        self.cb_label.setChecked(True)
        self.cb_label.toggled.connect(lambda on: self.graf.set_label(on))
        baris.addWidget(self.cb_label)
        baris.addWidget(kit.tombol("Pas-kan", lambda: self.graf.muat_penuh()))
        baris.addStretch(1)
        v.addLayout(baris)

        pisah = QSplitter(Qt.Horizontal)
        self.graf = TampilanGraf()
        self.graf.simpulDipilih.connect(self._simpul_dipilih)
        pisah.addWidget(self.graf)
        kanan = QWidget()
        kn = QVBoxLayout(kanan)
        kn.setContentsMargins(0, 0, 0, 0)
        kn.addWidget(QLabel("Protein hub (peringkat MCC)"))
        self.t_hub = kit.tabel(["Gen", "MCC", "Derajat", "Betweenness", "Closeness"], urut=True)
        self.t_hub.setSelectionMode(QAbstractItemView.SingleSelection)
        self.t_hub.itemSelectionChanged.connect(self._hub_dipilih)
        kn.addWidget(self.t_hub, 1)
        pisah.addWidget(kanan)
        pisah.setSizes([720, 380])
        v.addWidget(pisah, 1)

        aksi = QHBoxLayout()
        aksi.addWidget(kit.tombol("Ekspor GraphML (Cytoscape)…", self._ekspor_graphml))
        aksi.addWidget(kit.tombol("Ekspor CSV tepi…", self._ekspor_tepi))
        aksi.addWidget(kit.tombol("Ekspor gambar PNG…", self._ekspor_png))
        aksi.addStretch(1)
        v.addLayout(aksi)
        self.l_jaringan = kit.catatan("Jaringan belum dibangun.")
        v.addWidget(self.l_jaringan)

    def _bangun_jaringan(self):
        gen = list(self.k.get("irisan") or [])
        if not gen:
            gen = sorted({g for d in (self.k.get("target_senyawa") or {}).values() for g in d})
        if len(gen) < 2:
            kit.pesan_peringatan(self, "Perlu setidaknya dua gen. Lengkapi tahap 3 dan 4 dulu.")
            return
        ambang = self.sp_string.value()
        berlapis = self.cb_lapisan.isChecked()
        self._mulai(f"Mengambil tepi STRING untuk {len(gen)} gen…")

        def kerjakan(lapor=None):
            tepi, jejak = jaringan.tepi_string(gen, ambang=ambang)
            return tepi, jejak

        def selesai(hasil):
            tepi, jejak = hasil
            self._jejak += list(jejak or [])
            self.k["tepi_ppi"] = [[a, b, s] for a, b, s in tepi]
            self.k["ambang_string"] = ambang
            if berlapis:
                senyawa = {n: [g for g in d if g in set(gen)] for n, d in (self.k.get("target_senyawa") or {}).items()}
                senyawa = {n: d for n, d in senyawa.items() if d}
                G = jaringan.bangun(senyawa or {"Senyawa": gen}, jalur=self.k.get("jalur") or None,
                                    tepi_ppi=tepi, penyakit=[])
            else:
                G = F.graf_ppi(gen, tepi)
            self._graf = G
            self.graf.set_graf(G, mode=kit.mode(), tampilkan_label=self.cb_label.isChecked())
            G_ppi = F.graf_ppi(gen, tepi)
            self.k["hub"] = F.hub(G_ppi, n=30)
            sendiri = F.terpencil(G_ppi)
            self._isi_tabel_hub()
            pesan = f"{G.number_of_nodes()} simpul, {G.number_of_edges()} tepi (STRING ≥ {ambang:g})."
            if sendiri:
                # Dilaporkan, bukan disembunyikan: tanpa tepi belum tentu tidak berperan — bisa jadi
                # ambang STRING-nya yang terlalu tinggi untuk pasangan itu.
                pesan += (f" {len(sendiri)} target tanpa tepi PPI pada ambang ini "
                          f"({', '.join(sendiri[:6])}{'…' if len(sendiri) > 6 else ''}) "
                          f"— turunkan ambang bila ingin menyertakannya.")
            self.l_jaringan.setText(pesan)
            self._henti(f"Jaringan dibangun: {len(tepi)} tepi PPI.")

        kerja.jalankan(kerjakan, selesai=selesai, galat=self._galat)

    def _isi_tabel_hub(self):
        t = self.t_hub
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for b in self.k.get("hub") or []:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, kit.sel(b["gen"]))
            t.setItem(r, 1, kit.sel_angka(b["mcc"], 1))
            t.setItem(r, 2, kit.sel_angka(b["derajat"], 0))
            t.setItem(r, 3, kit.sel_angka(b["betweenness"], 4))
            t.setItem(r, 4, kit.sel_angka(b["closeness"], 4))
        t.setSortingEnabled(True)

    def _hub_dipilih(self):
        baris = self.t_hub.currentRow()
        if baris < 0 or self._graf is None:
            return
        it = self.t_hub.item(baris, 0)
        if it is None:
            return
        nid = f"T:{it.text()}"
        if nid in self._graf:
            self.graf.pilih(nid)

    def _simpul_dipilih(self, nid, data):
        if not nid:
            self.l_jaringan.setText(f"{self._graf.number_of_nodes()} simpul, {self._graf.number_of_edges()} tepi."
                                    if self._graf is not None else "Jaringan belum dibangun.")
            return
        jenis = {"senyawa": "Senyawa", "target": "Target", "jalur": "Jalur", "penyakit": "Penyakit"}.get(
            data.get("jenis", ""), data.get("jenis", ""))
        derajat = self._graf.degree(nid) if self._graf is not None and nid in self._graf else 0
        self.l_jaringan.setText(f"{data.get('label', nid)} — {jenis}, {derajat} koneksi.")

    def _ekspor_graphml(self):
        if self._graf is None:
            kit.pesan_peringatan(self, "Bangun jaringannya dulu.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan GraphML", "jaringan.graphml", "GraphML (*.graphml)")
        if path:
            M_graf.ekspor_graphml(self._graf, path)
            self._catat(f"GraphML disimpan: {path}")

    def _ekspor_tepi(self):
        if self._graf is None:
            kit.pesan_peringatan(self, "Bangun jaringannya dulu.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan CSV tepi", "tepi_jaringan.csv", "CSV (*.csv)")
        if path:
            M_graf.ekspor_csv_tepi(self._graf, path)
            self._catat(f"CSV tepi disimpan: {path}")

    def _ekspor_png(self):
        if self._graf is None:
            kit.pesan_peringatan(self, "Bangun jaringannya dulu.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan gambar jaringan", "jaringan.png",
                                              "PNG (*.png);;TIFF (*.tif)")
        if path:
            self.graf.gambar_png(2400).save(path)
            self._catat(f"Gambar jaringan disimpan: {path}")

    # ================================================================ 6. jalur
    def _tab_jalur(self, w):
        v = QVBoxLayout(w)
        v.setSpacing(8)
        baris = QHBoxLayout()
        baris.addWidget(QLabel("Set gen:"))
        self.cb_gmt = QComboBox()
        self.cb_gmt.addItem("Reactome", "reactome")
        self.cb_gmt.addItem("Gene Ontology — Biological Process", "go_bp")
        baris.addWidget(self.cb_gmt)
        baris.addWidget(QLabel("q maksimum:"))
        self.sp_q = QDoubleSpinBox()
        self.sp_q.setRange(0.001, 1.0)
        self.sp_q.setSingleStep(0.01)
        self.sp_q.setDecimals(3)
        self.sp_q.setValue(0.05)
        baris.addWidget(self.sp_q)
        baris.addWidget(kit.tombol("Hitung pengayaan jalur", self._jalankan_jalur, utama=True))
        baris.addStretch(1)
        v.addLayout(baris)

        pisah = QSplitter(Qt.Vertical)
        self.t_jalur = kit.tabel(["Jalur", "Nama", "Tumpang tindih", "Ukuran set", "p", "q"], regang=1, urut=True)
        pisah.addWidget(self.t_jalur)
        self.g_jalur = kit.GambarSvg()
        pisah.addWidget(self.g_jalur)
        pisah.setSizes([420, 300])
        v.addWidget(pisah, 1)
        self.l_jalur = kit.catatan("Uji hipergeometrik satu sisi dengan koreksi Benjamini-Hochberg. "
                                   "Latar belakang adalah gabungan seluruh gen pada set gen yang dipilih.")
        v.addWidget(self.l_jalur)

    def _jalankan_jalur(self):
        gen = list(self.k.get("irisan") or []) or sorted(
            {g for d in (self.k.get("target_senyawa") or {}).values() for g in d})
        if not gen:
            kit.pesan_peringatan(self, "Belum ada gen untuk diuji. Lengkapi tahap 3 atau 4 dulu.")
            return
        nama_gmt, q_maks = self.cb_gmt.currentData(), self.sp_q.value()
        self._mulai(f"Menghitung pengayaan jalur untuk {len(gen)} gen…")

        def kerjakan(lapor=None):
            return F.jalur(gen, nama_gmt=nama_gmt, q_maks=q_maks, maks=40)

        def selesai(baris):
            self.k["jalur"] = baris
            self.k["gmt"] = nama_gmt
            self._isi_tabel_jalur()
            self._henti(f"{len(baris)} jalur dilaporkan." if baris else "Tidak ada jalur yang lolos ambang q.")

        kerja.jalankan(kerjakan, selesai=selesai, galat=self._galat)

    def _isi_tabel_jalur(self):
        baris = self.k.get("jalur") or []
        t = self.t_jalur
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for b in baris:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, kit.sel(b["jalur"]))
            t.setItem(r, 1, kit.sel(b["nama"]))
            t.setItem(r, 2, kit.sel_angka(b["n_overlap"], 0))
            t.setItem(r, 3, kit.sel_angka(b["n_set"], 0))
            t.setItem(r, 4, kit.sel_angka(b["p"], 4))
            t.setItem(r, 5, kit.sel_angka(b.get("q"), 4))
        t.setSortingEnabled(True)
        atas = baris[:15]
        if atas:
            from ..core import grafik
            label = [b["nama"][:48] for b in atas][::-1]
            nilai = [b["n_overlap"] for b in atas][::-1]
            self.g_jalur.atur_pembuat(
                lambda l, h: grafik.batang(label, nilai, lebar=max(320, l), tinggi=max(220, h),
                                           gelap=(kit.mode() == "gelap"),
                                           judul="Jumlah gen per jalur (15 teratas)"))

    # ================================================================ 7. figur
    def _tab_figur(self, w):
        v = QVBoxLayout(w)
        v.setSpacing(8)
        pisah = QSplitter(Qt.Horizontal)

        kiri = QWidget()
        kv = QVBoxLayout(kiri)
        kv.setContentsMargins(0, 0, 0, 0)
        kv.addWidget(QLabel("Pilih figur"))
        self.lw_figur = QListWidget()
        for d in FG.daftar():
            it = QListWidgetItem(d["nama"])
            it.setData(Qt.UserRole, d["kunci"])
            it.setToolTip(d["ket"])
            self.lw_figur.addItem(it)
        self.lw_figur.setCurrentRow(0)
        self.lw_figur.currentRowChanged.connect(lambda _=0: self._segarkan_figur())
        kv.addWidget(self.lw_figur, 1)
        self.l_figur_ket = kit.catatan("")
        kv.addWidget(self.l_figur_ket)
        pisah.addWidget(kiri)

        kanan = QWidget()
        kn = QVBoxLayout(kanan)
        kn.setContentsMargins(0, 0, 0, 0)
        self.g_figur = kit.GambarSvg()
        kn.addWidget(self.g_figur, 1)
        pisah.addWidget(kanan)
        pisah.setSizes([300, 820])
        v.addWidget(pisah, 1)

        aksi = QHBoxLayout()
        aksi.addWidget(QLabel("Jumlah butir:"))
        self.sp_figur_n = QSpinBox()
        self.sp_figur_n.setRange(3, 40)
        self.sp_figur_n.setValue(10)
        self.sp_figur_n.setToolTip("Berapa protein hub atau jalur yang digambar")
        self.sp_figur_n.valueChanged.connect(lambda _=0: self._segarkan_figur())
        aksi.addWidget(self.sp_figur_n)
        aksi.addWidget(kit.tombol("Segarkan", self._segarkan_figur))
        aksi.addStretch(1)
        aksi.addWidget(QLabel("DPI:"))
        self.sp_dpi = QSpinBox()
        self.sp_dpi.setRange(96, 1200)
        self.sp_dpi.setSingleStep(100)
        self.sp_dpi.setValue(600)
        self.sp_dpi.setToolTip("Resolusi ekspor raster; kebanyakan jurnal meminta 300–600 dpi")
        aksi.addWidget(self.sp_dpi)
        aksi.addWidget(kit.tombol("Simpan SVG/PNG…", self._simpan_figur, utama=True))
        aksi.addWidget(kit.tombol("Simpan semua…", self._simpan_semua_figur,
                                  tip="Tulis seluruh figur yang datanya sudah ada ke satu folder"))
        v.addLayout(aksi)

    def _svg_figur(self, kunci: str, lebar: int = 860, tinggi: int = 600) -> str:
        """Bangun SVG satu figur dari keadaan alur saat ini. Kembalikan "" bila datanya belum ada."""
        gelap = kit.mode() == "gelap"
        n = self.sp_figur_n.value()
        if kunci == "venn":
            hasil = F.irisan(self.k.get("target_senyawa") or {}, self.k.get("gen_penyakit") or [])
            if not (hasil["target"] or hasil["penyakit"]):
                return ""
            return venn.svg({"Target senyawa": hasil["target"], "Gen penyakit": hasil["penyakit"]},
                            lebar=lebar, tinggi=tinggi, mode=kit.mode(), judul="Irisan target")
        if kunci == "jaringan":
            if self._graf is None or self._graf.number_of_nodes() == 0:
                return ""
            warna_simpul = {nd: WARNA_JENIS.get(d.get("jenis", ""), WARNA_JENIS[""])
                            for nd, d in self._graf.nodes(data=True)}
            label = {nd: d.get("label", nd) for nd, d in self._graf.nodes(data=True)}
            return M_graf.svg_graf(self._graf, warna_simpul=warna_simpul, label=label,
                                   lebar=lebar, tinggi=tinggi, tema=kit.mode())
        if kunci == "hub":
            if not self.k.get("hub"):
                return ""
            return FG.lingkar_hub(self.k["hub"], [tuple(t) for t in (self.k.get("tepi_ppi") or [])],
                                  n=n, lebar=min(lebar, 680), tinggi=tinggi, gelap=gelap,
                                  judul=f"Protein paling sentral ({min(n, len(self.k['hub']))} teratas, MCC)")
        if kunci == "gelembung":
            if not self.k.get("jalur"):
                return ""
            return FG.gelembung_jalur(self.k["jalur"], n=n, lebar=lebar, tinggi=tinggi, gelap=gelap,
                                      judul="Pengayaan jalur")
        if kunci == "batang":
            if not self.k.get("jalur"):
                return ""
            return FG.batang_jalur(self.k["jalur"], n=n, lebar=lebar, tinggi=tinggi, gelap=gelap,
                                   judul="Jumlah gen per jalur")
        return ""

    def _segarkan_figur(self):
        it = self.lw_figur.currentItem() if hasattr(self, "lw_figur") else None
        if it is None:
            return
        kunci = it.data(Qt.UserRole)
        ket = next((d["ket"] for d in FG.daftar() if d["kunci"] == kunci), "")
        contoh = self._svg_figur(kunci)
        if not contoh:
            self.l_figur_ket.setText(f"{ket}  Datanya belum ada — selesaikan tahap yang bersangkutan dulu.")
            self.g_figur.atur_pembuat(lambda l, t: "")
            self.g_figur.update()
            return
        self.l_figur_ket.setText(ket)
        self.g_figur.atur_pembuat(
            lambda l, t, k=kunci: self._svg_figur(k, lebar=max(360, l), tinggi=max(260, t)) or "")

    def _simpan_figur(self):
        it = self.lw_figur.currentItem()
        if it is None:
            return
        kunci = it.data(Qt.UserRole)
        svg = self._svg_figur(kunci, lebar=900, tinggi=640)
        if not svg:
            kit.pesan_peringatan(self, "Figur ini belum punya data.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan figur", f"figur_{kunci}.svg",
                                              "SVG (*.svg);;PNG (*.png);;TIFF (*.tif)")
        if path:
            self._tulis_figur(svg, path)
            self._catat(f"Figur disimpan: {path}")

    def _simpan_semua_figur(self):
        folder = QFileDialog.getExistingDirectory(self, "Pilih folder untuk seluruh figur")
        if not folder:
            return
        from pathlib import Path
        ditulis, dilewati = [], []
        for d in FG.daftar():
            svg = self._svg_figur(d["kunci"], lebar=900, tinggi=640)
            if not svg:
                dilewati.append(d["nama"])
                continue
            for akhiran in (".svg", ".png"):
                p = Path(folder) / f"figur_{d['kunci']}{akhiran}"
                self._tulis_figur(svg, str(p))
            ditulis.append(d["kunci"])
        pesan = f"{len(ditulis)} figur ditulis (SVG + PNG {self.sp_dpi.value()} dpi) ke {folder}."
        if dilewati:
            pesan += f" Dilewati karena datanya belum ada: {', '.join(dilewati)}."
        self._catat(pesan)

    def _tulis_figur(self, svg: str, path: str):
        """Tulis SVG apa adanya, atau render ke raster pada DPI yang diminta."""
        from pathlib import Path
        p = Path(path)
        if p.suffix.lower() == ".svg":
            p.write_text(svg, encoding="utf-8")
            return
        from PySide6.QtCore import QByteArray
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
        r = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        ukuran = r.defaultSize()
        # SVG di sini digambar pada 96 dpi semu, jadi skalanya rasio dpi yang diminta terhadap 96.
        skala = max(1.0, self.sp_dpi.value() / 96.0)
        img = QImage(int(ukuran.width() * skala), int(ukuran.height() * skala), QImage.Format_ARGB32)
        img.fill(Qt.transparent if p.suffix.lower() == ".png" else Qt.white)
        pen = QPainter(img)
        pen.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        r.render(pen)
        pen.end()
        img.setDotsPerMeterX(int(self.sp_dpi.value() / 0.0254))
        img.setDotsPerMeterY(int(self.sp_dpi.value() / 0.0254))
        img.save(str(p))

    # ================================================================ 8. laporan
    def _tab_laporan(self, w):
        v = QVBoxLayout(w)
        v.setSpacing(8)
        self.kartu: Dict[str, kit.Kartu] = {}
        baris1, baris2 = [], []
        for i, r in enumerate(F.ringkasan(F.keadaan_baru())):
            k = kit.Kartu(r["tahap"], "0", r["satuan"])
            self.kartu[r["tahap"]] = k
            (baris1 if i < 4 else baris2).append(k)
        v.addLayout(kit.baris_kartu(*baris1))
        v.addLayout(kit.baris_kartu(*baris2))

        v.addWidget(QLabel("Paragraf metode (siap tempel ke naskah)"))
        from PySide6.QtWidgets import QTextBrowser
        self.tb_metode = QTextBrowser()
        self.tb_metode.setMinimumHeight(170)
        v.addWidget(self.tb_metode, 1)

        aksi = QHBoxLayout()
        aksi.addWidget(kit.tombol("Segarkan", self._segarkan_laporan))
        aksi.addWidget(kit.tombol("Salin metode (ID)",
                                  lambda: kit.salin(F.paragraf_metode(self.k), self.l_status)))
        aksi.addWidget(kit.tombol("Salin metode (EN)",
                                  lambda: kit.salin(F.paragraf_metode(self.k, inggris=True), self.l_status)))
        aksi.addWidget(kit.tombol("Ekspor JSON…", self._ekspor_json,
                                  tip="Seluruh keadaan alur untuk lampiran suplemen"))
        aksi.addStretch(1)
        v.addLayout(aksi)

    def _segarkan_laporan(self):
        # Sumber senyawa diketik di tab 1 dan hanya dibaca saat menyimpan; tanpa baris ini paragraf
        # metode memakai teks pengganti "sumber senyawa" walau penggunanya sudah mengisi kolom itu.
        self.k["tanaman"] = self.e_tanaman.text().strip()
        for r in F.ringkasan(self.k):
            kartu = self.kartu.get(r["tahap"])
            if kartu is not None:
                kartu.isi(str(r["nilai"]), r["ket"] or r["satuan"])
        self.tb_metode.setPlainText(F.paragraf_metode(self.k))

    def _ekspor_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Simpan keadaan alur", "farmakologi_jaringan.json",
                                              "JSON (*.json)")
        if not path:
            return
        from pathlib import Path
        Path(path).write_text(F.ke_json(self.k), encoding="utf-8")
        self._catat(f"Keadaan alur disimpan: {path}")

    # ================================================================ keadaan
    def _muat_keadaan(self):
        self.e_tanaman.setText(self.k.get("tanaman") or "")
        pen = self.k.get("penyakit") or {}
        if pen.get("nama"):
            self.e_penyakit.setText(pen["nama"])
        if self.k.get("ambang_string"):
            self.sp_string.setValue(float(self.k["ambang_string"]))
        idx = self.cb_gmt.findData(self.k.get("gmt") or "reactome")
        if idx >= 0:
            self.cb_gmt.setCurrentIndex(idx)
        self._isi_tabel_senyawa()
        self._isi_tabel_admet()
        self._isi_tabel_target()
        if self.k.get("gen_penyakit"):
            self._hitung_irisan()
        self._isi_tabel_hub()
        self._isi_tabel_jalur()
        self._segarkan_figur()
        self._segarkan_laporan()

    def _simpan(self):
        self.k["tanaman"] = self.e_tanaman.text().strip()
        self._segarkan_laporan()
        if self.proyek is None:
            kit.pesan_peringatan(self, "Belum ada proyek terbuka, jadi keadaan alur tidak bisa disimpan. "
                                       "Buat atau buka proyek dulu, lalu simpan lagi.")
            return
        self.proyek.farmakologi = self.k
        for j in self._jejak:
            try:
                self.proyek.catat_jejak(j)
            except Exception:
                pass
        self.keadaanBerubah.emit(self.k)
        if self.jw is not None and hasattr(self.jw, "minta_simpan"):
            self.jw.minta_simpan()
        self._catat("Keadaan alur farmakologi jaringan disimpan ke proyek.")
