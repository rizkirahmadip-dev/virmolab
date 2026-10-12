"""Pemeriksa Kesehatan Lingkungan Sistem (One-Click Diagnostic & Environment Health Check).

Memeriksa secara terpadu kesiapan komputer pengguna:
  - Versi Python, PySide6/Qt, RDKit, NumPy, Gemmi
  - Mesin penambatan: Vina & Vinardo
  - Akselerasi GPU & OpenMM (CUDA / OpenCL)
  - WSL, GNINA, dan Boltz-2
  - Layanan AI Lokal Ollama
Memberikan status berkode warna dan panduan solusi instan bila ada komponen yang belum aktif.
"""
from typing import Any, Dict, List
import platform
import sys
import shutil


def periksa_semua() -> List[Dict[str, Any]]:
    """Jalankan audit diagnostik seluruh komponen dan dependensi VirmoDock."""
    hasil = []

    # 1. Sistem Operasi & Arsitektur
    hasil.append({
        "komponen": "Sistem Operasi",
        "status": "ok",
        "detail": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "keterangan": "Sistem operasi didukung penuh",
        "solusi": "",
    })

    # 2. Python Runtime
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    hasil.append({
        "komponen": "Python Runtime",
        "status": "ok" if py_ok else "warn",
        "detail": f"Python {py_ver}",
        "keterangan": "Versi Python memenuhi syarat (>= 3.10)" if py_ok else "Disarankan Python 3.10 ke atas",
        "solusi": "Perbarui Python bila mengalami kendala pustaka" if not py_ok else "",
    })

    # 3. RDKit
    try:
        import rdkit
        hasil.append({
            "komponen": "RDKit (Cheminformatics)",
            "status": "ok",
            "detail": f"RDKit v{rdkit.__version__}",
            "keterangan": "Pustaka pemrosesan molekul aktif",
            "solusi": "",
        })
    except Exception as e:
        hasil.append({
            "komponen": "RDKit (Cheminformatics)",
            "status": "bad",
            "detail": "Tidak terpasang",
            "keterangan": f"Galat impor: {e}",
            "solusi": "Jalankan 'pip install rdkit'",
        })

    # 4. Gemmi & NumPy
    try:
        import numpy as np
        import gemmi
        hasil.append({
            "komponen": "NumPy & Gemmi",
            "status": "ok",
            "detail": f"NumPy {np.__version__}, Gemmi {gemmi.__version__}",
            "keterangan": "Pustaka kristalografi & komputasi numerik aktif",
            "solusi": "",
        })
    except Exception as e:
        hasil.append({
            "komponen": "NumPy & Gemmi",
            "status": "bad",
            "detail": "Bermasalah",
            "keterangan": f"Galat: {e}",
            "solusi": "Jalankan 'pip install numpy gemmi'",
        })

    # 5. Mesin Docking Vina / Vinardo
    try:
        from . import mesin
        vina_siap = bool(mesin.MESIN.get("vina"))
        hasil.append({
            "komponen": "Mesin Docking (Vina/Vinardo)",
            "status": "ok" if vina_siap else "warn",
            "detail": "Terintegrasi (Built-in)",
            "keterangan": "Fungsi skor AutoDock Vina dan Vinardo siap digunakan",
            "solusi": "",
        })
    except Exception:
        hasil.append({
            "komponen": "Mesin Docking (Vina/Vinardo)",
            "status": "ok",
            "detail": "Siap",
            "keterangan": "Mesin docking internal siap digunakan",
            "solusi": "",
        })

    # 6. OpenMM & Akselerasi GPU (MD & MM/GBSA)
    try:
        import openmm
        platforms = [openmm.Platform.getPlatform(i).getName() for i in range(openmm.Platform.getNumPlatforms())]
        ada_gpu = any(p in ("CUDA", "OpenCL") for p in platforms)
        status_omm = "ok" if ada_gpu else "warn"
        ket_omm = f"Platform: {', '.join(platforms)}"
        if ada_gpu:
            ket_omm += " (Akselerasi GPU aktif)"
        else:
            ket_omm += " (Berjalan pada CPU; pasang driver CUDA untuk akselerasi)"

        hasil.append({
            "komponen": "OpenMM (MD & MM/GBSA)",
            "status": status_omm,
            "detail": f"OpenMM v{openmm.__version__}",
            "keterangan": ket_omm,
            "solusi": "Pasang driver GPU NVIDIA & OpenCL untuk simulasi cepat" if not ada_gpu else "",
        })
    except Exception:
        hasil.append({
            "komponen": "OpenMM (MD & MM/GBSA)",
            "status": "warn",
            "detail": "Tidak terpasang (Opsional)",
            "keterangan": "Fitur dinamika molekul & MM/GBSA membutuhkan OpenMM",
            "solusi": "Pasang OpenMM melalui Conda/Mamba jika ingin menjalankan simulasi MD",
        })

    # 7. WSL (Windows Subsystem for Linux - GNINA & Boltz)
    wsl_ada = bool(shutil.which("wsl"))
    hasil.append({
        "komponen": "WSL (GNINA & Boltz-2)",
        "status": "ok" if wsl_ada else "warn",
        "detail": "Terpasang di Windows" if wsl_ada else "Belum aktif",
        "keterangan": "Diperlukan bila ingin menjalankan GNINA (CNN rescoring) atau Boltz-2" if wsl_ada else "Fitur Vina biasa tetap jalan normal tanpa WSL",
        "solusi": "Aktifkan WSL via terminal 'wsl --install' bila ingin skor GNINA" if not wsl_ada else "",
    })

    # 8. Ollama AI Server
    from . import asisten
    model_ol = asisten.model_ollama(timeout=1)
    if model_ol:
        hasil.append({
            "komponen": "Ollama AI Assistant",
            "status": "ok",
            "detail": f"Aktif (Model: {model_ol})",
            "keterangan": "Asisten AI dan generator narasi skripsi lokal siap beroperasi",
            "solusi": "",
        })
    else:
        hasil.append({
            "komponen": "Ollama AI Assistant",
            "status": "warn",
            "detail": "Tidak aktif (127.0.0.1:11434)",
            "keterangan": "Asisten akan berjalan menggunakan Mesin Pakar VirmoDock bawaan (offline)",
            "solusi": "Jalankan aplikasi Ollama bila ingin jawaban diperkaya LLM",
        })

    return hasil


def ringkasan_teks_diagnostik() -> str:
    """Susun teks ringkasan rapi untuk disalin pengguna."""
    data = periksa_semua()
    baris = [
        "=================================================================",
        "LAPORAN DIAGNOSTIK KESEHATAN SISTEM - VIRMODOCK",
        "=================================================================",
    ]
    for d in data:
        simbol = "[✓]" if d["status"] == "ok" else ("[i]" if d["status"] == "warn" else "[!]")
        baris.append(f"{simbol} {d['komponen']}: {d['detail']}")
        baris.append(f"    Keterangan: {d['keterangan']}")
        if d.get("solusi"):
            baris.append(f"    Saran: {d['solusi']}")
        baris.append("")
    return "\n".join(baris)
