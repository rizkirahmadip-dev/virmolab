"""Pengendali penapisan bertahap (pembelajaran aktif): memilih batch, menyiapkan ligan, mengantrekan docking, dan
mengumpulkan skornya, putaran demi putaran.

Dimiliki jendela utama (bukan dialog), jadi kampanye terus berjalan walaupun dialognya ditutup. Statusnya disimpan di
proyek (proyek.pembelajaran_aktif), sehingga kampanye yang terputus (aplikasi ditutup, job dijeda) bisa dilanjutkan.
Perhitungan berat (sidik jari, pelatihan model, preparasi ligan) berjalan di thread latar; perubahan status kampanye
dan proyek hanya dilakukan di thread GUI.
"""
import shutil
import time
from datetime import datetime

from PySide6.QtCore import QObject, Signal

from ..core import antrean
from ..core import pembelajaran_aktif as PA
from . import kerja

BERKAS_PUSTAKA = "pustaka.tsv.gz"


class PengendaliAL(QObject):
    berubah = Signal(str)                    # id kampanye: status/skor berubah
    kemajuan = Signal(str, int, int, str)    # id kampanye, i, n, teks tahap latar
    galat = Signal(str, str)                 # id kampanye, pesan

    def __init__(self, jw):
        super().__init__(jw)
        self.jw = jw
        self._pustaka = {}       # (folder proyek, id) -> PA.Pustaka
        self._kp = {}            # (folder proyek, id) -> PA.Kampanye
        self._tahap = {}         # id -> teks tahap latar yang sedang berjalan ("" = diam)
        self._jeda = set()       # id kampanye yang berhenti setelah putaran berjalan
        self._aktif = set()      # kampanye yang sedang dijalankan (termasuk jeda antar tahap)
        jw.pelaksana.jobSelesai.connect(self._job_selesai)

    # ------------------------------------------------------------------ akses
    @property
    def proyek(self):
        return self.jw.proyek

    def _kunci(self, cid):
        return (str(self.proyek.folder) if self.proyek else "", cid)

    def daftar(self):
        return list(self.proyek.pembelajaran_aktif) if self.proyek else []

    def cari(self, cid):
        return next((e for e in self.daftar() if e["id"] == cid), None)

    def kampanye(self, cid):
        k = self._kunci(cid)
        if k not in self._kp:
            e = self.cari(cid)
            if e is None:
                return None
            self._kp[k] = PA.Kampanye.dari_dict(e["kampanye"])
        return self._kp[k]

    def pustaka(self, cid):
        return self._pustaka.get(self._kunci(cid))

    def tahap(self, cid):
        return self._tahap.get(cid, "")

    def akan_berhenti(self, cid):
        return cid in self._jeda

    def job_aktif(self, cid):
        e = self.cari(cid)
        j = self.jw.pelaksana.cari(e.get("job")) if e and e.get("job") else None
        return j if j and j["status"] in ("menunggu", "berjalan", "dijeda") else None

    def status(self, cid):
        """baru | berjalan | dijeda | selesai, dibaca dari keadaan nyata (job & tahap latar), bukan hanya label."""
        e = self.cari(cid)
        if e is None:
            return ""
        if self._tahap.get(cid):
            return "berjalan"
        j = self.job_aktif(cid)
        if j is not None:
            return "dijeda" if j["status"] == "dijeda" else "berjalan"
        kp = self.kampanye(cid)
        if kp is not None and kp.selesai():
            return "selesai"
        if cid in self._aktif:      # antara dua tahap (job selesai, putaran berikutnya belum diantrekan)
            return "berjalan"
        return "baru" if not (kp and kp.putaran) else "dijeda"

    def _simpan(self, cid):
        e, kp = self.cari(cid), self._kp.get(self._kunci(cid))
        if e is not None and kp is not None:
            e["kampanye"] = kp.ke_dict()
        self.jw.minta_simpan()
        self.berubah.emit(cid)

    # ------------------------------------------------------------------ membuat
    def buat(self, nama, pustaka, pengaturan, sumber):
        """Kampanye baru dari pustaka yang sudah dibaca. Setelan docking (mesin, parameter, kotak, reseptor) diambil
        dari panel docking sekarang dan dikunci untuk semua putaran, supaya skor antarputaran sebanding."""
        pr = self.proyek
        cid = time.strftime("AL%Y%m%d_%H%M%S")
        while any(e["id"] == cid for e in pr.pembelajaran_aktif):
            cid += "_2"
        pr.siapkan_folder()
        f = pr.p("pembelajaran_aktif", cid, BERKAS_PUSTAKA)
        PA.tulis_pustaka(pustaka, f)
        kp = PA.Kampanye(len(pustaka), pengaturan)
        e = {"id": cid, "nama": nama, "dibuat": datetime.now().isoformat(timespec="seconds"), "sumber": sumber,
             "pustaka": pr.rel(f), "ringkasan_pustaka": dict(pustaka.ringkasan), "docking": self._setelan_docking(),
             "kampanye": kp.ke_dict(), "job": None, "pose": {}}
        pr.pembelajaran_aktif.append(e)
        self._pustaka[self._kunci(cid)] = pustaka
        self._kp[self._kunci(cid)] = kp
        self._simpan(cid)
        return cid

    def _setelan_docking(self):
        jw, pr = self.jw, self.proyek
        p = jw.param.parameter()
        mesin, alat = p["mesin"], p["perangkat"]
        if mesin == "adgpu" and (alat != "gpu" or not (jw.env and jw.env.opencl_ok)):
            mesin, alat = "vina", "cpu"
        par = dict(p, nrun=p["nrun_gpu"] if mesin == "adgpu" else p["nrun_ad4"],
                   nev=p["nev_gpu"] if mesin == "adgpu" else p["nev_ad4"])
        k = jw.box
        return {"mesin": mesin, "perangkat": alat, "parameter": par,
                "kotak": {"pusat": list(k["pusat"]), "ukuran": list(k["ukuran"]), "spasi": k.get("spasi", 0.375)},
                "reseptor": pr.reseptor.get("pdbqt"), **antrean._fleksibel(pr)}

    def hapus(self, cid):
        """Hapus catatan kampanye dan salinan pustakanya. Job dan ligan yang sudah didocking tetap di proyek."""
        if self.job_aktif(cid) or self._tahap.get(cid):
            return False
        pr = self.proyek
        pr.pembelajaran_aktif[:] = [e for e in pr.pembelajaran_aktif if e["id"] != cid]
        shutil.rmtree(pr.p("pembelajaran_aktif", cid), ignore_errors=True)
        self._kp.pop(self._kunci(cid), None)
        self._pustaka.pop(self._kunci(cid), None)
        self.jw.minta_simpan()
        self.berubah.emit(cid)
        return True

    # ------------------------------------------------------------------ menjalankan
    def jalankan(self, cid):
        """Mulai atau lanjutkan: job putaran yang dijeda dilanjutkan; bila tidak ada, putaran berikutnya dipilih."""
        self._jeda.discard(cid)
        self._aktif.add(cid)
        if self._tahap.get(cid):
            return
        j = self.job_aktif(cid)
        if j is not None:
            if j["status"] == "dijeda":
                self.jw.pelaksana.lanjut(j["id"])
            self.berubah.emit(cid)
            return
        self._sinkron(cid)
        self.dengan_pustaka(cid, self._putaran_berikut)

    def berhenti_setelah_putaran(self, cid):
        self._jeda.add(cid)
        self.berubah.emit(cid)

    def hentikan(self, cid):
        """Batalkan job putaran berjalan; ligan yang belum didocking dikembalikan ke kumpulan kandidat."""
        self._jeda.add(cid)
        self._aktif.discard(cid)
        j = self.job_aktif(cid)
        if j is not None:
            self.jw.pelaksana.batal(j["id"])
        self.berubah.emit(cid)

    def _tahap_atur(self, cid, teks):
        if teks:
            self._tahap[cid] = teks
        else:
            self._tahap.pop(cid, None)
        self.berubah.emit(cid)

    def _sah(self, kunci):
        """Hasil kerja latar masih untuk proyek yang sama (pengguna bisa berganti proyek di tengah jalan)."""
        return self.proyek is not None and kunci[0] == str(self.proyek.folder) and self.cari(kunci[1]) is not None

    def _gagal(self, cid, pesan):
        self._aktif.discard(cid)
        self._tahap_atur(cid, "")
        self.galat.emit(cid, pesan.split("\n\n")[0])

    def dengan_pustaka(self, cid, lanjut):
        kunci = self._kunci(cid)
        if kunci in self._pustaka:
            lanjut(cid)
            return
        e = self.cari(cid)
        f = self.proyek.p(e["pustaka"])
        if not f.exists():
            self.galat.emit(cid, f"Salinan pustaka kampanye tidak ditemukan: {f}")
            return
        self._tahap_atur(cid, "Memuat pustaka…")

        def selesai(pus):
            if not self._sah(kunci):
                return
            if len(pus) != self.kampanye(cid).n:
                self._gagal(cid, "Pustaka kampanye berubah (jumlah senyawa tidak cocok); kampanye tidak bisa dilanjutkan.")
                return
            self._pustaka[kunci] = pus
            self._tahap_atur(cid, "")
            lanjut(cid)
        kerja.jalankan(PA.pustaka_dari_berkas, f, selesai=selesai, galat=lambda g: self._gagal(cid, g),
                       progres=lambda i, n, t: self.kemajuan.emit(cid, i, n, t))

    def _putaran_berikut(self, cid):
        kp, kunci = self.kampanye(cid), self._kunci(cid)
        if kp.selesai():
            self._aktif.discard(cid)
            self._simpan(cid)
            return
        if cid in self._jeda:
            self._jeda.discard(cid)
            self._aktif.discard(cid)
            self._simpan(cid)
            return
        if not kp.putaran:
            self._siapkan(cid, kp.batch_awal())
            return
        self._tahap_atur(cid, f"Melatih model dan memilih putaran {len(kp.putaran)}…")
        pus = self._pustaka[kunci]

        def selesai(r):
            if not self._sah(kunci):
                return
            idx = kp.terima_rencana(r)
            if not idx:
                self._aktif.discard(cid)
                self._tahap_atur(cid, "")
                self._simpan(cid)
                return
            self._siapkan(cid, idx)
        kerja.jalankan(lambda lapor: kp.rencana_berikut(pus, lapor), selesai=selesai,
                       galat=lambda g: self._gagal(cid, g), progres=lambda i, n, t: self.kemajuan.emit(cid, i, n, t))

    def _siapkan(self, cid, idx):
        from ..core import prep_ligan
        kunci = self._kunci(cid)
        pus = self._pustaka[kunci]
        ke = len(self.kampanye(cid).putaran) - 1
        self._tahap_atur(cid, f"Menyiapkan {len(idx):,} ligan putaran {ke}…".replace(",", "."))
        self._simpan(cid)
        daftar = [(pus.nama[i] or f"L{i}", pus.smiles[i], "smiles") for i in idx]
        opsi = prep_ligan.OpsiLigan()

        def selesai(hasil):
            if self._sah(kunci):
                self._daftarkan(cid, idx, hasil)
        kerja.jalankan(lambda lapor: prep_ligan.siapkan_banyak(daftar, opsi, lapor=lapor), selesai=selesai,
                       galat=lambda g: self._gagal(cid, g), progres=lambda i, n, t: self.kemajuan.emit(cid, i, n, t))

    def _daftarkan(self, cid, idx, hasil):
        """Ligan yang berhasil disiapkan didaftarkan ke proyek (tanpa objek viewer) lalu satu job diantrekan."""
        pr, e, kp = self.proyek, self.cari(cid), self.kampanye(cid)
        pus = self._pustaka[self._kunci(cid)]
        ke = len(kp.putaran) - 1
        pr.siapkan_folder()
        ada = {l["id"] for l in pr.ligan}
        ligan, gagal = [], {}
        for i, h in zip(idx, hasil):
            if h is None or h.status == "gagal" or not h.pdbqt:
                gagal[i] = None
                continue
            dasar = "".join(c if c.isalnum() or c in "-_" else "_" for c in (h.nama or f"L{i}"))[:40] or f"L{i}"
            lid, n = dasar, 2
            while lid in ada:
                lid, n = f"{dasar}_{n}", n + 1
            ada.add(lid)
            pr.p("ligan", "sumber", f"{lid}.sdf").write_text(h.sdf, encoding="utf-8")
            pr.p("ligan", "pdbqt", f"{lid}.pdbqt").write_text(h.pdbqt, encoding="utf-8")
            info = h.ke_dict()
            info.update(id=lid, sumber=f"Penapisan bertahap {e['nama']}", sdf=f"ligan/sumber/{lid}.sdf",
                        pdbqt=f"ligan/pdbqt/{lid}.pdbqt", smiles=pus.smiles[i], al=cid, al_idx=int(i))
            pr.ligan.append(info)
            ligan.append(info)
        if gagal:
            kp.catat(gagal)
        if not ligan:
            self._tahap_atur(cid, "")
            self._simpan(cid)
            self.dengan_pustaka(cid, self._putaran_berikut)
            return
        d = e["docking"]
        job = antrean.job_baru(pr, ligan, d["mesin"], d["perangkat"], d["parameter"], d["kotak"],
                               nama=f"Penapisan bertahap · {e['nama']} · putaran {ke} · {len(ligan)} ligan")
        job.pop("flex", None)
        job.pop("fleksibel", None)
        job["reseptor"] = d["reseptor"]
        if d.get("flex"):
            job["flex"], job["fleksibel"] = d["flex"], d.get("fleksibel", [])
        job["al"] = {"id": cid, "putaran": ke}
        e["job"] = job["id"]
        self._tahap_atur(cid, "")
        self.jw.pelaksana.tambah(job)
        self._simpan(cid)

    # ------------------------------------------------------------------ hasil job
    def _kumpulkan(self, cid, j):
        """Skor job putaran -> kampanye. Ligan yang batal didocking dikembalikan ke kumpulan kandidat."""
        pr, e, kp = self.proyek, self.cari(cid), self.kampanye(cid)
        lig = {l["id"]: l for l in pr.ligan if l.get("al") == cid}
        hasil, sisa = {}, []
        for x in j["ligan"]:
            l = lig.get(x["id"])
            if l is None:
                continue
            i = int(l["al_idx"])
            if x["status"] == "selesai" and x.get("energi") is not None:
                hasil[i] = float(x["energi"])
                e.setdefault("pose", {})[str(i)] = [j["id"], x["id"]]
            elif x["status"] in ("gagal", "dilewati"):
                hasil[i] = None
            else:
                sisa.append(i)
        kp.catat(hasil)
        kp.lepas(sisa)
        e["job"] = None
        return j["status"] == "dibatalkan"

    def _job_selesai(self, jid):
        if not self.proyek:
            return
        j = self.jw.pelaksana.cari(jid)
        al = (j or {}).get("al")
        if not al or self.cari(al["id"]) is None or self.cari(al["id"]).get("job") != jid:
            return
        cid = al["id"]
        dibatalkan = self._kumpulkan(cid, j)
        if dibatalkan:
            self._jeda.discard(cid)
            self._aktif.discard(cid)
            self._simpan(cid)
            return
        if j["status"] == "gagal":           # tidak satu pun ligan berhasil: jangan terus memutar putaran kosong
            self._aktif.discard(cid)
            self._simpan(cid)
            self.galat.emit(cid, f"Semua ligan putaran {al.get('putaran', '')} gagal didocking. Periksa log antrean "
                                 "(reseptor, kotak, atau mesin docking), lalu klik Lanjutkan.")
            return
        self._simpan(cid)
        self.dengan_pustaka(cid, self._putaran_berikut)

    def _sinkron(self, cid):
        """Kumpulkan skor job putaran yang sudah berakhir tetapi belum tercatat (mis. aplikasi ditutup di antaranya,
        atau job dihapus dari antrean)."""
        e = self.cari(cid)
        if not e or not e.get("job"):
            return
        j = self.jw.pelaksana.cari(e["job"])
        if j is None:
            e["job"] = None
            self.kampanye(cid).lepas(self.kampanye(cid).putaran[-1]["indeks"] if self.kampanye(cid).putaran else [])
        elif j["status"] in ("selesai", "gagal", "dibatalkan"):
            self._kumpulkan(cid, j)
        self._simpan(cid)
