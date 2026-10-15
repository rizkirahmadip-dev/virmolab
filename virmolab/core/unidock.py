"""Uni-Dock (GPU, Linux) lewat WSL untuk docking banyak ligan sekaligus.

Uni-Dock 1.2 (Apache-2.0; Yu dkk., J. Chem. Theory Comput. 2023) menjalankan pencarian Monte Carlo dengan
fungsi skor Vina/Vinardo untuk ratusan ligan bersamaan di GPU NVIDIA. Programnya hanya ada untuk Linux + CUDA,
jadi VirmoLab memanggilnya di WSL seperti GNINA dan Boltz (dipasang build_tools/pasang_openfe_unidock_wsl.sh,
tidak ikut installer). Keluarannya PDBQT bergaya Vina dan dibaca dengan pembaca Vina, sehingga tabel hasil,
interaksi, PoseBusters, dan RMSD redocking berjalan sama seperti Vina.

Modul ini murni: menyusun skrip batch dan memetakan keluaran; eksekusi (QProcess, progres, batal) ada di antrean.
"""
import shlex
from pathlib import Path

from .lanjutan import ALAT, _wsl, _wsl_ada, ke_wsl

PROGRAM = f"{ALAT}/unidock/bin/unidock"
MODE = {"fast": "Cepat", "balance": "Seimbang", "detail": "Detail"}
PRESET_KE_MODE = {"Cepat": "fast", "Standar": "balance", "Teliti": "detail"}
_status = {"ada": False, "versi": "", "diperiksa": False}
_akar_drive = {}


def status(segar=False):
    """{ada, versi, pesan}. Memanggil WSL (±1-3 s) hanya bila belum pernah diperiksa atau segar=True."""
    if segar or not _status["diperiksa"]:
        _status["diperiksa"] = True
        _status["ada"] = _wsl_ada(f"test -x {PROGRAM} && echo ADA")
        if _status["ada"]:
            try:
                p = _wsl(f"{PROGRAM} --version", timeout=40)
                _status["versi"] = (p.stdout or "").strip().splitlines()[0] if p.stdout else ""
            except Exception:
                _status["versi"] = ""
    pesan = (f"{_status['versi'] or 'Uni-Dock'} siap di WSL (GPU NVIDIA). Banyak ligan didocking sekaligus; "
             "fungsi skor Vina, jadi ΔG setara Vina." if _status["ada"] else
             "Uni-Dock belum terpasang di WSL. Pasang dengan build_tools/pasang_openfe_unidock_wsl.sh "
             "(Linux + CUDA, Apache-2.0, tidak ikut installer).")
    return {"ada": _status["ada"], "versi": _status["versi"], "pesan": pesan}


def tersedia():
    """Status terakhir tanpa memanggil WSL (aman dipanggil dari thread GUI)."""
    return bool(_status["ada"])


def jalur_wsl(p):
    """Jalur Windows -> WSL tanpa memanggil wslpath untuk tiap berkas (ribuan ligan): akar drive ditanyakan
    sekali ke WSL lalu sisa jalurnya disambung."""
    p = Path(p).resolve()
    drive = p.anchor
    if drive not in _akar_drive:
        try:
            _akar_drive[drive] = ke_wsl(drive).rstrip("/")
        except (TimeoutError, RuntimeError):
            # WSL sibuk (mis. simulasi lain) atau baru bangun: pola /mnt/<huruf> berlaku pada pemasangan baku
            huruf = drive[0].lower()
            if not huruf.isalpha():
                raise
            _akar_drive[drive] = f"/mnt/{huruf}"
    return _akar_drive[drive] + "/" + p.relative_to(drive).as_posix()


def tulis_skrip(reseptor, ligan, keluar, kotak, mode="balance", skor="vina", num_modes=9, seed=42, max_gpu_mb=0):
    """Tulis skrip bash untuk satu batch -> (jalur skrip Windows, {nama symlink: jalur ligan asli}).

    Uni-Dock memecah berkas --ligand_index pada spasi, jadi ligan dirujuk lewat symlink bernama sederhana
    (u00001.pdbqt, ...) di folder sementara WSL. Daftar ligan ada di dalam skrip, bukan di baris perintah
    Windows (batas 32 KB), sehingga ribuan ligan tetap muat. Keluaran: <keluar>/u00001_out.pdbqt, ..."""
    keluar = Path(keluar)
    keluar.mkdir(parents=True, exist_ok=True)
    peta = {}
    baris = ["#!/bin/bash", "set -u", 'T=$(mktemp -d)', "trap 'rm -rf \"$T\"' EXIT"]
    for i, p in enumerate(ligan, 1):
        nama = f"u{i:05d}"
        peta[nama] = Path(p)
        baris.append(f'ln -s {shlex.quote(jalur_wsl(p))} "$T/{nama}.pdbqt"')
    baris.append('ls "$T"/u*.pdbqt > "$T/indeks.txt"')
    c, s = kotak.pusat, kotak.ukuran
    arg = ["--receptor", jalur_wsl(reseptor), "--dir", jalur_wsl(keluar),
           "--center_x", f"{c[0]:.3f}", "--center_y", f"{c[1]:.3f}", "--center_z", f"{c[2]:.3f}",
           "--size_x", f"{s[0]:.2f}", "--size_y", f"{s[1]:.2f}", "--size_z", f"{s[2]:.2f}",
           "--search_mode", mode, "--scoring", skor, "--num_modes", str(num_modes), "--verbosity", "1"]
    if seed:
        arg += ["--seed", str(seed)]
    if max_gpu_mb:
        arg += ["--max_gpu_memory", str(max_gpu_mb)]
    # program dan $T tidak dikutip tunggal supaya bash memperluasnya; jalur lain dikutip (spasi)
    baris.append(f'{PROGRAM} --ligand_index "$T/indeks.txt" ' + " ".join(shlex.quote(a) for a in arg))
    f = keluar / "jalan_unidock.sh"
    f.write_bytes(("\n".join(baris) + "\n").encode("utf-8"))      # LF: bash menolak CRLF
    return f, peta


def perintah_wsl(skrip):
    """Argumen QProcess/subprocess: wsl -e bash <skrip>."""
    return ["wsl", "-e", "bash", jalur_wsl(skrip)]


def keluaran_ligan(folder_keluar, nama_symlink):
    """Uni-Dock menulis <nama berkas masukan>_out.pdbqt di --dir (nama masukan = nama symlink, mis. u00001)."""
    return Path(folder_keluar) / f"{nama_symlink}_out.pdbqt"
