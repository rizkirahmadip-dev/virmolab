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

# --------------------------------------------------------------- unduh + verifikasi + pasang
# Unduhan sungguhannya ratusan megabita, jadi peladennya ditiru di sini: isi tiruan 1 MB dengan sidik
# jari yang diketahui. Yang diuji bukan kecepatan unduh, melainkan tiga perilaku yang menentukan apakah
# modul ini aman dipakai pada berkas sebesar itu: unduhan dilanjutkan dan tidak diulang dari nol, berkas
# yang sidik jarinya tidak cocok ditolak, dan sisa unduhan yang gagal tidak ditinggalkan di disk pengguna.
import hashlib  # noqa: E402
import tempfile  # noqa: E402

from virmolab.core import unduh_pembaruan as U  # noqa: E402

ISI = bytes(range(256)) * 4000                  # 1.024.000 bita
SIDIK = hashlib.sha256(ISI).hexdigest()
SUMS = f"{SIDIK}  VirmoLab-Setup-9.9.9.exe\n{'0' * 64}  berkas-lain.exe\n"
HASIL = {"status": "baru", "versi": "9.9.9", "aset": [
    {"nama": "VirmoLab-Setup-9.9.9.exe", "url": "https://contoh/exe", "ukuran": len(ISI)},
    {"nama": "SHA256SUMS-9.9.9.txt", "url": "https://contoh/sums", "ukuran": len(SUMS)}]}


class _Unduhan:
    def __init__(self, data, status=200):
        self.b = io.BytesIO(data)
        self.status = status
        self.headers = {"Content-Length": str(len(data))}

    def read(self, n=-1):
        return self.b.read(n)


permintaan = []         # (url, nilai header Range) setiap permintaan yang dilayani


def _layan(req, timeout=None):
    url = req.full_url
    rng = req.get_header("Range")
    permintaan.append((url, rng))
    data = SUMS.encode() if url.endswith("sums") else ISI
    if rng:
        awal = int(rng.split("=")[1].split("-")[0])
        return _Unduhan(data[awal:], 206)
    return _Unduhan(data, 200)


cek(U.sidik_harapan(SUMS, "VirmoLab-Setup-9.9.9.exe") == SIDIK, "sidik jari dibaca dari SHA256SUMS")
cek(U.sidik_harapan(f"{SIDIK} *VirmoLab-Setup-9.9.9.exe\n", "VirmoLab-Setup-9.9.9.exe") == SIDIK,
    "format biner (*nama) terbaca")
cek(U.sidik_harapan(SUMS, "tidak-terdaftar.exe") is None, "nama yang tidak terdaftar -> None")
cek(U.sidik_harapan("bukan sidik jari sama sekali\n", "a.exe") is None, "baris rusak -> None, bukan melempar")

inst, sums = U.installer_dan_sidik(HASIL)
cek(inst.nama.endswith(".exe") and sums.nama.endswith(".txt"), "installer dan SHA256SUMS dikenali dari aset")
cek(inst.ukuran == len(ISI), "ukuran aset terbaca")
cek(U.installer_dan_sidik({"aset": []}) == (None, None), "rilis tanpa aset -> (None, None)")

with tempfile.TemporaryDirectory() as tmp:
    TMP = Path(tmp)
    exe = TMP / inst.nama
    part = TMP / (inst.nama + ".part")
    asli_ambil = U._ambil

    with mock.patch.object(U, "folder_unduh", lambda: TMP), \
            mock.patch("urllib.request.urlopen", _layan):
        f = U.unduh_terverifikasi(HASIL)
        cek(f.read_bytes() == ISI, "unduhan utuh dan sidik jarinya cocok")
        cek(not list(TMP.glob("*.part")), "berkas .part dibersihkan sesudah unduhan selesai")

        n = len(permintaan)
        U.unduh_terverifikasi(HASIL)
        cek(not [u for u, _ in permintaan[n:] if u.endswith("exe")],
            "berkas utuh yang sudah ada tidak diunduh ulang")

        # Lanjutan unduhan: separuh berkas sudah ada, sisanya saja yang diminta.
        exe.unlink()
        part.write_bytes(ISI[:300_000])
        permintaan.clear()
        f = U.unduh_terverifikasi(HASIL)
        rng = [r for u, r in permintaan if u.endswith("exe")]
        cek(rng[:1] == ["bytes=300000-"], f"unduhan dilanjutkan lewat header Range ({rng[:1]})")
        cek(f.read_bytes() == ISI, "hasil lanjutan unduhan tetap utuh")

        # Sidik jari tidak cocok: berkasnya ditolak DAN dihapus. Membiarkannya berarti 500 MB sampah
        # yang menunggu unduhan berikutnya, dan pengguna tidak pernah diberi tahu berkas itu ada.
        exe.unlink()

        def _rusak(url, tujuan, *a, **k):
            if str(tujuan).endswith(".exe"):
                tujuan.write_bytes(b"isi yang rusak")
                return tujuan
            return asli_ambil(url, tujuan, *a, **k)

        with mock.patch.object(U, "_ambil", _rusak):
            try:
                U.unduh_terverifikasi(HASIL)
                cek(False, "berkas dengan sidik jari salah ditolak")
            except U.GalatUnduh as e:
                cek("tidak cocok" in str(e), "berkas dengan sidik jari salah ditolak")
        cek(not exe.exists(), "berkas yang gagal verifikasi dihapus, bukan disimpan")

        # Unduhan terpotong tidak pernah menjadi berkas jadi.
        def _potong(req, timeout=None):
            if req.full_url.endswith("exe"):
                r = _Unduhan(ISI[:1000])
                r.headers["Content-Length"] = str(len(ISI))
                return r
            return _layan(req, timeout)

        with mock.patch("urllib.request.urlopen", _potong):
            try:
                U.unduh_terverifikasi(HASIL)
                cek(False, "unduhan terpotong ditolak")
            except U.GalatUnduh as e:
                cek("tidak utuh" in str(e), "unduhan terpotong ditolak")
        cek(not part.exists() and not exe.exists(), "sisa unduhan terpotong dibuang")

        # Pembatalan: dicek di tiap potongan, jadi tidak perlu menunggu unduhan selesai.
        try:
            U.unduh_terverifikasi(HASIL, dibatalkan=lambda: True)
            cek(False, "pembatalan menghentikan unduhan")
        except U.GalatUnduh as e:
            cek("Dibatalkan" in str(e), "pembatalan menghentikan unduhan")

        try:
            U.unduh_terverifikasi({"aset": [HASIL["aset"][0]]})
            cek(False, "rilis tanpa SHA256SUMS tidak diunduh")
        except U.GalatUnduh as e:
            cek("SHA256SUMS" in str(e), "rilis tanpa SHA256SUMS tidak diunduh")

with mock.patch.object(U.paths, "PORTABLE", True):
    cek(not U.dapat_dipasang(), "versi portable tidak menawarkan pemasangan otomatis")
try:
    U.jalankan_installer(Path("berkas-installer-yang-tidak-ada.exe"))
    cek(False, "installer yang hilang -> galat jelas, bukan crash")
except U.GalatUnduh:
    cek(True, "installer yang hilang -> galat jelas, bukan crash")


# --------------------------------------------------------------- pop-up sekali per versi
# Rilis baru membuka dialog pembaruan sendiri. Yang dijaga di sini aturan "sekali per versi": pop-up
# setiap kali aplikasi dibuka akan membuat pengguna menutupnya tanpa membaca, dan pop-up yang tidak
# pernah muncul lagi membuat rilis berikutnya terlewat. Logikanya diuji atas objek tiruan; dialog
# sungguhannya sudah diuji di bagian dialog di bawah.
from virmolab.ui.mainwindow_dialog import PembukaDialog as _PD  # noqa: E402

class _JwPalsu:
    def __init__(self):
        self.st = St()
        self.dibuka = []

    def buka_pembaruan(self, h=None):
        self.dibuka.append(h.get("versi") if h else None)

    tawarkan = _PD._tawarkan_pembaruan


jw = _JwPalsu()
H93 = {"status": "baru", "versi": "1.9.3", "versi_sekarang": "1.9.2"}
jw.tawarkan(H93)
cek(jw.dibuka == ["1.9.3"], f"rilis baru membuka dialog pembaruan ({jw.dibuka})")
jw.tawarkan(H93)
cek(jw.dibuka == ["1.9.3"], "versi yang sama tidak ditawarkan dua kali")
jw.tawarkan(dict(H93, versi="1.9.4"))
cek(jw.dibuka == ["1.9.3", "1.9.4"], f"rilis berikutnya tetap ditawarkan ({jw.dibuka})")
jw.tawarkan({"status": "baru"})
cek(jw.dibuka == ["1.9.3", "1.9.4"], "hasil tanpa nomor versi tidak membuka apa pun")


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
            cek(d.b_pasang.isVisibleTo(d) == U.dapat_dipasang(),
                f"tombol Unduh & pasang tampil sesuai kemampuan pemasangan ({tema})")
        d.close()
QSettings("VirmoLab", "VirmoLab").setValue("cek_pembaruan", st_lama)
print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
sys.exit(1 if gagal else 0)
