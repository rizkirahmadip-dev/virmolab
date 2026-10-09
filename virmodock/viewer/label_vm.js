'use strict';
/* Label 3D VirmoDock: menggantikan gambar label bawaan 3Dmol (kotak polos seukuran huruf CSS yang diregangkan
   di layar HiDPI -> buram). Di sini label digambar sendiri pada resolusi k x (k = rasio piksel kanvas WebGL yang
   sebenarnya, ikut naik saat ekspor/rekam 4K), lalu sprite diperkecil 1/k: ukuran di layar tetap, tajam.

   Desain: pil membulat, bayangan lembut, garis tepi tipis. Gaya tambahan di stylespec (selain opsi 3Dmol):
     vmGaya: 'residu'  -> "VAL 82": nama residu semi-tebal + nomor warna kedua (warna2)
     aksen:  '#rrggbb' -> titik warna di kiri (mis. jenis interaksi terkuat residu tsb.)
     bayang: false     -> tanpa bayangan;  radius, padX, padY (px CSS);  berat (bobot huruf)
   Dipakai juga oleh laporan HTML interaktif (core/laporan_interaktif.py menyisipkan berkas ini). */
const LabelVM = {
  /* rasio piksel kanvas WebGL: 3Dmol menggandakan devicePixelRatio < 2 untuk antialias */
  k() {
    const d = window.devicePixelRatio || 1;
    return Math.min(12, Math.max(2, Math.ceil(d < 2 ? d * 2 : d)));
  },
  rgba(c, a) {
    if (c && typeof c === 'object' && 'r' in c) {     // $3Dmol.Color (0..1) atau {r,g,b} 0..255
      const s = c.r <= 1 && c.g <= 1 && c.b <= 1 ? 255 : 1;
      return `rgba(${Math.round(c.r * s)},${Math.round(c.g * s)},${Math.round(c.b * s)},${a})`;
    }
    let h = String(c || '#ffffff').trim();
    if (/^0x/i.test(h)) h = '#' + h.slice(2);
    if (h[0] !== '#') return h;
    if (h.length === 4) h = '#' + h[1] + h[1] + h[2] + h[2] + h[3] + h[3];
    const n = parseInt(h.slice(1, 7), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  },
  pil(x, X, Y, W, H, r) {
    x.beginPath();
    x.moveTo(X + r, Y); x.lineTo(X + W - r, Y); x.arcTo(X + W, Y, X + W, Y + r, r);
    x.lineTo(X + W, Y + H - r); x.arcTo(X + W, Y + H, X + W - r, Y + H, r);
    x.lineTo(X + r, Y + H); x.arcTo(X, Y + H, X, Y + H - r, r);
    x.lineTo(X, Y + r); x.arcTo(X, Y, X + r, Y, r); x.closePath();
  },
  /* Anti-tabrakan: label diletakkan berurutan (prioritas: jarak & kantong dulu, lalu residu); bila kotaknya
     menimpa label yang sudah diletakkan, dicoba posisi lain di sekitar titik jangkar (atas, bawah, samping,
     diagonal, makin jauh). Posisi dipasang lewat material.screenOffset (satuan piksel tekstur = CSS × k). */
  rapikan(v, daftar) {
    const label = (daftar || []).filter(l => l && l.sprite && l.sprite.visible !== false && l.canvas && l._k);
    if (!label.length) return false;
    let berubah = false;
    const prio = l => (l.stylespec.vmGaya === 'residu' ? 1 : 0);
    label.sort((a, b) => prio(a) - prio(b));
    const tumpang = (p, q) => p.x < q.x + q.w && q.x < p.x + p.w && p.y < q.y + q.h && q.y < p.y + p.h;
    const kotak = [];
    for (const l of label) {
      const st = l.stylespec, k = l._k, m = l.sprite.material;
      const w = l.canvas.width / k + 2, h = l.canvas.height / k + 1;
      const pos = st.position;
      if (!pos) continue;
      const p = v.modelToScreen(pos);
      const ax = st.alignment === 'bottomCenter' ? 0 : 0, ay = st.alignment === 'bottomCenter' ? -h : -h / 2;
      const dasar = {x: p.x - w / 2 + ax, y: p.y + ay, w, h};
      let pilih = [0, 0];
      if (kotak.some(q => tumpang(q, dasar))) {
        pilih = null;
        for (let s = 1; s <= 4 && !pilih; s++) {
          for (const [dx, dy] of [[0, -h * s], [0, h * s], [w * 0.55 * s, 0], [-w * 0.55 * s, 0],
                                  [w * 0.5 * s, -h * s], [-w * 0.5 * s, -h * s], [w * 0.5 * s, h * s],
                                  [-w * 0.5 * s, h * s]]) {
            const r = {x: dasar.x + dx, y: dasar.y + dy, w, h};
            if (!kotak.some(q => tumpang(q, r))) { pilih = [dx, dy]; break; }
          }
        }
        pilih = pilih || [0, 0];
      }
      kotak.push({x: dasar.x + pilih[0], y: dasar.y + pilih[1], w, h});
      const so = {x: pilih[0] * k, y: -pilih[1] * k};
      const lama = m.screenOffset;
      if (!lama || Math.abs(lama.x - so.x) > 0.5 || Math.abs(lama.y - so.y) > 0.5) {
        m.screenOffset = so;
        berubah = true;
      }
    }
    return berubah;
  },
  /* gambar ulang semua label viewer (setelah devicePixelRatio berubah, mis. ekspor resolusi tinggi) */
  segarkan(v) {
    for (const l of (v && v.labels) || []) if (l && l.sprite) v.setLabelStyle(l, l.stylespec);
  },
};

(function pasangLabelVM() {
  const L = $3Dmol.Label;
  if (!L || L.prototype._vm) return;
  const asli = L.prototype.setContext;
  L.prototype.setContext = function () {
    // 3Dmol membuat material, tekstur (berbasis this.canvas), perataan & kedalaman; kanvasnya lalu digambar ulang
    asli.call(this);
    const t = this.stylespec || {}, k = LabelVM.k();
    const fs = parseFloat(t.fontSize) || 12;
    const keluarga = `"${t.font || 'Segoe UI'}", "Segoe UI", "Helvetica Neue", Arial, sans-serif`;
    const tinta = t.fontColor || '#1b2430';
    let seg;
    if (t.vmGaya === 'residu') {
      const i = this.text.indexOf(' ');
      seg = i > 0 ? [{teks: this.text.slice(0, i), berat: 600, warna: tinta},
                     {teks: ' ' + this.text.slice(i + 1), berat: 400, warna: t.warna2 || tinta}]
                   : [{teks: this.text, berat: 600, warna: tinta}];
    } else {
      seg = [{teks: String(this.text), berat: t.berat || (t.bold ? 700 : 500), warna: tinta}];
    }
    const c = this.canvas, x = this.context;
    const huruf = s => `${s.berat} ${fs * k}px ${keluarga}`;
    let lebarTeks = 0;
    for (const s of seg) { x.font = huruf(s); s.w = x.measureText(s.teks).width; lebarTeks += s.w; }
    const latar = !(t.showBackground === false || t.showBackground === 'false' || t.showBackground === '0');
    const bayang = latar && t.bayang !== false ? 2.5 * k : 0;
    const padX = (t.padX !== undefined ? t.padX : 5) * k, padY = (t.padY !== undefined ? t.padY : 1.5) * k;
    const aksen = t.aksen ? 8 * k : 0;
    const tinggiIsi = fs * 1.28 * k + 2 * padY;
    const W = Math.ceil(lebarTeks + 2 * padX + aksen + 2 * bayang), H = Math.ceil(tinggiIsi + 2 * bayang);
    c.width = Math.max(2, W); c.height = Math.max(2, H);
    x.clearRect(0, 0, c.width, c.height);
    const bx = bayang, by = bayang * 0.7, bw = W - 2 * bayang, bh = tinggiIsi;
    const r = Math.min(bh / 2, (t.radius !== undefined ? t.radius : bh / 2 / k) * k);
    if (latar) {
      const op = t.backgroundOpacity !== undefined ? parseFloat(t.backgroundOpacity) : 0.92;
      x.save();
      if (bayang) {
        x.shadowColor = 'rgba(15,23,42,0.30)'; x.shadowBlur = bayang * 1.2; x.shadowOffsetY = 0.5 * k;
      }
      x.fillStyle = LabelVM.rgba(t.backgroundColor || '#ffffff', op);
      LabelVM.pil(x, bx, by, bw, bh, r); x.fill();
      x.restore();
      const tepi = parseFloat(t.borderThickness) || 0;
      if (tepi > 0) {
        x.lineWidth = tepi * k * 0.9;
        x.strokeStyle = LabelVM.rgba(t.borderColor || '#c9d1dc', t.borderOpacity !== undefined ? t.borderOpacity : 1);
        LabelVM.pil(x, bx + x.lineWidth / 2, by + x.lineWidth / 2, bw - x.lineWidth, bh - x.lineWidth,
                    Math.max(0, r - x.lineWidth / 2));
        x.stroke();
      }
    }
    if (aksen) {
      x.fillStyle = t.aksen;
      x.beginPath(); x.arc(bx + padX + 2.6 * k, by + bh / 2, 2.6 * k, 0, 2 * Math.PI); x.fill();
    }
    x.textBaseline = 'middle';
    let px = bx + padX + aksen;
    const py = by + bh / 2 + 0.06 * fs * k;
    for (const s of seg) { x.font = huruf(s); x.fillStyle = s.warna; x.fillText(s.teks, px, py); px += s.w; }

    const m = this.sprite.material;
    if (m.map) m.map.needsUpdate = true;
    if (m.screenOffset) m.screenOffset = {x: m.screenOffset.x * k, y: m.screenOffset.y * k};   // relatif lebar tekstur
    this.sprite.scale.set(1 / k, 1 / k, 1);
    this._k = k;
  };
  L.prototype._vm = true;
})();
