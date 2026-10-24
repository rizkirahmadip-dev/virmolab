"""Uji RBFE OpenFE (F9 lanjutan): pembacaan hasil quickrun, ΔΔG tepi, MLE jaringan, dan dialognya.

Hasil nyata dipakai bila ada: uji pemasangan TYK2 (tepi lig_ejm_31 -> lig_ejm_43, protokol uji cepat) di
~/virmolab-alat/uji_rbfe. Bila berkas itu tidak ada, bagian itu dilewati dan sisanya tetap diuji.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_rbfe_openfe.py
Keluaran gambar: dev/uji/rbfe/dialog_{terang,gelap}.png
"""
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))
sys.argv = [sys.argv[0]]

from PySide6.QtWidgets import QApplication, QWidget          # noqa: E402

from virmolab.core import rbfe_openfe as R                   # noqa: E402
from virmolab.ui import theme                                # noqa: E402

KELUAR = AKAR / "dev" / "uji" / "rbfe"
# Ki eksperimen TYK2 (Liang dkk., Eur J Med Chem 2013;67:175-187), lewat set tolok ukur OpenFE
KI_UM = {"lig_ejm_31": 0.096, "lig_ejm_43": 0.84}
gagal = []


def tunggu(app, syarat, detik=60):
    """Proses event sampai syarat() benar (pekerjaan latar dialog) atau waktu habis."""
    import time
    batas = time.time() + detik
    while time.time() < batas:
        app.processEvents()
        if syarat():
            return True
        time.sleep(0.05)
    return False


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


def ambil_hasil_wsl(tujuan):
    """Salin hasil_solvent.json / hasil_complex.json dari WSL (bila uji pemasangan pernah dijalankan)."""
    try:
        p = subprocess.run(["wsl", "-e", "bash", "-lc", "ls ~/virmolab-alat/uji_rbfe/hasil_*.json"],
                           capture_output=True, text=True, timeout=60)
    except Exception as e:
        print("LEWAT: WSL tidak bisa dipanggil:", e)
        return None
    berkas = [b.strip() for b in (p.stdout or "").splitlines() if b.strip().endswith(".json")]
    if len(berkas) < 2:
        print("LEWAT: hasil uji pemasangan TYK2 tidak ada di WSL.")
        return None
    for b in berkas:
        nama = Path(b).name
        subprocess.run(["wsl", "-e", "bash", "-lc", f"cat {b}"], stdout=open(tujuan / nama, "wb"), timeout=300)
    return tujuan


def uji_hasil_nyata(folder):
    gk, ek, setel = R.baca_hasil_kaki(folder / "hasil_complex.json")
    gp, ep, _ = R.baca_hasil_kaki(folder / "hasil_solvent.json")
    cek(gk is not None and gp is not None, f"kedua kaki terbaca (kompleks {gk}, pelarut {gp})")
    ddg = gk - gp
    galat = math.hypot(ek or 0, ep or 0)
    exp = R.ddg_eksperimen(KI_UM["lig_ejm_31"], KI_UM["lig_ejm_43"])
    print(f"ΔΔG hitung {ddg:+.2f} ± {galat:.2f} kkal/mol; eksperimen {exp:+.2f}; selisih {ddg - exp:+.2f} "
          f"({abs(ddg - exp) / galat:.2f} σ)", flush=True)
    cek(abs(ddg - 2.281) < 0.01, f"ΔΔG tepi = +2,28 kkal/mol ({ddg:+.3f})")
    cek(0.3 < galat < 1.5, f"galat gabungan masuk akal ({galat:.2f} kkal/mol)")
    cek(abs(exp - 1.285) < 0.01, f"ΔΔG eksperimen dari Ki = +1,28 kkal/mol ({exp:+.3f})")
    cek((ddg - exp) * exp > 0 and abs(ddg - exp) < 2.0,
        f"arah perubahan benar dan selisih < 2 kkal/mol ({ddg - exp:+.2f})")
    cek(bool(setel), "pengaturan protokol ikut terbaca dari JSON")

    # jaringan 2 ligan: MLE harus mengembalikan ΔG relatif = ΔΔG tepi
    lig = R.mle([{"a": "lig_ejm_31", "b": "lig_ejm_43", "ddg": ddg, "galat": galat}],
                ["lig_ejm_31", "lig_ejm_43"])
    cek(abs(lig["lig_ejm_31"][0]) < 1e-9 and abs(lig["lig_ejm_43"][0] - ddg) < 1e-6,
        f"MLE jaringan 2 ligan konsisten ({lig})")
    # jaringan segitiga: siklus tertutup harus memberi ΔG relatif yang konsisten
    tiga = R.mle([{"a": "A", "b": "B", "ddg": 1.0, "galat": 0.2},
                  {"a": "B", "b": "C", "ddg": 0.5, "galat": 0.2},
                  {"a": "A", "b": "C", "ddg": 1.6, "galat": 0.2}], ["A", "B", "C"])
    cek(abs(tiga["A"][0]) < 1e-9 and abs(tiga["B"][0] - 1.03) < 0.05 and abs(tiga["C"][0] - 1.57) < 0.05,
        f"MLE segitiga menyeimbangkan siklus ({ {k: round(v[0], 2) for k, v in tiga.items()} })")


def uji_paragraf_metode(h):
    """Paragraf metode setelah run nyata memuat yang benar-benar dijalankan (dibaca dari JSON), bukan rencana."""
    idn, ing = R.paragraf_metode(h, en=False), R.paragraf_metode(h, en=True)
    print("PARAGRAF (ID):", idn, flush=True)
    for butir in ("OpenFE 1.13.0", "OpenMM 8.4", "CUDA", "Amber ff14SB", "TIP3P", "openff-2.2.1", "NAGL",
                  "11 jendela lambda", "298,15 K", "dodecahedron", "0,1 ns ekuilibrasi", "0,5 ns produksi",
                  "ΔG(kompleks) − ΔG(pelarut)", "Eksperimental"):
        cek(butir in idn, f"paragraf ID memuat '{butir}'")
    for butir in ("OpenFE 1.13.0", "0.5 ns of production", "298.15 K", "Experimental"):
        cek(butir in ing, f"paragraf EN memuat '{butir}'")
    cek("direncanakan" not in idn and "Planned" not in ing, "paragraf run tidak berbunyi 'direncanakan'")
    kosong = R.paragraf_metode({"tepi": [{"ddg": None}], "setel": {}, "versi": {}}, en=False)
    cek(kosong == "", "tanpa tepi selesai paragraf kosong, bukan paragraf separuh jadi")
    rusak = dict(h, setel={"forcefield_settings": {}})
    cek(R.paragraf_metode(rusak, en=False) == "" or "None" not in R.paragraf_metode(rusak, en=False),
        "pengaturan tidak lengkap tidak menghasilkan kata 'None' di naskah")


def uji_kumpulkan_palsu():
    """kumpulkan() membaca struktur folder run; dibuat dari hasil nyata dengan nama berkas yang dipakai VirmoLab."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        sumber = ambil_hasil_wsl(tmp)
        if sumber is None:
            return
        run = tmp / "run"
        (run / "hasil").mkdir(parents=True)
        (run / "run.json").write_text(json.dumps({
            "tepi": [["lig_ejm_31", "lig_ejm_43"]],
            "peta_nama": {"lig_ejm_31": "lig_ejm_31", "lig_ejm_43": "lig_ejm_43"}}), encoding="utf-8")
        shutil.copy(sumber / "hasil_complex.json", run / "hasil" / "lig_ejm_31__lig_ejm_43__kompleks.json")
        shutil.copy(sumber / "hasil_solvent.json", run / "hasil" / "lig_ejm_31__lig_ejm_43__pelarut.json")
        h = R.kumpulkan(run)
        t = h["tepi"][0]
        cek(t["ddg"] is not None and abs(t["ddg"] - 2.281) < 0.01, f"kumpulkan(): ΔΔG tepi {t['ddg']:.3f}")
        cek(abs(h["ligan"]["lig_ejm_43"][0] - t["ddg"]) < 1e-6, "kumpulkan(): ΔG relatif ligan dari MLE")
        cek(h["versi"].get("openfe") == "1.13.0" and h["versi"].get("openmm") == "8.4",
            f"kumpulkan(): versi perangkat lunak dibaca dari JSON hasil ({h['versi']})")
        uji_paragraf_metode(h)
        uji_hasil_nyata(sumber)


TYK2 = {
    "lig_ejm_31": "[H]c1c(c(c(c(c1[H])Cl)C(=O)N([H])c2c(c(nc(c2[H])N([H])C(=O)C([H])([H])[H])[H])[H])Cl)[H]",
    "lig_ejm_42": "[H]c1c(c(c(c(c1[H])Cl)C(=O)N([H])c2c(c(nc(c2[H])N([H])C(=O)C([H])([H])C([H])([H])[H])[H])[H])Cl)[H]",
    "lig_ejm_43": "[H]c1c(c(c(c(c1[H])Cl)C(=O)N([H])c2c(c(nc(c2[H])N([H])C(=O)C([H])(C([H])([H])[H])C([H])([H])[H])"
                  "[H])[H])Cl)[H]",
}


class JendelaPalsu(QWidget):
    """Jendela utama tiruan: dialog RBFE hanya memerlukan daftar ligan proyek dan pose aktif."""
    proyek = None
    objek = {}
    _aktif_inter = None

    def _sumber_sifat(self):
        from rdkit import Chem
        hasil = []
        for i, (nama, smi) in enumerate(TYK2.items(), 1):
            m = Chem.AddHs(Chem.MolFromSmiles(smi))
            from rdkit.Chem import AllChem
            AllChem.EmbedMolecule(m, randomSeed=42)
            hasil.append((f"lig{i}", nama, Chem.MolToMolBlock(m), "sdf", None))
        return hasil


def uji_dialog():
    from virmolab.ui.dialog_rbfe import DialogRbfe
    KELUAR.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    for tema in ("terang", "gelap"):
        app.setPalette(theme.palet(tema))
        app.setStyleSheet(theme.qss(tema))
        d = DialogRbfe(JendelaPalsu())
        d.resize(1120, 700)
        d.show()
        for _ in range(12):
            app.processEvents()
        cek(d.cb_protokol.count() >= 2, f"preset protokol tersedia ({tema})")
        cek(d.daftar.count() == 3, f"3 ligan TYK2 terbaca dari jendela utama ({tema}, {d.daftar.count()})")
        d._centang(True)
        d._susun()
        tunggu(app, lambda: d.tabel.rowCount() > 0, 90)
        cek(d.tabel.rowCount() >= 2, f"jaringan perturbasi tersusun ({tema}, {d.tabel.rowCount()} tepi)")
        d.cb_protokol.setCurrentIndex(1)       # uji cepat
        tunggu(app, lambda: "ns simulasi" in d.l_beban.text(), 10)
        cek("hari" in d.l_beban.text() or "ns simulasi" in d.l_beban.text(),
            f"perkiraan beban simulasi tampil ({tema}): {d.l_beban.text()[:110]}")
        p = KELUAR / f"dialog_{tema}.png"
        d.grab().save(str(p))
        cek(p.exists() and p.stat().st_size > 5000, f"tangkapan layar {tema}")
        d.close()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    st = R.status()
    print("status OpenFE di WSL:", st["ada"], st.get("versi", ""), flush=True)
    uji_kumpulkan_palsu()
    uji_dialog()
    print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
    sys.exit(1 if gagal else 0)


if __name__ == "__main__":
    main()
