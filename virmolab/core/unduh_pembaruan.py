"""Unduh installer rilis baru, verifikasi SHA-256-nya, lalu jalankan pemasangannya.

Sebelumnya pembaruan berhenti pada pemberitahuan: pengguna membuka peramban, mengunduh 500 MB sendiri,
mencocokkan sidik jari dengan tangan, lalu menjalankan installer. Enam langkah manual untuk tiap rilis.

Yang TIDAK dilakukan modul ini, dan sengaja:

- Tidak mengunduh sendiri tanpa diminta. Berkasnya ratusan megabita; pada koneksi berbayar atau lambat
  itu keputusan penggunanya, bukan keputusan aplikasi.
- Tidak memasang diam-diam di latar belakang. Mengganti berkas program saat docking atau MD sedang
  berjalan merusak pekerjaan yang mungkin sudah berjam-jam. Pemasangan selalu menutup aplikasi lebih dulu.
- Tidak pernah menjalankan berkas yang sidik jarinya tidak cocok. Berkas yang gagal verifikasi dihapus,
  bukan disimpan untuk "dicoba lagi".
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import winreg
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .. import __version__ as VERSI
from . import paths

UA = {"User-Agent": f"VirmoLab/{VERSI} (pembaruan)"}
POTONGAN = 1 << 20          # 1 MiB per bacaan: kemajuan terasa halus tanpa membanjiri sinyal


class GalatUnduh(Exception):
    pass


@dataclass
class Berkas:
    nama: str
    url: str
    ukuran: int


def _aset(hasil, akhiran):
    for a in hasil.get("aset") or []:
        if str(a.get("nama", "")).lower().endswith(akhiran):
            return Berkas(a["nama"], a["url"], int(a.get("ukuran") or 0))
    return None


def installer_dan_sidik(hasil):
    """(installer, berkas SHA256SUMS) dari hasil pembaruan.periksa(), atau (None, None)."""
    return _aset(hasil, ".exe"), _aset(hasil, ".txt")


def folder_unduh() -> Path:
    d = Path(paths.APPDATA) / "unduhan"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ambil(url, tujuan: Path, ukuran_harap=0, lapor=None, dibatalkan=None):
    """Unduh ke `tujuan`, melanjutkan berkas .part yang belum selesai bila ada."""
    part = tujuan.with_suffix(tujuan.suffix + ".part")
    sudah = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(url, headers=dict(UA))
    if sudah:
        req.add_header("Range", f"bytes={sudah}-")
    try:
        r = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        if sudah and e.code in (416, 200):      # peladen menolak lanjutan: mulai dari nol
            part.unlink(missing_ok=True)
            sudah = 0
            r = urllib.request.urlopen(urllib.request.Request(url, headers=dict(UA)), timeout=60)
        else:
            raise GalatUnduh(f"Peladen menolak permintaan ({e.code}).") from e
    except OSError as e:
        raise GalatUnduh(f"Koneksi gagal: {e}") from e

    total = ukuran_harap or (int(r.headers.get("Content-Length") or 0) + sudah)
    mode = "ab" if sudah and r.status == 206 else "wb"
    if mode == "wb":
        sudah = 0
    with open(part, mode) as f:
        while True:
            if dibatalkan is not None and dibatalkan():
                raise GalatUnduh("Dibatalkan.")
            blok = r.read(POTONGAN)
            if not blok:
                break
            f.write(blok)
            sudah += len(blok)
            if lapor:
                lapor(sudah, total)
    if total and sudah != total:
        part.unlink(missing_ok=True)
        raise GalatUnduh(f"Unduhan tidak utuh ({sudah} dari {total} bita).")
    part.replace(tujuan)
    return tujuan


def _sha256(f: Path, lapor=None):
    h = hashlib.sha256()
    n = 0
    total = f.stat().st_size
    with open(f, "rb") as fh:
        for blok in iter(lambda: fh.read(POTONGAN), b""):
            h.update(blok)
            n += len(blok)
            if lapor:
                lapor(n, total)
    return h.hexdigest()


def sidik_harapan(teks_sums: str, nama: str):
    """Sidik jari untuk `nama` dari isi berkas SHA256SUMS."""
    for baris in teks_sums.splitlines():
        m = re.match(r"([0-9a-fA-F]{64})\s+\*?(.+)$", baris.strip())
        if m and m.group(2).strip() == nama:
            return m.group(1).lower()
    return None


def unduh_terverifikasi(hasil, lapor=None, dibatalkan=None) -> Path:
    """Unduh installer rilis dan kembalikan jalurnya hanya bila SHA-256-nya cocok.

    `lapor(tahap, selesai, total)` dipanggil untuk kemajuan; `dibatalkan()` dicek di tiap potongan.
    """
    inst, sums = installer_dan_sidik(hasil)
    if inst is None or sums is None:
        raise GalatUnduh("Rilis ini tidak memuat installer beserta berkas SHA256SUMS-nya.")

    d = folder_unduh()
    # Sidik jari diambil lebih dulu: mengunduh 500 MB tanpa tahu pembandingnya tidak ada gunanya.
    f_sums = _ambil(sums.url, d / sums.nama, sums.ukuran,
                    lapor=(lambda a, b: lapor("sidik", a, b)) if lapor else None,
                    dibatalkan=dibatalkan)
    harap = sidik_harapan(f_sums.read_text(encoding="utf-8", errors="replace"), inst.nama)
    if not harap:
        raise GalatUnduh(f"{sums.nama} tidak memuat sidik jari untuk {inst.nama}.")

    f_inst = d / inst.nama
    if f_inst.exists():
        if _sha256(f_inst) == harap:
            return f_inst                   # sudah pernah diunduh dan masih utuh
        # Sisa unduhan lama yang tidak cocok: dibuang sekarang, bukan dibiarkan. Berkasnya ratusan
        # megabita, dan membiarkannya menunggu unduhan berikutnya berarti dua salinan di disk pengguna.
        f_inst.unlink(missing_ok=True)
    _ambil(inst.url, f_inst, inst.ukuran,
           lapor=(lambda a, b: lapor("unduh", a, b)) if lapor else None, dibatalkan=dibatalkan)

    nyata = _sha256(f_inst, lapor=(lambda a, b: lapor("verifikasi", a, b)) if lapor else None)
    if nyata != harap:
        f_inst.unlink(missing_ok=True)      # berkas yang tidak cocok tidak pernah disimpan
        raise GalatUnduh("Sidik jari SHA-256 tidak cocok; berkas dihapus. Coba unduh ulang, dan bila "
                         "tetap berbeda, laporkan — berkasnya mungkin rusak di tengah jalan.")
    return f_inst


APPID = "{6E3B2A51-8C1D-4E7F-9A42-5B0D7C9E1F38}"


def cakupan_pemasangan(appid=None):
    """"/CURRENTUSER", "/ALLUSERS", atau None bila VirmoLab tidak terdaftar sebagai terpasang.

    Installer menanyakan "untuk saya" atau "untuk semua pengguna" lewat dialog. Pada pemasangan senyap
    dialog itu tetap dibuat tetapi tidak terlihat, dan pemutakhiran menggantung menunggu jawaban yang
    tidak pernah datang. Cakupannya dibaca dari tempat pemasangan sebelumnya terdaftar supaya
    pemutakhiran tetap di tempat yang sama dengan sebelumnya.
    """
    kunci = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{appid or APPID}_is1"
    for akar, bendera in ((winreg.HKEY_CURRENT_USER, "/CURRENTUSER"),
                          (winreg.HKEY_LOCAL_MACHINE, "/ALLUSERS")):
        try:
            winreg.CloseKey(winreg.OpenKey(akar, kunci))
            return bendera
        except OSError:
            continue
    return None


def jalankan_installer(f: Path, senyap=True, jalankan_lagi=True, appid=None):
    """Jalankan installer lalu minta aplikasi ditutup; pemasangan tidak dapat menimpa berkas yang terpakai.

    Senyap secara bawaan: untuk pemutakhiran semua jawaban wizard sudah diketahui (folder dari pemasangan
    sebelumnya, tugas dari pilihan dulu), jadi pengguna tidak perlu menjawabnya lagi. /SUPPRESSMSGBOXES
    sengaja tidak dipakai — bila pemasangan gagal, sebabnya harus terlihat.
    """
    if not f.exists():
        raise GalatUnduh("Berkas installer tidak ditemukan.")
    arg = [str(f)]
    if senyap:
        arg += ["/SILENT", "/NORESTART"]
        cakupan = cakupan_pemasangan(appid)
        if cakupan:
            arg.append(cakupan)
        if jalankan_lagi:
            arg.append("/JALANKANLAGI=1")     # dibaca [Run] di installer/virmolab.iss
    try:
        subprocess.Popen(arg, close_fds=True,
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    except OSError as e:
        raise GalatUnduh(f"Installer tidak dapat dijalankan: {e}") from e


def dapat_dipasang() -> bool:
    """Versi portable tidak punya installer: berkasnya diganti dengan menimpa foldernya sendiri."""
    return not paths.PORTABLE and sys.platform == "win32"
