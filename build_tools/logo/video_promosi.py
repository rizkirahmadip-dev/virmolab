"""Video promosi VirmoLab (tegak 1080 x 1920, 60 fps, tanpa suara, < 60 detik) -> branding/promosi/virmolab_promosi.mp4

Urutan: splash logo (video_intro) -> logo meluncur ke slide 1 -> slide 1-6 story (promosi_story, termasuk galeri grafik) dengan elemen muncul
bertahap; kartu slide 2 diisi klip 3D sinematik dari viewer VirmoLab (rekam_3d_promosi) -> memudar ke putih.

  .venv\\Scripts\\python.exe build_tools\\logo\\rekam_3d_promosi.py <folder_klip> 12 60
  .venv\\Scripts\\python.exe build_tools\\logo\\video_promosi.py <folder_klip> [--stills]
"""
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QByteArray, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath
from PySide6.QtSvg import QSvgRenderer

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import promosi_story as PS  # noqa: E402
import video_intro as VI  # noqa: E402

KLIP = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else None
W, H = 1080, 1920
FPS = 30 if "--30fps" in sys.argv else 60     # --30fps: versi ringan untuk dikirim lewat HP
KLIP_FPS = 60                                    # bingkai klip 3D direkam 60 fps
OUT = PS.OUT
SPLASH = VI.DURASI                       # 6,2 s
SLIDE = [(PS.slide1, 6.0), (PS.slide2, 12.2), (PS.slide3, 8.5), (PS.slide4, 8.5), (PS.slide5, 8.5),
         (PS.slide6, 8.0)]
KLIP_MULAI, KLIP_DETIK, KLIP_LAJU = 0.7, 12.0, 1.1     # relatif terhadap awal slide 2; klip diputar 1,1x
TOTAL = SPLASH + sum(d for _, d in SLIDE)


def in_cubic(p):
    return p ** 3


# ---------------------------------------------------------------- lapisan per elemen slide
def _render_lapisan(isi):
    s = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'viewBox="0 0 {W} {H}" width="{W}" height="{H}">{isi}</svg>')
    img = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(QByteArray(s.encode())).render(p, QRectF(0, 0, W, H))
    p.end()
    a = _alfa(img)
    ys, xs = np.nonzero(a)
    if not len(xs):
        return None
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    return img.copy(int(x0), int(y0), int(x1 - x0), int(y1 - y0)), int(x0), int(y0)


def _alfa(img):
    arr = np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)
    return arr[:, :img.width(), 3]


def lapisan_slide(fn, no):
    PS.svg = lambda isi: isi                     # ambil daftar elemen, bukan SVG utuh
    isi = fn()
    n_air = 2 if no == 1 else 1
    out, k = [], 0
    for i, e in enumerate(isi):
        r = _render_lapisan(e)
        if not r:
            continue
        img, x, y = r
        jenis = "air" if i < n_air else "kepala" if i == n_air else "kartu" if "<image" in e else "isi"
        d = {"img": img, "x": x, "y": y, "jenis": jenis, "urut": k}
        if jenis in ("isi", "kartu"):
            k += 1
        if jenis == "kartu":                     # area tangkapan layar = piksel opak penuh (bayangan < 255)
            a = _alfa(img)
            ys, xs = np.nonzero(a >= 250)
            d["dalam"] = QRectF(x + xs.min(), y + ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1)
        out.append(d)
    return out


# ---------------------------------------------------------------- splash -> slide 1
def bbox_opak(img, ambang=200):
    ys, xs = np.nonzero(_alfa(img) >= ambang)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


class Klip:
    def __init__(self, folder):
        self.f = sorted(Path(folder).glob("f_*.jpg")) if folder else []
        self._cache = (None, None)

    def bingkai(self, t, ukuran):
        if not self.f:
            return None
        i = min(len(self.f) - 1, max(0, int(round(t * KLIP_FPS))))
        if self._cache[0] != (i, ukuran):
            im = QImage(str(self.f[i])).scaled(ukuran[0], ukuran[1], Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self._cache = ((i, ukuran), im)
        return self._cache[1]


def siapkan():
    T = VI.Tata(W, H, "tegak")
    bg, bay = VI.latar(W, H), VI.bayangan(1)
    transparan = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    transparan.fill(Qt.transparent)
    akhir_splash = VI.bingkai(SPLASH, T, transparan, bay)
    slides = [lapisan_slide(fn, i + 1) for i, (fn, _) in enumerate(SLIDE)]
    logo1 = next(d for d in slides[0] if d["jenis"] == "isi" and d["urut"] == 1)   # urut 0 = label, 1 = logo
    logo1["dari_splash"] = True
    sx0, sy0, sx1, sy1 = bbox_opak(akhir_splash)
    lx0, ly0, lx1, ly1 = bbox_opak(logo1["img"])
    lx0, lx1, ly0, ly1 = lx0 + logo1["x"], lx1 + logo1["x"], ly0 + logo1["y"], ly1 + logo1["y"]
    k = (ly1 - ly0) / (sy1 - sy0)
    peta = {"k": k, "dari": ((sx0 + sx1) / 2, (sy0 + sy1) / 2), "ke": ((lx0 + lx1) / 2, (ly0 + ly1) / 2)}
    return {"T": T, "bg": bg, "bay": bay, "splash": akhir_splash, "peta": peta, "slides": slides, "klip": Klip(KLIP)}


# ---------------------------------------------------------------- satu bingkai
def gambar_slide(p, lap, t0, dur, t, data, no):
    lokal = t - t0
    keluar = VI.fase(t, t0 + dur - 0.6, 0.6) if no < len(SLIDE) else 0.0
    ek = in_cubic(keluar)
    n_isi = sum(1 for d in lap if d["jenis"] in ("isi", "kartu"))
    jeda = 0.12 if n_isi <= 10 else 0.075
    for d in lap:
        j = d["jenis"]
        dy, sc = 0.0, 1.0
        if j == "air":
            o = VI.out_cubic(VI.fase(t, t0, 1.2)) * (1 - ek)
            dy = 30 * (1 - lokal / dur)
        elif j == "kepala":
            o = VI.out_cubic(VI.fase(t, t0 + 0.1, 0.5)) * (1 - ek)
        else:
            if d.get("dari_splash"):
                o = VI.fase(t, t0 + 0.8, 0.3)
            else:
                mulai = t0 + (0.55 if no == 1 else 0.3) + jeda * d["urut"]
                q = VI.fase(t, mulai, 0.85 if j == "kartu" else 0.8)
                e = VI.out_cubic(q)
                o = e
                dy = 36 * (1 - e)
                if j == "kartu":
                    sc = 0.965 + 0.035 * e + (0.012 * lokal / dur if no != 2 else 0)
            o *= 1 - ek
            dy -= 24 * ek
        if o <= 0.002:
            continue
        img = d["img"]
        p.save()
        p.setOpacity(o)
        cx, cy = d["x"] + img.width() / 2, d["y"] + img.height() / 2 + dy
        p.translate(cx, cy)
        p.scale(sc, sc)
        p.translate(-img.width() / 2, -img.height() / 2)
        if j == "kartu" and no == 2:
            # kartu + klip disusun dulu di gambar sementara, lalu diburamkan bersama (tanpa bayangan ganda)
            r = d["dalam"]
            ukuran = (round(r.width()), round(r.height()))
            fr = data["klip"].bingkai(min(KLIP_DETIK, max(0.0, (lokal - KLIP_MULAI) * KLIP_LAJU)), ukuran)
            if fr is not None:
                img = img.copy()
                q = QPainter(img)
                q.setRenderHint(QPainter.Antialiasing)
                klip = QPainterPath()
                klip.addRoundedRect(QRectF(r.x() - d["x"], r.y() - d["y"], r.width(), r.height()), 28, 28)
                q.setClipPath(klip)
                q.drawImage(round(r.x() - d["x"]), round(r.y() - d["y"]), fr)
                q.end()
        p.drawImage(0, 0, img)
        p.restore()


def bingkai(t, data):
    if t < SPLASH:
        return VI.bingkai(t, data["T"], data["bg"], data["bay"])
    img = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor("#ffffff"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    t0 = SPLASH
    for no, ((_, dur), lap) in enumerate(zip(SLIDE, data["slides"]), 1):
        if t0 <= t < t0 + dur or (no == len(SLIDE) and t >= t0):
            if no == 1:                              # logo splash meluncur ke posisi logo slide 1
                q = VI.inout_cubic(VI.fase(t, t0, 1.1))
                o = 1 - VI.fase(t, t0 + 0.8, 0.3)
                if o > 0:
                    m = data["peta"]
                    k = 1 + (m["k"] - 1) * q
                    cx = m["dari"][0] + (m["ke"][0] - m["dari"][0]) * q
                    cy = m["dari"][1] + (m["ke"][1] - m["dari"][1]) * q
                    p.save()
                    p.setOpacity(o)
                    p.translate(cx, cy)
                    p.scale(k, k)
                    p.translate(-m["dari"][0], -m["dari"][1])
                    p.drawImage(0, 0, data["splash"])
                    p.restore()
            gambar_slide(p, lap, t0, dur, t, data, no)
            break
        t0 += dur
    putih = VI.fase(t, TOTAL - 1.0, 0.8)                 # akhir: memudar ke putih
    if putih > 0:
        p.setOpacity(VI.inout_cubic(putih))
        p.fillRect(QRectF(0, 0, W, H), QColor("#ffffff"))
    p.end()
    return img


# ---------------------------------------------------------------- keluaran
def stills(data):
    waktu = [3.0, 6.7, 8.0, 13.0, 16.5, 21.0, 26.5, 34.0, 43.0, 47.5, 53.0, 57.5]
    lw, lh = 360, 640
    lembar = QImage(lw * 6 + 70, lh * 2 + 30, QImage.Format_RGB32)
    lembar.fill(QColor("#9aa3b0"))
    p = QPainter(lembar)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    for i, t in enumerate(waktu):
        p.drawImage(QRectF(10 + (i % 6) * (lw + 10), 10 + (i // 6) * (lh + 10), lw, lh), bingkai(t, data))
    p.end()
    lembar.save(str(OUT / "_cek_promosi.png"))
    print("stills ->", OUT / "_cek_promosi.png")


def video(data):
    from virmodock.ui.perekam_video import PerekamVideo
    n = int(round(TOTAL * FPS))
    f = str(OUT / ("virmolab_promosi_30fps.mp4" if FPS == 30 else "virmolab_promosi.mp4"))
    rek = PerekamVideo(f, W, H, FPS)
    st = {"i": 0}

    def pompa():
        while st["i"] < n and rek.boleh_lagi():
            rek.kirim(bingkai(st["i"] / FPS, data))
            st["i"] += 1
            if st["i"] % 600 == 0:
                print(f"  {st['i']}/{n}", flush=True)
        if st["i"] >= n and not rek._tutup:
            rek.akhiri()

    rek.siap_lagi.connect(pompa)
    rek.selesai.connect(lambda path: (print("video ->", path, f"({n} bingkai, {TOTAL:.1f} s)"), VI.app.quit()))
    rek.galat.connect(lambda e: (print("GALAT", e), VI.app.quit()))
    QTimer.singleShot(0, pompa)
    VI.app.exec()


if __name__ == "__main__":
    d = siapkan()
    print(f"durasi {TOTAL:.1f} s, klip 3D: {len(d['klip'].f)} bingkai")
    if "--stills" in sys.argv:
        stills(d)
    else:
        video(d)
