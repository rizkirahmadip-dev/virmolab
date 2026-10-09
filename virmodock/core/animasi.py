"""Penyandi animasi viewport: bingkai PNG -> GIF / WebP animasi / folder PNG (Pillow, sudah dibundel).

GIF: palet adaptif bersama dari beberapa bingkai contoh (warna konsisten, tanpa kedip), tanpa dithering
agar kartun/permukaan tetap halus. WebP: lossy q90, jauh lebih kecil dari GIF dengan warna penuh.
"""
import io
from pathlib import Path

JENIS = {"sinema": "Presentasi sinematik (zoom → putar → sorot interaksi)", "putar": "Putar 360°",
         "goyang": "Goyang ±30°", "zoom": "Zoom masuk ke situs pengikatan"}
FORMAT = {"mp4": "Video MP4 H.264 (kualitas terbaik, Full HD–4K)", "gif": "GIF animasi (WhatsApp, web)",
          "webp": "WebP animasi (lebih kecil, warna penuh)", "png": "Folder bingkai PNG (untuk video editor)"}


def simpan(bingkai, f, fmt, fps, lapor=None, ukuran=None):
    """bingkai: list bytes PNG. f: berkas (gif/webp) atau folder (png). ukuran: (lebar, tinggi) akhir —
    bingkai yang dirender lebih besar (layar HiDPI) diperkecil LANCZOS = antialias tambahan.
    Kembalikan jalur keluaran."""
    from PIL import Image
    durasi = int(round(1000 / fps))
    gambar = []
    for b in bingkai:
        g = Image.open(io.BytesIO(b)).convert("RGB")
        if ukuran and g.size != tuple(ukuran):
            g = g.resize(tuple(ukuran), Image.Resampling.LANCZOS)
        gambar.append(g)
    if fmt == "png":
        d = Path(f)
        d.mkdir(parents=True, exist_ok=True)
        for i, g in enumerate(gambar):
            g.save(d / f"bingkai_{i + 1:04d}.png")
        return str(d)
    if lapor:
        lapor.log.emit(f"Menyandikan {len(gambar)} bingkai…")
    if fmt == "webp":
        gambar[0].save(f, "WEBP", save_all=True, append_images=gambar[1:], duration=durasi, loop=0, quality=90,
                       method=4)
        return f
    # palet bersama dari mosaik bingkai contoh
    contoh = gambar[:: max(1, len(gambar) // 8)][:8]
    w, h = contoh[0].size
    mosaik = Image.new("RGB", (w, h * len(contoh)))
    for i, g in enumerate(contoh):
        mosaik.paste(g, (0, i * h))
    palet = mosaik.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    p = [g.quantize(palette=palet, dither=Image.Dither.NONE) for g in gambar]
    p[0].save(f, "GIF", save_all=True, append_images=p[1:], duration=durasi, loop=0, optimize=False, disposal=1)
    return f
