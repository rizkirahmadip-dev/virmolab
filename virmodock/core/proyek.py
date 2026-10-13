"""Model data proyek VirmoDock (folder *.vmd).

  NamaProyek.vmd/
    proyek.json          semua metadata & parameter (ditulis atomik, 5 cadangan di .cadangan/)
    objek/               isi objek viewer (struktur asli, ligan asli, ...) agar sesi pulih persis
    reseptor/            asli.pdb, bersih.pdb, reseptor.pdbqt, laporan_prep.txt
    ligan/               sumber/*.sdf, pdbqt/*.pdbqt
    grid/                reseptor.gpf, *.map, reseptor.maps.fld (dipakai ulang bila GPF sama)
    hasil/<id_job>/      keluaran mesin per ligan + log
"""
import json
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

VERSI_FORMAT = 1


def nama_aman(t):
    t = re.sub(r"[^A-Za-z0-9_.-]+", "_", t.strip()).strip("._")
    return t[:80] or "x"


def tulis_atomik(path, teks):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(teks)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def migrasi_proyek(data: dict) -> dict:
    """Migrasikan format data proyek dari versi lawas (0.9.x - 1.0.x) ke format terkini."""
    if not isinstance(data, dict):
        return {}
    data.setdefault("format", VERSI_FORMAT)
    data.setdefault("aplikasi", "VirmoDock")
    data.setdefault("ligan", [])
    data.setdefault("job", [])
    data.setdefault("objek", [])
    data.setdefault("uji_grafik", {})
    data.setdefault("komposer", {})
    data.setdefault("validasi", {})
    data.setdefault("blast", {})
    data.setdefault("syarat_jarak", {})
    data.setdefault("eksperimen", {})
    data.setdefault("md", [])
    data.setdefault("templat", "")
    data.setdefault("catatan", "")
    data.setdefault("jejak", [])
    return data


class Proyek:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.nama = self.folder.stem
        self.dibuat = datetime.now().isoformat(timespec="seconds")
        self.reseptor = None          # dict: nama, sumber, pdbqt, bersih, asli, metode, atom, residu, dibuang, logam, objek
        self.ligan = []               # list dict: id, nama, sumber, status, alasan, sdf, pdbqt, rumus, mw, torsi, atom, tipe, objek
        self.kotak = None             # dict: pusat, ukuran, spasi
        self.parameter = {}
        self.uji_grafik = {}          # data & pengaturan tab Uji & Grafik
        self.komposer = {}            # Komposer figur: {panel, opsi}; panel raster disimpan di komposer/*.png
        self.job = []                 # list dict (lihat core/antrean.py)
        self.objek = []               # list dict objek viewer
        self.catatan = ""
        self.validasi = {}            # hasil validasi redocking terakhir
        self.blast = {}               # {rid, rantai} nomor BLAST NCBI yang masih bisa diambil
        self.syarat_jarak = {}        # {rantai, resi, jarak} saringan pose sesudah docking
        self.templat = ""             # kunci templat proyek (core/templat.py), bila dibuat dari templat
        self.md = []                  # riwayat MD / MM-GBSA: {id, mode, tanggal, status, folder, ligan, opsi}
        self.eksperimen = {}          # data aktivitas eksperimen (ChEMBL): target, aktivitas [{chembl, nama, smiles, inchikey, pchembl, …}]
        self.jejak = []               # riwayat sumber data internet: [{sumber, versi, diambil, kueri, lisensi}]

    def catat_jejak(self, jejak):
        """Catat jejak sumber data internet (objek Jejak atau dict) tanpa duplikat (kunci sumber+kueri)."""
        if hasattr(jejak, "to_dict"):
            d = jejak.to_dict()
        elif isinstance(jejak, dict):
            d = dict(jejak)
        else:
            return
        kunci = (d.get("sumber", ""), d.get("kueri", ""))
        for i, entri in enumerate(self.jejak):
            if (entri.get("sumber", ""), entri.get("kueri", "")) == kunci:
                self.jejak[i] = d
                return
        self.jejak.append(d)

    # ------------------------------------------------------------- jalur
    def p(self, *bag):
        return self.folder.joinpath(*bag)

    def rel(self, path):
        return Path(path).resolve().relative_to(self.folder.resolve()).as_posix()

    def siapkan_folder(self):
        for d in ("objek", "reseptor", "ligan/sumber", "ligan/pdbqt", "grid", "hasil", ".cadangan"):
            self.p(d).mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------- simpan/buka
    def ke_dict(self):
        return {"format": VERSI_FORMAT, "aplikasi": "VirmoDock", "nama": self.nama, "dibuat": self.dibuat,
                "diubah": datetime.now().isoformat(timespec="seconds"), "reseptor": self.reseptor,
                "ligan": self.ligan, "kotak": self.kotak, "parameter": self.parameter, "uji_grafik": self.uji_grafik,
                "komposer": self.komposer, "job": self.job,
                "objek": self.objek, "catatan": self.catatan, "validasi": self.validasi,
                "blast": self.blast, "syarat_jarak": self.syarat_jarak,
                "eksperimen": self.eksperimen, "md": self.md, "templat": self.templat,
                "jejak": self.jejak}

    def simpan(self):
        self.siapkan_folder()
        f = self.p("proyek.json")
        if f.exists():  # cadangan bergilir 5 versi
            cad = sorted(self.p(".cadangan").glob("proyek_*.json"))
            for lama in cad[:-4]:
                lama.unlink(missing_ok=True)
            shutil.copy2(f, self.p(".cadangan", f"proyek_{time.strftime('%Y%m%d_%H%M%S')}.json"))
        tulis_atomik(f, json.dumps(self.ke_dict(), ensure_ascii=False, indent=1))

    @classmethod
    def buka(cls, folder):
        folder = Path(folder)
        f = folder / "proyek.json"
        if not f.exists():
            raise FileNotFoundError(f"{folder} bukan folder proyek VirmoDock (proyek.json tidak ada).")
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cad = sorted((folder / ".cadangan").glob("proyek_*.json"))
            if not cad:
                raise
            d = json.loads(cad[-1].read_text(encoding="utf-8"))
        d = migrasi_proyek(d)
        pr = cls(folder)
        pr.nama = d.get("nama", folder.stem)
        pr.dibuat = d.get("dibuat", pr.dibuat)
        for k in ("reseptor", "kotak", "catatan"):
            setattr(pr, k, d.get(k))
        pr.catatan = pr.catatan or ""
        pr.ligan = d.get("ligan") or []
        pr.parameter = d.get("parameter") or {}
        pr.uji_grafik = d.get("uji_grafik") or {}
        pr.komposer = d.get("komposer") or {}
        pr.job = d.get("job") or []
        pr.objek = d.get("objek") or []
        pr.validasi = d.get("validasi") or {}
        pr.blast = d.get("blast") or {}
        pr.syarat_jarak = d.get("syarat_jarak") or {}
        pr.eksperimen = d.get("eksperimen") or {}
        pr.md = d.get("md") or []
        pr.templat = d.get("templat") or ""
        pr.jejak = d.get("jejak") or []
        # job yang terputus (aplikasi ditutup/crash) bisa dilanjutkan
        for j in pr.job:
            if j.get("status") in ("berjalan", "menunggu"):
                j["status"] = "dijeda"
                for l in j.get("ligan", []):
                    if l.get("status") == "berjalan":
                        l["status"] = "menunggu"
                        l["progres"] = 0
        return pr

    @classmethod
    def baru(cls, induk, nama):
        folder = Path(induk) / (nama_aman(nama) + ".vmd")
        n = 2
        while folder.exists():
            folder = Path(induk) / f"{nama_aman(nama)}_{n}.vmd"
            n += 1
        pr = cls(folder)
        pr.nama = nama
        pr.siapkan_folder()
        pr.simpan()
        return pr

    # -------------------------------------------------------------- objek
    def simpan_objek(self, daftar):
        """daftar: objek molekul.Objek dari sesi. Teks ditulis ke objek/<id>.<fmt>."""
        self.p("objek").mkdir(parents=True, exist_ok=True)
        hasil, dipakai = [], set()
        for o in daftar:
            nama_f = f"{o.id}.{o.fmt}"
            f = self.p("objek", nama_f)
            if not f.exists() or f.stat().st_size != len(o.teks.encode()):
                f.write_text(o.teks, encoding="utf-8")
            dipakai.add(nama_f)
            hasil.append({"id": o.id, "nama": o.nama, "jenis": o.jenis, "fmt": o.fmt, "berkas": f"objek/{nama_f}",
                          "sumber": o.sumber, "tampil": o.tampil, "rantai": o.rantai, "info": o.info, "gaya": o.gaya,
                          "induk": o.induk, "grup": getattr(o, "grup", "")})
        for f in self.p("objek").glob("*"):
            if f.name not in dipakai:
                f.unlink(missing_ok=True)
        self.objek = hasil

    def muat_objek(self):
        from . import molekul
        hasil = []
        for d in self.objek:
            f = self.p(d["berkas"])
            if not f.exists():
                continue
            o = molekul.Objek(nama=d["nama"], jenis=d["jenis"], teks=f.read_text(encoding="utf-8"), fmt=d["fmt"],
                              sumber=d.get("sumber", ""), id=molekul.id_baru(), tampil=d.get("tampil", True),
                              rantai={k: [tuple(x) for x in v] for k, v in (d.get("rantai") or {}).items()},
                              info=d.get("info") or {}, gaya=d.get("gaya") or {}, induk=d.get("induk", ""),
                              grup=d.get("grup", ""))
            o.id_lama = d["id"]
            hasil.append(o)
        # petakan id lama -> baru untuk referensi induk/reseptor/ligan
        peta = {o.id_lama: o.id for o in hasil}
        for o in hasil:
            o.induk = peta.get(o.induk, "")
        return hasil, peta

    # ------------------------------------------------------------- ligan
    def ligan_siap(self):
        return [l for l in self.ligan if l.get("status") in ("siap", "peringatan") and l.get("pdbqt")]

    def cari_ligan(self, lid):
        return next((l for l in self.ligan if l["id"] == lid), None)

    def smiles_ligan(self, l):
        """SMILES netral ligan proyek: kunci smiles, cache sifat, SDF sumber, lalu REMARK SMILES PDBQT ('' bila gagal)."""
        if not l:
            return ""
        smi = l.get("smiles") or (l.get("sifat") or {}).get("smiles")
        if smi:
            return smi
        if not hasattr(self, "_smiles"):
            self._smiles = {}
        if l.get("id") in self._smiles:
            return self._smiles[l["id"]]
        smi = ""
        try:
            from rdkit import Chem
            f = self.p(l["sdf"]) if l.get("sdf") else None
            if f and f.exists():
                m = Chem.MolFromMolBlock(f.read_text(encoding="utf-8").split("$$$$")[0])
                smi = Chem.MolToSmiles(Chem.RemoveHs(m)) if m is not None else ""
            f = self.p(l["pdbqt"]) if not smi and l.get("pdbqt") else None
            if f and f.exists():
                for b in f.read_text(encoding="utf-8", errors="replace").splitlines():
                    if b.startswith("REMARK SMILES ") and not b.startswith("REMARK SMILES IDX"):
                        m = Chem.MolFromSmiles(b.split(None, 2)[2].strip())
                        if m is not None:
                            from rdkit.Chem.MolStandardize import rdMolStandardize
                            smi = Chem.MolToSmiles(rdMolStandardize.Uncharger().uncharge(m))
                        break
        except Exception:
            smi = ""
        self._smiles[l.get("id")] = smi
        return smi

    def id_ligan_baru(self, nama):
        dasar = nama_aman(nama)
        ada = {l["id"] for l in self.ligan}
        lid, n = dasar, 2
        while lid in ada:
            lid = f"{dasar}_{n}"
            n += 1
        return lid

    def job_baru_id(self):
        dasar = time.strftime("J%Y%m%d_%H%M%S")
        ada = {j["id"] for j in self.job}
        jid, n = dasar, 2
        while jid in ada:
            jid = f"{dasar}_{n}"
            n += 1
        return jid
