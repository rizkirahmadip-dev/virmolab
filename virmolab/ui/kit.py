"""Komponen kecil bersama untuk dialog analisis: judul, kartu angka, lencana, tabel, format angka.

Warna selalu dari token tema (terang/gelap), jadi dialog tidak memakai warna tetap.
"""
from PySide6.QtCore import QByteArray, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPalette
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core.laporan import id_angka
from . import theme


def mode():
    """'gelap' / 'terang' sesuai palet aplikasi saat ini."""
    return "gelap" if QGuiApplication.palette().color(QPalette.Window).lightness() < 128 else "terang"


def warna(kunci):
    """Token warna tema aktif (ok, warn, bad, acc, mut, ink, ink2, line, …) sebagai QColor."""
    return QColor(theme.TOKEN[mode()][kunci])


def f(v, d=2, satuan=""):
    """Angka gaya Indonesia (koma desimal, minus asli); '–' bila kosong."""
    if v is None or v == "":
        return "–"
    try:
        t = id_angka(f"{float(v):.{d}f}")
    except (TypeError, ValueError):
        return str(v)
    return f"{t} {satuan}".rstrip()


def amp(t):
    """Teks judul tab/grup: '&' tampil apa adanya (bukan garis bawah mnemonik)."""
    return t.replace("&", "&&")


def judul(teks, sub=None):
    """Kepala dialog: judul + satu kalimat penjelasan (muted)."""
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 2)
    v.setSpacing(2)
    a = QLabel(teks)
    a.setObjectName("judulDialog")
    v.addWidget(a)
    if sub:
        b = QLabel(sub)
        b.setObjectName("subjudul")
        b.setWordWrap(True)
        v.addWidget(b)
    return w


def catatan(teks, jenis="muted"):
    """Label keterangan: muted | info | peringatan."""
    l = QLabel(teks)
    l.setObjectName(jenis)
    l.setWordWrap(True)
    l.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return l


def lencana(teks="", nada="info"):
    l = QLabel(teks)
    l.setObjectName("lencana")
    atur_nada(l, nada)
    return l


def atur_nada(label, nada):
    label.setProperty("nada", nada)
    label.style().unpolish(label)
    label.style().polish(label)


class Kartu(QFrame):
    """Kartu ringkas: label kecil, nilai besar, keterangan."""

    def __init__(self, label, nilai="–", ket=""):
        super().__init__()
        self.setObjectName("kartu")
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 8, 12, 9)
        v.setSpacing(1)
        self.l_label = QLabel(label.upper())
        self.l_label.setObjectName("kartuLabel")
        self.l_nilai = QLabel(nilai)
        self.l_nilai.setObjectName("kartuNilai")
        self.l_nilai.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.l_ket = QLabel(ket)
        self.l_ket.setObjectName("kartuKet")
        self.l_ket.setWordWrap(True)
        for x in (self.l_label, self.l_nilai, self.l_ket):
            v.addWidget(x)
        v.addStretch(1)

    def isi(self, nilai, ket=None, nada=None):
        self.l_nilai.setText(nilai)
        if ket is not None:
            self.l_ket.setText(ket)
        self.l_nilai.setStyleSheet(f"color: {theme.TOKEN[mode()][nada]};" if nada else "")


def baris_kartu(*kartu):
    h = QHBoxLayout()
    h.setSpacing(8)
    for k in kartu:
        h.addWidget(k, 1)
    return h


def sel(teks, angka=None, rata_kanan=None):
    """Sel tabel; angka disimpan di UserRole (urut numerik) dan rata kanan."""
    it = QTableWidgetItem("–" if teks is None else str(teks))
    if angka is not None:
        it.setData(Qt.UserRole, angka)
    if rata_kanan or (rata_kanan is None and angka is not None):
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return it


class SelAngka(QTableWidgetItem):
    """Sel yang diurutkan menurut UserRole (angka), bukan teks."""

    def __lt__(self, lain):
        a, b = self.data(Qt.UserRole), lain.data(Qt.UserRole)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return a < b
        return super().__lt__(lain)


def sel_angka(v, d=2, satuan=""):
    it = SelAngka(f(v, d, satuan))
    it.setData(Qt.UserRole, float(v) if isinstance(v, (int, float)) else None)
    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return it


def tabel(kolom, regang=None, urut=False):
    """QTableWidget baris-pilih, tanpa sunting, kolom 'regang' melebar (bawaan: kolom terakhir)."""
    t = QTableWidget(0, len(kolom))
    t.setHorizontalHeaderLabels(kolom)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(24)
    t.setWordWrap(False)
    t.setSortingEnabled(urut)
    h = t.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeToContents)
    h.setStretchLastSection(regang is None)
    if regang is not None:
        h.setSectionResizeMode(regang, QHeaderView.Stretch)
    h.setHighlightSections(False)
    return t


def tombol(teks, fn=None, utama=False, tip=None):
    b = QPushButton(teks)
    if utama:
        b.setObjectName("primary")
    if fn:
        b.clicked.connect(fn)
    if tip:
        b.setToolTip(tip)
    return b


def bar_bawah(dialog, kiri=(), kanan=(), tutup=True):
    """Baris tombol bawah: aksi di kiri, (opsional) aksi utama + Tutup di kanan."""
    h = QHBoxLayout()
    h.setSpacing(6)
    for b in kiri:
        h.addWidget(b)
    h.addStretch(1)
    for b in kanan:
        h.addWidget(b)
    if tutup:
        h.addWidget(tombol("✕ Tutup", dialog.close))
    return h


def salin(teks, status=None, pesan="Disalin ke papan klip."):
    QGuiApplication.clipboard().setText(teks)
    if status is not None:
        status.setText(pesan)


def garis():
    g = QFrame()
    g.setObjectName("garis")
    g.setFixedHeight(1)
    return g


# ------------------------------------------------------------------ data proyek untuk dialog analisis
def ligan_proyek(jw, dengan_mol=True, min_atom=6):
    """[{kunci, nama, smiles, mol, atom, dg, le, job}] ligan proyek + ligan viewer, urut nama.

    dg = ΔG terbaik di semua job (None bila belum di-docking). Dilewati: ligan yang tidak terbaca RDKit, aditif
    kristalografi (gliserol, DMSO, ion, buffer), dan serpihan di bawah `min_atom` atom berat."""
    from rdkit import Chem
    from ..core import ekspor
    terbaik = {}
    if jw.proyek:
        for b in ekspor.baris_hasil(jw.proyek):
            if b.get("kovalen"):
                continue
            lama = terbaik.get(b["lid"])
            if lama is None or b["energi"] < lama["energi"]:
                terbaik[b["lid"]] = b
    hasil = []
    for kunci, nama, teks, fmt, l in jw._sumber_sifat():
        o = jw.objek.get(kunci)
        if o is not None and o.info.get("aditif"):
            continue
        smi = jw.proyek.smiles_ligan(l) if (l is not None and jw.proyek) else ""
        mol = Chem.MolFromSmiles(smi) if smi else None
        if mol is None:
            try:
                from ..core import kemiripan
                mol = kemiripan.mol_dari(teks, fmt)
                smi = Chem.MolToSmiles(mol)
            except Exception:
                continue
        n_atom = mol.GetNumHeavyAtoms()
        if n_atom < min_atom:          # DMS, GOL, SO4, ion: bukan kandidat ligan
            continue
        b = terbaik.get(kunci) or {}
        hasil.append({"kunci": kunci, "nama": nama, "smiles": smi, "mol": mol if dengan_mol else None,
                      "atom": n_atom, "dg": b.get("energi"), "le": b.get("le"), "job": b.get("job"),
                      "baris": b or None})
    hasil.sort(key=lambda l: (l["dg"] if l["dg"] is not None else 0.0, l["nama"]))
    return hasil


def reseptor_proyek(jw):
    """(teks PDB, nama, Path | None) reseptor proyek (bersih → asli), atau protein di viewer; ('', '', None)."""
    pr = jw.proyek
    if pr and pr.reseptor:
        for k in ("bersih", "asli"):
            if pr.reseptor.get(k):
                p = pr.p(pr.reseptor[k])
                if p.exists():
                    return p.read_text(encoding="utf-8", errors="replace"), pr.reseptor.get("nama") or "reseptor", p
    o = jw._reseptor_objek()
    if o is not None and o.fmt == "pdb":
        return o.teks, o.nama, None
    return "", "", None


def pose_aktif(jw):
    """Objek pose/ligan yang sedang dianalisis di panel Interaksi (atau None)."""
    a = getattr(jw, "_aktif_inter", None)
    o = jw.objek.get(a["oid"]) if a else None
    return o if o is not None and o.jenis in ("pose", "ligan") else None


def pusat_kotak(jw):
    """Pusat grid box aktif [x, y, z] atau None."""
    b = getattr(jw, "box", None) or {}
    return list(b["pusat"]) if b.get("pusat") else None


# ------------------------------------------------------------------ tanda proses berjalan
class sibuk:
    """Tanda 'sedang bekerja': kursor tunggu + teks status, dipulihkan saat blok selesai.

        with kit.sibuk(self.l_status, "Menghitung kontak…"):
            hasil = hitung()

    Pakai untuk hitungan singkat (≤ beberapa detik) yang berjalan di thread UI. Untuk pekerjaan panjang,
    pakai `kerja.jalankan` agar jendela tidak membeku, dan tampilkan `Sibuk` di bilah status dialog.
    """

    def __init__(self, label=None, pesan="Sedang menghitung…", tombol=()):
        self.label = label
        self.pesan = pesan
        self.tombol = [b for b in tombol if b is not None]
        self.teks_lama = None

    def __enter__(self):
        from PySide6.QtWidgets import QApplication
        self.teks_lama = self.label.text() if self.label is not None else None
        if self.label is not None:
            self.label.setText(self.pesan)
        for b in self.tombol:
            b.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        return self

    def selesai(self, pesan):
        """Teks yang ditampilkan setelah blok selesai (bawaan: teks sebelumnya kembali)."""
        self.teks_lama = pesan

    def __exit__(self, *galat):
        from PySide6.QtWidgets import QApplication
        QApplication.restoreOverrideCursor()
        for b in self.tombol:
            b.setEnabled(True)
        if self.label is not None:
            if galat[0]:
                self.label.setText("Gagal menghitung — lihat panel Pesan.")
            elif self.label.text() == self.pesan:     # badan blok tidak menulis apa pun: kembalikan teks lama
                self.label.setText(self.teks_lama or "")
        QApplication.processEvents()
        return False


class GambarSvg(QWidget):
    """Tampilkan grafik SVG yang mengikuti ukuran panel.

    `atur_pembuat(fn)` membuat grafik digambar ulang seukuran widget setiap kali panel berubah ukuran, sehingga
    grafik tidak pernah teregang, tidak menyisakan ruang kosong, dan tebal garis serta ukuran teksnya tetap wajar.
    `muat(svg)` dipakai untuk SVG yang ukurannya memang tetap; gambar itu diskalakan dengan rasio aspek terjaga.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._renderer = QSvgRenderer(self)
        self._renderer.repaintNeeded.connect(self.update)
        self._pembuat = None
        self._ukuran_render = (0, 0)
        self._tunda = QTimer(self)
        self._tunda.setSingleShot(True)
        self._tunda.setInterval(120)       # gambar ulang setelah seretan ukuran berhenti, bukan tiap piksel
        self._tunda.timeout.connect(self._gambar_ulang)
        self.setMinimumHeight(240)

    def atur_pembuat(self, fn):
        """fn(lebar, tinggi) -> str SVG. None mengosongkan gambar."""
        self._pembuat = fn
        self._ukuran_render = (0, 0)
        if fn is None:
            self._renderer.load(QByteArray(b""))
            self.update()
            return
        self._gambar_ulang()
        # saat dipasang, tata letak sering belum selesai: gambar sekali lagi dengan ukuran final
        QTimer.singleShot(0, self._gambar_ulang)

    def muat(self, svg: str):
        self._pembuat = None
        self._renderer.load(QByteArray(svg.encode("utf-8")))
        self.update()

    def kosong(self) -> bool:
        return not self._renderer.isValid()

    def _gambar_ulang(self):
        if not self._pembuat:
            return
        l, t = max(360, self.width()), max(240, self.height())
        if (l, t) == self._ukuran_render:
            return
        try:
            svg = self._pembuat(l, t)
        except Exception:
            return
        if svg:
            self._ukuran_render = (l, t)
            self._renderer.load(QByteArray(svg.encode("utf-8")))
            self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not self._pembuat:
            return
        # perubahan besar (mis. tata letak pertama atau jendela dimaksimalkan) digambar segera agar grafik tidak
        # sempat tampil dengan ukuran lama; seretan kecil ditunda supaya tidak menggambar ulang tiap piksel
        if abs(self.width() - self._ukuran_render[0]) > 40 or abs(self.height() - self._ukuran_render[1]) > 40:
            self._gambar_ulang()
        else:
            self._tunda.start()

    def showEvent(self, e):
        super().showEvent(e)
        if self._pembuat:
            self._tunda.start()

    def paintEvent(self, e):
        if not self._renderer.isValid():
            return
        ukuran = self._renderer.defaultSize()
        if ukuran.isEmpty():
            return
        ukuran.scale(self.size(), Qt.KeepAspectRatio)
        x = (self.width() - ukuran.width()) // 2
        y = (self.height() - ukuran.height()) // 2
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self._renderer.render(p, QRectF(x, y, ukuran.width(), ukuran.height()))
        p.end()


def bilah_sibuk(teks="Sedang menghitung…"):
    """Bilah progres tak tentu + teks, untuk pekerjaan latar belakang; sembunyikan lewat `atur()`."""
    from PySide6.QtWidgets import QHBoxLayout, QProgressBar, QWidget
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(8)
    bar = QProgressBar()
    bar.setRange(0, 0)               # tak tentu: animasi berjalan terus
    bar.setFixedWidth(120)
    lbl = QLabel(teks)
    lbl.setObjectName("subjudul")
    h.addWidget(bar)
    h.addWidget(lbl, 1)
    w.bar, w.label = bar, lbl
    w.setVisible(False)

    def atur(tampil, pesan=None):
        if pesan:
            lbl.setText(pesan)
        w.setVisible(bool(tampil))
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

    w.atur = atur
    return w


def hx(kunci):
    """Nilai heks token tema aktif, untuk teks HTML/QSS yang butuh string warna (mis. "#2e9e5b")."""
    return theme.TOKEN[mode()][kunci]
