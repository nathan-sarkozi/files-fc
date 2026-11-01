from __future__ import annotations

import argparse
import multiprocessing
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from atelier import __version__
from atelier.core.models import Operation
from atelier.desktop import clean_vscode_snap_environment
from atelier.ui.theme import STYLE
from atelier.ui.window import Window


def main() -> int:
    multiprocessing.freeze_support()
    clean_vscode_snap_environment(os.environ)
    parser = argparse.ArgumentParser(description="Atelier — convertisseur local pour Linux")
    parser.add_argument("files", nargs="*", help="Images à ajouter à la conversion")
    parser.add_argument("--pdf", type=Path, help="Ouvrir un document dans les outils PDF")
    parser.add_argument(
        "--smoke-test", action="store_true", help="Démarrer puis quitter après 1 seconde"
    )
    parser.add_argument("--screenshot", type=Path, help="Enregistrer une capture de la fenêtre")
    args = parser.parse_args()
    if args.pdf and args.files:
        parser.error("Utilisez --pdf ou une liste de fichiers, pas les deux.")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Atelier")
    app.setOrganizationName("AtelierLocal")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#141a1d"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1b2327"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e8eeee"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e8eeee"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#3d6453"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    families = QFontDatabase.families()
    family = next(
        (name for name in ("Inter", "Noto Sans", "DejaVu Sans") if name in families), "Sans"
    )
    app.setFont(QFont(family, 10))
    check_icon = (Path(__file__).parent / "assets/check.svg").as_posix()
    app.setStyleSheet(STYLE.replace("__CHECK_ICON__", check_icon))
    window = Window()
    if args.pdf or (len(args.files) == 1 and Path(args.files[0]).suffix.lower() == ".pdf"):
        window._set_mode(Operation.PDF_TOOLS)
        window.pdf_editor.open_paths([str(args.pdf or args.files[0])])
    elif args.files and all(Path(path).suffix.lower() == ".pdf" for path in args.files):
        window._set_mode(Operation.MERGE)
        window.add_paths(args.files)
    else:
        window.add_paths(args.files)
    window.show()
    if args.screenshot:
        QTimer.singleShot(700, lambda: window.grab().save(str(args.screenshot)))
    if args.smoke_test:
        QTimer.singleShot(1000, window.close)
    return app.exec()
