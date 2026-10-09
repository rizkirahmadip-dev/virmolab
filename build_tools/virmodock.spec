# -*- mode: python -*-
# Build: .venv\Scripts\pyinstaller build_tools\virmodock.spec --noconfirm --distpath dist --workpath build
import re
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

AKAR = Path(SPECPATH).parent
versi = re.search(r'__version__ = "([^"]+)"', (AKAR / "virmodock" / "__init__.py").read_text()).group(1)
a_, b_, c_ = (versi.split(".") + ["0", "0"])[:3]
info = (AKAR / "build_tools" / "versi.txt.in").read_text()
for k, v in (("@A@", a_), ("@B@", b_), ("@C@", c_), ("@V@", versi)):
    info = info.replace(k, v)
(AKAR / "build" ).mkdir(exist_ok=True)
(AKAR / "build" / "versi.txt").write_text(info)

datas = [(str(AKAR / "virmodock" / "viewer"), "virmodock/viewer"),
         (str(AKAR / "virmodock" / "aset"), "virmodock/aset"),
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
datas += [(str(AKAR / "virmodock" / "i18n" / "en.json"), "virmodock/i18n")]
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

# dua titik masuk berbagi satu PYZ/_internal: VirmoDock.exe (jendela) + VirmoDock-cli.exe (konsol, virmodock/cli.py)
a = Analysis([str(AKAR / "VirmoDock.pyw"), str(AKAR / "VirmoDock_cli.py")], pathex=[str(AKAR)], datas=datas,
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
    """Berkas Qt yang tidak dipakai VirmoDock (hemat ± 150 MB)."""
    d = tujuan.replace("\\", "/")
    if d.startswith("PySide6/qml/") or d.startswith("docs/_sumber"):
        return True
    # data DrugBank (CC BY-NC) tidak dipakai (drugbank_path=None); PaDEL (Java) tidak dipakai ADMET-AI
    if d.endswith("admet_ai/resources/data/drugbank_approved.csv") or d.startswith("padelpy/PaDEL"):
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
skrip_gui = [s for s in a.scripts if s[0] != "VirmoDock_cli"]
skrip_cli = [s for s in a.scripts if s[0] != "VirmoDock"]
exe = EXE(pyz, skrip_gui, [], exclude_binaries=True, name="VirmoDock", console=False,
          icon=str(AKAR / "virmodock" / "aset" / "virmodock.ico"), version=str(AKAR / "build" / "versi.txt"),
          upx=False)
exe_cli = EXE(pyz, skrip_cli, [], exclude_binaries=True, name="VirmoDock-cli", console=True,
              icon=str(AKAR / "virmodock" / "aset" / "virmodock.ico"), version=str(AKAR / "build" / "versi.txt"),
              upx=False)
coll = COLLECT(exe, exe_cli, a.binaries, a.datas, name="VirmoDock", upx=False)
