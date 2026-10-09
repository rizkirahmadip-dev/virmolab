"""Diagnostik bug kamera: ukuran #gl vs kanvas vs viewport WebGL setelah impor (meniru dev/buat_screenshot.py)."""
import os
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

sys.argv = [sys.argv[0]]
st = QSettings("VirmoDock", "VirmoDock")
for k in ("layout", "layout_v2", "sesi_terbuka", "geometri"):
    st.remove(k)
st.setValue("wizard_selesai", True)
st.setValue("tema", "terang")
UK = [int(x) for x in os.environ.get("VD_UKURAN", "1440x900").split("x")]

import virmodock.app as A  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
Path("dev/uji/gambar").mkdir(parents=True, exist_ok=True)  # keluaran gambar uji

JS = ("(()=>{const g=document.getElementById('gl').getBoundingClientRect(), c=VM.v.getCanvas(), "
      "gl=c.getContext('webgl2')||c.getContext('webgl'), vp=gl?gl.getParameter(gl.VIEWPORT):null;"
      "return JSON.stringify({gl:[Math.round(g.width),Math.round(g.height)], css:[c.clientWidth,c.clientHeight],"
      "buf:[c.width,c.height], vp, W:[VM.v.WIDTH,VM.v.HEIGHT], dpr:window.devicePixelRatio, "
      "win:[innerWidth,innerHeight]});})()")


def hook():
    from virmodock.ui import mainwindow

    class U(mainwindow.JendelaUtama):
        def __init__(s):
            super().__init__()
            s.resize(*UK)
            s.move(30, 30)
            print("init", flush=True)
            s.viewer.page().renderProcessTerminated.connect(lambda st, kode: print("RENDERER MATI", st, kode, flush=True))
            QTimer.singleShot(3000, s.l1)

        def cek(s, label, lanjut=None):
            def cb(r):
                print(label, r, flush=True)
                s.grab().save(f"dev/uji/gambar/diag_{label}.png")
                if lanjut:
                    lanjut()
            print("cek", label, flush=True)
            print("LOG:", s.log.toPlainText()[-1500:], flush=True)
            s.grab().save(f"dev/uji/gambar/diag_{label}_pra.png")
            s.viewer.page().runJavaScript("1+1", 0, lambda r: print("js-sederhana", r, flush=True))
            s.viewer.page().runJavaScript("JSON.stringify([innerWidth, innerHeight, document.getElementById('gl').getBoundingClientRect().width])", 0, lambda r: print("js-ukuran", r, flush=True))
            s.viewer.page().runJavaScript(JS, 0, cb)

        def l1(s):
            print("l1", flush=True)
            s.viewer.page().runJavaScript("2+2", 0, lambda r: print("js-sebelum-impor", r, flush=True))
            s.viewer.pesanJs.connect(lambda t: print("KONSOL", t, flush=True))
            s.viewer.page().runJavaScript("""
              setInterval(()=>console.log('detak'), 500);
              for (const k of Object.keys(VM)) { const f = VM[k]; if (typeof f !== 'function' || k==='gizmo') continue;
                VM[k] = function(...a){ console.log('masuk '+k); const r = f.apply(this, a); console.log('keluar '+k); return r; }; }
              for (const k of ['resize','zoomTo','render','zoom','setView']) { const f = VM.v[k].bind(VM.v);
                VM.v[k] = function(...a){ const g=document.getElementById('gl').getBoundingClientRect(); console.log('v.'+k+' masuk '+JSON.stringify(a[0]&&a[0].model?{model:a[0].model.length}:a[0])+' gl '+g.width+'x'+g.height); const r=f(...a); console.log('v.'+k+' keluar'); return r; }; }
            """, 0)
            for t in (300, 800, 1500, 2500):
                QTimer.singleShot(t, lambda t=t: s.viewer.page().runJavaScript("3+3", 0, lambda r, t=t: print("js", t, r, flush=True)))
            s.impor([str(Path("dev/uji/1HSG.pdb").resolve())])
            QTimer.singleShot(4000, lambda: s.cek("impor", lambda: QTimer.singleShot(2000, s.l2)))

        def l2(s):
            s.viewer.js("segarkanKanvas")
            QTimer.singleShot(1000, lambda: s.cek("segarkan", lambda: QApplication.quit()))

    mainwindow.JendelaUtama = U
    A.main()


hook()
