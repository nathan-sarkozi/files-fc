STYLE = """
QWidget { color: #e8eeee; font-size: 13px; }
QMainWindow, QDialog { background: #141a1d; }
QLabel { background: transparent; }
QFrame#sidebar { background: #101619; border-right: 1px solid #293135; }
QLabel#brand { font-size: 24px; font-weight: 700; letter-spacing: -1px; }
QLabel#muted { color: #94a3a7; }
QLabel#eyebrow { color: #9aaead; font-size: 10px; font-weight: 600; letter-spacing: 2px; }
QLabel#title { font-size: 30px; font-weight: 600; letter-spacing: -1px; }
QLabel#cardTitle { font-size: 15px; font-weight: 600; }
QLabel#badge { color: #b5efd2; background: #20352e; border: 1px solid #365448;
 border-radius: 12px; padding: 5px 11px; font-size: 11px; }
QLabel#note { color: #a6b4b8; font-size: 12px; }
QPushButton { background: #253035; border: 1px solid #354247; border-radius: 7px;
 padding: 9px 12px; font-weight: 500; }
QPushButton:hover { background: #303e43; border-color: #526367; }
QPushButton:pressed { background: #1a2428; }
QPushButton:disabled { color: #829195; background: #20282c; border-color: #303a3f; }
QPushButton:focus, QComboBox:focus, QLineEdit:focus, QListWidget:focus {
 border: 1px solid #b5efd2; }
QPushButton#primary { background: #b5efd2; color: #172d24; border: none;
 padding: 12px 18px; font-weight: 700; }
QPushButton#primary:hover { background: #cdf9e2; }
QPushButton#primary:disabled { background: #415c50; color: #bfcec6; }
QPushButton#nav { text-align: left; background: transparent; border: none;
 color: #a0adb1; padding: 13px; }
QPushButton#nav:checked { background: #23332f; color: #c4f4dd; }
QPushButton#nav:hover { background: #202a2e; }
QPushButton#quiet { background: transparent; border: 1px solid #334045; }
QPushButton#mini { padding: 6px; }
QFrame#card { background: #1b2327; border: 1px solid #303b40; border-radius: 12px; }
QFrame#dropzone { background: #1a2627; border: 1px dashed #526a63; border-radius: 10px; }
QFrame#safety { background: #1e302a; border: 1px solid #304b3f; border-radius: 8px; }
QFrame#warning { background: #332d20; border: 1px solid #645333; border-radius: 8px; }
QScrollArea#optionsScroll { background: transparent; border: none; }
QLineEdit, QComboBox, QSpinBox { background: #141c20; border: 1px solid #3b484d;
 border-radius: 7px; padding: 9px; selection-background-color: #456a58; }
QComboBox::drop-down { border: none; width: 25px; }
QComboBox QAbstractItemView { background: #202b30; selection-background-color: #3b544a; }
QCheckBox { spacing: 9px; padding: 5px 0; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #53625d;
 border-radius: 4px; background: #14211c; }
QCheckBox::indicator:checked { background: #b5efd2; border-color: #b5efd2;
 image: url("__CHECK_ICON__"); }
QCheckBox:focus { color: #b5efd2; }
QSlider::groove:horizontal { height: 4px; background: #39464b; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #b5efd2; border-radius: 2px; }
QSlider::handle:horizontal { background: #b5efd2; width: 14px; margin: -5px 0;
 border-radius: 7px; }
QListWidget { background: transparent; border: none; outline: 0; }
QListWidget::item { border-bottom: 1px solid #2d393e; border-radius: 5px; }
QListWidget::item:selected { background: #2a3c37; }
QListWidget::item:hover { background: #253136; }
QProgressBar { background: #303c41; border: none; border-radius: 3px; height: 6px;
 color: transparent; }
QProgressBar::chunk { background: #b5efd2; border-radius: 3px; }
QScrollBar:vertical { background: transparent; width: 7px; margin: 2px; }
QScrollBar::handle:vertical { background: #46575c; border-radius: 3px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTextBrowser { background: #1b2327; border: 1px solid #354247; border-radius: 8px;
 padding: 12px; }
QToolTip { color: #e8eeee; background: #283a34; border: 1px solid #547463; padding: 5px; }
"""
