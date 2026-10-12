"""Kontribusi energi per atom ligan (fungsi skor AutoDock Vina, suku antarmolekul).

Vina 1.2 tidak lagi punya `--atom_terms`, jadi suku Vina dihitung ulang di sini dengan NumPy:
tipe atom XS dari tipe AutoDock (PDBQT) + ikatan dari jarak kovalen, jarak permukaan d = r − R1 − R2,
lalu gauss1, gauss2, repulsi, hidrofobik, dan ikatan H dengan bobot Vina (Trott & Olson 2010), batas 8 Å.
Tiap pasangan ligan-reseptor dibebankan penuh ke atom ligan. Jumlah semua atom ≈ "Final Intermolecular
Energy" `vina --score_only` (selisih kecil karena Vina memakai interpolasi grid).
Nilai negatif = menguntungkan (hijau), positif = merugikan (merah).
"""
import numpy as np

BOBOT = {"gauss1": -0.035579, "gauss2": -0.005156, "repulsi": 0.840245, "hidrofobik": -0.035069, "hbond": -0.587439}
BATAS = 8.0
R_VDW = {"C": 1.9, "N": 1.8, "O": 1.7, "S": 2.0, "P": 2.1, "F": 1.5, "Cl": 1.8, "Br": 2.0, "I": 2.2, "Met": 1.2}
R_KOV = {"H": 0.37, "C": 0.77, "N": 0.75, "O": 0.73, "S": 1.02, "P": 1.06, "F": 0.71, "Cl": 0.99, "Br": 1.14,
         "I": 1.33, "Met": 1.2}
LOGAM = {"Mg", "Mn", "Zn", "Ca", "Fe", "Cu", "Co", "Ni", "Na", "K", "MG", "MN", "ZN", "CA", "FE", "CU"}


def _unsur(ad):
    if ad in ("C", "A"):
        return "C"
    if ad in ("N", "NA", "NS"):
        return "N"
    if ad in ("O", "OA", "OS"):
        return "O"
    if ad in ("S", "SA"):
        return "S"
    if ad in ("H", "HD", "HS"):
        return "H"
    if ad in ("CL", "Cl"):
        return "Cl"
    if ad in ("BR", "Br"):
        return "Br"
    if ad in LOGAM:
        return "Met"
    return ad if ad in R_VDW else None


def baca_pdbqt(teks):
    """[(nama, tipe AD, xyz, label residu)] dari baris ATOM/HETATM PDBQT (model pertama)."""
    out = []
    for b in teks.splitlines():
        if b.startswith("ENDMDL"):
            break
        if b.startswith(("ATOM", "HETATM")) and len(b) >= 78:
            ad = b[77:79].strip() or b[76:79].strip()
            out.append((b[12:16].strip(), ad, (float(b[30:38]), float(b[38:46]), float(b[46:54])),
                        f"{b[17:20].strip()} {b[22:26].strip()} {b[21].strip()}".strip()))
    return out


def _tipe_xs(atom):
    """atom: hasil baca_pdbqt. Kembalikan (unsur, hidrofobik, donor, akseptor, xyz) untuk atom berat."""
    el = [_unsur(a[1]) for a in atom]
    xyz = np.array([a[2] for a in atom], float) if atom else np.zeros((0, 3))
    n = len(atom)
    rk = np.array([R_KOV.get(e or "C", 0.77) for e in el])
    # ikatan dari jarak (blok agar memori kecil)
    tetangga = [[] for _ in range(n)]
    for i0 in range(0, n, 512):
        d = np.linalg.norm(xyz[i0:i0 + 512, None, :] - xyz[None, :, :], axis=2)
        batas = 1.1 * (rk[i0:i0 + 512, None] + rk[None, :])
        for i, j in zip(*np.where((d < batas) & (d > 0.01))):
            tetangga[i0 + i].append(j)
    hasil = []
    for i, a in enumerate(atom):
        e = el[i]
        if e in (None, "H"):
            continue
        ad = a[1]
        ada_hd = any(atom[j][1] == "HD" for j in tetangga[i])
        hetero = any(el[j] not in ("C", "H", None) for j in tetangga[i])
        hid = don = aks = False
        if e == "C":
            hid = not hetero
        elif e == "N":
            aks = ad in ("NA", "NS")
            don = ada_hd
        elif e == "O":
            aks = True
            don = ada_hd
        elif e in ("F", "Cl", "Br", "I"):
            hid = True
        elif e == "Met":
            don = True
        hasil.append((i, e, hid, don, aks))
    return hasil, xyz


def per_atom(teks_reseptor, teks_ligan):
    """Kontribusi per atom berat ligan. Kembalikan (daftar dict, total kcal/mol).
    dict: indeks (urutan atom PDBQT ligan), nama, energi, suku {gauss1, gauss2, repulsi, hidrofobik, hbond}."""
    rec, lig = baca_pdbqt(teks_reseptor), baca_pdbqt(teks_ligan)
    tl, xl = _tipe_xs(lig)
    if not tl:
        return [], 0.0
    pl = xl[[t[0] for t in tl]]
    # reseptor: hanya atom dalam 8 Å + 2 Å dari ligan (tipe XS butuh tetangga, jadi seleksi dulu lalu tipe)
    xr_semua = np.array([a[2] for a in rec], float)
    dekat = np.where(np.linalg.norm(xr_semua[:, None, :] - pl[None, :, :], axis=2).min(axis=1) <= BATAS + 2.5)[0]
    rec_d = [rec[i] for i in dekat]
    tr, xr = _tipe_xs(rec_d)
    if not tr:   # ligan jauh dari reseptor: semua kontribusi nol
        return [{"indeks": t[0], "nama": lig[t[0]][0], "unsur": t[1], "energi": 0.0, "suku": {s: 0.0 for s in BOBOT},
                 "xyz": [round(float(v), 3) for v in pl[k]]} for k, t in enumerate(tl)], 0.0
    pr = xr[[t[0] for t in tr]]
    Rl = np.array([R_VDW[t[1]] for t in tl])
    Rr = np.array([R_VDW[t[1]] for t in tr])
    r = np.linalg.norm(pl[:, None, :] - pr[None, :, :], axis=2)
    d = r - Rl[:, None] - Rr[None, :]
    dalam = r < BATAS
    g1 = np.exp(-(d / 0.5) ** 2)
    g2 = np.exp(-((d - 3.0) / 2.0) ** 2)
    rep = np.where(d < 0, d * d, 0.0)
    b = lambda daftar, k: np.array([t[k] for t in daftar], dtype=bool)
    hl = b(tl, 2)[:, None] & b(tr, 2)[None, :]
    hf = np.where(d < 0.5, 1.0, np.where(d < 1.5, 1.5 - d, 0.0)) * hl
    dl, al, dr, ar = b(tl, 3), b(tl, 4), b(tr, 3), b(tr, 4)
    pas = (dl[:, None] & ar[None, :]) | (al[:, None] & dr[None, :])
    hb = np.where(d < -0.7, 1.0, np.where(d < 0, -d / 0.7, 0.0)) * pas
    suku = {"gauss1": g1, "gauss2": g2, "repulsi": rep, "hidrofobik": hf, "hbond": hb}
    per = {k: (v * dalam).sum(axis=1) * BOBOT[k] for k, v in suku.items()}
    tot = sum(per.values())
    daftar = [{"indeks": t[0], "nama": lig[t[0]][0], "unsur": t[1], "energi": round(float(tot[k]), 3),
               "suku": {s: round(float(per[s][k]), 3) for s in per}, "xyz": [round(float(v), 3) for v in pl[k]]}
              for k, t in enumerate(tl)]
    return daftar, round(float(tot.sum()), 3)
