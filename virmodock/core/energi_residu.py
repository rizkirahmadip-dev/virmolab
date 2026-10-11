"""Sumbangan tiap residu pada skor Vina antarmolekul, dan pemindaian alanin pada fungsi skor yang sama.

Ini bukan MM/GBSA. MM/GBSA total tetap dihitung di modul MD. Angka di sini menjawab pertanyaan
“residu mana yang menopang skor pose ini”, dalam hitungan detik, dengan fungsi yang sama seperti
pewarnaan kontribusi per atom.
"""
from .kontribusi import BOBOT, BATAS, R_VDW, baca_pdbqt, per_atom, _tipe_xs
import numpy as np

TULANG = {"N", "CA", "C", "O", "CB", "OXT"}


def per_residu(teks_reseptor, teks_ligan):
    """[{residu, energi}] energi Vina antarmolekul yang dibebankan ke residu reseptor, plus total."""
    rec, lig = baca_pdbqt(teks_reseptor), baca_pdbqt(teks_ligan)
    tl, xl = _tipe_xs(lig)
    if not tl:
        return [], 0.0
    pl = xl[[t[0] for t in tl]]
    xr_semua = np.array([a[2] for a in rec], float)
    dekat = np.where(np.linalg.norm(xr_semua[:, None, :] - pl[None, :, :], axis=2).min(axis=1) <= BATAS + 2.5)[0]
    rec_d = [rec[i] for i in dekat]
    tr, xr = _tipe_xs(rec_d)
    if not tr:
        return [], 0.0
    pr = xr[[t[0] for t in tr]]
    Rl = np.array([R_VDW[t[1]] for t in tl])
    Rr = np.array([R_VDW[t[1]] for t in tr])
    r = np.linalg.norm(pl[:, None, :] - pr[None, :, :], axis=2)
    d = r - Rl[:, None] - Rr[None, :]
    dalam = r < BATAS

    def b(daftar, k):
        return np.array([t[k] for t in daftar], dtype=bool)

    hl = b(tl, 2)[:, None] & b(tr, 2)[None, :]
    hf = np.where(d < 0.5, 1.0, np.where(d < 1.5, 1.5 - d, 0.0)) * hl
    dl, al, dr, ar = b(tl, 3), b(tl, 4), b(tr, 3), b(tr, 4)
    pas = (dl[:, None] & ar[None, :]) | (al[:, None] & dr[None, :])
    hb = np.where(d < -0.7, 1.0, np.where(d < 0, -d / 0.7, 0.0)) * pas
    suku = {"gauss1": np.exp(-(d / 0.5) ** 2), "gauss2": np.exp(-((d - 3.0) / 2.0) ** 2),
            "repulsi": np.where(d < 0, d * d, 0.0), "hidrofobik": hf, "hbond": hb}
    pasangan = sum((v * dalam) * BOBOT[k] for k, v in suku.items())
    tot = {}
    for j, t in enumerate(tr):
        label = rec_d[t[0]][3]
        tot[label] = tot.get(label, 0.0) + float(pasangan[:, j].sum())
    daftar = [{"residu": k, "energi": round(v, 3)} for k, v in sorted(tot.items(), key=lambda kv: kv[1])]
    return daftar, round(sum(tot.values()), 3)


def _buang_samping(teks, label):
    """Ala virtual: buang atom rantai samping residu `label` (selain CB)."""
    baris = []
    for b in teks.splitlines():
        if b.startswith(("ATOM", "HETATM")) and len(b) >= 26:
            lab = f"{b[17:20].strip()} {b[22:26].strip()} {b[21].strip()}".strip()
            if lab == label and b[12:16].strip() not in TULANG and not b[12:16].strip().startswith("H"):
                continue
        baris.append(b)
    return "\n".join(baris) + "\n"


def alanin(teks_reseptor, teks_ligan, maks=12):
    """Pemindaian alanin pada skor Vina. delta = skor tanpa rantai samping − skor semula.

    Delta positif: residu itu menguntungkan (menghapusnya memperburuk skor). Maksimal `maks` residu
    dengan sumbangan paling negatif.
    """
    residu, _ = per_residu(teks_reseptor, teks_ligan)
    _, e0 = per_atom(teks_reseptor, teks_ligan)
    sasaran = [r for r in residu if r["energi"] < -0.05][:maks]
    hasil = []
    for r in sasaran:
        _, e1 = per_atom(_buang_samping(teks_reseptor, r["residu"]), teks_ligan)
        delta = round(e1 - e0, 3)
        hasil.append({"residu": r["residu"], "sumbangan": r["energi"], "delta_alanin": delta,
                      "makna": "menguntungkan" if delta > 0.2 else ("merugikan" if delta < -0.2 else "kecil")})
    return hasil
