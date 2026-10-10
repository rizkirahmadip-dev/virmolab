"""Palet perintah (Ctrl+K): cari dan jalankan perintah menu mana pun dengan mengetik (rencana A9)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout


def kumpulkan(menubar):
    """[(jalur menu, QAction)] dari semua menu & submenu (tanpa pemisah/judul)."""
    out = []

    def jelajah(menu, jalur):
        for a in menu.actions():
            if a.isSeparator() or not a.text().strip():
                continue
            if a.menu():
                jelajah(a.menu(), jalur + [a.text().replace("&", "")])
            elif a.isVisible():
                out.append((" › ".join(jalur), a))
    for a in menubar.actions():
        if a.menu():
            jelajah(a.menu(), [a.text().replace("&", "")])
    return out


def _cocok(kueri, teks):
    """Semua kata kueri muncul (urutan bebas) -> skor (makin kecil makin baik), atau None."""
    t = teks.lower()
    skor = 0
    for k in kueri.lower().split():
        i = t.find(k)
        if i < 0:
            return None
        skor += i
    return skor


class DialogPalet(QDialog):
    def __init__(self, jw):
        super().__init__(jw, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("palet")
        self.setStyleSheet("#palet { border: 1px solid #2b6fd6; border-radius: 4px; }")
        self.resize(620, 420)
        g = jw.geometry()
        self.move(g.x() + (g.width() - 620) // 2, g.y() + 90)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        self.kotak = QLineEdit()
        self.kotak.setPlaceholderText("Ketik perintah… (mis. reseptor, ekspor sdf, mm/gbsa, tema)")
        self.kotak.textChanged.connect(self._saring)
        self.kotak.returnPressed.connect(self._jalankan)
        v.addWidget(self.kotak)
        self.daftar = QListWidget()
        self.daftar.itemActivated.connect(lambda *_: self._jalankan())
        v.addWidget(self.daftar, 1)
        ket = QLabel("↑/↓ pilih · Enter jalankan · Esc tutup")
        ket.setObjectName("muted")
        v.addWidget(ket)
        self.aksi = kumpulkan(jw.menuBar())
        self._saring("")
        self.kotak.installEventFilter(self)

    def eventFilter(self, obj, e):
        from PySide6.QtCore import QEvent
        if obj is self.kotak and e.type() == QEvent.KeyPress and e.key() in (Qt.Key_Down, Qt.Key_Up):
            r = self.daftar.currentRow() + (1 if e.key() == Qt.Key_Down else -1)
            self.daftar.setCurrentRow(max(0, min(self.daftar.count() - 1, r)))
            return True
        return super().eventFilter(obj, e)

    def _saring(self, q):
        self.daftar.clear()
        calon = []
        for jalur, a in self.aksi:
            teks = a.text().replace("&", "")
            s = _cocok(q, f"{teks} {jalur} {a.toolTip()}") if q.strip() else 0
            if s is None:
                continue
            calon.append((0 if q and q.lower() in teks.lower() else 1, s, jalur, teks, a))
        calon.sort(key=lambda x: (x[0], x[1], x[3]))
        for _p, _s, jalur, teks, a in calon[:80]:
            pint = a.shortcut().toString()
            it = QListWidgetItem(f"{teks}    —  {jalur}" + (f"    [{pint}]" if pint else ""))
            it.setData(Qt.UserRole, a)
            it.setToolTip(a.toolTip())
            if not a.isEnabled():
                it.setFlags(it.flags() & ~Qt.ItemIsEnabled)
            self.daftar.addItem(it)
        for r in range(self.daftar.count()):
            if self.daftar.item(r).flags() & Qt.ItemIsEnabled:
                self.daftar.setCurrentRow(r)
                break

    def _jalankan(self):
        it = self.daftar.currentItem()
        if not it or not (it.flags() & Qt.ItemIsEnabled):
            return
        a = it.data(Qt.UserRole)
        self.close()
        if a.isCheckable():
            a.toggle()
        else:
            a.trigger()
