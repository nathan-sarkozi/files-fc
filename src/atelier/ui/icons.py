from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS = {
    "pages": '<rect x="7" y="3" width="14" height="17" rx="2"/>'
    '<path d="M3 7v13a3 3 0 0 0 3 3h11M11 8h6m-6 4h6m-6 4h3"/>',
    "rotate": '<path d="M4 9a8 8 0 1 1 1 10M4 3v6h6"/>',
    "undo": '<path d="m8 4-5 5 5 5M3 9h11a6 6 0 0 1 0 12"/>',
    "trash": '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
    "convert": '<path d="M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4"/>',
    "merge": '<path d="M5 3v4c0 3 7 3 7 7m7-11v4c0 3-7 3-7 7v7m-4-4 4 4 4-4"/>',
    "images": '<rect x="3" y="3" width="18" height="18" rx="3"/>'
    '<circle cx="8" cy="8" r="1"/><path d="m3 17 6-6 4 4 3-3 5 5"/>',
    "upload": '<path d="M12 16V3m-5 5 5-5 5 5M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5"/>',
    "folder": '<path d="M3 7V5h6l2 3h10v12H3Zm0 1h8"/>',
    "arrow": '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    "up": '<path d="m6 14 6-6 6 6"/>',
    "down": '<path d="m6 10 6 6 6-6"/>',
    "close": '<path d="m6 6 12 12M6 18 18 6"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
    "shield": '<path d="m12 3 8 3v6c0 4-5 8-8 9-3-1-8-5-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
    "settings": '<path d="M4 6h16M4 12h16M4 18h16"/><path d="M8 3v6m8 0v6m-6 0v6"/>',
    "file": '<path d="M5 3h9l5 5v13H5Zm9 0v6h5M8 13h8m-8 4h5"/>',
}


def icon(name: str, color: str = "#a6b4b4", size: int = 20) -> QIcon:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="1.7" '
        f'stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</svg>'
    )
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
