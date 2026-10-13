"""Klien internet bersama dengan cache lokal, pembatas laju, dan pencatatan jejak data.

Modul ini menyediakan akses terstandarisasi ke API dan basis data daring
(Wikidata SPARQL, RCSB PDB, ChEMBL, UniProt, dll.) dengan:
- Pencatatan jejak sumber data (Jejak) untuk laporan ilmiah otomatis.
- Cache berkas lokal di APPDATA/cache_http dengan waktu kedaluwarsa.
- Mode luring otomatis: bila jaringan terputus, memakai data cache tersimpan.
- Pembatasan laju permintaan per domain (rate limiting).
- Pesan galat ramah dalam Bahasa Indonesia.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

from . import paths

try:
    from .. import VERSI
except ImportError:
    VERSI = "1.2.0"

USER_AGENT = f"VirmoDock/{VERSI} (akademik; https://github.com/virmodock)"

# Pembatas laju waktu antar-permintaan (detik) per domain
BATAS_LAJU_DOMAIN = {
    "query.wikidata.org": 1.0,
    "www.wikidata.org": 1.0,
}
LAJU_BAWAAN = 0.5
_waktu_terakhir_domain: dict[str, float] = {}


@dataclass
class Jejak:
    """Catatan asal-usul data dari internet untuk transparansi dan laporan metode."""
    sumber: str
    versi: str
    diambil: str
    kueri: str
    lisensi: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Jejak":
        return cls(
            sumber=d.get("sumber", ""),
            versi=d.get("versi", ""),
            diambil=d.get("diambil", ""),
            kueri=d.get("kueri", ""),
            lisensi=d.get("lisensi", "")
        )


def folder_cache() -> Path:
    """Jalur direktori cache HTTP di data aplikasi."""
    d = paths.APPDATA / "cache_http"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _kunci_cache(url: str, params: dict | None, data: bytes | str | None) -> str:
    """Kunci hash SHA-256 unik untuk kombinasi URL, parameter, dan body data."""
    komponen = [url]
    if params:
        komponen.append(json.dumps(params, sort_keys=True))
    if data:
        if isinstance(data, bytes):
            komponen.append(hashlib.sha256(data).hexdigest())
        else:
            komponen.append(str(data))
    gabungan = "|".join(komponen)
    return hashlib.sha256(gabungan.encode("utf-8")).hexdigest()


def _tunggu_laju(domain: str):
    """Pastikan jeda waktu minimum antar-permintaan ke domain yang sama terpenuhi."""
    jeda_min = BATAS_LAJU_DOMAIN.get(domain, LAJU_BAWAAN)
    sekarang = time.time()
    lalu = _waktu_terakhir_domain.get(domain, 0.0)
    selisih = sekarang - lalu
    if selisih < jeda_min:
        time.sleep(jeda_min - selisih)
    _waktu_terakhir_domain[domain] = time.time()


def _format_galat(e: Exception) -> str:
    """Format pesan galat ramah Bahasa Indonesia dari urllib/jaringan."""
    if isinstance(e, urllib.error.HTTPError):
        if e.code == 429:
            return "Server sibuk (batas laju permintaan terlampaui/HTTP 429). Silakan tunggu sejenak."
        if e.code in (500, 502, 503, 504):
            return f"Layanan server sedang mengalami gangguan atau pemeliharaan (HTTP {e.code})."
        if e.code == 404:
            return "Data atau berkas tidak ditemukan di server (HTTP 404)."
        return f"Permintaan ke server gagal dengan kode HTTP {e.code} ({e.reason})."
    if isinstance(e, urllib.error.URLError):
        pesan = str(e.reason).lower()
        if "timed out" in pesan or "timeout" in pesan:
            return "Batas waktu permintaan terlampaui (server tidak merespons tepat waktu)."
        return "Koneksi internet tidak tersedia atau alamat server tidak dapat dihubungi."
    if isinstance(e, TimeoutError):
        return "Batas waktu permintaan terlampaui (koneksi terputus)."
    return f"Gagal menghubungi server: {e}"


def _baca_cache(kunci: str, cache_jam: float) -> tuple[dict | None, bool]:
    """Baca isi cache bila ada. Mengembalikan (entri, masih_segar)."""
    berkas = folder_cache() / f"{kunci}.json"
    if not berkas.exists():
        return None, False
    try:
        data = json.loads(berkas.read_text(encoding="utf-8"))
        waktu_buat = datetime.fromisoformat(data["waktu"])
        masih_segar = (datetime.now() - waktu_buat) <= timedelta(hours=cache_jam)
        return data, masih_segar
    except Exception:
        return None, False


def _tulis_cache(kunci: str, konten: any, tipe: str, sumber: str, versi: str, lisensi: str, kueri: str):
    """Simpan hasil ke cache berkas lokal."""
    berkas = folder_cache() / f"{kunci}.json"
    data = {
        "waktu": datetime.now().isoformat(timespec="seconds"),
        "tipe": tipe,
        "konten": konten,
        "sumber": sumber,
        "versi": versi,
        "lisensi": lisensi,
        "kueri": kueri
    }
    try:
        berkas.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def ambil_teks(url: str, params: dict | None = None, data: bytes | str | None = None,
               headers: dict | None = None, batas: int = 30, coba: int = 3,
               cache_jam: float = 168.0, lisensi: str = "", sumber: str = "") -> tuple[str, Jejak]:
    """Ambil konten teks (CSV, TSV, GMT, XML) dari internet atau cache lokal."""
    kunci = _kunci_cache(url, params, data)
    kueri_label = url if not params else f"{url}?{urllib.parse.urlencode(params)}"
    nama_sumber = sumber or urllib.parse.urlparse(url).netloc or "Internet"

    # Periksa cache segar
    cache_data, segar = _baca_cache(kunci, cache_jam)
    if cache_data and segar:
        tgl_cache = cache_data.get("waktu", "")[:10]
        versi_asal = cache_data.get("versi", "")
        # Jika versi tersimpan bukan versi khusus, tandai sebagai cache
        versi_label = f"cache {tgl_cache}" if versi_asal in ("", "langsung") else versi_asal
        jejak = Jejak(
            sumber=cache_data.get("sumber", nama_sumber),
            versi=versi_label,
            diambil=cache_data.get("waktu", datetime.now().isoformat(timespec="seconds")),
            kueri=cache_data.get("kueri", kueri_label),
            lisensi=cache_data.get("lisensi", lisensi)
        )
        return str(cache_data["konten"]), jejak

    # Siapkan URL & Request
    full_url = url
    if params:
        tanda = "&" if "?" in url else "?"
        full_url = f"{url}{tanda}{urllib.parse.urlencode(params)}"

    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)

    body_bytes = None
    if data is not None:
        body_bytes = data.encode("utf-8") if isinstance(data, str) else data

    req = urllib.request.Request(full_url, data=body_bytes, headers=h)
    domain = urllib.parse.urlparse(full_url).netloc

    terakhir_err = None
    for percobaan in range(1, coba + 1):
        try:
            _tunggu_laju(domain)
            with urllib.request.urlopen(req, timeout=batas) as resp:
                raw = resp.read()
                teks = raw.decode("utf-8", errors="replace")
                diambil_tgl = datetime.now().isoformat(timespec="seconds")
                versi_info = "langsung"

                _tulis_cache(kunci, teks, "teks", nama_sumber, versi_info, lisensi, kueri_label)

                jejak = Jejak(
                    sumber=nama_sumber,
                    versi=versi_info,
                    diambil=diambil_tgl,
                    kueri=kueri_label,
                    lisensi=lisensi
                )
                return teks, jejak
        except Exception as e:
            terakhir_err = e
            # Jika server error atau 429, jeda sebelum coba lagi
            if percobaan < coba:
                time.sleep(1.0 * percobaan)

    # Bila gagal jaringan tetapi ada cache (walau kadaluwarsa) -> mode luring
    if cache_data:
        tgl_cache = cache_data.get("waktu", "")[:10]
        jejak = Jejak(
            sumber=cache_data.get("sumber", nama_sumber),
            versi=f"cache {tgl_cache}",
            diambil=cache_data.get("waktu", datetime.now().isoformat(timespec="seconds")),
            kueri=cache_data.get("kueri", kueri_label),
            lisensi=cache_data.get("lisensi", lisensi)
        )
        return str(cache_data["konten"]), jejak

    raise IOError(_format_galat(terakhir_err))


def ambil_json(url: str, params: dict | None = None, data: bytes | str | None = None,
               headers: dict | None = None, batas: int = 30, coba: int = 3,
               cache_jam: float = 168.0, lisensi: str = "", sumber: str = "") -> tuple[any, Jejak]:
    """Ambil data JSON dari internet atau cache lokal."""
    h = {"Accept": "application/json"}
    if headers:
        h.update(headers)
    teks, jejak = ambil_teks(
        url, params=params, data=data, headers=h, batas=batas,
        coba=coba, cache_jam=cache_jam, lisensi=lisensi, sumber=sumber
    )
    try:
        obj = json.loads(teks)
        return obj, jejak
    except Exception as e:
        raise ValueError(f"Respons dari server bukan format JSON yang valid: {e}")


def sparql(endpoint: str, kueri: str, batas: int = 60, coba: int = 3,
           cache_jam: float = 168.0, lisensi: str = "CC0 1.0",
           sumber: str = "Wikidata SPARQL") -> tuple[list[dict], Jejak]:
    """Kueri endpoint SPARQL (mis. query.wikidata.org). Mengembalikan list bindings dan Jejak."""
    params = {"query": kueri, "format": "json"}
    headers = {"Accept": "application/sparql-results+json"}
    obj, jejak = ambil_json(
        endpoint, params=params, headers=headers, batas=batas,
        coba=coba, cache_jam=cache_jam, lisensi=lisensi, sumber=sumber
    )
    if isinstance(obj, dict) and "results" in obj and "bindings" in obj["results"]:
        return obj["results"]["bindings"], jejak
    if isinstance(obj, list):
        return obj, jejak
    return [obj], jejak


def hapus_cache() -> int:
    """Hapus seluruh berkas cache HTTP lokal. Mengembalikan jumlah berkas yang dihapus."""
    folder = folder_cache()
    jumlah = 0
    for f in folder.glob("*.json"):
        try:
            f.unlink(missing_ok=True)
            jumlah += 1
        except Exception:
            pass
    return jumlah


def ukuran_cache() -> str:
    """Hitung total ukuran berkas cache HTTP dalam format teks terbaca (KB/MB)."""
    folder = folder_cache()
    total_byte = 0
    for f in folder.glob("*.json"):
        try:
            total_byte += f.stat().st_size
        except Exception:
            pass

    if total_byte < 1024:
        return f"{total_byte} B"
    if total_byte < 1024 * 1024:
        kb = total_byte / 1024
        return f"{kb:.1f} KB".replace(".", ",")
    mb = total_byte / (1024 * 1024)
    return f"{mb:.2f} MB".replace(".", ",")
