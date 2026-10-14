# -*- mode: python -*-
# Build: .venv\Scripts\pyinstaller build_tools\virmolab.spec --noconfirm --distpath dist --workpath build
import re
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

AKAR = Path(SPECPATH).parent
versi = re.search(r'__version__ = "([^"]+)"', (AKAR / "virmolab" / "__init__.py").read_text()).group(1)
a_, b_, c_ = (versi.split(".") + ["0", "0"])[:3]
info = (AKAR / "build_tools" / "versi.txt.in").read_text()
for k, v in (("@A@", a_), ("@B@", b_), ("@C@", c_), ("@V@", versi)):
    info = info.replace(k, v)
(AKAR / "build" ).mkdir(exist_ok=True)
(AKAR / "build" / "versi.txt").write_text(info)

datas = [(str(AKAR / "virmolab" / "viewer"), "virmolab/viewer"),
         (str(AKAR / "virmolab" / "aset"), "virmolab/aset"),
         (str(AKAR / "docs"), "docs"),
         (str(AKAR / "licenses"), "licenses"),
         (str(AKAR / "LICENSE"), "."),
         (str(AKAR / "CHANGELOG.md"), "."),
         (str(AKAR / "LISENSI_PIHAK_KETIGA.txt"), ".")]
# program mesin & Open Babel (dipanggil sebagai proses terpisah) -> _internal/bin
for f in (AKAR / "vendor" / "bin").rglob("*"):
    if f.is_file():
        datas.append((str(f), str(Path("bin") / f.parent.relative_to(AKAR / "vendor" / "bin"))))
datas += collect_data_files("meeko") + collect_data_files("rdkit", includes=["Data/*.fdef", "Data/*.txt", "Data/*.csv"])  # csv: deskriptor fr_* (ADMET-AI)
datas += collect_data_files("posebusters")   # config/*.yml (konfigurasi uji)
datas += collect_data_files("dimorphite_dl")  # smarts/site_substructures.smarts (aturan pKa)
datas += collect_data_files("pdb2pqr") + collect_data_files("propka")   # topologi/forcefield & parameter pKa
datas += collect_data_files("admet_ai") + collect_data_files("chemprop") + collect_data_files("descriptastorus")
datas += collect_data_files("lightning") + collect_data_files("lightning_fabric")
datas += [(str(AKAR / "virmolab" / "i18n" / "en.json"), "virmolab/i18n")]
datas += [(str(AKAR / "virmolab" / "data" / "nama_tanaman_id.csv"), "virmolab/data")]   # nama lokal tanaman obat (F1)
# Wajib ada: tanpa ini fitur terpasang rusak diam-diam, jadi build harus gagal bila folder hilang
for _d in ("panel_target", "gmt"):   # panel target penargetan balik (F3), set gen Reactome/GO (F3b)
    assert (AKAR / "virmolab" / "data" / _d).is_dir(), f"virmolab/data/{_d} tidak ada"
    datas += [(str(AKAR / "virmolab" / "data" / _d), f"virmolab/data/{_d}")]
# cuik_molmaker (chemprop; Apache-2.0) memuat .pyd lewat os.listdir di folder paketnya -> salin apa adanya
_cuik = Path(__import__("cuik_molmaker").__file__).parent
binaries = [(str(f), "cuik_molmaker") for f in _cuik.iterdir() if f.suffix in (".pyd", ".dll")]
datas += collect_data_files("cuik_molmaker")
# Ketcher standalone (editor struktur, Apache-2.0) -> _internal/ketcher
for f in (AKAR / "vendor" / "ketcher").rglob("*"):
    if f.is_file():
        datas.append((str(f), str(Path("ketcher") / f.parent.relative_to(AKAR / "vendor" / "ketcher"))))
hidden = collect_submodules("meeko") + collect_submodules("dimorphite_dl") + ["gemmi", "openpyxl", "rdkit.Chem.ChemicalFeatures"]
hidden += collect_submodules("pdb2pqr") + collect_submodules("propka") + collect_submodules("admet_ai")
hidden += collect_submodules("chemprop") + ["rdkit.Chem.Pharm2D.Gobbi_Pharm2D", "rdkit.Chem.Pharm2D.Generate"]
# QSAR (core/qsar.py): scikit-learn memuat estimator lewat nama modul, joblib dipakai menyimpan model
hidden += collect_submodules("sklearn") + ["joblib", "scipy.stats", "scipy.special.cython_special"]
# F4 (rdShapeAlign, pekerja ProcessPoolExecutor) dan F12 (fit 4PL scipy.optimize.curve_fit)
hidden += ["rdkit.Chem.rdShapeAlign", "scipy.optimize", "concurrent.futures.process"]

# ---- MD & MM/GBSA (core/md.py): OpenMM + PDBFixer + openmmforcefields + OpenFF (toolkit, Interchange, NAGL)
import openmm as _omm  # noqa: E402
from PyInstaller.utils.hooks import copy_metadata  # noqa: E402
_omm_lib = Path(_omm.__file__).parent.parent / "OpenMM.libs" / "lib"
# openmm/version.py mencari plugin di openmm/../OpenMM.libs/lib/plugins (relatif) -> pertahankan tata letak itu
binaries += [(str(f), "OpenMM.libs/lib") for f in _omm_lib.glob("*.dll")]
binaries += [(str(f), "OpenMM.libs/lib/plugins") for f in (_omm_lib / "plugins").glob("*.dll")]
datas += collect_data_files("openmm", includes=["app/data/amber14/*", "app/data/amber14-all.xml", "app/data/implicit/*",
                                                "app/data/pdbNames.xml", "app/data/residues.xml",
                                                "app/data/hydrogens.xml", "app/data/tip3p.xml",
                                                "app/data/tip3p.pdb"])   # kotak air Modeller.addSolvent
datas += collect_data_files("pdbfixer", includes=["templates/*", "soft.xml"])
datas += collect_data_files("openff.units") + collect_data_files("openff.utilities")
_off = Path(__import__("openforcefields").__file__).parent / "offxml" / "openff-2.3.0.offxml"
datas += [(str(_off), "openforcefields/offxml")]     # Sage 2.3.0 (CC BY 4.0); berkas lain tidak dipakai
_nagl = Path(__import__("openff.nagl_models", fromlist=["x"]).__file__).parent / "models" / "am1bcc"
datas += [(str(_nagl / "openff-gnn-am1bcc-1.0.0.pt"), "openff/nagl_models/models/am1bcc")]
for _d in ("openmm", "pdbfixer", "openmmforcefields", "openff-toolkit", "openff-interchange", "openff-units",
           "openff-utilities", "openff-nagl", "openff-nagl-models", "openforcefields", "pint", "pydantic",
           "flexcache", "flexparser"):
    datas += copy_metadata(_d)
_bukan_uji = lambda n: ".tests" not in n and "._tests" not in n and not n.endswith(".conftest")  # noqa: E731
hidden += collect_submodules("openmm") + collect_submodules("pdbfixer", filter=lambda n: "uiserver" not in n)
hidden += collect_submodules("openmmforcefields.generators", filter=_bukan_uji)
for _p in ("openff.toolkit", "openff.interchange", "openff.units", "openff.utilities", "openff.nagl",
           "openff.nagl_models"):
    hidden += collect_submodules(_p, filter=_bukan_uji)
hidden += ["openforcefields", "lxml.etree", "xmltodict", "cachetools", "constraint"]
# ParmEd 4.3.1 (LGPL): topologi GROMACS. Tanpa ekstensi _rdparm.
datas += collect_data_files("parmed")
datas += copy_metadata("ParmEd")
hidden += collect_submodules("parmed", filter=_bukan_uji)

# dua titik masuk berbagi satu PYZ/_internal: VirmoLab.exe (jendela) + VirmoLab-cli.exe (konsol, virmolab/cli.py)
a = Analysis([str(AKAR / "VirmoLab.pyw"), str(AKAR / "VirmoLab_cli.py")], pathex=[str(AKAR)], datas=datas,
             binaries=binaries, hiddenimports=hidden,
             excludes=["openbabel", "tkinter", "IPython", "pytest", "PySide6.Qt3DCore", "PySide6.QtCharts",
                       "PySide6.QtDataVisualization", "PySide6.QtQuick3D", "PySide6.QtSql", "PySide6.QtMultimediaWidgets",
                       "PySide6.QtTest", "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors",
                       "PySide6.QtSerialPort", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtLocation",
                       "PySide6.QtGraphs", "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech"],
             # modul Python sebagai .pyc di _internal (bukan PYZ di dalam exe): dipakai bersama kedua exe,
             # tanpa ini tiap exe membawa salinan PYZ ±70 MB
             noarchive=True)


def buang(tujuan):
    """Berkas Qt yang tidak dipakai VirmoLab (hemat ± 150 MB)."""
    d = tujuan.replace("\\", "/")
    if d.startswith("PySide6/qml/") or d.startswith("docs/_sumber"):
        return True
    # data DrugBank (CC BY-NC) tidak dipakai (drugbank_path=None); PaDEL (Java) tidak dipakai ADMET-AI
    if d.endswith("admet_ai/resources/data/drugbank_approved.csv") or d.startswith("padelpy/PaDEL"):
        return True
    # OpenMM: pustaka impor (.lib) & header C++ tidak diperlukan saat berjalan
    if d.startswith("OpenMM.libs/") and (d.endswith(".lib") or "/include/" in d):
        return True
    if re.search(r"PySide6/resources/.*\.debug\.(pak|bin)$", d) or "qtwebengine_devtools_resources" in d:
        return True
    if d.startswith("PySide6/translations/"):
        nama = d.rsplit("/", 1)[-1]
        if "/qtwebengine_locales/" in d:
            return nama not in ("en-US.pak", "id.pak")
        return not nama.endswith("_id.qm")
    return False


a.datas = [x for x in a.datas if not buang(x[0])]
a.binaries = [x for x in a.binaries if not buang(x[0])]
pyz = PYZ(a.pure)
# a.scripts = hook runtime + kedua skrip; tiap EXE hanya menjalankan skrip miliknya
skrip_gui = [s for s in a.scripts if s[0] != "VirmoLab_cli"]
skrip_cli = [s for s in a.scripts if s[0] != "VirmoLab"]
exe = EXE(pyz, skrip_gui, [], exclude_binaries=True, name="VirmoLab", console=False,
          icon=str(AKAR / "virmolab" / "aset" / "virmolab.ico"), version=str(AKAR / "build" / "versi.txt"),
          upx=False)
exe_cli = EXE(pyz, skrip_cli, [], exclude_binaries=True, name="VirmoLab-cli", console=True,
              icon=str(AKAR / "virmolab" / "aset" / "virmolab.ico"), version=str(AKAR / "build" / "versi.txt"),
              upx=False)
coll = COLLECT(exe, exe_cli, a.binaries, a.datas, name="VirmoLab", upx=False)
