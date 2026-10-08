"""Tema VirmoDock: palet netral, satu aksen biru, mode terang dan gelap.

Semua warna antarmuka didefinisikan di sini sebagai token, lalu dirangkai
menjadi Qt Style Sheet. Widget lain cukup memakai objectName / property.
"""
from PySide6.QtGui import QColor, QPalette

TOKEN = {
    "terang": {
        "chrome": "#e9ecf1", "panel": "#f6f7f9", "surf": "#ffffff", "line": "#d3d9e1", "line2": "#e4e8ee",
        "ink": "#1b2430", "ink2": "#465263", "mut": "#7b8698", "hov": "#e6ebf2",
        "acc": "#1f5fbf", "acc2": "#2b6fd6", "accs": "#e2ebf8", "acct": "#174a96",
        "head1": "#204f8f", "head2": "#173b6c", "tb1": "#fbfcfd", "tb2": "#edf0f4",
        "view": "#ffffff", "ok": "#2e9e5b", "warn": "#c98a12", "bad": "#cf3f3f",
    },
    "gelap": {
        "chrome": "#181b20", "panel": "#1d2128", "surf": "#14171c", "line": "#2d333d", "line2": "#262b33",
        "ink": "#e2e6ed", "ink2": "#aab3c0", "mut": "#7d8796", "hov": "#262c35",
        "acc": "#4a8ce6", "acc2": "#5b9af0", "accs": "#1d2d45", "acct": "#8fbaf3",
        "head1": "#1c3b66", "head2": "#142b4a", "tb1": "#21262e", "tb2": "#1b1f26",
        "view": "#0f1216", "ok": "#3fb56f", "warn": "#d9a03a", "bad": "#e05a5a",
    },
}

# warna interaksi (bermakna, sama di kedua mode)
INTERAKSI = {"hbond": "#2e9e5b", "hidrofobik": "#c98a12", "pi": "#7b5cd6", "pikation": "#2f8fd6",
             "garam": "#cf3f3f", "halogen": "#1aa3a3", "logam": "#7d80b0", "vdw": "#9aa6b8"}


def qss(mode):
    t = TOKEN[mode]
    return f"""
* {{ font-family: "Segoe UI Variable Text","Segoe UI",Inter,sans-serif; font-size: 9pt; }}
QMainWindow, QWidget#central {{ background: {t['chrome']}; }}
QWidget {{ color: {t['ink']}; }}
QToolTip {{ background: {t['surf']}; color: {t['ink']}; border: 1px solid {t['line']}; padding: 4px 6px; }}

QMenuBar {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {t['head1']}, stop:1 {t['head2']});
           color: #e8eef8; border-bottom: 1px solid #0e2747; padding: 1px 4px; }}
QMenuBar::item {{ background: transparent; padding: 5px 10px; border-radius: 2px; color: #dbe5f3; }}
QMenuBar::item:selected {{ background: rgba(255,255,255,0.14); color: #ffffff; }}
QMenu {{ background: {t['surf']}; border: 1px solid {t['line']}; padding: 4px 0; }}
QMenu::item {{ padding: 5px 28px 5px 26px; }}
QMenu::item:selected {{ background: {t['accs']}; color: {t['acct']}; }}
QMenu::item:disabled {{ color: {t['mut']}; }}
QMenu::separator {{ height: 1px; background: {t['line2']}; margin: 4px 8px; }}
QMenu::icon {{ padding-left: 8px; }}

QToolBar {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {t['tb1']}, stop:1 {t['tb2']});
           border: 0; border-bottom: 1px solid {t['line']}; spacing: 2px; padding: 3px 6px; }}
QToolBar::separator {{ width: 1px; background: {t['line']}; margin: 4px 6px; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 3px; padding: 4px 6px; color: {t['ink2']}; }}
QToolButton:hover {{ background: {t['hov']}; border-color: {t['line']}; }}
QToolButton:checked {{ background: {t['accs']}; border-color: {t['acc']}; color: {t['acct']}; }}
QToolButton:pressed {{ background: {t['line2']}; }}
QToolButton#run {{ background: {t['acc']}; color: #ffffff; border: 1px solid {t['acct']}; font-weight: 600; padding: 4px 12px; }}
QToolButton#run:hover {{ background: {t['acc2']}; }}
QToolButton#run:disabled {{ background: {t['line']}; color: {t['mut']}; border-color: {t['line']}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}

QDockWidget {{ color: {t['ink']}; titlebar-close-icon: none; }}
QDockWidget::title {{ background: {t['tb2']}; padding: 5px 8px; border-bottom: 1px solid {t['line']};
                     text-align: left; font-weight: 600; }}
QDockWidget > QWidget {{ background: {t['panel']}; }}
QMainWindow::separator {{ background: {t['chrome']}; width: 4px; height: 4px; }}
QMainWindow::separator:hover {{ background: {t['acc']}; }}

QTabWidget::pane {{ border: 0; border-top: 1px solid {t['line']}; background: {t['surf']}; }}
QTabBar {{ background: {t['tb2']}; }}
QTabBar::tab {{ background: {t['tb2']}; color: {t['mut']}; padding: 6px 14px; border: 0;
               border-right: 1px solid {t['line2']}; }}
QTabBar::tab:selected {{ background: {t['surf']}; color: {t['ink']}; border-top: 2px solid {t['acc']}; }}
QTabBar::tab:hover:!selected {{ color: {t['ink']}; }}
QTabBar::close-button {{ subcontrol-position: right; }}

QTreeWidget, QTreeView, QTableWidget, QTableView, QListWidget {{
    background: {t['panel']}; alternate-background-color: {t['panel']}; border: 0; outline: 0;
    selection-background-color: {t['accs']}; selection-color: {t['acct']}; }}
QTreeView::item, QListWidget::item {{ height: 22px; padding: 0 2px; }}
QTreeView::item:hover, QTableView::item:hover {{ background: {t['hov']}; }}
QTreeView::item:selected, QTableView::item:selected {{ background: {t['accs']}; color: {t['acct']}; }}
QTableWidget, QTableView {{ background: {t['surf']}; gridline-color: {t['line2']}; }}
QHeaderView::section {{ background: {t['tb2']}; color: {t['ink2']}; border: 0; border-right: 1px solid {t['line2']};
                        border-bottom: 1px solid {t['line']}; padding: 4px 8px; font-weight: 600; }}
QTableCornerButton::section {{ background: {t['tb2']}; border: 0; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {t['surf']}; border: 1px solid {t['line']}; border-radius: 3px; padding: 3px 6px;
    selection-background-color: {t['acc']}; selection-color: #ffffff; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color: {t['acc']}; }}
QComboBox::drop-down {{ border: 0; width: 18px; }}
QComboBox QAbstractItemView {{ background: {t['surf']}; border: 1px solid {t['line']}; selection-background-color: {t['accs']}; selection-color: {t['acct']}; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: 0; }}
QPlainTextEdit#log {{ font-family: "Cascadia Mono",Consolas,monospace; font-size: 8.5pt; border: 0; background: {t['surf']}; color: {t['ink2']}; }}

QPushButton {{ background: {t['surf']}; border: 1px solid {t['line']}; border-radius: 3px; padding: 5px 12px; }}
QPushButton:hover {{ border-color: {t['mut']}; }}
QPushButton:pressed {{ background: {t['hov']}; }}
QPushButton#primary {{ background: {t['acc']}; color: #ffffff; border-color: {t['acct']}; font-weight: 600; }}
QPushButton#primary:hover {{ background: {t['acc2']}; }}
QPushButton:disabled {{ color: {t['mut']}; background: {t['panel']}; }}
QPushButton:checked {{ background: {t['acc']}; color: #ffffff; border-color: {t['acct']}; }}

QCheckBox, QRadioButton {{ spacing: 6px; }}
QCheckBox::indicator, QTreeView::indicator {{ width: 13px; height: 13px; border: 1px solid {t['mut']}; border-radius: 2px; background: {t['surf']}; }}
QCheckBox::indicator:checked, QTreeView::indicator:checked {{ background: {t['acc']}; border-color: {t['acc']}; image: url(ICON_CHECK); }}

QGroupBox {{ border: 0; border-top: 1px solid {t['line']}; margin-top: 18px; padding-top: 6px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; top: 2px; color: {t['ink2']}; text-transform: uppercase; }}
QLabel#sech {{ background: {t['tb2']}; border-bottom: 1px solid {t['line2']}; border-top: 1px solid {t['line2']};
              padding: 5px 8px; font-weight: 600; color: {t['ink']}; }}
QLabel#muted {{ color: {t['mut']}; }}
QLabel#mono {{ font-family: "Cascadia Mono",Consolas,monospace; }}

QSlider::groove:horizontal {{ height: 4px; background: {t['line']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {t['acc']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 12px; margin: -5px 0; background: {t['surf']}; border: 1px solid {t['acc']}; border-radius: 6px; }}

QProgressBar {{ border: 0; background: {t['line2']}; height: 6px; border-radius: 1px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {t['acc']}; border-radius: 1px; }}

QStatusBar {{ background: {t['tb2']}; border-top: 1px solid {t['line']}; color: {t['ink2']}; }}
QStatusBar::item {{ border: 0; }}
QStatusBar QLabel {{ padding: 0 10px; border-right: 1px solid {t['line']}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t['line']}; border-radius: 3px; min-height: 30px; margin: 2px; }}
QScrollBar::handle:vertical:hover {{ background: {t['mut']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {t['line']}; border-radius: 3px; min-width: 30px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: {t['chrome']}; }}
QWizard, QDialog {{ background: {t['panel']}; }}
"""


def palet(mode):
    t = TOKEN[mode]
    p = QPalette()
    p.setColor(QPalette.Window, QColor(t["panel"]))
    p.setColor(QPalette.WindowText, QColor(t["ink"]))
    p.setColor(QPalette.Base, QColor(t["surf"]))
    p.setColor(QPalette.AlternateBase, QColor(t["panel"]))
    p.setColor(QPalette.Text, QColor(t["ink"]))
    p.setColor(QPalette.Button, QColor(t["surf"]))
    p.setColor(QPalette.ButtonText, QColor(t["ink"]))
    p.setColor(QPalette.Highlight, QColor(t["acc"]))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.PlaceholderText, QColor(t["mut"]))
    p.setColor(QPalette.ToolTipBase, QColor(t["surf"]))
    p.setColor(QPalette.ToolTipText, QColor(t["ink"]))
    return p
