"""Pemasang alat Linux lanjutan di WSL, dijalankan dari Alat › Pasang alat lanjutan (WSL).

Empat alat hanya ada untuk Linux (sebagian hanya CUDA) sehingga tidak ikut installer Windows (±32 GB):
Uni-Dock dan OpenFE (paket "Docking GPU & RBFE"), GNINA dan Boltz-2 (paket "Co-folding & skor CNN"). Modul ini
murni (tanpa Qt) dan menyiapkan semua yang dibutuhkan dialog:

- `periksa_prasyarat()` memeriksa Windows, WSL, distro, GPU NVIDIA, ruang disk, alat dasar, dan internet dalam
  satu panggilan WSL, lalu menyatakan paket mana yang bisa dipasang beserta alasannya.
- `skrip_paket()` merakit skrip yang dikirim ke `bash -s` lewat stdin. Jalur skrip TIDAK diserahkan ke WSL karena
  folder aplikasi bisa berspasi dan ber-huruf non-ASCII (C:\\Users\\Rizkí\\...).
- `urai_kemajuan()` menerjemahkan penanda langkah yang dicetak skrip (UNDUH_OPENFE, PASANG_SELESAI, ...) menjadi
  label dan urutan langkah.

Skrip pemasangnya idempoten: menjalankan lagi melanjutkan dari unduhan yang sudah tersimpan.
"""
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import paths
from .lanjutan import awalan_wsl, distro_wsl, teks_wsl

PAKET = {
    "gpu_rbfe": {
        "nama": "Docking GPU & RBFE",
        "alat": "Uni-Dock 1.2 (docking batch GPU) dan OpenFE 1.13 (energi bebas relatif)",
        "skrip": "pasang_openfe_unidock_wsl.sh",
        # diukur pada pemasangan dari nol (Ubuntu 26.04, 25 Okt 2026): lingkungan OpenFE 13 GB + Uni-Dock 1,9 GB;
        # arsip .conda (±4,5 GB) baru dihapus sesudah sukses, jadi ruang puncaknya lebih besar
        "ukuran_gb": 15,
        "puncak_gb": 19,
        "lisensi": "Uni-Dock Apache-2.0, OpenFE MIT; paket dari conda-forge",
        "alat_cuda": "unidock",          # dilewati tanpa GPU NVIDIA; OpenFE tetap bisa di CPU
        "langkah": [("UNDUH_MICROMAMBA", "Mengunduh micromamba (pengelola paket)"),
                    ("UNDUH_OPENFE", "Mengunduh dan memasang OpenFE (paling lama)"),
                    ("UNDUH_UNIDOCK", "Mengunduh dan memasang Uni-Dock"),
                    ("VERSI_OPENFE", "Memeriksa OpenFE"),
                    ("VERSI_UNIDOCK", "Memeriksa Uni-Dock"),
                    ("PASANG_SELESAI", "Mencatat versi paket")],
    },
    "cofolding": {
        "nama": "Co-folding & skor CNN",
        "alat": "Boltz-2 2.2.1 (co-folding, docking peptida) beserta bobotnya, dan GNINA 1.3.3 (skor ulang CNN)",
        "skrip": "pasang_gnina_boltz_wsl.sh",
        # venv Boltz + PyTorch 7,0 GB (tautan keras dengan cache uv), GNINA 2,0 GB, bobot dan CCD di ~/.boltz 7,6 GB
        "ukuran_gb": 17,
        "puncak_gb": 17,
        "lisensi": "Boltz-2 MIT, GNINA GPL-2.0; dari GitHub, PyPI, dan PyTorch",
        "alat_cuda": "gnina",            # dilewati tanpa GPU NVIDIA; Boltz tetap bisa di CPU
        "langkah": [("UNDUH_GNINA", "Mengunduh GNINA (±2 GB)"),
                    ("UNDUH_UV", "Mengunduh uv (pengelola Python)"),
                    ("PYTHON_312", "Menyiapkan Python 3.12 untuk Boltz"),
                    ("UNDUH_TORCH", "Mengunduh PyTorch (paling lama)"),
                    ("UNDUH_BOLTZ", "Memasang Boltz-2"),
                    ("BANTUAN_GNINA", "Memeriksa GNINA"),
                    ("BANTUAN_BOLTZ", "Memeriksa Boltz-2"),
                    ("PASANG_SELESAI", "Alat terpasang"),
                    ("UNDUH_BOBOT_BOLTZ", "Mengunduh bobot model Boltz-2")],
    },
}
CADANGAN_DISK_GB = 5          # ruang sisa minimal pada titik puncak pemasangan
# Boltz-2 (1HSG dua rantai + indinavir, afinitas) dihentikan OOM killer pada VM WSL 4 GB (MemTotal 3,8 GB, RSS 3,5 GB;
# uji 25 Okt 2026) dan berjalan pada VM bawaan 8 GB (MemTotal ±7,7 GB). WSL bawaan memakai separuh RAM Windows, jadi
# laptop 8 GB hanya memberi WSL 4 GB.
MEMORI_BOLTZ_GB = 7
_BOBOT = "unduh_bobot_boltz.py"


# ------------------------------------------------------------------ prasyarat
@dataclass
class Syarat:
    kunci: str
    judul: str
    ok: bool
    wajib: bool
    pesan: str
    aksi: str = ""            # pasang_wsl | terminal | salin | ""
    perintah: str = ""        # untuk aksi salin


@dataclass
class Prasyarat:
    syarat: List[Syarat] = field(default_factory=list)
    distro: str = ""
    daftar_distro: List[Dict] = field(default_factory=list)
    gpu: str = ""
    disk_gb: Optional[int] = None
    mem_gb: Optional[float] = None              # RAM yang dilihat VM WSL (MemTotal), dibatasi .wslconfig
    bisa: Dict[str, tuple] = field(default_factory=dict)      # paket -> (boleh, alasan, lewati)

    @property
    def wsl_siap(self):
        return all(s.ok for s in self.syarat if s.wajib and s.kunci in ("windows", "wsl", "wsl2"))


def daftar_distro(keluaran):
    """Urai `wsl -l -v`: [{nama, status, versi, bawaan}]. Baris kepala dan baris pesan diabaikan."""
    hasil = []
    for b in keluaran.splitlines():
        m = re.match(r"^\s*(\*)?\s*(\S+)\s+(\S+)\s+([12])\s*$", b)
        if m and m.group(2).upper() != "NAME":
            hasil.append({"nama": m.group(2), "status": m.group(3), "versi": int(m.group(4)),
                          "bawaan": bool(m.group(1))})
    return hasil


# satu panggilan WSL untuk semua pemeriksaan di dalam distro (WSL dingin bisa butuh ±10 s per panggilan)
_SKRIP_PRASYARAT = r"""
echo "pengguna=$(whoami)"
if [ -x /usr/lib/wsl/lib/nvidia-smi ]; then
  echo "gpu=$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null | head -n1)"
else
  echo "gpu="
fi
echo "disk_gb=$(df -BG --output=avail "$HOME" 2>/dev/null | tail -n1 | tr -dc 0-9)"
echo "mem_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo 2>/dev/null)"
for p in curl tar python3; do command -v "$p" >/dev/null 2>&1 || echo "hilang=$p"; done
if command -v curl >/dev/null 2>&1 && curl -sI --max-time 15 https://conda.anaconda.org/conda-forge/ >/dev/null 2>&1
then echo internet=1; else echo internet=0; fi
echo selesai=1
"""


def urai_prasyarat_dalam(teks):
    """Keluaran _SKRIP_PRASYARAT -> dict (hilang = daftar)."""
    d = {"hilang": []}
    for b in teks.splitlines():
        if "=" not in b:
            continue
        k, v = b.split("=", 1)
        k, v = k.strip(), v.strip()
        if k == "hilang":
            d["hilang"].append(v)
        elif k:
            d[k] = v
    return d


def _jalankan(argv, input_=None, timeout=90):
    try:
        p = subprocess.run(argv, input=input_, capture_output=True, timeout=timeout)
        return p.returncode, teks_wsl(p.stdout) + teks_wsl(p.stderr)
    except FileNotFoundError:
        return None, ""
    except subprocess.TimeoutExpired:
        return -1, "batas waktu"


def disk_host_gb(distro):
    """Ruang kosong (GB) di drive Windows tempat disk virtual distro berada. `df` di dalam WSL melaporkan batas
    disk virtual (±1 TB), bukan ruang nyata: ext4.vhdx tumbuh di drive Windows itu sampai drive penuh."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Lxss") as akar:
            for i in range(winreg.QueryInfoKey(akar)[0]):
                with winreg.OpenKey(akar, winreg.EnumKey(akar, i)) as k:
                    if winreg.QueryValueEx(k, "DistributionName")[0] == distro:
                        basis = str(winreg.QueryValueEx(k, "BasePath")[0]).replace("\\\\?\\", "")
                        return int(shutil.disk_usage(basis).free // 2 ** 30)
    except OSError:
        return None
    return None


def _sumber_daya_habis(teks):
    return "ERROR_NO_SYSTEM_RESOURCES" in teks or "Insufficient system resources" in teks


def periksa_prasyarat(distro=None, jalankan=_jalankan, build_windows=None, disk_host=disk_host_gb):
    """Periksa semua prasyarat. `jalankan` dan `build_windows` dapat diganti di uji (tanpa WSL sungguhan)."""
    pr = Prasyarat()
    build = build_windows if build_windows is not None else (
        sys.getwindowsversion().build if sys.platform == "win32" else 0)
    win_ok = build >= 19041
    pr.syarat.append(Syarat("windows", "Windows 10 versi 2004 atau lebih baru", win_ok, True,
                            f"build {build}" if win_ok else
                            f"Windows build {build}: WSL 2 butuh Windows 10 versi 2004 (build 19041) atau Windows 11."))
    kode, teks = jalankan(["wsl", "-l", "-v"], timeout=60)
    if kode is None or (kode != 0 and not daftar_distro(teks)):
        pr.syarat.append(Syarat("wsl", "WSL dan distro Linux", False, True,
                                "WSL belum terpasang (atau belum ada distro Linux). Memasangnya butuh izin "
                                "administrator dan restart.", aksi="pasang_wsl"))
        _simpulkan(pr)
        return pr
    pr.daftar_distro = daftar_distro(teks)
    pilih = distro or distro_wsl()
    target = next((d for d in pr.daftar_distro if d["nama"] == pilih), None) if pilih else None
    target = target or next((d for d in pr.daftar_distro if d["bawaan"]), None) or \
        (pr.daftar_distro[0] if pr.daftar_distro else None)
    if target is None:
        pr.syarat.append(Syarat("wsl", "WSL dan distro Linux", False, True,
                                "WSL ada, tetapi belum ada distro Linux.", aksi="pasang_wsl"))
        _simpulkan(pr)
        return pr
    pr.distro = target["nama"]
    pr.syarat.append(Syarat("wsl", "WSL dan distro Linux", True, True, f"distro {pr.distro}"))
    v2 = target["versi"] == 2
    pr.syarat.append(Syarat("wsl2", "Distro berjalan di WSL 2", v2, True,
                            "WSL 2" if v2 else f"{pr.distro} berjalan di WSL 1; alat GPU butuh WSL 2.",
                            aksi="" if v2 else "salin", perintah="" if v2 else f"wsl --set-version {pr.distro} 2"))
    if not v2:
        _simpulkan(pr)
        return pr

    kode, teks = jalankan(["wsl", "-d", pr.distro, "-e", "bash", "-s"], input_=_SKRIP_PRASYARAT.encode(),
                          timeout=120)
    if _sumber_daya_habis(teks):
        pr.syarat.append(Syarat("jalan", "WSL dapat dijalankan", False, True,
                                "WSL menolak berjalan karena sumber daya Windows sedang habis "
                                "(ERROR_NO_SYSTEM_RESOURCES). Tutup aplikasi kamera atau video, lalu Periksa ulang."))
        _simpulkan(pr)
        return pr
    d = urai_prasyarat_dalam(teks)
    if kode != 0 or d.get("selesai") != "1":
        pr.syarat.append(Syarat("jalan", "WSL dapat dijalankan", False, True,
                                "Perintah di dalam WSL gagal: "
                                + (teks.strip().splitlines() or ["tanpa keluaran"])[-1][:200],
                                aksi="terminal"))
        _simpulkan(pr)
        return pr
    pr.gpu = d.get("gpu", "")
    pr.syarat.append(Syarat("gpu", "GPU NVIDIA terlihat dari WSL", bool(pr.gpu), False,
                            pr.gpu or ("Tidak ada GPU NVIDIA yang terlihat dari WSL. Uni-Dock dan GNINA (CUDA saja) "
                                       "tidak dapat dipasang; OpenFE dan Boltz-2 tetap bisa di CPU, tetapi sangat "
                                       "lambat. Bila laptop punya GPU NVIDIA, perbarui drivernya di Windows.")))
    try:
        dalam = int(d.get("disk_gb") or "")
    except ValueError:
        dalam = None
    host = disk_host(pr.distro)
    nilai = [x for x in (dalam, host) if x is not None]
    pr.disk_gb = min(nilai) if nilai else None
    terbesar = max(p["puncak_gb"] for p in PAKET.values()) + CADANGAN_DISK_GB
    disk_ok = pr.disk_gb is None or pr.disk_gb >= terbesar
    pr.syarat.append(Syarat("disk", "Ruang disk untuk WSL", disk_ok, False,
                            f"{pr.disk_gb} GB bebas di drive disk WSL" if disk_ok else
                            f"Hanya {pr.disk_gb} GB bebas; satu paket butuh hingga {terbesar} GB. Disk virtual WSL "
                            "tumbuh di drive Windows tempatnya berada (biasanya C:) — kosongkan drive itu lebih dulu.",
                            aksi="" if disk_ok else "salin",
                            perintah="" if disk_ok else f"wsl --manage {pr.distro} --set-sparse true"))
    try:
        pr.mem_gb = round(int(d.get("mem_mb") or "") / 1024, 1)
    except ValueError:
        pr.mem_gb = None
    mem_ok = pr.mem_gb is None or pr.mem_gb >= MEMORI_BOLTZ_GB
    pr.syarat.append(Syarat("memori", "Memori untuk WSL", mem_ok, False,
                            (f"{_gb(pr.mem_gb)} GB RAM" if pr.mem_gb is not None else "tidak terbaca") if mem_ok else
                            f"WSL hanya mendapat {_gb(pr.mem_gb)} GB RAM. Boltz-2 dihentikan sistem pada 4 GB dan "
                            "berjalan pada 8 GB; bila RAM laptop 16 GB atau lebih, naikkan memory= di "
                            "%USERPROFILE%\\.wslconfig lalu jalankan wsl --shutdown."))
    hilang = d["hilang"]
    pr.syarat.append(Syarat("alat_dasar", "Alat dasar Linux (curl, tar, python3)", not hilang, True,
                            "lengkap" if not hilang else f"Belum ada: {', '.join(hilang)}. Pasang sekali di terminal "
                                                         "Ubuntu (diminta kata sandi Ubuntu).",
                            aksi="" if not hilang else "terminal",
                            perintah="" if not hilang else
                            "sudo apt update && sudo apt install -y " + " ".join(hilang)))
    inet = d.get("internet") == "1"
    pr.syarat.append(Syarat("internet", "Internet dari WSL", inet, True,
                            "conda-forge terjangkau" if inet else
                            "conda-forge tidak terjangkau dari WSL. Periksa koneksi; di jaringan kampus mungkin perlu "
                            "proksi (variabel HTTPS_PROXY di Ubuntu)."))
    pr.syarat.append(Syarat("pengguna", "Pengguna Linux", True, False,
                            f"alat dipasang di /home pengguna '{d.get('pengguna', '?')}'"
                            if d.get("pengguna") != "root" else
                            "Distro berjalan sebagai root; alat dipasang di /root/virmolab-alat dan tetap dapat "
                            "dipakai."))
    _simpulkan(pr)
    return pr


def _gb(x):
    """Angka GB satu desimal berkoma (3,8); kamus Inggris menggantinya dengan titik."""
    return f"{x:.1f}".replace(".", ",")


def _simpulkan(pr):
    """Isi pr.bisa: paket -> (boleh, alasan, daftar alat yang dilewati)."""
    wajib_gagal = [s for s in pr.syarat if s.wajib and not s.ok]
    for kunci, p in PAKET.items():
        if wajib_gagal:
            pr.bisa[kunci] = (False, wajib_gagal[0].pesan, [])
            continue
        if pr.disk_gb is not None and pr.disk_gb < p["puncak_gb"] + CADANGAN_DISK_GB:
            pr.bisa[kunci] = (False, f"Butuh ±{p['puncak_gb'] + CADANGAN_DISK_GB} GB bebas di WSL; "
                                     f"tersedia {pr.disk_gb} GB.", [])
            continue
        catatan, lewati = [], []
        if not pr.gpu:
            nama_cuda = {"unidock": "Uni-Dock", "gnina": "GNINA"}[p["alat_cuda"]]
            catatan.append(f"Tanpa GPU NVIDIA: {nama_cuda} dilewati; sisanya berjalan di CPU dan sangat lambat.")
            lewati.append(p["alat_cuda"])
        if kunci == "cofolding" and pr.mem_gb is not None and pr.mem_gb < MEMORI_BOLTZ_GB:
            catatan.append(f"Memori WSL {_gb(pr.mem_gb)} GB: prediksi Boltz-2 kemungkinan dihentikan sistem karena "
                           "memori habis.")
        pr.bisa[kunci] = (True, " ".join(catatan), lewati)


# ------------------------------------------------------------------ menjalankan
def skrip_paket(kunci, lewati=()):
    """Isi skrip (bytes, LF) yang dikirim ke `bash -s` untuk satu paket."""
    p = PAKET[kunci]
    isi = (paths.ALAT_WSL / p["skrip"]).read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
    # VIRMOLAB_PID: dialog menghentikan pohon proses ini (micromamba, curl, uv) bila pengguna menekan Hentikan
    bagian = ['echo "VIRMOLAB_PID=$$"', f'export VIRMOLAB_LEWATI="{" ".join(lewati)}"', isi.rstrip("\n")]
    if kunci == "cofolding":
        bobot = (paths.ALAT_WSL / _BOBOT).read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
        # bobot diunduh sekarang, supaya prediksi pertama tidak tertahan unduhan ±2 GB tanpa kabar
        bagian += ['if [[ -x "$HOME/virmolab-alat/boltz/bin/python" ]]; then',
                   '  echo UNDUH_BOBOT_BOLTZ',
                   "  \"$HOME/virmolab-alat/boltz/bin/python\" - <<'VIRMOLAB_PY'",
                   bobot.rstrip("\n"),
                   "VIRMOLAB_PY",
                   "fi"]
    bagian.append("echo PAKET_SELESAI")
    return ("\n".join(bagian) + "\n").encode("utf-8")


def argv_pasang(distro=""):
    """Argumen proses pemasangan: isi skrip dikirim lewat stdin, bukan lewat jalur."""
    d = distro or distro_wsl()
    return (["wsl", "-d", d] if d else awalan_wsl()) + ["-e", "bash", "-s"]


def pid_dari(baris):
    """PID bash pemasang dari baris 'VIRMOLAB_PID=<n>'; None bila bukan baris itu."""
    m = re.match(r"^VIRMOLAB_PID=(\d+)$", baris.strip())
    return int(m.group(1)) if m else None


def argv_hentikan(distro, pid):
    """Hentikan bash pemasang beserta seluruh keturunannya di dalam WSL. Mematikan wsl.exe saja tidak menghentikan
    unduhan yang sedang berjalan di Linux."""
    bunuh = ('bunuh() { for c in $(pgrep -P "$1"); do bunuh "$c"; done; kill -TERM "$1" 2>/dev/null; }; '
             f"bunuh {int(pid)}")
    d = distro or distro_wsl()
    return (["wsl", "-d", d] if d else awalan_wsl()) + ["-e", "bash", "-c", bunuh]


def argv_pasang_wsl():
    """Pasang WSL + Ubuntu lewat UAC (pengguna menyetujui jendela Windows); butuh restart sesudahnya."""
    return ["powershell", "-NoProfile", "-Command",
            "Start-Process -FilePath wsl.exe -ArgumentList '--install','Ubuntu' -Verb RunAs"]


def argv_terminal(distro=""):
    """Buka terminal distro di jendela baru (untuk perintah yang butuh kata sandi Ubuntu)."""
    d = distro or distro_wsl()
    return ["cmd", "/c", "start", "", "wsl.exe"] + (["-d", d] if d else []) + ["~"]


def urai_kemajuan(baris, kunci):
    """Satu baris keluaran -> (indeks langkah, total, label) bila baris itu penanda; selain itu None."""
    b = baris.strip()
    langkah = PAKET[kunci]["langkah"]
    if b == "PAKET_SELESAI":
        return len(langkah), len(langkah), "Selesai"
    m = re.match(r"^ULANG_UNDUH\s+(\d+)$", b)
    if m:                     # indeks -1: kabar tanpa memajukan langkah
        return -1, len(langkah), f"Unduhan putus, mencoba lagi ({m.group(1)}/4)"
    if b.startswith("LEWATI_"):
        return -1, len(langkah), f"{b[7:].capitalize()} dilewati (butuh GPU NVIDIA)"
    for i, (penanda, label) in enumerate(langkah):
        if b == penanda:
            return i, len(langkah), label
    return None


def pesan_gagal(kode, log):
    """Kalimat untuk pengguna saat proses pemasangan berakhir dengan galat."""
    if _sumber_daya_habis(log):
        return ("WSL kehabisan sumber daya Windows (ERROR_NO_SYSTEM_RESOURCES). Tutup aplikasi kamera atau video, lalu "
                "klik Pasang lagi; unduhan yang sudah selesai tidak diulang.")
    if "No space left on device" in log:
        return "Disk WSL penuh. Kosongkan drive C:, lalu klik Pasang lagi untuk melanjutkan."
    if re.search(r"Could not resolve host|Failed to connect|Connection timed out|curl: \(\d+\)|urlopen error|"
                 r"handshake operation timed out|Temporary failure in name resolution|Network is unreachable|"
                 r"Gagal mengunduh .* putaran", log):
        return ("Koneksi internet terputus atau diblokir. Klik Pasang lagi untuk melanjutkan dari unduhan yang "
                "tersimpan.")
    ekor = [b for b in log.strip().splitlines() if b.strip()][-1:] or ["tanpa keluaran"]
    return f"Pemasangan berhenti (kode {kode}): {ekor[0][:200]}. Klik Pasang lagi untuk melanjutkan."


def berkas_log(kunci):
    f = paths.APPDATA / "log" / f"alat_wsl_{kunci}.log"
    f.parent.mkdir(parents=True, exist_ok=True)
    return f


# ------------------------------------------------------------------ status
def status_paket():
    """Status tiap alat (ada, pesan) dari modul pemakainya, dibaca segar dari WSL."""
    from . import lanjutan, rbfe_openfe, unidock
    return {"gpu_rbfe": {"Uni-Dock": unidock.status(segar=True), "OpenFE": rbfe_openfe.status(segar=True)},
            "cofolding": {"Boltz-2": lanjutan.status_boltz(segar=True), "GNINA": lanjutan.status_gnina(segar=True)}}


def segarkan_semua():
    """Lupakan status WSL yang tersimpan (dipanggil sesudah pemasangan atau saat distro diganti)."""
    from . import lanjutan, rbfe_openfe, unidock
    unidock.status(segar=True)
    rbfe_openfe.status(segar=True)
    lanjutan.segarkan_status()


def wsl_ada():
    return bool(shutil.which("wsl"))
