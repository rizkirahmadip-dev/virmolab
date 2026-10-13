"""Uji core/graf.py: graf 10 simpul -> SVG valid (xml.etree parse), GraphML bisa dibaca ulang
networkx, dan ekspor CSV tepi.

Jalankan:
  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/uji_graf.py
"""
import csv
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

AKAR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR))

import networkx as nx
from virmodock.core.graf import ekspor_csv_tepi, ekspor_graphml, svg_graf, tata_letak

OUT = AKAR / "dev" / "uji" / "graf"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)

gagal = []


def cek(kondisi, pesan):
    print(("OK    " if kondisi else "GAGAL ") + pesan, flush=True)
    if not kondisi:
        gagal.append(pesan)


def main():
    # 1. Buat graf 10 simpul dengan networkx
    G = nx.Graph()
    for i in range(1, 11):
        G.add_node(f"P{i}", label=f"Protein {i}", jenis="target", derajat=i)

    # Tambah tepi interaksi (siklus + beberapa koneksi lintas)
    for i in range(1, 10):
        G.add_edge(f"P{i}", f"P{i+1}", bobot=0.8, jenis="ppi")
    G.add_edge("P10", "P1", bobot=0.9, jenis="ppi")
    G.add_edge("P1", "P5", bobot=0.6, jenis="ppi")
    G.add_edge("P3", "P8", bobot=0.7, jenis="ppi")

    cek(len(G.nodes()) == 10, f"graf memiliki 10 simpul: {len(G.nodes())}")
    cek(len(G.edges()) == 12, f"graf memiliki 12 tepi: {len(G.edges())}")

    # 2. Uji tata letak spring dan kk
    pos_spring = tata_letak(G, metode="spring", benih=42)
    cek(len(pos_spring) == 10 and all(len(v) == 2 for v in pos_spring.values()),
        "tata_letak 'spring' mengembalikan posisi 2D untuk semua 10 simpul")

    pos_kk = tata_letak(G, metode="kk", benih=42)
    cek(len(pos_kk) == 10 and all(len(v) == 2 for v in pos_kk.values()),
        "tata_letak 'kk' (Kamada-Kawai) mengembalikan posisi 2D untuk semua 10 simpul")

    # 3. Uji generasi SVG (tema terang dan gelap)
    svg_terang = svg_graf(
        G, posisi=pos_spring,
        warna_simpul={"P1": "#e53e3e", "P2": "#3182ce"},
        ukuran_simpul={"P1": 18.0},
        label=True,
        lebar=900, tinggi=650,
        tema="terang"
    )
    cek(svg_terang.startswith("<svg") and svg_terang.endswith("</svg>"),
        "svg_graf menghasilkan dokumen SVG dengan tag pembuka dan penutup")

    # Uji validitas XML SVG dengan xml.etree
    try:
        akar_xml = ET.fromstring(svg_terang)
        cek(akar_xml.tag.endswith("svg"), f"SVG terurai sebagai XML valid: tag akar <{akar_xml.tag}>")
    except Exception as e:
        cek(False, f"SVG gagal di-parse sebagai XML: {e}")

    # Uji SVG tema gelap
    svg_gelap = svg_graf(G, tema="gelap")
    try:
        akar_gelap = ET.fromstring(svg_gelap)
        cek(akar_gelap.tag.endswith("svg"), "SVG tema gelap terurai sebagai XML valid")
    except Exception as e:
        cek(False, f"SVG tema gelap gagal di-parse: {e}")

    # Simpan SVG ke berkas uji untuk dokumentasi
    (OUT / "graf_terang.svg").write_text(svg_terang, encoding="utf-8")
    (OUT / "graf_gelap.svg").write_text(svg_gelap, encoding="utf-8")

    # 4. Uji ekspor dan pembacaan ulang GraphML
    jalur_graphml = OUT / "jaringan.graphml"
    ekspor_graphml(G, jalur_graphml)
    cek(jalur_graphml.exists() and jalur_graphml.stat().st_size > 0, "berkas GraphML berhasil dibuat")

    G_baca = nx.read_graphml(str(jalur_graphml))
    cek(len(G_baca.nodes()) == 10, f"GraphML dibaca ulang memiliki 10 simpul: {len(G_baca.nodes())}")
    cek(len(G_baca.edges()) == 12, f"GraphML dibaca ulang memiliki 12 tepi: {len(G_baca.edges())}")
    cek(G_baca.nodes["P1"].get("label") == "Protein 1", "atribut simpul tersimpan dan pulih dari GraphML")

    # 5. Uji ekspor CSV tepi
    jalur_csv = OUT / "tepi.csv"
    ekspor_csv_tepi(G, jalur_csv)
    cek(jalur_csv.exists() and jalur_csv.stat().st_size > 0, "berkas CSV tepi berhasil dibuat")

    with open(jalur_csv, "r", encoding="utf-8") as f:
        pembaca = list(csv.reader(f))
        header = pembaca[0]
        baris_data = pembaca[1:]
        cek("sumber" in header and "target" in header, f"header CSV memiliki kolom sumber dan target: {header}")
        cek(len(baris_data) == 12, f"jumlah baris data CSV sesuai jumlah tepi: {len(baris_data)}")

    print("GAGAL" if gagal else "LULUS", len(gagal), flush=True)
    sys.exit(1 if gagal else 0)


if __name__ == "__main__":
    main()
