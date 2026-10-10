"""Ekspor: kompleks PDB, SDF bertag, tabel CSV/XLSX, gambar raster dengan metadata DPI."""
import csv
import io
from datetime import datetime

KOLOM_HASIL = [("peringkat", "Peringkat"), ("ligan", "Ligan"), ("energi", "ΔG (kcal/mol)"), ("ki", "Ki perkiraan"),
               ("le", "LE (kcal/mol/atom berat)"), ("klaster", "Klaster (n)"), ("rmsd_kristal", "RMSD kristal (Å)"),
               ("rmsd", "RMSD ref / l.b. (Å)"), ("ifp_sim", "Kemiripan IFP vs kristal (Tanimoto)"),
               ("mmgbsa", "MM/GBSA ΔG (kcal/mol)"), ("mmgbsa_sd", "MM/GBSA SD (kcal/mol)"),
               ("mmgbsa_metode", "MM/GBSA metode"), ("posebusters", "PoseBusters"),
               ("posebusters_gagal", "PoseBusters: uji gagal"), ("hbond", "Ikatan H"), ("hidrofobik", "Hidrofobik"), ("pi", "π–π"),
               ("pikation", "π–kation"), ("garam", "Jembatan garam"), ("halogen", "Halogen"), ("logam", "Logam"),
               ("n_pose", "Jumlah pose"), ("mesin", "Mesin"), ("job", "Job"), ("detik", "Waktu (s)"),
               ("smiles", "SMILES")]


def baris_hasil(proyek, jobs=None):
    """Satu baris per ligan per job (pose terbaik), urut ΔG."""
    from . import mesin as M
    from . import qc
    baris = []
    for j in (jobs if jobs is not None else proyek.job):
        for l in j["ligan"]:
            if l["status"] != "selesai":
                continue
            p0 = l["pose"][0] if l.get("pose") else {}
            n = l.get("interaksi") or {}
            lig = proyek.cari_ligan(l["id"]) or {}
            baris.append({"ligan": l["nama"], "lid": l["id"], "energi": l["energi"], "ki": l.get("ki", ""),
                          "le": l.get("le"), "klaster": p0.get("klaster") or None,
                          "rmsd_kristal": l.get("rmsd_kristal"),
                          "rmsd": p0.get("rmsd_ref") if p0 and p0.get("rmsd_ref", -1) >= 0 else None,
                          **{k: n.get(k, 0) for k in ("hbond", "hidrofobik", "pi", "pikation", "garam", "halogen",
                                                      "logam")},
                          "n_pose": l.get("n_pose"), "mesin": M.MESIN.get(j["mesin"], j["mesin"]), "job": j["id"],
                          "detik": l.get("detik"), "smiles": lig.get("smiles", ""), "residu": l.get("residu") or {}, "ifp": l.get("ifp") or [],
                          "pose": l.get("pose") or [], "qc": l.get("qc"), "posebusters": qc.teks_sel(l.get("qc")),
                          "posebusters_gagal": ", ".join((l.get("qc") or {}).get("gagal") or []),
                          "mmgbsa": (l.get("mmgbsa") or {}).get("dG"), "mmgbsa_sd": (l.get("mmgbsa") or {}).get("sd"),
                          "mmgbsa_metode": (l.get("mmgbsa") or {}).get("metode", "")})
    # acuan IFP: pose kristal ligan asli (dari job dengan reseptor yang sama bila ada)
    from .analisis import tanimoto
    acuan = {}
    for j in proyek.job:
        for l in j["ligan"]:
            if l.get("ifp_kristal"):
                acuan.setdefault(j.get("reseptor"), l["ifp_kristal"])
                acuan.setdefault(None, l["ifp_kristal"])
    rec_job = {j["id"]: j.get("reseptor") for j in proyek.job}
    for b in baris:
        ref = acuan.get(rec_job.get(b["job"])) or acuan.get(None)
        b["ifp_sim"] = tanimoto(b["ifp"], ref) if ref else None
    baris.sort(key=lambda b: b["energi"])
    for i, b in enumerate(baris, 1):
        b["peringkat"] = i
    return baris


# ------------------------------------------------------------------ tabel
def _angka(v, desimal_koma):
    if isinstance(v, float):
        t = f"{v:.3f}".rstrip("0").rstrip(".") if abs(v) < 1000 else f"{v:.1f}"
        return t.replace(".", ",") if desimal_koma else t
    return "" if v is None else str(v)


def csv_teks(baris, pemisah=";", desimal_koma=True):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=pemisah, lineterminator="\r\n")
    w.writerow([t for _, t in KOLOM_HASIL])
    for b in baris:
        w.writerow([_angka(b.get(k), desimal_koma) for k, _ in KOLOM_HASIL])
    return "﻿" + buf.getvalue()   # BOM: Excel membaca Δ, µ, Å dengan benar


def simpan_xlsx(path, proyek, baris, interaksi_per_ligan=None, info=None, sifat_ligan=None):
    """Lembar: Ringkasan, Semua pose, Interaksi, Sifat ligan, Statistik, Parameter, Info."""
    from openpyxl import Workbook
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    kepala = Font(bold=True, color="FFFFFF")
    isi_kepala = PatternFill("solid", fgColor="1F5FBF")

    def lembar(ws, judul, kolom, data):
        ws.title = judul
        ws.append(kolom)
        for c in ws[1]:
            c.font, c.fill = kepala, isi_kepala
            c.alignment = Alignment(vertical="center", wrap_text=True)
        for r in data:
            ws.append(r)
        ws.freeze_panes = "A2"
        if data:
            ws.auto_filter.ref = f"A1:{get_column_letter(len(kolom))}{len(data) + 1}"
        for i, k in enumerate(kolom, 1):
            lebar = max([len(str(k))] + [len(str(r[i - 1])) for r in data[:500] if i - 1 < len(r)])
            ws.column_dimensions[get_column_letter(i)].width = min(48, max(9, lebar + 2))
        return ws

    ws = lembar(wb.active, "Ringkasan", [t for _, t in KOLOM_HASIL],
                [[b.get(k) for k, _ in KOLOM_HASIL] for b in baris])
    for kol in (3, 5, 7, 8):
        for c in ws.iter_cols(min_col=kol, max_col=kol, min_row=2):
            for x in c:
                x.number_format = "0.00"
    if baris:
        ws.conditional_formatting.add(f"C2:C{len(baris) + 1}",
                                      ColorScaleRule(start_type="min", start_color="1F5FBF", mid_type="percentile",
                                                     mid_value=50, mid_color="E2EBF8", end_type="max",
                                                     end_color="FFFFFF"))
    pose = []
    for b in baris:
        for p in b["pose"]:
            pose.append([b["ligan"], b["job"], b["mesin"], p.get("peringkat"), p.get("energi"),
                         p.get("rmsd_lb"), p.get("rmsd_ub"), p.get("klaster"),
                         p.get("rmsd_ref") if p.get("rmsd_ref", -1) >= 0 else None, p.get("rmsd_kristal")])
    lembar(wb.create_sheet(), "Semua pose", ["Ligan", "Job", "Mesin", "Pose", "ΔG (kcal/mol)", "RMSD l.b. (Å)",
                                             "RMSD u.b. (Å)", "Klaster (n)", "RMSD ref (Å)", "RMSD kristal (Å)"], pose)
    inter = []
    for (lig, job), daftar in (interaksi_per_ligan or {}).items():
        from .analisis import NAMA_JENIS
        for h in daftar:
            inter.append([lig, job, NAMA_JENIS.get(h["jenis"], h["jenis"]), h.get("sub", ""), h["residu"],
                          h["atom_p"], h["jarak"], h.get("sudut")])
    lembar(wb.create_sheet(), "Interaksi", ["Ligan", "Job", "Jenis", "Subjenis", "Residu", "Atom protein",
                                            "Jarak (Å)", "Sudut (°)"], inter)
    bit = sorted({x for b in baris for x in b.get("ifp") or []},
                 key=lambda x: (-sum(1 for b in baris if x in (b.get("ifp") or [])), x))
    if bit:   # sidik jari interaksi: 1 baris per ligan, 1 kolom per bit 'residu|jenis' (urut frekuensi)
        from .analisis import NAMA_JENIS
        kol = ["Ligan", "Job", "ΔG (kcal/mol)", "IFP vs kristal"] + [
            f"{x.split('|')[0]} · {NAMA_JENIS.get(x.split('|')[1], x.split('|')[1])}" for x in bit]
        ws = lembar(wb.create_sheet(), "Sidik jari interaksi", kol,
                    [[b["ligan"], b["job"], b["energi"], b.get("ifp_sim")]
                     + [1 if x in (b.get("ifp") or []) else 0 for x in bit] for b in baris])
        if baris:
            ws.conditional_formatting.add(
                f"E2:{get_column_letter(len(kol))}{len(baris) + 1}",
                ColorScaleRule(start_type="num", start_value=0, start_color="FFFFFF", end_type="num", end_value=1,
                               end_color="1F5FBF"))
    if sifat_ligan:
        from .sifat import baris_xlsx
        kol, data = baris_xlsx(sifat_ligan)
        lembar(wb.create_sheet(), "Sifat ligan", kol, data)
    from . import statistik as S
    sif = {l["id"]: l["sifat"] for l in proyek.ligan if isinstance(l.get("sifat"), dict)}
    ds = S.dataset(baris, sif)
    stat = []
    for jid in dict.fromkeys(d["job"] for d in ds):
        sub = [d for d in ds if d["job"] == jid]
        for k, label, _p, _d in S.VARIABEL:
            r = S.deskriptif(S.kolom(sub, k))
            if r["n"]:
                stat.append([jid, sub[0]["mesin"], label, r["n"], r["rerata"], r["sd"], r["median"], r["q1"], r["q3"],
                             r["min"], r["maks"]])
    if stat:
        ws = lembar(wb.create_sheet(), "Statistik", ["Job", "Mesin", "Variabel", "n", "Rerata", "SD", "Median", "Q1",
                                                     "Q3", "Min", "Maks"], stat)
        for c in ws.iter_rows(min_row=2, min_col=5, max_col=11):
            for x in c:
                x.number_format = "0.000"
    par = []
    for j in proyek.job:
        for k, v in j["parameter"].items():
            par.append([j["id"], k, str(v)])
        par.append([j["id"], "kotak", str(j["kotak"])])
    lembar(wb.create_sheet(), "Parameter", ["Job", "Parameter", "Nilai"], par)
    lembar(wb.create_sheet(), "Info", ["Kunci", "Nilai"], [[k, str(v)] for k, v in (info or {}).items()] +
           [["Dibuat", datetime.now().isoformat(timespec="seconds")],
            ["Catatan", "Hasil docking adalah prediksi komputasi; Ki dihitung dari ΔG (perkiraan, 298 K)."]])
    wb.save(path)


# --------------------------------------------------------------- struktur
def kompleks_pdb(teks_reseptor_pdb, mol_pose, remark=None, resn="LIG", rantai="L"):
    """Reseptor (ATOM) + ligan (HETATM, rantai terpisah, CONECT) dengan REMARK hasil."""
    from rdkit import Chem
    rec = [b for b in teks_reseptor_pdb.splitlines() if b.startswith(("ATOM", "HETATM"))]
    n = len(rec)
    m = Chem.Mol(mol_pose)
    for a in m.GetAtoms():
        info = Chem.AtomPDBResidueInfo()
        info.SetResidueName(resn)
        info.SetResidueNumber(1)
        info.SetChainId(rantai)
        info.SetIsHeteroAtom(True)
        nm = f"{a.GetSymbol().upper()}{a.GetIdx() + 1}"
        info.SetName(((" " + nm) if len(a.GetSymbol()) == 1 and len(nm) < 4 else nm)[:4].ljust(4))
        a.SetMonomerInfo(info)
    blok = Chem.MolToPDBBlock(m, flavor=0).splitlines()
    out = [f"REMARK   1 {t}"[:80] for t in (remark or [])]
    out.append("REMARK   1 Dibuat oleh VirmoDock " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    for i, b in enumerate(rec, 1):
        out.append(b[:6] + f"{i % 100000:5d}" + b[11:])
    out.append("TER")
    for b in blok:
        if b.startswith("HETATM"):
            out.append(b[:6] + f"{(int(b[6:11]) + n) % 100000:5d}" + b[11:])
        elif b.startswith("CONECT"):
            ser = [int(b[i:i + 5]) for i in range(6, len(b), 5) if b[i:i + 5].strip()]
            out.append("CONECT" + "".join(f"{s + n:5d}" for s in ser))
    out.append("END")
    return "\n".join(out) + "\n"


def sdf_bertag(entri):
    """entri: [(mol, nama, {tag: nilai})] -> teks SDF."""
    from rdkit import Chem
    buf = io.StringIO()
    w = Chem.SDWriter(buf)
    for mol, nama, tag in entri:
        m = Chem.Mol(mol)
        for k in list(m.GetPropNames()):
            m.ClearProp(k)
        m.SetProp("_Name", nama)
        for k, v in tag.items():
            if v is not None and v != "":
                m.SetProp(k, f"{v:.3f}" if isinstance(v, float) else str(v))
        w.write(m)
    w.close()
    return buf.getvalue()


# ----------------------------------------------------------------- gambar
def simpan_gambar(png_bytes, path, dpi=300, fmt=None, kompresi_tiff="tiff_lzw", kualitas=95, latar=None, ukuran=None):
    """Simpan PNG (bytes) ke PNG/TIFF/JPEG/WebP dengan metadata DPI yang benar (ukuran piksel dipastikan tepat)."""
    from PIL import Image
    img = Image.open(io.BytesIO(png_bytes))
    img.load()
    if ukuran and tuple(img.size) != tuple(ukuran):
        img = img.resize(tuple(int(x) for x in ukuran), Image.LANCZOS)
    fmt = (fmt or str(path).rsplit(".", 1)[-1]).lower()
    if fmt in ("jpg", "jpeg", "bmp") or (latar and img.mode == "RGBA"):
        dasar = Image.new("RGB", img.size, latar or "#ffffff")
        if img.mode == "RGBA":
            dasar.paste(img, mask=img.split()[3])
        else:
            dasar.paste(img)
        img = dasar
    opsi = {"dpi": (dpi, dpi)}
    if fmt in ("tif", "tiff"):
        opsi["compression"] = kompresi_tiff
        img.save(path, "TIFF", **opsi)
    elif fmt in ("jpg", "jpeg"):
        img.save(path, "JPEG", quality=kualitas, **opsi)
    elif fmt == "webp":
        img.save(path, "WEBP", quality=kualitas)
    else:
        img.save(path, "PNG", **opsi)
    return img.size


def mm_ke_px(mm, dpi):
    return int(round(mm / 25.4 * dpi))
