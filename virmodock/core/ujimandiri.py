"""Uji mandiri instalasi: semua komponen penting bisa dimuat dan dijalankan di laptop ini.

Dipakai dari menu Tools › Uji mandiri dan baris perintah `VirmoDock.exe --uji-mandiri hasil.json`.
"""
import json
import subprocess
import tempfile
import time
from pathlib import Path

from . import paths

NOWIN = 0x08000000


def _jalan(cmd, timeout=60):
    p = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=NOWIN)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def uji(lapor=None):
    hasil = []

    def cek(nama, fn):
        t = time.time()
        try:
            detail = fn() or "ok"
            hasil.append({"uji": nama, "ok": True, "detail": str(detail)[:200], "detik": round(time.time() - t, 2)})
        except Exception as e:
            hasil.append({"uji": nama, "ok": False, "detail": f"{type(e).__name__}: {e}"[:300],
                          "detik": round(time.time() - t, 2)})
        if lapor:
            h = hasil[-1]
            lapor.log.emit(f"{'OK   ' if h['ok'] else 'GAGAL'} {nama}: {h['detail']}")

    def program(nama, arg):
        def f():
            exe = paths.program(nama)
            if not exe:
                raise FileNotFoundError(f"{nama} tidak ada di {paths.BIN}")
            kode, out = _jalan([exe] + arg)
            baris = [b for b in out.splitlines() if b.strip()]
            return (baris[0] if baris else f"kode {kode}")
        return f

    cek("AutoDock Vina", program("vina.exe", ["--version"]))
    cek("AutoGrid4", program("autogrid4.exe", ["--version"]))
    cek("AutoDock4", program("autodock4.exe", ["--version"]))
    cek("AutoDock-GPU", program("autodock_gpu.exe", ["--version"]))

    def ob():
        from . import obabel
        return obabel.konversi("CC(=O)Oc1ccccc1C(=O)O\n", "smi", "smi", ["-p", "7.4"]).split()[0]
    cek("Open Babel (obabel)", ob)

    def lig():
        from . import prep_ligan
        h = prep_ligan.siapkan_satu("aspirin", "CC(=O)Oc1ccccc1C(=O)O", "smiles", prep_ligan.OpsiLigan())
        if h.status == "gagal":
            raise RuntimeError(h.alasan)
        return f"RDKit + Meeko: {h.rumus}, {h.torsi} torsi, {h.atom} atom PDBQT"
    cek("Preparasi ligan (RDKit, Meeko)", lig)

    def gem():
        import gemmi
        st = gemmi.read_pdb_string("ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00  0.00           N\nEND\n")
        return f"gemmi {gemmi.__version__}, {st[0].count_atom_sites()} atom"
    cek("gemmi", gem)

    def fitur():
        from rdkit import Chem
        from . import analisis
        f = analisis._fitur(Chem.AddHs(Chem.MolFromSmiles("NCC(=O)O")))
        return "fitur: " + ", ".join(sorted(f))
    cek("Fitur kimia RDKit (interaksi)", fitur)

    def vina_dock():
        from . import prep_ligan
        h = prep_ligan.siapkan_satu("asetat", "CC(=O)O", "smiles", prep_ligan.OpsiLigan(protonasi=False))
        rec = ("ATOM      1  CA  ALA A   1       2.000   0.000   0.000  1.00  0.00     0.000 C \n"
               "ATOM      2  O   ALA A   1      -2.000   0.000   0.000  1.00  0.00    -0.300 OA\n")
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "r.pdbqt").write_text(rec)
            (d / "l.pdbqt").write_text(h.pdbqt)
            kode, out = _jalan([paths.program("vina.exe"), "--receptor", str(d / "r.pdbqt"), "--ligand",
                                str(d / "l.pdbqt"), "--center_x", "0", "--center_y", "0", "--center_z", "0",
                                "--size_x", "12", "--size_y", "12", "--size_z", "12", "--exhaustiveness", "1",
                                "--num_modes", "1", "--seed", "1", "--cpu", "1", "--out", str(d / "o.pdbqt")], 120)
            if not (d / "o.pdbqt").exists():
                raise RuntimeError(out.strip().splitlines()[-1] if out.strip() else f"kode {kode}")
            return "docking kecil berhasil"
    cek("Docking Vina mini", vina_dock)

    def gpu():
        from . import env
        e = env.deteksi({})
        g = e.gpu_utama
        return (f"{g.nama} · OpenCL {'ya' if g.opencl else 'tidak'}" if g else "tanpa GPU") + f" · mode {e.mode_bawaan}"
    cek("Deteksi GPU/OpenCL", gpu)

    def xlsx():
        import openpyxl
        return f"openpyxl {openpyxl.__version__}"
    cek("Ekspor Excel", xlsx)
    return hasil


def tulis(path):
    from .. import __version__
    h = uji()
    data = {"versi": __version__, "portable": paths.PORTABLE, "bin": str(paths.BIN), "hasil": h,
            "semua_ok": all(x["ok"] for x in h)}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data["semua_ok"]
