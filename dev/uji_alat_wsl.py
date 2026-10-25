"""Uji modul pemasang alat WSL (core/alat_wsl.py) tanpa memasang apa pun.

Keluaran wsl.exe ditiru untuk tiap keadaan laptop pengguna (tanpa WSL, WSL1, tanpa NVIDIA, disk kurang, alat dasar
hilang, internet mati, sumber daya habis), lalu diperiksa: syarat yang gagal, aksi perbaikan, dan paket yang boleh
dipasang. Penanda langkah dicocokkan dua arah dengan skrip sungguhan, dan skrip rakitan diperiksa `bash -n` bila WSL
ada.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_alat_wsl.py
"""
import re
import subprocess
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))
from virmolab.core import alat_wsl as A, paths            # noqa: E402
from virmolab.core.lanjutan import teks_wsl                # noqa: E402

gagal = []


def cek(ok, pesan):
    print(("OK    " if ok else "GAGAL ") + pesan, flush=True)
    if not ok:
        gagal.append(pesan)


DAFTAR = "  NAME      STATE           VERSION\n* Ubuntu    Running         2\n  Lain      Stopped         1\n"
DALAM_OK = ("pengguna=rizki\ngpu=NVIDIA GeForce RTX 3060 Laptop GPU, 610.74\ndisk_gb=914\nmem_mb=7890\ninternet=1\n"
            "selesai=1\n")


def tiru(daftar=DAFTAR, dalam=DALAM_OK, kode_dalam=0, tanpa_wsl=False):
    def jalankan(argv, input_=None, timeout=90):
        if tanpa_wsl:
            return None, ""
        if argv[:3] == ["wsl", "-l", "-v"]:
            return 0, daftar
        return kode_dalam, dalam
    return jalankan


def pr_(**kw):
    host, build = kw.pop("host", 90), kw.pop("build", 19045)
    return A.periksa_prasyarat(jalankan=tiru(**kw), build_windows=build, disk_host=lambda _d: host)


def syarat(pr, kunci):
    return next((s for s in pr.syarat if s.kunci == kunci), None)


# --- dekode & daftar distro
cek(teks_wsl("  NAME   STATE   VERSION\r\n* Ubuntu Running 2\r\n".encode("utf-16-le")).count("Ubuntu") == 1,
    "keluaran wsl.exe UTF-16LE terbaca")
d = A.daftar_distro(DAFTAR)
cek([(x["nama"], x["versi"], x["bawaan"]) for x in d] == [("Ubuntu", 2, True), ("Lain", 1, False)],
    f"daftar distro dan distro bawaan ({d})")

# --- laptop lengkap
pr = pr_()
cek(pr.distro == "Ubuntu" and all(s.ok for s in pr.syarat), "semua syarat terpenuhi pada laptop lengkap")
cek(all(v[0] and not v[2] for v in pr.bisa.values()), "kedua paket boleh dipasang tanpa yang dilewati")

# --- tanpa WSL
pr = pr_(tanpa_wsl=True)
s = syarat(pr, "wsl")
cek(s and not s.ok and s.aksi == "pasang_wsl", "tanpa WSL: syarat wsl gagal dengan aksi pasang_wsl")
cek(not any(v[0] for v in pr.bisa.values()), "tanpa WSL: tidak ada paket yang boleh dipasang")

# --- WSL ada tetapi tanpa distro
pr = pr_(daftar="Windows Subsystem for Linux has no installed distributions.\n")
cek(not syarat(pr, "wsl").ok and syarat(pr, "wsl").aksi == "pasang_wsl", "WSL tanpa distro: tawarkan pasang")

# --- Windows terlalu lama
pr = pr_(build=18363)
cek(not syarat(pr, "windows").ok and not any(v[0] for v in pr.bisa.values()), "Windows 1909: ditolak")

# --- WSL1
pr = pr_(daftar="  NAME  STATE  VERSION\n* Ubuntu Running 1\n")
s = syarat(pr, "wsl2")
cek(s and not s.ok and s.perintah == "wsl --set-version Ubuntu 2", "WSL1: perintah ubah ke WSL 2")

# --- tanpa NVIDIA (K5)
pr = pr_(dalam=DALAM_OK.replace("gpu=NVIDIA GeForce RTX 3060 Laptop GPU, 610.74", "gpu="))
cek(not syarat(pr, "gpu").ok and not syarat(pr, "gpu").wajib, "tanpa NVIDIA: syarat gpu gagal tetapi tidak wajib")
cek(pr.bisa["gpu_rbfe"][:1] == (True,) and pr.bisa["gpu_rbfe"][2] == ["unidock"]
    and pr.bisa["cofolding"][2] == ["gnina"], f"tanpa NVIDIA: paket boleh, Uni-Dock/GNINA dilewati ({pr.bisa})")

# --- disk host kurang (df di dalam WSL melaporkan 914 GB virtual)
pr = pr_(host=12)
cek(pr.disk_gb == 12 and not syarat(pr, "disk").ok, "disk diukur dari drive Windows, bukan df virtual")
cek(not pr.bisa["gpu_rbfe"][0] and not pr.bisa["cofolding"][0], f"disk 12 GB: kedua paket ditolak ({pr.bisa})")
pr = pr_(host=23)
cek(not pr.bisa["gpu_rbfe"][0] and pr.bisa["cofolding"][0],
    "disk 23 GB: hanya co-folding (puncak 17+5 GB) boleh, GPU & RBFE (19+5 GB) ditolak")

# --- memori WSL kecil (laptop 8 GB: WSL bawaan hanya 4 GB); Boltz-2 dihentikan OOM pada 4 GB
pr = pr_(dalam=DALAM_OK.replace("mem_mb=7890", "mem_mb=3889"))
s = syarat(pr, "memori")
cek(s and not s.ok and not s.wajib and "3,8 GB" in s.pesan, f"memori 3,8 GB: syarat memori gagal, tidak wajib ({s and s.pesan})")
cek(pr.bisa["cofolding"][0] and "Boltz-2" in pr.bisa["cofolding"][1] and not pr.bisa["gpu_rbfe"][1],
    f"memori 3,8 GB: co-folding tetap boleh dengan peringatan, GPU & RBFE tanpa catatan ({pr.bisa})")
pr = pr_(dalam=DALAM_OK.replace("mem_mb=7890", "mem_mb=3889").replace(
    "gpu=NVIDIA GeForce RTX 3060 Laptop GPU, 610.74", "gpu="))
cek(pr.bisa["cofolding"][2] == ["gnina"] and "GNINA" in pr.bisa["cofolding"][1] and "Memori" in pr.bisa["cofolding"][1],
    "tanpa NVIDIA + memori kecil: kedua catatan digabung")

# --- alat dasar hilang & internet mati
pr = pr_(dalam=DALAM_OK + "hilang=curl\n")
s = syarat(pr, "alat_dasar")
cek(s and not s.ok and s.aksi == "terminal" and "apt install -y curl" in s.perintah, "curl hilang: perintah apt")
pr = pr_(dalam=DALAM_OK.replace("internet=1", "internet=0"))
cek(not syarat(pr, "internet").ok and not any(v[0] for v in pr.bisa.values()), "internet mati: paket ditolak")

# --- WSL gagal berjalan / sumber daya habis / pengguna root
pr = pr_(dalam="Wsl/Service/CreateInstance/CreateVm/ERROR_NO_SYSTEM_RESOURCES\n", kode_dalam=1)
cek("ERROR_NO_SYSTEM_RESOURCES" in syarat(pr, "jalan").pesan and "kamera" in syarat(pr, "jalan").pesan,
    "sumber daya habis: pesan khusus")
pr = pr_(dalam="", kode_dalam=1)
cek(not syarat(pr, "jalan").ok and syarat(pr, "jalan").aksi == "terminal", "perintah dalam WSL gagal: buka terminal")
pr = pr_(dalam=DALAM_OK.replace("pengguna=rizki", "pengguna=root"))
cek(syarat(pr, "pengguna").ok and "root" in syarat(pr, "pengguna").pesan, "pengguna root: dicatat, tidak memblokir")

# --- penanda langkah dua arah terhadap skrip sungguhan
for kunci, p in A.PAKET.items():
    teks = (paths.ALAT_WSL / p["skrip"]).read_text(encoding="utf-8")
    dicetak = set(re.findall(r'echo\s+"?([A-Z][A-Z0-9_]+)"?', teks))
    if kunci == "cofolding":
        dicetak.add("UNDUH_BOBOT_BOLTZ")             # ditambahkan skrip_paket()
    langkah = {m for m, _l in p["langkah"]}
    tak_dikenal = {m for m in dicetak - langkah if not m.startswith(("ULANG_UNDUH", "LEWATI_"))}
    cek(not tak_dikenal, f"{kunci}: semua penanda skrip dikenali ({sorted(tak_dikenal)})")
    cek(not (langkah - dicetak), f"{kunci}: tiap langkah memang dicetak skrip ({sorted(langkah - dicetak)})")

cek(A.urai_kemajuan("UNDUH_OPENFE", "gpu_rbfe")[:2] == (1, 6), "UNDUH_OPENFE = langkah 2 dari 6")
cek(A.urai_kemajuan("PAKET_SELESAI", "cofolding")[0] == len(A.PAKET["cofolding"]["langkah"]), "PAKET_SELESAI")
cek(A.urai_kemajuan("ULANG_UNDUH 2", "gpu_rbfe") == (-1, 6, "Unduhan putus, mencoba lagi (2/4)"), "ULANG_UNDUH")
cek(A.urai_kemajuan("LEWATI_UNIDOCK", "gpu_rbfe")[0] == -1, "LEWATI_UNIDOCK dikabarkan tanpa memajukan langkah")
cek(A.urai_kemajuan("Downloading openmm-8.4", "gpu_rbfe") is None, "baris biasa bukan penanda")

# --- skrip rakitan
for kunci in A.PAKET:
    s = A.skrip_paket(kunci, ["unidock"] if kunci == "gpu_rbfe" else [])
    cek(b"\r" not in s and s.startswith(b'echo "VIRMOLAB_PID=$$"\nexport VIRMOLAB_LEWATI=')
        and s.rstrip().endswith(b"echo PAKET_SELESAI"),
        f"{kunci}: skrip rakitan LF, diawali PID & LEWATI, diakhiri PAKET_SELESAI")
    try:
        p = subprocess.run(["wsl", "-e", "bash", "-n"], input=s, capture_output=True, timeout=60)
        galat = teks_wsl(p.stderr or b"")
        if p.returncode != 0 and "syntax error" not in galat.lower():
            # wsl.exe sendiri gagal start (mis. ERROR_NO_SYSTEM_RESOURCES saat distro lain sedang sibuk)
            print(f"LEWAT {kunci}: WSL tidak dapat dijalankan sekarang ({galat.strip()[:80]})")
        else:
            cek(p.returncode == 0, f"{kunci}: skrip rakitan sah menurut bash -n ({galat.strip()[:120]})")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print(f"LEWAT {kunci}: WSL tidak ada, bash -n tidak diperiksa")
cek(b"VIRMOLAB_PY" in A.skrip_paket("cofolding") and b"download_boltz2" in A.skrip_paket("cofolding"),
    "cofolding: unduh bobot Boltz disisipkan sebagai heredoc")

# --- pesan galat & argumen
cek("kamera" in A.pesan_gagal(1, "...ERROR_NO_SYSTEM_RESOURCES..."), "pesan: sumber daya habis")
cek("penuh" in A.pesan_gagal(1, "tar: write error: No space left on device"), "pesan: disk penuh")
cek("internet" in A.pesan_gagal(6, "curl: (6) Could not resolve host: conda.anaconda.org"), "pesan: internet")
cek("internet" in A.pesan_gagal(1, "boltz2_conf.ckpt: https://x gagal (<urlopen error _ssl.c:993: The handshake "
                                   "operation timed out>)\nGagal mengunduh boltz2_conf.ckpt sesudah 4 putaran; periksa "
                                   "koneksi internet."), "pesan: unduh bobot Boltz putus (urllib)")
cek("kode 2" in A.pesan_gagal(2, "baris1\nsesuatu rusak\n"), "pesan: galat lain menyebut kode dan baris terakhir")
cek(A.argv_pasang("VirmoLabUji") == ["wsl", "-d", "VirmoLabUji", "-e", "bash", "-s"], "argv pemasangan via stdin")
cek("-Verb RunAs" in " ".join(A.argv_pasang_wsl()), "pasang WSL lewat UAC (RunAs)")
cek(A.pid_dari("VIRMOLAB_PID=4321") == 4321 and A.pid_dari("PID 4321") is None, "PID bash pemasang terbaca")
cek(A.argv_hentikan("VirmoLabUji", 4321)[:5] == ["wsl", "-d", "VirmoLabUji", "-e", "bash"]
    and "bunuh 4321" in A.argv_hentikan("VirmoLabUji", 4321)[-1], "Hentikan menghentikan pohon proses di WSL")

print("\nLULUS" if not gagal else f"\nGAGAL {len(gagal)}")
sys.exit(1 if gagal else 0)
