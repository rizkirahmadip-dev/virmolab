"""Uji ujung-ke-ujung simulasi RBFE lewat dialog: Jalankan -> WSL -> OpenFE -> hasil terbaca di tabel.

Berbeda dari dev/uji_rbfe_openfe.py (membaca hasil yang sudah ada), uji ini benar-benar menjalankan jalur
siapkan_run -> jalankan.sh -> `openfe quickrun` -> penyalinan hasil -> kumpulkan() -> tabel dialog, dengan jalur
proyek berspasi (E:\\Bikin Docking Simpel\\...) seperti komputer pengguna.

Protokol sengaja super singkat (11 jendela, ekuilibrasi 0,02 ns, produksi 0,05 ns, 1 repeat): yang dibuktikan
hanya alurnya, angka ΔΔG-nya tidak bermakna. ±20-30 menit di RTX 3060 Laptop. Butuh OpenFE di WSL dan set TYK2
di ~/virmolab-alat/uji_rbfe (tyk2_ligands.sdf, tyk2_protein.pdb); tanpa itu uji dilewati.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_rbfe_jalan.py
Keluaran: dev/uji/rbfe_jalan/ (proyek tiruan, tangkapan layar)
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))
sys.argv = [sys.argv[0]]

from PySide6.QtGui import QGuiApplication                    # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget          # noqa: E402
from rdkit import Chem, RDLogger                             # noqa: E402

from virmolab.core import rbfe_openfe                        # noqa: E402
from virmolab.ui import kit, theme                           # noqa: E402
from virmolab.ui.dialog_rbfe import DialogRbfe               # noqa: E402

RDLogger.DisableLog("rdApp.*")
KERJA = AKAR / "dev" / "uji" / "rbfe_jalan"
PILIH = ("lig_ejm_31", "lig_ejm_43")
BATAS_MENIT = 75
gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


def dari_wsl(jalur):
    p = subprocess.run(["wsl", "-e", "bash", "-lc", f"cat {jalur}"], capture_output=True, timeout=120)
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else ""


class ProyekPalsu:
    """Hanya yang dipakai dialog: folder proyek dan p()."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.reseptor = None
        self.job = []
        self.ligan = []

    def p(self, *bag):
        return self.folder.joinpath(*bag)


class JendelaPalsu(QWidget):
    objek = {}
    _aktif_inter = None

    def __init__(self, proyek):
        super().__init__()
        self.proyek = proyek


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    st = rbfe_openfe.status(segar=True)
    if not st["ada"]:
        print("LEWAT: OpenFE belum terpasang di WSL.")
        return
    sdf = dari_wsl("~/virmolab-alat/uji_rbfe/tyk2_ligands.sdf")
    pdb = dari_wsl("~/virmolab-alat/uji_rbfe/tyk2_protein.pdb")
    if not sdf or not pdb:
        print("LEWAT: set TYK2 tidak ada di ~/virmolab-alat/uji_rbfe.")
        return
    blok, smiles = {}, {}
    for b in sdf.split("$$$$"):
        b = b.lstrip("\r\n")
        nama = b.splitlines()[0].strip() if b.strip() else ""
        if nama in PILIH:
            blok[nama] = b.rstrip() + "\n"
            m = Chem.MolFromMolBlock(b, removeHs=False)
            smiles[nama] = Chem.MolToSmiles(Chem.RemoveHs(m))
    cek(set(blok) == set(PILIH), f"dua ligan TYK2 terbaca dari set tolok ukur ({sorted(blok)})")

    shutil.rmtree(KERJA, ignore_errors=True)
    KERJA.mkdir(parents=True)
    proyek = ProyekPalsu(KERJA / "proyek.vmd")
    proyek.folder.mkdir()

    # Bahan simulasi yang di aplikasi nyata datang dari hasil docking proyek; di sini dari set tolok ukur.
    kit.ligan_proyek = lambda jw, **k: [{"nama": n, "smiles": smiles[n], "baris": {"mb": blok[n]}} for n in PILIH]
    rbfe_openfe.pose_dari_baris = lambda pr, baris: baris["mb"]
    rbfe_openfe.reseptor_untuk_rbfe = lambda pr: (pdb, ["protein dari set tolok ukur TYK2"])
    asli = rbfe_openfe.siapkan_run

    def siapkan_singkat(folder, ligan, protein, tepi, **kw):
        kw.update(ns_produksi=0.05, ns_ekuilibrasi=0.02, repeat=1, jendela=11)     # hanya alurnya yang diuji
        return asli(folder, ligan, protein, tepi, **kw)
    rbfe_openfe.siapkan_run = siapkan_singkat

    app = QApplication.instance() or QApplication(sys.argv)
    app.setPalette(theme.palet("terang"))
    app.setStyleSheet(theme.qss("terang"))
    d = DialogRbfe(JendelaPalsu(proyek))
    d.resize(1120, 720)
    d.show()

    def tunggu(syarat, detik, label=""):
        batas = time.time() + detik
        terakhir = 0.0
        while time.time() < batas:
            app.processEvents()
            if syarat():
                return True
            if label and time.time() - terakhir > 60:
                terakhir = time.time()
                print(f"  … {label}: {d.l_sim.text()[:160]}", flush=True)
            time.sleep(0.1)
        return False

    tunggu(lambda: "siap di WSL" in d.l_mesin.text(), 60)
    cek("siap di WSL" in d.l_mesin.text(), f"dialog menyatakan OpenFE siap: {d.l_mesin.text()[:60]}")
    d._susun()
    tunggu(lambda: d.tabel.rowCount() > 0, 90)
    cek(d.tabel.rowCount() == 1, f"jaringan 1 tepi untuk 2 ligan ({d.tabel.rowCount()} baris)")
    cek(d.b_jalan.isEnabled(), "tombol Jalankan aktif setelah jaringan tersusun")

    t0 = time.time()
    d._jalankan()
    for _ in range(20):
        app.processEvents()
    folder_run = d._run
    cek(folder_run is not None and (folder_run / "jalankan.sh").exists(), f"siapkan_run menulis skrip: {folder_run}")
    cek((folder_run / "masukan" / "ligan.sdf").exists() and (folder_run / "masukan" / "protein.pdb").exists(),
        "berkas masukan (ligan, protein) tertulis")
    cek(b"\r\n" not in (folder_run / "jalankan.sh").read_bytes(), "jalankan.sh berakhir baris LF")
    cek("Simulasi dimulai" in d.l_sim.text(), f"dialog melaporkan simulasi dimulai: {d.l_sim.text()[:90]}")

    selesai = tunggu(lambda: "SEMUA_SELESAI" in ((folder_run / "jalan.log").read_text(encoding="utf-8", errors="replace")
                                                   if (folder_run / "jalan.log").exists() else ""),
                     BATAS_MENIT * 60, "simulasi")
    menit = (time.time() - t0) / 60
    log = (folder_run / "jalan.log").read_text(encoding="utf-8", errors="replace") if (folder_run / "jalan.log").exists() else ""
    print("---- jalan.log ----\n" + log[-900:] + "\n-------------------", flush=True)
    cek(selesai, f"semua kaki selesai dalam {menit:.1f} menit")
    hasil = sorted(p.name for p in (folder_run / "hasil").glob("*.json"))
    cek(any(h.endswith("__kompleks.json") for h in hasil) and any(h.endswith("__pelarut.json") for h in hasil),
        f"hasil kedua kaki tersalin ke folder proyek ({hasil})")
    cek("GAGAL" not in log, "log run tanpa penanda kegagalan")  # teks cek tanpa kata itu: runner regresi mencarinya

    # dialog membaca hasilnya sendiri lewat timer pantau; beri kesempatan, lalu paksa bila perlu
    tunggu(lambda: d._hasil_openfe is not None if hasattr(d, "_hasil_openfe") else False, 60)
    if not getattr(d, "_hasil_openfe", None):
        d._muat_hasil()
        for _ in range(10):
            app.processEvents()
    h = getattr(d, "_hasil_openfe", None)
    cek(bool(h) and len(h["tepi"]) == 1 and h["tepi"][0]["ddg"] is not None,
        f"ΔΔG tepi terbaca: {h['tepi'][0]['ddg'] if h else None}")
    teks_ddg = d.tabel.item(0, 3).text() if d.tabel.rowCount() else ""
    cek(teks_ddg not in ("", "–"), f"kolom ΔΔG tabel terisi ({teks_ddg})")
    cek(d.tabel_ligan.rowCount() == 2, f"tab ΔG relatif per ligan berisi 2 ligan ({d.tabel_ligan.rowCount()})")
    cek(d.tabel.item(0, 5).text() == "OpenFE", "catatan baris menandai asal angka: OpenFE")

    # paragraf metode setelah simulasi nyata harus memuat perangkat lunak dan protokol yang sebenarnya dipakai
    d._salin_metode()
    teks = QGuiApplication.clipboard().text()
    print("PARAGRAF METODE:", teks, flush=True)
    cek("OpenFE" in teks and "1.13" in teks, "paragraf metode menyebut OpenFE dan versinya")
    cek("openff-2.2.1" in teks and "NAGL" in teks and "ff14SB" in teks, "paragraf metode menyebut medan gaya dan muatan")
    cek("0,05" in teks or "0.05" in teks, "paragraf metode memuat panjang produksi yang sebenarnya (0,05 ns), bukan rencana")
    cek("direncanakan" not in teks and "Planned" not in teks, "paragraf metode tidak lagi berbunyi 'direncanakan'")

    d.grab().save(str(KERJA / "dialog_setelah_run.png"))
    d.close()
    # bersihkan berkas simulasi di WSL (ratusan MB)
    info = rbfe_openfe_info(folder_run)
    if info:
        subprocess.run(["wsl", "-e", "bash", "-lc", f"rm -rf {info}"], capture_output=True, timeout=120)
    print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
    sys.exit(1 if gagal else 0)


def rbfe_openfe_info(folder_run):
    import json
    try:
        return json.loads((folder_run / "run.json").read_text(encoding="utf-8"))["kerja_wsl"]
    except Exception:
        return ""


if __name__ == "__main__":
    main()
