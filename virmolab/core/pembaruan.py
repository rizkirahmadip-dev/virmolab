"""Pemeriksaan versi baru VirmoLab di halaman rilis GitHub.

Hanya nomor versi, tanggal, catatan rilis, dan daftar berkas rilis terbaru yang dibaca. Tidak ada yang diunduh
atau dipasang otomatis, dan tidak ada data proyek yang dikirim: permintaannya GET biasa dengan User-Agent
VirmoLab/<versi>, sama seperti klien internet lain di aplikasi ini. Pemasangan tetap lewat installer yang
diunduh pengguna sendiri, lalu dicocokkan dengan SHA256SUMS di halaman rilis.
"""
import json
import re
import time
import urllib.error
import urllib.request

from .. import __version__ as VERSI

REPO = "virmolab/virmolab"
API_TERBARU = f"https://api.github.com/repos/{REPO}/releases/latest"
HALAMAN_RILIS = f"https://github.com/{REPO}/releases"
JEDA_DETIK = 24 * 3600          # pemeriksaan otomatis paling sering sekali sehari


def urai_versi(teks):
    """'v1.6.0' / '1.6.0' / '1.6.0-rc1' -> ((1, 6, 0), pra_rilis). None bila bukan nomor versi."""
    m = re.match(r"^\s*v?(\d+)\.(\d+)(?:\.(\d+))?([-+.]?[A-Za-z][\w.]*)?\s*$", str(teks or ""))
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)), bool(m.group(4))


def lebih_baru(calon, sekarang=VERSI):
    """True bila versi calon lebih baru dari versi sekarang. Versi pra-rilis tidak pernah ditawarkan."""
    a, b = urai_versi(calon), urai_versi(sekarang)
    if not a or not b or a[1]:
        return False
    return a[0] > b[0]


def _aset(daftar):
    hasil = []
    for a in daftar or []:
        nama = a.get("name", "")
        if not nama:
            continue
        hasil.append({"nama": nama, "url": a.get("browser_download_url", ""), "ukuran": int(a.get("size") or 0)})
    # Installer dulu, lalu portable, lalu checksum; sisanya menurut nama.
    urut = {"Setup": 0, "Portable": 1, "SHA256SUMS": 2}
    return sorted(hasil, key=lambda a: (next((v for k, v in urut.items() if k in a["nama"]), 9), a["nama"]))


def urai_respons(data, versi_sekarang=VERSI):
    """JSON /releases/latest -> ringkasan. Dipisah dari jaringan supaya bisa diuji tanpa internet."""
    if not isinstance(data, dict) or not data.get("tag_name"):
        return {"status": "galat", "pesan": "Jawaban GitHub tidak memuat nomor versi rilis."}
    tag = str(data["tag_name"])
    versi = tag[1:] if tag[:1] in "vV" else tag
    if not urai_versi(versi):
        return {"status": "galat", "pesan": f"Nomor versi rilis tidak dikenali: {tag}"}
    catatan = (data.get("body") or "").strip()
    if len(catatan) > 6000:
        catatan = catatan[:6000].rsplit("\n", 1)[0] + "\n\n…"
    return {
        "status": "baru" if lebih_baru(versi, versi_sekarang) else "terkini",
        "versi": versi,
        "versi_sekarang": versi_sekarang,
        "url": data.get("html_url") or HALAMAN_RILIS,
        "tanggal": (data.get("published_at") or "")[:10],
        "catatan": catatan,
        "aset": _aset(data.get("assets")),
    }


def periksa(versi_sekarang=VERSI, batas=20):
    """Tanya GitHub rilis terbaru. Selalu mengembalikan dict berkunci 'status':
    baru | terkini | belum_ada_rilis | galat. Tidak pernah melempar galat jaringan ke pemanggil."""
    from .sumber_data import USER_AGENT, _format_galat
    req = urllib.request.Request(API_TERBARU, headers={
        "User-Agent": USER_AGENT, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=batas) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"status": "belum_ada_rilis", "versi_sekarang": versi_sekarang, "url": HALAMAN_RILIS,
                    "pesan": "Belum ada rilis yang diterbitkan di GitHub."}
        if e.code in (403, 429):
            return {"status": "galat", "versi_sekarang": versi_sekarang,
                    "pesan": "GitHub membatasi jumlah permintaan dari alamat ini. Coba lagi sejam lagi."}
        return {"status": "galat", "versi_sekarang": versi_sekarang, "pesan": _format_galat(e)}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"status": "galat", "versi_sekarang": versi_sekarang, "pesan": _format_galat(e)}
    except ValueError:
        return {"status": "galat", "versi_sekarang": versi_sekarang, "pesan": "Jawaban GitHub bukan JSON."}
    return urai_respons(data, versi_sekarang)


def otomatis_aktif(st):
    return st.value("cek_pembaruan", True, type=bool)


def perlu_diperiksa(st, sekarang=None):
    """Pemeriksaan otomatis: aktif, dan pemeriksaan terakhir lebih dari sehari lalu."""
    if not otomatis_aktif(st):
        return False
    try:
        terakhir = float(st.value("cek_pembaruan_terakhir", 0) or 0)
    except (TypeError, ValueError):
        terakhir = 0.0
    return (sekarang or time.time()) - terakhir >= JEDA_DETIK


def catat_diperiksa(st, sekarang=None):
    st.setValue("cek_pembaruan_terakhir", float(sekarang or time.time()))


def ukuran_teks(n):
    if n >= 1 << 30:
        return f"{n / (1 << 30):.1f} GB"
    if n >= 1 << 20:
        return f"{n / (1 << 20):.0f} MB"
    if n >= 1024:
        return f"{n / 1024:.0f} KB"
    return f"{max(n, 0)} B"
