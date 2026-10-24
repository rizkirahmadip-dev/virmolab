"""Uji ringkasan konservasi residu kantong (core/konservasi.ringkas_kantong) pada 1HSG nyata.

Homolog uji dibuat dari sekuens rantai A dengan mutasi yang diketahui: tiga residu kantong (Asp25, Gly48, Ile50)
dan dua residu jauh dari MK1 (Gln2, Lys70). Ringkasan harus menurunkan identitas kantong, menyebut tepat residu
kantong yang dimutasi, dan tidak memasukkan residu jauh ke kantong.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_konservasi_kantong.py [--gui]
--gui: jalur tombol nyata. 1HSG diimpor, MK1 dipilih, homolog bermutasi ditempel di Penelitian lanjutan ›
Konservasi residu, tombol "Hitung & warnai B-faktor" diklik; keluaran harus memuat ringkasan kantong.
"""
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))
from virmolab.core import konservasi as K                           # noqa: E402

gagal = []


def cek(ok, pesan):
    print(("OK    " if ok else "GAGAL ") + pesan)
    if not ok:
        gagal.append(pesan)


pdb = (AKAR / "dev" / "uji" / "1HSG.pdb").read_text(encoding="utf-8", errors="replace")
mk1 = "\n".join(b for b in pdb.splitlines() if b.startswith("HETATM") and b[17:20] == "MK1")
xyz = K.koordinat_ligan(mk1)
cek(len(xyz) == 45, f"MK1: 45 atom berat ({len(xyz)})")

urut = K.sekuens_rantai(pdb, "A")
query = "".join(aa for _, aa, _, _ in urut)
nomor = [int(r[3]) for r in urut]
homolog = list(query)
mutasi = {25: "N", 48: "A", 50: "V", 2: "E", 70: "R"}
for resi, aa in mutasi.items():
    homolog[nomor.index(resi)] = aa
homolog = "".join(homolog)
skor = K.skor(query, [query, homolog])          # dua homolog: satu identik, satu bermutasi -> 50 % di posisi mutasi

r = K.ringkas_kantong(pdb, "A", skor, xyz)
label = {x[0]: x[2] for x in r["residu"]}
cek(10 <= r["n"] <= 25, f"kantong rantai A ≤ 5 Å dari MK1: {r['n']} residu")
cek(all(k in label for k in ("ASP25", "GLY48", "ILE50")), "Asp25, Gly48, Ile50 masuk kantong")
cek("GLN2" not in label and "LYS70" not in label, "residu jauh (Gln2, Lys70) tidak masuk kantong")
cek(abs(label["ASP25"] - 0.5) < 1e-9 and abs(label["ILE50"] - 0.5) < 1e-9, "identitas posisi mutasi kantong = 50 %")
cek({x[0] for x in r["residu"][:3]} == {"ASP25", "GLY48", "ILE50"}, "tiga terbawah = residu kantong yang dimutasi")
harap_kantong = 1 - 1.5 / r["n"]
cek(abs(r["rata_kantong"] - harap_kantong) < 1e-9, f"rata-rata kantong {r['rata_kantong']:.3f} = 1 − 1,5/n")
cek(r["rata_rantai"] > r["rata_kantong"], f"rantai {r['rata_rantai']:.3f} > kantong {r['rata_kantong']:.3f}")
cek(K.ringkas_kantong(pdb, "A", skor, []) is None, "tanpa ligan -> None")
cek(K.ringkas_kantong(pdb, "A", skor, [(500.0, 500.0, 500.0)]) is None, "ligan jauh dari protein -> None")
sdf = "x\n  RDKit\n\n  2  1  0  0  0  0  0  0  0  0999 V2000\n    1.0000    2.0000    3.0000 C   0  0\n" \
      "    1.5000    2.0000    3.0000 H   0  0\n  1  2  1  0\nM  END\n"
cek(K.koordinat_ligan(sdf) == [(1.0, 2.0, 3.0)], "koordinat dari blok MOL, H dibuang")
if "--gui" not in sys.argv:
    print("\nLULUS" if not gagal else f"\nGAGAL {len(gagal)}")
    sys.exit(1 if gagal else 0)

# ===================================================================== jalur tombol (--gui)
import os                                                           # noqa: E402
import shutil                                                       # noqa: E402
from PySide6.QtCore import QSettings, QTimer                       # noqa: E402

sys.argv = [sys.argv[0]]
KERJA = AKAR / "dev" / "uji" / "kerja_konservasi"
shutil.rmtree(KERJA, ignore_errors=True)
KERJA.mkdir(parents=True)
st = QSettings("VirmoLab", "VirmoLab")
st.setValue("wizard_selesai", True)
st.setValue("tema", "terang")
st.setValue("folder_kerja", str(KERJA))
st.remove("layout")
st.remove("sesi_terbuka")
import virmolab.app as A                                            # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton             # noqa: E402


def hook():
    from virmolab.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1500, 920)
            QTimer.singleShot(2000, s.l1)
            QTimer.singleShot(90000, lambda: (cek(False, "TIMEOUT"), s.akhir()))

        def l1(s):
            s.impor([str(AKAR / "dev" / "uji" / "1HSG.pdb")])
            QTimer.singleShot(2500, s.l2)

        def l2(s):
            asli = next(o for o in s.objek.values() if o.info.get("ligan_asli"))
            s.aktif = asli.id
            s.buka_penelitian()
            d = next(w for w in QApplication.topLevelWidgets() if w.windowTitle() == "Penelitian lanjutan")
            d.e_rantai.setText("A")
            d.e_fasta.setPlainText(f">identik\n{query}\n>mutan\n{homolog}\n")
            next(b for b in d.findChildren(QPushButton) if b.text() == "Hitung & warnai B-faktor").click()
            QApplication.processEvents()
            teks = d.keluar.toPlainText()
            print(teks, flush=True)
            cek("Kantong (16 residu" in teks and asli.nama in teks, f"ringkasan kantong 16 residu dari {asli.nama}")
            # Dialog membuang entri FASTA pertama yang identik dengan sekuens rantai (dianggap kueri), jadi hanya
            # homolog mutan yang dihitung: posisi termutasi 0 %, rata-rata kantong 1 - 3/16 = 81 %.
            cek("ASP25 0%, GLY48 0%, ILE50 0%" in teks, "tiga residu kantong termutasi teratas, 0 %")
            cek("identitas rata-rata 81%" in teks, "rata-rata identitas kantong 81 %")
            d.grab().save(str(KERJA / "konservasi_kantong.png"))
            s.akhir()

        def akhir(s):
            print("\nLULUS" if not gagal else f"\nGAGAL {len(gagal)}: " + "; ".join(gagal), flush=True)
            QApplication.quit()
            os._exit(1 if gagal else 0)

    mainwindow.JendelaUtama = Uji
    A.main()


hook()
