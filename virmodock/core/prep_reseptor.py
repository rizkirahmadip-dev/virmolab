"""Preparasi reseptor: bersihkan struktur (gemmi) lalu PDBQT (Meeko, cadangan Open Babel).

Alur:
  1. gemmi: model pertama, altloc, buang H, pilih rantai, buang air/ligan,
     pertahankan ion logam bila diminta, tulis PDB bersih (kolom elemen terisi).
  2. Meeko Polymer: tambah H, muatan Gasteiger, tipe atom AD4 -> PDBQT.
     Residu yang tidak cocok templat dibuang dan dilaporkan.
  3. Cadangan bila Meeko gagal: Open Babel (-xr, H polar, Gasteiger).
  4. Ion logam ditambahkan ke PDBQT dengan tipe AD4 dan muatan formal.
"""
import io
import re
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field

import gemmi

from .molekul import ADITIF, AIR

LOGAM = {"ZN": ("Zn", 2.0), "MG": ("Mg", 2.0), "CA": ("Ca", 2.0), "MN": ("Mn", 2.0), "FE": ("Fe", 3.0),
         "FE2": ("Fe", 2.0), "CU": ("Cu", 2.0), "CU1": ("Cu", 1.0), "CO": ("Co", 2.0), "NI": ("Ni", 2.0)}
# tipe AD4 yang dikenali autogrid4 / Vina untuk logam
TIPE_LOGAM = {"Zn": "Zn", "Mg": "Mg", "Ca": "Ca", "Mn": "Mn", "Fe": "Fe", "Cu": "Cu", "Co": "Zn", "Ni": "Zn"}


@dataclass
class OpsiReseptor:
    rantai: list = None              # None = semua
    hapus_air: bool = True
    hapus_ligan: bool = True
    pertahankan_logam: bool = True
    radius_logam: float = 8.0        # Å dari ligan asli; 0 = semua logam
    altloc: str = "tertinggi"        # "A" | "tertinggi"
    muatan: str = "gasteiger"        # gasteiger | templat
    hidrogen: str = "polar"          # polar | semua (PDBQT AD4 selalu H polar; 'semua' disimpan di PDB)
    protonasi: str = "templat"       # templat (keadaan baku Meeko) | propka (PDB2PQR + PROPKA pada pH)
    ph: float = 7.4
    optimasi_h: bool = True          # PDB2PQR: optimasi jaringan ikatan H + flip His/Asn/Gln
    air_jembatan: bool = False       # bila air dibuang: oksigen yang menjembatani protein dan ligan dipertahankan
    kofaktor: bool = False           # HET selain ligan utama dan aditif (HEM, NAD, …) ikut struktur


@dataclass
class HasilReseptor:
    pdbqt: str
    pdb_bersih: str
    metode: str
    atom: int = 0
    residu: int = 0
    dibuang: list = field(default_factory=list)     # residu cacat yang dibuang
    logam: list = field(default_factory=list)       # ion yang dipertahankan
    peringatan: list = field(default_factory=list)
    laporan: str = ""
    protonasi: object = None                        # protonasi.HasilProtonasi bila memakai PROPKA
    pdb_meeko: str = ""                             # PDB masukan Meeko (setelah protonasi) - dasar residu fleksibel


class GalatPrep(Exception):
    pass


# ------------------------------------------------------------- pembersihan
def _altloc_tertinggi(st):
    """Hapus konformasi alternatif, pertahankan altloc dengan okupansi tertinggi per residu."""
    for ch in st[0]:
        for r in ch:
            alt = {}
            for a in r:
                if a.altloc != "\0":
                    alt[a.altloc] = alt.get(a.altloc, 0.0) + a.occ
            if len(alt) < 2:
                continue
            terbaik = max(alt, key=alt.get)
            for i in range(len(r) - 1, -1, -1):
                if r[i].altloc not in ("\0", terbaik):
                    del r[i]
    st.remove_alternative_conformations()


def baca_struktur(teks, fmt="pdb"):
    if fmt == "cif" or teks.lstrip().startswith("data_"):
        st = gemmi.make_structure_from_block(gemmi.cif.read_string(teks).sole_block())
    else:
        st = gemmi.read_pdb_string(teks)
    if len(st) == 0:
        raise GalatPrep("Struktur tidak berisi model atom.")
    for i in range(len(st) - 1, 0, -1):
        del st[i]
    st.setup_entities()
    return st


def info_rantai(st):
    """Daftar rantai polimer: [(nama, jumlah residu)]."""
    hasil = []
    for ch in st[0]:
        n = sum(1 for r in ch if r.het_flag != "H" and r.name not in AIR)
        if n:
            hasil.append((ch.name, n))
    return hasil


def _pusat_ligan(st):
    xs = [a.pos for ch in st[0] for r in ch if r.het_flag == "H" and r.name not in AIR
          and r.name.upper() not in LOGAM and r.name.upper() not in ADITIF and len(r) > 4 for a in r]
    return xs


def bersihkan(st, opsi):
    """Kembalikan (struktur protein bersih, daftar ion logam [(resn, elemen, muatan, pos, rantai, resi)])."""
    st = st.clone()
    if opsi.altloc == "A":
        st.remove_alternative_conformations()
    else:
        _altloc_tertinggi(st)
    st.remove_hydrogens()
    if opsi.rantai:
        for i in range(len(st[0]) - 1, -1, -1):
            if st[0][i].name not in opsi.rantai:
                del st[0][i]
    lig_pos = _pusat_ligan(st)
    jaga_air, jaga_kof = set(), set()
    if opsi.air_jembatan or opsi.kofaktor:
        from . import air as airmod
        telaah = airmod.telaah(st)
        if opsi.air_jembatan:
            jaga_air = airmod.kunci_jembatan(telaah)
        if opsi.kofaktor:
            jaga_kof = airmod.kunci_kofaktor(telaah)
    logam = []
    for ch in st[0]:
        for i in range(len(ch) - 1, -1, -1):
            r = ch[i]
            nama = r.name.upper()
            if nama in AIR:
                if opsi.hapus_air and (ch.name, str(r.seqid.num)) not in jaga_air:
                    del ch[i]
                continue
            if r.het_flag != "H":
                continue
            if nama in LOGAM and len(r) == 1:
                if opsi.pertahankan_logam:
                    p = r[0].pos
                    dekat = (not lig_pos or opsi.radius_logam <= 0
                             or min(p.dist(q) for q in lig_pos) <= opsi.radius_logam)
                    if dekat:
                        el, q = LOGAM[nama]
                        logam.append((nama, el, q, (p.x, p.y, p.z), ch.name, r.seqid.num))
                del ch[i]
                continue
            # residu HET lain: ligan, ion non-logam, aditif kristalisasi
            if (ch.name, str(r.seqid.num), nama) in jaga_kof:
                continue
            if opsi.hapus_ligan or len(r) <= 1:
                del ch[i]
    st.remove_empty_chains()
    # sisa air (jika tidak dihapus) ikut ditulis; Meeko akan menolak -> dibuang & dilaporkan
    st.setup_entities()
    return st, logam


def tulis_pdb(st):
    opt = gemmi.PdbWriteOptions()
    opt.minimal_file = True
    opt.ter_records = True
    teks = st.make_pdb_string(opt)
    # pastikan kolom elemen terisi (PDB lama seperti 1ITB tidak punya)
    baris = []
    for b in teks.splitlines():
        if b.startswith(("ATOM", "HETATM")) and len(b.rstrip()) < 78:
            b = b.ljust(76)[:76] + _tebak_elemen(b[12:16]).rjust(2)
        baris.append(b)
    return "\n".join(baris) + "\n"


def _tebak_elemen(nama):
    n = nama.strip()
    if not n:
        return "C"
    if nama[0].isalpha() and nama[0] != " " and nama[:2].strip().upper() in ("FE", "ZN", "MG", "MN", "CA", "CL", "BR", "SE", "CU"):
        return nama[:2].strip().capitalize()
    return re.sub(r"[^A-Za-z]", "", n)[:1].upper() or "C"


# --------------------------------------------------------------- Meeko
_RE_RES = re.compile(r"([A-Za-z0-9]+):(-?\d+)([A-Za-z]?)")


def _meeko(pdb, opsi, fleksibel=None):
    """PDB -> (PDBQT kaku, residu dibuang, keluaran log[, PDBQT fleksibel, residu fleksibel gagal]).
    fleksibel: ['A:42', …] -> rantai samping dipisah ke blok BEGIN_RES/END_RES (Vina --flex, AD-GPU --flexres)."""
    from meeko import MoleculePreparation, Polymer, PDBQTWriterLegacy, ResidueChemTemplates
    cfg = {"compute_charges": opsi.muatan == "gasteiger"}
    if opsi.muatan == "gasteiger":
        cfg["charge_model"] = "gasteiger"
    mk_prep = MoleculePreparation.from_config(cfg)
    templat = ResidueChemTemplates.create_from_defaults()
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pol = Polymer.from_pdb_string(pdb, templat, mk_prep, allow_bad_res=True)
    dibuang = sorted(pol.get_ignored_monomers().keys())
    if fleksibel is None:
        rigid, _flex = PDBQTWriterLegacy.write_from_polymer(pol)
        return rigid, dibuang, buf.getvalue()
    gagal = []
    sah = pol.get_valid_monomers()
    for rid in fleksibel:
        if rid not in sah:
            gagal.append(f"{rid} (residu tidak ada/dibuang)")
            continue
        try:
            with redirect_stdout(buf), redirect_stderr(buf):
                pol.flexibilize_sidechain(rid, mk_prep)
        except Exception as e:
            gagal.append(f"{rid} ({str(e).strip().splitlines()[0][:80] if str(e).strip() else type(e).__name__})")
    rigid, flex = PDBQTWriterLegacy.write_from_polymer(pol)
    teks_flex = "".join(flex.values()) if isinstance(flex, dict) else (flex or "")
    return rigid, dibuang, buf.getvalue(), teks_flex, gagal


def _openbabel(pdb):
    """Cadangan bila Meeko gagal: Open Babel (program terpisah) -> PDBQT kaku, H polar, Gasteiger."""
    from . import obabel
    return obabel.konversi(pdb, "pdb", "pdbqt", ["--AddPolarH", "--partialcharge", "gasteiger", "-xr", "-xp"])


def _baris_logam(logam, mulai):
    baris = []
    for i, (resn, el, q, (x, y, z), c, resi) in enumerate(logam):
        t = TIPE_LOGAM.get(el, "Zn")
        nama = el.upper().ljust(3)
        baris.append(f"HETATM{(mulai + i) % 100000:5d} {nama:<4} {resn[:3]:>3} {c[:1]}{resi % 10000:4d}    "
                     f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00    {q:+6.3f} {t:<2}")
    return baris


def hitung_atom(pdbqt):
    return sum(1 for b in pdbqt.splitlines() if b.startswith(("ATOM", "HETATM")))


def tipe_atom(pdbqt):
    t = set()
    for b in pdbqt.splitlines():
        if b.startswith(("ATOM", "HETATM")):
            s = b[77:].split()
            if s:
                t.add(s[0])
    return t


def siapkan(teks, opsi=None, fmt="pdb", lapor=None):
    """Siapkan reseptor dari teks PDB/mmCIF. Kembalikan HasilReseptor."""
    opsi = opsi or OpsiReseptor()
    log = (lambda s: lapor.log.emit(s)) if lapor else (lambda s: None)
    st = baca_struktur(teks, fmt)
    bersih, logam = bersihkan(st, opsi)
    n_res = sum(len(ch) for ch in bersih[0])
    if not n_res:
        raise GalatPrep("Tidak ada residu protein setelah pembersihan. Periksa pilihan rantai.")
    pdb = tulis_pdb(bersih)
    log(f"Struktur bersih: {len(bersih[0])} rantai, {n_res} residu, {bersih[0].count_atom_sites()} atom berat")
    peringatan, dibuang = [], []
    metode = "Meeko (Gasteiger)" if opsi.muatan == "gasteiger" else "Meeko (muatan templat)"
    hp = None
    pdb_meeko = pdb
    if opsi.protonasi == "propka":
        from . import protonasi
        try:
            hp = protonasi.jalankan(pdb, opsi.ph, opsi.optimasi_h, lapor=lapor)
            pdb_meeko = hp.pdb
            if logam:       # His pengikat logam: tautomer ditetapkan dari geometri koordinasi
                pdb_meeko, his = protonasi.sesuaikan_his_logam(pdb_meeko, [p for _, _, _, p, _, _ in logam])
                if his:
                    kunci = lambda t: tuple(t.split()[1:3])     # noqa: E731  (nomor, rantai)
                    lama = {kunci(x) for x in his}
                    hp.keadaan = [k for k in hp.keadaan if kunci(k[0]) not in lama]
                    hp.keadaan += [(x.split(" (")[0], x.split()[0], "His pengikat logam") for x in his]
                    log("His pengikat logam: " + ", ".join(his))
            metode += f", PROPKA/PDB2PQR pH {opsi.ph:.1f}"
            peringatan += [f"PDB2PQR: {m}" for m in hp.peringatan[:10]]
        except Exception as e:
            log(f"PROPKA/PDB2PQR gagal ({e}); memakai keadaan protonasi baku templat Meeko")
            peringatan.append(f"PROPKA/PDB2PQR gagal ({str(e)[:160]}); protonasi baku templat dipakai.")
    try:
        pdbqt, dibuang, keluaran = _meeko(pdb_meeko, opsi)
        if not hitung_atom(pdbqt):
            raise GalatPrep("Meeko tidak menghasilkan atom.")
        if dibuang:
            peringatan.append(f"{len(dibuang)} residu tidak lengkap/tidak dikenal dibuang oleh Meeko: "
                              + ", ".join(dibuang[:30]) + (" …" if len(dibuang) > 30 else ""))
    except Exception as e:
        log(f"Meeko gagal ({str(e).strip().splitlines()[0][:200] if str(e).strip() else type(e).__name__}); "
            "memakai cadangan Open Babel")
        peringatan.append("Meeko gagal; reseptor disiapkan dengan Open Babel (H polar, Gasteiger).")
        pdbqt = _openbabel(pdb)
        metode = "Open Babel (Gasteiger)"
    baris = [b for b in pdbqt.splitlines() if b.strip()]
    if logam:
        baris = [b for b in baris if not b.startswith(("END", "TER"))] + _baris_logam(logam, hitung_atom(pdbqt) + 1)
        log("Ion logam dipertahankan: " + ", ".join(f"{r} {c}{i}" for r, _, _, _, c, i in logam))
    if opsi.air_jembatan:
        mulai = hitung_atom("\n".join(baris)) + 1
        air_baris = []
        for ch in bersih[0]:
            for r in ch:
                if r.name.upper() not in AIR:
                    continue
                for a in r:
                    if a.element.name != "O":
                        continue
                    p = a.pos
                    air_baris.append(
                        f"HETATM{mulai % 100000:5d} {'O':<4} HOH {ch.name[:1]}{r.seqid.num % 10000:4d}    "
                        f"{p.x:8.3f}{p.y:8.3f}{p.z:8.3f}  1.00  0.00    {-0.400:+6.3f} OA")
                    mulai += 1
        if air_baris:
            baris = [b for b in baris if not b.startswith(("END", "TER"))] + air_baris
            log(f"Air penjembatan dipertahankan: {len(air_baris)} (tipe OA)")
            peringatan.append(f"{len(air_baris)} air penjembatan ditulis sebagai akseptor OA. "
                              "Skornya tidak setara dengan air eksplisit.")
    pdbqt = "\n".join(baris) + "\n"
    h = HasilReseptor(pdbqt=pdbqt, pdb_bersih=pdb, metode=metode, atom=hitung_atom(pdbqt), residu=n_res - len(dibuang),
                      dibuang=dibuang, logam=[f"{r} {c}{i}" for r, _, _, _, c, i in logam], peringatan=peringatan,
                      protonasi=hp, pdb_meeko=pdb_meeko if metode.startswith("Meeko") else "")
    jumlah_h = sum(1 for b in baris if b.startswith(("ATOM", "HETATM")) and b[77:].split()[:1] == ["HD"])
    q_total = sum(float(b[70:76]) for b in baris if b.startswith(("ATOM", "HETATM")) and _angka(b[70:76]))
    h.laporan = "\n".join([
        "Laporan preparasi reseptor (VirmoDock)",
        f"Metode       : {metode}",
        f"Rantai       : {', '.join(ch.name for ch in bersih[0])}",
        f"Residu       : {h.residu}",
        f"Atom PDBQT   : {h.atom} (H polar {jumlah_h})",
        f"Muatan total : {q_total:+.3f}",
        f"Tipe atom    : {' '.join(sorted(tipe_atom(pdbqt)))}",
        f"Air dihapus  : {'ya' if opsi.hapus_air else 'tidak'}"
        + (" (air penjembatan dipertahankan)" if opsi.air_jembatan else ""),
        f"Kofaktor     : {'dipertahankan' if opsi.kofaktor else 'dibuang bersama ligan'}",
        f"Ligan dihapus: {'ya' if opsi.hapus_ligan else 'tidak'}",
        f"Altloc       : {'A' if opsi.altloc == 'A' else 'okupansi tertinggi'}",
        f"Ion logam    : {', '.join(h.logam) or '-'}",
        f"Residu dibuang ({len(dibuang)}): {', '.join(dibuang) or '-'}",
    ] + (_laporan_protonasi(hp) if hp else ["Protonasi    : keadaan baku templat Meeko (Asp/Glu −, Lys/Arg +, "
                                             "His netral)"])
      + ([""] + ["Peringatan: " + p for p in peringatan] if peringatan else [])) + "\n"
    return h


def _laporan_protonasi(hp):
    from .protonasi import ringkas_pka
    o = [f"Protonasi    : PROPKA 3 + PDB2PQR pada pH {hp.ph:.1f} ({hp.detik:.1f} s)",
         f"Keadaan tak-baku ({len(hp.keadaan)}): " + (", ".join(f"{l} [{k}]" for l, _n, k in hp.keadaan) or "-"),
         f"Atom/residu dilengkapi ({len(hp.diperbaiki)}): " + ("; ".join(hp.diperbaiki[:12]) or "-")]
    r = ringkas_pka(hp)
    if r:
        o += ["pKa penting (pergeseran ≥ 1 atau dekat pH):"] + ["  " + x for x in r]
    return o


def _angka(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


# AD-GPU: jumlah atom & torsi ligan + residu fleksibel dibatasi (MAX_NUM_OF_ATOMS 256, MAX_NUM_OF_ROTBONDS 32)
MAKS_FLEKSIBEL = 8


def buat_fleksibel(pdb_meeko, pdbqt_lama, residu, opsi=None):
    """Bagi reseptor menjadi bagian kaku + residu fleksibel (Meeko). Ion logam dari PDBQT lama dipertahankan.
    -> (pdbqt_kaku, pdbqt_flex, residu_berhasil, gagal)."""
    opsi = opsi or OpsiReseptor()
    if not pdb_meeko:
        raise GalatPrep("Data preparasi Meeko tidak tersedia. Siapkan ulang reseptor (langkah 1) lalu coba lagi.")
    residu = [r.strip() for r in residu if r.strip()]
    if not residu:
        raise GalatPrep("Pilih minimal satu residu fleksibel.")
    if len(residu) > MAKS_FLEKSIBEL:
        raise GalatPrep(f"Maksimal {MAKS_FLEKSIBEL} residu fleksibel (ruang pencarian membesar cepat; "
                        "praktik umum 2-6 residu kantong).")
    rigid, _dibuang, _log, flex, gagal = _meeko(pdb_meeko, opsi, fleksibel=residu)
    if not flex.strip():
        raise GalatPrep("Tidak ada residu yang bisa dibuat fleksibel: " + "; ".join(gagal))
    logam = [b for b in pdbqt_lama.splitlines() if b.startswith("HETATM") and b[17:20].strip().upper() in LOGAM]
    baris = [b for b in rigid.splitlines() if b.strip() and not b.startswith(("END", "TER"))]
    rigid = "\n".join(baris + logam) + "\n"
    berhasil = []
    for b in flex.splitlines():
        if b.startswith("BEGIN_RES"):
            s = b.split()
            if len(s) >= 4:
                berhasil.append(f"{s[2]}:{s[3]}")
    return rigid, flex if flex.endswith("\n") else flex + "\n", berhasil, gagal


def torsi_flex(flex):
    """Jumlah ikatan rotasi pada blok residu fleksibel (BRANCH)."""
    return sum(1 for b in flex.splitlines() if b.startswith("BRANCH"))


def pdbqt_ke_pdb(pdbqt):
    """PDBQT -> PDB untuk viewer (kolom elemen dari tipe AD4)."""
    from .molekul import _elemen_pdbqt
    return "\n".join(b[:66].ljust(66) + " " * 10 + _elemen_pdbqt(b) for b in pdbqt.splitlines()
                     if b.startswith(("ATOM", "HETATM"))) + "\nEND\n"
