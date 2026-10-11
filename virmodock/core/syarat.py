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
