"""Dialog Glikosida dan aglikon: potong gula, tambahkan aglikon ke proyek, bandingkan efisiensi ikatan.

Daftar atas memuat ligan proyek yang dikenali sebagai glikosida (core/glikosida.py) beserta unit gulanya; diagram 2D
menyorot atom gula yang dipotong. Aglikon yang belum ada di proyek dapat ditambahkan sebagai ligan baru untuk
didocking dengan reseptor dan kotak yang sama. Tabel bawah membandingkan pasangan yang keduanya sudah didocking pada
kondisi yang sama: ΔΔG, LE, FQ, dan sumbangan skor per atom gula.
"""
import csv
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QGroupBox, QHBoxLayout, QSplitter, QVBoxLayout

from .. import i18n
from ..core import glikosida as G
from . import kerja, kit

KOLOM_LIGAN = ["Ligan", "Gula", "Atom berat", "Aglikon di proyek", "Catatan"]
KOLOM_BANDING = ["Glikosida", "Aglikon", "Kondisi docking", "ΔG glikosida", "ΔG aglikon", "ΔΔG", "Kesimpulan",
                 "LE glikosida → aglikon", "FQ glikosida → aglikon", "Per atom gula"]
NADA_KESIMPULAN = {"aglikon": "ok", "ukuran": "warn", "gula": "acc", "kurang": "mut"}


def gambar_glikosida(smiles, atom_gula, lebar, tinggi, gelap=False):
    """SVG 2D glikosida dengan atom dan ikatan unit gula disorot kuning."""
    from rdkit import Chem
    from rdkit.Chem import rdDepictor
    from rdkit.Chem.Draw import rdMolDraw2D
    m = Chem.MolFromSmiles(smiles or "")
    if m is None:
        return ""
    m = Chem.RemoveHs(m)
    rdDepictor.SetPreferCoordGen(True)
    rdDepictor.Compute2DCoords(m)
    d = rdMolDraw2D.MolDraw2DSVG(max(lebar, 120), max(tinggi, 120))
    o = d.drawOptions()
    o.bondLineWidth = 2
    o.padding = 0.06
    o.clearBackground = False
    if gelap:
        o.updateAtomPalette({6: (0.88, 0.9, 0.93), 7: (0.48, 0.66, 1.0), 8: (1.0, 0.45, 0.45),
                             16: (0.95, 0.82, 0.3)})
        o.setSymbolColour((0.88, 0.9, 0.93))
    # RGB tanpa alfa: RDKit menulis RGBA sebagai heksa 8 digit yang tidak dikenali QtSvg (tampil hitam)
    kuning = (0.45, 0.36, 0.12) if gelap else (1.0, 0.86, 0.45)
    o.highlightRadius = 0.32
    gula = set(atom_gula or [])
    ikatan = [b.GetIdx() for b in m.GetBonds() if b.GetBeginAtomIdx() in gula and b.GetEndAtomIdx() in gula]
    rdMolDraw2D.PrepareAndDrawMolecule(d, m, highlightAtoms=sorted(gula), highlightBonds=ikatan,
                                       highlightAtomColors={i: kuning for i in gula},
                                       highlightBondColors={i: kuning for i in ikatan})
    d.FinishDrawing()
    return re.sub(r"<\?xml[^>]*>", "", d.GetDrawingText())


def _sel_delta(v):
    it = kit.sel_angka(v)
    if isinstance(v, (int, float)) and v > 0:
        it.setText("+" + it.text())
    return it


class DialogGlikosida(QDialog):
    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self.setWindowTitle("Glikosida dan aglikon")
        self.setMinimumSize(1180, 740)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self._analisis = {"glikosida": [], "pasangan": []}
        self._kerja = None
        self._bangun()
        self._muat()

    # ================================================================== tata letak
    def _bangun(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(kit.judul("Glikosida dan aglikon",
                                "Potong unit gula seperti hidrolisis enzimatik, lalu bandingkan efisiensi ikatan "
                                "glikosida dengan aglikonnya pada reseptor, kotak, dan mesin docking yang sama."))
        atas = QSplitter(Qt.Horizontal, self)
        atas.setChildrenCollapsible(False)

        g_lig = QGroupBox("Ligan glikosida di proyek")
        v = QVBoxLayout(g_lig)
        self.tabel_ligan = kit.tabel(KOLOM_LIGAN, urut=True)
        self.tabel_ligan.itemSelectionChanged.connect(self._ganti_ligan)
        v.addWidget(self.tabel_ligan, 1)
        h = QHBoxLayout()
        self.b_tambah = kit.tombol("Tambahkan aglikon ke proyek", self._tambah_aglikon, utama=True,
                                   tip="Aglikon yang belum ada disimpan sebagai ligan proyek, siap didocking dengan "
                                       "reseptor dan kotak yang sama")
        self.b_tambah.setEnabled(False)
        h.addWidget(self.b_tambah)
        h.addStretch(1)
        v.addLayout(h)
        atas.addWidget(g_lig)

        g_2d = QGroupBox("Struktur")
        v2 = QVBoxLayout(g_2d)
        self.gambar = kit.GambarSvg()
        self.gambar.setMinimumSize(300, 240)
        v2.addWidget(self.gambar, 1)
        self.l_struktur = kit.catatan("Pilih ligan untuk melihat unit gula (disorot kuning) yang dipotong.", "muted")
        self.l_struktur.setMinimumHeight(3 * self.l_struktur.fontMetrics().lineSpacing() + 4)
        self.l_struktur.setAlignment(Qt.AlignTop)
        v2.addWidget(self.l_struktur)
        atas.addWidget(g_2d)
        atas.setSizes([720, 420])
        lay.addWidget(atas, 5)

        self.k_pasangan = kit.Kartu("Perbandingan", "–", "pasangan × kondisi docking")
        self.k_efisien = kit.Kartu("Aglikon lebih efisien", "–", "LE aglikon > LE glikosida")
        self.k_ukuran = kit.Kartu("Unggul karena ukuran", "–",
                                  "glikosida lebih kuat, tetapi per atom gula < LE aglikon")
        lay.addLayout(kit.baris_kartu(self.k_pasangan, self.k_efisien, self.k_ukuran))

        g_bd = QGroupBox("Perbandingan pada kondisi docking yang sama")
        vb = QVBoxLayout(g_bd)
        self.tabel_banding = kit.tabel(KOLOM_BANDING, urut=True)
        self.tabel_banding.itemSelectionChanged.connect(self._ganti_pasangan)
        vb.addWidget(self.tabel_banding, 1)
        self.l_rinci = kit.catatan("", "info")
        self.l_rinci.setMinimumHeight(2 * self.l_rinci.fontMetrics().lineSpacing() + 4)
        self.l_rinci.setAlignment(Qt.AlignTop)
        vb.addWidget(self.l_rinci)
        vb.addWidget(kit.catatan(
            "ΔΔG negatif berarti glikosida berskor lebih kuat. LE turun dengan sendirinya saat molekul membesar; FQ "
            "mengoreksi pengaruh ukuran itu (Reynolds dkk., 2007). Skor docking bukan afinitas terukur.", "muted"))
        lay.addWidget(g_bd, 4)

        self.l_status = kit.catatan("", "muted")
        lay.addWidget(self.l_status)
        self.b_metode = kit.tombol("Salin metode", self._salin_metode)
        self.b_csv = kit.tombol("Ekspor CSV…", self._ekspor_csv)
        self.b_muat = kit.tombol("Muat ulang", self._muat, tip="Baca ulang ligan dan hasil docking proyek")
        lay.addLayout(kit.bar_bawah(self, kiri=(self.b_metode, self.b_csv, self.b_muat)))

    def _status(self, teks, jenis="muted"):
        self.l_status.setText(teks)
        self.l_status.setObjectName(jenis if teks else "muted")
        self.l_status.style().unpolish(self.l_status)
        self.l_status.style().polish(self.l_status)

    # ================================================================== data
    def _muat(self):
        pr = self.jw.proyek
        if not pr or not pr.ligan:
            self._analisis = {"glikosida": [], "pasangan": []}
            self._isi()
            self._status("Proyek belum berisi ligan.", "peringatan")
            return
        with kit.sibuk(self.l_status, "Mengenali gula dan mencocokkan aglikon…"):
            self._analisis = G.analisis_proyek(pr)
        self._isi()

    def _isi(self):
        gl = self._analisis["glikosida"]
        t = self.tabel_ligan
        t.setSortingEnabled(False)
        t.setRowCount(len(gl))
        for r, g in enumerate(gl):
            h = g["hasil"]
            it = kit.sel(g["nama"])
            it.setData(Qt.UserRole + 1, r)
            t.setItem(r, 0, it)
            t.setItem(r, 1, kit.sel(G.ringkas_gula(h.gula, i18n.t) if h.gula else "–"))
            atom = f"{h.atom_berat} → {h.atom_berat_aglikon}" if h.atom_berat_aglikon else str(h.atom_berat)
            t.setItem(r, 2, kit.sel(atom, h.atom_berat, True))
            if g["aglikon"]:
                agl = g["aglikon"][1] + ("" if g["aglikon"][2] == "persis" else f" ({i18n.t(g['aglikon'][2])})")
            elif h.glikosida:
                agl = i18n.t("belum ada")
            else:
                agl = "–"
            t.setItem(r, 3, kit.sel(agl))
            catatan = {"hanya_c": "C-glikosida: tidak dipotong", "gula_saja": "Seluruhnya gula"}.get(h.status, "")
            t.setItem(r, 4, kit.sel(i18n.t(h.pesan or catatan) if (h.pesan or catatan) else ""))
        t.setSortingEnabled(True)
        if gl:
            t.selectRow(0)
            self._ganti_ligan()          # baris 0 mungkin sudah terpilih sebelum dimuat ulang (sinyal tidak terpancar)
        else:
            self.gambar.atur_pembuat(None)

        kurang = [g for g in gl if g["hasil"].glikosida and not g["aglikon"]]
        self.b_tambah.setEnabled(bool(kurang) and self._kerja is None)
        self.b_tambah.setText(i18n.t("Tambahkan aglikon ke proyek") + (f" ({len(kurang)})" if kurang else ""))

        p = self._analisis["pasangan"]
        tb = self.tabel_banding
        tb.setSortingEnabled(False)
        tb.setRowCount(len(p))
        for r, x in enumerate(p):
            tb.setItem(r, 0, kit.sel(x["nama_g"]))
            tb.setItem(r, 1, kit.sel(x["nama_a"]))
            tb.setItem(r, 2, kit.sel(x["label_kondisi"]))
            tb.setItem(r, 3, kit.sel_angka(x["dg_g"]))
            tb.setItem(r, 4, kit.sel_angka(x["dg_a"]))
            tb.setItem(r, 5, _sel_delta(x["ddg"]))
            it = kit.sel(i18n.t(G.KESIMPULAN_SINGKAT[x["kode"]]))
            it.setToolTip(i18n.t(x["kesimpulan"]))
            it.setData(Qt.UserRole + 1, r)
            it.setForeground(kit.warna(NADA_KESIMPULAN.get(x["kode"], "ink")))
            tb.setItem(r, 6, it)
            for c, (a, b) in ((7, ("le_g", "le_a")), (8, ("fq_g", "fq_a"))):
                # diurutkan menurut selisih (aglikon - glikosida): paling atas = aglikon paling unggul
                beda = x[b] - x[a] if x[a] is not None and x[b] is not None else None
                sel = kit.SelAngka(f"{kit.f(x[a], 3)} → {kit.f(x[b], 3)}")
                sel.setData(Qt.UserRole, beda)
                sel.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                tb.setItem(r, c, sel)
            tb.setItem(r, 9, kit.sel_angka(x["per_atom_gula"], 3) if x["per_atom_gula"] is not None
                       else kit.sel("–"))
        tb.setSortingEnabled(True)
        if p:
            tb.selectRow(0)
        else:
            self.l_rinci.setText("")

        n_efisien = sum(1 for x in p if x["aglikon_lebih_efisien"])
        n_ukuran = sum(1 for x in p if x["kode"] == "ukuran")
        self.k_pasangan.isi(str(len(p)) if p else "–")
        self.k_efisien.isi(f"{n_efisien} / {len(p)}" if p else "–", nada="ok" if p and n_efisien else None)
        self.k_ukuran.isi(f"{n_ukuran} / {len(p)}" if p else "–", nada="warn" if n_ukuran else None)
        self.b_metode.setEnabled(bool(p))
        self.b_csv.setEnabled(bool(p))

        if not gl:
            self._status("Tidak ada ligan glikosida di proyek ini. Yang dikenali: gula siklik (piranosa/furanosa) yang "
                         "terikat lewat ikatan O-, N-, atau S-glikosidik, termasuk ester glikosil.", "muted")
        elif kurang:
            self._status(f"{len(kurang)} aglikon belum ada di proyek. Tambahkan, lalu docking dengan reseptor dan "
                         "kotak yang sama dengan glikosidanya.", "info")
        elif not p:
            self._status("Aglikon sudah ada, tetapi belum ada pasangan yang keduanya didocking dengan reseptor, kotak, "
                         "dan mesin yang sama.", "info")
        else:
            self._status(f"{len(p)} perbandingan dari {len({x['lid_g'] for x in p})} glikosida.", "muted")

    def _ganti_pasangan(self):
        it = self.tabel_banding.item(self.tabel_banding.currentRow(), 6)
        if it is None:
            self.l_rinci.setText("")
            return
        x = self._analisis["pasangan"][it.data(Qt.UserRole + 1)]
        rinci = i18n.t(x["kesimpulan"])
        if x["per_atom_gula"] is not None and x["le_a"] is not None and x["ddg"] < 0:
            rinci += " " + i18n.t(f"{x['n_gula']} gula ({x['ha_g'] - x['ha_a']} atom berat) menambah "
                                  f"{kit.f(-x['ddg'], 2)} kkal/mol, yaitu {kit.f(x['per_atom_gula'], 3)} per atom; "
                                  f"LE aglikon {kit.f(x['le_a'], 3)}.")
        self.l_rinci.setText(f"{x['nama_g']} → {x['nama_a']}: " + rinci)

    def _baris_ligan(self):
        it = self.tabel_ligan.item(self.tabel_ligan.currentRow(), 0)
        if it is None:
            return None
        return self._analisis["glikosida"][it.data(Qt.UserRole + 1)]

    def _ganti_ligan(self):
        g = self._baris_ligan()
        if g is None:
            self.gambar.atur_pembuat(None)
            return
        h = g["hasil"]
        # tema dibaca saat menggambar, supaya diagram ikut berganti bila tema diubah selagi dialog terbuka
        self.gambar.atur_pembuat(lambda w, t, s=h.smiles, a=h.atom_gula:
                                 gambar_glikosida(s, a, w, t, kit.mode() == "gelap"))
        if h.smiles_aglikon:
            self.l_struktur.setText(i18n.t("Kuning: unit gula yang dipotong. Aglikon: ") + h.smiles_aglikon)
        else:
            self.l_struktur.setText(i18n.t(h.pesan or "Tidak ada gula yang dapat dipotong."))

    # ================================================================== aksi
    def _tambah_aglikon(self):
        kurang = [g for g in self._analisis["glikosida"] if g["hasil"].glikosida and not g["aglikon"]]
        if not kurang or self._kerja is not None:
            return
        akhiran = i18n.t("aglikon")          # nama ligan tersimpan di proyek, jadi mengikuti bahasa saat dibuat
        tugas = [(f"{g['nama']} ({akhiran})", g["hasil"].smiles_aglikon) for g in kurang]

        def siapkan(lapor=None):
            from ..core import prep_ligan
            return [(nama, smi, prep_ligan.siapkan_satu(nama, smi, "smiles", prep_ligan.OpsiLigan()))
                    for nama, smi in tugas]

        self.b_tambah.setEnabled(False)
        self._status(f"Menyiapkan {len(tugas)} aglikon (protonasi, konformasi 3D, PDBQT)…", "muted")
        self._kerja = kerja.jalankan(siapkan, selesai=self._aglikon_siap, galat=self._aglikon_galat)

    def _aglikon_siap(self, hasil):
        self._kerja = None
        from ..core import molekul
        siap, gagal = [], []
        for nama, smi, h in hasil:
            if h.status == "gagal":
                gagal.append(f"{nama}: {h.alasan}")
                continue
            siap.append((molekul.Objek(nama=nama, jenis="ligan", teks=smi, fmt="smiles", sumber="aglikon"), h))
        if siap:
            self.jw._ligan_siap(siap)
        self._muat()
        teks = (f"{len(siap)} aglikon ditambahkan sebagai ligan proyek. Docking dengan reseptor dan kotak yang sama "
                "dengan glikosidanya, lalu klik Muat ulang.")
        if gagal:
            teks += " " + i18n.t("Gagal: ") + "; ".join(gagal)
        self._status(teks, "peringatan" if gagal else "info")

    def _aglikon_galat(self, pesan):
        self._kerja = None
        self.b_tambah.setEnabled(True)
        self._status(i18n.t("Aglikon gagal disiapkan: ") + str(pesan).split("\n")[0], "peringatan")

    def _salin_metode(self):
        teks = G.teks_metode(self._analisis, en=i18n.inggris())
        if not teks:
            self._status("Belum ada pasangan yang dibandingkan.", "peringatan")
            return
        kit.salin(teks + "\n\n" + "\n".join(G.PUSTAKA))
        self._status("Paragraf metode dan daftar pustaka disalin ke papan klip.")

    def _ekspor_csv(self):
        if not self._analisis["pasangan"]:
            return
        path, _ = QFileDialog.getSaveFileName(self, i18n.t("Ekspor perbandingan"), "glikosida_aglikon.csv",
                                              "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerows(G.baris_csv(self._analisis))
        self._status(f"Tabel disimpan ke {path}")
