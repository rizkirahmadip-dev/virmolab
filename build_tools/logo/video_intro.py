"""Video pembuka logo VirmoLab (latar putih, 60 fps, H.264) -> branding/promosi/virmolab_intro_<tata>.mp4

Koreografi (detik):
  0,1-0,8   titik cahaya azure di dasar kantong
  0,3-1,7   lima faset tumbuh dari titik kantong, berputar halus ke tempatnya (kristal terbentuk)
  1,05-2,05 ligan turun sambil berputar lalu tertambat di kantong; dua riak menyebar di belakang tanda
  2,15-3,05 kilau cahaya menyapu permukaan tanda
  2,4-3,35  tanda bergeser ke posisi logo; 3,22 huruf VirmoLab naik satu per satu; 3,95 tagline merapat
  5,1-6,2   diam (logo utuh)

  .venv\\Scripts\\python.exe build_tools\\logo\\video_intro.py [fhd|uhd|tegak ...] [--stills]
"""
import math
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QGuiApplication, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen, QRadialGradient, QTransform)

app = QGuiApplication.instance() or QGuiApplication(sys.argv)
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from buat_logo import teks_ke_path  # noqa: E402
from eksplorasi_virmolab import S3, heks  # noqa: E402

AKAR = Path(__file__).resolve().parents[2]
OUT = AKAR / "branding" / "promosi"
OUT.mkdir(parents=True, exist_ok=True)

FPS, DURASI = 60, 6.2
NAVY, AZURE, TAG_WARNA = "#12305a", "#2f74e0", "#6b7a90"
FONT, TAG = "Figtree Light", "VIRTUAL MOLECULAR LAB"
TATA = {"fhd": (1920, 1080, "datar"), "uhd": (3840, 2160, "datar"), "tegak": (1080, 1920, "tegak")}


def campur(a, b, t):
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return QColor(*[round(x + (y - x) * t) for x, y in zip(pa, pb)])


# ---------------------------------------------------------------- geometri tanda (sama dengan produksi_virmolab)
CX, CY, R = 50.0, 56.0, 42.0
S_LIG, CELAH = 11.5, 4.2
_h = heks(CX, CY, R)
APEX = QPointF(CX, CY)
LUAR = [_h[5], _h[0], _h[1], _h[2], _h[3], _h[4]]
FASET_WARNA = [campur(NAVY, "#ffffff", 0.16), campur(NAVY, "#ffffff", 0.09), campur(NAVY, "#ffffff", 0.03),
               campur(NAVY, "#000000", 0.05), campur(NAVY, "#000000", 0.12)]
Y_LIG = CY - (2 * CELAH + S_LIG * S3)
BB = (CX - R, Y_LIG - S_LIG * S3 / 2, CX + R, CY + R * S3 / 2)
BBW, BBH = BB[2] - BB[0], BB[3] - BB[1]
BBC = QPointF((BB[0] + BB[2]) / 2, (BB[1] + BB[3]) / 2)


def poligon(pts):
    p = QPainterPath(QPointF(*pts[0]))
    for q in pts[1:]:
        p.lineTo(QPointF(*q))
    p.closeSubpath()
    return p


def poligon_bulat(pts, rr):
    p = QPainterPath()
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]

        def ke(q):
            dx, dy = q[0] - p1[0], q[1] - p1[1]
            k = rr / math.hypot(dx, dy)
            return QPointF(p1[0] + dx * k, p1[1] + dy * k)
        a, b = ke(p0), ke(p2)
        (p.moveTo if i == 0 else p.lineTo)(a)
        p.quadTo(QPointF(*p1), b)
    p.closeSubpath()
    return p


FASET = [poligon([(CX, CY), LUAR[i], LUAR[i + 1]]) for i in range(5)]
BADAN = poligon([_h[4], (CX, CY), _h[5], _h[0], _h[1], _h[2], _h[3]])
LIGAN = poligon_bulat(heks(0, 0, S_LIG), 0.95)          # berpusat di (0, 0)


# ---------------------------------------------------------------- easing
def klem(x):
    return max(0.0, min(1.0, x))


def fase(t, mulai, lama):
    return klem((t - mulai) / lama)


def out_cubic(p):
    return 1 - (1 - p) ** 3


def out_expo(p):
    return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)


def inout_cubic(p):
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def out_back(p, s=1.25):
    return 1 + (s + 1) * (p - 1) ** 3 + s * (p - 1) ** 2


def inout_sine(p):
    return -(math.cos(math.pi * p) - 1) / 2


# ---------------------------------------------------------------- tata letak
class Tata:
    def __init__(self, W, H, mode):
        self.W, self.H, self.mode = W, H, mode
        fm = lambda b: QFontMetricsF(self._font(b))  # noqa: E731
        if mode == "datar":
            hm = 0.30 * H
            self.kap = 0.40 * hm
            self.kap_tag = 0.075 * hm
            self.k = hm / BBH
            mw = BBW * self.k
            huruf, lebar_wm = self._huruf(0, 0)
            L = mw + 0.24 * hm + lebar_wm
            kiri = (W - L) / 2
            self.akhir = QPointF(kiri + mw / 2, H / 2)
            tx = kiri + mw + 0.24 * hm
            blok = self.kap + 0.16 * hm + self.kap_tag
            self.base = H / 2 - hm / 2 + (hm - blok) / 2 + self.kap
            self.huruf, _ = self._huruf(tx, self.base)
            self.tag_x, self.tag_tengah = tx + 0.012 * hm, False
            self.tag_base = self.base + 0.16 * hm + self.kap_tag
            self.awal_k = self.k * 1.18
        else:
            hm = 0.20 * H
            self.kap = 0.30 * hm
            self.kap_tag = 0.058 * hm
            self.k = hm / BBH
            blok = hm + 0.24 * hm + self.kap + 0.15 * hm + self.kap_tag
            atas = (H - blok) / 2
            self.akhir = QPointF(W / 2, atas + hm / 2)
            self.base = atas + hm + 0.24 * hm + self.kap
            _, lebar_wm = self._huruf(0, 0)
            self.huruf, _ = self._huruf((W - lebar_wm) / 2, self.base)
            self.tag_x, self.tag_tengah = W / 2, True
            self.tag_base = self.base + 0.15 * hm + self.kap_tag
            self.awal_k = self.k * 1.15
        self.awal = QPointF(W / 2, H / 2)
        del fm

    @staticmethod
    def _font(berat):
        f = QFont(FONT)
        f.setPixelSize(200)
        f.setWeight(QFont.Weight(berat))
        f.setHintingPreference(QFont.PreferNoHinting)
        return f

    def _huruf(self, x, base):
        """Daftar (path huruf, x, skala) per huruf, posisi mengikuti wordmark statis (Virmo 600 + Lab 300)."""
        out, cur = [], x
        for i, (bagian, berat) in enumerate((("Virmo", 600), ("Lab", 300))):
            path, kotak, kap0 = teks_ke_path(bagian, FONT, berat, 200, 0.0)
            sk = self.kap / kap0
            if i == 0:
                cur -= kotak.left() * sk
            fm = QFontMetricsF(self._font(berat))
            for j, c in enumerate(bagian):
                xj = fm.horizontalAdvance(bagian[:j + 1]) - fm.horizontalAdvance(c)
                pj, _, _ = teks_ke_path(c, FONT, berat, 200, 0.0)
                out.append((pj, cur + xj * sk, base, sk))
            cur += kotak.right() * sk
        return out, cur - x


def latar(W, H):
    """Putih polos. (Vinyet halus sempat dicoba, tetapi encoder H.264 membuang dithering-nya -> pita/banding.)"""
    img = QImage(W, H, QImage.Format_ARGB32)
    img.fill(QColor("#ffffff"))
    return img


def bayangan(ukuran):
    """Siluet tanda diburamkan (Pillow) -> QImage navy transparan; ukuran = lebar px untuk 1 satuan k."""
    from PIL import Image, ImageFilter
    s = 8.0
    w, h = int(BBW * s + 160), int(BBH * s + 160)
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(80 - BB[0] * s, 80 - BB[1] * s)
    p.scale(s, s)
    p.fillPath(BADAN, QColor(0, 0, 0))
    p.end()
    ptr = img.constBits()
    arr = np.frombuffer(ptr, np.uint8).reshape(h, img.bytesPerLine() // 4, 4)[:, :w]
    alfa = Image.fromarray(arr[..., 3].copy()).filter(ImageFilter.GaussianBlur(22))
    al = np.asarray(alfa, np.float32) * 0.20
    out = np.zeros((h, w, 4), np.uint8)
    out[..., 0], out[..., 1], out[..., 2] = 90, 48, 18                 # BGRA navy
    out[..., 3] = al.astype(np.uint8)
    q = QImage(np.ascontiguousarray(out).data, w, h, w * 4, QImage.Format_ARGB32)
    return q.copy(), s


# ---------------------------------------------------------------- gambar satu bingkai
def bingkai(t, T, bg, bay):
    W, H = T.W, T.H
    img = bg.copy()
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)

    mv = inout_cubic(fase(t, 2.4, 0.95))
    pos = QPointF(T.awal.x() + (T.akhir.x() - T.awal.x()) * mv, T.awal.y() + (T.akhir.y() - T.awal.y()) * mv)
    k = T.awal_k + (T.k - T.awal_k) * mv
    tf = QTransform()
    tf.translate(pos.x(), pos.y())
    tf.scale(k, k)
    tf.translate(-BBC.x(), -BBC.y())

    # bayangan lembut di bawah tanda
    rakit = out_cubic(fase(t, 0.6, 1.4))
    if rakit > 0:
        img_b, s = bay
        p.save()
        p.setTransform(tf)
        p.setOpacity(rakit)
        p.translate(BB[0] - 80 / s, BB[1] - 80 / s + 5.5)
        p.scale(1 / s, 1 / s)
        p.drawImage(0, 0, img_b)
        p.restore()

    # riak tambat (di belakang tanda)
    for mulai in (1.62, 1.82):
        q = fase(t, mulai, 1.05)
        if 0 < q < 1:
            e = out_cubic(q)
            p.save()
            p.setTransform(tf)
            c = QColor(AZURE)
            c.setAlphaF(0.42 * (1 - e) ** 1.4)
            p.setPen(QPen(c, 0.9))
            p.setBrush(Qt.NoBrush)
            rr = 16 + 40 * e
            p.drawEllipse(QPointF(CX, Y_LIG + 6), rr, rr)
            p.restore()

    # titik cahaya awal
    q = fase(t, 0.1, 0.7)
    if 0 < q < 1:
        p.save()
        p.setTransform(tf)
        g = QRadialGradient(APEX, 6)
        c0 = QColor(AZURE)
        c0.setAlphaF(math.sin(math.pi * q) * 0.9)
        c1 = QColor(AZURE)
        c1.setAlphaF(0)
        g.setColorAt(0, c0)
        g.setColorAt(1, c1)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(APEX, 6, 6)
        p.restore()

    # lapisan dasar di bawah faset (menutup garis rambut antar-faset) setelah semua faset terpasang
    q = fase(t, 1.5, 0.25)
    if q > 0:
        p.save()
        p.setTransform(tf)
        p.setOpacity(q)
        p.fillPath(BADAN, FASET_WARNA[2])
        p.restore()

    # faset
    for i, (path, warna) in enumerate(zip(FASET, FASET_WARNA)):
        q = fase(t, 0.30 + 0.11 * i, 1.0)
        if q <= 0:
            continue
        e = out_expo(q)
        p.save()
        p.setTransform(tf)
        p.translate(APEX)
        p.rotate(-16 * (1 - e))
        sc = 0.25 + 0.75 * e
        p.scale(sc, sc)
        p.translate(-APEX.x(), -APEX.y())
        p.setOpacity(klem(q * 2.4))
        p.fillPath(path, warna)
        p.restore()

    # ligan
    q = fase(t, 1.05, 1.0)
    if q > 0:
        e = out_back(q)
        p.save()
        p.setTransform(tf)
        p.translate(CX, Y_LIG - 40 * (1 - e))
        p.rotate(120 * (1 - out_cubic(q)))
        sc = 0.6 + 0.4 * out_cubic(q)
        p.scale(sc, sc)
        p.setOpacity(klem(q / 0.35))
        p.fillPath(LIGAN, QColor(AZURE))
        p.restore()

    # kilau
    q = fase(t, 2.15, 0.9)
    if 0 < q < 1:
        e = inout_sine(q)
        klip = QPainterPath(BADAN)
        lig = QTransform().translate(CX, Y_LIG).map(LIGAN)
        klip = klip.united(lig)
        p.save()
        p.setTransform(tf)
        p.setClipPath(klip)
        cx = BB[0] - 40 + (BBW + 80) * e
        g = QLinearGradient(QPointF(cx - 16, BBC.y() - 7), QPointF(cx + 16, BBC.y() + 7))   # pita miring
        for pos_, a in ((0, 0), (0.5, 0.32), (1, 0)):
            c = QColor(255, 255, 255)
            c.setAlphaF(a)
            g.setColorAt(pos_, c)
        p.fillRect(QRectF(BB[0] - 60, BB[1] - 20, BBW + 120, BBH + 40), g)
        p.restore()

    # huruf
    for j, (path, x, base, sk) in enumerate(T.huruf):
        mulai = 3.22 + 0.055 * j + (0.05 if j >= 5 else 0)
        q = fase(t, mulai, 0.75)
        if q <= 0:
            continue
        e = out_cubic(q)
        p.save()
        p.translate(x, base + (1 - e) * 0.30 * T.kap)
        p.scale(sk, sk)
        p.setOpacity(e)
        p.fillPath(path, QColor(NAVY))
        p.restore()

    # tagline
    q = fase(t, 3.95, 1.1)
    if q > 0:
        e = out_cubic(q)
        spasi = 0.26 + 0.44 * (1 - e)
        path, kotak, kap0 = teks_ke_path(TAG, FONT, 500, 200, spasi)
        sk = T.kap_tag / kap0
        x = T.tag_x - (kotak.width() * sk / 2 if T.tag_tengah else 0)
        p.save()
        p.translate(x - kotak.left() * sk, T.tag_base)
        p.scale(sk, sk)
        p.setOpacity(e)
        p.fillPath(path, QColor(TAG_WARNA))
        p.restore()

    p.end()
    return img


# ---------------------------------------------------------------- keluaran
def stills(nama):
    W, H, mode = TATA[nama]
    T = Tata(W, H, mode)
    bg, bay = latar(W, H), bayangan(1)
    waktu = [0.35, 0.8, 1.35, 1.75, 2.5, 3.1, 3.6, 4.2, 6.0]
    lw = 640
    lh = int(lw * H / W)
    lembar = QImage(lw * 3 + 40, lh * 3 + 40, QImage.Format_RGB32)
    lembar.fill(QColor("#cfd6e0"))
    p = QPainter(lembar)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    for i, t in enumerate(waktu):
        im = bingkai(t, T, bg, bay)
        p.drawImage(QRectF(10 + (i % 3) * (lw + 10), 10 + (i // 3) * (lh + 10), lw, lh), im)
        if t == waktu[-1]:
            im.save(str(OUT / f"virmolab_intro_{nama}_akhir.png"))
    p.end()
    lembar.save(str(OUT / f"_cek_intro_{nama}.png"))


def video(nama):
    from virmodock.ui.perekam_video import PerekamVideo
    W, H, mode = TATA[nama]
    T = Tata(W, H, mode)
    bg, bay = latar(W, H), bayangan(1)
    n = int(round(DURASI * FPS))
    f = str(OUT / f"virmolab_intro_{nama}.mp4")
    rek = PerekamVideo(f, W, H, FPS)
    state = {"i": 0, "hasil": None}

    def pompa():
        while state["i"] < n and rek.boleh_lagi():
            rek.kirim(bingkai(state["i"] / FPS, T, bg, bay))
            state["i"] += 1
        if state["i"] >= n and not rek._tutup:
            rek.akhiri()

    rek.siap_lagi.connect(pompa)
    rek.selesai.connect(lambda path: (state.update(hasil=path), app.quit()))
    rek.galat.connect(lambda e: (print("GALAT", e), app.quit()))
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, pompa)
    app.exec()
    print(nama, "->", state["hasil"], f"({n} bingkai)")


if __name__ == "__main__":
    pilih = [a for a in sys.argv[1:] if a in TATA] or ["fhd"]
    for nm in pilih:
        if "--stills" in sys.argv:
            stills(nm)
        else:
            video(nm)
