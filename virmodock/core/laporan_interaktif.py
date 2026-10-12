"""Laporan HTML interaktif satu berkas (bisa dibuka offline di peramban mana pun, dikirim lewat email/WA).

Isi: penjelajah 3D (3Dmol.js disisipkan utuh, lisensi BSD-3) - klik baris tabel untuk melihat pose ligan di
situs pengikatan beserta residu kontak & daftar interaksi; tabel hasil lengkap yang bisa dicari dan
diurutkan; laporan lengkap (isi sama dengan laporan PDF) di tab kedua.
"""
import base64
import json
import re
from html import escape

from . import paths
from .laporan import GAYA as GAYA_LAPORAN
from .laporan import _id

KOLOM = (("peringkat", "#", "n"), ("ligan", "Ligan", ""), ("energi", "ΔG (kcal/mol)", "n"), ("ki", "Ki perkiraan", ""),
         ("le", "LE", "n"), ("hbond", "Ikatan H", "n"), ("hidrofobik", "Hidrofobik", "n"), ("pi", "π", "n"),
         ("rmsd_kristal", "RMSD kristal (Å)", "n"), ("posebusters", "PoseBusters", ""), ("mesin", "Mesin", ""))

CSS = """
:root{--latar:#f4f6f9;--kartu:#fff;--garis:#d3d9e1;--tinta:#1b2430;--tinta2:#465263;--mut:#7b8698;--aksen:#1f5fbf;
--aksen-s:#e2ebf8;--ok:#2e9e5b;--bad:#cf3f3f;--warn:#c98a12}
*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',Arial,sans-serif;font-size:14px;color:var(--tinta);
background:var(--latar)}
header{background:linear-gradient(90deg,#173b6c,#204f8f);color:#fff;padding:14px 20px}
header h1{margin:0;font-size:20px;font-weight:600}header p{margin:3px 0 0;opacity:.8;font-size:12.5px}
nav{display:flex;gap:4px;padding:0 16px;background:#173b6c}
nav button{background:none;border:0;color:#cfe0f7;padding:9px 14px;font:inherit;cursor:pointer;border-radius:6px 6px 0 0}
nav button.aktif{background:var(--latar);color:var(--tinta);font-weight:600}
main{padding:14px 16px}.tab{display:none}.tab.aktif{display:block}
.grid{display:grid;grid-template-columns:minmax(320px,1fr) minmax(320px,1.2fr);gap:14px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
.kartu{background:var(--kartu);border:1px solid var(--garis);border-radius:8px;padding:10px}
#v3d{position:relative;width:100%;height:470px;border-radius:6px;overflow:hidden;background:#fff}
.alat{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.alat button,.alat label{font:inherit;font-size:12.5px;padding:4px 10px;border:1px solid var(--garis);background:#fff;
border-radius:5px;cursor:pointer;color:var(--tinta)}.alat button:hover{background:var(--aksen-s)}
#cari{width:100%;padding:7px 10px;border:1px solid var(--garis);border-radius:6px;font:inherit;margin-bottom:8px}
.gulir{max-height:470px;overflow:auto;border:1px solid var(--garis);border-radius:6px}
table.h{border-collapse:collapse;width:100%;font-size:12.5px}
table.h th{position:sticky;top:0;background:#e9ecf1;text-align:left;padding:6px;cursor:pointer;white-space:nowrap;
user-select:none}table.h th:hover{background:#dde3eb}
table.h td{padding:5px 6px;border-top:1px solid #eceff3;white-space:nowrap}
table.h td.n,table.h th.n{text-align:right;font-variant-numeric:tabular-nums}
table.h tr.ada{cursor:pointer}table.h tr.ada:hover td{background:#f1f5fb}
table.h tr.pilih td{background:var(--aksen-s)!important}table.h tr.tanpa td{color:var(--mut)}
.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}
#rinci h3{margin:4px 0 6px;font-size:15px}#rinci .mut{color:var(--mut);font-size:12.5px}
.chip{display:inline-block;padding:2px 8px;margin:2px;border-radius:10px;font-size:12px;color:#fff}
.lap{background:#fff;border:1px solid var(--garis);border-radius:8px;padding:18px 22px;max-width:980px}
.lap img{max-width:100%;height:auto}
footer{color:var(--mut);font-size:12px;padding:6px 16px 16px}
"""

JS = r"""
const D = JSON.parse(document.getElementById('data').textContent);
const WARNA = {hbond:'#2b6fd6', hidrofobik:'#7a8a3a', pi:'#2e9e5b', pikation:'#8e44ad', garam:'#cf3f3f',
               halogen:'#16a2a2', logam:'#9a6b2f', vdw:'#9aa5b1'};
let v = null, recModel = null, poseModel = null, permukaan = null, label = true, putar = false, urut = {k: 'peringkat', naik: true};
function tab(n){document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('aktif',b.dataset.t===n));
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('aktif',t.id===n)); if(n==='jelajah'&&v) v.resize();}
function f(x,d){ if(x===null||x===undefined||x==='') return '-'; return typeof x==='number' ? x.toFixed(d).replace('.',',').replace('-','−') : x; }
function isiTabel(){
  const q = document.getElementById('cari').value.toLowerCase();
  let rows = D.baris.filter(b => !q || (b.ligan+' '+b.mesin).toLowerCase().includes(q));
  rows.sort((a,b)=>{let x=a[urut.k], y=b[urut.k]; if(x===null||x===undefined) return 1; if(y===null||y===undefined) return -1;
    return (x<y?-1:x>y?1:0)*(urut.naik?1:-1);});
  const tb = document.querySelector('#tabel tbody'); tb.innerHTML='';
  for(const b of rows){
    const tr=document.createElement('tr'); tr.className = b.pose>=0 ? 'ada' : 'tanpa';
    if(b.pose>=0){ tr.onclick=()=>tampil(b.pose, tr); tr.title='Klik untuk melihat pose 3D'; }
    tr.innerHTML = D.kolom.map(([k,_,c])=>{let x=b[k]; let cls=c;
      if(k==='posebusters'&&b.qc!==null) cls += b.qc ? ' ok':' bad';
      const d = k==='le'?3:(k==='energi'||k==='rmsd_kristal')?2:0;
      return `<td class="${cls}">${typeof x==='number'?f(x,d):(x??'-')}</td>`}).join('');
    tb.appendChild(tr);
  }
}
function siapkanViewer(){
  v = $3Dmol.createViewer('v3d',{backgroundColor:'white'});
  v.fogStart = 0.75;   // kabut kedalaman bawaan (0,4) membuat warna pucat
  v.setViewStyle({style:'outline', color:'#16202e', width:0.055});   // garis tepi, sama dengan viewport
  recModel = v.addModel(D.reseptor, D.fmt_reseptor);
  v.setStyle({model:recModel},{cartoon:{color:'#c9d3e0', opacity:0.8}});
  if(D.pose.length) tampil(0, null); else { v.zoomTo(); v.render(); }
}
function tampil(i, tr){
  const p = D.pose[i]; if(!p) return; aktif = i;
  document.querySelectorAll('#tabel tr').forEach(r=>r.classList.remove('pilih'));
  if(tr) tr.classList.add('pilih'); else { const r=[...document.querySelectorAll('#tabel tbody tr')].find(r=>r.cells[1]&&r.cells[1].textContent===p.ligan); if(r) r.classList.add('pilih'); }
  if(poseModel) v.removeModel(poseModel);
  v.removeAllLabels(); v.removeAllShapes();
  poseModel = v.addModel(p.sdf, 'sdf');
  v.setStyle({model:recModel},{cartoon:{color:'#c9d3e0', opacity:0.8}});
  v.setStyle({model:poseModel},{stick:{colorscheme:'greenCarbon', radius:0.2}});
  const kontak = selKontak(p);
  v.addStyle(kontak,{stick:{colorscheme:'whiteCarbon', radius:0.14}});
  const warnaRes={}; for(const h of p.interaksi){ if(h.jenis!=='vdw'&&!warnaRes[h.residu]) warnaRes[h.residu]=WARNA[h.jenis]; }
  if(label){ const sudah={}; for(const a of v.selectedAtoms(kontak)){ const k=a.chain+a.resi; if(sudah[k]||a.atom!=='CA') continue; sudah[k]=1;
      const ak = warnaRes[a.resn+' '+a.resi+' '+a.chain] || warnaRes[a.resn+' '+a.resi];
      v.addLabel(a.resn+' '+a.resi,{position:{x:a.x,y:a.y,z:a.z},fontSize:11.5,font:'Segoe UI',vmGaya:'residu',aksen:ak,
        fontColor:'#142033',warna2:'#5b6b82',backgroundColor:'#ffffff',backgroundOpacity:0.94,borderColor:'#d5dce6',
        borderThickness:1,alignment:'bottomCenter'}); } }
  for(const h of p.interaksi){ if(!h.p||!h.l||h.jenis==='vdw') continue;
    v.addCylinder({start:{x:h.p[0],y:h.p[1],z:h.p[2]}, end:{x:h.l[0],y:h.l[1],z:h.l[2]}, radius:0.06, dashed:true,
      color:WARNA[h.jenis]||'#888', fromCap:1, toCap:1}); }
  if(permukaan!==null){ v.removeSurface(permukaan); permukaan = v.addSurface($3Dmol.SurfaceType.VDW,{opacity:0.55,color:'#e8eef7'},kontak); }
  v.zoomTo({model:poseModel}); v.zoom(0.75); v.render();
  const nama = {}; D.jenis.forEach(([k,t])=>nama[k]=t);
  const hit = {}; p.interaksi.forEach(h=>{ if(h.jenis!=='vdw') hit[h.jenis]=(hit[h.jenis]||0)+1; });
  document.getElementById('rinci').innerHTML = `<h3>${p.ligan}</h3><div class="mut">ΔG ${f(p.energi,2)} kcal/mol · ${p.mesin} · pose ${p.peringkat}</div>`
    + `<div style="margin:6px 0">${Object.entries(hit).map(([k,n])=>`<span class="chip" style="background:${WARNA[k]||'#888'}">${nama[k]||k} ${n}</span>`).join('')||'<span class="mut">Tidak ada interaksi spesifik.</span>'}</div>`
    + `<table class="h"><tr><th>Jenis</th><th>Residu</th><th>Atom</th><th class="n">Jarak (Å)</th></tr>`
    + p.interaksi.filter(h=>h.jenis!=='vdw').map(h=>`<tr><td><span class="chip" style="background:${WARNA[h.jenis]||'#888'}">${nama[h.jenis]||h.jenis}</span></td><td>${h.residu}</td><td>${h.atom}</td><td class="n">${f(h.jarak,2)}</td></tr>`).join('') + '</table>';
}
let aktif = 0;
function pilihan(){ return aktif; }
function selKontak(p){ // residu kontak (≤ 4 Å, dihitung VirmoDock) pada model reseptor
  const daftar = p.kontak.map(([c,r]) => c ? {chain:c, resi:r} : {resi:r});
  return daftar.length ? {model:recModel, or:daftar} : {model:recModel, resi:-999999}; }
function alat(k){
  if(k==='reset'){ v.zoomTo({model:poseModel}); v.zoom(0.75); v.render(); }
  if(k==='semua'){ v.zoomTo(); v.render(); }
  if(k==='permukaan'){ if(permukaan!==null){ v.removeSurface(permukaan); permukaan=null; v.render(); }
    else { const i=pilihan(); permukaan = v.addSurface($3Dmol.SurfaceType.VDW,{opacity:0.55,color:'#e8eef7'},selKontak(D.pose[i<0?0:i])); } }
  if(k==='label'){ label=!label; const i=pilihan(); tampil(i<0?0:i,null); }
  if(k==='putar'){ putar=!putar; v.spin(putar?'y':false, 0.6); }
  if(k==='png'){ const a=document.createElement('a'); a.href=v.pngURI(); a.download='pose.png'; a.click(); }
}
document.querySelectorAll('#tabel th').forEach((th,i)=>th.onclick=()=>{ const k=D.kolom[i][0];
  urut = {k, naik: urut.k===k ? !urut.naik : true}; isiTabel(); });
document.getElementById('cari').oninput = isiTabel;
isiTabel();
window.addEventListener('load', siapkanViewer);
"""


def buat(judul, html_laporan, baris, pose, reseptor, fmt_reseptor, js3dmol, jenis, gambar3d=None, svg2d=None,
         sub=""):
    """baris: eksmod.baris_hasil; pose: list dict {ligan, energi, peringkat, mesin, sdf, interaksi[]} (urut = indeks
    yang dirujuk baris['pose']); jenis: [(kunci, nama)] jenis interaksi."""
    m = re.search(r"<body[^>]*>(.*)</body>", html_laporan, re.S)
    isi = m.group(1) if m else html_laporan
    if gambar3d:
        isi = isi.replace("src='img3d'", f"src='data:image/png;base64,{base64.b64encode(gambar3d).decode()}'")
    if svg2d:
        isi = isi.replace("src='img2d'",
                          f"src='data:image/svg+xml;base64,{base64.b64encode(svg2d.encode('utf-8')).decode()}'")
    gaya_lap = re.sub(r"(^|\})\s*([^{}]+)\{", lambda g: g.group(1) + " " + ", ".join(
        ".lap " + s.strip() for s in g.group(2).split(",")) + " {", GAYA_LAPORAN)
    data = {"baris": [{k: b.get(k) for k, _, _ in KOLOM} | {"ki": _id(str(b.get("ki") or "")) or None,
                                                         "pi": b.get("pi", 0) + b.get("pikation", 0),
                                                         "qc": (b["qc"].get("lulus") if b.get("qc") and not
                                                                b["qc"].get("galat") else None),
                                                         "pose": b.get("_pose", -1)} for b in baris],
            "pose": pose, "reseptor": reseptor, "fmt_reseptor": fmt_reseptor, "kolom": KOLOM, "jenis": jenis}
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    js_label = (paths.VIEWER / "label_vm.js").read_text(encoding="utf-8")   # label pil tajam, sama dengan viewport
    kepala_tabel = "".join(f"<th class='{c}' title='Klik untuk mengurutkan'>{escape(t)}</th>" for _k, t, c in KOLOM)
    return f"""<!doctype html>
<html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="VirmoDock"><title>{escape(judul)}</title>
<style>{CSS}{gaya_lap}</style>
<script>/* 3Dmol.js - BSD 3-Clause License, (c) University of Pittsburgh. https://3dmol.org */
{js3dmol}</script>
<script>{js_label}</script></head>
<body><header><h1>{escape(judul)}</h1><p>{escape(sub)}</p></header>
<nav><button class="aktif" data-t="jelajah" onclick="tab('jelajah')">Penjelajah interaktif</button>
<button data-t="laporan" onclick="tab('laporan')">Laporan lengkap</button></nav>
<main><section id="jelajah" class="tab aktif"><div class="grid">
<div class="kartu"><div id="v3d"></div>
<div class="alat"><button onclick="alat('reset')">Fokus ligan</button><button onclick="alat('semua')">Seluruh protein</button>
<button onclick="alat('permukaan')">Permukaan kantong</button><button onclick="alat('label')">Label residu</button>
<button onclick="alat('putar')">Putar</button><button onclick="alat('png')">Simpan PNG</button></div>
<div id="rinci" style="margin-top:10px"></div></div>
<div class="kartu"><input id="cari" placeholder="Cari ligan atau mesin…">
<div class="gulir"><table class="h" id="tabel"><thead><tr>{kepala_tabel}</tr></thead><tbody></tbody></table></div>
<p style="color:var(--mut);font-size:12px;margin:6px 2px 0">Baris berwarna gelap dapat diklik untuk melihat pose 3D
(ligan teratas). Klik judul kolom untuk mengurutkan.</p></div></div></section>
<section id="laporan" class="tab"><div class="lap">{isi}</div></section></main>
<footer>Dibuat dengan VirmoDock. Hasil docking adalah prediksi komputasi, bukan bukti aktivitas biologis.</footer>
<script type="application/json" id="data">{data_json}</script>
<script>{JS}</script></body></html>"""
