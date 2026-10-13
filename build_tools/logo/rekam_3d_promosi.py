"""Rekam klip 3D sinematik (proyek contoh 1HSG, pose 1) dari viewer VirmoLab -> bingkai JPEG untuk video promosi.

Jalur kamera sendiri: protein utuh berputar pelan -> terbang ke kantong ikatan -> orbit ligan (bidang potong depan
menyingkap kantong; label residu terpenting & jarak Å muncul saat dekat, huruf diperbesar). Kotak grid disembunyikan. Setiap bingkai dirender ulang oleh WebGL pada resolusi penuh (bukan rekaman layar).

  .venv\\Scripts\\python.exe build_tools\\logo\\rekam_3d_promosi.py KELUAR_DIR [detik] [fps] [lebar] [tinggi]
"""
import base64
import os
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AKAR))
OUT = Path(sys.argv[1])
DETIK = float(sys.argv[2]) if len(sys.argv) > 2 else 13.0
FPS = int(sys.argv[3]) if len(sys.argv) > 3 else 60
LEBAR = int(sys.argv[4]) if len(sys.argv) > 4 else 1332
TINGGI = int(sys.argv[5]) if len(sys.argv) > 5 else 1064
PROYEK = AKAR / "dev" / "uji" / "kerja_docs" / "Docs_1HSG.vmd"
OUT.mkdir(parents=True, exist_ok=True)
for f in OUT.glob("f_*.jpg"):
    f.unlink()

from PySide6.QtCore import QSettings, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

sys.argv = [sys.argv[0]]
app = QApplication(sys.argv)
app.setApplicationName("VirmoDock")
app.setOrganizationName("VirmoDock")
app.setStyle("Fusion")
st = QSettings("VirmoDock", "VirmoDock")
tema_lama = st.value("tema")
st.setValue("tema", "terang")
from virmodock import i18n  # noqa: E402
i18n.pasang(app)
from virmodock.core import ekspor  # noqa: E402
from virmodock.ui.mainwindow import JendelaUtama  # noqa: E402

w = JendelaUtama()
w.resize(1180, 820)          # viewport kecil -> label relatif lebih besar di bingkai
w.show()
n = int(round(DETIK * FPS))
keadaan = {"i": 0}


def pulihkan_dan_keluar(kode=0):
    if tema_lama is not None:
        st.setValue("tema", tema_lama)
    w.close()
    app.exit(kode)


def buka():
    w.buka_proyek(str(PROYEK))
    QTimer.singleShot(4000, pose)


def pose():
    b = ekspor.baris_hasil(w.proyek)
    w.atur_ruang("analisis")
    w.buka_pose(b[0]["job"], b[0]["lid"], 1)
    w.tab_tengah.setCurrentWidget(w.w_view)
    QTimer.singleShot(5000, mulai)


FAKTOR_HURUF, MAKS_RESIDU, MAKS_JARAK = 1.95, 8, 6
JS_SIAPKAN = r"""(function(){
  const V = VM, v = VM.v;
  if (V.kotak) V.kotak.tampil = false;
  V.clearShapes('box');
  const vis = Object.values(V.models).filter(o => !o.spec || o.spec.visible !== false);
  const n = o => o.m.selectedAtoms({}).length;
  const lig = vis.filter(o => n(o) > 5).sort((a, b) => n(a) - n(b))[0];
  v.zoomTo(V._terlihat()); v.zoom(1.55); const W = v.getView();
  v.zoomTo({model: lig.m}); v.zoom(0.80); const C = v.getView();
  const putar = (P, a, s) => { v.setView(P); v.rotate(a, s || 'y', 0); return v.getView(); };
  const K0 = putar(W, -40), K1 = putar(W, 15), K2 = putar(C, -25), K3 = putar(C, 70);
  const sl = v.getSlab();
  // label interaksi dibuat ulang khusus rekaman: huruf lebih besar, residu terpenting saja, jarak bersatuan Å
  (V.labels.inter || []).forEach(l => v.removeLabel(l));
  const F = FAKTOR_HURUF, lab = [];
  const urut = ['hbond', 'garam', 'pikation', 'pi', 'halogen', 'logam', 'hidrofobik'];
  const inter = (V._inter || []).filter(i => urut.includes(i.jenis));
  const jarakSudah = new Set();          // jarak: satu per residu (terpendek), maksimal MAKS_JARAK
  inter.filter(i => ['hbond', 'garam', 'halogen'].includes(i.jenis)).sort((a, b) => a.jarak - b.jarak)
    .filter(i => !jarakSudah.has(i.residu) && jarakSudah.size < MAKS_JARAK && jarakSudah.add(i.residu))
    .forEach(i => {
    const mid = {x: (i.l[0] + i.p[0]) / 2, y: (i.l[1] + i.p[1]) / 2, z: (i.l[2] + i.p[2]) / 2};
    lab.push(v.addLabel(i.jarak.toFixed(2).replace('.', ',') + ' Å', {position: mid, fontSize: 10 * F,
      font: 'Segoe UI', berat: 600, fontColor: i.warna, backgroundColor: '#ffffff', backgroundOpacity: 0.92,
      borderColor: i.warna, borderOpacity: 0.5, borderThickness: 1, bayang: false, padX: 4, padY: 0.5,
      inFront: true, alignment: 'center'}));
  });
  const sudah = new Set();
  inter.slice().sort((a, b) => urut.indexOf(a.jenis) - urut.indexOf(b.jenis) || (a.jarak || 9) - (b.jarak || 9))
    .forEach(i => {
      if (sudah.has(i.residu) || sudah.size >= MAKS_RESIDU) return;
      sudah.add(i.residu);
      lab.push(v.addLabel(i.resn + ' ' + i.resi + (i.rantai ? ' · ' + i.rantai : ''), {position: V.xyz(i.p), fontSize: 11.5 * F, font: 'Segoe UI',
        vmGaya: 'residu', aksen: i.warna, fontColor: '#142033', warna2: '#5b6b82', backgroundColor: '#ffffff',
        backgroundOpacity: 0.94, borderColor: '#d5dce6', borderThickness: 1, inFront: true,
        alignment: 'bottomCenter'}));
    });
  V.labels.inter = lab;
  V._promo = {K0, K1, K2, K3, lab, S0: sl.near, SF: sl.far};
  V._promoBingkai = function (t) {
    const P = this._promo, m = x => this._mulus(x), seg = (a, b) => Math.min(1, Math.max(0, (t - a) / (b - a)));
    let view;
    if (t < 0.26) view = this._antara(P.K0, P.K1, m(seg(0, 0.26)));
    else if (t < 0.50) view = this._antara(P.K1, P.K2, m(seg(0.26, 0.50)));
    else view = this._antara(P.K2, P.K3, m(seg(0.50, 1.0)));
    this.v.setView(view);
    // label muncul memudar saat kamera tiba di kantong; bidang potong depan menyingkap ligan
    const a = Math.min(1, Math.max(0, (t - 0.47) / 0.06));
    P.lab.forEach(l => {
      if (a <= 0) { l.hide(); return; }
      l.show();
      if (l.sprite && l.sprite.material) { l.sprite.material.transparent = true; l.sprite.material.opacity = a; }
    });
    const k = m(seg(0.36, 0.58));
    this.v.setSlab(P.S0 + (-6 - P.S0) * k, P.SF);
    this.rapikanLabel(false);
    this.v.render();
    return this.v.getCanvas().toDataURL('image/jpeg', 0.97);
  };
  v.setView(K0); v.render();
  return n(lig);
})()"""


def mulai():
    if w.a_box.isChecked():
        w.a_box.trigger()                                   # sembunyikan kotak grid
    w.viewer.js("animMulai", LEBAR, TINGGI, "#ffffff", "putar", 360,
                cb=lambda _: QTimer.singleShot(400, siapkan))


def siapkan():
    js = JS_SIAPKAN.replace("FAKTOR_HURUF", str(FAKTOR_HURUF)).replace("MAKS_RESIDU", str(MAKS_RESIDU)).replace("MAKS_JARAK", str(MAKS_JARAK))
    w.viewer._jalankan(js, lambda n_atom: (print("atom ligan:", n_atom), QTimer.singleShot(400, berikut)))


def berikut():
    if keadaan["i"] >= n:
        w.viewer.js("animSelesai")
        print(f"selesai: {n} bingkai {LEBAR}x{TINGGI} -> {OUT}")
        QTimer.singleShot(500, pulihkan_dan_keluar)
        return
    w.viewer._jalankan(f"VM._promoBingkai({keadaan['i'] / (n - 1):.6f})", terima)


def terima(url):
    if not url or "," not in url:
        print("GALAT: render bingkai gagal")
        pulihkan_dan_keluar(1)
        return
    (OUT / f"f_{keadaan['i']:04d}.jpg").write_bytes(base64.b64decode(url.split(",", 1)[1]))
    keadaan["i"] += 1
    if keadaan["i"] % 120 == 0:
        print(f"  {keadaan['i']}/{n}", flush=True)
    QTimer.singleShot(0, berikut)


QTimer.singleShot(3000, buka)
QTimer.singleShot(900000, lambda: (print("TIMEOUT"), pulihkan_dan_keluar(2)))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.exit(app.exec())
