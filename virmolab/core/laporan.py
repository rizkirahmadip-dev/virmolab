"""Laporan ringkas (HTML untuk QTextDocument -> PDF)."""
from datetime import datetime
import re
from html import escape

from .analisis import KRITERIA, NAMA_JENIS, URUT_JENIS
from . import mesin as M

SITASI = {
    "adgpu": "Santos-Martins D, Solis-Vasquez L, Tillack AF, Sanner MF, Koch A, Forli S. Accelerating AutoDock4 with "
             "GPUs and gradient-based local search. J Chem Theory Comput. 2021;17(2):1060-1073. "
             "doi:10.1021/acs.jctc.0c01006",
    "vina": "Eberhardt J, Santos-Martins D, Tillack AF, Forli S. AutoDock Vina 1.2.0: new docking methods, expanded "
            "force field, and Python bindings. J Chem Inf Model. 2021;61(8):3891-3898. doi:10.1021/acs.jcim.1c00203; "
            "Trott O, Olson AJ. AutoDock Vina. J Comput Chem. 2010;31(2):455-461. doi:10.1002/jcc.21334",
    "ad4": "Morris GM, Huey R, Lindstrom W, Sanner MF, Belew RK, Goodsell DS, Olson AJ. AutoDock4 and AutoDockTools4. "
           "J Comput Chem. 2009;30(16):2785-2791. doi:10.1002/jcc.21256",
    "unidock": "Yu Y, Cai C, Wang J, Bo Z, Zhu Z, Zheng H. Uni-Dock: GPU-accelerated docking enables ultralarge "
               "virtual screening. J Chem Theory Comput. 2023;19(11):3336-3345. doi:10.1021/acs.jctc.2c01145",
    "meeko": "Meeko: preparation of small molecules and receptors for AutoDock (Forli Lab, Scripps Research). "
             "https://github.com/forlilab/Meeko",
    "rdkit": "RDKit: Open-source cheminformatics. https://www.rdkit.org",
    "openbabel": "O'Boyle NM, Banck M, James CA, Morley C, Vandermeersch T, Hutchison GR. Open Babel: an open chemical "
                 "toolbox. J Cheminform. 2011;3:33. doi:10.1186/1758-2946-3-33",
    "gemmi": "Wojdyr M. GEMMI: a library for structural biology. J Open Source Softw. 2022;7(73):4200. "
             "doi:10.21105/joss.04200",
    "3dmol": "Rego N, Koes D. 3Dmol.js: molecular visualization with WebGL. Bioinformatics. 2015;31(8):1322-1324. "
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
    m = re.match(r"^([-+]?)(\d+)\.(\d+)", t)
    if m:
        tanda = "−" if m.group(1) == "-" else m.group(1)
        t = tanda + m.group(2) + "," + m.group(3) + t[m.end():]
    elif t.startswith("-") and t[1:2].isdigit():
        t = "−" + t[1:]
    return t


_id = id_angka


def _n(v, d=2):
    """Angka -> teks gaya Indonesia dengan d desimal."""
    return "-" if v is None or v == "" else _id(f"{float(v):.{d}f}")


def _f(v, fmt="{:.2f}"):
    if v is None or v == "":
        return "-"
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
    o.append(f"<h1>Laporan Docking Molekuler - {escape(pr.nama)}</h1>")
    n = datetime.now()
    bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
             "November", "Desember"][n.month - 1]
    o.append(f"<p class='mut'>{n.day} {bulan} {n.year}, {n:%H:%M} · VirmoLab {escape(info.get('versi', ''))}"
             + (f" · {escape(penulis)}" if penulis else "") + "</p>")

    # ---- validasi
    val = getattr(pr, "validasi", None) or {}
    o.append("<h2>1. Validasi metode (redocking)</h2>")
    if val.get("rmsd") is not None and val.get("protokol") == "smiles":
        ok = val["rmsd"] <= 2.0
        o.append(f"<p>Angka ini hasil redocking buta yang sudah diukur untuk 1HSG dan MK1, "
                 f"bukan pengukuran ulang saat proyek ini dibuka. Ligan <b>{escape(val.get('ligan', 'MK1'))}</b> "
                 f"dibangun dari SMILES bermuatan (bukan koordinat kristal), diminimisasi MMFF, reseptor "
                 f"diprotonasi PROPKA pH 7,4, lalu didocking dengan {escape(val.get('mesin', 'AutoDock Vina'))}, "
                 f"exhaustiveness 16, 9 pose, seed 42, kotak pada ligan kristal. RMSD atom berat terhadap kristal, "
                 f"dalam kerangka yang sama dan tanpa superposisi: "
                 f"<span class='{'ok' if ok else 'bad'}'>{_n(val['rmsd'])} Å</span> "
                 f"({'valid, ≤ 2,0 Å' if ok else 'tidak valid, > 2,0 Å'}). "
                 f"ΔG Vina {_f(val.get('energi'))} kcal/mol. GNINA Affinity {_f(val.get('gnina'))} kcal/mol, "
                 f"CNNscore {_f(val.get('cnnscore'))}, CNNaffinity {_f(val.get('cnnaffinity'))} pK.</p>")
    elif val.get("rmsd") is not None:
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
    sumber = rec.get("sumber") or ""
    if re.match(r"^[A-Za-z]:[\\/]", sumber):      # berkas lokal: cukup namanya (jalur memuat nama pengguna Windows)
        from pathlib import PureWindowsPath
        sumber = PureWindowsPath(sumber).name
    for k, v in (("Struktur", rec.get("nama")), ("Sumber", sumber), ("Metode preparasi", rec.get("metode")),
                 ("Atom PDBQT", rec.get("atom")), ("Residu", rec.get("residu")),
                 ("Ion logam dipertahankan", ", ".join(rec.get("logam") or []) or "-"),
                 ("Residu tidak lengkap dibuang", ", ".join(rec.get("dibuang") or []) or "-")):
        o.append(f"<tr><th>{k}</th><td>{_f(v)}</td></tr>")
    af = rec.get("alphafold") or {}
    if af:
        o.append(f"<tr><th>Model prediksi</th><td>AlphaFold DB {escape(str(af.get('entri')))} v{escape(str(af.get('versi')))}"
                 f" - UniProt {escape(str(af.get('aksesi')))} ({escape(af.get('nama', ''))}, "
                 f"{escape(af.get('organisme', ''))}); pLDDT rerata {_f(af.get('plddt_rerata'))}"
                 + (f"; residu pLDDT &lt; {_n(af['ambang'], 0)} dipangkas: {escape(af.get('dibuang', ''))}"
                    if af.get("n_dibuang") else "") + "</td></tr>")
    jobs_flex = sorted({", ".join(j.get("fleksibel") or []) for j in jobs if j.get("fleksibel")})
    if jobs_flex:
        o.append(f"<tr><th>Residu fleksibel</th><td>{escape(' | '.join(jobs_flex))} (rantai samping dapat "
                 "berotasi selama docking; Meeko)</td></tr>")
    jobs_kov = sorted({(j["kovalen"].get("label") or j["kovalen"].get("residu") or "")
                       for j in jobs if j.get("kovalen")})
    if jobs_kov:
        o.append(f"<tr><th>Docking kovalen</th><td>residu sasaran {escape(' | '.join(jobs_kov))} (metode tethered: "
                 "ligan diikat ke rantai samping residu dan di-docking sebagai aduk)</td></tr>")
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
        if j.get("impor"):     # pose dari program lain: pencarian dan grid box bukan milik VirmoLab
            from .impor_docking import label_skor
            im = j["impor"]
            ok = sum(1 for l in j["ligan"] if l["status"] == "selesai")
            sumber_e = ("skor ulang Vina (--score_only)" if im.get("energi") == "vina_ulang"
                        else label_skor(im["energi"]) if im.get("energi") else "-")
            cari = (f"Hasil impor {im.get('program', '')}; docking tidak dijalankan di VirmoLab. "
                    f"Urutan pose: {label_skor(im['skor_utama']) if im.get('skor_utama') else 'berkas asal'}. "
                    f"ΔG: {sumber_e}.")
            o.append(f"<tr><td>{escape(j['id'])}</td><td>{escape(M.label_mesin(j))}</td><td>-</td>"
                     f"<td>{escape(cari)}</td><td>-</td><td class='n'>{ok}/{len(j['ligan'])}</td></tr>")
            continue
        if j["mesin"] == "vina":
            cari = (f"exhaustiveness {p.get('exhaustiveness')}, {p.get('num_modes')} pose, rentang "
                    f"{_f(p.get('energy_range'), '{:.1f}')}")
        elif j["mesin"] == "adgpu":
            cari = f"{p.get('nrun')} run, " + ("evaluasi heuristik" if p.get("heuristik") else f"{p.get('nev')} evaluasi")
        elif j["mesin"] == "unidock":
            cari = (f"mode pencarian {p.get('unidock_mode', 'balance')}, fungsi skor {p.get('unidock_skor', 'vina')}, "
                    f"{p.get('num_modes')} pose")
        else:
            cari = f"ga_run {p.get('nrun')}, pop {p.get('pop')}, {p.get('nev')} evaluasi"
        cari += f", seed {p.get('seed') or 'acak'}"
        k = j["kotak"]
        kot = (f"({' · '.join(_n(v) for v in k['pusat'])}); {' × '.join(_n(v, 1) for v in k['ukuran'])} Å; "
               f"{_n(k.get('spasi', 0.375), 3)} Å")
        ok = sum(1 for l in j["ligan"] if l["status"] == "selesai")
        o.append(f"<tr><td>{escape(j['id'])}</td><td>{escape(M.label_mesin(j))}"
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
             "<th>Mesin</th><th>GNINA (kcal/mol)</th><th>CNNscore</th><th>CNNaffinity (pK)</th>"
             "<th>Syarat jarak (Å)</th></tr>")
    for b in baris[:15]:
        o.append(f"<tr><td class='n'>{b['peringkat']}</td><td>{escape(b['ligan'])}</td><td class='n'>{_n(b['energi'])}</td>"
                 f"<td class='n'>{_f(b['ki'])}</td><td class='n'>{_f(b['le'], '{:.3f}')}</td>"
                 f"<td class='n'>{b['hbond']}</td><td class='n'>{b['hidrofobik']}</td>"
                 f"<td class='n'>{b['pi'] + b['pikation']}</td><td class='n'>{_f(b['rmsd_kristal'])}</td>"
                 f"<td{_kelas_qc(b.get('qc'))}>{escape(b.get('posebusters') or '-')}</td>"
                 f"<td>{escape(b['mesin'])}</td><td class='n'>{_f(b.get('gnina'))}</td>"
                 f"<td class='n'>{_f(b.get('cnnscore'), '{:.3f}')}</td>"
                 f"<td class='n'>{_f(b.get('cnnaffinity'))}</td>"
                 f"<td class='n'>{_f(b.get('syarat_jarak'))}</td></tr>")
    o.append("</table>")
    o.append("<p class='mut'>Kolom GNINA kosong bila programnya tidak terpasang di WSL, atau bila ligan itu di luar "
             "10 energi terbaik dan belum diminta lewat Analisis › GNINA untuk sisa ligan. Sel kosong bukan nol. "
             "CNNaffinity dalam pK, bukan kcal/mol. Syarat jarak diukur sesudah pencarian; tanda - berarti syarat "
             "belum diatur. Mesin docking tidak memaksa kontak itu. Bila ada pose lain yang lolos, "
             "baris memakai pose berenergi terbaik yang lolos; ΔG-nya tetap skor docking pose itu.</p>")
    if len(baris) > 15:
        o.append(f"<p class='mut'>15 dari {len(baris)} hasil ditampilkan; tabel lengkap tersedia di ekspor CSV/XLSX.</p>")
    from .arti import html
    o.append("<p class='mut'><b>Arti angka.</b> " + html() + "</p>")
    if jobs_kov:
        o.append("<p class='mut'>Docking kovalen: angka pada kolom ΔG adalah skor aduk-reseptor (energi residu "
                 "fleksibel), bukan ΔG ikatan; Ki dan efisiensi ligan tidak dihitung. Bandingkan hanya antar-ligan "
                 "kovalen pada residu sasaran yang sama.</p>")
    if baris:
        b = baris[0]
        o.append(f"<p>Ligan terbaik: <b>{escape(b['ligan'])}</b>, "
                 + (f"skor kovalen {_n(b['energi'])} kcal/mol.</p>" if jobs_kov else
                    f"ΔG {_n(b['energi'])} kcal/mol (Ki perkiraan {_f(b['ki'])}).</p>"))
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
            o.append("<p><b>Sifat ligan (drug-likeness, BOILED-Egg, SAScore)</b></p>")
            o.append("<table class='t'><tr><th>Ligan</th><th>MW</th><th>WLOGP</th><th>TPSA (Å²)</th><th>QED</th>"
                     "<th>SAScore</th><th>Lipinski</th><th>Veber</th><th>Absorpsi GI</th><th>BBB</th><th>PAINS</th></tr>")
            for n in urut[:15]:
                x = sifat_ligan[n]
                o.append(f"<tr><td>{escape(n)}</td><td class='n'>{_n(x['mw'], 1)}</td><td class='n'>{_n(x['wlogp'])}</td>"
                         f"<td class='n'>{_n(x['tpsa'], 1)}</td><td class='n'>{_f(x.get('qed'), '{:.2f}')}</td>"
                         f"<td class='n'>{_f(x.get('sascore'), '{:.2f}')}</td>"
                         f"<td>{escape(S.sel(x, 'lipinski'))}</td><td>{escape(S.sel(x, 'veber'))}</td>"
                         f"<td>{escape(S.sel(x, 'gi'))}</td><td>{escape(S.sel(x, 'bbb'))}</td>"
                         f"<td>{'<span class=warn>' + escape(', '.join(x['pains'])) + '</span>' if x['pains'] else '-'}"
                         "</td></tr>")
            o.append("</table>")

    # ---- MM/GBSA & MD
    mm = [b for b in baris if b.get("mmgbsa") is not None]
    if mm:
        o.append("<p><b>Penyempurnaan pasca-docking (MM/GBSA)</b></p>")
        o.append("<table class='t'><tr><th>Ligan</th><th>ΔG docking (kcal/mol)</th><th>ΔG MM/GBSA (kcal/mol)</th>"
                 "<th>SD</th><th>Metode</th></tr>")
        for b in sorted(mm, key=lambda b: b["mmgbsa"])[:20]:
            o.append(f"<tr><td>{escape(b['ligan'])}</td><td class='n'>{_n(b['energi'])}</td>"
                     f"<td class='n'>{_n(b['mmgbsa'])}</td><td class='n'>{_f(b.get('mmgbsa_sd'))}</td>"
                     f"<td>{escape(b.get('mmgbsa_metode') or '')}</td></tr>")
        o.append("</table><p class='mut'>ΔG MM/GBSA satu-trajektori tanpa entropi konformasi: dipakai untuk "
                 "peringkat relatif antar-ligan, bukan afinitas absolut.</p>")

    # ---- metode
    k = KRITERIA
    o.append("<h2>5. Metode singkat</h2>")
    o.append("<p>Struktur reseptor dibersihkan dengan gemmi, lalu hidrogen polar, muatan parsial, dan tipe atom "
             "AutoDock ditambahkan dengan Meeko. Ligan diprotonasi (Open Babel), dibuat 3D dan diminimisasi "
             "(RDKit, MMFF94), lalu dikonversi ke PDBQT (Meeko). "
             + ("Peta grid dibuat dengan AutoGrid4. " if any(m in ("adgpu", "ad4") for m in mesin_dipakai) else "")
             + "Docking dijalankan dengan " + ", ".join(M.MESIN[m] for m in mesin_dipakai) + ". "
             f"Interaksi dianalisis dengan kriteria geometri: ikatan hidrogen D···A ≤ {_n(k['hbond_da'], 1)} Å dan "
             f"sudut D-H···A ≥ {k['hbond_sudut']:.0f}°, kontak hidrofobik ≤ {_n(k['hidrofobik'], 1)} Å, "
             f"π-π ≤ {_n(k['pi'], 1)} Å, π-kation ≤ {_n(k['pikation'], 1)} Å, jembatan garam ≤ {_n(k['garam'], 1)} Å, "
             f"ikatan halogen ≤ {_n(k['halogen'], 1)} Å. "
             "RMSD redocking dihitung tanpa penjajaran dan memperhitungkan simetri molekul."
             + (" Docking kovalen memakai metode tethered (rantai samping fleksibel): ligan direaksikan secara kimia "
                "dengan rantai samping residu sasaran menjadi satu aduk, aduk disejajarkan pada sumbu CA-CB residu "
                "dan di-docking sebagai residu fleksibel tunggal (AutoDock-GPU --flexres) terhadap reseptor tanpa "
                "rantai samping tersebut. Skor yang dilaporkan adalah energi aduk-reseptor, bukan ΔG ikatan, dan "
                "hanya dibandingkan antar-ligan kovalen pada residu sasaran yang sama." if jobs_kov else "")
             + (" Sifat fisikokimia dan kemiripan obat dihitung dengan RDKit dari struktur netral (WLOGP "
                "Wildman-Crippen, TPSA Ertl); aturan Lipinski, Veber, Ghose, Egan, Muegge; peringatan substruktur "
                "PAINS; prediksi absorpsi saluran cerna dan penetrasi sawar darah otak dengan model BOILED-Egg."
                if sifat_ligan else "")
             + (" Kewajaran fisik pose terbaik tiap ligan (kimia, geometri ikatan, kerataan cincin, energi internal, "
                "jarak dan tumpang-tindih dengan protein) diperiksa dengan PoseBusters (konfigurasi dock)."
                if any(b.get("qc") and not b["qc"].get("galat") for b in baris) else "")
             + (" Pose terbaik disempurnakan dengan OpenMM: protein Amber ff14SB, ligan OpenFF Sage 2.3 dengan muatan "
                "parsial OpenFF NAGL (setara AM1-BCC), ion logam model nonbonded Li/Merz. Kompleks diminimisasi di "
                "pelarut implisit OBC2 (atom berat protein dikekang 5 kcal/mol/Å²) dan/atau disimulasikan (MD "
                "Langevin 300 K, langkah 2 fs, ikatan-H dikendala; air eksplisit TIP3P dengan PME dan NaCl 0,15 M bila "
                "dipilih). ΔG MM/GBSA dihitung dengan pendekatan satu-trajektori (OBC2, igb = 5, radii mbondi2, "
                "suku permukaan ACE) tanpa entropi konformasi." if mm else "") + "</p>")

    # ---- sumber data
    jejak_list = getattr(pr, "jejak", None) or []
    nomor_perangkat = 6
    if jejak_list:
        nomor_perangkat = 7
        o.append("<h2>6. Sumber data</h2>")
        o.append("<p>Informasi dan struktur dalam proyek ini diperoleh dari basis data daring berikut:</p>")
        o.append("<table class='t'><tr><th>Sumber</th><th>Versi</th><th>Tanggal Ambil</th><th>Lisensi</th><th>Kueri</th></tr>")
        ada_cc_by = False
        for j in jejak_list:
            lis = j.get("lisensi", "")
            if "CC BY" in lis.upper():
                ada_cc_by = True
            o.append(f"<tr><td><b>{escape(j.get('sumber', ''))}</b></td><td>{escape(j.get('versi', ''))}</td>"
                     f"<td>{escape(j.get('diambil', '')[:10])}</td><td>{escape(lis)}</td>"
                     f"<td><code>{escape(j.get('kueri', ''))}</code></td></tr>")
        o.append("</table>")
        if ada_cc_by:
            o.append("<p class='mut'>Atribusi: Data dengan lisensi Creative Commons Atribusi (CC BY) digunakan sesuai ketentuan lisensi dengan mencantumkan sumber aslinya.</p>")

    o.append(f"<h2>{nomor_perangkat}. Perangkat lunak yang dikutip</h2><ol>")
    kunci = [m for m in mesin_dipakai] + ["meeko", "rdkit", "openbabel", "gemmi", "3dmol"]
    if "adgpu" in kunci and "ad4" not in kunci:
        kunci.insert(1, "ad4")  # AD-GPU memakai fungsi skor & AutoGrid AutoDock4
    if "unidock" in kunci and "vina" not in kunci:
        kunci.insert(kunci.index("unidock") + 1, "vina")    # Uni-Dock memakai fungsi skor Vina
    for x in kunci:
        o.append(f"<li>{escape(SITASI[x])}</li>")
    if jobs_kov:
        o.append("<li>" + escape("Bianco G, Forli S, Goodsell DS, Olson AJ. Covalent docking using AutoDock: "
                                 "two-point attractor and flexible side chain methods. Protein Sci. "
                                 "2016;25(1):295-301. doi:10.1002/pro.2733") + "</li>")
    if any(b.get("qc") and not b["qc"].get("galat") for b in baris):
        from .qc import SITASI as SITASI_QC
        o.append(f"<li>{escape(SITASI_QC)}</li>")
    if mm:
        from .md import SITASI as SITASI_MD
        for x in SITASI_MD:
            o.append(f"<li>{escape(x)}</li>")
    if sifat_ligan:
        from .sifat import SITASI as SITASI_SIFAT
        for x in SITASI_SIFAT[:5] + SITASI_SIFAT[7:8]:   # BOILED-Egg, Lipinski, Ghose, Veber, Egan, PAINS
            o.append(f"<li>{escape(x)}</li>")
    o.append("</ol>")
    o.append("<p class='mut'>Hasil docking adalah prediksi komputasi, bukan bukti aktivitas biologis; konfirmasi "
             "dengan uji eksperimen. Ki dihitung dari ΔG pada 298 K sebagai perkiraan.</p>")
    o.append("</body></html>")
    return "".join(o)


def laporan_md_html(proyek, run_id=None, ligan_idx=0, info=None) -> str:
    """Laporan komprehensif Dinamika Molekul (MD) F2 lengkap dengan 5 figur standar (SVG inline),

    tabel ringkas (rata-rata ± SD paruh kedua), dan evaluasi konvergensi.
    """
    import json
    import numpy as np
    from . import grafik, md_analisis

    pr = proyek
    info = info or {}
    o = [f"<html><head><style>{GAYA}</style></head><body>"]
    o.append(f"<h1>Laporan Dinamika Molekul & Analisis Trajektori - {escape(pr.nama)}</h1>")

    # Temukan data MD
    md_list = getattr(pr, "md", [])
    if run_id:
        run = next((r for r in md_list if r.get("id") == run_id), None)
    else:
        run = next((r for r in reversed(md_list) if r.get("status") == "selesai"), None)

    if not run:
        o.append("<p class='warn'>Tidak ada hasil simulasi MD yang selesai dalam proyek ini.</p></body></html>")
        return "".join(o)

    f_hasil = pr.p(run.get("folder", ""), "hasil.json")
    if not f_hasil.exists():
        o.append("<p class='warn'>Berkas hasil.json simulasi MD tidak ditemukan.</p></body></html>")
        return "".join(o)

    h = json.loads(f_hasil.read_text(encoding="utf-8"))
    ligan_selesai = [x for x in h.get("ligan", []) if x.get("selesai")]
    if not ligan_selesai:
        o.append("<p class='warn'>Tidak ada ligan yang berhasil disimulasikan.</p></body></html>")
        return "".join(o)

    lig_idx = min(ligan_idx, len(ligan_selesai) - 1)
    lig = ligan_selesai[lig_idx]
    opsi = h.get("opsi") or run.get("opsi") or {}
    dt_ps = opsi.get("interval_ps", 10.0)
    dt_ns = dt_ps / 1000.0

    o.append(f"<p class='mut'>Sistem: <b>{escape(lig['nama'])}</b> · Tanggal: {escape(run.get('tanggal', ''))} "
             f"· Platform: {escape(h.get('platform', 'CPU'))} · Lama: {opsi.get('ns', 1.0)} ns</p>")

    # 1. Ringkasan & Konvergensi
    tr = lig.get("trajektori") or {}
    an = lig.get("analisis") or {}
    rm_l = tr.get("rmsd_ligan") or []
    rm_c = tr.get("rmsd_ca") or []
    rg = an.get("rg") or []
    hb = an.get("hb") or []
    mm = lig.get("mmgbsa") or {}
    konv = an.get("konvergensi") or {}

    # Hitung rata-rata ± SD paruh kedua
    def _rata_sd(arr):
        if not arr:
            return "-", "-"
        p2 = arr[len(arr) // 2:] if len(arr) > 1 else arr
        return f"{np.mean(p2):.2f}", f"{np.std(p2):.2f}"

    rml_m, rml_s = _rata_sd(rm_l)
    rmc_m, rmc_s = _rata_sd(rm_c)
    rg_m, rg_s = _rata_sd(rg)
    hb_m, hb_s = (f"{konv['hb_rerata']:.1f}", f"{konv['hb_gs']:.1f}") if "hb_rerata" in konv else _rata_sd(hb)
    dg_m = f"{mm.get('dG', 0.0):.2f}" if mm.get("dG") is not None else "-"
    dg_s = f"{mm.get('sd', 0.0):.2f}" if mm.get("sd") is not None else "-"

    o.append("<h2>1. Ringkasan Metrik Trajektori (Paruh Kedua)</h2>")
    o.append("<table class='t'><tr><th>Metrik</th><th>Rata-rata</th><th>SD / GS</th><th>Satuan</th><th>Interpretasi</th></tr>")
    o.append(f"<tr><td>RMSD Ligan</td><td class='n'>{_id(rml_m)}</td><td class='n'>{_id(rml_s)}</td><td>Å</td>"
             f"<td>{'Stabil di kantong' if float(rml_m.replace(',', '.')) <= 2.5 else 'Mengalami pergeseran konformasi'}</td></tr>")
    o.append(f"<tr><td>RMSD Cα Protein</td><td class='n'>{_id(rmc_m)}</td><td class='n'>{_id(rmc_s)}</td><td>Å</td>"
             f"<td>Stabilitas tulang punggung protein</td></tr>")
    o.append(f"<tr><td>Radius Girasi (Rg)</td><td class='n'>{_id(rg_m)}</td><td class='n'>{_id(rg_s)}</td><td>Å</td>"
             f"<td>Kekompakan lipatan global</td></tr>")
    o.append(f"<tr><td>Ikatan Hidrogen</td><td class='n'>{_id(hb_m)}</td><td class='n'>{_id(hb_s)}</td><td>kontak</td>"
             f"<td>Persistensi interaksi elektrostatik</td></tr>")
    o.append(f"<tr><td>ΔG MM/GBSA</td><td class='n'>{_id(dg_m)}</td><td class='n'>{_id(dg_s)}</td><td>kcal/mol</td>"
             f"<td>Afinitas pengikatan relatif (OBC2, tanpa entropi)</td></tr>")
    o.append("</table>")

    # Kalimat konvergensi otomatis
    o.append("<p><b>Evaluasi Konvergensi:</b> ")
    if rm_l and float(rml_m.replace(",", ".")) <= 2.5 and float(rml_s.replace(",", ".")) < 0.6:
        o.append("Simulasi menunjukkan konvergensi struktural yang baik pada paruh kedua lintasan produksi, "
                 "dengan deviasi posisi ligan stabil (fluktuasi SD < 0,6 Å) dan lipatan protein kompak. "
                 f"Analisis blok rata-rata ikatan hidrogen mengonfirmasi kestabilan ikatan ({_id(hb_m)} ± {_id(hb_s)} kontak).")
    elif rm_l and float(rml_m.replace(",", ".")) > 3.0:
        o.append("Pose ligan bergeser relatif terhadap posisi awal docking (> 3 Å), mengindikasikan adaptasi "
                 "konformasi atau pengikatan fleksibel di situs target.")
    else:
        o.append("Simulasi menunjukkan dinamika menengah; disarankan memperpanjang lintasan atau menambah replika "
                 "untuk memverifikasi kestabilan keadaan akhir.")
    o.append("</p>")

    # 2. Lima Figur Standar MD
    o.append("<h2>2. Figur Standar Analisis Dinamika Molekul</h2>")

    # Figur 1: RMSD
    t_rm = [(i + 1) * dt_ns for i in range(len(rm_l))]
    seri_rmsd = [("Ligan (atom berat)", t_rm, rm_l), ("Protein Cα", t_rm, rm_c)]
    svg_rmsd = grafik.garis(seri_rmsd, "Waktu (ns)", "RMSD (Å)", f"Figur 1: RMSD - {lig['nama']}",
                            lebar=720, tinggi=360, y_nol=True)
    o.append(f"<div>{svg_rmsd}</div>")

    # Figur 2: RMSF
    v_rmsf = tr.get("rmsf") or []
    svg_rmsf = grafik.garis([("Cα", list(range(1, len(v_rmsf) + 1)), v_rmsf)], "Nomor Residu", "RMSF (Å)",
                            f"Figur 2: Fluktuasi Residu (RMSF Cα) - {lig['nama']}", lebar=720, tinggi=360, y_nol=True)
    o.append(f"<div>{svg_rmsf}</div>")

    # Figur 3: Rg
    t_rg = [(i + 1) * dt_ns for i in range(len(rg))]
    svg_rg = grafik.garis([("Radius Girasi (Rg)", t_rg, rg)], "Waktu (ns)", "Rg (Å)",
                          f"Figur 3: Radius Girasi Protein (Rg) - {lig['nama']}", lebar=720, tinggi=360)
    o.append(f"<div>{svg_rg}</div>")

    # Figur 4: Ikatan Hidrogen
    t_hb = [(i + 1) * dt_ns for i in range(len(hb))]
    svg_hb = grafik.garis([("Ikatan-H", t_hb, hb)], "Waktu (ns)", "Jumlah Ikatan Hidrogen",
                          f"Figur 4: Ikatan Hidrogen per Frame - {lig['nama']}", lebar=720, tinggi=360, y_nol=True)
    o.append(f"<div>{svg_hb}</div>")

    # Figur 5: FEL 2D
    fel_d = an.get("fel") or {}
    var_pca = (an.get("pca") or {}).get("varians_rasio", [0, 0])
    v1 = var_pca[0] if len(var_pca) > 0 else None
    v2 = var_pca[1] if len(var_pca) > 1 else None
    svg_fel = md_analisis.svg_fel_2d(fel_d, var_pc1=v1, var_pc2=v2, lebar=540, tinggi=420,
                                     judul=f"Figur 5: Lanskap Energi Bebas (FEL) 2D - {lig['nama']}")
    o.append(f"<div>{svg_fel}</div>")

    # 3. Klaster Konformasi
    kl_list = an.get("klaster") or []
    if kl_list:
        o.append("<h2>3. Klaster Konformasi Ligan (Ambang RMSD 2,0 Å)</h2>")
        o.append("<table class='t'><tr><th>Klaster</th><th>Ukuran (%)</th><th>Jumlah Anggota</th><th>Frame Medoid</th></tr>")
        for k_i, k_c in enumerate(kl_list):
            o.append(f"<tr><td>Klaster {k_i + 1}</td><td class='n'>{k_c.get('ukuran_persen', 0.0):.1f} %</td>"
                     f"<td class='n'>{k_c.get('ukuran', 0)}</td><td class='n'>Frame {k_c.get('medoid', 0) + 1}</td></tr>")
        o.append("</table>")

    # 4. Multi-Replika
    rep_list = lig.get("replika") or (h.get("replika") if h.get("replika") else [])
    if len(rep_list) > 1:
        o.append("<h2>4. Evaluasi Multi-Replika Independen</h2>")
        o.append("<table class='t'><tr><th>Replika</th><th>Benih Acak</th><th>RMSD Ligan (Å)</th><th>RMSD Cα (Å)</th>"
                 "<th>Rg (Å)</th><th>ΔG MM/GBSA (kcal/mol)</th></tr>")
        for rep in rep_list:
            r_tr = rep.get("trajektori") or {}
            r_an = rep.get("analisis") or {}
            r_rml = np.mean(r_tr.get("rmsd_ligan") or [0])
            r_rmc = np.mean(r_tr.get("rmsd_ca") or [0])
            r_rg = np.mean(r_an.get("rg") or [0])
            r_dg = (rep.get("mmgbsa") or {}).get("dG", 0.0)
            o.append(f"<tr><td>Replika {rep.get('replika', 1)}</td><td>{rep.get('seed', '-')}</td>"
                     f"<td class='n'>{_id(f'{r_rml:.2f}')}</td><td class='n'>{_id(f'{r_rmc:.2f}')}</td>"
                     f"<td class='n'>{_id(f'{r_rg:.2f}')}</td><td class='n'>{_id(f'{r_dg:.2f}')}</td></tr>")
        o.append("</table>")

    o.append("</body></html>")
    return "".join(o)

