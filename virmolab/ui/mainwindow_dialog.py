"""Pembuka dialog analisis untuk jendela utama.

Dipisahkan dari `mainwindow.py` (yang sudah lebih dari lima ribu baris) agar penambahan alat baru tidak lagi
menyenggol kode viewer, antrean, atau ekspor. Semua metode di sini memakai `self` milik JendelaUtama: kelas
`PembukaDialog` dipasang sebagai mixin, bukan kelas berdiri sendiri.

Pola tiap pembuka: periksa syarat (proyek, reseptor, pose aktif) → beri pesan jelas bila belum terpenuhi →
buat dialog, sambungkan sinyalnya, lalu tampilkan dengan WA_DeleteOnClose supaya tidak menumpuk di memori.
"""
from PySide6.QtCore import Qt, QTimer

from ..core import molekul
from . import kit


class PembukaDialog:
    """Kumpulan metode `buka_*` JendelaUtama (mixin; lihat mainwindow.JendelaUtama)."""

    # ------------------------------------------------------------ impor hasil eksternal
    def buka_impor_docking(self, berkas=()):
        from .dialog_impor_docking import DialogImporDocking
        d = DialogImporDocking(self, berkas)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.selesai.connect(self._impor_docking_selesai)
        d.show()

    def _impor_docking_selesai(self, job):
        """Job impor masuk proyek: segarkan tabel & antrean, buka pose terbaik, jalankan PoseBusters di latar."""
        pr = self.proyek
        if not pr:
            return
        self.antrean.muat(pr.job)
        self._muat_hasil()
        self.minta_simpan()
        im = job.get("impor") or {}
        self.log.tulis(f"Impor {im.get('program', '')}: {len(job['ligan'])} ligan masuk sebagai job {job['id']} "
                       f"(reseptor: {im.get('reseptor') or '-'}).")
        for c in job.get("catatan") or []:
            self.pesan.tulis("Impor docking: " + c)
        for l in job["ligan"]:
            if l.get("pesan"):
                self.log.tulis(f"  {l['nama']}: {l['pesan']}")
        terbaik = min(job["ligan"], key=lambda l: l["energi"])
        self.ke_langkah(4)
        # pindah ke ruang Analisis mengubah ukuran viewport: fokus kamera setelah tata letak tenang
        QTimer.singleShot(350, lambda: self.buka_pose(job["id"], terbaik["id"], 1))
        QTimer.singleShot(1200, lambda: self.aktif in self.objek and (self.viewer.js("segarkanKanvas"),
                                                                      self.viewer.js("fokus", {"id": self.aktif})))
        self.analisis_ulang()

    def buka_impor_md(self, berkas=()):
        from .dialog_impor_md import DialogImporMD
        d = DialogImporMD(self, berkas)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.selesai.connect(self.buka_md_hasil)
        d.show()

    def buka_md_hasil(self, rid):
        """Jendela analisis trajektori (mode lihat) untuk satu hasil MD proyek, mis. trajektori impor."""
        from .dialog_md import DialogMD
        d = DialogMD(self, lihat=rid)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()
        d.raise_()

    def buka_grafik_berkas(self, berkas=()):
        from .dialog_grafik_berkas import DialogGrafikBerkas
        d = DialogGrafikBerkas(self, berkas)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_asisten(self):
        from .dialog_asisten import DialogAsisten
        d = DialogAsisten(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_penelitian(self):
        from .dialog_penelitian import DialogPenelitian
        d = DialogPenelitian(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_md(self):
        from ..core import md as mdmod
        if not mdmod.tersedia():
            self._galat("Modul MD (OpenMM/OpenFF) tidak terpasang. Pasang ulang VirmoLab.")
            return
        if not self.proyek or not any(l["status"] == "selesai" for j in self.proyek.job for l in j["ligan"]):
            ada = [r for r in (self.proyek.md if self.proyek else []) if r.get("status") == "selesai"]
            if ada:     # proyek tanpa docking tetapi berisi trajektori impor: buka jendela analisis saja
                self.buka_md_hasil(ada[-1]["id"])
                return
            self._galat("Belum ada hasil docking. Jalankan docking dulu (langkah 4), lalu buka MD & MM/GBSA. "
                        "Trajektori dari program lain bisa dibuka lewat Berkas › Impor hasil eksternal › "
                        "Trajektori MD.")
            return
        d = getattr(self, "_dlg_md", None)
        if d is None or (d.proyek_awal is not self.proyek and not d.proses_berjalan()):
            from .dialog_md import DialogMD
            d = self._dlg_md = DialogMD(self)
            d.selesai.connect(self.terapkan_md)
        else:
            d.muat()
        d.show()
        d.raise_()
        d.activateWindow()

    def terapkan_md(self, h, run):
        """Tulis ΔG MM/GBSA ke ligan job (kolom Hasil, Statistik, ekspor, laporan)."""
        pr = self.proyek
        if not pr:
            return
        o = h.get("opsi") or {}
        for x in h.get("ligan", []):
            if not x.get("selesai"):
                continue
            j = self.pelaksana.cari(x.get("job"))
            l = next((y for y in (j or {}).get("ligan", []) if y["id"] == x.get("lid")), None)
            if l is None:
                continue
            md_ = x.get("mmgbsa")
            mn = x.get("mmgbsa_min") or {}
            if md_:
                metode = (f"MM/GBSA OBC2, MD {'air eksplisit' if o.get('pelarut') == 'eksplisit' else 'implisit'} "
                          f"{o.get('ns')} ns, {md_.get('n')} frame")
                l["mmgbsa"] = {"dG": md_["dG"], "sd": md_.get("sd"), "sem": md_.get("sem"), "min": mn.get("dG"),
                               "vdw": md_.get("vdw"), "elek": md_.get("elek"), "gb": md_.get("gb"), "sa": md_.get("sa"),
                               "metode": metode, "md": run.get("id")}
                tr = x.get("trajektori") or {}
                if tr.get("rmsd_ligan"):
                    l["mmgbsa"]["rmsd_ligan"] = sum(tr["rmsd_ligan"]) / len(tr["rmsd_ligan"])
            elif mn:
                l["mmgbsa"] = {"dG": mn["dG"], "sd": None, "min": mn["dG"], "vdw": mn.get("vdw"), "elek": mn.get("elek"),
                               "gb": mn.get("gb"), "sa": mn.get("sa"), "metode": "MM/GBSA OBC2 (minimisasi)",
                               "md": run.get("id")}
        pr.md = [r for r in pr.md if r.get("id") != run.get("id")] + [dict(run, status="selesai")]
        self._muat_hasil()
        self.minta_simpan()
        n = sum(1 for x in h.get("ligan", []) if x.get("selesai"))
        self.pesan.tulis(f"MM/GBSA: {n} ligan diperbarui di tabel Hasil (kolom MM/GBSA). Nilai untuk peringkat relatif; "
                         "entropi konformasi tidak dihitung.")
        if any((x.get("logam") or 0) > 0 for x in h.get("ligan", [])):
            self.pesan.tulis("MM/GBSA: reseptor memuat ion logam (model nonbonded 12-6) - energi interaksi logam-ligan "
                             "bersifat pendekatan; bandingkan hanya antar-ligan dengan mode ikatan logam yang sama.")

    def buka_admet(self):
        if not self._sumber_sifat():
            self._galat("Belum ada ligan. Impor atau siapkan ligan dulu.")
            return
        from .dialog_admet import DialogAdmet
        d = DialogAdmet(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_pustaka(self):
        from .dialog_pustaka import DialogPustaka
        d = DialogPustaka(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_chembl(self, tab=0):
        from .dialog_chembl import DialogChembl
        d = DialogChembl(self, tab)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_kemiripan(self):
        from .dialog_kemiripan import DialogKemiripan
        if len(self._sumber_sifat()) < 2:
            self._galat("Butuh minimal 2 ligan (impor atau siapkan ligan dulu).")
            return
        d = DialogKemiripan(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_konsensus(self):
        if not self.proyek or not self.proyek.job:
            self._galat("Belum ada hasil docking.")
            return
        from .dialog_konsensus import DialogKonsensus
        DialogKonsensus(self).exec()

    def buka_mpo(self):
        if not self.proyek or not self.proyek.ligan:
            self._galat("Belum ada ligan di dalam proyek.")
            return
        from .dialog_mpo import DialogMPO
        d = DialogMPO(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_labplanner(self):
        if not self.proyek or not self.proyek.ligan:
            self._galat("Belum ada ligan di dalam proyek.")
            return
        from .dialog_labplanner import DialogLabPlanner
        d = DialogLabPlanner(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def _pilih_ligan_dari_nama(self, nama):
        if not self.proyek:
            return
        for j in getattr(self.proyek, "job", []):
            for l in j.get("ligan", []):
                if l.get("nama") == nama or l.get("id") == nama:
                    self.buka_pose(j["id"], l["id"], 1)
                    return

    def buka_penapisan(self):
        if not self.proyek or not self.proyek.ligan:
            self._galat("Belum ada ligan di dalam proyek.")
            return
        from .dialog_penapisan import DialogPenapisan
        d = DialogPenapisan(self)
        d.liganDipilih.connect(self._pilih_ligan_dari_nama)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_mmp(self):
        if not self.proyek or not self.proyek.ligan:
            self._galat("Belum ada ligan di dalam proyek.")
            return
        from .dialog_mmp import DialogMMP
        d = DialogMMP(self)
        d.liganDipilih.connect(self._pilih_ligan_dari_nama)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_alat_wsl(self, paket=None):
        """Dialog pemasang alat WSL; `paket` ('gpu_rbfe' / 'cofolding') bila dibuka dari fitur yang membutuhkannya."""
        from .dialog_alat_wsl import DialogAlatWsl
        d = DialogAlatWsl(self, paket_awal=paket if isinstance(paket, str) else None)
        d.alatBerubah.connect(self._alat_wsl_berubah)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()
        return d

    def _alat_wsl_berubah(self):
        """Sesudah pemasangan: tombol mesin Uni-Dock dan deteksi perangkat mengikuti status WSL terbaru."""
        from ..core import unidock
        ada = unidock.tersedia()
        if getattr(self, "env", None) is not None:
            self.env.unidock = ada
        self.param.atur_unidock(ada)
        self._gnina_tidak_ada = False              # kolom GNINA dicoba lagi pada pemilihan pose berikutnya
        if getattr(self, "aktif", None) in getattr(self, "objek", {}):
            self.pilih_objek(self.aktif)           # panel co-folding membaca status Boltz yang baru
        self.pesan.tulis("Alat lanjutan WSL diperbarui: Uni-Dock " + ("siap." if ada else "belum terpasang."))

    def buka_glikosida(self):
        if not self.proyek or not self.proyek.ligan:
            self._galat("Belum ada ligan di dalam proyek.")
            return
        from .dialog_glikosida import DialogGlikosida
        d = DialogGlikosida(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()
        return d

    def buka_selektivitas(self):
        if not self.proyek:
            self._galat("Belum ada proyek yang terbuka.")
            return
        from .dialog_selektivitas import DialogSelektivitas
        d = DialogSelektivitas(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_interpretasi(self):
        from .dialog_asisten import DialogAsisten
        d = DialogAsisten(self, tab_awal=1)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_ppi(self):
        from .dialog_ppi import DialogPPI
        d = DialogPPI(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_kantong(self):
        if not self.proyek or not self.proyek.reseptor:
            self._galat("Belum ada reseptor (makromolekul) di dalam proyek.")
            return
        from .dialog_kantong import DialogKantong
        d = DialogKantong(self)
        d.kotakDipilih.connect(lambda k: self._atur_kotak(k["pusat"], k["ukuran"], sumber="kantong terdeteksi"))
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def impor_smiles(self, nama, smiles, sebutan="Ligan"):
        """Tambahkan molekul dari SMILES sebagai objek ligan di viewer (belum disiapkan untuk docking)."""
        try:
            objs = molekul.dari_smiles(smiles, nama)
        except Exception as e:
            self._galat(f"Gagal membuat 3D untuk '{nama}': {e}")
            return False
        for o in objs:
            o.tampil = False
        self.tambah_objek(objs, fokus=False)
        self._info(f"{sebutan} '{nama}' ditambahkan. Lanjutkan di Siapkan ligan untuk didocking.")
        return True

    def buka_fbdd(self):
        from .dialog_fbdd import DialogFBDD
        d = DialogFBDD(self)
        d.liganDiimpor.connect(lambda n, s: self.impor_smiles(n, s, "Turunan FBDD"))
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_skrip_publikasi(self):
        from .dialog_skrip_publikasi import DialogSkripPublikasi
        d = DialogSkripPublikasi(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_diagnostik(self):
        from .dialog_diagnostik import DialogDiagnostik
        d = DialogDiagnostik(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_terowongan(self):
        from .dialog_terowongan import DialogTerowongan
        if not kit.reseptor_proyek(self)[0]:
            self._galat("Belum ada reseptor (makromolekul) yang bisa dipindai.")
            return
        d = DialogTerowongan(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_kinetika(self):
        from .dialog_kinetika import DialogKinetika
        d = DialogKinetika(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_protac(self):
        from .dialog_protac import DialogPROTAC
        d = DialogPROTAC(self)
        d.protacDiimpor.connect(lambda n, s: self.impor_smiles(n, s, "PROTAC"))
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_metabolisme(self):
        from .dialog_metabolisme import DialogMetabolisme
        d = DialogMetabolisme(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_rescore_ml(self):
        if not kit.pose_aktif(self):
            self._galat("Buka satu pose hasil docking dulu (tab Hasil › klik pose), lalu ulangi.")
            return
        from .dialog_rescore_ml import DialogRescoreML
        d = DialogRescoreML(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_pengaturan(self):
        from .dialog_pengaturan import DialogPengaturan
        d = DialogPengaturan(self)
        d.exec()

    def buka_pembaruan(self, hasil=None):
        from .dialog_pembaruan import DialogPembaruan
        d = DialogPembaruan(self, hasil)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def _tawarkan_pembaruan(self, h):
        """Buka dialog pembaruan sendiri, sekali untuk tiap nomor versi.

        Sebelumnya rilis baru hanya diumumkan lewat satu baris di bilah status yang hilang sesudah 15
        detik dan satu baris di panel Pesan yang biasanya tertutup; praktis tidak pernah terlihat.
        Nomor versi yang sudah ditawarkan dicatat sebelum dialognya dibuka, sehingga rilis yang sama
        tidak ditawarkan lagi pada pembukaan aplikasi berikutnya — rilis berikutnya tetap muncul."""
        versi = str(h.get("versi") or "")
        if not versi or str(self.st.value("pembaruan_ditawarkan", "")) == versi:
            return
        self.st.setValue("pembaruan_ditawarkan", versi)
        self.buka_pembaruan(h)

    def _cek_pembaruan_otomatis(self):
        """Sekali sehari di latar; menawarkan dialog pembaruan bila ada versi baru yang belum ditawarkan.
        Gagal jaringan diam saja (dicatat di log), karena aplikasi tetap bekerja tanpa internet."""
        from ..core import pembaruan
        from . import kerja
        if not pembaruan.perlu_diperiksa(self.st):
            return

        def selesai(h):
            st = h.get("status")
            if st in ("baru", "terkini", "belum_ada_rilis"):
                pembaruan.catat_diperiksa(self.st)
            if st == "baru":
                self.pesan.tulis(f"VirmoLab {h['versi']} sudah terbit (terpasang {h['versi_sekarang']}). "
                                 "Bantuan › Periksa pembaruan… untuk catatan rilis dan tautan unduhan.")
                self.statusBar().showMessage(f"VirmoLab {h['versi']} tersedia - Bantuan › Periksa pembaruan…", 15000)
                self._tawarkan_pembaruan(h)
            elif st == "galat":
                self.log.tulis("Pemeriksaan pembaruan dilewati: " + h.get("pesan", ""))

        kerja.jalankan(lambda lapor: pembaruan.periksa(), selesai=selesai,
                       galat=lambda g: self.log.tulis("Pemeriksaan pembaruan dilewati: " + g.split("\n")[0]))

    def buka_tanaman(self):
        from .dialog_tanaman import DialogTanaman
        d = DialogTanaman(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_validasi_protokol(self):
        from .dialog_validasi_protokol import DialogValidasiProtokol
        d = DialogValidasiProtokol(self, proyek=self.proyek)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_sunting3d(self):
        from .dialog_sunting3d import DialogSunting3D
        d = DialogSunting3D(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()
        return d

    def buka_pembelajaran_aktif(self):
        from .dialog_pembelajaran_aktif import DialogPembelajaranAktif
        if not self.proyek:
            self._pastikan_proyek()
        d = DialogPembelajaranAktif(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()
        return d

    def buka_rbfe(self):
        from .dialog_rbfe import DialogRbfe
        d = DialogRbfe(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()
        return d

    def buka_generatif(self):
        from .dialog_generatif import DialogGeneratif
        d = DialogGeneratif(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()
        return d

    def buka_xtb(self):
        from .dialog_xtb import DialogXtb
        d = DialogXtb(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()
        return d

    def buka_peptida(self):
        from .dialog_peptida import DialogPeptida
        d = DialogPeptida(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()
        return d

    def buka_qsar(self):
        from .dialog_qsar import DialogQSAR
        d = DialogQSAR(self, proyek=self.proyek)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()
        return d

    def buka_target_balik(self):
        from .dialog_target_balik import DialogTargetBalik
        d = DialogTargetBalik(self, proyek=self.proyek)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()

    def buka_farmakologi(self, tab=0):
        """Alur farmakologi jaringan. `tab` membuka langsung tahap tertentu (0 = Senyawa … 6 = Laporan)."""
        from .dialog_farmakologi import DialogFarmakologi
        d = getattr(self, "_d_farmakologi", None)
        if d is not None and d.isVisible():
            # Satu alur per jendela: kalau sudah terbuka, angkat yang ada supaya keadaannya tidak bercabang.
            d.tabs.setCurrentIndex(max(0, min(int(tab), d.tabs.count() - 1)))
            d.raise_()
            d.activateWindow()
            return
        d = DialogFarmakologi(self, proyek=self.proyek)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.tabs.setCurrentIndex(max(0, min(int(tab), d.tabs.count() - 1)))
        d.keadaanBerubah.connect(lambda _k: self.segarkan_langkah())
        d.destroyed.connect(lambda *_: setattr(self, "_d_farmakologi", None))
        self._d_farmakologi = d
        d.show()

    def buka_farmakofor(self):
        from .dialog_farmakofor import DialogFarmakofor
        d = DialogFarmakofor(self)
        d.setAttribute(Qt.WA_DeleteOnClose)
        d.show()


