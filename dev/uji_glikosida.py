"""Uji fitur Glikosida dan aglikon (core/glikosida.py, ui/dialog_glikosida.py).

Bagian 1 (selalu, ±2 s): deglikosilasi 26 molekul rujukan PubChem (dev/data/glikosida_pubchem.tsv) — aglikon harus
sama dengan entri PubChem aglikonnya (kunci InChI), C-glikosida dan tanin tidak dipotong, sukrosa dikenali sebagai
gula seluruhnya — serta angka LE/FQ.
Bagian 2 (--gui, ±1 menit): alur nyata di jendela VirmoLab. 1HSG diimpor dan disiapkan, kosmosiin dan arbutin
ditambahkan sebagai ligan, dialog dibuka lewat handler menunya, tombol "Tambahkan aglikon" diklik, keempat ligan
didocking dengan Vina (exhaustiveness 4) pada kotak yang sama, lalu tabel perbandingan harus berisi dua pasangan
dengan ΔG nyata dari job itu. Tangkapan dialog terang dan gelap disimpan.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_glikosida.py [--gui [--en]]
Keluaran gambar: dev/uji/glikosida/
"""
import os
import shutil
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))
GUI = "--gui" in sys.argv
BAHASA = "en" if "--en" in sys.argv else "id"      # --en: dialog berbahasa Inggris
sys.argv = [sys.argv[0]]
OUT = AKAR / "dev" / "uji" / "glikosida"
gagal = []


def cek(ok, pesan):
    print(("OK    " if ok else "GAGAL ") + pesan, flush=True)
    if not ok:
        gagal.append(pesan)


# ===================================================================== bagian 1: inti
from rdkit import Chem, RDLogger                                    # noqa: E402
from virmolab.core import glikosida as G                            # noqa: E402

RDLogger.DisableLog("rdApp.*")
REF = {}
for baris in (AKAR / "dev" / "data" / "glikosida_pubchem.tsv").read_text(encoding="utf-8").splitlines():
    if baris and not baris.startswith("#"):
        nama, smi = baris.split("\t")
        REF[nama] = smi


def ik(smi):
    return Chem.MolToInchiKey(Chem.MolFromSmiles(smi))[:14]


# glikosida -> (aglikon PubChem, jumlah gula, jenis gula yang diharapkan)
PASANGAN = {
    "rutin": ("quercetin", 2, {"heksosa", "deoksiheksosa"}),
    "naringin": ("naringenin", 2, {"heksosa", "deoksiheksosa"}),
    "hesperidin": ("hesperetin", 2, {"heksosa", "deoksiheksosa"}),
    "quercitrin": ("quercetin", 1, {"deoksiheksosa"}),
    "cosmosiin": ("apigenin", 1, {"heksosa"}),
    "arbutin": ("hydroquinone", 1, {"heksosa"}),
    "amygdalin": ("mandelonitrile", 2, {"heksosa"}),
    "digitoxin": ("digitoxigenin", 3, {"dideoksiheksosa"}),
    "adenosine": ("adenine", 1, {"pentosa"}),
}
for g, (a, n, jenis) in PASANGAN.items():
    h = G.deglikosilasi(REF[g])
    cek(h.status == "ok" and h.smiles_aglikon and ik(h.smiles_aglikon) == ik(REF[a]),
        f"{g}: aglikon = {a} ({h.status}, {h.smiles_aglikon})")
    cek(len(h.gula) == n and {x.jenis for x in h.gula} == jenis, f"{g}: {G.ringkas_gula(h.gula)}")
    cek(h.atom_berat_aglikon == Chem.MolFromSmiles(REF[a]).GetNumHeavyAtoms(),
        f"{g}: atom berat aglikon {h.atom_berat_aglikon}")
    cek(len(h.atom_gula) == h.atom_berat - h.atom_berat_aglikon, f"{g}: atom gula tersorot = selisih atom berat")

cek(G.deglikosilasi(REF["adenosine"]).gula[0].ikatan == "N-glikosida", "adenosin: ikatan N-glikosida")
h = G.deglikosilasi(REF["ginsenoside Rb1"])
cek(h.status == "ok" and len(h.gula) == 4 and h.atom_berat_aglikon == 33,
    f"ginsenosida Rb1: 4 glukosa di dua posisi, aglikon protopanaksadiol 33 atom ({h.atom_berat_aglikon})")
for n in ("vitexin", "mangiferin"):
    h = G.deglikosilasi(REF[n])
    cek(h.status == "hanya_c" and h.n_c_glikosida == 1 and not h.smiles_aglikon, f"{n}: C-glikosida tidak dipotong")
h = G.deglikosilasi(REF["sucrose"])
cek(h.status == "gula_saja" and [x.jenis for x in h.gula] == ["heksosa", "heksosa"],
    f"sukrosa: seluruhnya gula, dua heksosa ({G.ringkas_gula(h.gula)})")
cek(G.deglikosilasi(REF["methyl beta-D-glucopyranoside"]).status == "aglikon_kecil", "metil glukosida: aglikon kecil")
cek(G.deglikosilasi(REF["1,2,3,4,6-pentagalloylglucose"]).status == "bukan",
    "pentagaloilglukosa: inti tanin, bukan glikosida")
for n in ("topiramate", "ibuprofen", "quercetin"):
    cek(G.deglikosilasi(REF[n]).status == "bukan", f"{n}: bukan glikosida")
cek(G.deglikosilasi("bukan-smiles").status == "gagal", "SMILES rusak -> gagal, tidak melempar")

# LE_scale (Reynolds dkk., 2007) dan logika perbandingan
cek(abs(G.le_scale(22) - 0.4332) < 1e-3 and abs(G.le_scale(43) - 0.2561) < 1e-3, "LE_scale 22 dan 43 atom berat")
le, fq = G.efisiensi(-9.0, 22)
cek(abs(le - 9 / 22) < 1e-9 and abs(fq - (9 / 22) / G.le_scale(22)) < 1e-9, "LE dan FQ")
cek(G.efisiensi(0.5, 22) == (None, None), "skor positif -> tanpa LE")
b = G.bandingkan(-10.0, 43, -8.5, 22)          # gula 21 atom menambah 1,5 kkal/mol: 0,071 per atom < LE aglikon 0,386
cek(b["kode"] == "ukuran" and abs(b["per_atom_gula"] - 1.5 / 21) < 1e-9 and b["aglikon_lebih_efisien"],
    f"glikosida unggul karena ukuran ({b['kesimpulan']})")
cek(G.bandingkan(-7.0, 43, -8.5, 22)["kode"] == "aglikon", "aglikon lebih kuat")
cek(G.bandingkan(-20.0, 43, -8.5, 22)["kode"] == "gula", "gula menyumbang melebihi LE aglikon")
print(f"\nBagian inti: {len(gagal)} gagal", flush=True)

if not GUI:
    print("LULUS" if not gagal else f"GAGAL {len(gagal)}")
    sys.exit(1 if gagal else 0)


# ===================================================================== bagian 2: alur GUI
from PySide6.QtCore import QSettings, QTimer                       # noqa: E402

KERJA = (AKAR / "dev" / "uji" / "kerja_glikosida").resolve()
shutil.rmtree(KERJA, ignore_errors=True)
KERJA.mkdir(parents=True)
OUT.mkdir(parents=True, exist_ok=True)
st = QSettings("VirmoLab", "VirmoLab")
st.setValue("wizard_selesai", True)
st.setValue("tema", "terang")
st.setValue("bahasa", BAHASA)
st.setValue("folder_kerja", str(KERJA))
st.remove("layout")
st.remove("sesi_terbuka")

import virmolab.app as A                                            # noqa: E402
from PySide6.QtWidgets import QApplication                          # noqa: E402


def hook():
    from virmolab.core import molekul, prep_ligan, prep_reseptor
    from virmolab.ui import kerja, mainwindow, theme
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1500, 920)
            s.d = None
            s.pelaksana.jobSelesai.connect(s._uji_job_selesai)
            QTimer.singleShot(2000, s.l1)
            QTimer.singleShot(240000, lambda: (cek(False, "TIMEOUT 240 s"), s.akhir()))

        def l1(s):
            s.impor([str(AKAR / "dev" / "uji" / "1HSG.pdb")])
            QTimer.singleShot(2500, s.l2)

        def l2(s):
            prot = next(o for o in s.objek.values() if o.jenis == "protein")
            opsi = prep_reseptor.OpsiReseptor()
            kerja.jalankan(prep_reseptor.siapkan, prot.teks, opsi,
                           selesai=lambda h: (s._reseptor_siap(prot, h, opsi), QTimer.singleShot(300, s.l3)),
                           galat=lambda g: (cek(False, f"reseptor: {g[:200]}"), s.akhir()))

        def l3(s):
            asal = [molekul.dari_smiles(REF[n], n)[0] for n in ("cosmosiin", "arbutin")]
            data = [(o.nama, o.teks, o.fmt) for o in asal]
            kerja.jalankan(prep_ligan.siapkan_banyak, data, prep_ligan.OpsiLigan(),
                           selesai=lambda h: (s._ligan_siap(list(zip(asal, h))), QTimer.singleShot(300, s.l4)),
                           galat=lambda g: (cek(False, f"ligan: {g[:200]}"), s.akhir()))

        def l4(s):
            s.d = s.buka_glikosida()
            cek(s.d is not None, "dialog dibuka lewat handler menu (buka_glikosida)")
            t = s.d.tabel_ligan
            cek(t.rowCount() == 2, f"2 glikosida dikenali ({t.rowCount()})")
            kolom_agl = {t.item(r, 0).text(): t.item(r, 3).text() for r in range(t.rowCount())}
            from virmolab import i18n
            cek(all(v == i18n.t("belum ada") for v in kolom_agl.values()), f"aglikon belum ada di proyek ({kolom_agl})")
            cek(s.d.b_tambah.isEnabled() and "(2)" in s.d.b_tambah.text(), f"tombol: {s.d.b_tambah.text()}")
            s.d.resize(1280, 820)
            QTimer.singleShot(600, lambda: s.d.grab().save(str(OUT / "dialog_awal.png")))
            n_awal = len(s.proyek.ligan)
            s.d.b_tambah.click()
            s._tunggu(lambda: len(s.proyek.ligan) == n_awal + 2, 60, s.l5, "aglikon masuk proyek")

        def l5(s):
            from virmolab import i18n
            ak = i18n.t("aglikon")
            nama = {l["nama"]: s.proyek.smiles_ligan(l) for l in s.proyek.ligan}
            cek(f"cosmosiin ({ak})" in nama and ik(nama[f"cosmosiin ({ak})"]) == ik(REF["apigenin"]),
                "aglikon kosmosiin di proyek = apigenin")
            cek(f"arbutin ({ak})" in nama and ik(nama[f"arbutin ({ak})"]) == ik(REF["hydroquinone"]),
                "aglikon arbutin di proyek = hidrokuinon")
            t = s.d.tabel_ligan
            kolom_agl = {t.item(r, 0).text(): t.item(r, 3).text() for r in range(t.rowCount())}
            cek(kolom_agl.get("cosmosiin") == f"cosmosiin ({ak})", f"tabel menautkan aglikon ({kolom_agl})")
            cek(not s.d.b_tambah.isEnabled(), "tombol Tambahkan mati setelah semua aglikon ada")
            s.aksi_kotak("ligan_asli")
            s.param.set_parameter({"mesin": "vina", "perangkat": "cpu", "exhaustiveness": 4})
            s._param_berubah(s.param.parameter())
            s.jalankan_docking()

        def _uji_job_selesai(s, jid):
            j = s.pelaksana.cari(jid)
            hasil = [(l["nama"], l["status"], l["energi"]) for l in j["ligan"]]
            print("JOB", jid, j["status"], hasil, flush=True)
            cek(all(st_ == "selesai" and e is not None for _n, st_, e in hasil), "keempat ligan selesai didocking")
            QTimer.singleShot(500, lambda: s.l6(j))

        def l6(s, j):
            s.d.b_muat.click()
            p = s.d._analisis["pasangan"]
            cek(len(p) == 2 and s.d.tabel_banding.rowCount() == 2, f"2 pasangan dibandingkan ({len(p)})")
            energi = {l["nama"]: l["energi"] for l in j["ligan"]}
            for x in p:
                cek(abs(x["dg_g"] - energi[x["nama_g"]]) < 1e-6 and abs(x["dg_a"] - energi[x["nama_a"]]) < 1e-6,
                    f"{x['nama_g']}: ΔG {x['dg_g']} vs aglikon {x['dg_a']} dari job {j['id']}; {x['kesimpulan']}")
                cek(x["le_g"] is not None and x["le_a"] is not None and x["fq_g"] is not None,
                    f"{x['nama_g']}: LE {x['le_g']:.3f}/{x['le_a']:.3f}, FQ {x['fq_g']:.2f}/{x['fq_a']:.2f}")
            cek(s.d.k_pasangan.l_nilai.text() == "2", f"kartu Perbandingan = {s.d.k_pasangan.l_nilai.text()}")
            s.d.b_metode.click()
            teks = QApplication.clipboard().text()
            cek("Hopkins" in teks and "Reynolds" in teks and "10.1186/s13321-020-00467-y" in teks
                and ("2 docking comparison" in teks if BAHASA == "en" else "2 perbandingan" in teks),
                "paragraf metode + pustaka disalin")
            s.d.tabel_banding.selectRow(0)
            QTimer.singleShot(800, s.l7)

        def l7(s):
            s.d.grab().save(str(OUT / f"dialog_hasil_terang_{BAHASA}.png"))
            app = QApplication.instance()
            app.setPalette(theme.palet("gelap"))
            app.setStyleSheet(theme.qss("gelap"))
            s.d._muat()
            QTimer.singleShot(900, lambda: (s.d.grab().save(str(OUT / f"dialog_hasil_gelap_{BAHASA}.png")), s.akhir()))

        def _tunggu(s, syarat, detik, lanjut, nama, _mulai=[0]):
            import time
            if not _mulai[0]:
                _mulai[0] = time.time()
            if syarat():
                _mulai[0] = 0
                lanjut()
            elif time.time() - _mulai[0] > detik:
                cek(False, f"menunggu {nama} > {detik} s ({s.d.l_status.text()})")
                s.akhir()
            else:
                QTimer.singleShot(300, lambda: s._tunggu(syarat, detik, lanjut, nama))

        def akhir(s):
            print("\n" + ("LULUS" if not gagal else f"GAGAL {len(gagal)}: " + "; ".join(gagal)), flush=True)
            s._simpan_diam()
            QSettings("VirmoLab", "VirmoLab").setValue("bahasa", "id")
            QApplication.quit()
            os._exit(1 if gagal else 0)

    mainwindow.JendelaUtama = Uji
    A.main()


hook()
