"""Simulasi energi bebas relatif (RBFE) dengan OpenFE di WSL.

OpenFE (MIT) hanya berjalan di Linux/macOS, jadi VirmoLab menjalankannya di WSL seperti Boltz dan Uni-Dock
(dipasang build_tools/pasang_openfe_unidock_wsl.sh). Alur satu "run":

  1. siapkan_run: ligan (pose docking ber-H), protein, daftar tepi, dan pengaturan ditulis ke folder proyek
     rbfe/<run>/masukan; skrip WSL ikut ditulis.
  2. jalankan.sh (WSL): masukan disalin ke ~/virmolab-alat/rbfe/<run> (berkas simulasi besar tetap di ext4 WSL,
     tidak di drive Windows), transformasi OpenFE dibuat (pemetaan atom LOMAP, hybrid topology), lalu tiap kaki
     (pelarut, kompleks) dijalankan `openfe quickrun` berurutan. Hasil JSON disalin ke rbfe/<run>/hasil.
     Bisa dilanjutkan: kaki yang sudah punya hasil dilewati.
  3. kumpulkan: ΔΔG tiap tepi = ΔG kompleks − ΔG pelarut; ΔG relatif tiap ligan dari kuadrat terkecil
     berbobot (MLE) atas jaringan, dengan ligan pertama sebagai acuan 0.

Muatan parsial ligan: OpenFF NAGL (AmberTools tidak ikut paket conda OpenFE yang dipasang). Kecepatan terukur
di RTX 3060 Laptop: ±99 ns/hari untuk kaki kompleks TYK2, jadi protokol bawaan OpenFE (11 jendela × 5 ns × 3
repeat per kaki) butuh ±1,7 hari per kaki kompleks; mode "uji cepat" (0,5 ns, 1 repeat) ±1,3 jam.

Uji pemasangan (16 Okt 2026, RTX 3060 Laptop, mode uji cepat 0,5 ns × 1 repeat): tepi lig_ejm_31 -> lig_ejm_43
dari set tolok ukur TYK2 OpenFE memberi ΔΔG = +2,28 ± 0,95 kkal/mol (kaki kompleks 29,83 ± 0,85; kaki pelarut
27,55 ± 0,41), dibanding +1,28 kkal/mol dari Ki eksperimen (0,096 µM -> 0,84 µM; Liang dkk., Eur J Med Chem
2013;67:175-187). Arah perubahan benar dan selisihnya 1,0 kkal/mol, masih dalam galat statistik protokol
secepat itu; protokol bawaan (5 ns × 3 repeat) dipakai bila angkanya hendak dilaporkan.
"""
import json
import math
import re
import shlex
from pathlib import Path

from .lanjutan import ALAT, _wsl, _wsl_ada

PY = f"{ALAT}/openfe/bin/python"
OPENFE = f"{ALAT}/openfe/bin/openfe"
NS_PER_HARI_TERUKUR = 99.0      # kaki kompleks TYK2 (±4.700 atom berat + air), RTX 3060 Laptop, CUDA, HMR 3 amu
_status = {"diperiksa": False, "ada": False, "versi": ""}

SKRIP_SIAPKAN = r'''
"""Dibuat VirmoLab: transformasi OpenFE untuk tiap tepi (pelarut + kompleks)."""
import json, sys
from rdkit import Chem
import openfe
from openfe import SmallMoleculeComponent, ProteinComponent, SolventComponent
from openfe.protocols.openmm_rfe import RelativeHybridTopologyProtocol
from openff.units import unit
cfg = json.load(open("pengaturan.json"))
tepi = json.load(open("tepi.json"))
mols = {m.GetProp("_Name"): SmallMoleculeComponent(m) for m in Chem.SDMolSupplier("ligan.sdf", removeHs=False) if m}
teks = open("protein.pdb").read()
if not any(b.startswith("ATOM") and b[76:78].strip() == "H" for b in teks.splitlines()):
    # reseptor disiapkan tanpa PROPKA: hidrogen ditambahkan PDBFixer pada pH 7,4
    from pdbfixer import PDBFixer
    from openmm.app import PDBFile
    fx = PDBFixer(filename="protein.pdb")
    fx.findMissingResidues(); fx.missingResidues = {}
    fx.findMissingAtoms(); fx.addMissingAtoms(); fx.addMissingHydrogens(7.4)
    PDBFile.writeFile(fx.topology, fx.positions, open("protein.pdb", "w"), keepIds=True)
    print("PROTEIN_DIPROTONASI_PDBFIXER")
protein = ProteinComponent.from_pdb_file("protein.pdb")
mapper = openfe.LomapAtomMapper(max3d=1.0, element_change=False)
s = RelativeHybridTopologyProtocol.default_settings()
s.simulation_settings.equilibration_length = cfg["ns_ekuilibrasi"] * unit.nanosecond
s.simulation_settings.production_length = cfg["ns_produksi"] * unit.nanosecond
s.protocol_repeats = cfg["repeat"]
s.lambda_settings.lambda_windows = cfg["jendela"]
s.simulation_settings.n_replicas = cfg["jendela"]
s.engine_settings.compute_platform = cfg["platform"]
s.partial_charge_settings.partial_charge_method = "nagl"
s.partial_charge_settings.off_toolkit_backend = "rdkit"
rencana = []
for t in tepi:
    a, b = mols[t["a"]], mols[t["b"]]
    try:
        m = next(mapper.suggest_mappings(a, b))
    except StopIteration:
        rencana.append({"a": t["a"], "b": t["b"], "galat": "LOMAP tidak menemukan pemetaan atom"})
        continue
    skor = openfe.lomap_scorers.default_lomap_score(m)
    item = {"a": t["a"], "b": t["b"], "n_peta": len(m.componentA_to_componentB), "skor_lomap": round(skor, 3), "kaki": {}}
    for kaki, ka, kb in (("pelarut", {"ligand": a, "solvent": SolventComponent()}, {"ligand": b, "solvent": SolventComponent()}),
                         ("kompleks", {"ligand": a, "protein": protein, "solvent": SolventComponent()},
                                      {"ligand": b, "protein": protein, "solvent": SolventComponent()})):
        tr = openfe.Transformation(stateA=openfe.ChemicalSystem(ka), stateB=openfe.ChemicalSystem(kb), mapping=m,
                                   protocol=RelativeHybridTopologyProtocol(s), name=f"{t['a']}__{t['b']}__{kaki}")
        nama = f"{t['a']}__{t['b']}__{kaki}"
        tr.to_json(f"transformasi/{nama}.json")
        item["kaki"][kaki] = nama
    rencana.append(item)
json.dump(rencana, open("rencana.json", "w"), indent=1)
print("RENCANA", len(rencana))
'''


def status(segar=False):
    """{ada, versi, pesan}; memanggil WSL hanya sekali (atau bila segar=True)."""
    if segar or not _status["diperiksa"]:
        _status["diperiksa"] = True
        _status["ada"] = _wsl_ada(f"test -x {OPENFE} && echo ADA")
        if _status["ada"]:
            try:
                p = _wsl(f"{OPENFE} --version", timeout=60)
                _status["versi"] = (p.stdout or "").strip().splitlines()[-1] if p.stdout else ""
            except Exception:
                _status["versi"] = ""
    pesan = (f"{_status['versi'] or 'OpenFE'} siap di WSL. Simulasi berjalan di GPU NVIDIA lewat WSL; hasil "
             "disalin ke folder proyek rbfe/." if _status["ada"] else
             "OpenFE belum terpasang di WSL. Pasang dengan build_tools/pasang_openfe_unidock_wsl.sh "
             "(conda-forge, ±5 GB). Tanpa itu dialog ini hanya menyusun jaringan dan menganalisis hasil.")
    return {"ada": _status["ada"], "versi": _status["versi"], "pesan": pesan}


def pose_dari_baris(proyek, baris):
    """Pose terbaik satu ligan (baris ekspor.baris_hasil) sebagai blok MOL ber-H dengan koordinat docking."""
    from rdkit import Chem
    from . import analisis
    from . import mesin as M
    j = next(x for x in proyek.job if x["id"] == baris["job"])
    l = next(x for x in j["ligan"] if x["id"] == baris["lid"])
    pembaca = "vina" if j["mesin"] in ("vina", "unidock") else j["mesin"]
    pose = M.baca_hasil(pembaca, proyek.p(l["keluaran"]))
    mol = analisis.pose_mol(proyek.p(l["pdbqt"]).read_text(), pose[0].pdbqt)
    return Chem.MolToMolBlock(mol)


def reseptor_untuk_rbfe(proyek):
    """(teks PDB protein, catatan). PDB keluaran PROPKA/PDB2PQR (sudah ber-H) bila ada; kalau tidak PDB bersih dan
    hidrogennya ditambahkan PDBFixer di WSL. Kofaktor dan ion logam tidak ikut: medan gaya OpenFE untuk protein
    tidak memuat parameternya."""
    r = proyek.reseptor or {}
    catatan = []
    for k in ("meeko", "bersih"):
        if r.get(k) and proyek.p(r[k]).exists():
            teks = proyek.p(r[k]).read_text(encoding="utf-8", errors="replace")
            baris = [b for b in teks.splitlines() if b.startswith(("ATOM", "TER", "END"))]
            if any(b.startswith("HETATM") for b in teks.splitlines()) or r.get("logam"):
                catatan.append("kofaktor, ion logam, dan air tidak ikut simulasi RBFE")
            if not any(b.startswith("ATOM") and b[76:78].strip() == "H" for b in baris):
                catatan.append("hidrogen protein ditambahkan PDBFixer pH 7,4 (reseptor disiapkan tanpa PROPKA)")
            return "\n".join(baris) + "\n", catatan
    raise ValueError("Reseptor proyek belum disiapkan.")


def _nama_aman(n):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", n)[:60] or "ligan"


def siapkan_run(folder_run, ligan, protein_pdb, tepi, ns_produksi=5.0, ns_ekuilibrasi=1.0, repeat=3,
                jendela=11, platform="CUDA"):
    """ligan: [(nama, molblock ber-H dengan koordinat pose)]; tepi: [(nama_a, nama_b)].
    Nama ligan diseragamkan agar aman di jalur Linux. -> dict ringkasan run (juga ditulis ke run.json)."""
    from .unidock import jalur_wsl
    folder = Path(folder_run)
    masuk = folder / "masukan"
    (folder / "hasil").mkdir(parents=True, exist_ok=True)
    masuk.mkdir(parents=True, exist_ok=True)
    peta_nama, blok = {}, []
    for nama, mb in ligan:
        aman = _nama_aman(nama)
        while aman in peta_nama.values():
            aman += "_"
        peta_nama[nama] = aman
        baris = mb.splitlines()
        baris[0] = aman
        blok.append("\n".join(baris).rstrip() + "\n$$$$\n")
    (masuk / "ligan.sdf").write_bytes("".join(blok).encode("utf-8"))
    (masuk / "protein.pdb").write_bytes(protein_pdb.replace("\r\n", "\n").encode("utf-8"))
    (masuk / "tepi.json").write_bytes(json.dumps([{"a": peta_nama[a], "b": peta_nama[b]} for a, b in tepi]).encode())
    cfg = {"ns_produksi": float(ns_produksi), "ns_ekuilibrasi": float(ns_ekuilibrasi), "repeat": int(repeat),
           "jendela": int(jendela), "platform": platform}
    (masuk / "pengaturan.json").write_bytes(json.dumps(cfg).encode())
    (masuk / "siapkan.py").write_bytes(SKRIP_SIAPKAN.encode("utf-8"))
    run_id = _nama_aman(folder.name)
    kerja = f"{ALAT}/rbfe/{run_id}"
    win_masuk, win_hasil = jalur_wsl(masuk), jalur_wsl(folder / "hasil")
    sh = f"""#!/bin/bash
# Dibuat VirmoLab. Jalankan ulang untuk melanjutkan: kaki yang sudah punya hasil dilewati.
set -u
W={kerja}
mkdir -p "$W/transformasi" "$W/hasil" "$W/log" "$W/kerja"
cp -n {shlex.quote(win_masuk)}/* "$W/"
cd "$W"
if [ ! -f rencana.json ]; then
  echo "TAHAP siapkan"
  {PY} siapkan.py > log/siapkan.log 2>&1 || {{ echo "GAGAL siapkan"; tail -n 20 log/siapkan.log; exit 3; }}
fi
for t in transformasi/*.json; do
  n=$(basename "$t" .json)
  if [ -f "hasil/$n.json" ]; then echo "LEWAT $n"; continue; fi
  echo "MULAI $n"
  {OPENFE} quickrun "$W/$t" -o "$W/hasil/$n.json" -d "$W/kerja/$n" > "log/$n.log" 2>&1
  kode=$?
  echo "SELESAI $n $kode"
  [ -f "hasil/$n.json" ] && cp "hasil/$n.json" {shlex.quote(win_hasil)}/
done
cp rencana.json {shlex.quote(win_hasil)}/ 2>/dev/null
echo "SEMUA_SELESAI"
"""
    (folder / "jalankan.sh").write_bytes(sh.encode("utf-8"))
    info = {"run": run_id, "kerja_wsl": kerja, "peta_nama": peta_nama, "tepi": [[a, b] for a, b in tepi],
            "pengaturan": cfg}
    (folder / "run.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


def perintah_jalan(folder_run):
    from .unidock import jalur_wsl
    return ["wsl", "-e", "bash", jalur_wsl(Path(folder_run) / "jalankan.sh")]


def perintah_jalan_terlepas(folder_run):
    """Untuk QProcess.startDetached: keluaran ditulis ke rbfe/<run>/jalan.log (dibaca dialog), sehingga run tetap
    berjalan dan terpantau walau dialog atau VirmoLab ditutup."""
    from .unidock import jalur_wsl
    sh, log = jalur_wsl(Path(folder_run) / "jalankan.sh"), jalur_wsl(Path(folder_run) / "jalan.log")
    return ["wsl", "-e", "bash", "-c", f"bash {shlex.quote(sh)} > {shlex.quote(log)} 2>&1"]


def hentikan(run_id):
    """Hentikan run di WSL (skrip dan quickrun yang sedang berjalan). Kaki yang selesai tetap tersimpan."""
    # pola [x]yz: perintah pkill sendiri tidak cocok dengan polanya, jadi bash pembungkusnya tidak ikut terbunuh
    pola = f"rbfe/[{run_id[0]}]{run_id[1:]}"
    return _wsl(f"pkill -f '{pola}' ; true", timeout=60)


def kemajuan(folder_run):
    """Persen dan perkiraan sisa waktu kaki yang sedang berjalan (dibaca dari berkas analisis OpenFE di WSL)."""
    info = json.loads((Path(folder_run) / "run.json").read_text(encoding="utf-8"))
    w = info["kerja_wsl"]
    cmd = (f'cd {w} 2>/dev/null || exit 0; for f in kerja/*/shared_*Simulation*/simulation_real_time_analysis.yaml; '
           f'do [ -f "$f" ] || continue; n=$(echo "$f" | cut -d/ -f2); '
           f'p=$(grep percent_complete "$f" | tail -1 | awk \'{{print $2}}\'); '
           f'e=$(grep estimated_time_remaining "$f" | tail -1 | cut -d"\'" -f2); echo "$n|$p|$e"; done; '
           f'ls hasil 2>/dev/null | sed "s/^/HASIL|/"')
    try:
        p = _wsl(cmd, timeout=60)
    except Exception:
        return {}
    keluar = {}
    for b in (p.stdout or "").splitlines():
        s = b.split("|")
        if s[0] == "HASIL" and len(s) > 1:
            keluar.setdefault(s[1].replace(".json", ""), {})["selesai"] = True
        elif len(s) == 3:
            try:
                keluar.setdefault(s[0], {}).update(persen=float(s[1] or 0), sisa=s[2])
            except ValueError:
                pass
    return keluar


def _nilai(q):
    return float(q["magnitude"]) if isinstance(q, dict) and "magnitude" in q else None


def baca_hasil_kaki(path):
    """JSON quickrun -> (ΔG kcal/mol, galat kcal/mol, pengaturan). Galat = sebaran antar-repeat bila >1 repeat,
    kalau tidak galat MBAR repeat tunggal."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    est, unc = _nilai(d.get("estimate")), _nilai(d.get("uncertainty"))
    mbar, setel = [], {}
    for daftar in ((d.get("protocol_result") or {}).get("data") or {}).values():
        for u in daftar:
            o = u.get("outputs") or {}
            if "unit_estimate_error" in o:
                mbar.append(_nilai(o["unit_estimate_error"]))
            if not setel:
                setel = ((u.get("inputs") or {}).get("protocol") or {}).get("settings") or {}
    if (unc is None or unc == 0.0) and mbar:
        unc = math.sqrt(sum(x * x for x in mbar if x is not None)) / max(1, len(mbar))
    return est, unc, setel


def versi_hasil(path):
    """Versi perangkat lunak yang menjalankan kaki ini ({openfe, gufe, openmm}). OpenFE mencatatnya di keluaran unit
    penyiapan pada JSON hasil, jadi angkanya dibaca dari hasil nyata, bukan dari paket yang kebetulan terpasang."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    v = {}
    for u in (d.get("unit_results") or {}).values():
        o = u.get("outputs") or {}
        for sumber, kunci in (("openfe_version", "openfe"), ("gufe_version", "gufe"), ("openmm_version", "openmm")):
            if o.get(sumber) and kunci not in v:
                v[kunci] = str(o[sumber])
    return v


def kumpulkan(folder_run):
    """-> {tepi: [{a, b, ddg, galat, dg_kompleks, dg_pelarut}], ligan: {nama: (dg_rel, galat)}, setel, versi}."""
    folder = Path(folder_run)
    info = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    balik = {v: k for k, v in info["peta_nama"].items()}
    hasil, setel, versi = [], {}, {}
    for a, b in info["tepi"]:
        aa, bb = info["peta_nama"][a], info["peta_nama"][b]
        fk, fp = folder / "hasil" / f"{aa}__{bb}__kompleks.json", folder / "hasil" / f"{aa}__{bb}__pelarut.json"
        row = {"a": a, "b": b, "ddg": None, "galat": None}
        if fk.exists() and fp.exists():
            gk, ek, setel = baca_hasil_kaki(fk)
            gp, ep, _ = baca_hasil_kaki(fp)
            if gk is not None and gp is not None:
                row.update(ddg=gk - gp, galat=math.hypot(ek or 0.0, ep or 0.0), dg_kompleks=gk, dg_pelarut=gp)
                versi = versi or versi_hasil(fk)
        hasil.append(row)
    lig = mle([r for r in hasil if r["ddg"] is not None], [balik.get(v, v) for v in info["peta_nama"].values()])
    return {"tepi": hasil, "ligan": lig, "setel": setel, "versi": versi}


def paragraf_metode(h, en=None):
    """Paragraf metode dari run OpenFE yang benar-benar selesai. Perangkat lunak dan pengaturan dibaca dari JSON
    hasil (kumpulkan), bukan dari rencana di dialog, supaya yang tertulis di naskah sama dengan yang dijalankan.
    Kosong bila belum ada tepi yang selesai atau pengaturan di JSON tidak lengkap (pemanggil lalu memakai paragraf
    rencana); paragraf separuh jadi lebih berbahaya daripada tidak ada."""
    try:
        return _paragraf_metode(h, en)
    except (KeyError, TypeError, ValueError, AttributeError):
        return ""


def _paragraf_metode(h, en):
    from .. import i18n
    from .rbfe import LABEL_EKSPERIMENTAL, LABEL_EKSPERIMENTAL_EN
    en = i18n.inggris() if en is None else en
    s = h.get("setel") or {}
    selesai = [t for t in h.get("tepi", []) if t.get("ddg") is not None]
    if not selesai or not s:
        return ""

    def g(grup, kunci):
        v = (s.get(grup) or {}).get(kunci)
        return float(v["magnitude"]) if isinstance(v, dict) and "magnitude" in v else v

    def a(x, d=2):
        """Angka dengan desimal sesuai bahasa; bilangan bulat tanpa nol di belakang."""
        t = f"{float(x):.{d}f}".rstrip("0").rstrip(".")
        return t if en else t.replace(".", ",")

    v = h.get("versi") or {}
    ff = ((s.get("forcefield_settings") or {}).get("forcefields")) or []
    protein = "Amber ff14SB" if any("ff14SB" in f for f in ff) else ", ".join(ff[:2])
    air = {"tip3p": "TIP3P", "tip4pew": "TIP4P-Ew", "spce": "SPC/E"}.get(str(g("solvation_settings", "solvent_model")),
                                                                        str(g("solvation_settings", "solvent_model")))
    ligan_ff = (s.get("forcefield_settings") or {}).get("small_molecule_forcefield") or "OpenFF"
    muatan = {"nagl": "OpenFF NAGL", "am1bcc": "AM1-BCC", "am1bccelf10": "AM1-BCC ELF10", "espaloma": "espaloma"}.get(
        str(g("partial_charge_settings", "partial_charge_method") or "nagl").lower(), "OpenFF NAGL")
    n_win = g("lambda_settings", "lambda_windows")
    ulang = s.get("protocol_repeats") or 1
    perangkat = f"OpenFE {v['openfe']}" if v.get("openfe") else "OpenFE"
    if v.get("openmm"):
        perangkat += f" (OpenMM {v['openmm']}, {g('engine_settings', 'compute_platform') or 'GPU'})"
    n_tepi = len(selesai)
    if en:
        return (f"Relative binding free energies were computed with the {perangkat} RelativeHybridTopologyProtocol: "
                f"hybrid-topology alchemical transformations with {a(n_win, 0)} lambda windows and Hamiltonian replica "
                f"exchange, each leg (complex and solvent) repeated {ulang} time(s). Proteins were described with "
                f"{protein} and {air} water, ligands with {ligan_ff}, and ligand partial charges came from {muatan}. "
                f"Systems were solvated in a {g('solvation_settings', 'box_shape')} box with "
                f"{a(g('solvation_settings', 'solvent_padding'), 1)} nm padding; long-range electrostatics used PME "
                f"({a(g('forcefield_settings', 'nonbonded_cutoff'), 1)} nm cutoff), hydrogen masses were repartitioned "
                f"to {a(g('forcefield_settings', 'hydrogen_mass'), 1)} amu with a {a(g('integrator_settings', 'timestep'), 0)}"
                f" fs time step, at {a(g('thermo_settings', 'temperature'), 2)} K and "
                f"{a(g('thermo_settings', 'pressure'), 0)} bar (Langevin integrator, Monte Carlo barostat). Each window "
                f"ran {a(g('simulation_settings', 'equilibration_length'))} ns of equilibration and "
                f"{a(g('simulation_settings', 'production_length'))} ns of production. Free energies of each leg were "
                f"estimated with MBAR; the ddG of each of the {n_tepi} edges is dG(complex) - dG(solvent), and relative "
                f"dG values per ligand come from a maximum-likelihood estimate over the network. "
                + LABEL_EKSPERIMENTAL_EN)
    return (f"Energi bebas ikatan relatif dihitung dengan RelativeHybridTopologyProtocol {perangkat}: transformasi "
            f"alkimia topologi hibrid dengan {a(n_win, 0)} jendela lambda dan pertukaran replika Hamiltonian, tiap kaki "
            f"(kompleks dan pelarut) diulang {ulang} kali. Protein dimodelkan dengan {protein} dan air {air}, ligan "
            f"dengan {ligan_ff}, dan muatan parsial ligan dari {muatan}. Sistem dilarutkan dalam kotak "
            f"{g('solvation_settings', 'box_shape')} dengan jarak pelarut {a(g('solvation_settings', 'solvent_padding'), 1)} "
            f"nm; interaksi elektrostatik jarak jauh memakai PME (cutoff {a(g('forcefield_settings', 'nonbonded_cutoff'), 1)}"
            f" nm), massa hidrogen disetel ulang menjadi {a(g('forcefield_settings', 'hydrogen_mass'), 1)} amu dengan "
            f"langkah waktu {a(g('integrator_settings', 'timestep'), 0)} fs, pada {a(g('thermo_settings', 'temperature'), 2)} "
            f"K dan {a(g('thermo_settings', 'pressure'), 0)} bar (integrator Langevin, barostat Monte Carlo). Tiap "
            f"jendela dijalankan {a(g('simulation_settings', 'equilibration_length'))} ns ekuilibrasi dan "
            f"{a(g('simulation_settings', 'production_length'))} ns produksi. Energi bebas tiap kaki diestimasi dengan "
            f"MBAR; ΔΔG tiap tepi ({n_tepi} tepi) adalah ΔG(kompleks) − ΔG(pelarut), dan ΔG relatif tiap ligan berasal "
            f"dari estimasi kemungkinan maksimum atas jaringan. " + LABEL_EKSPERIMENTAL)


def mle(tepi, nama):
    """ΔG relatif tiap ligan dari kuadrat terkecil berbobot 1/σ² atas tepi (ligan pertama = 0).
    Galat dari diagonal invers matriks Fisher. Ligan yang tidak tersambung diberi None."""
    import numpy as np
    if not tepi:
        return {}
    idx = {n: i for i, n in enumerate(nama)}
    n = len(nama)
    F = np.zeros((n, n))
    z = np.zeros(n)
    for t in tepi:
        i, j = idx[t["a"]], idx[t["b"]]
        w = 1.0 / max(t["galat"] or 0.1, 0.1) ** 2
        F[i, i] += w
        F[j, j] += w
        F[i, j] -= w
        F[j, i] -= w
        z[j] += w * t["ddg"]
        z[i] -= w * t["ddg"]
    # komponen terhubung ke ligan acuan
    terhubung = {0}
    ubah = True
    while ubah:
        ubah = False
        for t in tepi:
            i, j = idx[t["a"]], idx[t["b"]]
            if (i in terhubung) != (j in terhubung):
                terhubung |= {i, j}
                ubah = True
    pakai = sorted(terhubung)
    keluar = {nm: (None, None) for nm in nama}
    keluar[nama[0]] = (0.0, 0.0)
    if len(pakai) < 2:
        return keluar
    sub = [k for k in pakai if k != 0]
    Fs = F[np.ix_(sub, sub)]
    zs = z[sub]
    try:
        inv = np.linalg.inv(Fs)
    except np.linalg.LinAlgError:
        return keluar
    g = inv @ zs
    for k, i in enumerate(sub):
        keluar[nama[i]] = (float(g[k]), float(math.sqrt(max(inv[k, k], 0.0))))
    return keluar


def ddg_eksperimen(ki_a_um, ki_b_um, suhu=298.15):
    """ΔΔG eksperimen (b − a) dari Ki/IC50 dalam satuan yang sama."""
    return 0.0019872 * suhu * math.log(ki_b_um / ki_a_um)
