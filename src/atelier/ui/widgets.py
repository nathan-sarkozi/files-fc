from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from atelier.ui.icons import icon


def button(text: str, glyph: str = "", name: str = "") -> QPushButton:
    widget = QPushButton(text)
    if name:
        widget.setObjectName(name)
    if glyph:
        widget.setIcon(icon(glyph))
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(16)
    return frame, layout


def label(text: str, name: str = "", wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("o", "Kio", "Mio", "Gio", "Tio"):
        if value < 1024:
            return f"{value:.1f} {unit}" if unit != "o" else f"{size} o"
        value /= 1024
    return f"{value:.1f} Pio"


class DropZone(QFrame):
    paths_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropzone")
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and self.isEnabled():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        self.paths_dropped.emit(paths)
        event.acceptProposedAction()


class FileList(QListWidget):
    paths_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSpacing(2)
        self.setAccessibleName("Fichiers à traiter, dans l’ordre d’assemblage")
        self.setMinimumHeight(90)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            self.paths_dropped.emit(
                [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            )
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class FileRow(QWidget):
    def __init__(self, path: Path, size: int) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(12)
        extension = label(path.suffix.lstrip(".").upper()[:5] or "FILE")
        extension.setFixedSize(45, 40)
        extension.setAlignment(Qt.AlignmentFlag.AlignCenter)
        extension.setStyleSheet(
            "background:#303c42;color:#c7d9d6;border-radius:7px;font-size:10px;font-weight:700;"
        )
        layout.addWidget(extension)
        text = QVBoxLayout()
        text.setSpacing(5)
        self.filename = label(path.name)
        self.filename.setMinimumWidth(0)
        self.detail = label(format_size(size), "muted")
        self.detail.setStyleSheet("font-size:11px;")
        text.addWidget(self.filename)
        text.addWidget(self.detail)
        layout.addLayout(text, 1)
        self.status = label("En attente", "muted")
        self.status.setStyleSheet("font-size:11px;")
        layout.addWidget(self.status)
        self.setToolTip(str(path))

    def set_status(self, state: str, message: str) -> None:
        texts = {
            "pending": "En attente",
            "running": "En cours…",
            "success": "Terminé",
            "error": "Erreur",
            "cancelled": "Annulé",
        }
        colors = {
            "pending": "#a6b4b8",
            "running": "#cce6df",
            "success": "#b5efd2",
            "error": "#f3b3a2",
            "cancelled": "#d7c495",
        }
        self.status.setText(texts.get(state, state))
        self.status.setStyleSheet(f"font-size:11px;color:{colors.get(state, '#a6b4b8')};")
        self.status.setToolTip(message)


def make_item(path: Path, size: int) -> tuple[QListWidgetItem, FileRow]:
    item = QListWidgetItem()
    item.setSizeHint(QSize(0, 76))
    item.setData(Qt.ItemDataRole.UserRole, str(path))
    item.setToolTip(str(path))
    return item, FileRow(path, size)
