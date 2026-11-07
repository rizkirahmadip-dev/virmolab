# -*- coding: utf-8 -*-
"""Uji pemutakhiran installer: versi baru harus mendarat di folder tempat pengguna memasang versi lama.

Tidak ikut regresi otomatis (ada di LEWATI dev/regresi.py): uji ini memasang dan mencopot perangkat lunak
sungguhan lewat Inno Setup. Jalankan sebelum rilis, atau sesudah menyentuh installer/virmolab.iss:

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_pemutakhiran_installer.py

Yang dijaga: pengguna yang memasang VirmoLab di folder pilihannya sendiri — bukan folder bawaan — tetap
mendapat SATU salinan saat memutakhirkan. Dengan UsePreviousAppDir=no, versi baru mendarat di
{autopf}\\VirmoLab, versi lama ditinggalkan utuh, dan entri uninstall ikut pindah ke folder baru sehingga
folder lama tidak lagi dapat dibuang lewat Apps & features. Sisa setengah gigabita yang tidak terlihat.
Uji ini menjalankan kedua perilaku: yang lama harus menghasilkan dua salinan (bukti bugnya nyata), yang
sekarang harus menghasilkan satu.

Skrip .iss sungguhan dipakai apa adanya; hanya AppId dan sumber berkas yang diganti, supaya pemasangan
VirmoLab milik pengembang tidak tersentuh dan muatan 1,8 GB tidak perlu disalin empat kali.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import time
import winreg
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
ISCC = AKAR / "vendor" / "innosetup" / "ISCC.exe"
APPID = "{A1B2C3D4-0000-4444-8888-99AA00BB11CC}"
KUNCI = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APPID}_is1"

gagal = []


def cek(ok, pesan):
    print(("OK    " if ok else "GAGAL ") + pesan, flush=True)
    if not ok:
        gagal.append(pesan)


def skrip(kerja: Path, versi: str, perilaku_lama: bool) -> Path:
    s = (AKAR / "installer" / "virmolab.iss").read_bytes().decode("utf-8").replace("\r\n", "\n")
    ganti = [
        ("AppId={{6E3B2A51-8C1D-4E7F-9A42-5B0D7C9E1F38}", "AppId={{" + APPID[1:]),
        ('Source: "{#Akar}\\dist\\VirmoLab\\*"', 'Source: "muatan\\*"'),
        ("Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"
         "{6E3B2A51-8C1D-4E7F-9A42-5B0D7C9E1F38}_is1", KUNCI),
        ("SetupIconFile={#Akar}\\virmolab\\aset\\virmolab.ico", ""),
        ("OutputDir={#Akar}\\rilis", f"OutputDir={kerja}"),
    ]
    # Entri [Run] yang membuka aplikasi lagi diarahkan ke penanda berkas: muatan uji bukan program
    # sungguhan, sedangkan yang perlu diuji adalah Check-nya — kapan entri itu berjalan, bukan apa yang
    # dijalankannya. Flags dan Check dibiarkan persis seperti aslinya.
    ganti.append(('Filename: "{app}\\VirmoLab.exe"; Flags: nowait runasoriginaluser; '
                  'Check: MintaJalankanLagi',
                  'Filename: "{cmd}"; Parameters: "/c echo ya > ""{app}\\dijalankan_lagi.txt"""; '
                  'Flags: runasoriginaluser; Check: MintaJalankanLagi'))
    for a, b in ganti:
        assert s.count(a) == 1, f"pola tidak cocok lagi di virmolab.iss: {a[:60]!r}"
        s = s.replace(a, b)
    if perilaku_lama:
        s, n = re.subn(r"^UsePreviousAppDir=yes$", "UsePreviousAppDir=no", s, flags=re.M)
        assert n == 1, "UsePreviousAppDir=yes tidak ditemukan di virmolab.iss"
    sisa = [b for b in s.splitlines() if "{#Akar}" in b and not b.startswith("#define")]
    assert not sisa, f"rujukan {{#Akar}} tertinggal dan arahnya salah di folder kerja: {sisa}"
    f = kerja / f"uji_{versi}{'_lama' if perilaku_lama else ''}.iss"
    f.write_text(s.replace("\n", "\r\n"), encoding="utf-8")
    return f


def bangun(kerja: Path, versi: str, perilaku_lama: bool, tanda: str) -> Path:
    for n in ("Indonesian.isl", "wizard_besar_1x.bmp", "wizard_besar_2x.bmp",
              "wizard_kecil_1x.bmp", "wizard_kecil_2x.bmp"):
        shutil.copy2(AKAR / "installer" / n, kerja / n)
    m = kerja / "muatan"
    shutil.rmtree(m, ignore_errors=True)
    (m / "_internal").mkdir(parents=True)
    (m / "VirmoLab.exe").write_text(tanda, encoding="utf-8")
    (m / "_internal" / "penanda.txt").write_text(tanda, encoding="utf-8")
    f = skrip(kerja, versi, perilaku_lama)
    r = subprocess.run([str(ISCC), f"/DVersi={versi}", str(f)], capture_output=True, text=True, cwd=kerja)
    assert "Successful compile" in r.stdout, (r.stdout[-1500:] + r.stderr[-800:])
    keluar = kerja / f"VirmoLab-Setup-{versi}.exe"
    akhir = kerja / f"{keluar.stem}{'-lama' if perilaku_lama else ''}.exe"
    keluar.replace(akhir)
    return akhir


def pasang(exe: Path, tujuan: Path | None = None):
    arg = [str(exe), "/SILENT", "/CURRENTUSER", "/SUPPRESSMSGBOXES", "/NORESTART"]
    if tujuan:
        arg.append(f"/DIR={tujuan}")
    subprocess.run(arg, check=True, timeout=900)


def pasang_seperti_aplikasi(exe: Path):
    """Jalankan installer persis seperti tombol Unduh dan pasang melakukannya.

    Benderanya dibangun oleh unduh_pembaruan.jalankan_installer, bukan ditulis ulang di sini: kalau
    daftarnya berubah dan salah, uji ini yang harus ikut merah — bukan lulus karena memakai salinan
    bendera yang sudah usang.
    """
    sys.path.insert(0, str(AKAR))
    from virmolab.core import unduh_pembaruan as U
    cakupan = U.cakupan_pemasangan(APPID)
    assert cakupan == "/CURRENTUSER", f"cakupan pemasangan uji tidak terbaca: {cakupan}"
    U.jalankan_installer(exe, appid=APPID)
    # jalankan_installer sengaja tidak menunggu: aplikasi sungguhan menutup dirinya lebih dulu.
    batas = time.time() + 900
    while time.time() < batas:
        if not [x for x in subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {exe.name}"],
                                          capture_output=True, text=True).stdout.splitlines()
                if exe.name.lower() in x.lower()]:
            break
        time.sleep(1)
    else:
        raise AssertionError("pemasangan senyap tidak selesai dalam 15 menit (kemungkinan menunggu dialog)")
    time.sleep(3)       # entri [Run] berjalan sesudah berkas tersalin


def terdaftar():
    for akar in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(akar, KUNCI) as k:
                return str(winreg.QueryValueEx(k, "Inno Setup: App Path")[0]).rstrip("\\")
        except OSError:
            continue
    return None


def tanda(folder: Path):
    f = folder / "VirmoLab.exe"
    return f.read_text(encoding="utf-8").strip() if f.exists() else None


def copot(*folder):
    for d in folder:
        u = d / "unins000.exe"
        if u.exists():
            subprocess.run([str(u), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=900)
        shutil.rmtree(d, ignore_errors=True)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, KUNCI)
    except OSError:
        pass


def main():
    import os
    bawaan = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "VirmoLab"
    assert terdaftar() is None, (f"AppId uji {APPID} sudah terdaftar; copot sisa uji sebelumnya dulu. "
                                 "Pemasangan VirmoLab sungguhan memakai AppId lain dan tidak tersentuh.")
    with tempfile.TemporaryDirectory(prefix="vm_upd_") as tmp:
        kerja = Path(tmp)
        pilihan = kerja / "FolderPilihanPengguna"       # folder tujuan di luar lokasi bawaan
        v_lama = bangun(kerja, "1.0.0", True, "versi lama")
        pemutakhir = {"perilaku lama (UsePreviousAppDir=no)": bangun(kerja, "1.0.1", True, "versi baru"),
                      "skrip installer saat ini": bangun(kerja, "1.0.1", False, "versi baru")}

        for label, exe in pemutakhir.items():
            satu_salinan = "saat ini" in label
            print(f"\n--- {label} ---", flush=True)
            copot(pilihan, bawaan)
            pasang(v_lama, pilihan)
            cek(tanda(pilihan) == "versi lama", "versi lama terpasang di folder pilihan pengguna")
            cek(terdaftar() == str(pilihan), "entri uninstall menunjuk folder pilihan pengguna")

            pasang(exe)                 # tanpa /DIR: persis seperti pembaruan dari dalam aplikasi
            di_pilihan, di_bawaan = tanda(pilihan), tanda(bawaan)
            print(f"  folder pengguna : {di_pilihan}\n  folder bawaan   : {di_bawaan}\n"
                  f"  terdaftar di    : {terdaftar()}", flush=True)
            if satu_salinan:
                cek(di_pilihan == "versi baru", "pemutakhiran mendarat di folder pengguna")
                cek(di_bawaan is None, "tidak ada salinan kedua di folder bawaan")
                cek(terdaftar() == str(pilihan), "entri uninstall tetap menunjuk folder pengguna")
                cek((pilihan / "_internal" / "penanda.txt").read_text(encoding="utf-8").strip() == "versi baru",
                    "isi _internal diganti, bukan bercampur dengan versi lama")
            else:
                cek(di_pilihan == "versi lama" and di_bawaan == "versi baru",
                    "perilaku lama memang menghasilkan dua salinan (bug yang diperbaiki)")
            copot(pilihan, bawaan)
            cek(not pilihan.exists() and not bawaan.exists(), "pemasangan uji terhapus bersih")

        # --- pemutakhiran senyap: persis jalur tombol Unduh dan pasang ---------------------------
        print("\n--- pemutakhiran senyap dari dalam aplikasi ---", flush=True)
        copot(pilihan, bawaan)
        pasang(v_lama, pilihan)
        penanda = pilihan / "dijalankan_lagi.txt"
        cek(not penanda.exists(), "pemasangan biasa tidak menjalankan entri /JALANKANLAGI")

        pasang_seperti_aplikasi(pemutakhir["skrip installer saat ini"])
        cek(tanda(pilihan) == "versi baru", f"pemasangan senyap selesai tanpa satu klik pun ({tanda(pilihan)})")
        cek(terdaftar() == str(pilihan), "pemutakhiran senyap tetap di folder pengguna")
        cek(penanda.exists(), "aplikasi dijalankan lagi sendiri sesudah pemasangan senyap")
        copot(pilihan, bawaan)
        cek(not pilihan.exists(), "pemasangan uji terhapus bersih")

    print(("\nGAGAL " if gagal else "\nLULUS ") + str(len(gagal)), flush=True)
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
