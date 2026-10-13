import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from virmolab.ui.viewer_widget import Viewer
from virmolab.core import molekul
app = QApplication(sys.argv)
v = Viewer(); v.resize(900, 600); v.show()
o = molekul.baca_teks_struktur(open("dev/uji/1HSG.pdb").read(), "1HSG")[0]
v.muat(o); v.tampil(o, molekul.spek_viewer(o))
js = """(()=>{const out=[]; for (const [w,h,t] of [[2000,1400,false],[2000,1400,true],[4252,2835,false],[2000,1400,true]]) {
 const u=VM.gambar(w,h,t,'#ffffff'); const img=new Image(); out.push([w,h,t,u.length]); } 
 return JSON.stringify([out, window.devicePixelRatio, document.getElementById('gl').getBoundingClientRect().width]);})()"""
def cek():
    v.page().runJavaScript(js, 0, lambda r: print(r))
    for w, h, t in ((2000, 1400, False), (2000, 1400, True)):
        v.js("gambar", w, h, t, "#ffffff", cb=lambda u, w=w, t=t: ukur(u, w, t))
def ukur(u, w, t):
    import base64, io
    from PIL import Image
    im = Image.open(io.BytesIO(base64.b64decode(u.split(",", 1)[1])))
    print("diminta", w, "transparan", t, "->", im.size, im.mode)
QTimer.singleShot(4000, cek); QTimer.singleShot(9000, app.quit)
app.exec()
