"""Desain generatif terpandu docking (F8).

Dari satu senyawa induk, bangun analog dengan CReM (BSD-3-Clause), saring dengan aturan yang sudah
dipakai modul sifat dan MPO, lalu peringkat secara multi-objektif. Fragmen CReM berasal dari senyawa
nyata, sehingga analognya cenderung masih dapat disintesis, berbeda dari pembangkit acak.

Basis data fragmen dibangun sendiri dari pustaka lokal (lihat `dev/buat_db_fragmen.py`), bukan
diunduh dari basis data ChEMBL penuh yang berukuran gigabyte. Konsekuensinya keragaman fragmennya
lebih sempit; itu disebut apa adanya di `catatan_basis_data()` dan ikut ke paragraf metode.

Alur lengkapnya (`siklus`) memerlukan fungsi docking dari pemanggil, supaya modul ini tidak
bergantung pada antrean dan tetap dapat diuji tanpa menjalankan docking.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import catat, paths

OPERASI = ("mutate", "grow", "link")

# Ambang saringan; sama dengan yang dipakai modul sifat dan MPO supaya hasilnya konsisten
SA_MAKS = 4.0
QED_MIN = 0.4
KEBARUAN_MAKS = 0.8      # Tanimoto ke induk; analog yang terlalu mirip tidak menambah informasi


@dataclass
class Kandidat:
    smiles: str
    induk: str = ""
    operasi: str = ""
    generasi: int = 1
    qed: Optional[float] = None
    sascore: Optional[float] = None
    mpo: Optional[float] = None
    kemiripan_induk: Optional[float] = None
    dg: Optional[float] = None
    alasan_tolak: str = ""
    inchikey: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in
                ("smiles", "induk", "operasi", "generasi", "qed", "sascore", "mpo",
                 "kemiripan_induk", "dg", "alasan_tolak", "inchikey")}


def basis_data() -> Optional[Path]:
    """Berkas basis data fragmen bawaan paket, atau None bila tidak ikut dibundel."""
    p = paths.data_app() / "crem" / "fragmen_lokal.db" if hasattr(paths, "data_app") else None
    if p and p.exists():
        return p
    for kandidat in (Path(__file__).resolve().parents[1] / "data" / "crem" / "fragmen_lokal.db",
                     paths.BIN.parent / "data" / "crem" / "fragmen_lokal.db"):
        if kandidat.exists():
            return kandidat
    return None


def catatan_basis_data() -> str:
    """Keterangan asal fragmen; wajib ikut ke paragraf metode supaya cakupannya tidak dilebihkan."""
    p = basis_data()
    if not p:
        return "Basis data fragmen tidak ikut dalam pemasangan ini."
    sumber = p.parent / "sumber.txt"
    if sumber.exists():
        return sumber.read_text(encoding="utf-8").strip().replace("\n", " ")
    return f"Basis data fragmen lokal: {p.name}."


def _catatan_basis_data_aktif() -> str:
    from .. import i18n
    return catatan_basis_data_en() if i18n.inggris() else catatan_basis_data()


def catatan_basis_data_en() -> str:
    """Versi Inggris catatan_basis_data. Isi sumber.txt ditulis dev/buat_db_fragmen.py dalam Bahasa Indonesia,
    jadi angkanya dibaca ulang dari berkas itu, bukan diterjemahkan kata per kata."""
    import re
    p = basis_data()
    if not p:
        return "The fragment database is not included in this installation."
    sumber = p.parent / "sumber.txt"
    if not sumber.exists():
        return f"Local fragment database: {p.name}."
    isi = sumber.read_text(encoding="utf-8")
    n = re.search(r"dari (\d+) senyawa", isi)
    rad = re.search(r"Radius konteks: ([\d ]+)\.", isi)
    inti = re.search(r"Maksimum atom berat inti: (\d+)", isi)
    tgl = re.search(r"pada (\d{4}-\d{2}-\d{2})", isi)
    return ("The CReM fragment database was built from "
            + (f"{n.group(1)} compounds of the local VirmoLab library (approved drugs, ChEMBL snapshot)" if n
               else "the local VirmoLab library")
            + (f"; context radii {rad.group(1).strip().replace(' ', ', ')}" if rad else "")
            + (f"; maximum core size {inti.group(1)} heavy atoms" if inti else "")
            + "; built with cremdb_create (crem, BSD-3-Clause)"
            + (f" on {tgl.group(1)}" if tgl else "") + ".")


def tersedia() -> Dict[str, Any]:
    """{ada, pesan, db}: apakah paket crem dan basis data fragmen siap dipakai."""
    try:
        import importlib.util
        if importlib.util.find_spec("crem") is None:
            raise ImportError
    except ImportError:
        return {"ada": False, "db": "", "pesan": "Paket crem belum terpasang di lingkungan ini."}
    db = basis_data()
    if not db:
        return {"ada": False, "db": "", "pesan": "Basis data fragmen tidak ditemukan. "
                                                 "Bangun dengan dev/buat_db_fragmen.py."}
    return {"ada": True, "db": str(db),
            "pesan": f"CReM siap. {_catatan_basis_data_aktif()}"}


def _mol(smiles: str):
    from rdkit import Chem

    return Chem.MolFromSmiles(smiles)


def generasi(induk: str, operasi: str = "mutate", radius: int = 2, maks: int = 500,
             pasangan: Optional[str] = None, benih: int = 42) -> List[Kandidat]:
    """Bangun analog dari satu induk dengan operasi CReM.

    operasi: 'mutate' mengganti fragmen, 'grow' menambah fragmen pada hidrogen, 'link' menyambung
    induk dengan molekul kedua (`pasangan` wajib diisi). radius = ukuran konteks kimia yang harus
    cocok; makin besar makin konservatif dan makin sedikit hasilnya.
    """
    from rdkit import Chem

    if operasi not in OPERASI:
        raise ValueError(f"Operasi '{operasi}' tidak dikenal. Pilihan: {', '.join(OPERASI)}.")
    info = tersedia()
    if not info["ada"]:
        raise RuntimeError(info["pesan"])

    m = _mol(induk)
    if m is None:
        raise ValueError("SMILES induk tidak valid.")

    from crem.crem import grow_mol, link_mols, mutate_mol

    db = info["db"]
    try:
        if operasi == "mutate":
            keluar = mutate_mol(m, db, radius=radius, max_replacements=maks, return_mol=False)
        elif operasi == "grow":
            keluar = grow_mol(m, db, radius=radius, max_replacements=maks, return_mol=False)
        else:
            m2 = _mol(pasangan or "")
            if m2 is None:
                raise ValueError("Operasi 'link' memerlukan molekul kedua yang valid.")
            keluar = link_mols(m, m2, db=db, radius=radius, max_replacements=maks, return_mol=False)
    except Exception as e:
        raise RuntimeError(f"CReM gagal membangun analog: {e}") from e

    induk_kanon = Chem.MolToSmiles(m)
    hasil, terlihat = [], set()
    for smi in keluar:
        mm = _mol(smi)
        if mm is None:
            continue
        kanon = Chem.MolToSmiles(mm)
        if kanon == induk_kanon:
            continue
        kunci = Chem.MolToInchiKey(mm)
        if not kunci or kunci in terlihat:
            continue
        terlihat.add(kunci)
        hasil.append(Kandidat(smiles=kanon, induk=induk_kanon, operasi=operasi, inchikey=kunci))
    return hasil


def _kemiripan(a, b) -> float:
    from rdkit import DataStructs
    from rdkit.Chem import rdFingerprintGenerator

    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    return float(DataStructs.TanimotoSimilarity(gen.GetFingerprint(a), gen.GetFingerprint(b)))


def saring(kandidat: Sequence[Kandidat], sa_maks: float = SA_MAKS, qed_min: float = QED_MIN,
           kebaruan_maks: float = KEBARUAN_MAKS, preset_mpo: str = "oral",
           buang_pains: bool = True, buang_brenk: bool = True,
           relatif_induk: bool = True) -> Tuple[List[Kandidat], List[Kandidat]]:
    """Saring kandidat dan kembalikan (lolos, ditolak). Setiap penolakan menyimpan alasannya.

    `relatif_induk` menurunkan ambang QED dan menaikkan ambang SAScore sampai setara induk bila induk
    sendiri sudah di luar ambang baku. Tanpa ini, optimasi senyawa seperti inhibitor peptidomimetik
    (indinavir ber-QED sekitar 0,24) menolak seluruh turunannya, sehingga fiturnya tidak terpakai
    justru pada kasus yang paling membutuhkannya. Ambang baku tetap berlaku bila induknya sudah lolos.

    Nilai sifat tetap dihitung untuk yang ditolak, supaya pengguna bisa melihat sebabnya dan
    melonggarkan ambang bila perlu.
    """
    from . import mpo as mpo_mod
    from . import sifat as sifat_mod

    sifat_induk = {}
    if relatif_induk:
        for induk_smi in {k.induk for k in kandidat if k.induk}:
            mi = _mol(induk_smi)
            if mi is None:
                continue
            try:
                si = sifat_mod.hitung(mi)
                sifat_induk[induk_smi] = (float(si.get("qed") or 0.0), float(si.get("sascore") or 0.0))
            except Exception:
                continue

    lolos, ditolak = [], []
    for k in kandidat:
        m = _mol(k.smiles)
        if m is None:
            k.alasan_tolak = "struktur tidak dapat diurai"
            ditolak.append(k)
            continue
        try:
            s = sifat_mod.hitung(m)
        except Exception as e:
            k.alasan_tolak = f"sifat gagal dihitung: {e}"
            ditolak.append(k)
            continue

        k.qed = round(float(s.get("qed") or 0.0), 3)
        k.sascore = round(float(s.get("sascore") or 0.0), 2)
        try:
            k.mpo = mpo_mod.hitung_mpo(s, preset=preset_mpo).get("skor")
        except Exception:
            k.mpo = None
        induk_mol = _mol(k.induk) if k.induk else None
        k.kemiripan_induk = round(_kemiripan(induk_mol, m), 3) if induk_mol is not None else None

        qed_batas, sa_batas = qed_min, sa_maks
        if relatif_induk and k.induk in sifat_induk:
            qed_induk, sa_induk = sifat_induk[k.induk]
            qed_batas = min(qed_min, round(qed_induk, 3))
            sa_batas = max(sa_maks, round(sa_induk, 2))

        sebab = []
        if buang_pains and s.get("pains"):
            sebab.append("PAINS")
        if buang_brenk and s.get("brenk"):
            sebab.append("Brenk")
        if k.sascore and k.sascore > sa_batas:
            sebab.append(f"SA {k.sascore} > {sa_batas}")
        if k.qed is not None and k.qed < qed_batas:
            sebab.append(f"QED {k.qed} < {qed_batas}")
        if k.kemiripan_induk is not None and k.kemiripan_induk > kebaruan_maks:
            sebab.append(f"terlalu mirip induk (Tanimoto {k.kemiripan_induk})")

        if sebab:
            k.alasan_tolak = "; ".join(sebab)
            ditolak.append(k)
        else:
            lolos.append(k)
    return lolos, ditolak


def pareto(kandidat: Sequence[Kandidat]) -> List[Kandidat]:
    """Front Pareto pertama atas (ΔG rendah, QED tinggi, SAScore rendah).

    Kandidat tanpa ΔG tidak dapat dibandingkan pada sumbu itu, jadi dikeluarkan dari front, bukan
    diberi nilai pengganti.
    """
    layak = [k for k in kandidat if k.dg is not None and k.qed is not None and k.sascore is not None]

    def tidak_lebih_buruk(a, b):
        return a.dg <= b.dg and a.qed >= b.qed and a.sascore <= b.sascore

    def lebih_baik_di_satu(a, b):
        return a.dg < b.dg or a.qed > b.qed or a.sascore < b.sascore

    front = []
    for k in layak:
        didominasi = any(tidak_lebih_buruk(l, k) and lebih_baik_di_satu(l, k)
                         for l in layak if l is not k)
        if not didominasi:
            front.append(k)
    return sorted(front, key=lambda k: (k.dg, -k.qed, k.sascore))


def silsilah(kandidat: Sequence[Kandidat]) -> Dict[str, Any]:
    """Graf induk ke anak untuk ditampilkan dengan `core/graf.py`: {simpul, tepi}."""
    simpul, tepi = {}, []
    for k in kandidat:
        simpul.setdefault(k.smiles, {"id": k.smiles, "generasi": k.generasi, "dg": k.dg,
                                     "qed": k.qed, "sascore": k.sascore})
        if k.induk:
            simpul.setdefault(k.induk, {"id": k.induk, "generasi": max(0, k.generasi - 1),
                                        "dg": None, "qed": None, "sascore": None})
            tepi.append({"dari": k.induk, "ke": k.smiles, "operasi": k.operasi})
    return {"simpul": list(simpul.values()), "tepi": tepi}


def siklus(induk: str, dock: Optional[Callable[[Sequence[Kandidat], bool], None]] = None,
           n_generasi: int = 3, operasi: str = "mutate", radius: int = 2, maks: int = 500,
           n_docking_penuh: int = 20, batal=None,
           progres: Optional[Callable[[int, int, str], None]] = None,
           **opsi_saring) -> Dict[str, Any]:
    """Jalankan beberapa generasi: bangun, saring, docking cepat, docking penuh untuk yang teratas.

    `dock(kandidat, penuh)` diisi pemanggil dan mengisi atribut `dg` tiap kandidat; kandidat yang
    gagal di-docking tetap bernilai None dan dihitung terpisah, tidak diberi skor pengganti. Tanpa
    `dock`, siklus berhenti setelah penyaringan dan ΔG tetap kosong.
    """
    def _dibatalkan():
        if batal is None:
            return False
        return batal() if callable(batal) else bool(getattr(batal, "is_set", lambda: False)())

    def _lapor(i, n, pesan):
        if progres:
            progres(i, n, pesan)

    semua: List[Kandidat] = []
    ditolak_semua: List[Kandidat] = []
    induk_aktif = induk
    n_gagal_docking = 0

    for g in range(1, max(1, n_generasi) + 1):
        if _dibatalkan():
            break
        _lapor(g - 1, n_generasi, f"Generasi {g}: membangun analog dari {induk_aktif[:40]}…")
        anak = generasi(induk_aktif, operasi=operasi, radius=radius, maks=maks)
        for k in anak:
            k.generasi = g

        _lapor(g - 1, n_generasi, f"Generasi {g}: menyaring {len(anak)} analog…")
        lolos, ditolak = saring(anak, **opsi_saring)
        ditolak_semua.extend(ditolak)
        if not lolos:
            catat.log.info(f"Generasi {g} tidak menyisakan kandidat setelah penyaringan.")
            break

        if dock is not None and not _dibatalkan():
            _lapor(g - 1, n_generasi, f"Generasi {g}: docking cepat {len(lolos)} kandidat…")
            dock(lolos, False)
            berhasil = [k for k in lolos if k.dg is not None]
            n_gagal_docking += len(lolos) - len(berhasil)
            teratas = sorted(berhasil, key=lambda k: k.dg)[:n_docking_penuh]
            if teratas and not _dibatalkan():
                _lapor(g - 1, n_generasi, f"Generasi {g}: docking penuh {len(teratas)} teratas…")
                dock(teratas, True)

        semua.extend(lolos)
        berperingkat = [k for k in lolos if k.dg is not None]
        if berperingkat:
            induk_aktif = min(berperingkat, key=lambda k: k.dg).smiles
        else:
            induk_aktif = lolos[0].smiles
        _lapor(g, n_generasi, f"Generasi {g} selesai: {len(lolos)} kandidat lolos saringan.")

    return {"kandidat": semua, "ditolak": ditolak_semua, "pareto": pareto(semua),
            "silsilah": silsilah(semua), "n_gagal_docking": n_gagal_docking,
            "induk": induk, "catatan_db": catatan_basis_data()}


def paragraf_metode(hasil: Dict[str, Any], operasi: str = "mutate", radius: int = 2,
                    sa_maks: float = SA_MAKS, qed_min: float = QED_MIN) -> str:
    """Kalimat metode dari hasil nyata; kosong bila belum ada kandidat."""
    kandidat = hasil.get("kandidat") or []
    if not kandidat:
        return ""
    n_pareto = len(hasil.get("pareto") or [])
    n_tolak = len(hasil.get("ditolak") or [])
    berdg = [k for k in kandidat if k.dg is not None] if hasattr(kandidat[0], "dg") else []
    from .. import i18n
    if i18n.inggris():
        teks = (f"Analogues were generated from the parent compound with CReM (operation {operasi}, context "
                f"radius {radius}) using a fragment database built from the local compound library. "
                f"{len(kandidat)} analogues passed filtering and {n_tolak} were rejected by the substructure "
                f"filters (PAINS and Brenk), synthetic accessibility (SAScore <= {sa_maks:g}), drug-likeness "
                f"(QED >= {qed_min:g}), and novelty relative to the parent.")
        if berdg:
            teks += (f" {len(berdg)} candidates were docked, and {n_pareto} of them lie on the first Pareto "
                     "front over binding free energy, QED, and SAScore.")
            if hasil.get("n_gagal_docking"):
                teks += f" {hasil['n_gagal_docking']} candidates failed docking and were excluded from the ranking."
        return (teks + " " + hasil.get("catatan_db_en", catatan_basis_data_en()) +
                " All analogues are computational proposals that still require assessment by a synthetic chemist.")
    teks = (f"Analog dibangkitkan dari senyawa induk dengan CReM (operasi {operasi}, radius konteks "
            f"{radius}) memakai basis data fragmen yang dibangun dari pustaka senyawa lokal. "
            f"{len(kandidat)} analog lolos penyaringan dan {n_tolak} ditolak oleh saringan substruktur "
            f"pengganggu (PAINS dan Brenk), kemudahan sintesis (SAScore <= {sa_maks:g}), "
            f"kemiripan obat (QED >= {qed_min:g}), dan kebaruan terhadap induk.")
    if berdg:
        teks += (f" {len(berdg)} kandidat berhasil di-docking dan {n_pareto} di antaranya berada pada "
                 "front Pareto pertama atas energi bebas pengikatan, QED, dan SAScore.")
        if hasil.get("n_gagal_docking"):
            teks += f" {hasil['n_gagal_docking']} kandidat gagal di-docking dan dikeluarkan dari peringkat."
    teks += (" " + hasil.get("catatan_db", catatan_basis_data()) +
             " Seluruh analog adalah usulan komputasi yang masih memerlukan penilaian ahli kimia sintesis.")
    return teks
