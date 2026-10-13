"""Peta ADMET: diagram alur kartu organ, dua dimensi dan tanpa figur manusia.

Baris atas = perjalanan obat (penyerapan → peredaran → metabolisme → pembuangan) dengan panah penghubung dan
titik berjalan; baris bawah = organ serta sistem yang terdampak. Tiap kartu memuat ikon organ, nama, angka skor
0–100, dan bilah skor.

Dilukis dengan QPainter supaya tajam di layar HiDPI, warnanya ikut tema, animasinya mulus, dan tetap bisa
diekspor ke PNG/SVG. Ikon organ digambar sendiri (`bentuk_organ.py`) — tanpa aset berlisensi dari luar.
"""
from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QTimer, QVariantAnimation, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ..core import peta_tubuh as PT
from . import theme
from .bentuk_organ import bentuk as bentuk_organ

LEBAR, TINGGI = 780.0, 500.0        # kanvas acuan (termasuk judul ligan dan legenda)
KARTU_W, KARTU_H = 152.0, 132.0
SELA = 22.0
WARNA_STATUS = {"baik": "ok", "sedang": "warn", "risiko": "bad", "kosong": "mut"}
BARIS_ALUR = ["cerna", "jantung", "hati", "ginjal"]        # berurutan, dihubungkan panah
BARIS_DAMPAK = ["otak", "kulit", "sel", "sistemik"]
TAHAP = {"cerna": "Penyerapan", "jantung": "Peredaran", "hati": "Metabolisme", "ginjal": "Pembuangan"}


def _kotak_kartu(baris, kolom, n):
    total = n * KARTU_W + (n - 1) * SELA
    x = (LEBAR - total) / 2 + kolom * (KARTU_W + SELA)
    return QRectF(x, 92.0 if baris == 0 else 306.0, KARTU_W, KARTU_H)


class PetaTubuh(QWidget):
    """Diagram organ ADMET. `muat(hasil)` mengisi data; sinyal `organDipilih(kunci)` saat kartu diklik."""

    organDipilih = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(560, 360)
        self._mode_tema = "terang"
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.organ = []
        self.hasil = {}
        self.nama = ""
        self.terpilih = None
        self._hover = None
        self._skor_tampil = {}
        self._fase = 0.0
        self._alur = 0.0
        self._alur_hidup = True
        self._denyut_sisa = 0.0
        self._durasi_alur = 6.0
        self._masuk = 1.0              # 0→1: kartu muncul bertahap saat ligan berganti
        self._hover_t = {}             # kunci → 0..1 halusnya efek sorot
        self._riak = None              # (kunci, 0..1) lingkaran menyebar saat kartu dipilih
        self._tujuan, self._awal = {}, {}
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._anim.valueChanged.connect(self._langkah_anim)
        self._t = QTimer(self)
        self._t.setInterval(40)        # 25 fps: mulus tetapi ringan untuk laptop
        self._t.timeout.connect(self._detak)

    # ------------------------------------------------------------------ data
    def muat(self, hasil, nama=""):
        """Isi diagram dari satu baris prediksi ADMET-AI ({kolom: nilai}); {} = belum diprediksi."""
        self.hasil = hasil or {}
        self.nama = nama
        lama = dict(self._skor_tampil)
        self.organ = PT.nilai_organ(self.hasil)
        self._tujuan = {o["kunci"]: (o["skor"] if o["skor"] is not None else -1.0) for o in self.organ}
        self._awal = {k: lama.get(k, -1.0) for k in self._tujuan}
        self._durasi_alur = PT.waktu_alur(self.hasil)
        self._denyut_sisa = 6.0 if any(o["status"] == "risiko" for o in self.organ) else 0.0
        self._masuk = 0.0 if self._alur_hidup else 1.0
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._t.start()

    def atur_alur(self, hidup):
        """Hidupkan/matikan seluruh gerak: partikel aliran, kartu masuk, denyut, dan riak."""
        self._alur_hidup = bool(hidup)
        if hidup:
            self._t.start()
        else:
            self._anim.stop()                       # warna langsung di nilai akhir, tanpa gerak
            self._langkah_anim(1.0)
            self._masuk, self._riak, self._denyut_sisa = 1.0, None, 0.0
            self._hover_t.clear()
            self._t.stop()
        self.update()

    def organ_kunci(self, kunci):
        return next((o for o in self.organ if o["kunci"] == kunci), None)

    def _langkah_anim(self, t):
        self._skor_tampil = {k: self._awal[k] + (self._tujuan[k] - self._awal[k]) * float(t) for k in self._tujuan}
        self.update()

    def _detak(self):
        self._fase = (self._fase + 0.04) % 1.0
        if self._alur_hidup:
            self._alur = (self._alur + 0.04 / max(1.0, self._durasi_alur)) % 1.0
            self._masuk = min(1.0, self._masuk + 0.055)              # kartu masuk bertahap
        else:
            self._masuk = 1.0
        if self._denyut_sisa > 0:
            self._denyut_sisa = max(0.0, self._denyut_sisa - 0.04)   # denyut berhenti sendiri (±6 detik)
        for kunci in list(self._hover_t):                            # sorot naik/turun halus
            tujuan = 1.0 if kunci == self._hover else 0.0
            nilai = self._hover_t[kunci] + (0.18 if tujuan > self._hover_t[kunci] else -0.18)
            self._hover_t[kunci] = max(0.0, min(1.0, nilai))
            if self._hover_t[kunci] in (0.0,) and kunci != self._hover:
                self._hover_t.pop(kunci, None)
        if self._riak:
            kunci, nilai = self._riak
            self._riak = (kunci, nilai + 0.07) if nilai < 1.0 else None
        diam = (not self._alur_hidup and self._denyut_sisa <= 0 and not self._anim.state()
                and self._masuk >= 1.0 and not self._hover_t and not self._riak)
        if diam:
            self._t.stop()
        self.update()

    # ------------------------------------------------------------------ tata letak
    def _kotak(self, kunci):
        if kunci in BARIS_ALUR:
            return _kotak_kartu(0, BARIS_ALUR.index(kunci), len(BARIS_ALUR))
        if kunci in BARIS_DAMPAK:
            return _kotak_kartu(1, BARIS_DAMPAK.index(kunci), len(BARIS_DAMPAK))
        return QRectF()

    def _skala(self):
        k = min(self.width() / LEBAR, self.height() / TINGGI)
        return k, (self.width() - LEBAR * k) / 2, (self.height() - TINGGI * k) / 2

    def _mode(self):
        return self._mode_tema

    def _huruf(self, ukuran, tebal=False):
        """Huruf antarmuka aplikasi pada ukuran tertentu — ikut penskalaan Windows, bukan nama huruf tetap."""
        f = QFont(self.font())
        f.setPointSizeF(ukuran)
        f.setBold(tebal)
        return f

    def _warna(self, o):
        t = theme.TOKEN[self._mode()]
        s = self._skor_tampil.get(o["kunci"], o["skor"] if o["skor"] is not None else -1.0)
        if s < 0:
            return QColor(t["acc"] if o.get("info") else t["line"])   # netral berinfo vs benar-benar kosong
        return QColor(t[WARNA_STATUS[PT.status(s)]])

    # ------------------------------------------------------------------ lukisan
    def paintEvent(self, _e):
        from .kit import mode
        self._mode_tema = mode()
        t = theme.TOKEN[self._mode()]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(t["surf"]))
        k, dx, dy = self._skala()
        p.translate(dx, dy)
        p.scale(k, k)
        self.gambar(p, t)
        p.end()

    def gambar(self, p, t):
        """Lukis diagram pada kanvas acuan 780 × 500 — dipakai layar maupun ekspor."""
        self._kepala(p, t)
        self._judul_baris(p, t, "PERJALANAN OBAT", 60.0)
        self._judul_baris(p, t, "ORGAN DAN SISTEM TERDAMPAK", 274.0)
        self._panah(p, t)
        if self.organ and all(o["skor"] is None and not o.get("info") for o in self.organ):
            p.setFont(self._huruf(9.0))
            p.setPen(QColor(t["mut"]))
            p.drawText(QRectF(0, TINGGI / 2 - 12, LEBAR, 24), Qt.AlignCenter,
                       "Ligan ini belum diprediksi — klik “Prediksi ligan yang belum dihitung”.")
        for kunci in BARIS_ALUR + BARIS_DAMPAK:
            o = self.organ_kunci(kunci)
            if o:
                self._kartu(p, t, o)
        if self._alur_hidup:
            self._titik_alur(p, t)
        self._legenda(p, t)
        p.setFont(self._huruf(7.4))
        p.setPen(QColor(t["mut"]))
        p.drawText(QRectF(0, TINGGI - 24, LEBAR, 16), Qt.AlignCenter,
                   "Skor 0–100: makin tinggi makin aman. Prediksi model pembelajaran mesin, bukan hasil uji.")

    def _kepala(self, p, t):
        """Nama ligan dan ringkasan di atas gambar — ikut terbawa saat diekspor."""
        p.setFont(self._huruf(12.0, tebal=True))
        p.setPen(QColor(t["ink"]))
        p.drawText(QRectF(0, 14, LEBAR, 22), Qt.AlignCenter, self.nama or "Peta organ ADMET")
        p.setFont(self._huruf(7.8))
        p.setPen(QColor(t["mut"]))
        p.drawText(QRectF(60, 36, LEBAR - 120, 18), Qt.AlignCenter, PT.ringkas(self.organ))

    def _legenda(self, p, t):
        """Kunci warna: aman / perlu dicermati / berisiko / informasi."""
        butir = [("ok", "70–100 aman"), ("warn", "40–69 perlu dicermati"), ("bad", "0–39 berisiko"),
                 ("acc", "angka biru = informasi, bukan risiko")]
        p.setFont(self._huruf(7.2))
        lebar = [p.fontMetrics().horizontalAdvance(x[1]) + 26 for x in butir]
        x = (LEBAR - sum(lebar)) / 2
        y = TINGGI - 46
        for (kunci, teks), w in zip(butir, lebar):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(t[kunci]))
            p.drawRoundedRect(QRectF(x, y + 4, 11, 11), 3, 3)
            p.setPen(QColor(t["ink2"]))
            p.drawText(QRectF(x + 17, y, w - 17, 18), Qt.AlignLeft | Qt.AlignVCenter, teks)
            x += w

    def _judul_baris(self, p, t, teks, y):
        f = self._huruf(7.6, tebal=True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.1)
        p.setFont(f)
        p.setPen(QColor(t["mut"]))
        lebar_teks = p.fontMetrics().horizontalAdvance(teks)
        p.drawText(QRectF(0, y, LEBAR, 16), Qt.AlignCenter, teks)
        y_garis = y + 8
        p.setPen(QPen(QColor(t["line2"]), 1.0))
        tepi = (LEBAR - lebar_teks) / 2 - 14
        p.drawLine(QPointF(46, y_garis), QPointF(tepi, y_garis))
        p.drawLine(QPointF(LEBAR - tepi, y_garis), QPointF(LEBAR - 46, y_garis))

    def _jalur_alur(self):
        kotak = [self._kotak(k) for k in BARIS_ALUR]
        jalur = QPainterPath(QPointF(kotak[0].right(), kotak[0].center().y()))
        for r in kotak[1:]:
            jalur.lineTo(r.left(), r.center().y())
        return jalur

    def _panah(self, p, t):
        kotak = [self._kotak(k) for k in BARIS_ALUR]
        for a, b in zip(kotak, kotak[1:]):
            y = a.center().y()
            p.setPen(QPen(QColor(t["line"]), 2.0, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawLine(QPointF(a.right() + 3, y), QPointF(b.left() - 9, y))
            kepala = QPainterPath(QPointF(b.left() - 2, y))
            kepala.lineTo(b.left() - 11, y - 5)
            kepala.lineTo(b.left() - 11, y + 5)
            kepala.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(t["line"]))
            p.drawPath(kepala)

    def _titik_alur(self, p, t):
        """Beberapa partikel berjarak tetap menyusuri panah; yang terdepan paling terang."""
        jalur = self._jalur_alur()
        if jalur.isEmpty():
            return
        p.setPen(Qt.NoPen)
        kartu = [self._kotak(k).adjusted(-2, -2, 2, 2) for k in BARIS_ALUR]
        for i, geser in enumerate((0.0, 0.16, 0.32)):
            pos = (self._alur - geser) % 1.0
            titik = jalur.pointAtPercent(pos)
            if any(r.contains(titik) for r in kartu):     # partikel hanya tampak di celah antar-kartu
                continue
            kuat = 1.0 - i * 0.33
            halo = QColor(t["acc"])
            halo.setAlpha(int(55 * kuat))
            p.setBrush(halo)
            p.drawEllipse(titik, 10.0 * kuat, 10.0 * kuat)
            inti = QColor(t["acc"])
            inti.setAlpha(int(255 * kuat))
            p.setBrush(inti)
            p.drawEllipse(titik, 4.0 * kuat, 4.0 * kuat)

    def _kartu(self, p, t, o):
        r = self._kotak(o["kunci"])
        warna = self._warna(o)
        aktif = o["kunci"] in (self.terpilih, self._hover)
        gelap = self._mode() == "gelap"

        urut = (BARIS_ALUR + BARIS_DAMPAK).index(o["kunci"])
        maju = max(0.0, min(1.0, self._masuk * 2.2 - urut * 0.16))     # tiap kartu menyusul 0,16 detik
        if maju <= 0.0:
            return
        sorot = self._hover_t.get(o["kunci"], 0.0)
        p.save()
        p.setOpacity(maju)
        naik = (1.0 - maju) * 16.0 + sorot * 3.0                       # kartu melayang naik saat muncul/disorot
        p.translate(0, -naik)
        if sorot:                                                      # bayangan lembut saat disorot
            bayang = QColor(0, 0, 0, int(26 * sorot))
            p.setPen(Qt.NoPen)
            p.setBrush(bayang)
            p.drawRoundedRect(r.adjusted(2, 5, 2, 7), 13, 13)

        latar = QColor(warna)
        latar.setAlpha(46 if aktif else (30 if gelap else 24))
        p.setBrush(latar)
        p.setPen(QPen(warna if (aktif or o["status"] == "risiko") else QColor(t["line"]), 2.0 if aktif else 1.2))
        p.drawRoundedRect(r, 13, 13)
        if self.hasFocus() and o["kunci"] == self.terpilih:          # penanda fokus papan ketik
            pena_fokus = QPen(QColor(t["acc"]), 1.2, Qt.DashLine)
            p.setPen(pena_fokus)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(4, 4, -4, -4), 9, 9)

        # ikon organ, digambar pada kotak satuan 100 × 100
        isi, detail = bentuk_organ(o["kunci"])
        sisi = 48.0
        p.save()
        p.translate(r.center().x() - sisi / 2, r.top() + 13)
        p.scale(sisi / 100.0, sisi / 100.0)
        isi_warna = QColor(warna)
        isi_warna.setAlpha(225 if o["status"] != "kosong" else 150)
        if o["status"] == "risiko" and self._denyut_sisa > 0:
            denyut = abs(0.5 - self._fase) * 2
            isi_warna.setAlpha(int(165 + 80 * denyut))
            halo = QColor(warna)
            halo.setAlpha(int(70 * (1.0 - denyut)))
            p.setPen(Qt.NoPen)
            p.setBrush(halo)
            p.drawEllipse(QPointF(50, 50), 46 + 10 * (1.0 - denyut), 46 + 10 * (1.0 - denyut))
        p.setBrush(isi_warna)
        p.setPen(QPen(warna.darker(135), 2.0))
        p.drawPath(isi)
        pena = QPen(QColor(t["surf"]), 2.6)
        pena.setCapStyle(Qt.RoundCap)
        p.setPen(pena)
        p.setBrush(Qt.NoBrush)
        p.drawPath(detail)
        p.restore()

        f = self._huruf(8.6)
        p.setFont(f)
        p.setPen(QColor(t["ink"]))
        p.drawText(QRectF(r.left() + 6, r.top() + 66, r.width() - 12, 16), Qt.AlignCenter,
                   o.get("singkat", o["nama"]))
        if o["kunci"] in TAHAP:
            f.setPointSizeF(7.0)
            p.setFont(f)
            p.setPen(QColor(t["mut"]))
            p.drawText(QRectF(r.left() + 6, r.top() + 82, r.width() - 12, 14), Qt.AlignCenter, TAHAP[o["kunci"]])

        f.setPointSizeF(13.5)
        f.setBold(True)
        p.setFont(f)
        p.setPen(warna.darker(125) if not gelap else warna.lighter(115))
        teks = f"{o['skor']:.0f}" if o["skor"] is not None else (o.get("info") or "–")
        p.drawText(QRectF(r.left(), r.bottom() - 44, r.width(), 22), Qt.AlignCenter, teks)

        if self._riak and self._riak[0] == o["kunci"]:                 # riak sekali saat kartu dipilih
            maju_riak = self._riak[1]
            cincin = QColor(warna)
            cincin.setAlpha(int(120 * (1.0 - maju_riak)))
            p.setPen(QPen(cincin, 2.0))
            p.setBrush(Qt.NoBrush)
            tumbuh = 10.0 + 26.0 * maju_riak
            p.drawRoundedRect(r.adjusted(-tumbuh, -tumbuh, tumbuh, tumbuh), 20, 20)

        bilah = QRectF(r.left() + 20, r.bottom() - 18, r.width() - 40, 6)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t["line2"]))
        p.drawRoundedRect(bilah, 3, 3)
        if o["skor"] is not None:
            s = max(0.0, min(100.0, self._skor_tampil.get(o["kunci"], o["skor"])))
            terisi = QRectF(bilah)
            terisi.setWidth(max(4.0, bilah.width() * s / 100.0))
            p.setBrush(warna)
            p.drawRoundedRect(terisi, 3, 3)
        elif o.get("info"):
            f.setPointSizeF(6.8)
            f.setBold(False)
            p.setFont(f)
            p.setPen(QColor(t["mut"]))
            p.drawText(QRectF(r.left(), r.bottom() - 22, r.width(), 12), Qt.AlignCenter, "informasi, bukan risiko")
        p.restore()

    # ------------------------------------------------------------------ interaksi
    def _organ_di(self, titik):
        k, dx, dy = self._skala()
        q = QPointF((titik.x() - dx) / k, (titik.y() - dy) / k)
        return next((kunci for kunci in BARIS_ALUR + BARIS_DAMPAK if self._kotak(kunci).contains(q)), None)

    def mouseMoveEvent(self, e):
        kunci = self._organ_di(e.position())
        if kunci == self._hover:
            return
        self._hover = kunci
        if kunci:
            self._hover_t.setdefault(kunci, 0.0)
        self._t.start()
        self.setCursor(Qt.PointingHandCursor if kunci else Qt.ArrowCursor)
        o = self.organ_kunci(kunci) if kunci else None
        if o is None:
            self.setToolTip("")
        elif o["skor"] is not None:
            self.setToolTip(f"{o['nama']} — skor {o['skor']:.0f}/100")
        else:
            self.setToolTip(f"{o['nama']} — {o['endpoint'][0]['label']}: {o.get('info') or '–'} "
                            "(informasi, bukan penilaian risiko)")
        self.update()

    def mousePressEvent(self, e):
        kunci = self._organ_di(e.position())
        if kunci:
            self.setFocus(Qt.MouseFocusReason)
            self.pilih(kunci)

    def keyPressEvent(self, e):
        """Panah kiri/kanan berpindah kartu dalam satu baris, atas/bawah berpindah baris."""
        urut = BARIS_ALUR + BARIS_DAMPAK
        if e.key() not in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            return super().keyPressEvent(e)
        kini = self.terpilih or urut[0]
        baris = BARIS_ALUR if kini in BARIS_ALUR else BARIS_DAMPAK
        lain = BARIS_DAMPAK if kini in BARIS_ALUR else BARIS_ALUR
        i = baris.index(kini)
        if e.key() == Qt.Key_Left:
            self.pilih(baris[(i - 1) % len(baris)])
        elif e.key() == Qt.Key_Right:
            self.pilih(baris[(i + 1) % len(baris)])
        else:
            self.pilih(lain[min(i, len(lain) - 1)])

    def pilih(self, kunci):
        self.terpilih = kunci
        if self._alur_hidup:
            self._riak = (kunci, 0.0)        # lingkaran menyebar sekali sebagai tanda pilihan
            self._t.start()
        self.update()
        self.organDipilih.emit(kunci)

    # ------------------------------------------------------------------ ekspor
    def simpan_png(self, jalur, lebar=1600):
        from PySide6.QtGui import QImage
        tinggi = int(lebar * TINGGI / LEBAR)
        img = QImage(lebar, tinggi, QImage.Format_ARGB32)
        img.fill(QColor(theme.TOKEN[self._mode()]["surf"]))
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(lebar / LEBAR, tinggi / TINGGI)
        hidup, self._alur_hidup = self._alur_hidup, False      # ekspor selalu gambar diam
        masuk, self._masuk, riak, self._riak = self._masuk, 1.0, self._riak, None
        self.gambar(p, theme.TOKEN[self._mode()])
        self._alur_hidup, self._masuk, self._riak = hidup, masuk, riak
        p.end()
        return img.save(str(jalur))

    def simpan_svg(self, jalur):
        from PySide6.QtSvg import QSvgGenerator
        gen = QSvgGenerator()
        gen.setFileName(str(jalur))
        gen.setSize(QRectF(0, 0, LEBAR, TINGGI).size().toSize())
        gen.setViewBox(QRectF(0, 0, LEBAR, TINGGI))
        gen.setTitle("Peta ADMET per organ - VirmoLab")
        p = QPainter(gen)
        p.setRenderHint(QPainter.Antialiasing)
        hidup, self._alur_hidup = self._alur_hidup, False
        masuk, self._masuk, riak, self._riak = self._masuk, 1.0, self._riak, None
        self.gambar(p, theme.TOKEN[self._mode()])
        self._alur_hidup, self._masuk, self._riak = hidup, masuk, riak
        p.end()
        return True
