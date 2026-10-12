"""Diagram interaksi protein-ligan 2D (SVG vektor).

Ligan digambar RDKit (koordinat 2D CoordGen); residu diletakkan di sekeliling
ligan searah atom kontaknya, lalu dirapikan dengan relaksasi sederhana agar
tidak saling tumpuk dan tidak menutupi ligan.
"""
import math
import re
from xml.sax.saxutils import escape

from .analisis import NAMA_JENIS, URUT_JENIS

WARNA = {"hbond": "#2e9e5b", "hidrofobik": "#c98a12", "pi": "#7b5cd6", "pikation": "#2f8fd6",
         "garam": "#cf3f3f", "halogen": "#1aa3a3", "logam": "#7d80b0", "vdw": "#9aa6b8"}
FONT = "Segoe UI, Arial, Helvetica, sans-serif"


def _campur(hex_, t, latar="#ffffff"):
    a = [int(hex_[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(latar[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def svg(mol, daftar, lebar=960, tinggi=720, judul="", gelap=False, transparan=False, warna=None, jarak=True):
    from rdkit import Chem
    from rdkit.Chem import rdDepictor
    from rdkit.Chem.Draw import rdMolDraw2D
    warna = dict(WARNA, **(warna or {}))
    latar = "#14171c" if gelap else "#ffffff"
    tinta = "#e2e6ed" if gelap else "#1b2430"
    m = Chem.RemoveAllHs(Chem.Mol(mol), sanitize=False)
    try:
        Chem.SanitizeMol(m)
    except Exception:
        pass
    # E/Z & R/S dari geometri pose 3D; ikatan rangkap yang tetap tak tentu (STEREOANY) jangan digambar
    # sebagai ikatan silang - tampak cacat pada diagram interaksi (mis. hidrazon C=N).
    if m.GetNumConformers() and m.GetConformer().Is3D():
        try:
            Chem.AssignStereochemistryFrom3D(m)
        except Exception:
            pass
    for b in m.GetBonds():
        if b.GetStereo() == Chem.BondStereo.STEREOANY:
            b.SetStereo(Chem.BondStereo.STEREONONE)
        if b.GetBondDir() in (Chem.BondDir.EITHERDOUBLE, Chem.BondDir.UNKNOWN):
            b.SetBondDir(Chem.BondDir.NONE)
    m.RemoveAllConformers()
    rdDepictor.SetPreferCoordGen(True)
    rdDepictor.Compute2DCoords(m)

    leg_h = 46
    area_h = tinggi - leg_h - (30 if judul else 0)
    lw, lh = int(lebar * 0.48), int(area_h * 0.56)
    d = rdMolDraw2D.MolDraw2DSVG(lw, lh)
    o = d.drawOptions()
    o.clearBackground = False
    o.bondLineWidth = 2
    o.padding = 0.08
    o.fixedBondLength = 30
    if gelap:
        o.setBackgroundColour((0.08, 0.09, 0.11, 0))
        o.updateAtomPalette({6: (0.88, 0.9, 0.93), 7: (0.48, 0.66, 1.0), 8: (1.0, 0.45, 0.45),
                             16: (0.95, 0.82, 0.3), 9: (0.55, 0.9, 0.4), 17: (0.4, 0.9, 0.4)})
        o.setSymbolColour((0.88, 0.9, 0.93))
    d.DrawMolecule(m)
    d.FinishDrawing()
    isi = d.GetDrawingText()
    isi = re.sub(r"<\?xml[^>]*>", "", isi)
    isi = re.sub(r"<svg[^>]*>", "", isi, count=1).replace("</svg>", "")
    isi = re.sub(r"<rect[^>]*class='background'[^>]*/>", "", isi)
    ox = (lebar - lw) / 2
    oy = (30 if judul else 0) + (area_h - lh) / 2
    pos = []
    for i in range(m.GetNumAtoms()):
        p = d.GetDrawCoords(i)
        pos.append((p.x + ox, p.y + oy))
    cx = sum(p[0] for p in pos) / len(pos)
    cy = sum(p[1] for p in pos) / len(pos)

    # ---- kelompokkan per residu
    res = {}
    for h in daftar:
        r = res.setdefault(h["residu"], {"resn": h["resn"], "resi": h["resi"], "rantai": h["rantai"], "jenis": [],
                                         "garis": []})
        r["jenis"].append(h["jenis"])
        anchor = [a for a in h.get("anchor", []) if a < len(pos)]
        if not anchor:
            continue
        ax = sum(pos[a][0] for a in anchor) / len(anchor)
        ay = sum(pos[a][1] for a in anchor) / len(anchor)
        r["garis"].append((h["jenis"], (ax, ay), h["jarak"]))
    if not res:
        return _bungkus(lebar, tinggi, latar, transparan, isi, [], [], [], judul, tinta, warna, [], ox, oy)
    R = 27
    # titik penghalang: atom + titik tengah ikatan (lingkaran residu tidak boleh menutupi ligan)
    halang = list(pos) + [((pos[b.GetBeginAtomIdx()][0] + pos[b.GetEndAtomIdx()][0]) / 2,
                           (pos[b.GetBeginAtomIdx()][1] + pos[b.GetEndAtomIdx()][1]) / 2) for b in m.GetBonds()]
    # label atom berhuruf (NH, H2N, OH, Cl) melebar ke samping: lebarnya ikut jadi penghalang
    for a in m.GetAtoms():
        if a.GetAtomicNum() == 6 and not a.GetFormalCharge():
            continue
        x, y = pos[a.GetIdx()]
        lebar_lbl = 12 + (18 if a.GetTotalNumHs() else 0) + (12 if a.GetTotalNumHs() > 1 else 0)
        for f in (1 / 3, 2 / 3, 1.0):
            halang += [(x - lebar_lbl * f, y), (x + lebar_lbl * f, y)]
        halang += [(x - lebar_lbl - 8, y), (x + lebar_lbl + 8, y)]

    def keluar(ax, ay):
        """Arah normal keluar lokal di titik jangkar (menjauhi kerapatan atom ligan)."""
        vx = vy = 0.0
        for x, y in pos:
            dx, dy = ax - x, ay - y
            dd2 = dx * dx + dy * dy
            if dd2 > 1:
                vx += dx / dd2
                vy += dy / dd2
        vx += (ax - cx) * 0.002
        vy += (ay - cy) * 0.002
        n = math.hypot(vx, vy)
        return (vx / n, vy / n) if n > 1e-9 else (math.cos(len(simpul) * 2.4), math.sin(len(simpul) * 2.4))

    simpul = []
    for nama, r in sorted(res.items(), key=lambda kv: URUT_JENIS.index(min(kv[1]["jenis"], key=URUT_JENIS.index))):
        r["utama"] = min(r["jenis"], key=URUT_JENIS.index)
        if r["garis"]:
            ax = sum(g[1][0] for g in r["garis"]) / len(r["garis"])
            ay = sum(g[1][1] for g in r["garis"]) / len(r["garis"])
            ux, uy = keluar(ax, ay)
            # maju sepanjang sinar sampai melewati semua atom ligan yang dekat dengan sinar
            maju = 0.0
            for x, y in halang:
                dx, dy = x - ax, y - ay
                t = dx * ux + dy * uy
                if t > 0 and abs(dx * uy - dy * ux) < R + 14:
                    maju = max(maju, t)
            jauh = maju + R + (26 if r["utama"] != "vdw" else 44)
            tx, ty = ax + ux * jauh, ay + uy * jauh
            r["arah"] = (ux, uy)
        else:
            sud = len(simpul) * 2.4
            tx, ty = cx + (R + 120) * math.cos(sud), cy + (R + 120) * math.sin(sud)
        simpul.append({"nama": nama, "r": r, "x": tx, "y": ty, "tx": tx, "ty": ty})

    # ---- relaksasi: tolak antar residu, jauhi atom ligan, tarik ke posisi ideal
    xmin, xmax = R + 6, lebar - R - 6
    ymin, ymax = (30 if judul else 0) + R + 6, tinggi - leg_h - R - 4
    for it in range(400):
        for s in simpul:
            fx = (s["tx"] - s["x"]) * 0.04
            fy = (s["ty"] - s["y"]) * 0.04
            for t in simpul:
                if t is s:
                    continue
                dx, dy = s["x"] - t["x"], s["y"] - t["y"]
                dd = math.hypot(dx, dy) or 0.01
                if dd < 2 * R + 10:
                    f = (2 * R + 10 - dd) * 0.5
                    fx += dx / dd * f
                    fy += dy / dd * f
            for (x, y) in halang:
                dx, dy = s["x"] - x, s["y"] - y
                dd = math.hypot(dx, dy) or 0.01
                if dd < R + 16:
                    f = (R + 16 - dd) * 0.6
                    fx += dx / dd * f
                    fy += dy / dd * f
            s["x"] = min(xmax, max(xmin, s["x"] + fx))
            s["y"] = min(ymax, max(ymin, s["y"] + fy))
    # koreksi akhir: lingkaran tidak boleh menutupi atom/ikatan ligan
    for s_ in simpul:
        for _ in range(60):
            dekat = min(((math.hypot(s_["x"] - x, s_["y"] - y), x, y) for x, y in halang))
            if dekat[0] >= R + 10:
                break
            ux, uy = s_["r"].get("arah") or ((s_["x"] - cx), (s_["y"] - cy))
            n = math.hypot(ux, uy) or 1
            s_["x"] = min(xmax, max(xmin, s_["x"] + ux / n * 4))
            s_["y"] = min(ymax, max(ymin, s_["y"] + uy / n * 4))

    # ---- gambar
    garis, lingkar, label = [], [], []
    for s in simpul:
        r = s["r"]
        for jenis, (ax, ay), jr in r["garis"]:
            if jenis == "vdw":
                continue
            w = warna[jenis]
            dash = "5,3" if jenis in ("hbond", "halogen", "logam", "garam") else "2,3"
            # garis berhenti di tepi lingkaran residu
            dx, dy = ax - s["x"], ay - s["y"]
            dd = math.hypot(dx, dy) or 1
            x1, y1 = s["x"] + dx / dd * R, s["y"] + dy / dd * R
            garis.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{ax:.1f}" y2="{ay:.1f}" stroke="{w}" '
                         f'stroke-width="1.8" stroke-dasharray="{dash}" stroke-linecap="round"/>')
            if jarak and jenis in ("hbond", "garam", "halogen", "logam", "pi", "pikation"):
                mx, my = (x1 + ax) / 2, (y1 + ay) / 2
                label.append(f'<rect x="{mx - 13:.1f}" y="{my - 7:.1f}" width="26" height="13" rx="2" '
                             f'fill="{latar}" fill-opacity="0.85"/>')
                label.append(f'<text x="{mx:.1f}" y="{my + 3.5:.1f}" font-family="{FONT}" font-size="10" '
                             f'fill="{w}" text-anchor="middle">{jr:.2f}</text>')
        u = r["utama"]
        w = warna[u]
        isi_w = _campur(w, 0.55 if gelap else 0.78, latar)
        lingkar.append(f'<circle cx="{s["x"]:.1f}" cy="{s["y"]:.1f}" r="{R}" fill="{isi_w}" stroke="{w}" '
                       f'stroke-width="{1.2 if u == "vdw" else 1.8}"/>')
        lingkar.append(f'<text x="{s["x"]:.1f}" y="{s["y"] - 2:.1f}" font-family="{FONT}" font-size="11" '
                       f'font-weight="600" fill="{tinta}" text-anchor="middle">{escape(r["resn"])}</text>')
        lingkar.append(f'<text x="{s["x"]:.1f}" y="{s["y"] + 11:.1f}" font-family="{FONT}" font-size="10" '
                       f'fill="{tinta}" text-anchor="middle">{r["resi"]}{escape(r["rantai"])}</text>')
    ada = [j for j in URUT_JENIS if any(j in s["r"]["jenis"] for s in simpul)]
    return _bungkus(lebar, tinggi, latar, transparan, isi, garis, lingkar, label, judul, tinta, warna, ada, ox, oy)


def _bungkus(lebar, tinggi, latar, transparan, isi_lig, garis, lingkar, label, judul, tinta, warna, ada, ox, oy):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{lebar}" height="{tinggi}" '
           f'viewBox="0 0 {lebar} {tinggi}">']
    if not transparan:
        out.append(f'<rect x="0" y="0" width="{lebar}" height="{tinggi}" fill="{latar}"/>')
    if judul:
        out.append(f'<text x="16" y="22" font-family="{FONT}" font-size="14" font-weight="600" '
                   f'fill="{tinta}">{escape(judul)}</text>')
    # urutan lapisan: garis interaksi, ligan, lingkaran residu, label jarak
    out += garis
    out.append(f'<g transform="translate({ox:.1f},{oy:.1f})">{isi_lig}</g>')
    out += lingkar + label
    # legenda
    x, y = 16, tinggi - 20
    for j in ada:
        w = warna[j]
        if j == "vdw":
            out.append(f'<circle cx="{x + 8}" cy="{y - 4}" r="6" fill="{_campur(w, 0.78)}" stroke="{w}"/>')
        else:
            out.append(f'<line x1="{x}" y1="{y - 4}" x2="{x + 18}" y2="{y - 4}" stroke="{w}" stroke-width="2" '
                       f'stroke-dasharray="{"5,3" if j in ("hbond", "halogen", "logam", "garam") else "2,3"}"/>')
        t = NAMA_JENIS[j]
        out.append(f'<text x="{x + 24}" y="{y}" font-family="{FONT}" font-size="11" fill="{tinta}">{escape(t)}</text>')
        x += 34 + int(len(t) * 6.4)
    out.append("</svg>")
    return "\n".join(out)
