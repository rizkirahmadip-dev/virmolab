"""Syarat interaksi setelah docking: pose yang tidak menyentuh residu wajib ditandai, tidak dihitung ulang.

Vina dan AutoDock-GPU tidak memaksa ikatan saat pencarian. Penyaringan ini jujur: pose tetap
tersimpan, tetapi yang gagal syarat tidak dipakai sebagai pose terbaik.
"""


def _cocok(h, wajib):
    bagian = wajib.split()
    if len(bagian) >= 3 and bagian[-1] in ("hbond", "hidrofobik", "pi", "garam", "halogen", "logam", "vdw",
                                           "kation", "tumpuk"):
        jenis = bagian[-1]
        residu = " ".join(bagian[:-1])
    else:
        jenis, residu = None, " ".join(bagian)
    if h.get("jenis") == "vdw":
        return False
    label = h.get("residu") or ""
    if jenis and h.get("jenis") != jenis and not (jenis == "pi" and str(h.get("jenis", "")).startswith("pi")):
        return False
    return label == residu or label.startswith(residu + " ")


def periksa(interaksi, wajib):
    """wajib = daftar teks, misalnya 'ASP 25 A' atau 'ASP 25 A hbond'.

    Kembalikan (lulus, yang_gagal).
    """
    gagal = []
    for w in wajib:
        w = " ".join(w.split())
        if not w:
            continue
        if not any(_cocok(h, w) for h in interaksi or []):
            gagal.append(w)
    return not gagal, gagal


def _atom_baris(baris):
    if len(baris) < 54 or not baris.startswith(("ATOM", "HETATM")):
        return None
    nama = baris[12:16].strip()
    if nama.upper().startswith("H") or (len(baris) >= 78 and baris[76:78].strip().upper() == "H"):
        return None
    try:
        xyz = (float(baris[30:38]), float(baris[38:46]), float(baris[46:54]))
    except ValueError:
        return None
    return {"nama": nama or "?", "resn": baris[17:20].strip(), "rantai": baris[21].strip(),
            "resi": baris[22:26].strip(), "xyz": xyz}


def daftar_residu(aturan):
    """Daftar (rantai, nomor) dari syarat proyek. Format lama satu residu tetap terbaca."""
    if not isinstance(aturan, dict):
        return []
    hasil = []
    for r in aturan.get("residu") or []:
        if isinstance(r, dict) and str(r.get("resi") or "").strip():
            hasil.append((str(r.get("rantai") or "").strip()[:1], str(r.get("resi")).strip()))
    if not hasil and str(aturan.get("resi") or "").strip():
        hasil.append((str(aturan.get("rantai") or "").strip()[:1], str(aturan.get("resi")).strip()))
    return hasil


def pasangan_terdekat(teks_reseptor, residu, teks_pose):
    """Pasangan atom berat terdekat antara pose dan salah satu residu.

    residu = daftar (rantai, nomor). Rantai kosong cocok dengan semua rantai.
    Mengembalikan None bila residu atau pose tidak punya atom. Pencarian docking tidak diubah.
    """
    kunci = [(str(r or "").strip(), str(n).strip()) for r, n in residu or [] if str(n).strip()]
    if not kunci:
        return None
    sasaran = []
    for b in (teks_reseptor or "").splitlines():
        a = _atom_baris(b)
        if not a:
            continue
        for rantai, resi in kunci:
            if rantai and a["rantai"] != rantai:
                continue
            if a["resi"] == resi:
                sasaran.append(a)
                break
    pose = [a for b in (teks_pose or "").splitlines() if (a := _atom_baris(b))]
    if not sasaran or not pose:
        return None
    ligan = protein = None
    jarak = None
    for lig in pose:
        for prot in sasaran:
            d = ((lig["xyz"][0] - prot["xyz"][0]) ** 2 + (lig["xyz"][1] - prot["xyz"][1]) ** 2
                 + (lig["xyz"][2] - prot["xyz"][2]) ** 2) ** 0.5
            if jarak is None or d < jarak:
                jarak, ligan, protein = d, lig, prot
    return {"min": jarak, "atom_ligan": ligan["nama"], "atom_residu": protein["nama"],
            "resn": protein["resn"], "rantai": protein["rantai"], "resi": protein["resi"],
            "ligan": list(ligan["xyz"]), "protein": list(protein["xyz"])}


def jarak_minimum(teks_reseptor, rantai, resi, teks_pose):
    """Jarak terdekat (Å) antara atom berat pose dan atom residu. None bila salah satu tidak ada."""
    h = pasangan_terdekat(teks_reseptor, [(rantai, resi)], teks_pose)
    return None if h is None else h["min"]


def pilih_pose_syarat(ukur, ambang):
    """Pose yang ditampilkan: energi docking terbaik yang lolos ambang.

    Bila tidak ada yang lolos, kembalikan pose peringkat 1. Tidak mengubah skor tersimpan.
    """
    ada = [u for u in ukur or [] if isinstance(u.get("min"), (int, float))]
    if not ada:
        return None
    lolos = [u for u in ada if u["min"] <= float(ambang) + 1e-9]
    if lolos:
        return min(lolos, key=lambda u: (u["energi"] if isinstance(u.get("energi"), (int, float)) else 1e9,
                                         u.get("peringkat") or 99))
    return min(ada, key=lambda u: u.get("peringkat") or 99)


def saring_pose(pose, interaksi_tiap_peringkat, wajib):
    """pose = daftar dict ber-kunci peringkat. interaksi_tiap_peringkat = {peringkat: [interaksi]}.

    Kembalikan daftar pose yang lulus, urutan semula.
    """
    lulus = []
    for p in pose:
        ok, _ = periksa(interaksi_tiap_peringkat.get(p.get("peringkat"), []), wajib)
        if ok:
            lulus.append(p)
    return lulus
