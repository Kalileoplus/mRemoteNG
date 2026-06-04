"""
Tema dark per PyQt6 — stile MobaXterm/VS Code professionale.
"""

ACCENT_COLOR  = "#007ACC"
BG_COLOR      = "#0D0D0D"
CARD_COLOR    = "#141414"
TEXT_COLOR    = "#E0E0E0"
SUB_COLOR     = "#6A6A6A"
HOVER_COLOR   = "#1E1E1E"
BORDER_COLOR  = "#1E1E1E"
SEL_COLOR     = "#1A3A5A"

DARK_QSS = f"""
/* ── Base ─────────────────────────────────────────────────── */
QMainWindow, QDialog, QWidget {{
    background-color: {BG_COLOR};
    color: {TEXT_COLOR};
    font-family: "Segoe UI", "Arial";
    font-size: 12px;
}}

/* ── Menu bar ─────────────────────────────────────────────── */
QMenuBar {{
    background-color: #111111;
    color: {TEXT_COLOR};
    border-bottom: 1px solid {BORDER_COLOR};
    padding: 1px 0;
    font-size: 12px;
}}
QMenuBar::item {{ padding: 4px 10px; border-radius: 3px; margin: 1px 2px; }}
QMenuBar::item:selected {{ background: #1E1E1E; }}
QMenuBar::item:pressed  {{ background: {ACCENT_COLOR}; color: white; }}

QMenu {{
    background: #161616;
    color: {TEXT_COLOR};
    border: 1px solid #2A2A2A;
    border-radius: 4px;
    padding: 3px;
}}
QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 3px; margin: 1px 3px; }}
QMenu::item:selected {{ background: {ACCENT_COLOR}; color: white; }}
QMenu::separator {{ height: 1px; background: #2A2A2A; margin: 4px 8px; }}

/* ── Status bar ───────────────────────────────────────────── */
QStatusBar {{
    background: #005A9E;
    color: white;
    font-size: 11px;
    border-top: 1px solid #004880;
}}
QStatusBar::item {{ border: none; }}

/* ── Inputs ───────────────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: #111111;
    color: {TEXT_COLOR};
    border: 1px solid #252525;
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: {ACCENT_COLOR};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {ACCENT_COLOR};
}}
QLineEdit:disabled {{
    background: #0D0D0D;
    color: #444;
    border-color: #1A1A1A;
}}

/* ── ComboBox ─────────────────────────────────────────────── */
QComboBox {{
    background: #111111;
    color: {TEXT_COLOR};
    border: 1px solid #252525;
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 80px;
}}
QComboBox:focus {{ border-color: {ACCENT_COLOR}; }}
QComboBox::drop-down {{ border: none; background: transparent; width: 22px; }}
QComboBox::down-arrow {{
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {SUB_COLOR};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background: #161616; color: {TEXT_COLOR};
    border: 1px solid #2A2A2A; border-radius: 4px;
    selection-background-color: {ACCENT_COLOR};
    padding: 2px;
}}

/* ── SpinBox ──────────────────────────────────────────────── */
QSpinBox {{
    background: #111111;
    color: {TEXT_COLOR};
    border: 1px solid #252525;
    border-radius: 4px;
    padding: 3px 6px;
}}
QSpinBox:focus {{ border-color: {ACCENT_COLOR}; }}
QSpinBox::up-button, QSpinBox::down-button {{
    background: #1E1E1E; border: none; width: 16px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: {ACCENT_COLOR};
}}

/* ── Buttons ──────────────────────────────────────────────── */
QPushButton {{
    background: #1A1A1A;
    color: {TEXT_COLOR};
    border: 1px solid #2A2A2A;
    border-radius: 4px;
    padding: 5px 14px;
    min-width: 60px;
}}
QPushButton:hover {{ background: #222222; border-color: {ACCENT_COLOR}; color: white; }}
QPushButton:pressed {{ background: {ACCENT_COLOR}; border-color: {ACCENT_COLOR}; color: white; }}
QPushButton:default {{
    background: {ACCENT_COLOR}; border-color: {ACCENT_COLOR}; color: white;
}}
QPushButton:default:hover {{ background: #0088DD; }}
QPushButton:disabled {{ background: #111; color: #3A3A3A; border-color: #1A1A1A; }}

/* ── CheckBox / RadioButton ───────────────────────────────── */
QCheckBox, QRadioButton {{ color: {TEXT_COLOR}; spacing: 7px; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px; height: 14px;
    background: #111; border: 1px solid #333; border-radius: 2px;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT_COLOR}; border-color: {ACCENT_COLOR};
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {ACCENT_COLOR}; }}

/* ── ScrollBars ───────────────────────────────────────────── */
QScrollBar:vertical {{
    background: #0A0A0A; width: 8px; border: none; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #2A2A2A; border-radius: 4px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT_COLOR}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{
    background: #0A0A0A; height: 8px; border: none; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: #2A2A2A; border-radius: 4px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {ACCENT_COLOR}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Splitter ─────────────────────────────────────────────── */
QSplitter::handle {{
    background: #1A1A1A; width: 2px; height: 2px;
}}
QSplitter::handle:hover {{ background: {ACCENT_COLOR}; }}

/* ── Tree/List/Table ──────────────────────────────────────── */
QTreeWidget, QTreeView {{
    background: #111111; color: {TEXT_COLOR};
    border: none; outline: none;
    alternate-background-color: #0D0D0D;
}}
QTreeWidget::item {{ padding: 3px 2px; border: none; }}
QTreeWidget::item:hover {{ background: #161616; }}
QTreeWidget::item:selected {{ background: {ACCENT_COLOR}; color: white; }}
QTreeWidget::branch {{ background: #111111; }}

QListWidget {{
    background: #111111; color: {TEXT_COLOR};
    border: 1px solid {BORDER_COLOR}; border-radius: 4px; outline: none;
}}
QListWidget::item {{ padding: 5px 10px; border-radius: 3px; margin: 1px 3px; }}
QListWidget::item:selected {{ background: {ACCENT_COLOR}; color: white; }}
QListWidget::item:hover:!selected {{ background: #1A1A1A; }}

QTableWidget {{
    background: #111111; color: {TEXT_COLOR};
    border: 1px solid {BORDER_COLOR}; border-radius: 4px;
    gridline-color: #1A1A1A; outline: none;
    alternate-background-color: #0D0D0D;
}}
QTableWidget::item:selected {{ background: {SEL_COLOR}; color: white; }}
QTableWidget::item:hover {{ background: #161616; }}
QHeaderView::section {{
    background: #0D0D0D; color: {SUB_COLOR};
    border: none; border-bottom: 1px solid {BORDER_COLOR};
    border-right: 1px solid {BORDER_COLOR};
    padding: 5px 10px; font-weight: bold; font-size: 11px;
}}

/* ── GroupBox ─────────────────────────────────────────────── */
QGroupBox {{
    color: {SUB_COLOR}; border: 1px solid #252525; border-radius: 5px;
    margin-top: 10px; padding: 10px 6px 6px 6px; font-size: 11px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    padding: 0 6px; color: {SUB_COLOR}; background: {BG_COLOR};
}}

/* ── ToolTip ──────────────────────────────────────────────── */
QToolTip {{
    background: #1A1A1A; color: {TEXT_COLOR};
    border: 1px solid {ACCENT_COLOR}; border-radius: 4px;
    padding: 5px 8px; font-size: 11px;
}}

/* ── Dialogs ──────────────────────────────────────────────── */
QMessageBox {{ background: #141414; color: {TEXT_COLOR}; }}
QDialogButtonBox QPushButton {{ min-width: 80px; }}

/* ── ProgressBar ──────────────────────────────────────────── */
QProgressBar {{
    background: #111; border: none; border-radius: 3px;
    height: 6px; text-align: center; font-size: 10px; color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT_COLOR}; border-radius: 3px; }}

/* ── Frame separators ─────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    background: #1E1E1E; border: none; max-height: 1px;
}}
"""
