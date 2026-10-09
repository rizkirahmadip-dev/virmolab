"""Skrip sesi PyMOL (.pml) dan ChimeraX (.cxc) untuk pose aktif: reseptor, ligan, residu kontak, garis interaksi.

Berkas struktur ditulis di folder yang sama dengan skrip. ChimeraX membuka jalur relatif terhadap folder skrip;
PyMOL relatif terhadap folder kerjanya, jadi .pml memakai jalur absolut (garis miring /). Warna interaksi sama dengan diagram 2D.
"""
from pathlib import Path

from .analisis import NAMA_JENIS
from .diagram2d import WARNA

WARNA_LIGAN = "#2b6fd6"


def _residu(daftar):
    """[(rantai, resi, resn)] unik, urutan tetap."""
    lihat, out = set(), []
    for x in daftar:
        k = (x.get("rantai", ""), str(x["resi"]), x["resn"])
        if k not in lihat:
            lihat.add(k)
            out.append(k)
    return out


def _hex_pymol(h):
    return "0x" + h.lstrip("#").upper()


def _pml(daftar, rec_f, lig_f, judul):
    b = [f"# Sesi PyMOL dari VirmoDock: {judul}",
         "# Buka di PyMOL: File > Run Script, atau seret berkas ini ke jendela PyMOL.",
         "reinitialize", f"load {rec_f}, reseptor", f"load {lig_f}, ligan",
         "hide everything", "show cartoon, reseptor", "set cartoon_transparency, 0.45",
         "color grey80, reseptor", "show sticks, ligan and not (elem H and neighbor elem C)",
         f"color {_hex_pymol(WARNA_LIGAN)}, ligan and elem C", "set stick_radius, 0.18"]
    res = _residu([x for x in daftar if x["jenis"] != "vdw"])
    if res:
        sel = " or ".join(f"(chain {r} and resi {i})" if r else f"(resi {i})" for r, i, _ in res)
        b += [f"select kontak, reseptor and ({sel})",
              "show sticks, kontak and not name N+C+O and not elem H",
              "color grey60, kontak and elem C",
              "set label_size, 14", "set label_color, black, kontak",
              "label kontak and name CA, \"%s%s\" % (resn, resi)"]
    titik = []
    for n, x in enumerate(daftar, 1):
        if x["jenis"] == "vdw":
            continue
        w = WARNA.get(x["jenis"], "#888888")
        nama = f"{x['jenis']}_{n}"
        b += [f"pseudoatom _p{n}, pos=[{x['p'][0]}, {x['p'][1]}, {x['p'][2]}]",
              f"pseudoatom _l{n}, pos=[{x['l'][0]}, {x['l'][1]}, {x['l'][2]}]",
              f"distance {nama}, _p{n}, _l{n}",
              f"color {_hex_pymol(w)}, {nama}"]
        titik += [f"_p{n}", f"_l{n}"]
    if titik:
        b += ["hide everything, _p* or _l*", "group titik_interaksi, _p* _l*", "disable titik_interaksi",
              "group interaksi, " + " ".join(f"{x['jenis']}_{n}" for n, x in enumerate(daftar, 1)
                                              if x["jenis"] != "vdw"),
              "set dash_gap, 0.25", "set dash_radius, 0.05", "hide labels, interaksi"]
    b += ["bg_color white", "set ray_opaque_background, 1", "set antialias, 2",
          "orient ligan", "zoom ligan, 4", ""]
    return "\n".join(b)


def _cxc(daftar, rec_f, lig_f, judul):
    b = [f"# Sesi ChimeraX dari VirmoDock: {judul}",
         "# Buka di ChimeraX: File > Open, pilih berkas ini.",
         "close session", f"open {rec_f}", f"open {lig_f}",
         "hide #1 atoms", "cartoon #1", "color #1 lightgray", "transparency #1 45 target c",
         "show #2 atoms", "style #2 stick", f"color #2 & C {WARNA_LIGAN}", "hide #2 & HC atoms"]
    res = _residu([x for x in daftar if x["jenis"] != "vdw"])
    if res:
        spes = " ".join(f"#1/{r}:{i}" if r else f"#1:{i}" for r, i, _ in res)
        b += [f"show ({spes}) & sidechain & ~H atoms", f"style {spes} stick", f"color ({spes}) & C gray",
              f"label {spes} residues height 0.6 color black"]
    k = 0
    for x in daftar:
        if x["jenis"] == "vdw":
            continue
        w = WARNA.get(x["jenis"], "#888888")
        a, c = k * 2 + 1, k * 2 + 2
        b += [f"marker #10 position {x['p'][0]},{x['p'][1]},{x['p'][2]} color {w} radius 0.06",
              f"marker #10 position {x['l'][0]},{x['l'][1]},{x['l'][2]} color {w} radius 0.06",
              f"marker link #10.{a},{c} color {w} radius 0.04"]
        k += 1
    if k:
        b += ["rename #10 interaksi"]
    b += ["set bgColor white", "graphics silhouettes true", "lighting soft", "view #2", "zoom 0.7", ""]
    return "\n".join(b)


def tulis(folder, nama, teks_reseptor, mol_ligan, daftar, judul=""):
    """Tulis reseptor PDB, ligan SDF, <nama>.pml dan <nama>.cxc ke `folder`. Mengembalikan (pml, cxc)."""
    from rdkit import Chem
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rec_f, lig_f = f"{nama}_reseptor.pdb", f"{nama}_ligan.sdf"
    baris = [x for x in teks_reseptor.splitlines() if x.startswith(("ATOM", "HETATM", "TER"))]
    (folder / rec_f).write_text("\n".join(baris + ["END", ""]), encoding="utf-8")
    m = Chem.Mol(mol_ligan)
    m.SetProp("_Name", nama)
    (folder / lig_f).write_text(Chem.MolToMolBlock(m) + "$$$$\n", encoding="utf-8")
    daftar = [x for x in (daftar or []) if x.get("p") and x.get("l")]
    judul = judul or nama
    pml, cxc = folder / f"{nama}.pml", folder / f"{nama}.cxc"
    def absolut(f):
        return '"' + (folder / f).resolve().as_posix() + '"'
    pml.write_text(_pml(daftar, absolut(rec_f), absolut(lig_f), judul), encoding="utf-8")
    cxc.write_text(_cxc(daftar, rec_f, lig_f, judul), encoding="utf-8")
    ringkas = ", ".join(f"{NAMA_JENIS.get(j, j)} {sum(1 for x in daftar if x['jenis'] == j)}"
                        for j in dict.fromkeys(x["jenis"] for x in daftar) if j != "vdw")
    (folder / f"{nama}_BACA.txt").write_text(
        f"{judul}\nInteraksi: {ringkas or '-'}\n\n"
        f"PyMOL   : File > Run Script > {pml.name}  (atau seret ke jendela PyMOL)\n"
        f"ChimeraX: File > Open > {cxc.name}\n"
        "Skrip memuat berkas struktur di folder ini. Bila folder dipindah, .cxc tetap jalan; untuk .pml\n"
        "ubah jalur pada dua baris 'load'.\n", encoding="utf-8")
    return pml, cxc
