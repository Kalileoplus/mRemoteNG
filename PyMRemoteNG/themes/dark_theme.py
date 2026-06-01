"""
Tema dark per PyQt6 - ispirato a MobaXterm/mRemoteNG Darcula
"""

DARK_QSS = """
QMainWindow, QDialog, QWidget {
    background-color: #0D0D0D;
    color: #E8E8E8;
    font-family: "Segoe UI";
    font-size: 11px;
}

QMenuBar {
    background-color: #1A1A1A;
    color: #E8E8E8;
    border-bottom: 1px solid #333333;
}
QMenuBar::item:selected {
    background-color: #2D2D2D;
}
QMenuBar::item:pressed {
    background-color: #007ACC;
}

QMenu {
    background-color: #1A1A1A;
    color: #E8E8E8;
    border: 1px solid #333333;
}
QMenu::item:selected {
    background-color: #007ACC;
    color: white;
}
QMenu::separator {
    height: 1px;
    background: #333333;
    margin: 2px 5px;
}

QToolBar {
    background-color: #1A1A1A;
    border: none;
    border-bottom: 1px solid #333333;
    spacing: 2px;
    padding: 3px;
}
QToolBar::separator {
    background-color: #333333;
    width: 1px;
    margin: 4px 3px;
}
QToolButton {
    background-color: transparent;
    color: #E8E8E8;
    border: none;
    border-radius: 3px;
    padding: 4px 8px;
    min-width: 60px;
}
QToolButton:hover {
    background-color: #2D2D2D;
}
QToolButton:pressed {
    background-color: #007ACC;
}
QToolButton:checked {
    background-color: #005A9E;
}

QStatusBar {
    background-color: #007ACC;
    color: white;
    font-size: 10px;
}
QStatusBar::item {
    border: none;
}

QTreeWidget, QTreeView {
    background-color: #141414;
    color: #E8E8E8;
    border: none;
    outline: none;
    selection-background-color: #007ACC;
    selection-color: white;
    alternate-background-color: #1A1A1A;
}
QTreeWidget::item {
    padding: 3px 2px;
    border: none;
}
QTreeWidget::item:hover {
    background-color: #2D2D2D;
}
QTreeWidget::item:selected {
    background-color: #007ACC;
    color: white;
}
QTreeWidget::branch {
    background-color: #141414;
}
QTreeWidget::branch:has-siblings:!adjoins-item {
    border-image: none;
}
QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {
    image: url(none);
}

QTabWidget::pane {
    background-color: #0D0D0D;
    border: 1px solid #333333;
    border-top: none;
}
QTabBar {
    background-color: #1A1A1A;
}
QTabBar::tab {
    background-color: #1A1A1A;
    color: #888888;
    border: 1px solid #333333;
    border-bottom: none;
    padding: 6px 14px;
    margin-right: 2px;
    min-width: 80px;
}
QTabBar::tab:selected {
    background-color: #0D0D0D;
    color: #E8E8E8;
    border-bottom: 2px solid #007ACC;
}
QTabBar::tab:hover:!selected {
    background-color: #2D2D2D;
    color: #E8E8E8;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #1E1E1E;
    color: #E8E8E8;
    border: 1px solid #3E3E3E;
    border-radius: 3px;
    padding: 4px 6px;
    selection-background-color: #007ACC;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #007ACC;
}
QLineEdit:disabled {
    background-color: #141414;
    color: #555555;
}

QComboBox {
    background-color: #1E1E1E;
    color: #E8E8E8;
    border: 1px solid #3E3E3E;
    border-radius: 3px;
    padding: 4px 6px;
    min-width: 80px;
}
QComboBox:focus {
    border: 1px solid #007ACC;
}
QComboBox::drop-down {
    border: none;
    background: #2D2D2D;
    width: 20px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #888888;
    margin: 0 6px;
}
QComboBox QAbstractItemView {
    background-color: #1E1E1E;
    color: #E8E8E8;
    selection-background-color: #007ACC;
    border: 1px solid #3E3E3E;
}

QPushButton {
    background-color: #2D2D2D;
    color: #E8E8E8;
    border: 1px solid #3E3E3E;
    border-radius: 3px;
    padding: 5px 14px;
    min-width: 70px;
}
QPushButton:hover {
    background-color: #3D3D3D;
    border-color: #007ACC;
}
QPushButton:pressed {
    background-color: #007ACC;
}
QPushButton:default {
    background-color: #007ACC;
    border-color: #007ACC;
    color: white;
}
QPushButton:default:hover {
    background-color: #0088DD;
}
QPushButton:disabled {
    background-color: #1A1A1A;
    color: #555555;
    border-color: #2D2D2D;
}

QCheckBox, QRadioButton {
    color: #E8E8E8;
    spacing: 6px;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 14px;
    height: 14px;
    background-color: #1E1E1E;
    border: 1px solid #3E3E3E;
    border-radius: 2px;
}
QCheckBox::indicator:checked {
    background-color: #007ACC;
    border-color: #007ACC;
}
QCheckBox::indicator:hover {
    border-color: #007ACC;
}

QScrollBar:vertical {
    background-color: #141414;
    width: 10px;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #3D3D3D;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #555555;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #141414;
    height: 10px;
    border: none;
}
QScrollBar::handle:horizontal {
    background-color: #3D3D3D;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #555555;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QSplitter::handle {
    background-color: #333333;
    width: 1px;
    height: 1px;
}
QSplitter::handle:hover {
    background-color: #007ACC;
}

QLabel {
    color: #E8E8E8;
    background-color: transparent;
}

QGroupBox {
    color: #888888;
    border: 1px solid #333333;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    color: #888888;
}

QHeaderView::section {
    background-color: #1A1A1A;
    color: #888888;
    border: none;
    border-bottom: 1px solid #333333;
    padding: 4px 8px;
    font-weight: bold;
}

QTableWidget, QListWidget {
    background-color: #141414;
    color: #E8E8E8;
    border: 1px solid #333333;
    selection-background-color: #007ACC;
    alternate-background-color: #1A1A1A;
    gridline-color: #2D2D2D;
}
QTableWidget::item:selected, QListWidget::item:selected {
    background-color: #007ACC;
    color: white;
}
QTableWidget::item:hover, QListWidget::item:hover {
    background-color: #2D2D2D;
}

QToolTip {
    background-color: #1E1E1E;
    color: #E8E8E8;
    border: 1px solid #007ACC;
    padding: 4px 6px;
    border-radius: 3px;
}

QMessageBox {
    background-color: #1A1A1A;
    color: #E8E8E8;
}

QDialogButtonBox QPushButton {
    min-width: 80px;
}

/* Dock widget styles */
QDockWidget {
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
    color: #E8E8E8;
}
QDockWidget::title {
    background-color: #1A1A1A;
    padding: 4px 8px;
    border-bottom: 1px solid #333333;
    text-align: left;
    font-weight: bold;
    color: #888888;
}
QDockWidget::close-button, QDockWidget::float-button {
    background-color: transparent;
    border: none;
    padding: 2px;
}
QDockWidget::close-button:hover, QDockWidget::float-button:hover {
    background-color: #2D2D2D;
}

/* Splitter panels */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {
    background-color: #333333;
    border: none;
}
"""

ACCENT_COLOR = "#007ACC"
BG_COLOR = "#0D0D0D"
CARD_COLOR = "#1A1A1A"
TEXT_COLOR = "#E8E8E8"
SUB_COLOR = "#888888"
HOVER_COLOR = "#2D2D2D"
