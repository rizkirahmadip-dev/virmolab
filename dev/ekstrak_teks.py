"""Ekstrak teks UI (literal & f-string) dari kode untuk kamus terjemahan virmodock/i18n/en.json.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe dev/ekstrak_teks.py
Keluaran: dev/i18n_teks_baru.json {"literal": [...], "pola": [...]} — hanya teks yang BELUM ada di kamus.
Terjemahan teks baru ditulis ke dev/i18n_tambahan.json (BUKAN i18n_teks.json: berkas itu dipasangkan per indeks
dengan i18n_b*/p*.json oleh buat_kamus.py — menimpanya membuat terjemahan salah pasang).
f-string -> pola dengan {0}, {1}, … untuk bagian dinamis.
"""
import ast
import json
import re
from pathlib import Path

BERKAS = sorted(Path("virmodock/ui").glob("*.py")) + [Path(f"virmodock/core/{n}.py") for n in (
    "statistik", "analisis", "kemiripan", "admet", "protonasi", "periksa_protein", "sifat", "grafik", "grafik_uji",
    "uji", "pustaka", "chembl", "env", "qc", "konsensus", "ujimandiri", "mesin", "prep_reseptor", "prep_ligan",
    "molekul", "laporan", "ekspor", "p2rank", "pindah", "proyek", "antrean", "alphafold")]
LEWATI_FUNGSI = {"value", "setValue", "contains", "remove", "findData", "get", "setdefault", "pop", "startswith",
                 "endswith", "split", "replace", "join", "strip", "rstrip", "lstrip", "objectName", "setObjectName",
                 "js", "runJavaScript", "setProperty", "property", "getattr", "hasattr", "setStyleSheet", "format",
                 "Path", "p", "glob", "open", "re", "compile", "match", "search", "sub", "fullmatch", "index",
                 "encode", "decode", "lower", "upper", "write_text", "read_text", "mkdir", "with_suffix", "emit_raw"}
INDO = re.compile(r"\b(dan|yang|untuk|dari|atau|tidak|ligan|dengan|pada|belum|di|ke|ini|bila|semua|hasil|"
                  r"pilih|simpan|buka|tampilkan|jumlah|grafik|uji|data|nama|berkas|proyek|kotak|warna|ukuran|"
                  r"gambar|ekspor|impor|siapkan|jalankan|langkah|batal|tutup|lanjut|kembali|hitung|cari|salin|"
                  r"tambah|hapus|atur|sembunyikan|mesin|perangkat|reseptor|protein|interaksi|residu|pose|rantai|"
                  r"kantong|laporan|peringatan|galat|gagal|selesai|berhasil|sedang|menunggu|kemiripan|sifat|"
                  r"bawaan|otomatis|lanjutan|ketelitian|area|panel|tema|terang|gelap|bantuan|panduan|alat|"
                  r"analisis|statistik|rerata|median|sebaran|korelasi|kelompok|sumbu|judul|label|nilai|"
                  r"perkiraan|ikatan|hidrofobik|muatan|air|logam|ion|baku|terpilih|aktif|ditemukan|dibuka|"
                  r"tersimpan|disimpan|diekspor|dibuat|dihapus|baru|lama|kosong|penuh|besar|kecil|tinggi|"
                  r"rendah|baik|buruk|benar|salah|ya|teratas|terbaik|terendah|tertinggi|minimal|maksimal|"
                  r"kolom|baris|tabel|lembar|halaman|jendela|tampilan|gaya|representasi|permukaan)\b", re.I)


def kunci_teks(s):
    s = s.strip()
    return s and len(s) > 1 and re.search(r"[A-Za-zÀ-ɏ]{2}", s) and (INDO.search(s) or (
        re.match(r"^[A-Z]", s) and " " in s) or re.match(r"^[A-Z][a-zé]+[…:]?$", s))


def bukan_kode(s):
    return not (re.match(r"^[a-z_0-9.]+$", s) or s.startswith(("<svg", "<?xml", "QWidget", "QPushButton", "#", "rgba(",
                                                                 "font-", "background", "border", "{", "http", "M ", "m "))
                or "{" in s and "}" in s and ":" in s and ";" in s or s.count("\\") > 2)


def pola_f(node):
    """f-string -> (teks pola dengan {0},{1}…), atau None bila tidak bermakna sebagai teks UI."""
    bag, n = [], 0
    for v in node.values:
        if isinstance(v, ast.Constant):
            bag.append(str(v.value).replace("{", "{{").replace("}", "}}"))
        else:
            bag.append("{" + str(n) + "}")
            n += 1
    t = "".join(bag)
    lit = re.sub(r"\{\d+\}", " ", t)
    return t if kunci_teks(lit) and bukan_kode(lit) and len(lit.strip()) > 3 else None


def main():
    kamus = {}
    p_en = Path("virmodock/i18n/en.json")
    if p_en.exists():
        d = json.loads(p_en.read_text(encoding="utf-8"))
        kamus = {**d.get("teks", {}), **d.get("pola", {})}
    lit, pol = {}, {}
    for f in BERKAS:
        if not f.exists():
            continue
        pohon = ast.parse(f.read_text(encoding="utf-8"))
        induk = {}
        for node in ast.walk(pohon):
            for c in ast.iter_child_nodes(node):
                induk[c] = node
        for node in ast.walk(pohon):
            if isinstance(node, ast.JoinedStr):
                t = pola_f(node)
                if t and t not in kamus:
                    pol.setdefault(t, f.name)
                continue
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if isinstance(induk.get(node), ast.JoinedStr):
                continue
            s = node.value
            par = induk.get(node)
            if isinstance(par, ast.Call) and isinstance(par.func, ast.Attribute) and par.func.attr in LEWATI_FUNGSI:
                continue
            if isinstance(par, ast.Compare) or isinstance(par, ast.Subscript):
                continue
            if isinstance(par, ast.Expr):        # docstring
                continue
            if kunci_teks(s) and bukan_kode(s) and s not in kamus and len(s) < 900:
                lit.setdefault(s, f.name)
    keluar = {"literal": sorted(lit, key=lambda x: (lit[x], x)), "pola": sorted(pol, key=lambda x: (pol[x], x))}
    Path("dev/i18n_teks_baru.json").write_text(json.dumps(keluar, ensure_ascii=False, indent=0), encoding="utf-8")
    print(len(keluar["literal"]), "literal,", len(keluar["pola"]), "pola;",
          sum(map(len, keluar["literal"])) + sum(map(len, keluar["pola"])), "karakter")


main()
