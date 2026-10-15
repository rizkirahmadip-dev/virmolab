"""Deteksi perangkat keras dan software terkait.

Dijalankan setiap kali aplikasi dibuka (bukan disimpan permanen), sehingga
saat pindah laptop konfigurasi GPU langsung menyesuaikan.
"""
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import paths

NOWIN = 0x08000000 if os.name == "nt" else 0


def jalankan(cmd, timeout=30, cwd=None):
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, cwd=cwd, creationflags=NOWIN)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, "", str(e)


@dataclass
class GPU:
    nama: str
    vendor: str = ""
    vram_gb: float = 0.0
    driver: str = ""
    opencl: bool = False      # bisa dipakai AutoDock-GPU
    platform: str = ""
    devnum: int = 0           # nilai --devnum AutoDock-GPU (platform*256 + perangkat + 1); 0 = tidak diketahui


@dataclass
class Lingkungan:
    gpu: list = field(default_factory=list)
    opencl_ok: bool = False
    cpu: str = ""
    inti: int = 0
    ram_gb: float = 0.0
    unidock: bool = False              # Uni-Dock (GPU) terpasang di WSL
    program: dict = field(default_factory=dict)   # nama -> jalur bawaan
    eksternal: dict = field(default_factory=dict)  # PyMOL/ChimeraX/DSV -> jalur
    catatan: list = field(default_factory=list)

    @property
    def gpu_utama(self):
        ok = [g for g in self.gpu if g.opencl]
        if ok:  # utamakan GPU diskrit (VRAM terbesar)
            return max(ok, key=lambda g: g.vram_gb)
        return self.gpu[0] if self.gpu else None

    @property
    def mode_bawaan(self):
        return "gpu" if self.opencl_ok and paths.program("autodock_gpu.exe") else "cpu"

    def ke_dict(self):
        d = asdict(self)
        d["mode_bawaan"] = self.mode_bawaan
        return d


def _wmi_gpu():
    """Nama, vendor, driver, VRAM semua adaptor grafis lewat CIM (tanpa WSL)."""
    ps = ("Get-CimInstance Win32_VideoController | Select-Object Name,AdapterCompatibility,"
          "DriverVersion,AdapterRAM | ConvertTo-Json -Compress")
    kode, out, _ = jalankan(["powershell", "-NoProfile", "-Command", ps], timeout=30)
    if kode != 0 or not out.strip():
        return []
    data = json.loads(out)
    if isinstance(data, dict):
        data = [data]
    hasil = []
    for d in data:
        nama = (d.get("Name") or "").strip()
        if not nama or "Basic Display" in nama or "Remote" in nama:
            continue
        ram = d.get("AdapterRAM") or 0
        hasil.append(GPU(nama=nama, vendor=(d.get("AdapterCompatibility") or "").strip(),
                         vram_gb=round(ram / 1024 ** 3, 1) if ram > 0 else 0.0,
                         driver=(d.get("DriverVersion") or "").strip()))
    return hasil


def _nvidia_smi(gpus):
    smi = shutil.which("nvidia-smi") or r"C:\Windows\System32\nvidia-smi.exe"
    if not os.path.exists(smi):
        return
    kode, out, _ = jalankan([smi, "--query-gpu=name,memory.total,driver_version",
                             "--format=csv,noheader,nounits"], timeout=20)
    if kode != 0:
        return
    for b in out.strip().splitlines():
        bag = [x.strip() for x in b.split(",")]
        if len(bag) < 3:
            continue
        cocok = next((g for g in gpus if bag[0] in g.nama or g.nama in bag[0]), None)
        if not cocok:
            cocok = GPU(nama=bag[0], vendor="NVIDIA")
            gpus.append(cocok)
        cocok.vram_gb = round(float(bag[1]) / 1024, 1)  # AdapterRAM WMI terpotong di 4 GB
        cocok.driver = bag[2]


def _opencl(gpus, env):
    clinfo = paths.program("clinfo.exe")
    if not clinfo:
        env.catatan.append("clinfo.exe tidak ada di folder program.")
        return
    kode, out, err = jalankan([clinfo, "-l"], timeout=30, cwd=str(paths.BIN))
    platform, p_idx = "", 0
    for b in out.splitlines():
        m = re.match(r"Platform #(\d+):\s*(.+)", b)
        if m:
            p_idx, platform = int(m.group(1)), m.group(2).strip()
            continue
        m = re.search(r"Device #(\d+):\s*(.+)", b)
        if m:
            d_idx, nama = int(m.group(1)), m.group(2).strip()
            # perangkat CPU OpenCL (mis. Intel CPU runtime) tidak dihitung sebagai GPU
            if re.search(r"\bCPU\b|Core\(TM\)|Ryzen", nama) and "Graphics" not in nama:
                continue
            g = next((g for g in gpus if nama in g.nama or g.nama in nama), None)
            if not g:
                g = GPU(nama=nama)
                gpus.append(g)
            g.opencl, g.platform = True, platform
            # AutoDock-GPU: devnum-1 = perangkat + (platform << 8)
            g.devnum = (p_idx << 8) + d_idx + 1
            env.opencl_ok = True


def _cpu(env):
    env.inti = os.cpu_count() or 1
    kode, out, _ = jalankan(["powershell", "-NoProfile", "-Command",
                             "(Get-CimInstance Win32_Processor | Select-Object -First 1).Name;"
                             "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)"], timeout=30)
    baris = [b.strip() for b in out.splitlines() if b.strip()]
    if baris:
        env.cpu = baris[0]
    if len(baris) > 1:
        try:
            env.ram_gb = float(baris[1].replace(",", "."))
        except ValueError:
            pass


EKSTERNAL = {
    "PyMOL": [r"%LOCALAPPDATA%\Schrodinger\PyMOL2\PyMOLWin.exe", r"%ProgramFiles%\PyMOL\PyMOLWin.exe",
              r"%ProgramData%\Anaconda3\Scripts\pymol.exe", r"%USERPROFILE%\anaconda3\Scripts\pymol.exe",
              r"%USERPROFILE%\miniconda3\Scripts\pymol.exe", r"%ProgramFiles%\Schrodinger\PyMOL2\PyMOLWin.exe"],
    "ChimeraX": [r"%ProgramFiles%\ChimeraX\bin\ChimeraX.exe", r"%ProgramFiles%\ChimeraX*\bin\ChimeraX.exe"],
    "Discovery Studio Visualizer": [r"%ProgramFiles%\BIOVIA\Discovery Studio*\bin\DiscoveryStudio*.exe",
                                    r"%ProgramFiles(x86)%\BIOVIA\Discovery Studio*\bin\DiscoveryStudio*.exe"],
}


def cari_eksternal(manual=None):
    """Cari PyMOL/ChimeraX/DSV. `manual` = jalur yang diatur pengguna (diutamakan)."""
    hasil = {}
    for nama, pola in EKSTERNAL.items():
        if manual and manual.get(nama) and os.path.exists(manual[nama]):
            hasil[nama] = manual[nama]
            continue
        for p in pola:
            p = os.path.expandvars(p)
            if "*" in p:
                induk = Path(p.split("*")[0]).parent
                if induk.exists():
                    cocok = sorted(induk.glob(str(Path(p).relative_to(induk)).replace("\\", "/")), reverse=True)
                    if cocok:
                        hasil[nama] = str(cocok[0])
                        break
            elif os.path.exists(p):
                hasil[nama] = p
                break
        if nama == "PyMOL" and nama not in hasil and shutil.which("pymol"):
            hasil[nama] = shutil.which("pymol")
        if nama == "ChimeraX" and nama not in hasil and shutil.which("ChimeraX"):
            hasil[nama] = shutil.which("ChimeraX")
    return hasil


def deteksi(manual=None):
    env = Lingkungan()
    gpus = _wmi_gpu()
    _nvidia_smi(gpus)
    _opencl(gpus, env)
    env.gpu = gpus
    _cpu(env)
    for p in ("autodock_gpu.exe", "vina.exe", "autogrid4.exe", "autodock4.exe"):
        env.program[p] = paths.program(p)
    env.eksternal = cari_eksternal(manual)
    try:      # WSL dipanggil sekali di thread latar; panel docking membaca hasilnya tanpa memblok GUI
        from . import unidock
        env.unidock = unidock.status(segar=True)["ada"]
    except Exception:
        env.unidock = False
    if gpus and not env.opencl_ok:
        env.catatan.append("GPU terdeteksi tetapi OpenCL tidak tersedia: driver GPU perlu diperbarui.")
    return env


PANDUAN_DRIVER = {
    "NVIDIA": ("Pasang driver NVIDIA terbaru", "https://www.nvidia.com/Download/index.aspx",
               ["Buka tautan di bawah, pilih seri dan model GPU laptop Anda.",
                "Unduh 'Game Ready' atau 'Studio Driver' lalu jalankan installer.",
                "Pilih instalasi Express, tunggu selesai, lalu restart laptop.",
                "Buka VirmoLab lagi: GPU akan terdeteksi otomatis."]),
    "AMD": ("Pasang AMD Software (Adrenalin)", "https://www.amd.com/en/support/download/drivers.html",
            ["Buka tautan, pilih 'Auto-Detect and Install'.", "Jalankan installer dan ikuti langkahnya.",
             "Restart laptop, lalu buka VirmoLab lagi."]),
    "Intel": ("Pasang Intel Graphics Driver", "https://www.intel.com/content/www/us/en/support/detect.html",
              ["Buka tautan dan jalankan Intel Driver & Support Assistant.", "Pasang pembaruan grafis yang disarankan.",
               "Restart laptop, lalu buka VirmoLab lagi."]),
}


def panduan_untuk(env):
    g = env.gpu_utama
    if not g:
        return None
    for v in PANDUAN_DRIVER:
        if v.lower() in (g.vendor + " " + g.nama).lower():
            return PANDUAN_DRIVER[v]
    return None
