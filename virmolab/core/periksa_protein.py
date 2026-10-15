"""Pemeriksa kualitas struktur protein sebelum preparasi (gemmi saja).

Memeriksa: metode & resolusi, rantai, celah rantai (jarak C-N antar residu berurutan > 2 Å), residu dengan atom
berat hilang, konformasi alternatif, okupansi < 1, residu non-standar, ligan/ion/air, dan B-faktor.
Hasil = dict ringkasan + daftar temuan (tingkat: 'ok' | 'info' | 'peringatan' | 'masalah').
"""
from .molekul import ADITIF, AIR, PROSTETIK

# jumlah atom berat sisi + tulang punggung (tanpa OXT) asam amino baku
ATOM_BERAT = {"ALA": 5, "ARG": 11, "ASN": 8, "ASP": 8, "CYS": 6, "GLN": 9, "GLU": 9, "GLY": 4, "HIS": 10, "ILE": 8,
              "LEU": 8, "LYS": 9, "MET": 8, "PHE": 11, "PRO": 7, "SER": 6, "THR": 7, "TRP": 14, "TYR": 12, "VAL": 7}
LOGAM = {"ZN", "MG", "CA", "MN", "FE", "FE2", "CU", "CU1", "CO", "NI", "NA", "K", "CD", "HG"}


def periksa(teks, fmt="pdb"):
    from .prep_reseptor import baca_struktur
    st = baca_struktur(teks, fmt)
    model = st[0]
    temuan = []
    res_info = {"metode": (st.info["_exptl.method"] if "_exptl.method" in st.info else "").strip(" '") or None,
                "resolusi": st.resolution or None, "rantai": [], "residu": 0, "atom": model.count_atom_sites()}
    hilang, celah, altloc, okup, nonbaku, ligan, logam = [], [], set(), set(), set(), [], []
    air = 0
    bf = []
    for ch in model:
        n_pol = 0
        sebelum = None
        for r in ch:
            nama = r.name.upper()
            if nama in AIR:
                air += 1
                continue
            if r.het_flag == "H":
                if nama in LOGAM and len(r) == 1:
                    logam.append(f"{nama} {ch.name}{r.seqid.num}")
                elif nama in ADITIF:
                    ligan.append((f"{nama} {ch.name}{r.seqid.num}", "aditif"))
                elif nama == "MSE":
                    nonbaku.add(f"MSE {ch.name}{r.seqid.num}")
                else:
                    ligan.append((f"{nama} {ch.name}{r.seqid.num}", f"{len(r)} atom"))
                if nama != "MSE":
                    continue
            n_pol += 1
            label = f"{nama} {r.seqid.num}{r.seqid.icode.strip()} {ch.name}"
            if nama not in ATOM_BERAT and nama != "MSE":
                nonbaku.add(label)
            berat = {a.name for a in r if a.element.name != "H"}
            if nama in ATOM_BERAT and len(berat - {"OXT"}) < ATOM_BERAT[nama]:
                hilang.append(f"{label} ({ATOM_BERAT[nama] - len(berat - {'OXT'})} atom)")
            for a in r:
                if a.altloc != "\0":
                    altloc.add(label)
                if a.occ < 0.99 and a.altloc == "\0":
                    okup.add(label)
                bf.append(a.b_iso)
            c = r.find_atom("C", "*")
            n = r.find_atom("N", "*")
            if sebelum is not None and n is not None and sebelum[1] is not None:
                d = sebelum[1].pos.dist(n.pos)
                if d > 2.0:
                    celah.append(f"{sebelum[0]} → {label} ({d:.1f} Å)")
            sebelum = (label, c)
        if n_pol:
            res_info["rantai"].append((ch.name, n_pol))
            res_info["residu"] += n_pol
    res_info.update(hilang=hilang, celah=celah, altloc=sorted(altloc), okupansi=sorted(okup),
                    nonbaku=sorted(nonbaku), ligan=ligan, logam=logam, air=air,
                    b_rerata=(sum(bf) / len(bf)) if bf else None)
    # --- temuan
    rs = res_info["resolusi"]
    if rs:
        tingkat = "ok" if rs <= 2.5 else "peringatan" if rs <= 3.0 else "masalah"
        temuan.append((tingkat, f"Resolusi {rs:.2f} Å".replace(".", ",") + {"ok": " (baik untuk docking)",
                                                          "peringatan": " (sedang; periksa kantong dengan cermat)",
                                                          "masalah": " (rendah; posisi rantai samping kurang pasti)"}[tingkat]))
    elif res_info["metode"] and "NMR" in res_info["metode"].upper():
        temuan.append(("info", "Struktur NMR: hanya model pertama yang dipakai"))
    else:
        temuan.append(("info", "Resolusi tidak tercantum (model prediksi/homologi?) - periksa skor kepercayaan"))
    if celah:
        temuan.append(("peringatan", f"{len(celah)} celah rantai (residu hilang di model): " + "; ".join(celah[:6])
                       + (" …" if len(celah) > 6 else "") + ". Bila dekat kantong, pertimbangkan model lengkap."))
    else:
        temuan.append(("ok", "Tidak ada celah rantai"))
    if hilang:
        temuan.append(("peringatan", f"{len(hilang)} residu kehilangan atom berat: " + ", ".join(hilang[:8])
                       + (" …" if len(hilang) > 8 else "") + ". Pilih protonasi PROPKA/PDB2PQR (langkah 3) agar dilengkapi, "
                       "bukan dibuang."))
    else:
        temuan.append(("ok", "Semua residu baku lengkap"))
    if altloc:
        temuan.append(("info", f"{len(altloc)} residu punya konformasi alternatif (dipilih okupansi tertinggi)"))
    if okup:
        temuan.append(("info", f"{len(okup)} residu dengan okupansi < 1"))
    if nonbaku:
        temuan.append(("peringatan", f"Residu non-standar: {', '.join(sorted(nonbaku)[:8])}"
                       + (" …" if len(nonbaku) > 8 else "") + " - bisa dibuang saat preparasi"))
    lig = [l for l, k in ligan if k != "aditif" and l.split()[0] not in PROSTETIK]
    prost = [l for l, k in ligan if l.split()[0] in PROSTETIK]
    if lig:
        temuan.append(("info", f"Ligan kristal: {', '.join(lig[:6])}" + (" …" if len(lig) > 6 else "")
                       + " - dipakai untuk pusat grid & validasi redocking"))
    if prost:
        temuan.append(("info", f"Gugus prostetik: {', '.join(prost[:6])}" + (" …" if len(prost) > 6 else "")
                       + " - bagian situs aktif; dipertahankan bila 'Pertahankan kofaktor' dicentang"))
    if logam:
        temuan.append(("info", f"Ion logam: {', '.join(logam[:8])} - pertahankan bila di situs aktif"))
    if res_info["b_rerata"] and res_info["b_rerata"] > 80:
        temuan.append(("peringatan", f"B-faktor rerata tinggi ({res_info['b_rerata']:.0f} Å²): struktur fleksibel"))
    if len(res_info["rantai"]) > 1:
        temuan.append(("info", "Beberapa rantai: " + ", ".join(f"{c} ({n})" for c, n in res_info["rantai"])
                       + ". Pilih rantai yang membentuk kantong (dimer: biasanya keduanya)."))
    res_info["temuan"] = temuan
    return res_info


def skor(info):
    """Ringkasan satu kata untuk header wizard."""
    t = [x[0] for x in info["temuan"]]
    return "masalah" if "masalah" in t else "peringatan" if "peringatan" in t else "baik"
