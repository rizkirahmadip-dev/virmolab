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
  v: null, py: null, models: {}, shapes: {box: [], inter: [], ukur: [], sel: [], kontrib: [], kantong: [], farma: [], syarat: [], terowongan: []}, labels: {inter: [], ukur: [], res: [], kontrib: [], kantong: [], farma: [], syarat: []},
  bgc: '#ffffff', mode: 'putar', ukurAtom: [], dark: false, idSeret: {}, _tarik: null,

  init() {
    this.v = $3Dmol.createViewer(document.getElementById('gl'), {backgroundColor: 'white', antialias: true, cartoonQuality: 10});
    // Kabut kedalaman 3Dmol bawaan mulai di 40% kedalaman -> separuh belakang molekul memudar ke warna latar (tampak pucat).
    // Bawaan VirmoDock 'halus' (75%); bisa diubah lewat gayaRender (menu Render).
    this.v.fogStart = 0.75;
    this.v.setViewChangeCallback && this.v.setViewChangeCallback(() => { this.gizmo(); this.jadwalRapikan(); });
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
    // Tata letak Qt bisa mengubah ukuran wadah tanpa peristiwa resize jendela (tab/dock berganti).
    // Resize hanya bila ukuran #gl benar-benar berubah, dan ditunda ke frame berikutnya: tanpa pengaman ini
    // v.resize() mengubah kanvas -> ResizeObserver terpicu lagi -> loop tak berujung (JS sibuk terus,
    // kamera tergeser/kanvas kosong) pada ukuran jendela/DPI tertentu.
    const gl = document.getElementById('gl');
    let ukLama = '';
    const ukur = () => {
      cancelAnimationFrame(this._rafUkur);
      this._rafUkur = requestAnimationFrame(() => {
        const r = gl.getBoundingClientRect();
        const k = Math.round(r.width) + 'x' + Math.round(r.height);
        if (k === ukLama || r.width < 2 || r.height < 2) return;
        ukLama = k;
        this.v.resize(); this.v.render();
      });
    };
    window.addEventListener('resize', ukur);
    new ResizeObserver(ukur).observe(gl);
    this.pasangKotak();
    this.pasangSeret();
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
  clear() { Object.keys(this.models).forEach(id => this.remove(id)); this.clearShapes('box'); this.clearShapes('inter'); this.clearShapes('ukur'); this.clearShapes('sel'); this.clearShapes('farma'); this.clearShapes('syarat'); this.clearShapes('terowongan'); this.v.render(); },

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
    // pLDDT AlphaFold (kolom B): pita warna resmi AlphaFold DB
    if (mode === 'plddt') return {colorfunc: a => a.b > 90 ? '#0053D6' : a.b > 70 ? '#65CBF3' : a.b > 50 ? '#FFDB13' : '#FF7D45'};
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
  /* Jalankan fn hanya bila kanvas sudah berukuran nyata. Saat wadah baru muncul (halaman sambutan -> viewer,
     tab berganti) ukurannya bisa 0: resize/zoomTo 3Dmol dengan rasio NaN macet tanpa akhir dan membekukan
     seluruh halaman. Ditunggu per frame (maks. ± 3 s). */
  _bilaSiap(fn, coba) {
    const r = document.getElementById('gl').getBoundingClientRect();
    if (r.width >= 2 && r.height >= 2) { fn(); return; }
    if ((coba || 0) < 180) requestAnimationFrame(() => this._bilaSiap(fn, (coba || 0) + 1));
  },
  fokus(sel, ms) {
    this._bilaSiap(() => {
      const s = Object.assign({}, sel || {});
      if (s.id !== undefined) { const o = this.models[s.id]; delete s.id; if (o) s.model = o.m; }
      this.v.zoomTo(s, ms ?? 400);
    });
  },
  fokusTitik(pt, ms) {
    this._bilaSiap(() => {
      if (pt) {
        this.v.center(pt);
        this.v.zoom(1.2, ms ?? 400);
        this.v.render();
      }
    });
  },
  // hanya objek yang terlihat: objek tersembunyi (mis. ligan SMILES di titik asal) tidak boleh menggeser kamera
  _terlihat() {
    const m = Object.values(this.models).filter(o => !o.spec || o.spec.visible !== false).map(o => o.m);
    // catatan: {model: [m1, m2]} membuat zoomTo 3Dmol macet tanpa akhir (halaman beku) -> pakai 'or'
    if (!m.length) return {};
    return m.length === 1 ? {model: m[0]} : {or: m.map(x => ({model: x}))};
  },
  fokusSemua() { this._bilaSiap(() => this.v.zoomTo(this._terlihat(), 400)); },
  segarkanKanvas() { this._bilaSiap(() => { this.v.resize(); this.v.render(); }); },   // tab viewport tampil lagi
  ukurUlang() { this._bilaSiap(() => { this.v.resize(); this.v.zoomTo(this._terlihat()); this.v.render(); }); },

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
  geserDari(asal, dx, dy) {
    if (!this.v || !asal) return [0, 0, 0];
    const p0 = this.v.modelToScreen(asal);
    const e = this.v.screenOffsetToModel(1, 0), f = this.v.screenOffsetToModel(0, 1);
    if (!p0 || !e || !f) return [0, 0, 0];
    const px = this.v.modelToScreen({x: asal.x + e.x, y: asal.y + e.y, z: asal.z + e.z});
    const py = this.v.modelToScreen({x: asal.x + f.x, y: asal.y + f.y, z: asal.z + f.z});
    const a = px.x - p0.x, b = py.x - p0.x, cc = px.y - p0.y, d = py.y - p0.y, det = a * d - b * cc;
    if (Math.abs(det) < 1e-9) return [0, 0, 0];
    const u = (d * dx - b * dy) / det, w = (-cc * dx + a * dy) / det;
    return [u * e.x + w * f.x, u * e.y + w * f.y, u * e.z + w * f.z];
  },
  offsetModel(dx, dy) {
    const c = this.kotak && this.kotak.c;
    if (!c) return [0, 0, 0];
    return this.geserDari({x: c[0], y: c[1], z: c[2]}, dx, dy);
  },
  pasangSeret() {
    const gl = document.getElementById('gl');
    const lokal = (ev) => {
      const r = gl.getBoundingClientRect();
      return {x: ev.clientX - r.left, y: ev.clientY - r.top};
    };
    const terdekat = (sx, sy) => {
      let terbaik = null, jarak = 14;
      Object.keys(this.models).forEach(id => {
        if (!this.idSeret[id]) return;
        this.models[id].m.selectedAtoms({}).forEach(atom => {
          if (!atom || atom.elem === 'H') return;
          const p = this.v.modelToScreen(atom);
          if (!p) return;
          const d = Math.hypot(p.x - sx, p.y - sy);
          if (d < jarak) { jarak = d; terbaik = {id, atom}; }
        });
      });
      return terbaik;
    };
    gl.addEventListener('pointerdown', (ev) => {
      if ((this.mode !== 'seret' && this.mode !== 'geser') || ev.button !== 0) return;
      const p = lokal(ev);
      const t = terdekat(p.x, p.y);
      if (!t) return;
      ev.stopPropagation();
      ev.preventDefault();
      const utuh = this.mode === 'geser';
      const asal = utuh ? this.models[t.id].m.selectedAtoms({}).map(atom => (
        {atom, x: atom.x, y: atom.y, z: atom.z})) : null;
      this._tarik = {id: t.id, atom: t.atom, ox: t.atom.x, oy: t.atom.y, oz: t.atom.z,
        elem: t.atom.elem, sx: p.x, sy: p.y, utuh, asal};
      gl.style.cursor = 'grabbing';
    }, true);
    gl.addEventListener('pointermove', (ev) => {
      if (!this._tarik) return;
      ev.stopPropagation();
      ev.preventDefault();
      const p = lokal(ev);
      const a = this._tarik;
      const d = this.geserDari({x: a.ox, y: a.oy, z: a.oz}, p.x - a.sx, p.y - a.sy);
      if (a.utuh) {
        a.asal.forEach(s => { s.atom.x = s.x + d[0]; s.atom.y = s.y + d[1]; s.atom.z = s.z + d[2]; });
      } else {
        a.atom.x = a.ox + d[0];
        a.atom.y = a.oy + d[1];
        a.atom.z = a.oz + d[2];
      }
      this.v.render();
    }, true);
    const lepas = (ev) => {
      if (!this._tarik) return;
      if (ev) { ev.stopPropagation(); ev.preventDefault(); }
      const a = this._tarik;
      this._tarik = null;
      gl.style.cursor = '';
      const dx = a.atom.x - a.ox, dy = a.atom.y - a.oy, dz = a.atom.z - a.oz;
      if (Math.hypot(dx, dy, dz) < 0.08 || !this.py) return;
      const muatan = a.utuh
        ? {id: a.id, utuh: true, dx, dy, dz}
        : {id: a.id, elem: a.elem, x: a.atom.x, y: a.atom.y, z: a.atom.z, ox: a.ox, oy: a.oy, oz: a.oz};
      this.py.seret(JSON.stringify(muatan));
    };
    gl.addEventListener('pointerup', lepas, true);
    gl.addEventListener('pointercancel', lepas, true);
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
      this.shapes.box.push(this.v.addSphere({center: this.xyz(c), radius: 0.25, color: w}));
    }
    this.v.render();
  },
  xyz(p) { return {x: p[0], y: p[1], z: p[2]}; },
  /* kontribusi energi per atom: atom ligan (objek id) diwarnai hijau (menguntungkan) - putih - merah (merugikan),
     bola makin besar bila |E| makin besar. Bentuk transparan 3Dmol tidak tergambar di sini, jadi semuanya buram.
     daftar kosong = kembalikan gaya objek semula. */
  /* pusat kantong P2Rank: bola buram oranye + nomor peringkat */
  kantong(daftar) {
    this.clearShapes('kantong');
    (daftar || []).forEach(k => {
      this.shapes.kantong.push(this.v.addSphere({center: this.xyz(k.pusat), radius: k.nomor === 1 ? 1.2 : 0.9,
        color: k.nomor === 1 ? '#e67e22' : '#f0b26b'}));
      this.labels.kantong.push(this.v.addLabel('#' + k.nomor, {position: this.xyz(k.pusat), fontSize: 12,
        fontColor: '#7a3d00', backgroundColor: '#ffffff', backgroundOpacity: 0.85, borderThickness: 0, inFront: true,
        alignment: 'center'}));
    });
    this.v.render();
  },
  /* jalur terowongan: bola sepanjang garis tengah (jari-jari ∝ celah bebas, 0,25–1,4 Å; bentuk transparan tidak tergambar);
     titik tersempit diberi warna tegas. daftar kosong = hapus. */
  terowongan(daftar) {
    this.clearShapes('terowongan');
    (daftar || []).forEach(t => {
      const r = t.radius || [];
      const iMin = r.length ? r.indexOf(Math.min.apply(null, r)) : -1;
      (t.titik || []).forEach((p, i) => {
        this.shapes.terowongan.push(this.v.addSphere({center: this.xyz(p),
          radius: Math.max(0.25, Math.min(1.4, 0.6 * (r[i] || 1))), color: i === iMin ? (t.leher || '#c0392b') : t.warna}));
      });
    });
    this.v.render();
  },
  /* farmakofor: bola kerangka berwarna per fitur (bentuk transparan 3Dmol tidak tergambar di sini) + titik pusat
     buram kecil; label opsional (nama fitur / frekuensi). daftar kosong = hapus. */
  farmakofor(daftar, opsi) {
    this.clearShapes('farma');
    opsi = opsi || {};
    (daftar || []).forEach(f => {
      const c = this.xyz(f.xyz);
      this.shapes.farma.push(this.v.addSphere({center: c, radius: f.radius, color: f.warna, wireframe: true,
        linewidth: 1.2}));
      this.shapes.farma.push(this.v.addSphere({center: c, radius: 0.16, color: f.warna}));
      if (opsi.label)
        this.labels.farma.push(this.v.addLabel(f.label || f.nama, {position: c, fontSize: 10, font: 'Segoe UI',
          berat: 600, fontColor: f.warna, backgroundColor: this.bgc, backgroundOpacity: 0.85, borderColor: f.warna,
          borderOpacity: 0.4, borderThickness: 1, bayang: false, padX: 4, padY: 0.5, inFront: true,
          alignment: 'bottomCenter'}));
    });
    this.v.render();
    return (daftar || []).length;
  },
  _kontribId: null,
  kontribusi(id, daftar, opsi) {
    this.clearShapes('kontrib');
    if (this._kontribId && this.models[this._kontribId]) {
      const lama = this.models[this._kontribId];
      if (lama.spec) this.tampil(this._kontribId, lama.spec);
    }
    this._kontribId = null;
    const o = this.models[id];
    if (!o || !daftar || !daftar.length) { this.v.render(); return 0; }
    opsi = opsi || {};
    const maks = Math.max(0.3, ...daftar.map(a => Math.abs(a.energi)));
    const campur = (h, f) => {
      const c = [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
      return '#' + c.map(x => Math.round(245 + (x - 245) * f).toString(16).padStart(2, '0')).join('');
    };
    const atoms = o.m.selectedAtoms({});
    let n = 0;
    o.m.setStyle({}, {stick: {radius: 0.12, color: '#c9ced6'}});
    atoms.forEach(at => {
      let best = null, dmin = 0.25;
      daftar.forEach(a => {
        const d = Math.hypot(at.x - a.xyz[0], at.y - a.xyz[1], at.z - a.xyz[2]);
        if (d < dmin) { dmin = d; best = a; }
      });
      if (!best) { if (at.elem === 'H') o.m.setStyle({index: at.index}, {}); return; }
      n++;
      const f = Math.min(1, Math.abs(best.energi) / maks);
      const w = campur(best.energi < 0 ? '#1f8a4c' : '#c62828', 0.15 + 0.85 * f);
      o.m.setStyle({index: at.index}, {stick: {radius: 0.14, color: w}, sphere: {radius: 0.2 + 0.42 * f, color: w}});
      if (opsi.label && f > 0.6)
        this.labels.kontrib.push(this.v.addLabel(best.energi.toFixed(2), {position: {x: at.x, y: at.y, z: at.z},
          fontSize: 9, fontColor: best.energi < 0 ? '#14532d' : '#7f1d1d', backgroundColor: '#ffffff',
          backgroundOpacity: 0.75, borderThickness: 0, inFront: true, alignment: 'center', font: 'Consolas'}));
    });
    this._kontribId = id;
    this.v.render();
    return n;
  },
  interaksi(daftar, opsi) {
    this.clearShapes('inter');
    this._inter = daftar || [];   // dipakai presentasi sinematik
    opsi = opsi || {};
    (daftar || []).forEach(i => {
      if (i.jenis === 'vdw') return;
      this.shapes.inter.push(this.v.addCylinder({start: this.xyz(i.l), end: this.xyz(i.p), radius: 0.045, color: i.warna,
        dashed: true, dashLength: 0.18, gapLength: 0.12, fromCap: 1, toCap: 1}));
      if (i.jenis === 'pi' || i.jenis === 'pikation') {
        this.shapes.inter.push(this.v.addSphere({center: this.xyz(i.l), radius: 0.2, color: i.warna}));
        this.shapes.inter.push(this.v.addSphere({center: this.xyz(i.p), radius: 0.2, color: i.warna}));
      }
      if (opsi.jarak !== false && ['hbond', 'garam', 'halogen'].includes(i.jenis)) {
        const mid = {x: (i.l[0] + i.p[0]) / 2, y: (i.l[1] + i.p[1]) / 2, z: (i.l[2] + i.p[2]) / 2};
        this.labels.inter.push(this.v.addLabel(i.jarak.toFixed(2).replace('.', ','), {position: mid, fontSize: 10,
          font: 'Segoe UI', berat: 600, fontColor: i.warna, backgroundColor: this.bgc, backgroundOpacity: 0.9,
          borderColor: i.warna, borderOpacity: 0.45, borderThickness: 1, bayang: false, padX: 4, padY: 0.5,
          inFront: true, alignment: 'center'}));
      }
    });
    if (opsi.label !== false) {
      const sudah = new Set();
      (daftar || []).filter(i => i.jenis !== 'vdw').forEach(i => {
        if (sudah.has(i.residu)) return; sudah.add(i.residu);
        this.labels.inter.push(this.v.addLabel(i.resn + ' ' + i.resi, {position: this.xyz(i.p), fontSize: 11.5,
          font: 'Segoe UI', vmGaya: 'residu', aksen: i.warna,
          fontColor: this.dark ? '#eef2f7' : '#142033', warna2: this.dark ? '#9fb0c6' : '#5b6b82',
          backgroundColor: this.dark ? '#1b2029' : '#ffffff', backgroundOpacity: this.dark ? 0.9 : 0.94,
          borderColor: this.dark ? '#3a4352' : '#d5dce6', borderThickness: 1, inFront: true, alignment: 'bottomCenter'}));
      });
    }
    this.v.render();
  },
  sorot(id, sel) {
    this.clearShapes('sel');
    const o = this.models[id];
    if (o && sel) {
      const atoms = o.m.selectedAtoms(sel);
      atoms.forEach(a => this.shapes.sel.push(this.v.addSphere({center: {x: a.x, y: a.y, z: a.z}, radius: 0.5, color: '#2b6fd6', wireframe: true, linewidth: 1})));  // transparan tak tergambar -> kerangka
    }
    this.v.render();
  },

  /* ------------------------------------------------------ interaksi mouse */
  setMode(m) { this.mode = m; this.ukurAtom = []; this._tarik = null; },
  aturSeret(ids) {
    this.idSeret = {};
    (ids || []).forEach(id => { this.idSeret[id] = true; });
  },
  klik(id, atom) {
    if (this.mode === 'seret' || this.mode === 'geser') return;
    const info = {id, chain: atom.chain, resi: atom.resi, resn: atom.resn, atom: atom.atom, elem: atom.elem,
      x: atom.x, y: atom.y, z: atom.z, serial: atom.serial, hetflag: atom.hetflag};
    if (this.mode === 'ukur') {
      this.ukurAtom.push(info);
      this.shapes.ukur.push(this.v.addSphere({center: atom, radius: 0.3, color: '#c98a12'}));
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
  garisSyarat(info) {
    this.clearShapes('syarat');
    if (!info || !info.ligan || !info.protein) { this.v.render(); return; }
    const a = this.xyz(info.ligan), b = this.xyz(info.protein);
    const warna = info.lolos ? '#1f8a4c' : '#c62828';
    this.shapes.syarat.push(this.v.addCylinder({start: a, end: b, radius: 0.05, color: warna,
      dashed: true, dashLength: 0.18, gapLength: 0.12, fromCap: 1, toCap: 1}));
    this.shapes.syarat.push(this.v.addSphere({center: a, radius: 0.22, color: warna}));
    this.shapes.syarat.push(this.v.addSphere({center: b, radius: 0.22, color: warna}));
    const mid = {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2};
    const nama = (info.atom_ligan || 'ligan') + ' – ' + [info.resn, info.resi, info.rantai].filter(Boolean).join(' ')
      + ' ' + (info.atom_residu || '');
    const angka = (typeof info.min === 'number') ? info.min.toFixed(2).replace('.', ',') + ' Å' : '';
    this.labels.syarat.push(this.v.addLabel((nama + '  ' + angka).trim(), {position: mid, fontSize: 11,
      font: 'Segoe UI', fontColor: warna, backgroundColor: this.bgc, backgroundOpacity: 0.92,
      borderThickness: 0, inFront: true, alignment: 'center'}));
    this.v.render();
  },

  /* ----------------------------------------------------------- lain */
  tema(dark, bg) {
    this.dark = dark; this.bgc = bg;
    if (this._render) this.gayaRender(this._render);
    document.body.style.background = bg;
    this.v.setBackgroundColor(bg);
    const tip = document.getElementById('tip');
    tip.style.background = dark ? '#1d2128' : '#ffffff';
    tip.style.color = dark ? '#e2e6ed' : '#1b2430';
    tip.style.border = '1px solid ' + (dark ? '#2d333d' : '#d3d9e1');
    this.v.render();
  },
  spin(on) { this.v.spin(on ? 'y' : false); },
  /* posisi label disusun ulang (anti-tabrakan) setelah pandangan berubah — ditunda ke frame berikutnya */
  rapikanLabel(render) {
    // render ulang hanya bila ada label yang bergeser: render memicu viewChangeCallback -> tanpa ini loop tiap frame
    const berubah = LabelVM.rapikan(this.v, [].concat(this.labels.inter, this.labels.ukur, this.labels.kantong,
                                                     this.labels.kontrib, this.labels.syarat));
    if (berubah && render !== false) this.v.render();
  },
  jadwalRapikan() {
    if (this._rafLabel) return;
    this._rafLabel = requestAnimationFrame(() => { this._rafLabel = 0; this.rapikanLabel(); });
  },
  /* Gaya render (bawaan 3Dmol; ikut ekspor gambar & video):
     tepi  -> garis tepi gelap tipis ala ilustrasi jurnal (setViewStyle outline)
     ao    -> ambient occlusion: bayangan di celah & kantong
     kabut -> 'mati' | 'halus' (mulai 75% kedalaman) | 'kuat' (bawaan 3Dmol, 40%) */
  gayaRender(o) {
    this._render = o = Object.assign({tepi: true, ao: false, kabut: 'halus'}, o || {});
    const s = [];
    if (o.tepi) s.push('outline');
    if (o.ao) s.push('ambientOcclusion');
    this.v.setViewStyle({style: s.join(' '), color: this.dark ? '#05070a' : '#16202e', width: 0.055,
                         strength: 1.0, radius: 5});
    this.v.getConfig().disableFog = o.kabut === 'mati';
    this.v.fogStart = o.kabut === 'kuat' ? 0.4 : 0.75;
    this.v.render();
    return true;
  },
  /* PDB multi-MODEL (trajektori) diputar di viewport. */
  film(id, teks) {
    this.filmStop();
    this.remove(id);
    const m = this.v.addModelsAsFrames(teks, 'pdb');
    this.models[id] = {m, surf: [], spec: null};
    const n = (m.getNumFrames && m.getNumFrames()) || 1;
    this.v.zoomTo({model: m});
    let f = 0;
    this._filmTimer = setInterval(() => {
      f = (f + 1) % n;
      this.v.setFrame(f);
      this.v.render();
    }, 140);
    this.v.render();
    return n;
  },
  filmStop() {
    if (this._filmTimer) { clearInterval(this._filmTimer); this._filmTimer = null; }
  },
  /* Animasi untuk ekspor GIF/WebP: kanvas diset lebar x tinggi (seperti gambar()), lalu animBingkai(t) dengan
     t = 0..1 memutar/menggoyang pandangan awal atau beralih mulus dari seluruh protein ke pandangan sekarang. */
  animMulai(lebar, tinggi, latar, mode, sudut) {
    const gl = document.getElementById('gl');
    const r = gl.getBoundingClientRect();
    const cssW = r.width, cssH = Math.max(1, Math.round(cssW * tinggi / lebar));
    this.v.spin(false);
    const a = {asli: Object.getOwnPropertyDescriptor(window, 'devicePixelRatio'), pandang: this.v.getView(),
               mode, sudut: sudut || 360};
    this._anim = a;
    if (mode === 'zoom') { this.v.zoomTo(); a.awal = this.v.getView(); this.v.setView(a.pandang); }
    if (mode === 'sinema') a.seg = this._linimasaSinema(a.pandang);
    gl.style.right = 'auto'; gl.style.bottom = 'auto';
    gl.style.width = cssW + 'px'; gl.style.height = cssH + 'px';
    Object.defineProperty(window, 'devicePixelRatio', {get: () => lebar / cssW, configurable: true});
    this.v.setBackgroundColor(latar || this.bgc, 1);
    this.v.resize(); LabelVM.segarkan(this.v); this.rapikanLabel(false); this.v.setView(a.pandang);
    return true;
  },
  /* interpolasi pandangan 3Dmol [pos x,y,z, zoom, kuaternion x,y,z,w]: linear + slerp kuaternion */
  _antara(p, q, e) {
    const v = p.map((x, i) => x + (q[i] - x) * e);
    let d = p[4] * q[4] + p[5] * q[5] + p[6] * q[6] + p[7] * q[7], q2 = q.slice(4, 8);
    if (d < 0) { d = -d; q2 = q2.map(x => -x); }
    if (d < 0.9995) {
      const th = Math.acos(d), s = Math.sin(th), w1 = Math.sin((1 - e) * th) / s, w2 = Math.sin(e * th) / s;
      for (let i = 0; i < 4; i++) v[4 + i] = w1 * p[4 + i] + w2 * q2[i];
    }
    return v;
  },
  _mulus(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; },   // ease-in-out kubik
  /* Presentasi sinematik: seluruh protein -> zoom ke situs -> putar 360° pelan -> sorot tiap interaksi penting
     (maks. 4 residu: ikatan H, jembatan garam, π, halogen, logam, lalu hidrofobik) -> kembali. Bobot = durasi relatif. */
  _linimasaSinema(P) {
    const v = this.v, seg = [];
    v.zoomTo(); const semua = v.getView();
    v.setView(P); v.zoom(1.6, 0); const dekat = v.getView(); v.setView(P);
    // slab: bidang potong depan saat menyorot interaksi -> pita protein di depan tidak menghalangi (teknik PyMOL)
    const sl = v.getSlab(), S0 = sl.near, SF = 7;
    seg.push({jenis: 'pindah', dari: semua, ke: P, bobot: 3.2, s0: S0, s1: S0});
    seg.push({jenis: 'diam', di: P, bobot: 0.6, s0: S0, s1: S0});
    seg.push({jenis: 'putar', di: P, bobot: 7, s0: S0, s1: S0});
    const urut = ['hbond', 'garam', 'pikation', 'pi', 'halogen', 'logam', 'hidrofobik'];
    const sudah = new Set(), fokus = [];
    (this._inter || []).filter(h => urut.includes(h.jenis))
      .sort((x, y) => urut.indexOf(x.jenis) - urut.indexOf(y.jenis) || (x.jarak || 9) - (y.jarak || 9))
      .forEach(h => { if (!sudah.has(h.residu) && fokus.length < 4) { sudah.add(h.residu); fokus.push(h); } });
    let lalu = P;
    for (const h of fokus) {
      const m = [0, 1, 2].map(k => (h.l[k] + h.p[k]) / 2);
      const V = dekat.slice();
      V[0] = -m[0]; V[1] = -m[1]; V[2] = -m[2];
      seg.push({jenis: 'pindah', dari: lalu, ke: V, bobot: 1.7, s0: lalu === P ? S0 : -SF, s1: -SF});
      seg.push({jenis: 'diam', di: V, bobot: 1.5, s0: -SF, s1: -SF});
      lalu = V;
    }
    if (fokus.length) seg.push({jenis: 'pindah', dari: lalu, ke: P, bobot: 1.8, s0: -SF, s1: S0});
    seg.push({jenis: 'diam', di: P, bobot: 0.6, s0: S0, s1: S0});
    this._anim.slabAsli = [sl.near, sl.far];
    const total = seg.reduce((s, x) => s + x.bobot, 0);
    let acc = 0;
    seg.forEach(x => { x.t0 = acc / total; acc += x.bobot; x.t1 = acc / total; });
    return seg;
  },
  animBingkai(t, jpeg) {
    const a = this._anim;
    if (!a) return '';
    if (a.mode === 'zoom') {
      this.v.setView(this._antara(a.awal, a.pandang, this._mulus(t)));
    } else if (a.mode === 'sinema') {
      const x = a.seg.find(s => t <= s.t1 + 1e-9) || a.seg[a.seg.length - 1];
      const u = Math.min(1, Math.max(0, (t - x.t0) / Math.max(1e-9, x.t1 - x.t0)));
      this.v.setSlab(x.s0 + (x.s1 - x.s0) * this._mulus(u), this._anim.slabAsli[1]);
      if (x.jenis === 'pindah') this.v.setView(this._antara(x.dari, x.ke, this._mulus(u)));
      else {
        this.v.setView(x.di);
        if (x.jenis === 'putar') this.v.rotate(360 * (0.5 - 0.5 * Math.cos(Math.PI * u)), 'y', 0);
      }
    } else {
      this.v.setView(a.pandang);
      const sudut = a.mode === 'goyang' ? a.sudut * Math.sin(2 * Math.PI * t) : a.sudut * t;
      if (sudut) this.v.rotate(sudut, 'y', 0);
    }
    this.rapikanLabel(false);          // anti-tabrakan label untuk pandangan bingkai ini
    this.v.render();
    return jpeg ? this.v.getCanvas().toDataURL('image/jpeg', 0.97) : this.v.pngURI();
  },
  animSelesai() {
    const a = this._anim, gl = document.getElementById('gl');
    if (!a) return true;
    if (a.asli) Object.defineProperty(window, 'devicePixelRatio', a.asli); else delete window.devicePixelRatio;
    gl.style.width = ''; gl.style.height = ''; gl.style.right = ''; gl.style.bottom = '';
    this.v.setBackgroundColor(this.bgc, 1);
    if (a.slabAsli) this.v.setSlab(a.slabAsli[0], a.slabAsli[1]);
    this.v.resize(); LabelVM.segarkan(this.v); this.rapikanLabel(false); this.v.setView(a.pandang); this.v.render();
    this._anim = null;
    return true;
  },
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
      this.v.resize(); LabelVM.segarkan(this.v); this.rapikanLabel(false); this.v.setView(pandang); this.v.render();
      return this.v.pngURI();
    } finally {
      if (asli) Object.defineProperty(window, 'devicePixelRatio', asli); else delete window.devicePixelRatio;
      gl.style.width = ''; gl.style.height = ''; gl.style.right = ''; gl.style.bottom = '';
      this.v.setBackgroundColor(this.bgc, 1);
      this.v.resize(); LabelVM.segarkan(this.v); this.rapikanLabel(false); this.v.setView(pandang); this.v.render();
    }
  },
  /* Gambar sangat besar (> batas kanvas WebGL): dirender n x n ubin. Tiap ubin = kanvas lebar/n px dengan
     devicePixelRatio sama seperti gambar utuh (garis & label tetap berskala benar), lalu matriks proyeksi
     digeser/diperbesar n kali agar ubin (i, j) menampilkan potongan pandangan yang sama. Disatukan di Python. */
  ubinMulai(lebar, tinggi, n, transparan, latar) {
    const gl = document.getElementById('gl');
    const r = gl.getBoundingClientRect();
    const cssW = r.width, cssH = Math.max(1, cssW * tinggi / lebar);
    this._ubin = {n, rasio: lebar / cssW, pandang: this.v.getView(),
                  asli: Object.getOwnPropertyDescriptor(window, 'devicePixelRatio'), i: 0, j: 0};
    const u = this._ubin, kam = this.v.camera, upm = kam.updateProjectionMatrix;
    u.upm = upm;
    kam.updateProjectionMatrix = function () {
      upm.call(this);
      // P' = M P, M: x' = n x + (n-1-2i) w ; y' = n y - (n-1-2j) w  (elements kolom-mayor)
      const e = this.projectionMatrix.elements, tx = n - 1 - 2 * u.i, ty = -(n - 1 - 2 * u.j);
      for (let c = 0; c < 4; c++) {
        e[c * 4] = n * e[c * 4] + tx * e[c * 4 + 3];
        e[c * 4 + 1] = n * e[c * 4 + 1] + ty * e[c * 4 + 3];
      }
      this.projectionMatrixInverse.getInverse(this.projectionMatrix);
    };
    gl.style.right = 'auto'; gl.style.bottom = 'auto';
    gl.style.width = (cssW / n) + 'px'; gl.style.height = (cssH / n) + 'px';
    Object.defineProperty(window, 'devicePixelRatio', {get: () => u.rasio, configurable: true});
    if (transparan) this.v.setBackgroundColor(latar || this.bgc, 0);
    else if (latar) this.v.setBackgroundColor(latar, 1);
    this.v.resize(); LabelVM.segarkan(this.v); this.rapikanLabel(false); this.v.setView(u.pandang);
    return true;
  },
  ubin(i, j) {
    const u = this._ubin;
    if (!u) return '';
    u.i = i; u.j = j;
    this.v.setView(u.pandang); this.v.render();
    return this.v.pngURI();
  },
  ubinSelesai() {
    const u = this._ubin, gl = document.getElementById('gl');
    if (!u) return true;
    this.v.camera.updateProjectionMatrix = u.upm;
    if (u.asli) Object.defineProperty(window, 'devicePixelRatio', u.asli); else delete window.devicePixelRatio;
    gl.style.width = ''; gl.style.height = ''; gl.style.right = ''; gl.style.bottom = '';
    this.v.setBackgroundColor(this.bgc, 1);
    this.v.resize(); LabelVM.segarkan(this.v); this.rapikanLabel(false); this.v.setView(u.pandang); this.v.render();
    this._ubin = null;
    return true;
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
