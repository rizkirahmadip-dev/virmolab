"""Laporan ringkas (HTML untuk QTextDocument -> PDF)."""
from datetime import datetime
import re
from html import escape

from .analisis import KRITERIA, NAMA_JENIS, URUT_JENIS
from . import mesin as M

SITASI = {
    "adgpu": "Santos-Martins D, Solis-Vasquez L, Tillack AF, Sanner MF, Koch A, Forli S. Accelerating AutoDock4 with "
             "GPUs and gradient-based local search. J Chem Theory Comput. 2021;17(2):1060–1073. "
             "doi:10.1021/acs.jctc.0c01006",
    "vina": "Eberhardt J, Santos-Martins D, Tillack AF, Forli S. AutoDock Vina 1.2.0: new docking methods, expanded "
            "force field, and Python bindings. J Chem Inf Model. 2021;61(8):3891–3898. doi:10.1021/acs.jcim.1c00203; "
            "Trott O, Olson AJ. AutoDock Vina. J Comput Chem. 2010;31(2):455–461. doi:10.1002/jcc.21334",
    "ad4": "Morris GM, Huey R, Lindstrom W, Sanner MF, Belew RK, Goodsell DS, Olson AJ. AutoDock4 and AutoDockTools4. "
           "J Comput Chem. 2009;30(16):2785–2791. doi:10.1002/jcc.21256",
    "meeko": "Meeko: preparation of small molecules and receptors for AutoDock (Forli Lab, Scripps Research). "
             "https://github.com/forlilab/Meeko",
    "rdkit": "RDKit: Open-source cheminformatics. https://www.rdkit.org",
    "openbabel": "O'Boyle NM, Banck M, James CA, Morley C, Vandermeersch T, Hutchison GR. Open Babel: an open chemical "
                 "toolbox. J Cheminform. 2011;3:33. doi:10.1186/1758-2946-3-33",
    "gemmi": "Wojdyr M. GEMMI: a library for structural biology. J Open Source Softw. 2022;7(73):4200. "
             "doi:10.21105/joss.04200",
    "3dmol": "Rego N, Koes D. 3Dmol.js: molecular visualization with WebGL. Bioinformatics. 2015;31(8):1322–1324. "
             "doi:10.1093/bioinformatics/btu829",
}

GAYA = """
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 9pt; color: #1b2430; }
h1 { font-size: 17pt; color: #173b6c; margin: 0 0 2px 0; }
h2 { font-size: 11.5pt; color: #173b6c; margin: 14px 0 4px 0; border-bottom: 1px solid #d3d9e1; }
p { margin: 2px 0 4px 0; }
.mut { color: #7b8698; }
table.t { border-collapse: collapse; margin: 4px 0; }
table.t td, table.t th { border: 1px solid #d3d9e1; padding: 3px 6px; }
table.t th { background: #e9ecf1; font-weight: 600; text-align: left; }
td.n { text-align: right; font-family: Consolas, monospace; }
.ok { color: #2e9e5b; font-weight: 600; } .bad { color: #cf3f3f; font-weight: 600; } .warn { color: #c98a12; }
"""


def id_angka(t):
    """Teks angka -> gaya Indonesia: koma desimal, tanda minus asli (U+2212). Hanya angka di awal teks
    (mis. Ki "221.99 pM") yang diubah; teks lain apa adanya."""
    m = re.match(r"^(-?)(\d+)\.(\d+)", t)
    if m:
        t = ("−" if m.group(1) else "") + m.group(2) + "," + m.group(3) + t[m.end():]
    elif t.startswith("-") and t[1:2].isdigit():
        t = "−" + t[1:]
    return t


_id = id_angka


def _n(v, d=2):
    """Angka -> teks gaya Indonesia dengan d desimal."""
    return "–" if v is None or v == "" else _id(f"{float(v):.{d}f}")


def _f(v, fmt="{:.2f}"):
    if v is None or v == "":
        return "–"
    return escape(_id(fmt.format(v) if isinstance(v, float) else str(v)))


def _kelas_qc(q):
    if not q or q.get("galat"):
        return ""
    return " class='ok'" if q.get("lulus") else " class='bad'"


def html(proyek, baris, info, interaksi_terbaik=None, ada_gambar3d=False, ada_diagram=False, penulis="",
         sifat_ligan=None):
    """sifat_ligan: {nama ligan: dict core.sifat.hitung} (opsional)."""
    pr = proyek
    rec = pr.reseptor or {}
    jobs = pr.job
    mesin_dipakai = sorted({j["mesin"] for j in jobs if j["status"] in ("selesai", "dijeda", "gagal")})
    o = [f"<html><head><style>{GAYA}</style></head><body>"]
    o.append(f"<h1>Laporan Docking Molekuler — {escape(pr.nama)}</h1>")
    n = datetime.now()
    bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
             "November", "Desember"][n.month - 1]
    o.append(f"<p class='mut'>{n.day} {bulan} {n.year}, {n:%H:%M} · VirmoDock {escape(info.get('versi', ''))}"
             + (f" · {escape(penulis)}" if penulis else "") + "</p>")

    # ---- validasi
    val = getattr(pr, "validasi", None) or {}
    o.append("<h2>1. Validasi metode (redocking)</h2>")
    if val.get("rmsd") is not None:
        ok = val["rmsd"] <= 2.0
        o.append(f"<p>Ligan kristal <b>{escape(val.get('ligan', ''))}</b> didocking ulang ke reseptor dengan parameter "
                 f"yang sama ({escape(val.get('mesin', ''))}), dimulai dari konformasi kristal tanpa minimisasi. RMSD pose terbaik terhadap kristal: "
                 f"<span class='{'ok' if ok else 'bad'}'>{_n(val['rmsd'])} Å</span> "
                 f"({'valid, ≤ 2,0 Å' if ok else 'tidak valid, > 2,0 Å'}); RMSD minimum di antara pose teratas "
                 f"{_f(val.get('rmsd_min'))} Å; ΔG {_f(val.get('energi'))} kcal/mol.</p>")
    else:
        o.append("<p class='warn'>Validasi redocking belum dilakukan. Disarankan menjalankan Docking › Validasi "
                 "redocking sebelum menafsirkan hasil.</p>")

    # ---- reseptor
    o.append("<h2>2. Reseptor</h2><table class='t'>")
    for k, v in (("Struktur", rec.get("nama")), ("Sumber", rec.get("sumber")), ("Metode preparasi", rec.get("metode")),
                 ("Atom PDBQT", rec.get("atom")), ("Residu", rec.get("residu")),
                 ("Ion logam dipertahankan", ", ".join(rec.get("logam") or []) or "–"),
                 ("Residu tidak lengkap dibuang", ", ".join(rec.get("dibuang") or []) or "–")):
        o.append(f"<tr><th>{k}</th><td>{_f(v)}</td></tr>")
    af = rec.get("alphafold") or {}
    if af:
        o.append(f"<tr><th>Model prediksi</th><td>AlphaFold DB {escape(str(af.get('entri')))} v{escape(str(af.get('versi')))}"
                 f" — UniProt {escape(str(af.get('aksesi')))} ({escape(af.get('nama', ''))}, "
                 f"{escape(af.get('organisme', ''))}); pLDDT rerata {_f(af.get('plddt_rerata'))}"
                 + (f"; residu pLDDT &lt; {_n(af['ambang'], 0)} dipangkas: {escape(af.get('dibuang', ''))}"
                    if af.get("n_dibuang") else "") + "</td></tr>")
    jobs_flex = sorted({", ".join(j.get("fleksibel") or []) for j in jobs if j.get("fleksibel")})
    if jobs_flex:
        o.append(f"<tr><th>Residu fleksibel</th><td>{escape(' | '.join(jobs_flex))} (rantai samping dapat "
                 "berotasi selama docking; Meeko)</td></tr>")
    o.append("</table>")
    op = rec.get("opsi") or {}
    o.append(f"<p class='mut'>Air {'dihapus' if op.get('hapus_air', True) else 'dipertahankan'}; ligan/aditif "
             f"{'dihapus' if op.get('hapus_ligan', True) else 'dipertahankan'}; konformasi alternatif: "
             f"{'altloc A' if op.get('altloc') == 'A' else 'okupansi tertinggi'}; hidrogen polar & muatan "
             f"{'Gasteiger' if op.get('muatan', 'gasteiger') == 'gasteiger' else 'templat'} (Meeko).</p>")

    # ---- ligan & docking
    lig = pr.ligan_siap()
    o.append("<h2>3. Ligan dan parameter docking</h2>")
    o.append(f"<p>{len(lig)} ligan disiapkan (protonasi pH, minimisasi MMFF94, torsi & PDBQT oleh Meeko).</p>")
    o.append("<table class='t'><tr><th>Job</th><th>Mesin</th><th>Perangkat</th><th>Pencarian</th>"
             "<th>Grid box (pusat; ukuran; spasi)</th><th>Ligan</th></tr>")
    for j in jobs:
        p = j["parameter"]
        if j["mesin"] == "vina":
            cari = (f"exhaustiveness {p.get('exhaustiveness')}, {p.get('num_modes')} pose, rentang "
                    f"{_f(p.get('energy_range'), '{:.1f}')}")
        elif j["mesin"] == "adgpu":
            cari = f"{p.get('nrun')} run, " + ("evaluasi heuristik" if p.get("heuristik") else f"{p.get('nev')} evaluasi")
        else:
            cari = f"ga_run {p.get('nrun')}, pop {p.get('pop')}, {p.get('nev')} evaluasi"
        cari += f", seed {p.get('seed') or 'acak'}"
        k = j["kotak"]
        kot = (f"({' · '.join(_n(v) for v in k['pusat'])}); {' × '.join(_n(v, 1) for v in k['ukuran'])} Å; "
               f"{_n(k.get('spasi', 0.375), 3)} Å")
        ok = sum(1 for l in j["ligan"] if l["status"] == "selesai")
        o.append(f"<tr><td>{escape(j['id'])}</td><td>{escape(M.MESIN[j['mesin']])}"
                 + (" (alih dari AD-GPU)" if j["mesin"] != j.get("mesin_asal") else "")
                 + f"</td><td>{'GPU' if j.get('perangkat') == 'gpu' else 'CPU'}</td><td>{escape(cari)}</td>"
                   f"<td>{escape(kot)}</td><td class='n'>{ok}/{len(j['ligan'])}</td></tr>")
    o.append("</table>")
    if info.get("perangkat"):
        o.append(f"<p class='mut'>Perangkat: {escape(info['perangkat'])}</p>")

    # ---- hasil
    o.append("<h2>4. Hasil</h2>")
    o.append("<table class='t'><tr><th>#</th><th>Ligan</th><th>ΔG (kcal/mol)</th><th>Ki perkiraan</th><th>LE</th>"
             "<th>Ikatan H</th><th>Hidrofobik</th><th>π</th><th>RMSD kristal (Å)</th><th>PoseBusters</th>"
             "<th>Mesin</th></tr>")
    for b in baris[:15]:
        o.append(f"<tr><td class='n'>{b['peringkat']}</td><td>{escape(b['ligan'])}</td><td class='n'>{_n(b['energi'])}</td>"
                 f"<td class='n'>{_f(b['ki'])}</td><td class='n'>{_f(b['le'], '{:.3f}')}</td>"
                 f"<td class='n'>{b['hbond']}</td><td class='n'>{b['hidrofobik']}</td>"
                 f"<td class='n'>{b['pi'] + b['pikation']}</td><td class='n'>{_f(b['rmsd_kristal'])}</td>"
                 f"<td{_kelas_qc(b.get('qc'))}>{escape(b.get('posebusters') or '–')}</td>"
                 f"<td>{escape(b['mesin'])}</td></tr>")
    o.append("</table>")
    if len(baris) > 15:
        o.append(f"<p class='mut'>15 dari {len(baris)} hasil ditampilkan; tabel lengkap tersedia di ekspor CSV/XLSX.</p>")
    if baris:
        b = baris[0]
        o.append(f"<p>Ligan terbaik: <b>{escape(b['ligan'])}</b>, ΔG {_n(b['energi'])} kcal/mol "
                 f"(Ki perkiraan {_f(b['ki'])}).</p>")
        if ada_gambar3d or ada_diagram:
            o.append("<table><tr>")
            if ada_gambar3d:
                o.append("<td><img src='img3d' width='330'></td>")
            if ada_diagram:
                o.append("<td><img src='img2d' width='330'></td>")
            o.append("</tr></table>")
            o.append(f"<p class='mut'>Gambar: pose terbaik {escape(b['ligan'])} di situs pengikatan (kiri) dan "
                     "diagram interaksi 2D (kanan).</p>")
        if interaksi_terbaik:
            o.append("<table class='t'><tr><th>Jenis</th><th>Residu</th><th>Atom</th><th>Jarak (Å)</th><th>Sudut</th></tr>")
            for h in sorted(interaksi_terbaik, key=lambda h: (URUT_JENIS.index(h["jenis"]), h["jarak"])):
                if h["jenis"] == "vdw":
                    continue
                o.append(f"<tr><td>{NAMA_JENIS[h['jenis']]}</td><td>{escape(h['residu'])}</td>"
                         f"<td>{escape(h['atom_p'])}</td><td class='n'>{_n(h['jarak'])}</td>"
                         f"<td class='n'>{_f(h.get('sudut'), '{:.0f}°')}</td></tr>")
            o.append("</table>")

    # ---- sifat ligan
    if sifat_ligan and baris:
        from . import sifat as S
        urut, sudah = [], set()
        for b in baris:
            if b["ligan"] in sifat_ligan and b["ligan"] not in sudah:
                urut.append(b["ligan"])
                sudah.add(b["ligan"])
        if urut:
            o.append("<p><b>Sifat ligan (drug-likeness, BOILED-Egg)</b></p>")
            o.append("<table class='t'><tr><th>Ligan</th><th>MW</th><th>WLOGP</th><th>TPSA (Å²)</th><th>QED</th>"
                     "<th>Lipinski</th><th>Veber</th><th>Absorpsi GI</th><th>BBB</th><th>PAINS</th></tr>")
            for n in urut[:15]:
                x = sifat_ligan[n]
                o.append(f"<tr><td>{escape(n)}</td><td class='n'>{_n(x['mw'], 1)}</td><td class='n'>{_n(x['wlogp'])}</td>"
                         f"<td class='n'>{_n(x['tpsa'], 1)}</td><td class='n'>{_f(x.get('qed'), '{:.2f}')}</td>"
                         f"<td>{escape(S.sel(x, 'lipinski'))}</td><td>{escape(S.sel(x, 'veber'))}</td>"
                         f"<td>{escape(S.sel(x, 'gi'))}</td><td>{escape(S.sel(x, 'bbb'))}</td>"
                         f"<td>{'<span class=warn>' + escape(', '.join(x['pains'])) + '</span>' if x['pains'] else '–'}"
                         "</td></tr>")
            o.append("</table>")

    # ---- metode
    k = KRITERIA
    o.append("<h2>5. Metode singkat</h2>")
    o.append("<p>Struktur reseptor dibersihkan dengan gemmi, lalu hidrogen polar, muatan parsial, dan tipe atom "
             "AutoDock ditambahkan dengan Meeko. Ligan diprotonasi (Open Babel), dibuat 3D dan diminimisasi "
             "(RDKit, MMFF94), lalu dikonversi ke PDBQT (Meeko). "
             + ("Peta grid dibuat dengan AutoGrid4. " if any(m in ("adgpu", "ad4") for m in mesin_dipakai) else "")
             + "Docking dijalankan dengan " + ", ".join(M.MESIN[m] for m in mesin_dipakai) + ". "
             f"Interaksi dianalisis dengan kriteria geometri: ikatan hidrogen D···A ≤ {_n(k['hbond_da'], 1)} Å dan "
             f"sudut D–H···A ≥ {k['hbond_sudut']:.0f}°, kontak hidrofobik ≤ {_n(k['hidrofobik'], 1)} Å, "
             f"π–π ≤ {_n(k['pi'], 1)} Å, π–kation ≤ {_n(k['pikation'], 1)} Å, jembatan garam ≤ {_n(k['garam'], 1)} Å, "
             f"ikatan halogen ≤ {_n(k['halogen'], 1)} Å. "
             "RMSD redocking dihitung tanpa penjajaran dan memperhitungkan simetri molekul."
             + (" Sifat fisikokimia dan kemiripan obat dihitung dengan RDKit dari struktur netral (WLOGP "
                "Wildman–Crippen, TPSA Ertl); aturan Lipinski, Veber, Ghose, Egan, Muegge; peringatan substruktur "
                "PAINS; prediksi absorpsi saluran cerna dan penetrasi sawar darah otak dengan model BOILED-Egg."
                if sifat_ligan else "")
             + (" Kewajaran fisik pose terbaik tiap ligan (kimia, geometri ikatan, kerataan cincin, energi internal, "
                "jarak dan tumpang-tindih dengan protein) diperiksa dengan PoseBusters (konfigurasi dock)."
                if any(b.get("qc") and not b["qc"].get("galat") for b in baris) else "") + "</p>")
    o.append("<h2>6. Perangkat lunak yang dikutip</h2><ol>")
    kunci = [m for m in mesin_dipakai] + ["meeko", "rdkit", "openbabel", "gemmi", "3dmol"]
    if "adgpu" in kunci and "ad4" not in kunci:
        kunci.insert(1, "ad4")  # AD-GPU memakai fungsi skor & AutoGrid AutoDock4
    for x in kunci:
        o.append(f"<li>{escape(SITASI[x])}</li>")
    if any(b.get("qc") and not b["qc"].get("galat") for b in baris):
        from .qc import SITASI as SITASI_QC
        o.append(f"<li>{escape(SITASI_QC)}</li>")
    if sifat_ligan:
        from .sifat import SITASI as SITASI_SIFAT
        for x in SITASI_SIFAT[:5] + SITASI_SIFAT[7:8]:   # BOILED-Egg, Lipinski, Ghose, Veber, Egan, PAINS
            o.append(f"<li>{escape(x)}</li>")
    o.append("</ol>")
    o.append("<p class='mut'>Hasil docking adalah prediksi komputasi, bukan bukti aktivitas biologis; konfirmasi "
             "dengan uji eksperimen. Ki dihitung dari ΔG pada 298 K sebagai perkiraan.</p>")
    o.append("</body></html>")
    return "".join(o)
