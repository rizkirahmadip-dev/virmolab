import sys
from PySide6.QtWidgets import QApplication
from virmolab.app import siapkan_kimia
siapkan_kimia()
app = QApplication(sys.argv); app.setStyle("Fusion")
from virmolab.ui import theme
from virmolab.core import molekul
app.setPalette(theme.palet("terang")); app.setStyleSheet(theme.qss("terang").replace("ICON_CHECK", ""))
from virmolab.ui.dialog_reseptor import DialogReseptor
from virmolab.ui.dialog_ligan import DialogLigan
from pathlib import Path
Path("dev/uji/gambar").mkdir(parents=True, exist_ok=True)  # keluaran gambar uji
objs = molekul.baca_teks_struktur(open("dev/uji/1HSG.pdb").read(), "1HSG")
prot = [o for o in objs if o.jenis == "protein"]
d = DialogReseptor(prot, {prot[0].id: ["ZN A301"]}); d.show(); app.processEvents(); d.grab().save("dev/uji/gambar/dlg_reseptor.png")
print(d.opsi())
lig = [o for o in objs if o.jenis == "ligan"] + molekul.dari_smiles("CC(=O)Oc1ccccc1C(=O)O", "aspirin")
d2 = DialogLigan(lig); d2.show(); app.processEvents(); d2.grab().save("dev/uji/gambar/dlg_ligan.png")
