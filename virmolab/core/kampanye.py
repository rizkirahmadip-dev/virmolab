"""Menggabungkan beberapa job: ensemble (beberapa bentuk reseptor), selektivitas (beberapa protein),
dan perbandingan kovalen lawan non-kovalen. Dockingnya sendiri tetap lewat antrean yang sudah ada.
"""


def _baris(jobs):
    baris = []
    for j in jobs or []:
        reseptor = j.get("nama") or j.get("id") or "reseptor"
        for l in j.get("ligan") or []:
            if l.get("energi") is None:
                continue
            baris.append({"ligan": l.get("nama") or l.get("id"), "reseptor": reseptor,
                          "energi": float(l["energi"]), "kovalen": bool(j.get("kovalen")),
                          "warhead": l.get("warhead") or ""})
    return baris


def dari_job(jobs):
    return _baris(jobs)


def ensemble(baris):
    """Skor terbaik tiap ligan di antara semua reseptor. Energi lebih negatif menang."""
    terbaik = {}
    for b in baris:
        lama = terbaik.get(b["ligan"])
        if lama is None or b["energi"] < lama["energi"]:
            terbaik[b["ligan"]] = dict(b)
    return sorted(terbaik.values(), key=lambda x: x["energi"])


def selektivitas(baris):
    """{ligan: {reseptor: energi}} untuk tabel panel selektivitas."""
    tabel = {}
    for b in baris:
        tabel.setdefault(b["ligan"], {})[b["reseptor"]] = b["energi"]
    return tabel


def teks_tabel(tabel):
    if not tabel:
        return "Belum ada dua job selesai dengan ligan yang sama. Docking ligan yang sama ke protein kedua " \
               "(atau bentuk kedua) dulu, lalu buka lagi halaman ini."
    reseptor = sorted({r for kolom in tabel.values() for r in kolom})
    o = ["ligan\t" + "\t".join(reseptor)]
    for ligan in sorted(tabel):
        o.append(ligan + "\t" + "\t".join("" if tabel[ligan].get(r) is None else f"{tabel[ligan][r]:.2f}"
                                          for r in reseptor))
    return "\n".join(o)


def banding_kovalen(baris):
    """Pasangan ligan yang punya skor kovalen dan non-kovalen. Skor kovalen bukan ΔG."""
    grup = {}
    for b in baris:
        grup.setdefault(b["ligan"], []).append(b)
    pasangan = []
    for nama, daftar in grup.items():
        kov = [x for x in daftar if x["kovalen"]]
        biasa = [x for x in daftar if not x["kovalen"]]
        if kov and biasa:
            pasangan.append({"ligan": nama, "kovalen": min(x["energi"] for x in kov),
                             "nonkovalen": min(x["energi"] for x in biasa),
                             "warhead": next((x["warhead"] for x in kov if x["warhead"]), "")})
    return pasangan
