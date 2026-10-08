'use strict';
/* VirmoDock viewport: lapisan tipis di atas 3Dmol.js.
   Python memanggil fungsi VM.* lewat runJavaScript; kejadian (klik atom,
   ukur jarak) dikirim balik lewat QWebChannel objek "py". */

const ELEM = {C: '#909090', O: '#e04a4a', N: '#3a7bd5', S: '#d4b106', H: '#f2f2f2', P: '#f08020', F: '#7fd03b',
  Cl: '#2fbf2f', CL: '#2fbf2f', Br: '#a62929', BR: '#a62929', I: '#940094', Fe: '#e06633', FE: '#e06633',
  Zn: '#7d80b0', ZN: '#7d80b0', Mg: '#3fbf3f', MG: '#3fbf3f', Ca: '#3dff00', CA_: '#3dff00', Mn: '#9c7ac7', MN: '#9c7ac7',
  Cu: '#c88033', CU: '#c88033', Na: '#ab5cf2', NA_: '#ab5cf2', K: '#8f40d4', Se: '#ffa100', SE: '#ffa100', B: '#ffb5b5'};
const PAL = ['#4e79a7', '#59a14f', '#e15759', '#b07aa1', '#f28e2b', '#76b7b2', '#edc948', '#9c755f', '#ff9da7', '#bab0ac'];
// Kyte-Doolittle
const KD = {ILE: 4.5, VAL: 4.2, LEU: 3.8, PHE: 2.8, CYS: 2.5, MET: 1.9, ALA: 1.8, GLY: -0.4, THR: -0.7, SER: -0.8, TRP: -0.9,
  TYR: -1.3, PRO: -1.6, HIS: -3.2, GLU: -3.5, GLN: -3.5, ASP: -3.5, ASN: -3.5, LYS: -3.9, ARG: -4.5};
const MUATAN = {ASP: -1, GLU: -1, LYS: 1, ARG: 1, HIS: 0.3};

const VM = {
  v: null, py: null, models: {}, shapes: {box: [], inter: [], ukur: [], sel: []}, labels: {inter: [], ukur: [], res: []},
  bgc: '#ffffff', mode: 'putar', ukurAtom: [], dark: false,

  init() {
    this.v = $3Dmol.createViewer(document.getElementById('gl'), {backgroundColor: 'white', antialias: true, cartoonQuality: 10});
    this.v.setViewChangeCallback && this.v.setViewChangeCallback(() => this.gizmo());
    const tip = document.getElementById('tip');
    this.v.setHoverable({}, true, (atom, viewer, ev) => {
      if (!atom) return;
      tip.textContent = `${atom.resn || ''} ${atom.resi ?? ''}${atom.chain ? ' ' + atom.chain : ''} · ${atom.atom || atom.elem}`;
      tip.style.display = 'block';
      const r = document.getElementById('gl').getBoundingClientRect();
      tip.style.left = (ev.clientX - r.left + 14) + 'px';
      tip.style.top = (ev.clientY - r.top + 10) + 'px';
    }, () => { tip.style.display = 'none'; });
    this.v.setHoverDuration(80);
    window.addEventListener('resize', () => { this.v.resize(); this.v.render(); });
    this.pasangKotak();
    setInterval(() => this.gizmo(), 120);
  },

  /* --------------------------------------------------------- objek */
  load(id, teks, fmt) {
    this.remove(id);
    const m = this.v.addModel(teks, fmt, {keepH: true, assignBonds: true});
    this.models[id] = {m, surf: [], spec: null};
    m.setClickable({}, true, (atom) => this.klik(id, atom));
    m.setHoverable({}, true, (atom, viewer, ev) => {
      const tip = document.getElementById('tip');
      tip.textContent = `${atom.resn || ''} ${atom.resi ?? ''}${atom.chain ? ' ' + atom.chain : ''} · ${atom.atom || atom.elem}`;
      tip.style.display = 'block';
      const r = document.getElementById('gl').getBoundingClientRect();
      tip.style.left = (ev.clientX - r.left + 14) + 'px'; tip.style.top = (ev.clientY - r.top + 10) + 'px';
    }, () => { document.getElementById('tip').style.display = 'none'; });
    return m.selectedAtoms({}).length;
  },
  remove(id) {
    const o = this.models[id];
    if (!o) return;
    o.surf.forEach(s => this.v.removeSurface(s));
    this.v.removeModel(o.m);
    delete this.models[id];
    this.v.render();
  },
  clear() { Object.keys(this.models).forEach(id => this.remove(id)); this.clearShapes('box'); this.clearShapes('inter'); this.clearShapes('ukur'); this.clearShapes('sel'); this.v.render(); },

  /* --------------------------------------------- warna & representasi */
  warna(c) {
    // c: {mode, val, carbon, min, max}
    const mode = c && c.mode || 'element';
    if (mode === 'solid') return {color: c.val};
    if (mode === 'element') {
      const map = Object.assign({}, ELEM, {C: c.carbon || ELEM.C});
      return {colorfunc: a => map[a.elem] || map[(a.elem || '').toUpperCase()] || '#ff1493'};
    }
    if (mode === 'chain') {
      const urut = {};
      return {colorfunc: a => { if (!(a.chain in urut)) urut[a.chain] = Object.keys(urut).length; return PAL[urut[a.chain] % PAL.length]; }};
    }
    if (mode === 'ss') return {colorscheme: 'ssPyMOL'};
    if (mode === 'spectrum') {
      return {colorfunc: (a) => {
        const lo = c.min ?? 1, hi = c.max ?? 500;
        const t = Math.max(0, Math.min(1, ((a.resi || 0) - lo) / Math.max(1, hi - lo)));
        return this.pelangi(t);
      }};
    }
    if (mode === 'bfactor') return {colorscheme: {prop: 'b', gradient: 'rwb', min: c.max ?? 80, max: c.min ?? 10}};
    if (mode === 'hydro') return {colorfunc: a => this.gradien(((KD[a.resn] ?? 0) + 4.5) / 9, ['#3a6fc2', '#f4f4f4', '#d07b1c'])};
    if (mode === 'muatan') return {colorfunc: a => { const q = MUATAN[a.resn] || 0; return q < 0 ? '#d64545' : q > 0.5 ? '#3a6fd6' : q > 0 ? '#8fb0e6' : '#e9e9e9'; }};
    return {};
  },
  pelangi(t) {
    const h = (1 - t) * 240;
    return `hsl(${h},70%,50%)`;
  },
  gradien(t, cs) {
    t = Math.max(0, Math.min(1, t));
    const ke = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
    const [a, b, s] = t < 0.5 ? [ke(cs[0]), ke(cs[1]), t / 0.5] : [ke(cs[1]), ke(cs[2]), (t - 0.5) / 0.5];
    return 'rgb(' + a.map((x, i) => Math.round(x + (b[i] - x) * s)).join(',') + ')';
  },
  gaya(rep, col, lap) {
    const w = this.warna(col), op = lap.opacity ?? 1;
    switch (rep) {
      case 'cartoon': {
        const cw = col && col.mode === 'spectrum' ? {color: 'spectrum'} : w;
        return {cartoon: Object.assign({opacity: op, thickness: lap.thickness ?? 0.3, arrows: true}, cw)};
      }
      case 'ribbon': return {cartoon: Object.assign({style: 'trace', thickness: 0.35, opacity: op}, w)};
      case 'sticks': return {stick: Object.assign({radius: lap.radius ?? 0.18, opacity: op}, w)};
      case 'lines': return {line: Object.assign({linewidth: 1, opacity: op}, w)};
      case 'ballstick': return {stick: Object.assign({radius: 0.12, opacity: op}, w), sphere: Object.assign({scale: 0.24, opacity: op}, w)};
      case 'spheres': return {sphere: Object.assign({scale: lap.scale ?? 1.0, opacity: op}, w)};
      case 'cross': return {cross: Object.assign({radius: 0.3}, w)};
    }
    return {};
  },
  /* spec: {visible, layers:[{sel, rep, color, opacity, radius}], surface:{type, color, opacity, mesh, sel}} */
  tampil(id, spec) {
    const o = this.models[id];
    if (!o) return;
    o.spec = spec;
    o.surf.forEach(s => this.v.removeSurface(s));
    o.surf = [];
    o.m.setStyle({}, {});
    if (spec.visible !== false) {
      (spec.layers || []).forEach(l => {
        const st = this.gaya(l.rep, l.color, l);
        const sel = Object.assign({}, l.sel || {}, {model: o.m});
        if (l.tambah) this.v.addStyle(sel, st); else this.v.setStyle(sel, st);
      });
      (spec.surfaces || []).forEach(s => {
        const t = {vdw: $3Dmol.SurfaceType.VDW, sas: $3Dmol.SurfaceType.SAS, ses: $3Dmol.SurfaceType.SES, ms: $3Dmol.SurfaceType.MS}[s.type || 'ses'];
        const style = Object.assign({opacity: s.opacity ?? 0.8, wireframe: !!s.mesh}, this.warna(s.color));
        const sel = Object.assign({model: o.m}, s.sel || {});
        const h = this.v.addSurface(t, style, sel, {model: o.m});
        o.surf.push(h);
      });
    }
    this.v.render();
  },
  fokus(sel, ms) {
    const s = Object.assign({}, sel || {});
    if (s.id !== undefined) { const o = this.models[s.id]; delete s.id; if (o) s.model = o.m; }
    this.v.zoomTo(s, ms ?? 400);
  },
  fokusSemua() { this.v.zoomTo({}, 400); },

  /* ------------------------------------------------------- bentuk */
  clearShapes(k) { (this.shapes[k] || []).forEach(s => this.v.removeShape(s)); this.shapes[k] = []; (this.labels[k] || []).forEach(l => this.v.removeLabel(l)); this.labels[k] = []; },
  /* Grid box interaktif: Shift+seret = geser, Shift+gulir = ukuran seragam, Alt+gulir = satu sumbu (X/Y/Z). */
  kotak: null, sumbu: 0, _seret: null, _kirim: null,
  pasangKotak() {
    const gl = document.getElementById('gl');
    const aktif = () => this.kotak && this.kotak.tampil && this.kotak.c;
    gl.addEventListener('mousedown', e => {
      if (!e.shiftKey || e.button !== 0 || !aktif()) return;
      e.stopPropagation(); e.preventDefault();
      this._seret = {x: e.clientX, y: e.clientY, c: this.kotak.c.slice()};
      gl.style.cursor = 'move';
    }, true);
    window.addEventListener('mousemove', e => {
      if (!this._seret) return;
      e.stopPropagation(); e.preventDefault();
      const d = this.offsetModel(e.clientX - this._seret.x, e.clientY - this._seret.y);
      this.kotak.c = this._seret.c.map((v, i) => +(v + d[i]).toFixed(3));
      this.gambarKotak(); this.kirimKotak();
    }, true);
    window.addEventListener('mouseup', e => {
      if (!this._seret) return;
      e.stopPropagation();
      this._seret = null; gl.style.cursor = '';
      this.kirimKotak(true);
    }, true);
    gl.addEventListener('wheel', e => {
      if (!(e.shiftKey || e.altKey) || !aktif()) return;
      e.stopPropagation(); e.preventDefault();
      const arah = (e.deltaY || e.deltaX) < 0 ? 1 : -1;
      if (e.altKey) this.kotak.s[this.sumbu] = Math.max(2, Math.min(126, this.kotak.s[this.sumbu] + arah));
      else this.kotak.s = this.kotak.s.map(v => Math.max(2, Math.min(126, v + arah)));
      this.gambarKotak(); this.kirimKotak(true);
    }, {capture: true, passive: false});
    window.addEventListener('keydown', e => {
      const i = {x: 0, y: 1, z: 2}[e.key.toLowerCase()];
      if (i !== undefined && aktif()) { this.sumbu = i; this.info(`Sumbu ${'XYZ'[i]} dipilih: Alt + gulir mengubah ukuran ${'XYZ'[i]}`); }
    });
  },
  /* geser layar (piksel CSS) -> vektor model, diuji agar kotak mengikuti kursor */
  offsetModel(dx, dy) {
    const c = this.kotak.c, p0 = this.v.modelToScreen({x: c[0], y: c[1], z: c[2]});
    const e = this.v.screenOffsetToModel(1, 0), f = this.v.screenOffsetToModel(0, 1);
    // ukur skala piksel per satuan vektor basis lalu selesaikan 2x2
    const px = this.v.modelToScreen({x: c[0] + e.x, y: c[1] + e.y, z: c[2] + e.z});
    const py = this.v.modelToScreen({x: c[0] + f.x, y: c[1] + f.y, z: c[2] + f.z});
    const a = px.x - p0.x, b = py.x - p0.x, cc = px.y - p0.y, d = py.y - p0.y, det = a * d - b * cc;
    if (Math.abs(det) < 1e-9) return [0, 0, 0];
    const u = (d * dx - b * dy) / det, w = (-cc * dx + a * dy) / det;
    return [u * e.x + w * f.x, u * e.y + w * f.y, u * e.z + w * f.z];
  },
  kirimKotak(segera) {
    clearTimeout(this._kirim);
    const kirim = () => this.py && this.py.kotak(JSON.stringify({pusat: this.kotak.c, ukuran: this.kotak.s}));
    if (segera) kirim(); else this._kirim = setTimeout(kirim, 100);
  },
  info(t) {
    const el = document.getElementById('info');
    if (!el) return;
    el.textContent = t; el.style.display = 'block';
    clearTimeout(this._info); this._info = setTimeout(() => { el.style.display = 'none'; }, 2200);
  },
  box(c, s, tampil, warna) {
    this.kotak = {c: c ? c.slice() : null, s: s ? s.slice() : null, tampil: !!tampil, warna};
    this.gambarKotak();
  },
  gambarKotak() {
    const {c, s, tampil, warna} = this.kotak || {};
    this.clearShapes('box');
    if (tampil && c && s) {
      const w = warna || '#1f5fbf';
      const h = s.map(u => u / 2), k = [];
      this.shapes.box.push(this.v.addBox({center: {x: c[0], y: c[1], z: c[2]}, dimensions: {w: s[0], h: s[1], d: s[2]}, color: w, alpha: 0.07}));
      for (const dx of [-1, 1]) for (const dy of [-1, 1]) for (const dz of [-1, 1]) k.push([c[0] + dx * h[0], c[1] + dy * h[1], c[2] + dz * h[2]]);
      for (let a = 0; a < 8; a++) for (let b = a + 1; b < 8; b++) if ([0, 1, 2].filter(n => k[a][n] !== k[b][n]).length === 1)
        this.shapes.box.push(this.v.addCylinder({start: this.xyz(k[a]), end: this.xyz(k[b]), radius: 0.06, color: w, fromCap: 1, toCap: 1}));
      k.forEach(p => this.shapes.box.push(this.v.addSphere({center: this.xyz(p), radius: 0.3, color: w})));
      this.shapes.box.push(this.v.addSphere({center: this.xyz(c), radius: 0.25, color: w, alpha: 0.8}));
    }
    this.v.render();
  },
  xyz(p) { return {x: p[0], y: p[1], z: p[2]}; },
  interaksi(daftar, opsi) {
    this.clearShapes('inter');
    opsi = opsi || {};
    (daftar || []).forEach(i => {
      if (i.jenis === 'vdw') return;
      this.shapes.inter.push(this.v.addCylinder({start: this.xyz(i.l), end: this.xyz(i.p), radius: 0.045, color: i.warna,
        dashed: true, dashLength: 0.18, gapLength: 0.12, fromCap: 1, toCap: 1}));
      if (i.jenis === 'pi' || i.jenis === 'pikation') {
        this.shapes.inter.push(this.v.addSphere({center: this.xyz(i.l), radius: 0.2, color: i.warna, alpha: 0.75}));
        this.shapes.inter.push(this.v.addSphere({center: this.xyz(i.p), radius: 0.2, color: i.warna, alpha: 0.75}));
      }
      if (opsi.jarak !== false && ['hbond', 'garam', 'halogen'].includes(i.jenis)) {
        const mid = {x: (i.l[0] + i.p[0]) / 2, y: (i.l[1] + i.p[1]) / 2, z: (i.l[2] + i.p[2]) / 2};
        this.labels.inter.push(this.v.addLabel(i.jarak.toFixed(2), {position: mid, fontSize: 10, fontColor: i.warna, font: 'Consolas',
          backgroundColor: this.bgc, backgroundOpacity: 0.85, borderThickness: 0, inFront: true, alignment: 'center'}));
      }
    });
    if (opsi.label !== false) {
      const sudah = new Set();
      (daftar || []).filter(i => i.jenis !== 'vdw').forEach(i => {
        if (sudah.has(i.residu)) return; sudah.add(i.residu);
        this.labels.inter.push(this.v.addLabel(i.resn + ' ' + i.resi, {position: this.xyz(i.p), fontSize: 11, font: 'Segoe UI',
          fontColor: this.dark ? '#dfe5ee' : '#1b2430', backgroundColor: this.dark ? '#1d2128' : '#ffffff', backgroundOpacity: 0.9,
          borderColor: this.dark ? '#2d333d' : '#c9d1dc', borderThickness: 1, inFront: true, alignment: 'bottomCenter'}));
      });
    }
    this.v.render();
  },
  sorot(id, sel) {
    this.clearShapes('sel');
    const o = this.models[id];
    if (o && sel) {
      const atoms = o.m.selectedAtoms(sel);
      atoms.forEach(a => this.shapes.sel.push(this.v.addSphere({center: {x: a.x, y: a.y, z: a.z}, radius: 0.55, color: '#2b6fd6', alpha: 0.28})));
    }
    this.v.render();
  },

  /* ------------------------------------------------------ interaksi mouse */
  setMode(m) { this.mode = m; this.ukurAtom = []; },
  klik(id, atom) {
    const info = {id, chain: atom.chain, resi: atom.resi, resn: atom.resn, atom: atom.atom, elem: atom.elem,
      x: atom.x, y: atom.y, z: atom.z, serial: atom.serial, hetflag: atom.hetflag};
    if (this.mode === 'ukur') {
      this.ukurAtom.push(info);
      this.shapes.ukur.push(this.v.addSphere({center: atom, radius: 0.35, color: '#c98a12', alpha: 0.6}));
      if (this.ukurAtom.length === 2) {
        const [a, b] = this.ukurAtom;
        const d = Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
        this.shapes.ukur.push(this.v.addCylinder({start: a, end: b, radius: 0.04, color: '#c98a12', dashed: true, dashLength: 0.2, gapLength: 0.12}));
        this.labels.ukur.push(this.v.addLabel(d.toFixed(2) + ' Å', {position: {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2},
          fontSize: 11, font: 'Consolas', fontColor: '#7a5200', backgroundColor: '#fff6df', borderThickness: 0, inFront: true}));
        this.py && this.py.ukur(JSON.stringify({a, b, d}));
        this.ukurAtom = [];
      }
      this.v.render();
      return;
    }
    this.py && this.py.dipilih(JSON.stringify(info));
  },
  hapusUkur() { this.clearShapes('ukur'); this.ukurAtom = []; this.v.render(); },

  /* ----------------------------------------------------------- lain */
  tema(dark, bg) {
    this.dark = dark; this.bgc = bg;
    document.body.style.background = bg;
    this.v.setBackgroundColor(bg);
    const tip = document.getElementById('tip');
    tip.style.background = dark ? '#1d2128' : '#ffffff';
    tip.style.color = dark ? '#e2e6ed' : '#1b2430';
    tip.style.border = '1px solid ' + (dark ? '#2d333d' : '#d3d9e1');
    this.v.render();
  },
  spin(on) { this.v.spin(on ? 'y' : false); },
  png() { return this.v.pngURI(); },
  /* Gambar resolusi tinggi: kanvas dibuat lebar x tinggi piksel dengan menaikkan devicePixelRatio sementara,
     sehingga garis & label ikut berskala (tidak mengecil). Mengembalikan data URL PNG. */
  gambar(lebar, tinggi, transparan, latar) {
    const gl = document.getElementById('gl');
    const r = gl.getBoundingClientRect();
    const cssW = r.width, cssH = Math.max(1, Math.round(cssW * tinggi / lebar));
    const asli = Object.getOwnPropertyDescriptor(window, 'devicePixelRatio');
    const rasio = lebar / cssW;
    const pandang = this.v.getView();
    try {
      gl.style.right = 'auto'; gl.style.bottom = 'auto';
      gl.style.width = cssW + 'px'; gl.style.height = cssH + 'px';
      Object.defineProperty(window, 'devicePixelRatio', {get: () => rasio, configurable: true});
      if (transparan) this.v.setBackgroundColor(latar || this.bgc, 0);
      else if (latar) this.v.setBackgroundColor(latar, 1);
      this.v.resize(); this.v.setView(pandang); this.v.render();
      return this.v.pngURI();
    } finally {
      if (asli) Object.defineProperty(window, 'devicePixelRatio', asli); else delete window.devicePixelRatio;
      gl.style.width = ''; gl.style.height = ''; gl.style.right = ''; gl.style.bottom = '';
      this.v.setBackgroundColor(this.bgc, 1);
      this.v.resize(); this.v.setView(pandang); this.v.render();
    }
  },
  /* residu kontak sebagai stick (karbon abu-abu) di atas gaya objek reseptor */
  residuKontak(id, sel) {
    const o = this.models[id];
    if (!o) return;
    if (o.spec) this.tampil(id, o.spec);
    if (sel && o.spec && o.spec.visible !== false) {
      this.v.addStyle(Object.assign({model: o.m}, sel), {stick: Object.assign({radius: 0.14}, this.warna({mode: 'element', carbon: '#9aa3b2'}))});
      this.v.render();
    }
  },
  lihat() { return this.v.getView(); },
  zoom(f) { this.v.zoom(f); this.v.render(); },
  aturLihat(v) { if (v) { this.v.setView(v); this.v.render(); } },
  gizmo() {
    const cv = document.getElementById('gizmo'), g = cv.getContext('2d');
    g.clearRect(0, 0, 64, 64);
    if (!this.v) return;
    const q = this.v.getView().slice(4, 8); // x,y,z,w
    const [x, y, z, w] = q;
    const R = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]];
    const ax = [['x', '#cf3f3f', 0], ['y', '#2e9e5b', 1], ['z', '#2b6fd6', 2]]
      .map(([n, c, i]) => ({n, c, x: R[0][i], y: R[1][i], z: R[2][i]})).sort((a, b) => a.z - b.z);
    g.lineWidth = 1.8; g.font = '10px Segoe UI';
    ax.forEach(a => {
      g.strokeStyle = a.c; g.fillStyle = a.c;
      g.beginPath(); g.moveTo(32, 32); g.lineTo(32 + a.x * 22, 32 - a.y * 22); g.stroke();
      g.fillText(a.n, 32 + a.x * 27 - 3, 32 - a.y * 27 + 4);
    });
  },
};

VM.init();
if (window.qt && window.QWebChannel) {
  new QWebChannel(qt.webChannelTransport, ch => { VM.py = ch.objects.py; VM.py.siap(); });
}
