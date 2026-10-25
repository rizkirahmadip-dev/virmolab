"""Uji GUI impor hasil eksternal: docking (Vina PDBQT + SDF bergaya GOLD), trajektori MD (GRO + XTC terbungkus PBC
dengan air dan ion), pemutar trajektori di viewport, dan grafik XVG/CSV.

Data uji dibangkitkan dari MD internal proyek uji 1HSG + MK1 (dev/uji/md_gui), jadi tidak butuh GROMACS.

  PYTHONPATH=. .venv/Scripts/python.exe dev/uji_impor_eksternal_gui.py
Keluaran: dev/uji/impor_eksternal/*.png
"""
import shutil
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
AKAR = Path(__file__).resolve().parents[1]
KERJA = (AKAR / "dev" / "uji" / "kerja_impor_eksternal").resolve()
DATA = KERJA / "data"
KELUAR = AKAR / "dev" / "uji" / "impor_eksternal"
SUMBER = AKAR / "dev" / "uji" / "md_gui" / "proyek_md.vmd"
shutil.rmtree(KERJA, ignore_errors=True)
DATA.mkdir(parents=True)
KELUAR.mkdir(parents=True, exist_ok=True)
st = QSettings("VirmoLab", "VirmoLab")
st.setValue("wizard_selesai", True)
st.setValue("tema", "terang")
st.setValue("folder_kerja", str(KERJA))
st.remove("layout")
st.remove("sesi_terbuka")

if not (SUMBER / "md").is_dir():
    print(f"LEWAT: proyek MD contoh belum ada di {SUMBER}. Jalankan dev/uji_md_gui.py dulu "
          "(dev/regresi.py menjalankannya lebih dulu).")
    raise SystemExit(0)

import virmolab.app as A                                     # noqa: E402
from PySide6.QtWidgets import QApplication                  # noqa: E402

gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


# ------------------------------------------------------------------ data uji
def data_docking():
    from rdkit import Chem
    from virmolab.core import impor_docking as I
    # nama folder job dibuat dari waktu, jadi jangan dipatok: ambil hasil docking mana pun di proyek MD contoh
    vina = next((x for x in sorted(SUMBER.glob("hasil/*/*_out.pdbqt"))), None)
    if vina is None:
        raise SystemExit(f"LEWAT: belum ada hasil docking di {SUMBER / 'hasil'}; jalankan dev/uji_md_gui.py dulu.")
    shutil.copy(vina, DATA / "MK1_out.pdbqt")
    shutil.copy(SUMBER / "reseptor" / "reseptor.pdbqt", DATA / "1hsg_reseptor.pdbqt")
    d, _ = I.baca_berkas(vina)
    w = Chem.SDWriter(str(DATA / "gold_soln_MK1.sdf"))
    for i, p in enumerate(d[0].pose[:4], 1):      # empat pose, skor gaya GOLD (fitness, besar = baik)
        m = Chem.Mol(p.mol)
        m.SetProp("_Name", f"MK1_gold|mk1|sdf|1|dock{i}")
        m.SetProp("Gold.PLP.Fitness", f"{82 - 2.5 * i + (i % 3) * 3:.2f}")
        w.write(m)
    w.close()


def data_md():
    """Sistem terlarut + 300 air + 6 ion dalam kotak kubus; koordinat dibungkus per atom (molekul terpotong)."""
    from openmm import app
    from openmm.app.internal.xtc_utils import xtc_write_frame
    from virmolab.core import impor_md as M
    d = next((x.parent for x in sorted(SUMBER.glob("md/*/*/topologi.pdb"))), None)
    if d is None:
        raise SystemExit(f"LEWAT: belum ada trajektori MD di {SUMBER / 'md'}; jalankan dev/uji_md_gui.py dulu.")
    pdb = app.PDBFile(str(d / "topologi.pdb"))
    r = M.PembacaDCD(d / "trajektori_terlarut.dcd")
    n = r.n_atom
    # 25 frame (tiap frame ke-4) cukup menguji PBC, analisis, dan pemutar tanpa menunggu lama
    fr = np.array([x for _, x, _ in r.baca(list(range(0, r.n_frame, 4)), list(range(n)))], dtype=float)   # nm
    rng = np.random.default_rng(3)
    L = float(np.ptp(fr[0], axis=0).max() + 1.4)
    n_air = 300
    geser = np.array([0.8 * L, 0.15 * L, 0.55 * L]) - fr[0].mean(0)
    air = rng.uniform(0, L, (n_air, 3))
    baris = []
    for a in pdb.topology.atoms():
        baris.append((int(a.residue.id) if a.residue.id.lstrip("-").isdigit() else 1, a.residue.name, a.name))
    for j in range(n_air):
        baris += [(9000 + j, "SOL", "OW"), (9000 + j, "SOL", "HW1"), (9000 + j, "SOL", "HW2")]
    baris += [(9500 + j, "NA", "NA") for j in range(3)] + [(9600 + j, "CL", "CL") for j in range(3)]
    n_tot = len(baris)
    f_xtc = DATA / "md.xtc"
    for k in range(len(fr)):
        x = np.zeros((n_tot, 3))
        x[:n] = fr[k] + geser
        o = air + rng.normal(0, 0.05, air.shape) * (k + 1) ** 0.5
        for j in range(n_air):
            x[n + 3 * j] = o[j]
            x[n + 3 * j + 1] = o[j] + [0.0957, 0, 0]
            x[n + 3 * j + 2] = o[j] + [-0.024, 0.0927, 0]
        x[n + 3 * n_air:] = rng.uniform(0, L, (6, 3))
        x = np.mod(x, L)
        if k == 0:
            g = ["Sistem uji 1HSG MK1 air ion", f"{n_tot:5d}"]
            for i, ((resi, resn, nama), p) in enumerate(zip(baris, x), 1):
                g.append(f"{resi % 100000:5d}{resn:<5s}{nama:>5s}{i % 100000:5d}{p[0]:8.3f}{p[1]:8.3f}{p[2]:8.3f}")
            g.append(f"{L:10.5f}{L:10.5f}{L:10.5f}")
            (DATA / "md.gro").write_text("\n".join(g) + "\n", encoding="utf-8")
        xtc_write_frame(str(f_xtc).encode("utf-8"), x.astype(np.float32), np.diag([L, L, L]).astype(np.float32),
                        float(40.0 * k), int(20000 * k))
    # grafik gmx
    t = np.arange(0, 1001, 10.0)
    rmsd = 0.1 * (1 - np.exp(-t / 150)) + rng.normal(0, 0.006, len(t))
    for rep in (1, 2, 3):
        y = rmsd * (0.85 + 0.15 * rep) + rng.normal(0, 0.004, len(t))
        (DATA / f"rmsd_rep{rep}.xvg").write_text(
            '# gmx rms\n@    title "RMSD"\n@    xaxis  label "Time (ps)"\n@    yaxis  label "RMSD (nm)"\n@TYPE xy\n'
            + "".join(f"{a:10.3f} {b:10.6f}\n" for a, b in zip(t, y)), encoding="utf-8")


def hook():
    from virmolab.ui import mainwindow
    Asli = mainwindow.JendelaUtama

    class Uji(Asli):
        def __init__(s):
            super().__init__()
            s.resize(1600, 960)
            s.move(20, 20)
            QTimer.singleShot(1500, s.l1)
            QTimer.singleShot(10 * 60 * 1000, lambda: (print("TIMEOUT"), s.akhir()))

        def _cari(s, nama_kelas):
            return next((w for w in QApplication.topLevelWidgets() if type(w).__name__ == nama_kelas
                         and w.isVisible()), None)

        # ------------------------------------------------ docking
        def l1(s):
            data_docking()
            data_md()
            s.buka_impor_docking([str(DATA / "MK1_out.pdbqt"), str(DATA / "gold_soln_MK1.sdf"),
                                  str(DATA / "1hsg_reseptor.pdbqt")])
            QTimer.singleShot(500, lambda: s.l2(0))

        def l2(s, n):
            d = s._cari("DialogImporDocking")
            if d is None or d._antre or len(d.daftar) < 2:
                if n > 120:
                    cek(False, "dialog impor docking membaca berkas")
                    return s.akhir()
                return QTimer.singleShot(500, lambda: s.l2(n + 1))
            cek(len(d.daftar) == 2, f"dua ligan terbaca ({[x.nama for x in d.daftar]})")
            cek(d.cb_rec.currentData() == "berkas", "berkas protein otomatis menjadi reseptor")
            prog = {x.nama: x.program for x in d.daftar}
            cek(prog.get("MK1") == "AutoDock Vina" and prog.get("MK1_gold") == "GOLD", f"program dikenali ({prog})")
            d.resize(1100, 720)
            QTimer.singleShot(400, lambda: (d.grab().save(str(KELUAR / "impor_docking_dialog.png")), s.l3(d)))

        def l3(s, d):
            # skor utama: ChemPLP fitness (besar = baik); ΔG: skor ulang Vina untuk ligan GOLD, asli untuk Vina
            cek(d.cb_energi.currentData() == "vina", f"ΔG bawaan afinitas Vina ({d.cb_energi.currentData()})")
            s._job = None
            d.selesai.connect(lambda j: setattr(s, "_job", j))
            d._impor()
            QTimer.singleShot(1000, lambda: s.l4(0))

        def l4(s, n):
            if s._job is None:
                if n > 300:
                    cek(False, "impor docking selesai")
                    return s.akhir()
                return QTimer.singleShot(1000, lambda: s.l4(n + 1))
            j = s._job
            cek(j["label_mesin"].endswith("(impor)"), f"label mesin job ({j['label_mesin']})")
            lig = {l["nama"]: l for l in j["ligan"]}
            cek(lig["MK1"]["energi_sumber"].startswith("Afinitas Vina"), "ΔG Vina dari skor asli")
            cek(lig["MK1_gold"]["energi_sumber"].startswith("Skor ulang Vina"), "ΔG GOLD dari skor ulang Vina")
            cek(lig["MK1_gold"]["pose"][0]["skor"]["Gold.PLP.Fitness"] ==
                max(p["skor"]["Gold.PLP.Fitness"] for p in lig["MK1_gold"]["pose"]), "pose 1 GOLD = fitness tertinggi")
            cek((lig["MK1"].get("interaksi") or {}).get("hbond", 0) > 0, "interaksi pose terbaik terhitung")
            cek(s.hasil.pohon.topLevelItemCount() == 2, f"tabel hasil berisi 2 baris ({s.hasil.pohon.topLevelItemCount()})")
            mesin = {s.hasil.pohon.topLevelItem(i).text(13) for i in range(s.hasil.pohon.topLevelItemCount())}
            cek(any("impor" in m for m in mesin), f"kolom mesin menampilkan impor ({mesin})")
            QTimer.singleShot(2500, lambda: s.l4b(j))

        def l4b(s, j):
            aktif = s.objek.get(s.aktif)
            cek(aktif is not None and aktif.jenis == "pose" and aktif.info.get("energi_sumber"),
                "pose impor terbuka dan aktif di viewport")
            rec = s._reseptor_objek(aktif)
            cek(rec is not None and rec.info.get("reseptor_job") == j["id"], "interaksi memakai reseptor job impor")
            # kanvas WebGL harus seukuran wadahnya dan kamera berpusat di pose (bukan bingkai lama yang tergeser)
            s.viewer.page().runJavaScript(
                "(() => { try { const r = document.getElementById('gl').getBoundingClientRect();"
                " const c = document.querySelector('#gl canvas');"
                " const m = VM.models[%r]; const p = m ? m.m.selectedAtoms({}) : [];"
                " const cx = p.reduce((a, b) => a + b.x, 0) / Math.max(1, p.length);"
                " const cy = p.reduce((a, b) => a + b.y, 0) / Math.max(1, p.length);"
                " const cz = p.reduce((a, b) => a + b.z, 0) / Math.max(1, p.length);"
                " const s = VM.v.modelToScreen({x: cx, y: cy, z: cz});"
                " return JSON.stringify([r.width, r.height, c ? c.clientWidth : 0, c ? c.clientHeight : 0, s.x, s.y]);"
                " } catch (e) { return String(e); } })()"
                % s.aktif, 0, s._cek_kanvas)

        def _cek_kanvas(s, h):
            print("kanvas", h, flush=True)
            import json
            try:
                h = json.loads(h)
            except (TypeError, ValueError):
                h = None
            if isinstance(h, list):
                w, t, cw, ch, x, y = h
                cek(abs(w - cw) < 3 and abs(t - ch) < 3, f"kanvas WebGL seukuran wadah ({cw:.0f}×{ch:.0f} vs {w:.0f}×{t:.0f})")
                cek(abs(x - w / 2) < w * 0.15 and abs(y - t / 2) < t * 0.15,
                    f"pose impor di tengah viewport (layar {x:.0f},{y:.0f} dari {w:.0f}×{t:.0f})")
            s.grab().save(str(KELUAR / "impor_docking_hasil.png"))
            s.l5()

        # ------------------------------------------------ MD
        def l5(s):
            s.buka_impor_md([str(DATA / "md.xtc")])        # topologi md.gro dicari otomatis
            QTimer.singleShot(500, lambda: s.l6(0))

        def l6(s, n):
            d = s._cari("DialogImporMD")
            if d is None or not d.b_jalan.isEnabled():
                if n > 120:
                    cek(False, "dialog impor MD siap")
                    return s.akhir()
                return QTimer.singleShot(500, lambda: s.l6(n + 1))
            cek(Path(d.f_top).name == "md.gro", f"topologi dipilih otomatis ({d.f_top})")
            cek(d.cb_ligan.count() >= 2 and "UNK" in d.cb_ligan.itemText(0), f"ligan terdeteksi ({d.cb_ligan.itemText(0)})")
            QTimer.singleShot(300, lambda: (d.grab().save(str(KELUAR / "impor_md_dialog.png")), d._jalankan(),
                                            QTimer.singleShot(2000, lambda: s.l7(0))))

        def l7(s, n):
            v = s._cari("DialogMD")
            if v is None:
                if n > 600:
                    cek(False, "analisis trajektori impor selesai")
                    return s.akhir()
                return QTimer.singleShot(1000, lambda: s.l7(n + 1))
            x = v._ligan_hasil()
            cek(x is not None and x.get("impor"), "jendela analisis menampilkan hasil impor")
            tr = (x or {}).get("trajektori") or {}
            cek(len(tr.get("rmsd_ca") or []) == 25 and max(tr["rmsd_ca"]) < 3.0,
                f"RMSD Cα wajar setelah perbaikan PBC (maks {max(tr.get('rmsd_ca') or [0]):.2f} Å)")
            cek(bool(x.get("interaksi_frek")), "okupansi interaksi terhitung")
            v.resize(1100, 820)
            QTimer.singleShot(800, lambda: s.l8(v))

        def l8(s, v):
            v.grab().save(str(KELUAR / "impor_md_ringkasan.png"))
            v.tab.setCurrentIndex(1)
            QTimer.singleShot(500, lambda: (v.grab().save(str(KELUAR / "impor_md_rmsd.png")),
                                            v.tab.setCurrentIndex(2),
                                            QTimer.singleShot(500, lambda: (
                                                v.grab().save(str(KELUAR / "impor_md_interaksi.png")),
                                                v._putar(), QTimer.singleShot(1500, lambda: s.l9(v, 0))))))

        def l9(s, v, n):
            if not s.pemutar.isVisible():
                if n > 60:
                    cek(False, "pemutar trajektori muncul")
                    return s.akhir()
                return QTimer.singleShot(500, lambda: s.l9(v, n + 1))
            cek(s.pemutar.slider.maximum() >= 24, f"pemutar memuat semua bingkai ({s.pemutar.slider.maximum() + 1})")
            s.pemutar.putar_jeda(False)
            s.pemutar.slider.setValue(15)
            v.hide()
            QTimer.singleShot(1500, lambda: (s.grab().save(str(KELUAR / "impor_md_pemutar.png")), s.l10()))

        # ------------------------------------------------ grafik
        def l10(s):
            s.pemutar.tutup()
            s.buka_grafik_berkas([str(DATA / f"rmsd_rep{i}.xvg") for i in (1, 2, 3)])
            QTimer.singleShot(1200, s.l11)

        def l11(s):
            g = s._cari("DialogGrafikBerkas")
            cek(g is not None and len(g._terpilih()) == 3, "tiga seri RMSD replika ditumpuk")
            cek(g is not None and g.c_A.isChecked() and "Å" in g.e_y.text() and "ns" in g.e_x.text(),
                f"satuan dikonversi nm→Å dan ps→ns ({g.e_x.text() if g else ''} / {g.e_y.text() if g else ''})")
            g.c_rerata.setChecked(True)
            g.resize(1180, 760)
            QTimer.singleShot(600, lambda: (g.grab().save(str(KELUAR / "grafik_xvg_terang.png")), s.l12(g)))

        def l12(s, g):
            s.terapkan_tema("gelap")
            g.gambar()
            QTimer.singleShot(1200, lambda: (g.grab().save(str(KELUAR / "grafik_xvg_gelap.png")),
                                             s.buka_md_hasil(s.proyek.md[-1]["id"]),
                                             QTimer.singleShot(1500, s.l13)))

        def l13(s):
            v = s._cari("DialogMD")
            if v:
                v.resize(1100, 820)
                v.tab.setCurrentIndex(1)
            QTimer.singleShot(1000, lambda: (v and v.grab().save(str(KELUAR / "impor_md_rmsd_gelap.png")),
                                             s.terapkan_tema("terang"), s.akhir()))

        def akhir(s):
            print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
            for g in gagal:
                print("  -", g)
            QApplication.quit()

    mainwindow.JendelaUtama = Uji
    A.main()


hook()
