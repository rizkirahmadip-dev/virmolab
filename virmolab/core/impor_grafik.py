"""Baca data grafik keluaran program MD dan analisis: XVG (gmx/Grace), CSV/TSV, DAT/TXT berkolom (cpptraj, VMD,
NAMD, MDAnalysis), lalu siapkan seri untuk grafik VirmoLab (konversi satuan, rata-rata bergerak, statistik).

Satuan dikenali dari label sumbu, misalnya "RMSD (nm)" atau "Time (ps)", sehingga nm→Å, ps→ns, dan kJ/mol→kcal/mol
bisa diterapkan tanpa mengubah berkas asli.
"""
import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

EKSTENSI = (".xvg", ".csv", ".tsv", ".dat", ".agr")
KJ_KE_KCAL = 1 / 4.184


class GalatGrafik(Exception):
    pass


@dataclass
class Seri:
    nama: str
    x: list
    y: list
    berkas: str = ""


@dataclass
class DataGrafik:
    judul: str = ""
    label_x: str = ""
    label_y: str = ""
    seri: list = field(default_factory=list)
    berkas: str = ""
    jenis: str = "xy"          # xy | bar


# ------------------------------------------------------------------ teks Grace (XVG)
_YUNANI = {"a": "α", "b": "β", "g": "γ", "d": "δ", "D": "Δ", "e": "ε", "f": "φ", "F": "Φ", "l": "λ", "L": "Λ",
           "m": "μ", "n": "ν", "p": "π", "P": "Π", "r": "ρ", "s": "σ", "S": "Σ", "t": "τ", "q": "θ", "Q": "Θ",
           "w": "ω", "W": "Ω", "c": "χ", "y": "ψ", "Y": "Ψ", "x": "ξ", "h": "η", "k": "κ", "o": "ο", "z": "ζ"}
_ATAS = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
_BAWAH = str.maketrans("0123456789+-", "₀₁₂₃₄₅₆₇₈₉₊₋")


def bersihkan_grace(t):
    """Kode format Grace -> Unicode: \\xD\\f{} -> Δ, \\S2\\N -> ², \\s2\\N -> ₂, sisa kode dibuang."""
    t = re.sub(r"\\x(.)\\f\{\}", lambda m: _YUNANI.get(m.group(1), m.group(1)), t)
    t = re.sub(r"\\x(.)", lambda m: _YUNANI.get(m.group(1), m.group(1)), t)
    t = re.sub(r"\\S(.*?)\\N", lambda m: m.group(1).translate(_ATAS), t)
    t = re.sub(r"\\s(.*?)\\N", lambda m: m.group(1).translate(_BAWAH), t)
    t = re.sub(r"\\f\{[^}]*\}|\\f.|\\[NnuUoO0-9]", "", t)
    return t.replace("\\\\", "\\").strip()


def satuan(label):
    """Satuan dalam kurung terakhir label sumbu: 'RMSD (nm)' -> 'nm'."""
    m = re.findall(r"[\(\[]([^()\[\]]+)[\)\]]", label or "")
    return m[-1].strip() if m else ""


def _ganti_satuan(label, lama, baru):
    if not label:
        return label
    return re.sub(r"([\(\[])\s*" + re.escape(lama) + r"(\s*[\)\]])", r"\g<1>" + baru + r"\2", label)


# ------------------------------------------------------------------ pembaca
def baca_xvg(path):
    teks = Path(path).read_text(encoding="utf-8", errors="replace")
    d = DataGrafik(berkas=str(path))
    legenda, set_data, cur = {}, [], []
    for b in teks.splitlines():
        s = b.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("@"):
            m = re.match(r'@\s*title\s+"(.*)"', s)
            if m:
                d.judul = bersihkan_grace(m.group(1))
            m = re.match(r'@\s*xaxis\s+label\s+"(.*)"', s)
            if m:
                d.label_x = bersihkan_grace(m.group(1))
            m = re.match(r'@\s*yaxis\s+label\s+"(.*)"', s)
            if m:
                d.label_y = bersihkan_grace(m.group(1))
            m = re.match(r'@\s*s(\d+)\s+legend\s+"(.*)"', s)
            if m:
                legenda[int(m.group(1))] = bersihkan_grace(m.group(2))
            m = re.match(r"@\s*TYPE\s+(\w+)", s, re.I)
            if m and m.group(1).lower().startswith("bar"):
                d.jenis = "bar"
            continue
        if s.startswith("&"):
            if cur:
                set_data.append(cur)
            cur = []
            continue
        try:
            cur.append([float(v) for v in s.split()])
        except ValueError:
            continue
    if cur:
        set_data.append(cur)
    if not set_data:
        raise GalatGrafik("Tidak ada data angka di berkas XVG.")
    k = 0
    for blok in set_data:
        n = min(len(r) for r in blok)
        arr = np.array([r[:n] for r in blok], dtype=float)
        if n == 1:
            arr = np.column_stack([np.arange(len(arr)), arr[:, 0]])
            n = 2
        for c in range(1, n):
            if k in legenda:
                nama = legenda[k]
            elif n == 2 and len(set_data) == 1:     # satu seri tanpa legenda: pakai label sumbu y
                nama = re.sub(r"\s*[\(\[][^()\[\]]*[\)\]]\s*$", "", d.label_y) or "Nilai"
            else:
                nama = f"Seri {k + 1}"
            d.seri.append(Seri(nama, arr[:, 0].tolist(), arr[:, c].tolist(), str(path)))
            k += 1
    if not d.judul:
        d.judul = Path(path).stem
    return d


def _pemisah(sampel):
    if "\t" in sampel:
        return "\t"
    baris = [b for b in sampel.splitlines() if b.strip() and not b.lstrip().startswith(("#", "@"))][:20]
    for p in (";", ","):
        if baris and all(p in b for b in baris):
            return p
    return None          # spasi


def baca_tabel(path):
    """CSV/TSV/DAT: kolom pertama = x, kolom lain = seri. Baris kepala (juga '#Frame RMSD' gaya cpptraj) memberi
    nama kolom; desimal koma dikenali bila pemisah titik koma."""
    teks = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    pem = _pemisah(teks[:20000])
    kepala, data = None, []
    komentar_terakhir = None
    for b in teks.splitlines():
        s = b.strip()
        if not s:
            continue
        if s.startswith(("#", "@", ";", "!")):
            komentar_terakhir = s.lstrip("#@;! ").strip()
            continue
        if pem is None:
            sel = s.split()
        else:
            sel = next(csv.reader(io.StringIO(s), delimiter=pem))
        sel = [x.strip() for x in sel]
        nilai = []
        for x in sel:
            x2 = x.replace(",", ".") if pem == ";" else x
            try:
                nilai.append(float(x2))
            except ValueError:
                nilai.append(None)
        if all(v is None for v in nilai) and kepala is None and not data:
            kepala = sel
            continue
        if any(v is None for v in nilai) or len(nilai) < 1:
            continue
        data.append(nilai)
    if not data:
        raise GalatGrafik("Tidak ada baris angka di berkas.")
    if kepala is None and komentar_terakhir:
        calon = komentar_terakhir.split() if pem is None else [x.strip() for x in komentar_terakhir.split(pem)]
        if len(calon) == len(data[0]):
            kepala = calon
    n = min(len(r) for r in data)
    arr = np.array([r[:n] for r in data], dtype=float)
    if n == 1:
        arr = np.column_stack([np.arange(1, len(arr) + 1), arr[:, 0]])
        kepala = ["Indeks"] + (kepala or ["Nilai"])
        n = 2
    kepala = (kepala or [])[:n] + [f"Kolom {i + 1}" for i in range(len(kepala or []), n)]
    d = DataGrafik(judul=Path(path).stem, label_x=kepala[0], label_y=kepala[1] if n == 2 else "", berkas=str(path))
    for c in range(1, n):
        d.seri.append(Seri(kepala[c], arr[:, 0].tolist(), arr[:, c].tolist(), str(path)))
    return d


def baca(path):
    ext = Path(path).suffix.lower()
    if ext in (".xvg", ".agr"):
        return baca_xvg(path)
    return baca_tabel(path)


# ------------------------------------------------------------------ olah
def rata_bergerak(y, jendela):
    """Rata-rata bergerak terpusat; tepi memakai jendela yang menyempit (panjang seri tetap)."""
    y = np.asarray(y, dtype=float)
    if jendela <= 1 or len(y) < 3:
        return y.tolist()
    w = int(min(jendela, len(y)))
    k = np.ones(w)
    jumlah = np.convolve(y, k, mode="same")
    n = np.convolve(np.ones_like(y), k, mode="same")
    return (jumlah / n).tolist()


def statistik(y):
    """Rerata, SD, min, maks seluruh seri dan rerata ± SD paruh kedua (lazim untuk RMSD/Rg setelah ekuilibrasi)."""
    v = np.asarray(y, dtype=float)
    v = v[np.isfinite(v)]
    if not len(v):
        return {}
    h = v[len(v) // 2:]
    return {"n": int(len(v)), "rerata": float(v.mean()), "sd": float(v.std(ddof=1)) if len(v) > 1 else 0.0,
            "min": float(v.min()), "maks": float(v.max()), "rerata_2": float(h.mean()),
            "sd_2": float(h.std(ddof=1)) if len(h) > 1 else 0.0}


def konversi_tersedia(d):
    """Konversi yang masuk akal untuk data ini: {'x_ns', 'y_A', 'y_kcal', 'y_A2'} -> bool."""
    sx, sy = satuan(d.label_x).lower(), satuan(d.label_y).lower()
    return {"x_ns": sx == "ps", "y_A": sy == "nm", "y_A2": sy in ("nm²", "nm^2", "nm2", "nm\\s2\\n"),
            "y_kcal": sy in ("kj/mol", "kj mol⁻¹", "kj mol-1")}


def terapkan(d, x_ns=False, y_A=False, y_A2=False, y_kcal=False, jendela=1):
    """DataGrafik baru dengan konversi satuan dan rata-rata bergerak; label sumbu ikut diganti."""
    fx = 1 / 1000.0 if x_ns else 1.0
    fy = 10.0 if y_A else 100.0 if y_A2 else KJ_KE_KCAL if y_kcal else 1.0
    lx, ly = d.label_x, d.label_y
    if x_ns:
        lx = _ganti_satuan(lx, satuan(lx), "ns")
    if y_A:
        ly = _ganti_satuan(ly, satuan(ly), "Å")
    elif y_A2:
        ly = _ganti_satuan(ly, satuan(ly), "Å²")
    elif y_kcal:
        ly = _ganti_satuan(ly, satuan(ly), "kcal/mol")
    seri = []
    for s in d.seri:
        y = (np.asarray(s.y, float) * fy).tolist()
        seri.append(Seri(s.nama, (np.asarray(s.x, float) * fx).tolist(), rata_bergerak(y, jendela), s.berkas))
    return DataGrafik(d.judul, lx, ly, seri, d.berkas, d.jenis)


def csv_teks(seri, label_x="x"):
    """Seri (bisa beda panjang/x) -> CSV lebar: x tiap seri berdampingan dengan y-nya."""
    kepala, kolom = [], []
    for s in seri:
        kepala += [f"{s.nama} {label_x}".strip(), s.nama]
        kolom += [s.x, s.y]
    n = max((len(c) for c in kolom), default=0)
    baris = [",".join('"' + k.replace('"', "'") + '"' for k in kepala)]
    for i in range(n):
        baris.append(",".join(f"{c[i]:.6g}" if i < len(c) else "" for c in kolom))
    return "\n".join(baris) + "\n"
