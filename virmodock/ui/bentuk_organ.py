"""Ikon organ untuk peta ADMET — dua dimensi, datar, digambar sendiri.

Tiap organ dirakit dari bentuk dasar (elips, persegi membulat, busur) lalu digabung atau dilubangi, bukan dari
kurva tangan yang sulit ditebak. Hasilnya siluet bersih yang tetap rapi pada ikon kecil maupun ekspor 4K, serasi
dengan ikon garis aplikasi, dan bebas ketergantungan aset berlisensi.

`bentuk(kunci)` → (isi, garis). `isi` diwarnai menurut risiko; `garis` digambar di atasnya dengan warna latar
sebagai detail dalam (lekuk otak, sekat bilik jantung, gelung usus).
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainterPath, QPainterPathStroker, QTransform

K = 100.0        # sisi kotak satuan tiap ikon


def _elips(cx, cy, rx, ry, putar=0.0):
    j = QPainterPath()
    j.addEllipse(QPointF(cx, cy), rx, ry)
    if putar:
        j = QTransform().translate(cx, cy).rotate(putar).translate(-cx, -cy).map(j)
    return j


def _kotak(x, y, w, h, r=10.0):
    j = QPainterPath()
    j.addRoundedRect(QRectF(x, y, w, h), r, r)
    return j


def _gabung(*bagian):
    j = QPainterPath()
    for b in bagian:
        j = j.united(b)
    return j


def _tabung(jalur, tebal):
    """Ubah garis menjadi bentuk berisi — dipakai untuk pembuluh, aorta, dan usus penghubung."""
    s = QPainterPathStroker()
    s.setWidth(tebal)
    s.setCapStyle(Qt.RoundCap)
    s.setJoinStyle(Qt.RoundJoin)
    return s.createStroke(jalur)


def _busur(cx, cy, rx, ry, mulai, rentang):
    """Garis busur (tanpa isi) untuk detail; sudut dalam derajat, berlawanan arah jarum jam."""
    kotak = QRectF(cx - rx, cy - ry, 2 * rx, 2 * ry)
    j = QPainterPath()
    j.arcMoveTo(kotak, mulai)
    j.arcTo(kotak, mulai, rentang)
    return j


def _otak():
    """Dua belahan berlekuk dengan batang otak."""
    isi = _gabung(_elips(36, 42, 26, 27), _elips(64, 42, 26, 27), _elips(50, 34, 30, 20),
                  _elips(50, 58, 28, 21), _kotak(44, 66, 12, 24, 6))
    garis = QPainterPath()
    garis.moveTo(50, 16)
    garis.cubicTo(50, 38, 50, 54, 50, 70)                      # celah antarbelahan
    for arah in (-1, 1):
        for y, r in ((31, 11), (45, 13), (58, 10)):            # tiga lekuk tiap belahan
            garis.addPath(_busur(50 + arah * 17, y, r, r * 0.62, 90, 180 * arah))
    return isi, garis


def _jantung():
    """Jantung anatomis tampak depan: apeks ke kiri bawah, lengkung aorta dan arteri pulmonalis di atas."""
    badan = QPainterPath()
    badan.moveTo(30, 40)
    badan.cubicTo(28, 22, 50, 14, 54, 30)                      # serambi kiri
    badan.cubicTo(60, 16, 84, 24, 80, 44)                      # serambi kanan
    badan.cubicTo(77, 64, 62, 80, 42, 90)                      # dinding kanan menuju apeks
    badan.cubicTo(26, 76, 22, 58, 30, 40)                      # dinding kiri kembali ke atas
    badan.closeSubpath()
    aorta = QPainterPath()
    aorta.moveTo(56, 28)
    aorta.cubicTo(58, 8, 80, 10, 78, 26)                       # lengkung aorta
    pulmonal = QPainterPath()
    pulmonal.moveTo(42, 28)
    pulmonal.cubicTo(36, 14, 26, 12, 22, 20)                   # arteri pulmonalis
    isi = _gabung(badan, _tabung(aorta, 11), _tabung(pulmonal, 9))
    garis = QPainterPath()
    garis.moveTo(56, 36)
    garis.cubicTo(50, 50, 52, 64, 44, 82)                      # sekat antarbilik menuju apeks
    garis.moveTo(70, 52)
    garis.cubicTo(62, 58, 54, 62, 46, 64)                      # alur koroner
    return isi, garis


def _hati():
    """Lobus kanan besar, lobus kiri kecil, kantong empedu."""
    isi = _gabung(_elips(40, 50, 34, 23, -8), _elips(70, 46, 20, 16, -12), _kotak(14, 36, 60, 28, 14))
    garis = QPainterPath()
    garis.moveTo(58, 27)
    garis.cubicTo(56, 43, 55, 56, 53, 70)                      # alur antar-lobus
    garis.addPath(_elips(34, 64, 7, 5))                        # kantong empedu
    garis.moveTo(20, 44)
    garis.cubicTo(30, 47, 40, 48, 48, 48)                      # pembuluh porta
    return isi, garis


def _cerna():
    """Lambung berbentuk J dengan lengkung besar, duodenum, lalu gelung usus."""
    lambung = QPainterPath()
    lambung.moveTo(24, 18)
    lambung.cubicTo(22, 4, 46, 2, 52, 14)                      # fundus dan kardia
    lambung.cubicTo(58, 24, 60, 32, 56, 38)                    # korpus menurun
    lambung.cubicTo(52, 44, 40, 44, 32, 36)                    # antrum melengkung ke kiri
    lambung.cubicTo(24, 28, 22, 24, 24, 18)
    lambung.closeSubpath()
    duodenum = QPainterPath()
    duodenum.moveTo(55, 36)
    duodenum.cubicTo(72, 42, 72, 54, 60, 58)                   # pilorus menuju usus
    isi = _gabung(lambung, _tabung(duodenum, 9), _kotak(16, 54, 68, 36, 15))
    garis = QPainterPath()
    garis.moveTo(30, 20)
    garis.cubicTo(36, 28, 42, 33, 48, 34)                      # lengkung kecil lambung
    for y in (64, 73, 82):                                     # gelung usus
        garis.moveTo(24, y)
        garis.cubicTo(40, y - 6, 60, y + 6, 76, y)
    return isi, garis


def _ginjal():
    """Sepasang ginjal berbentuk kacang, terpisah jelas, pembuluh menuju tengah."""
    def kacang(x0):
        luar = _gabung(_elips(x0 + 16, 50, 16, 26), _elips(x0 + 22, 50, 13, 21))
        return luar.subtracted(_elips(x0 + 37, 50, 10, 8))     # takik hilus, secukupnya
    kiri = kacang(5)
    isi = _gabung(kiri, QTransform().translate(K, 0).scale(-1, 1).map(kiri))
    garis = QPainterPath()
    for arah, x in ((1, 35), (-1, 65)):                        # pembuluh dan ureter
        garis.moveTo(x, 50)
        garis.cubicTo(x + 7 * arah, 53, x + 9 * arah, 63, x + 4 * arah, 74)
    garis.addPath(_busur(20, 50, 7, 12, 250, 220))             # piramida ginjal
    garis.addPath(_busur(80, 50, 7, 12, 70, 220))
    return isi, garis


def _kulit():
    """Potongan kulit berlapis dengan folikel dan kelenjar."""
    isi = _kotak(12, 20, 76, 60, 14)
    garis = QPainterPath()
    for y in (38, 52, 66):                                     # epidermis – dermis – subkutis
        garis.moveTo(14, y)
        garis.cubicTo(36, y - 5, 64, y + 5, 86, y)
    garis.moveTo(34, 26)
    garis.cubicTo(38, 42, 33, 54, 37, 70)                      # folikel rambut
    garis.addPath(_elips(63, 62, 6, 5))                        # kelenjar
    return isi, garis


def _sel():
    """Sel dengan inti, untai kromatin, dan dua organel."""
    isi = _elips(50, 50, 40, 36)
    garis = QPainterPath()
    garis.addPath(_elips(50, 50, 18, 16))                      # inti
    for geser in (-5, 5):                                      # untai DNA
        garis.moveTo(50 + geser, 38)
        garis.cubicTo(50 - geser * 2, 44, 50 - geser * 2, 56, 50 + geser, 62)
    for y in (45, 50, 55):
        garis.moveTo(45, y)
        garis.lineTo(55, y)
    garis.addPath(_elips(76, 36, 5, 4))
    garis.addPath(_elips(25, 62, 5, 4))
    return isi, garis


def _sistemik():
    """Paparan menyeluruh: kapsul obat dengan pancaran — tanpa figur manusia."""
    pancaran = QPainterPath()
    for x1, y1, x2, y2 in ((15, 50, 4, 50), (85, 50, 96, 50), (27, 31, 19, 20), (73, 31, 81, 20),
                           (27, 69, 19, 80), (73, 69, 81, 80)):
        pancaran.moveTo(x1, y1)
        pancaran.lineTo(x2, y2)
    isi = _gabung(_kotak(22, 36, 56, 28, 14), _tabung(pancaran, 6))
    garis = QPainterPath()
    garis.moveTo(50, 37)
    garis.lineTo(50, 63)                                       # batas dua bagian kapsul
    return isi, garis


BENTUK = {"otak": _otak, "jantung": _jantung, "hati": _hati, "cerna": _cerna, "ginjal": _ginjal,
          "kulit": _kulit, "sel": _sel, "sistemik": _sistemik}


def bentuk(kunci):
    """(isi, garis) organ pada kotak satuan 100 × 100; kunci tak dikenal → lingkaran polos."""
    buat = BENTUK.get(kunci)
    if buat:
        return buat()
    return _elips(50, 50, 38, 38), QPainterPath()
