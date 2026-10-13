"""Modul graf dan visualisasi jaringan untuk farmakologi jaringan dan PPI.

Menyediakan:
- Perhitungan tata letak (spring, Kamada-Kawai) menggunakan NetworkX.
- Ekspor SVG graf murni dengan token tema terang/gelap (tanpa matplotlib/plotly).
- Ekspor berkas GraphML (standar Cytoscape / Gephi).
- Ekspor berkas CSV tepi interaksi.
"""

import csv
from pathlib import Path
from xml.sax.saxutils import escape

import networkx as nx

FONT = "Segoe UI, Arial, Helvetica, sans-serif"

# Token tema untuk visualisasi graf
TEMA_GRAF = {
    "terang": {
        "latar": "#ffffff",
        "tepi": "#b0b8c4",
        "tepi_aktif": "#2b6fd6",
        "teks": "#1b2430",
        "simpul_bawaan": "#2b6fd6",
        "stroke_simpul": "#ffffff",
    },
    "gelap": {
        "latar": "#14171c",
        "tepi": "#465263",
        "tepi_aktif": "#4d8cee",
        "teks": "#e2e6ed",
        "simpul_bawaan": "#4d8cee",
        "stroke_simpul": "#1e232b",
    }
}


def tata_letak(G: nx.Graph, metode: str = "spring", benih: int = 1) -> dict:
    """Hitung posisi (x, y) simpul graf dalam rentang normalisasi [-1, 1].

    Parameter:
    - G: networkx.Graph
    - metode: 'spring' (Fruchterman-Reingold) atau 'kk' (Kamada-Kawai)
    - benih: integer random seed untuk reprodusibilitas
    """
    if len(G) == 0:
        return {}
    if len(G) == 1:
        simpul = list(G.nodes())[0]
        return {simpul: (0.0, 0.0)}

    if metode == "kk":
        try:
            return nx.kamada_kawai_layout(G)
        except Exception:
            # Fallback ke spring bila graf tidak terhubung atau ada kendala matriks jarak
            return nx.spring_layout(G, seed=benih)
    return nx.spring_layout(G, seed=benih)


def svg_graf(G: nx.Graph, posisi: dict | None = None, warna_simpul: dict | str | None = None,
             ukuran_simpul: dict | float | None = None, label: dict | bool | None = True,
             lebar: int = 800, tinggi: int = 600, tema: str = "terang") -> str:
    """Hasilkan string dokumen SVG valid untuk visualisasi graf jaringan.

    Parameter:
    - G: networkx.Graph
    - posisi: dict {node: (x, y)} (bila None, dihitung dengan tata_letak)
    - warna_simpul: dict {node: '#hex'} atau string warna tunggal
    - ukuran_simpul: dict {node: radius_px} atau float radius bawaan (bawaan 12.0)
    - label: bool (tampilkan nama simpul) atau dict {node: 'teks_label'}
    - lebar, tinggi: dimensi piksel SVG
    - tema: 'terang' atau 'gelap'
    """
    t = TEMA_GRAF.get(tema, TEMA_GRAF["terang"])
    if posisi is None:
        posisi = tata_letak(G, metode="spring", benih=1)

    # Margin kanvas
    pad_x, pad_y = 60.0, 50.0
    w_efektif = lebar - 2 * pad_x
    h_efektif = tinggi - 2 * pad_y

    # Cari rentang koordinat asli
    xs = [coord[0] for coord in posisi.values()] or [0.0]
    ys = [coord[1] for coord in posisi.values()] or [0.0]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    rentang_x = max(max_x - min_x, 1e-6)
    rentang_y = max(max_y - min_y, 1e-6)

    def ke_px(coord):
        px = pad_x + ((coord[0] - min_x) / rentang_x) * w_efektif
        # Invert sumbu Y agar orientasi alami
        py = pad_y + (1.0 - (coord[1] - min_y) / rentang_y) * h_efektif
        return px, py

    pos_px = {node: ke_px(coord) for node, coord in posisi.items()}

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{lebar}" height="{tinggi}" viewBox="0 0 {lebar} {tinggi}">',
        f'<rect width="{lebar}" height="{tinggi}" fill="{t["latar"]}"/>'
    ]

    # 1. Gambar tepi (edges)
    out.append('<g class="edges">')
    for u, v, d in G.edges(data=True):
        if u not in pos_px or v not in pos_px:
            continue
        x1, y1 = pos_px[u]
        x2, y2 = pos_px[v]
        bobot = float(d.get("bobot", d.get("weight", 1.0)))
        tebal = max(0.8, min(4.0, 0.8 + bobot * 1.5))
        warna_tepi = d.get("warna", t["tepi"])
        out.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{warna_tepi}" stroke-width="{tebal:.2f}" stroke-opacity="0.6"/>'
        )
    out.append('</g>')

    # 2. Gambar simpul (nodes)
    out.append('<g class="nodes">')
    for node in G.nodes():
        if node not in pos_px:
            continue
        cx, cy = pos_px[node]
        # Tentukan radius
        if isinstance(ukuran_simpul, dict):
            r = float(ukuran_simpul.get(node, 12.0))
        elif isinstance(ukuran_simpul, (int, float)):
            r = float(ukuran_simpul)
        else:
            # Otomatis proporsional derajat simpul
            derajat = G.degree(node)
            r = max(8.0, min(28.0, 8.0 + (derajat ** 0.5) * 3.5))

        # Tentukan warna simpul
        if isinstance(warna_simpul, dict):
            warna = warna_simpul.get(node, t["simpul_bawaan"])
        elif isinstance(warna_simpul, str):
            warna = warna_simpul
        else:
            warna = G.nodes[node].get("warna", t["simpul_bawaan"])

        out.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
            f'fill="{warna}" stroke="{t["stroke_simpul"]}" stroke-width="1.8"/>'
        )
    out.append('</g>')

    # 3. Gambar label teks simpul
    if label:
        out.append('<g class="labels">')
        for node in G.nodes():
            if node not in pos_px:
                continue
            cx, cy = pos_px[node]
            if isinstance(label, dict):
                teks = str(label.get(node, node))
            else:
                teks = str(G.nodes[node].get("label", node))

            # Hitung offset vertikal agar berada di bawah atau di samping simpul
            if isinstance(ukuran_simpul, dict):
                r = float(ukuran_simpul.get(node, 12.0))
            elif isinstance(ukuran_simpul, (int, float)):
                r = float(ukuran_simpul)
            else:
                derajat = G.degree(node)
                r = max(8.0, min(28.0, 8.0 + (derajat ** 0.5) * 3.5))

            ty = cy + r + 13.0
            out.append(
                f'<text x="{cx:.1f}" y="{ty:.1f}" font-family="{FONT}" font-size="11" '
                f'font-weight="500" fill="{t["teks"]}" text-anchor="middle">{escape(teks)}</text>'
            )
        out.append('</g>')

    out.append('</svg>')
    return "\n".join(out)


def ekspor_graphml(G: nx.Graph, path: str | Path):
    """Ekspor graf ke berkas format GraphML (.graphml) untuk Cytoscape/Gephi."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    # Pastikan tipe data atribut bersih untuk GraphML
    G_bersih = G.copy()
    for n, d in G_bersih.nodes(data=True):
        for k, v in list(d.items()):
            if isinstance(v, (list, dict, set)):
                d[k] = str(v)
    for u, v, d in G_bersih.edges(data=True):
        for k, val in list(d.items()):
            if isinstance(val, (list, dict, set)):
                d[k] = str(val)
    nx.write_graphml(G_bersih, str(p), encoding="utf-8")


def ekspor_csv_tepi(G: nx.Graph, path: str | Path):
    """Ekspor daftar tepi (edges) ke berkas CSV standar (sumber, target, bobot, jenis)."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    semua_kunci = set()
    for _, _, d in G.edges(data=True):
        semua_kunci.update(d.keys())

    kunci_urut = [k for k in ["bobot", "weight", "jenis", "tipe", "skor", "score"] if k in semua_kunci]
    sisa_kunci = sorted(k for k in semua_kunci if k not in kunci_urut)
    kolom = ["sumber", "target"] + kunci_urut + sisa_kunci

    with open(p, "w", encoding="utf-8", newline="") as f:
        penulis = csv.writer(f)
        penulis.writerow(kolom)
        for u, v, d in G.edges(data=True):
            baris = [str(u), str(v)]
            for k in kunci_urut + sisa_kunci:
                baris.append(str(d.get(k, "")))
            penulis.writerow(baris)
