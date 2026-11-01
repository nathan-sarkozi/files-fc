from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QMimeData, QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from pytestqt.qtbot import QtBot

from atelier.core.models import Operation
from atelier.ui.widgets import FileRow
from atelier.ui.window import Window


def make_window(qtbot: QtBot, tmp_path: Path) -> Window:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = Window(settings)
    window.destination.setText(str(tmp_path))
    qtbot.addWidget(window)
    window.show()
    return window


def test_real_process_conversion(qtbot: QtBot, rgb: Path, tmp_path: Path) -> None:
    window = make_window(qtbot, tmp_path)
    window.add_paths([str(rgb), str(rgb)])
    assert window.files.count() == 1
    window.target.setCurrentText("TIFF")
    qtbot.mouseClick(window.start, Qt.MouseButton.LeftButton)
    assert not window.start.isEnabled()
    qtbot.waitUntil(lambda: window.job is None, timeout=15000)
    assert "1 réussi" in window.status.text()
    result = tmp_path / "couleurs.tiff"
    assert result.is_file()
    with Image.open(result) as image:
        assert image.size == (48, 32)
    assert not list(tmp_path.glob(".atelier-*"))
    assert window.start.isEnabled()


def test_drop_and_reorder(qtbot: QtBot, pdf_pair: tuple[Path, Path], tmp_path: Path) -> None:
    window = make_window(qtbot, tmp_path)
    qtbot.mouseClick(window.nav_buttons[Operation.MERGE], Qt.MouseButton.LeftButton)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in pdf_pair])
    enter = QDragEnterEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.drop.dragEnterEvent(enter)
    assert enter.isAccepted()
    drop = QDropEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.drop.dropEvent(drop)
    assert window._paths() == list(pdf_pair)
    window.files.setCurrentRow(1)
    qtbot.mouseClick(window.up, Qt.MouseButton.LeftButton)
    assert window._paths() == list(reversed(pdf_pair))
    qtbot.mouseClick(window.start, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.job is None, timeout=15000)
    assert (tmp_path / "assemblage.pdf").is_file()
    assert "2 réussi" in window.status.text()


def test_process_cancel_cleanup(qtbot: QtBot, rgb: Path, tmp_path: Path) -> None:
    window = make_window(qtbot, tmp_path)
    window.add_paths([str(rgb)])
    window.start_job()
    window.cancel_job()
    qtbot.waitUntil(lambda: window.job is None, timeout=10000)
    assert not list(tmp_path.glob(".atelier-*"))
    assert not (tmp_path / "couleurs (1).png").exists()
    assert "nnul" in window.status.text()


def test_queues_and_unsafe_input(qtbot: QtBot, rgb: Path, tmp_path: Path) -> None:
    window = make_window(qtbot, tmp_path)
    window.add_paths([str(rgb), str(tmp_path)])
    assert window.files.count() == 1
    assert window.log
    window._set_mode(Operation.MERGE)
    assert window.files.count() == 0
    window._set_mode(Operation.CONVERT)
    assert window._paths() == [rgb]
    assert isinstance(window.files.itemWidget(window.files.item(0)), FileRow)


def test_images_pdf_through_interface(qtbot: QtBot, rgb: Path, tmp_path: Path) -> None:
    from pypdf import PdfReader

    window = make_window(qtbot, tmp_path)
    window._set_mode(Operation.IMAGES_PDF)
    window.add_paths([str(rgb)])
    qtbot.mouseClick(window.start, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.job is None, timeout=15000)
    assert len(PdfReader(tmp_path / "assemblage.pdf").pages) == 1
    assert "1 réussi" in window.status.text()


def test_close_waits_for_worker(qtbot: QtBot, rgb: Path, tmp_path: Path) -> None:
    window = make_window(qtbot, tmp_path)
    window.add_paths([str(rgb)])
    window.start_job()
    window.close()
    qtbot.waitUntil(lambda: window.job is None, timeout=10000)
    assert not window.isVisible()
    assert not list(tmp_path.glob(".atelier-*"))
