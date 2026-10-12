"""Antrean job docking: satu QProcess per ligan (bukan thread Python).

Job disimpan sebagai dict di proyek.job sehingga status bertahan saat
aplikasi ditutup; job yang terputus dibuka lagi sebagai "dijeda".

Struktur job:
  {id, nama, mesin, mesin_asal, perangkat, parameter, kotak, status, dibuat, mulai, selesai, catatan,
   ligan: [{id, nama, pdbqt, status, progres, keluaran, energi, ki, rmsd_ref, n_pose, pose, pesan, detik}]}
Status job  : menunggu | berjalan | dijeda | selesai | gagal | dibatalkan
Status ligan: menunggu | berjalan | selesai | gagal | dilewati | dibatalkan
"""
import shutil
import time
from datetime import datetime

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from . import mesin as M

SIMPAN_POSE = 20   # jumlah pose (tanpa koordinat) yang diringkas di proyek.json


def job_baru(proyek, ligan, mesin, perangkat, parameter, kotak, nama=None):
    jid = proyek.job_baru_id()
    return {"id": jid, "nama": nama or f"{M.MESIN[mesin]} · {len(ligan)} ligan", "mesin": mesin, "mesin_asal": mesin,
            "perangkat": perangkat, "parameter": dict(parameter), "kotak": dict(kotak), "status": "menunggu",
            "dibuat": datetime.now().isoformat(timespec="seconds"), "mulai": None, "selesai": None, "catatan": [],
            "reseptor": proyek.reseptor.get("pdbqt") if proyek.reseptor else None,
            **_fleksibel(proyek),
            "ligan": [{"id": l["id"], "nama": l["nama"], "pdbqt": l["pdbqt"], "status": "menunggu", "progres": 0,
                       "keluaran": None, "energi": None, "ki": "", "rmsd_ref": None, "n_pose": 0, "pose": [],
                       "pesan": "", "detik": None, **({"flex": l["flex_kov"], "warhead": l.get("warhead", "")}
                                                         if l.get("flex_kov") else {})}
                      for l in ligan]}


def jadikan_kovalen(job, kv):
    """Ubah job biasa menjadi docking kovalen (AD-GPU --flexres per ligan; reseptor tanpa rantai samping sasaran).
    kv: {residu, resn, label, kaku}. Ligan job harus sudah membawa 'flex' (aduk) dan 'pdbqt' templat aduk."""
    job.pop("flex", None)
    job.pop("fleksibel", None)
    job["reseptor"] = kv["kaku"]
    job["kovalen"] = {k: kv[k] for k in ("residu", "resn", "label") if k in kv}
    job["nama"] = f"{M.MESIN[job['mesin']]} · kovalen {kv.get('label', kv.get('residu', ''))} · {len(job['ligan'])} ligan"
    return job


def _fleksibel(proyek):
    """Reseptor dengan residu fleksibel aktif -> job memakai PDBQT kaku + berkas flex."""
    fx = (proyek.reseptor or {}).get("fleksibel") or {}
    if not (fx.get("aktif") and fx.get("kaku") and fx.get("flex")):
        return {}
    return {"reseptor": fx["kaku"], "flex": fx["flex"], "fleksibel": list(fx.get("residu") or [])}


class Pelaksana(QObject):
    jobBerubah = Signal(str)                  # id job (tabel antrean diperbarui)
    liganSelesai = Signal(str, str)           # id job, id ligan
    jobSelesai = Signal(str)                  # id job (selesai / gagal / dibatalkan)
    log = Signal(str)
    pesan = Signal(str)                       # pesan penting untuk panel Pesan
    perluSimpan = Signal()
    qcSelesai = Signal(str, str, object)      # id job, id ligan, hasil PoseBusters (dari thread pekerja)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proyek = None
        self.proc = None
        self.job = None           # job yang sedang dijalankan
        self.lig = None           # ligan yang sedang dijalankan
        self.tahap = None         # "grid" | "dock"
        self.keluaran = ""
        self.mulai_lig = 0.0
        self.pembaca = None
        self.minta_jeda = set()
        self.timer_dlg = QTimer(self)
        self.timer_dlg.setInterval(1000)
        self.timer_dlg.timeout.connect(self._intip_dlg)
        self._dlg_pos = 0
        self._qc_pool = None      # PoseBusters di thread terpisah (± 0,4 s/pose) agar GUI tetap responsif
        self.qcSelesai.connect(self._qc_masuk)

    # ---------------------------------------------------------- QC pose
    def _qc_antre(self, j, l, pose):
        from . import qc
        if not qc.tersedia():
            return
        if self._qc_pool is None:
            from concurrent.futures import ThreadPoolExecutor
            self._qc_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qc")
        pr, jid, lid = self.proyek, j["id"], l["id"]
        salinan = dict(l)

        def kerja():
            try:
                h = qc.periksa_ligan(pr, j, salinan, pose)
            except Exception as e:   # jangan sampai thread mati diam-diam
                h = {"v": qc.VERSI, "galat": str(e)[:200]}
            if h is not None:
                self.qcSelesai.emit(jid, lid, h)   # antre ke thread GUI
        self._qc_pool.submit(kerja)

    def _qc_masuk(self, jid, lid, h):
        j = self.cari(jid)
        l = next((x for x in (j or {}).get("ligan", []) if x["id"] == lid), None)
        if l is None:
            return
        l["qc"] = h
        if h.get("gagal"):
            self.log.emit(f"PoseBusters {l['nama']}: gagal {len(h['gagal'])} uji - " + ", ".join(h["gagal"]))
        self.liganSelesai.emit(jid, lid)
        self.perluSimpan.emit()

    # ---------------------------------------------------------- publik
    def atur_proyek(self, proyek):
        if self.sibuk():
            self.batal(self.job["id"])
        self.proyek = proyek

    def sibuk(self):
        return self.proc is not None and self.proc.state() != QProcess.NotRunning

    def cari(self, jid):
        return next((j for j in (self.proyek.job if self.proyek else []) if j["id"] == jid), None)

    def tambah(self, job):
        self.proyek.job.append(job)
        self.log.emit(f"Job {job['id']} ditambahkan: {job['nama']}")
        self._simpan()
        self.jobBerubah.emit(job["id"])
        self._berikut()

    def jeda(self, jid):
        j = self.cari(jid)
        if not j:
            return
        if j is self.job and self.sibuk():
            self.minta_jeda.add(jid)
            self.log.emit(f"Job {jid} akan dijeda setelah ligan saat ini selesai.")
        elif j["status"] == "menunggu":
            j["status"] = "dijeda"
        self._ubah(j)

    def lanjut(self, jid):
        j = self.cari(jid)
        if not j or j["status"] not in ("dijeda", "gagal", "dibatalkan"):
            return
        self.minta_jeda.discard(jid)
        for l in j["ligan"]:
            if l["status"] in ("gagal", "dibatalkan", "berjalan"):
                l["status"], l["progres"], l["pesan"] = "menunggu", 0, ""
        j["status"] = "menunggu"
        self._ubah(j)
        self._berikut()

    def batal(self, jid):
        j = self.cari(jid)
        if not j:
            return
        if j is self.job and self.sibuk():
            j["status"] = "dibatalkan"
            self.proc.kill()
            return  # _proses_selesai menyelesaikan sisanya
        if j["status"] in ("menunggu", "dijeda"):
            j["status"] = "dibatalkan"
            for l in j["ligan"]:
                if l["status"] == "menunggu":
                    l["status"] = "dibatalkan"
            self._ubah(j)
            self.jobSelesai.emit(jid)

    def hapus_selesai(self):
        if not self.proyek:
            return
        self.proyek.job = [j for j in self.proyek.job if j["status"] not in ("selesai", "gagal", "dibatalkan")]
        self._simpan()
        self.jobBerubah.emit("")

    def hentikan_semua(self):
        """Dipanggil saat aplikasi ditutup: proses dihentikan, job jadi 'dijeda' agar bisa dilanjutkan."""
        if self.sibuk():
            j = self.job
            self.proc.kill()
            self.proc.waitForFinished(3000)
            if j:
                j["status"] = "dijeda"

    # ---------------------------------------------------------- internal
    def _simpan(self):
        self.perluSimpan.emit()

    def _ubah(self, j):
        self._simpan()
        self.jobBerubah.emit(j["id"])

    def _folder_job(self, j):
        f = self.proyek.p("hasil", j["id"])
        f.mkdir(parents=True, exist_ok=True)
        (f / "log").mkdir(exist_ok=True)
        return f

    def _berikut(self):
        if self.sibuk() or not self.proyek:
            return
        j = self.job if self.job and self.job["status"] == "berjalan" else \
            next((x for x in self.proyek.job if x["status"] == "menunggu"), None)
        if not j:
            self.job = None
            return
        self.job = j
        if j["status"] != "berjalan":
            j["status"] = "berjalan"
            j["mulai"] = j["mulai"] or datetime.now().isoformat(timespec="seconds")
            self.log.emit(f"Mulai job {j['id']} ({M.MESIN[j['mesin']]}, {len(j['ligan'])} ligan)")
        if j["id"] in self.minta_jeda:
            self.minta_jeda.discard(j["id"])
            j["status"] = "dijeda"
            self.job = None
            self.log.emit(f"Job {j['id']} dijeda.")
            self._ubah(j)
            self._berikut()
            return
        if j["mesin"] in ("adgpu", "ad4") and not self._grid_ok(j):
            return  # autogrid sedang berjalan
        lig = next((l for l in j["ligan"] if l["status"] == "menunggu"), None)
        if lig is None:
            self._tutup_job(j)
            return
        self._mulai_ligan(j, lig)

    def _tutup_job(self, j):
        ok = [l for l in j["ligan"] if l["status"] == "selesai"]
        j["status"] = "selesai" if ok else "gagal"
        j["selesai"] = datetime.now().isoformat(timespec="seconds")
        self.job = None
        self.log.emit(f"Job {j['id']} {j['status']}: {len(ok)}/{len(j['ligan'])} ligan berhasil")
        self._ubah(j)
        self.jobSelesai.emit(j["id"])
        self._berikut()

    def _reseptor(self, j):
        """Reseptor terurai untuk analisis interaksi (cache per berkas)."""
        from . import analisis
        f = self.proyek.p(j["reseptor"])
        kunci = (str(f), f.stat().st_mtime if f.exists() else 0)
        if getattr(self, "_rec_kunci", None) != kunci:
            self._rec_kunci = kunci
            self._rec = analisis.baca_reseptor(f.read_text()) if f.exists() else None
        return self._rec

    # ------------------------------------------------------------- grid
    def _grid_ok(self, j):
        pr = self.proyek
        rec = pr.p(j["reseptor"]).read_text()
        tipe = set()
        for l in j["ligan"]:
            f = pr.p(l["pdbqt"])
            if f.exists():
                tipe |= M.tipe_atom(f.read_text())
        if j.get("flex") and pr.p(j["flex"]).exists():     # peta untuk atom residu fleksibel juga
            tipe |= M.tipe_atom(pr.p(j["flex"]).read_text())
        kotak = M.Kotak(**j["kotak"])
        # komentar hash reseptor: peta lama tidak dipakai ulang bila reseptor berubah (mis. kaku <-> fleksibel)
        gpf = M.tulis_gpf(rec, tipe, kotak) + f"# reseptor {M.hash_teks(rec)}\n"
        g = pr.p("grid")
        g.mkdir(exist_ok=True)
        if M.grid_siap(g, gpf):
            return True
        for f in list(g.glob("reseptor.*.map")) + list(g.glob("reseptor.maps.*")):
            f.unlink(missing_ok=True)
        (g / "reseptor.pdbqt").write_text(rec)
        (g / "reseptor.gpf").write_text(gpf)
        self.log.emit(f"Membuat grid map (AutoGrid4), {' × '.join(map(str, kotak.npts()))} titik, "
                      f"tipe ligan {' '.join(M.tipe_peta(tipe))}")
        self.tahap, self.lig = "grid", None
        cmd, cwd = M.perintah_autogrid(g)
        self._jalankan(cmd, cwd)
        return False

    # ----------------------------------------------------------- ligan
    def _mulai_ligan(self, j, l):
        pr = self.proyek
        p = M.Parameter(**{k: v for k, v in j["parameter"].items() if k in M.Parameter.__dataclass_fields__})
        p.mesin = j["mesin"]
        folder = self._folder_job(j)
        lig = pr.p(l["pdbqt"])
        if not lig.exists():
            l["status"], l["pesan"] = "gagal", "berkas PDBQT ligan tidak ditemukan"
            self._ubah(j)
            QTimer.singleShot(0, self._berikut)
            return

        from . import sanitasi_struktur
        ok_lig, teks_bersih, cat_lig = sanitasi_struktur.validasi_sanitasi_pdbqt(lig, jenis="ligan")
        if not ok_lig:
            l["status"], l["pesan"] = "gagal", f"berkas PDBQT cacat: {'; '.join(cat_lig)}"
            self._ubah(j)
            QTimer.singleShot(0, self._berikut)
            return
        if cat_lig and teks_bersih:
            try:
                lig.write_text(teks_bersih, encoding="utf-8")
            except Exception:
                pass
        kovalen = bool(j.get("kovalen"))
        if kovalen:
            flex = pr.p(l["flex"]) if l.get("flex") else None
            if j["mesin"] != "adgpu":
                l["status"] = "dilewati"
                l["pesan"] = "docking kovalen di VirmoDock hanya didukung AutoDock-GPU"
                self._ubah(j)
                QTimer.singleShot(0, self._berikut)
                return
        else:
            flex = pr.p(j["flex"]) if j.get("flex") else None
        if kovalen and (flex is None or not flex.exists()):
            l["status"], l["pesan"] = "gagal", "berkas aduk kovalen tidak ditemukan; jalankan ulang docking kovalen"
            self._ubah(j)
            QTimer.singleShot(0, self._berikut)
            return
        if flex is not None and not flex.exists():
            l["status"], l["pesan"] = "gagal", "berkas residu fleksibel tidak ditemukan; atur ulang Residu fleksibel"
            self._ubah(j)
            QTimer.singleShot(0, self._berikut)
            return
        if flex is not None and j["mesin"] == "ad4":
            l["status"] = "dilewati"
            l["pesan"] = "AutoDock4 di VirmoDock belum mendukung residu fleksibel; pakai AutoDock-GPU atau Vina"
            self._ubah(j)
            QTimer.singleShot(0, self._berikut)
            return
        if j["mesin"] == "adgpu":
            teks = lig.read_text()
            from .prep_ligan import MAKS_ATOM_GPU, MAKS_TORSI_GPU
            import re
            tors = int((re.search(r"TORSDOF\s+(\d+)", teks) or [0, 0])[1]) if "TORSDOF" in teks else 0
            n_atom = sum(1 for b in teks.splitlines() if b.startswith(("ATOM", "HETATM")))
            if kovalen:          # ligan tidak dikirim terpisah: aduk seluruhnya ada di berkas flexres
                tors = n_atom = 0
            if flex is not None:     # batas AD-GPU berlaku untuk ligan + residu fleksibel
                tf = flex.read_text()
                tors += sum(1 for b in tf.splitlines() if b.startswith("BRANCH"))
                n_atom += sum(1 for b in tf.splitlines() if b.startswith(("ATOM", "HETATM")))
            if tors > MAKS_TORSI_GPU or n_atom > MAKS_ATOM_GPU:
                l["status"] = "dilewati"
                l["pesan"] = (f"melebihi batas AutoDock-GPU ({tors} torsi, {n_atom} atom"
                              + (" aduk kovalen); kurangi ikatan rotasi ligan" if kovalen else
                                 (" termasuk residu fleksibel" if flex is not None else "") + "); jalankan dengan Vina"))
                self._ubah(j)
                QTimer.singleShot(0, self._berikut)
                return
            basis = folder / l["id"]
            cmd = M.perintah_adgpu(pr.p("grid", "reseptor.maps.fld"), None if kovalen else lig, basis, p, flex=flex)
            l["keluaran"] = pr.rel(folder / f"{l['id']}.dlg")
            cwd = str(folder)
        elif j["mesin"] == "vina":
            out = folder / f"{l['id']}_out.pdbqt"
            cmd = M.perintah_vina(pr.p(j["reseptor"]), lig, out, M.Kotak(**j["kotak"]), p, flex=flex)
            l["keluaran"] = pr.rel(out)
            cwd = str(folder)
        else:
            shutil.copy2(lig, folder / f"{l['id']}.pdbqt")
            dpf = folder / f"{l['id']}.dpf"
            dpf.write_text(M.tulis_dpf(lig.read_text(), f"{l['id']}.pdbqt", "../../grid", p))
            cmd = M.perintah_ad4(dpf.name, f"{l['id']}.dlg")
            l["keluaran"] = pr.rel(folder / f"{l['id']}.dlg")
            cwd = str(folder)
            (folder / f"{l['id']}.dlg").unlink(missing_ok=True)
        l["status"], l["progres"], l["pesan"] = "berjalan", 0, ""
        self.lig, self.tahap = l, "dock"
        self.pembaca = M.PembacaProgres(j["mesin"], p)
        self.mulai_lig = time.time()
        self._ubah(j)
        self._jalankan(cmd, cwd)
        if j["mesin"] == "ad4":
            self._dlg_pos = 0
            self.timer_dlg.start()

    def _jalankan(self, cmd, cwd):
        if not cmd[0]:
            self.pesan.emit("Program mesin tidak ditemukan di folder bin. Pasang ulang VirmoDock.")
            self.job["status"] = "gagal"
            self._ubah(self.job)
            return
        self.keluaran = ""
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.setWorkingDirectory(cwd)
        self.proc.readyReadStandardOutput.connect(self._baca)
        self.proc.finished.connect(self._proses_selesai)
        self.proc.errorOccurred.connect(self._galat_proses)
        self.proc.start(cmd[0], [str(a) for a in cmd[1:]])

    def _galat_proses(self, e):
        if e == QProcess.FailedToStart:
            self.keluaran += f"\nProgram gagal dijalankan: {self.proc.program()}"

    def _baca(self):
        t = bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        self.keluaran += t
        if self.tahap == "dock" and self.lig is not None and self.pembaca:
            naik = None
            for b in t.replace("\r", "\n").split("\n"):
                v = self.pembaca.baca(b)
                if v is not None:
                    naik = v
            if naik is not None and naik != self.lig["progres"]:
                self.lig["progres"] = naik
                self.jobBerubah.emit(self.job["id"])

    def _intip_dlg(self):
        """AutoDock4 menulis progres ke .dlg, bukan stdout."""
        if not self.lig or not self.lig.get("keluaran"):
            return
        f = self.proyek.p(self.lig["keluaran"])
        if not f.exists():
            return
        with open(f, errors="replace") as h:
            h.seek(self._dlg_pos)
            t = h.read()
            self._dlg_pos = h.tell()
        for b in t.splitlines():
            v = self.pembaca.baca(b)
            if v is not None and v != self.lig["progres"]:
                self.lig["progres"] = v
                self.jobBerubah.emit(self.job["id"])

    def _proses_selesai(self, kode, status):
        self.timer_dlg.stop()
        j, l, tahap = self.job, self.lig, self.tahap
        self.proc.deleteLater()
        self.proc = None
        if j is None:
            return
        folder = self._folder_job(j)
        if tahap == "grid":
            glg = self.proyek.p("grid", "reseptor.glg")
            if not self.proyek.p("grid", "reseptor.maps.fld").exists():
                ekor = glg.read_text(errors="replace") if glg.exists() else self.keluaran
                j["status"] = "gagal"
                j["catatan"].append("AutoGrid4 gagal: " + M.ringkas_galat(ekor))
                self.pesan.emit(f"AutoGrid4 gagal membuat grid map untuk job {j['id']}:\n{M.ringkas_galat(ekor)}\n"
                                "Periksa grid box (ukuran/pusat) dan reseptor PDBQT.")
                self._ubah(j)
                self.job = None
                self.jobSelesai.emit(j["id"])
                self._berikut()
                return
            self.log.emit("Grid map selesai.")
            self._berikut()
            return
        # ---- tahap dock
        (folder / "log" / f"{l['id']}.log").write_text(self.keluaran, encoding="utf-8")
        l["detik"] = round(time.time() - self.mulai_lig, 1)
        if j["status"] == "dibatalkan":
            l["status"], l["pesan"] = "dibatalkan", "dibatalkan pengguna"
            for x in j["ligan"]:
                if x["status"] == "menunggu":
                    x["status"] = "dibatalkan"
            j["selesai"] = datetime.now().isoformat(timespec="seconds")
            self.job = None
            self.log.emit(f"Job {j['id']} dibatalkan.")
            self._ubah(j)
            self.jobSelesai.emit(j["id"])
            self._berikut()
            return
        out = self.proyek.p(l["keluaran"]) if l.get("keluaran") else None
        pose = []
        if out and out.exists():
            try:
                pose = M.baca_hasil(j["mesin"], out)
            except Exception as e:  # berkas rusak
                l["pesan"] = f"hasil tidak terbaca: {e}"
        if pose:
            l["status"], l["progres"] = "selesai", 100
            l["energi"] = pose[0].energi
            l["ki"] = pose[0].ki
            l["rmsd_ref"] = pose[0].rmsd_ref if pose[0].rmsd_ref >= 0 else None
            l["n_pose"] = len(pose)
            l["pose"] = [p.ke_dict() for p in pose[:SIMPAN_POSE]]
            try:  # analisis ringan: LE, interaksi pose terbaik, RMSD ke ligan kristal (bila ada)
                from . import analisis
                analisis.ringkas_ligan(self.proyek, l, pose, self._reseptor(j))
            except Exception as e:
                self.log.emit(f"Analisis {l['nama']} dilewati: {e}")
            if j.get("kovalen"):     # skor kovalen bukan ΔG ikatan: Ki dan LE tidak bermakna
                l["ki"], l["le"] = "", None
            self._qc_antre(j, l, pose)
            self.log.emit(f"{l['nama']}: {pose[0].energi:.2f} kcal/mol ({l['detik']:.1f} s)")
            self.liganSelesai.emit(j["id"], l["id"])
        elif j["mesin"] == "adgpu" and j.get("kovalen") and (M.RE_GALAT_OPENCL.search(self.keluaran)
                                                             or kode in M.KODE_GALAT_DLL):
            l["status"] = "gagal"
            l["pesan"] = "AutoDock-GPU tidak bisa memakai GPU (OpenCL); docking kovalen butuh AutoDock-GPU"
            self.log.emit(f"{l['nama']} gagal: {l['pesan']}")
        elif j["mesin"] == "adgpu" and (M.RE_GALAT_OPENCL.search(self.keluaran) or kode in M.KODE_GALAT_DLL):
            # GPU/OpenCL tidak bisa dipakai: lanjutkan seluruh job dengan Vina (CPU)
            j["mesin"] = "vina"
            j["perangkat"] = "cpu"
            j["catatan"].append("AutoDock-GPU gagal (OpenCL); dialihkan otomatis ke AutoDock Vina (CPU).")
            l["status"], l["progres"] = "menunggu", 0
            self.pesan.emit("AutoDock-GPU tidak bisa memakai GPU (galat OpenCL):\n"
                            f"{M.ringkas_galat(self.keluaran)}\n"
                            "Job dilanjutkan otomatis dengan AutoDock Vina di CPU. Perbarui driver GPU "
                            "(Alat › Cek sistem dan GPU) untuk memakai GPU lagi.")
        else:
            l["status"] = "gagal"
            l["pesan"] = l.get("pesan") or M.ringkas_galat(self.keluaran, 300) or f"kode keluar {kode}"
            self.log.emit(f"{l['nama']} gagal: {l['pesan']}")
        self.lig = None
        self._ubah(j)
        self._berikut()
