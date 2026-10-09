"""Protonasi reseptor berbasis pKa: PROPKA 3 + PDB2PQR (perbaikan atom hilang, optimasi jaringan ikatan H).

PDB2PQR (BSD-3) memakai PROPKA (LGPL-2.1) untuk memperkirakan pKa tiap gugus yang dapat terionisasi, memilih
keadaan protonasi pada pH yang diminta (Asp→ASH, Glu→GLH, His→HID/HIE/HIP, Lys→LYN, Cys→CYM/CYX), melengkapi
atom berat yang hilang, menambah semua hidrogen, lalu mengoptimasi jaringan ikatan H (rotasi OH/SH/NH3,
flip His/Asn/Gln) dan menghindari tumbukan (debump). Keluaran PDB bernama residu AMBER diterima templat Meeko,
dan posisi H hasil optimasi dipertahankan Meeko.

Sitasi: Jurrus et al. 2018 (Protein Sci 27:112, PDB2PQR/APBS); Olsson et al. 2011 (JCTC 7:525, PROPKA3);
Søndergaard et al. 2011 (JCTC 7:2284).
"""
import logging
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

# residu AMBER yang menandai keadaan protonasi tak-baku di pH tertentu
NAMA_KEADAAN = {"ASH": "Asp netral (terprotonasi)", "GLH": "Glu netral (terprotonasi)",
                "HID": "His netral (H di Nδ)", "HIE": "His netral (H di Nε)", "HIP": "His bermuatan +1",
                "LYN": "Lys netral", "CYM": "Cys terdeprotonasi (−1)", "CYX": "Cys ikatan disulfida",
                "ARN": "Arg netral", "TYM": "Tyr terdeprotonasi (−1)"}
BAKU = {"ASP": "ASP", "GLU": "GLU", "HIS": "HIS", "LYS": "LYS", "CYS": "CYS", "ARG": "ARG", "TYR": "TYR"}

_tertambal = False


def tambal_propka():
    """PROPKA 3.5.1 memanggil self.__annotations__ — di Python 3.14 (PEP 649) atribut itu tidak lagi
    tersedia dari instance. Ganti Parameters.parse_line dengan versi yang membaca anotasi kelas."""
    global _tertambal
    if _tertambal:
        return
    import propka.parameters as PP
    peta = [("_T_NUMBER_DICTIONARY", "parse_to_number_dictionary"), ("_T_STRING_LIST", "parse_to_string_list"),
            ("_T_STRING", "parse_string"), ("_T_LIST_DICTIONARY", "parse_to_list_dictionary"),
            ("_T_MATRIX", "parse_to_matrix"), ("_T_PAIR_WISE_MATRIX", "parse_to_matrix"),
            ("_T_STRING_DICTIONARY", "parse_to_string_dictionary")]

    def parse_line(self, line):
        kata = line.split("#", 1)[0].split()
        if not kata:
            return
        t = type(self).__annotations__.get(kata[0])
        for jenis, fungsi in peta:
            if hasattr(PP, jenis) and t is getattr(PP, jenis):
                return getattr(self, fungsi)(kata)
        return self.parse_parameter(kata)

    PP.Parameters.parse_line = parse_line
    _tertambal = True


@dataclass
class HasilProtonasi:
    pdb: str                                   # PDB dengan semua H, nama residu AMBER
    pqr: str
    ph: float
    pka: list = field(default_factory=list)    # [{residu, rantai, nomor, jenis, pka, pka_model, terkubur}]
    keadaan: list = field(default_factory=list)  # [(label residu, nama AMBER, keterangan)]
    diperbaiki: list = field(default_factory=list)  # pesan atom yang dilengkapi
    peringatan: list = field(default_factory=list)
    detik: float = 0.0


class _Tangkap(logging.Handler):
    def __init__(self):
        super().__init__(logging.INFO)
        self.pesan = []

    def emit(self, r):
        self.pesan.append((r.levelno, r.getMessage()))


def jalankan(pdb_teks, ph=7.4, optimasi_h=True, debump=True, forcefield="AMBER", lapor=None):
    """Jalankan PDB2PQR + PROPKA pada teks PDB protein (tanpa ligan). Kembalikan HasilProtonasi."""
    tambal_propka()
    import pdb2pqr.main as P2
    from pdb2pqr.main import run_pdb2pqr
    log = (lambda s: lapor.log.emit(s)) if lapor else (lambda s: None)
    tangkap = _Tangkap()
    lg = [logging.getLogger(n) for n in ("pdb2pqr", "propka", P2._LOGGER.name)]
    lama = [(x.level, x.propagate) for x in lg]
    for x in lg:
        x.addHandler(tangkap)
        x.setLevel(logging.INFO)
        x.propagate = False
    t0 = time.perf_counter()
    try:
        with tempfile.TemporaryDirectory(prefix="vd_pqr_") as d:
            d = Path(d)
            (d / "masuk.pdb").write_text(pdb_teks, encoding="utf-8")
            arg = ["--ff", forcefield, "--ffout", "AMBER", "--titration-state-method", "propka", "--with-ph",
                   f"{ph:.2f}", "--pdb-output", str(d / "keluar.pdb"), "--keep-chain", "--drop-water"]
            if not optimasi_h:
                arg.append("--noopt")
            if not debump:
                arg.append("--nodebump")
            log(f"PDB2PQR + PROPKA pada pH {ph:.1f} (optimasi ikatan H: {'ya' if optimasi_h else 'tidak'})…")
            hilang, pka, _bio = run_pdb2pqr(arg + [str(d / "masuk.pdb"), str(d / "keluar.pqr")])
            pdb = (d / "keluar.pdb").read_text(encoding="utf-8")
            pqr = (d / "keluar.pqr").read_text(encoding="utf-8")
    except (RuntimeError, ValueError) as e:
        alasan = next((m for lv, m in reversed(tangkap.pesan) if lv >= logging.ERROR), str(e))
        raise RuntimeError(f"PDB2PQR gagal: {alasan}") from e
    finally:
        for x, (lv, pr) in zip(lg, lama):
            x.removeHandler(tangkap)
            x.setLevel(lv)
            x.propagate = pr
    h = HasilProtonasi(pdb=_bersihkan_pdb(pdb), pqr=pqr, ph=ph, detik=time.perf_counter() - t0)
    for r in (pka or []):
        if r.get("pKa") is None:
            continue
        h.pka.append({"residu": r.get("res_name", ""), "rantai": (r.get("chain_id") or "").strip(),
                      "nomor": r.get("res_num"), "jenis": r.get("group_type", ""), "pka": float(r["pKa"]),
                      "pka_model": float(r.get("model_pKa") or 0), "terkubur": float(r.get("buried") or 0)})
    sudah = set()
    for b in h.pdb.splitlines():
        if b.startswith("ATOM") and b[17:20].strip() in NAMA_KEADAAN:
            k = (b[21], b[22:27].strip(), b[17:20].strip())
            if k not in sudah:
                sudah.add(k)
                h.keadaan.append((f"{k[2]} {k[1]} {k[0]}".strip(), k[2], NAMA_KEADAAN[k[2]]))
    import re
    for lv, m in tangkap.pesan:
        a = re.match(r"Added atom (\S+) to residue (\S+) (\S+) (\S+)", m)
        if a:
            t = f"{a.group(2)} {a.group(4)} {a.group(3)}: {a.group(1)}"
            if t not in h.diperbaiki:
                h.diperbaiki.append(t)
        elif lv >= logging.WARNING and not m.startswith(("Missing atom", "Ignoring")):
            if m not in h.peringatan:
                h.peringatan.append(m)
    if hilang:
        h.peringatan.append(f"{len(hilang)} residu tidak dapat dilengkapi PDB2PQR")
    log(f"Protonasi selesai {h.detik:.1f} s: {len(h.keadaan)} residu keadaan tak-baku, "
        f"{len(h.diperbaiki)} atom/residu dilengkapi")
    return h


def sesuaikan_his_logam(pdb, logam, batas=2.8):
    """His yang mengoordinasi ion logam: N pengikat tidak boleh ber-H. Nδ1 ke logam -> HIE, Nε2 -> HID.

    logam: [(x, y, z)]. H residu yang diubah dibuang agar Meeko menambahkannya ulang sesuai templat.
    Kembalikan (pdb baru, [label residu diubah])."""
    import math
    if not logam:
        return pdb, []
    baris = pdb.splitlines()
    his = {}
    for b in baris:
        if b.startswith("ATOM") and b[17:20] in ("HIS", "HID", "HIE", "HIP") and b[12:16].strip() in ("ND1", "NE2"):
            k = (b[21], b[22:27])
            p = (float(b[30:38]), float(b[38:46]), float(b[46:54]))
            d = min(math.dist(p, m) for m in logam)
            if d <= batas:
                his.setdefault(k, []).append((d, b[12:16].strip()))
    ubah = {}
    for k, v in his.items():
        n = min(v)[1]
        ubah[k] = "HIE" if n == "ND1" else "HID"
    if not ubah:
        return pdb, []
    out = []
    for b in baris:
        k = (b[21], b[22:27]) if b.startswith("ATOM") else None
        if k in ubah:
            if b[76:78].strip() == "H" or b[12:16].strip().startswith("H"):
                continue
            b = b[:17] + ubah[k] + b[20:]
        out.append(b)
    return "\n".join(out) + "\n", [f"{v} {k[1].strip()} {k[0]} (koordinasi logam)" for k, v in ubah.items()]


def _bersihkan_pdb(pdb):
    """Ambil baris ATOM/HETATM/TER saja (PDB2PQR menulis REMARK panjang)."""
    return "\n".join(b for b in pdb.splitlines() if b.startswith(("ATOM", "HETATM", "TER"))) + "\nEND\n"


def ringkas_pka(h, n=12):
    """Teks laporan: gugus dengan pKa bergeser ≥ 1 dari model atau dekat pH (±1), urut pergeseran."""
    baris = []
    for p in h.pka:
        geser = p["pka"] - p["pka_model"]
        if abs(geser) >= 1.0 or abs(p["pka"] - h.ph) <= 1.0:
            g = p["residu"] + ("" if p["jenis"] in (p["residu"], "COO") else f" ({p['jenis']})")
            baris.append((abs(geser), f"{g:<9} {p['nomor']:>4} {p['rantai']}  pKa {p['pka']:5.2f} "
                                      f"(model {p['pka_model']:4.1f}, geser {geser:+.2f}, terkubur "
                                      f"{p['terkubur'] * 100:3.0f} %)"))
    baris.sort(key=lambda x: -x[0])
    return [b for _, b in baris[:n]]


def csv_pka(h):
    out = ["Gugus;Residu;Rantai;Nomor;pKa;pKa model;Pergeseran;Terkubur (%);Bermuatan pada pH " + f"{h.ph:.1f}"]
    for p in h.pka:
        asam = p["jenis"] in ("ASP", "GLU", "C-", "TYR", "CYS")
        muatan = (p["pka"] < h.ph) if asam else (p["pka"] > h.ph)
        out.append(";".join([p["jenis"], p["residu"], p["rantai"], str(p["nomor"]), f"{p['pka']:.2f}",
                             f"{p['pka_model']:.2f}", f"{p['pka'] - p['pka_model']:+.2f}",
                             f"{p['terkubur'] * 100:.0f}", "ya" if muatan else "tidak"]).replace(".", ","))
    return "\n".join(out) + "\n"
