"""Komposer figur multi-panel untuk jendela utama.

Dipisahkan dari `mainwindow.py` agar penyusunan figur jurnal (panel A/B/C, tangkapan viewport, diagram 2D,
grafik, dan ekspor PDF/TIFF/SVG) bisa dibaca dan diubah tanpa menyentuh kode viewer maupun antrean docking.
Semua metode memakai `self` milik JendelaUtama: `KomposerFigur` dipasang sebagai mixin, bukan kelas mandiri.
"""
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, Qt, QTimer
from PySide6.QtGui import QImage
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ..core import analisis, diagram2d, kemiripan, kontribusi
from ..core import sifat as sifat_mod
from ..core.proyek import nama_aman
from . import kerja, theme
from .dialog_komposer import DialogKomposer


class KomposerFigur:
    """Metode komposer figur JendelaUtama (mixin; lihat mainwindow.JendelaUtama)."""

    def buka_komposer(self):
        if not self.komposer:
            from .dialog_komposer import DialogKomposer
            self.komposer = DialogKomposer(self)
            self.komposer.minta.connect(self._komposer_tambah)
            self.komposer.ekspor.connect(self._ekspor_komposer)
            self.komposer.berubah.connect(self._komposer_berubah)
            self.komposer.muat(self._komposer_dari_proyek())
        self.komposer.show()
        self.komposer.raise_()
        self.komposer.activateWindow()

    def _komposer_dari_proyek(self):
        """proyek.komposer -> data dialog (panel raster dibaca dari komposer/*.png)."""
        import base64
        pr = self.proyek
        d = (pr.komposer if pr else {}) or {}
        panel = []
        for p in d.get("panel") or []:
            p = dict(p)
            if p.get("jenis") == "png" and p.get("berkas"):
                f = pr.p("komposer", p["berkas"])
                if not f.exists():
                    continue
                p["isi"] = base64.b64encode(f.read_bytes()).decode("ascii")
            panel.append(p)
        return {"panel": panel, "opsi": d.get("opsi") or {}}

    def _komposer_berubah(self):
        import base64
        import uuid
        pr = self.proyek
        if not pr or not self.komposer:
            return
        pr.p("komposer").mkdir(exist_ok=True)
        simpan = []
        for p in self.komposer.panel:
            if p["jenis"] == "png":
                if not p.get("berkas"):
                    p["berkas"] = f"{uuid.uuid4().hex[:10]}.png"
                f = pr.p("komposer", p["berkas"])
                if not f.exists():
                    f.write_bytes(base64.b64decode(p["isi"]))
                simpan.append({k: v for k, v in p.items() if k != "isi"})
            else:
                simpan.append(dict(p))
        pakai = {p.get("berkas") for p in simpan}
        for f in pr.p("komposer").glob("*.png"):     # berkas panel yang sudah dihapus
            if f.name not in pakai:
                f.unlink(missing_ok=True)
        pr.komposer = {"panel": simpan, "opsi": dict(self.komposer.opsi)}
        self.minta_simpan()

    def _komposer_tambah(self, sumber):
        if not self.komposer:
            self.buka_komposer()
        ke = self.komposer.tambah
        if sumber == "uji":
            s, (w, h) = self.uji.svg(gelap=False)
            nama = self.uji.e_judul.text().strip() or self.uji.c_data.currentText().split(" (")[0]
        elif sumber == "statistik":
            s, (w, h) = self.statistik.svg(gelap=False) if self.statistik.data else ("", (0, 0))
            nama = self.statistik.c_jenis.currentText()
        elif sumber == "diagram":
            s, (w, h) = self._svg_diagram(gelap=False), (960, 720)
            nama = "Diagram interaksi 2D"
        elif sumber == "sifat":
            s, (w, h) = (self.sifat.svg(gelap=False) if self.sifat.data else ""), (760, 600)
            nama = "BOILED-Egg"
        elif sumber == "3d":
            if self.tab_tengah.currentWidget() is not self.w_view:
                self.tab_tengah.setCurrentWidget(self.w_view)
            # 3600 px: cukup untuk panel lebar penuh 174 mm @ 600 dpi tanpa diperbesar (di bawah batas kanvas 4096)
            lebar = 3600
            tinggi = round(lebar * self.viewer.height() / max(1, self.viewer.width()))

            def taruh(url):
                if not url or "," not in url:
                    self._galat("Render gambar 3D gagal (WebGL).")
                    return
                import base64
                from ..core.docx_ringan import ukuran_png
                isi = url.split(",", 1)[1]
                w_, h_ = ukuran_png(base64.b64decode(isi[:64]))     # ukuran nyata (layar HiDPI bisa lain)
                ke({"nama": "Struktur 3D", "jenis": "png", "isi": isi, "w": w_, "h": h_})
                self.statusBar().showMessage("Gambar 3D ditambahkan ke Komposer figur.", 4000)
            QTimer.singleShot(250, lambda: self.viewer.js("gambar", lebar, tinggi, False, "#ffffff", cb=taruh))
            return
        else:
            self._komposer_berkas()
            return
        if not s:
            self._galat("Grafik/diagram sumber masih kosong.")
            return
        ke({"nama": nama, "jenis": "svg", "isi": s, "w": w, "h": h})
        self.statusBar().showMessage(f"“{nama}” ditambahkan ke Komposer figur.", 4000)

    def _komposer_berkas(self):
        import base64
        from PySide6.QtCore import QBuffer, QIODevice
        from PySide6.QtGui import QImage
        from PySide6.QtSvg import QSvgRenderer
        f, _ = QFileDialog.getOpenFileName(self.komposer or self, "Tambah gambar ke komposer", "",
                                           "Gambar (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.svg)")
        if not f:
            return
        if f.lower().endswith(".svg"):
            teks = Path(f).read_text(encoding="utf-8", errors="replace")
            r = QSvgRenderer(QByteArray(teks.encode("utf-8")))
            if not r.isValid():
                self._galat("SVG tidak bisa dibaca.")
                return
            sz = r.defaultSize()
            if "viewBox=" not in teks[:3000]:     # panel butuh viewBox untuk diskalakan
                teks = teks.replace("<svg", f'<svg viewBox="0 0 {sz.width()} {sz.height()}"', 1)
            self.komposer.tambah({"nama": Path(f).stem, "jenis": "svg", "isi": teks, "w": sz.width(),
                                  "h": sz.height()})
            return
        img = QImage(f)
        if img.isNull():
            self._galat("Gambar tidak bisa dibaca.")
            return
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        img.save(buf, "PNG")
        self.komposer.tambah({"nama": Path(f).stem, "jenis": "png", "w": img.width(), "h": img.height(),
                              "isi": base64.b64encode(bytes(buf.data())).decode("ascii")})

    def _ekspor_komposer(self, fmt):
        s, (w, h) = self.komposer.svg()
        if not s:
            self._galat("Komposer masih kosong.")
            return
        if fmt == "salin":
            self._salin_svg(s, w, h, "Figur")
            return
        dasar = nama_aman(self.proyek.nama) if self.proyek else "virmodock"
        if fmt == "svg":
            f = self._path("Simpan figur", f"{dasar}_figur.pdf", "PDF (*.pdf);;SVG (*.svg)")
            jenis = "svg" if f.lower().endswith(".svg") else "pdf"
        else:
            f = self._path("Simpan figur", f"{dasar}_figur.tif", "TIFF (*.tif);;PNG (*.png)")
            jenis = "png" if f.lower().endswith(".png") else "tif"
        if f:
            self._simpan_svg(s, f, jenis, w, h, mm=self.komposer.opsi["lebar_mm"], dpi=600)
            self.log.tulis(f"Figur disimpan: {f}")
            self.statusBar().showMessage(f"Figur disimpan: {f}", 5000)

    def _ekspor_sifat(self, fmt):
        if not self.sifat.data:
            self._galat("Belum ada data sifat ligan.")
            return
        dasar = nama_aman(self.proyek.nama) if self.proyek else "virmodock"
        if fmt == "csv":
            f = self._path("Simpan tabel sifat ligan", f"{dasar}_sifat_ligan.csv", "CSV (*.csv)")
            if f:
                Path(f).write_text(sifat_mod.csv_teks(self.sifat.data), encoding="utf-8")
                self.log.tulis(f"Tabel sifat ligan disimpan: {f}")
            return
        if fmt == "salin":
            self._salin_svg(self.sifat.svg(gelap=False), 760, 600, "BOILED-Egg")
            return
        if fmt == "svg":
            f = self._path("Simpan BOILED-Egg", f"{dasar}_boiled_egg.svg", "SVG (*.svg);;PDF (*.pdf)")
            jenis = "pdf" if f.lower().endswith(".pdf") else "svg"
        else:
            f = self._path("Simpan BOILED-Egg", f"{dasar}_boiled_egg.png", "PNG (*.png);;TIFF (*.tif)")
            jenis = "tif" if f.lower().endswith((".tif", ".tiff")) else "png"
        if f:
            self._simpan_svg(self.sifat.svg(gelap=False), f, jenis, 760, 600, mm=140, dpi=600)
            self.log.tulis(f"BOILED-Egg disimpan: {f}")
            self.statusBar().showMessage(f"BOILED-Egg disimpan: {f}", 5000)

    def _reseptor_objek(self):
        siap = [o for o in self.objek.values() if o.jenis == "protein" and o.info.get("siap_docking")]
        lain = [o for o in self.objek.values() if o.jenis == "protein"]
        return (siap or lain or [None])[0]

    def _mol_objek(self, o):
        if o.jenis == "pose" and o.info.get("pdbqt") and self.proyek and o.info.get("lig_pdbqt"):
            f = self.proyek.p(o.info["lig_pdbqt"])
            if f.exists():
                return analisis.pose_mol(f.read_text(), o.info["pdbqt"])
        return analisis.mol_dari_objek(o)

    def _tampilkan_farmakofor(self, *_):
        """Fitur farmakofor 3D pose/ligan aktif -> bola kerangka berwarna di viewport."""
        if not self.a_farma.isChecked():
            self.viewer.js("farmakofor", [])
            return
        a = self._aktif_inter
        if not a or a["oid"] not in self.objek:
            self.viewer.js("farmakofor", [])
            self.statusBar().showMessage("Farmakofor: pilih pose hasil docking atau ligan dulu.", 5000)
            return
        from ..core import kemiripan
        try:
            fs = kemiripan.fitur(a["mol"])
        except Exception as e:
            self._galat(f"Farmakofor gagal: {e}")
            return
        self._farma_aktif = fs
        self.viewer.js("farmakofor", fs, {"label": False})
        self.statusBar().showMessage(f"Farmakofor {a['judul']}: {kemiripan.ringkas_fitur(fs)}", 12000)
        self.log.tulis(f"Farmakofor {a['judul']}: {kemiripan.ringkas_fitur(fs)}")

    def _tampilkan_kontribusi(self, *_):
        """Kontribusi energi per atom (fungsi skor Vina) untuk pose aktif -> bola berwarna di viewport."""
        if not self.a_kontrib.isChecked():
            self.viewer.js("kontribusi", None, [])
            return
        a = self._aktif_inter
        o = self.objek.get(a["oid"]) if a else None
        if not o or o.jenis != "pose" or not o.info.get("pdbqt"):
            self.viewer.js("kontribusi", None, [])
            self.statusBar().showMessage("Kontribusi per atom: pilih pose hasil docking dulu.", 5000)
            return
        j = self.pelaksana.cari(o.info.get("job")) if o.info.get("job") else None
        rf = self.proyek.p(j["reseptor"]) if j and j.get("reseptor") else None
        if not rf or not rf.exists():
            self.statusBar().showMessage("Kontribusi per atom: berkas reseptor PDBQT job tidak ditemukan.", 5000)
            return
        from ..core import kontribusi
        try:
            daftar, total = kontribusi.per_atom(rf.read_text(), o.info["pdbqt"])
        except Exception as e:
            self._galat(f"Kontribusi per atom gagal: {e}")
            return
        self.viewer.js("kontribusi", o.id, daftar, {"label": True},
                       cb=lambda n: n == 0 and self.statusBar().showMessage(
                           "Kontribusi per atom: atom pose tidak cocok dengan objek di viewport.", 6000))
        urut = sorted(daftar, key=lambda x: x["energi"])
        baik = ", ".join(f"{x['nama']} {x['energi']:.2f}" for x in urut[:3])
        buruk = ", ".join(f"{x['nama']} {x['energi']:+.2f}" for x in urut[::-1][:2] if x["energi"] > 0)
        self.statusBar().showMessage(f"Kontribusi Vina antarmolekul {total:.2f} kcal/mol · terbaik: {baik}"
                                     + (f" · merugikan: {buruk}" if buruk else ""), 15000)
        self.log.tulis(f"Kontribusi per atom {o.info.get('ligan', '')} {o.nama}: total {total:.2f} kcal/mol; "
                       + "; ".join(f"{x['nama']} {x['energi']:.2f}" for x in urut))

    def analisis_objek(self, o):
        """Interaksi pose/ligan aktif -> panel Interaksi, viewport, diagram 2D."""
        rec = self._reseptor_objek()
        if rec is None or o.jenis not in ("pose", "ligan") or o.info.get("aditif"):
            return
        try:
            if o.id not in self._cache_mol:
                self._cache_mol[o.id] = self._mol_objek(o)
            if rec.id not in self._cache_rec:
                self._cache_rec = {rec.id: analisis.baca_reseptor(rec.teks)}
            mol = self._cache_mol[o.id]
            daftar = analisis.interaksi(analisis.gabung_flex(self._cache_rec[rec.id], o.info.get("flex")), mol)
        except Exception as e:
            self.log.tulis(f"Analisis interaksi {o.nama} gagal: {e}")
            return
        self._aktif_inter = {"oid": o.id, "rec": rec.id, "daftar": daftar, "mol": mol,
                             "judul": f"{o.info.get('ligan', o.nama)}" + (f" · {o.nama}" if o.jenis == "pose" else "")
                             + (f" · {o.info['energi']:.2f} kcal/mol" if o.info.get("energi") is not None else "")}
        self.p_inter.muat(self._aktif_inter["judul"], daftar)
        self._tampilkan_interaksi()
        self._gambar_diagram()
        if self.a_kontrib.isChecked():
            self._tampilkan_kontribusi()
        if self.a_farma.isChecked():
            self._tampilkan_farmakofor()
        if o.jenis == "pose":
            hb = sum(1 for x in daftar if x.get("jenis") == "hbond")
            hf = sum(1 for x in daftar if x.get("jenis") == "hidrofobik")
            pi = sum(1 for x in daftar if x.get("jenis") in ("pi", "pikation"))
            self.statusBar().showMessage(
                f"Interaksi {o.nama}: {len(daftar)} interaksi ({hb} ikatan H, {hf} hidrofobik, {pi} π) · Ditampilkan di 3D",
                5000
            )

    def _tampilkan_interaksi(self, *_):
        a = self._aktif_inter
        if not a:
            return
        if not self.a_inter.isChecked() or a["oid"] not in self.objek or not self.objek[a["oid"]].tampil:
            self.viewer.js("interaksi", [], {})
            self.viewer.js("residuKontak", a["rec"], None)
            return
        jenis = self.p_inter.jenis_tampil()
        d = [dict(h, warna=theme.INTERAKSI.get(h["jenis"], "#888888")) for h in a["daftar"] if h["jenis"] in jenis]
        self.viewer.js("interaksi", d, {"jarak": self.p_inter.c_jarak.isChecked(),
                                         "label": self.p_inter.c_label.isChecked()})
        res = {}
        for h in d:
            res.setdefault(h["rantai"] or " ", set()).add(h["resi"])
        sel = {"or": [{"chain": c.strip() or None, "resi": sorted(r)} if c.strip() else {"resi": sorted(r)}
                      for c, r in res.items()]} if res and self.p_inter.c_stick.isChecked() else None
        self.viewer.js("residuKontak", a["rec"], sel)

    def _fokus_interaksi(self, h):
        a = self._aktif_inter
        if a:
            sel = {"id": a["rec"], "resi": h["resi"]}
            if h.get("rantai"):
                sel["chain"] = h["rantai"]
            self._fokus(sel)
            self.viewer.js("sorot", a["rec"], sel)
            self.statusBar().showMessage(
                f"Fokus interaksi: {h.get('resn', '')} {h['resi']} ({h.get('jenis', '')}) · Jarak: {h.get('jarak', 0):.2f} Å",
                5000
            )

    def _svg_diagram(self, vdw=True, jarak=True, transparan=False, judul=True, lebar=960, tinggi=720, gelap=None):
        a = self._aktif_inter
        if not a:
            return ""
        daftar = [h for h in a["daftar"] if vdw or h["jenis"] != "vdw"]
        return diagram2d.svg(a["mol"], daftar, lebar, tinggi, a["judul"] if judul else "",
                             gelap=(self.mode == "gelap") if gelap is None else gelap, transparan=transparan,
                             warna=theme.INTERAKSI, jarak=jarak)

    def _gambar_diagram(self):
        try:
            s = self._svg_diagram(self.diagram.c_vdw.isChecked(), self.diagram.c_jarak.isChecked())
        except Exception as e:
            self.log.tulis(f"Diagram 2D gagal: {e}")
            s = ""
        self.diagram.tampil(s, theme.TOKEN[self.mode]["surf"])

    def analisis_ulang(self):
        if not self.proyek:
            return
        self.s_prog.setText("Menganalisis hasil…")
        kerja.jalankan(analisis.analisis_ulang, self.proyek, log=self.log.tulis,
                       selesai=lambda n: (self.s_prog.setText(""), self._muat_hasil(), self.minta_simpan(),
                                          n and self.log.tulis(f"Analisis dilengkapi untuk {n} ligan.")),
                       galat=self._galat)

    def qc_pose_aktif(self):
        """PoseBusters lengkap untuk pose/ligan yang sedang dianalisis (pose mana pun), hasil di dialog."""
        from ..core import qc
        if not qc.tersedia():
            self._galat("Paket posebusters tidak terpasang.")
            return
        a = self._aktif_inter
        o = self.objek.get(a["oid"]) if a else None
        prot = qc.jalur_protein(self.proyek) if self.proyek else None
        if not o or prot is None:
            self._galat("Pilih pose dulu (klik dua kali baris di tab Hasil) dan pastikan reseptor sudah disiapkan.")
            return
        mol = a["mol"]
        self.s_prog.setText("PoseBusters…")
        kerja.jalankan(lambda lapor=None: qc.periksa_proses(mol, prot), log=self.log.tulis,
                       selesai=lambda h: (self.s_prog.setText(""), self._tampil_qc(a["judul"], h)),
                       galat=lambda e: (self.s_prog.setText(""), self._galat(f"PoseBusters gagal: {e}")))

    def _tampil_qc(self, judul, h):
        from html import escape
        from ..core import qc
        t = theme.TOKEN[self.mode]
        o = [f"<p><b>{escape(judul)}</b></p><p>{h['n_uji'] - len(h['gagal'])}/{h['n_uji']} uji lulus - "
             + (f"<span style='color:{t['ok']}'><b>pose wajar secara fisik (PB-valid)</b></span>" if h["lulus"] else
                f"<span style='color:{t['bad']}'><b>ada uji yang gagal</b></span>") + "</p><table>"]
        kel = None
        for _k, nama, g, ok in h["uji"]:
            if g != kel:
                o.append(f"<tr><td colspan=2><b>{g}</b></td></tr>")
                kel = g
            o.append(f"<tr><td>{escape(nama)}</td><td style='color:{t['ok'] if ok else t['bad']}'>"
                     f"{'lulus' if ok else 'GAGAL'}</td></tr>")
        o.append("</table><p>")
        o += [f"{escape(qc.ANGKA[k])}: {v}<br>" for k, v in h["angka"].items()]
        o.append(f"</p><p style='color:{t['mut']}'>{escape(qc.SITASI)}</p>")
        box = QMessageBox(self)
        box.setWindowTitle("PoseBusters - kontrol kualitas pose")
        box.setTextFormat(Qt.RichText)
        box.setText("".join(o))
        box.exec()
        self.log.tulis(f"PoseBusters {judul}: " + ("lulus semua uji" if h["lulus"] else "gagal: " + ", ".join(h["gagal"])))

    def _isi_kristal(self):
        """Proyek lama: simpan koordinat ligan kristal untuk RMSD redocking."""
        pr = self.proyek
        for l in pr.ligan:
            if l.get("ligan_asli") and not l.get("kristal"):
                o = next((x for x in self.objek.values() if x.nama == l["nama"] and x.fmt == "pdb"
                          and x.info.get("ligan_asli")), None)
                if o:
                    pr.p("ligan", "sumber", f"{l['id']}_kristal.pdb").write_text(o.teks, encoding="utf-8")
                    l["kristal"] = f"ligan/sumber/{l['id']}_kristal.pdb"
