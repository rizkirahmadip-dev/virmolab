"""Uji pemeriksaan pembaruan (core/pembaruan.py + dialog), tanpa internet kecuali diberi --daring.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_pembaruan.py [--daring]
Keluaran gambar: dev/uji/pembaruan/dialog_<keadaan>_<tema>.png
"""
import io
import json
import sys
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from virmolab.core import pembaruan as P  # noqa: E402

gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


# --- versi
cek(P.urai_versi("v1.6.0") == ((1, 6, 0), False), "urai v1.6.0")
cek(P.urai_versi("1.6") == ((1, 6, 0), False), "urai 1.6 -> patch 0")
cek(P.urai_versi("1.7.0-rc1")[1] is True, "rc dikenali pra-rilis")
cek(P.urai_versi("terbaru") is None, "teks bukan versi -> None")
cek(P.lebih_baru("1.6.1", "1.6.0"), "1.6.1 > 1.6.0")
cek(P.lebih_baru("1.10.0", "1.9.9"), "1.10.0 > 1.9.9 (numerik, bukan leksikal)")
cek(not P.lebih_baru("1.6.0", "1.6.0"), "sama tidak lebih baru")
cek(not P.lebih_baru("1.5.9", "1.6.0"), "lebih lama tidak ditawarkan")
cek(not P.lebih_baru("1.7.0-rc1", "1.6.0"), "pra-rilis tidak ditawarkan")

CONTOH = {
    "tag_name": "v1.7.0", "html_url": "https://github.com/rizkirahmadip-dev/virmolab/releases/tag/v1.7.0",
    "published_at": "2026-11-02T08:00:00Z", "body": "## Baru\n- Fitur A\n- Fitur B",
    "assets": [{"name": "SHA256SUMS-1.7.0.txt", "browser_download_url": "https://x/s", "size": 190},
               {"name": "VirmoLab-Portable-1.7.0.zip", "browser_download_url": "https://x/p", "size": 760_000_000},
               {"name": "VirmoLab-Setup-1.7.0.exe", "browser_download_url": "https://x/e", "size": 530_000_000}],
}
h = P.urai_respons(CONTOH, "1.6.0")
cek(h["status"] == "baru" and h["versi"] == "1.7.0", "respons 1.7.0 vs 1.6.0 -> baru")
cek([a["nama"] for a in h["aset"]] == ["VirmoLab-Setup-1.7.0.exe", "VirmoLab-Portable-1.7.0.zip",
                                        "SHA256SUMS-1.7.0.txt"], "aset diurutkan Setup, Portable, SHA256SUMS")
cek(h["tanggal"] == "2026-11-02", "tanggal terbit dipotong ke YYYY-MM-DD")
cek(P.urai_respons(CONTOH, "1.7.0")["status"] == "terkini", "versi sama -> terkini")

# Jalur rilis publik pertama (C4 rencana 1.8.0): aplikasi 1.7.0 terpasang harus melihat rilis 1.8.0
RILIS_18 = dict(CONTOH, tag_name="v1.8.0",
                html_url="https://github.com/rizkirahmadip-dev/virmolab/releases/tag/v1.8.0",
                assets=[{"name": "VirmoLab-Setup-1.8.0.exe", "browser_download_url": "https://x/e", "size": 530_000_000},
                        {"name": "SHA256SUMS-1.8.0.txt", "browser_download_url": "https://x/s", "size": 190}])
h18 = P.urai_respons(RILIS_18, "1.7.0")
cek(h18["status"] == "baru" and h18["versi"] == "1.8.0" and h18["url"].endswith("/tag/v1.8.0"),
    "aplikasi 1.7.0 melihat rilis 1.8.0 beserta tautan halamannya")
cek(P.REPO == "rizkirahmadip-dev/virmolab" and P.API_TERBARU.endswith("/releases/latest"),
    f"cek pembaruan menunjuk repo rilis ({P.REPO})")
cek(P.urai_respons({"tag_name": "nightly"}, "1.6.0")["status"] == "galat", "tag bukan versi -> galat")
cek(P.urai_respons({}, "1.6.0")["status"] == "galat", "respons kosong -> galat")
cek(P.ukuran_teks(530_000_000) == "505 MB", f"ukuran 530e6 B -> {P.ukuran_teks(530_000_000)}")


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http(kode):
    def f(*a, **k):
        raise urllib.error.HTTPError(P.API_TERBARU, kode, "x", {}, io.BytesIO(b""))
    return f


with mock.patch("urllib.request.urlopen", lambda *a, **k: _Resp(json.dumps(CONTOH).encode())):
    cek(P.periksa("1.6.0")["status"] == "baru", "periksa (urlopen tiruan) -> baru")
with mock.patch("urllib.request.urlopen", _http(404)):
    cek(P.periksa("1.6.0")["status"] == "belum_ada_rilis", "404 -> belum_ada_rilis")
with mock.patch("urllib.request.urlopen", _http(403)):
    r = P.periksa("1.6.0")
    cek(r["status"] == "galat" and "membatasi" in r["pesan"], "403 -> galat batas laju")
with mock.patch("urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("dns"))):
    cek(P.periksa("1.6.0")["status"] == "galat", "tanpa internet -> galat, tidak melempar")
with mock.patch("urllib.request.urlopen", lambda *a, **k: _Resp(b"<html>")):
    cek(P.periksa("1.6.0")["status"] == "galat", "bukan JSON -> galat")


class St:
    def __init__(self, d=None):
        self.d = dict(d or {})

    def value(self, k, bawaan=None, type=None):
        v = self.d.get(k, bawaan)
        return bool(v) if type is bool else v

    def setValue(self, k, v):
        self.d[k] = v


cek(P.perlu_diperiksa(St(), 1e9), "belum pernah diperiksa -> perlu")
cek(not P.perlu_diperiksa(St({"cek_pembaruan_terakhir": 1e9 - 3600}), 1e9), "1 jam lalu -> belum perlu")
cek(P.perlu_diperiksa(St({"cek_pembaruan_terakhir": 1e9 - 90000}), 1e9), "25 jam lalu -> perlu")
cek(not P.perlu_diperiksa(St({"cek_pembaruan": False}), 1e9), "dimatikan -> tidak diperiksa")

if "--daring" in sys.argv:
    r = P.periksa()
    print("  daring:", {k: r.get(k) for k in ("status", "versi", "pesan", "url")})
    cek(r["status"] in ("baru", "terkini", "belum_ada_rilis", "galat"), "periksa daring mengembalikan status sah")

# --- dialog (terang + gelap, tiga keadaan)
from PySide6.QtCore import QSettings, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
from virmolab.ui import theme  # noqa: E402
from virmolab.ui.dialog_pembaruan import DialogPembaruan  # noqa: E402

OUT = Path("dev/uji/pembaruan")
OUT.mkdir(parents=True, exist_ok=True)
st_lama = QSettings("VirmoLab", "VirmoLab").value("cek_pembaruan", True, type=bool)
keadaan = {"baru": P.urai_respons(CONTOH, "1.6.0"),
           "kosong": {"status": "belum_ada_rilis", "pesan": "Belum ada rilis yang diterbitkan di GitHub."},
           "galat": {"status": "galat", "pesan": "Koneksi internet tidak tersedia atau alamat server tidak dapat dihubungi."}}
for tema in ("terang", "gelap"):
    app.setPalette(theme.palet(tema))
    app.setStyleSheet(theme.qss(tema))
    for nama, hasil in keadaan.items():
        d = DialogPembaruan(None, hasil)
        d.show()
        for _ in range(10):
            app.processEvents()
        d.grab().save(str(OUT / f"dialog_{nama}_{tema}.png"))
        if nama == "baru":
            cek("1.7.0" in d.k_rilis.l_nilai.text(), f"kartu rilis menampilkan 1.7.0 ({tema})")
            cek("VirmoLab-Setup-1.7.0.exe" in d.catatan.toPlainText(), f"daftar berkas rilis tampil ({tema})")
            cek("Fitur A" in d.catatan.toPlainText(), f"catatan rilis Markdown tampil ({tema})")
        d.close()
QSettings("VirmoLab", "VirmoLab").setValue("cek_pembaruan", st_lama)
print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
sys.exit(1 if gagal else 0)
