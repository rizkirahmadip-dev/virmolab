"""Air penjembatan dan kofaktor pada struktur PDB.

Air penjembatan: oksigen air ≤ 3,5 Å dari atom N/O protein dan ≤ 3,5 Å dari atom berat ligan asli
(ligan = HET terbesar yang bukan aditif/ion). Kofaktor = HET lain yang bukan ligan utama, bukan aditif
kristalisasi, dan bukan ion logam.
"""
import gemmi

from .molekul import ADITIF, AIR, KOFAKTOR, PROSTETIK
from .prep_reseptor import LOGAM


def _pos(a):
    return (a.pos.x, a.pos.y, a.pos.z)


def _jarak(p, q):
    return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2) ** 0.5


def telaah(st):
    """st = gemmi.Structure. Kembalikan dict jembatan, kofaktor, ligan."""
    if isinstance(st, str):
        st = gemmi.read_pdb_string(st)
    protein, het = [], []
    for ch in st[0]:
        for r in ch:
            nama = r.name.upper()
            atom = [(a, _pos(a)) for a in r if a.element.name not in ("H", "D")]
            if not atom:
                continue
            if r.het_flag != "H" and nama not in AIR:
                for a, p in atom:
                    if a.element.name in ("N", "O"):
                        protein.append(p)
                continue
            het.append((ch.name, str(r.seqid.num), nama, atom))
    ligan = None
    calon = [h for h in het if h[2] not in AIR and h[2] not in ADITIF and h[2] not in LOGAM and len(h[3]) > 1
             and h[2] not in PROSTETIK]
    # Ko-substrat (NAD, ATP, SAM, …) bukan ligan asli selama ada kandidat lain; gugus prostetik (heme, flavin)
    # tidak pernah: pada CYP + obat HEM lebih besar dari obatnya, dan pada CYP apo heme harus tetap di reseptor.
    bukan_kof = [h for h in calon if h[2] not in KOFAKTOR]
    if bukan_kof or calon:
        ligan = max(bukan_kof or calon, key=lambda h: len(h[3]))
    lig_xyz = [p for _, p in ligan[3]] if ligan else []
    jembatan = []
    for ch, resi, nama, atom in het:
        if nama not in AIR:
            continue
        o = next((p for a, p in atom if a.element.name == "O"), None)
        if o is None or not lig_xyz or not protein:
            continue
        if any(_jarak(o, p) <= 3.5 for p in protein) and any(_jarak(o, p) <= 3.5 for p in lig_xyz):
            jembatan.append({"rantai": ch, "resi": resi, "resn": nama,
                             "xyz": [round(x, 3) for x in o]})
    kofaktor = []
    for ch, resi, nama, atom in het:
        if nama in AIR or nama in ADITIF or nama in LOGAM or len(atom) <= 1:
            continue
        if ligan and (ch, resi, nama) == (ligan[0], ligan[1], ligan[2]):
            continue
        if ligan and nama == ligan[2]:      # salinan ligan utama di rantai lain (kristal multimer)
            continue
        kofaktor.append({"rantai": ch, "resi": resi, "resn": nama, "atom": len(atom)})
    return {"jembatan": jembatan, "kofaktor": kofaktor,
            "ligan": None if not ligan else {"rantai": ligan[0], "resi": ligan[1], "resn": ligan[2],
                                             "atom": len(ligan[3])}}


def kunci_jembatan(hasil):
    return {(j["rantai"], str(j["resi"])) for j in hasil["jembatan"]}


def kunci_kofaktor(hasil):
    return {(k["rantai"], str(k["resi"]), k["resn"]) for k in hasil["kofaktor"]}
