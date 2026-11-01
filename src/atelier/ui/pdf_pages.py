from __future__ import annotations

import json
import uuid
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QMimeData,
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QImage,
    QPainter,
    QPen,
    QTransform,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from atelier.core.models import PdfPage

Index = QModelIndex | QPersistentModelIndex
MIME = "application/x-atelier-pdf-pages"
CACHE_SIZE = 48
EMPTY_INDEX = QModelIndex()


class PageModel(QAbstractListModel):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.pages: list[PdfPage] = []
        self.positions: dict[int, int] = {}
        self.cache: OrderedDict[int, QImage] = OrderedDict()
        self.errors: dict[int, str] = {}
        self.history: list[tuple[PdfPage, ...]] = []
        self.token = uuid.uuid4().hex

    def rowCount(self, parent: Index = EMPTY_INDEX) -> int:
        return 0 if parent.isValid() else len(self.pages)

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self.pages):
            return None
        page = self.pages[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return f"{index.row() + 1} · source {page.index + 1}"
        if role == Qt.ItemDataRole.ToolTipRole:
            return self.errors.get(
                page.index,
                f"Position {index.row() + 1}, page source {page.index + 1}"
                + (f", rotation ajoutée {page.rotation}°" if page.rotation else ""),
            )
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return self.data(index, Qt.ItemDataRole.ToolTipRole)
        if role == Qt.ItemDataRole.UserRole:
            return page
        return None

    def flags(self, index: Index) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsDragEnabled
            | Qt.ItemFlag.ItemIsDropEnabled
        )

    def reset_document(self, count: int) -> None:
        self.beginResetModel()
        self.pages = [PdfPage(index) for index in range(count)]
        self.positions = {index: index for index in range(count)}
        self.cache.clear()
        self.errors.clear()
        self.history.clear()
        self.token = uuid.uuid4().hex
        self.endResetModel()
        self.changed.emit()

    def set_pages(self, pages: list[PdfPage]) -> None:
        if pages == self.pages:
            return
        self.history.append(tuple(self.pages))
        del self.history[:-20]
        self.beginResetModel()
        self.pages = pages
        self.positions = {page.index: row for row, page in enumerate(pages)}
        self.endResetModel()
        self.changed.emit()

    def undo(self) -> None:
        if self.history:
            self.beginResetModel()
            self.pages = list(self.history.pop())
            self.positions = {page.index: row for row, page in enumerate(self.pages)}
            self.endResetModel()
            self.changed.emit()

    def rotate(self, rows: Sequence[int], angle: int) -> None:
        selected = set(rows)
        self.set_pages(
            [
                replace(page, rotation=(page.rotation + angle) % 360) if row in selected else page
                for row, page in enumerate(self.pages)
            ]
        )

    def remove(self, rows: Sequence[int]) -> None:
        selected = set(rows)
        self.set_pages([page for row, page in enumerate(self.pages) if row not in selected])

    def move(self, rows: Sequence[int], destination: int) -> list[int]:
        selected = sorted(set(rows))
        if not selected or any(row < 0 or row >= len(self.pages) for row in selected):
            return []
        if not 0 <= destination <= len(self.pages):
            return []
        moving = [self.pages[row] for row in selected]
        selected_set = set(selected)
        remaining = [page for row, page in enumerate(self.pages) if row not in selected_set]
        offset = destination - sum(row < destination for row in selected)
        self.set_pages(remaining[:offset] + moving + remaining[offset:])
        return list(range(offset, offset + len(moving)))

    def step(self, rows: Sequence[int], direction: int) -> list[int]:
        selected = set(rows)
        pages = self.pages.copy()
        for row in sorted(selected, reverse=direction > 0):
            other = row + direction
            if 0 <= other < len(pages) and other not in selected:
                pages[row], pages[other] = pages[other], pages[row]
                selected.remove(row)
                selected.add(other)
        self.set_pages(pages)
        return sorted(selected)

    def store_image(self, index: int, image: QImage) -> None:
        self.cache[index] = image
        self.cache.move_to_end(index)
        while len(self.cache) > CACHE_SIZE:
            self.cache.popitem(last=False)
        row = self.positions.get(index)
        if row is not None:
            self.dataChanged.emit(self.index(row), self.index(row), [])

    def mimeTypes(self) -> list[str]:
        return [MIME]

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        mime = QMimeData()
        mime.setData(
            MIME,
            json.dumps(
                {"token": self.token, "rows": sorted({index.row() for index in indexes})}
            ).encode(),
        )
        return mime

    def mime_rows(self, mime: QMimeData) -> list[int]:
        try:
            data = json.loads(bytes(mime.data(MIME).data()))
            rows = data["rows"]
            if data["token"] != self.token or not isinstance(rows, list):
                return []
            if any(type(row) is not int or not 0 <= row < len(self.pages) for row in rows):
                return []
            return sorted(set(rows))
        except (ValueError, KeyError, TypeError):
            return []


class PageDelegate(QStyledItemDelegate):
    def __init__(self, model: PageModel) -> None:
        super().__init__()
        self.pages = model

    def sizeHint(self, option: QStyleOptionViewItem, index: Index) -> QSize:
        return QSize(158, 218)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: Index) -> None:
        page = self.pages.pages[index.row()]
        painter.save()
        rect = option.rect.adjusted(5, 5, -5, -5)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setBrush(QColor("#293e35" if selected else "#202b30"))
        painter.setPen(QPen(QColor("#b5efd2" if selected else "#36454a"), 2 if selected else 1))
        painter.drawRoundedRect(rect, 8, 8)
        image_rect = rect.adjusted(10, 10, -10, -38)
        image = self.pages.cache.get(page.index)
        if image is not None:
            self.pages.cache.move_to_end(page.index)
            rotated = (
                image.transformed(QTransform().rotate(page.rotation)) if page.rotation else image
            )
            size = rotated.size().scaled(image_rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRect(0, 0, size.width(), size.height())
            target.moveCenter(image_rect.center())
            painter.drawImage(target, rotated)
        else:
            painter.setPen(QColor("#819795"))
            painter.drawText(
                image_rect,
                Qt.AlignmentFlag.AlignCenter,
                "Aperçu indisponible" if page.index in self.pages.errors else "Chargement…",
            )
        painter.setPen(QColor("#c7f1dd" if selected else "#d6e3e1"))
        painter.drawText(
            QRect(rect.left(), rect.bottom() - 30, rect.width(), 24),
            Qt.AlignmentFlag.AlignCenter,
            f"{index.row() + 1}  ·  source {page.index + 1}"
            + (f"  ↻{page.rotation}°" if page.rotation else ""),
        )
        if option.state & QStyle.StateFlag.State_HasFocus:
            painter.setPen(QPen(QColor("#ffffff"), 1, Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 6, 6)
        painter.restore()


class PageView(QListView):
    files_dropped = Signal(list)
    reordered = Signal(list)

    def __init__(self, model: PageModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pages = model
        self.setModel(model)
        self.setItemDelegate(PageDelegate(model))
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setUniformItemSizes(True)
        self.setGridSize(QSize(158, 218))
        self.setSpacing(0)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setAccessibleName("Pages PDF dans l’ordre de sortie. Ctrl et Maj pour sélectionner.")
        self.setStyleSheet("QListView{background:transparent;border:none;outline:0;}")

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        drag = QDrag(self)
        drag.setMimeData(self.pages.mimeData(self.selectionModel().selectedIndexes()))
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() or self.pages.mime_rows(event.mimeData()):
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls() or self.pages.mime_rows(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            self.files_dropped.emit(
                [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            )
            event.acceptProposedAction()
            return
        rows = self.pages.mime_rows(event.mimeData())
        if not rows:
            return
        index = self.indexAt(event.position().toPoint())
        destination = index.row() if index.isValid() else len(self.pages.pages)
        if index.isValid() and event.position().x() > self.visualRect(index).center().x():
            destination += 1
        self.reordered.emit(self.pages.move(rows, destination))
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()
