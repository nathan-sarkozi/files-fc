from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import make_pdf
from pypdf import PdfReader, PdfWriter
from PySide6.QtCore import QMimeData, QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import QDropEvent
from pytestqt.qtbot import QtBot

from atelier.core.models import Operation
from atelier.ui.pdf_editor import PdfEditor
from atelier.ui.pdf_pages import CACHE_SIZE
from atelier.ui.window import Window


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[Window]:
    result = Window(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    result.destination.setText(str(tmp_path))
    result.show()
    qtbot.addWidget(result)
    result._set_mode(Operation.PDF_TOOLS)
    yield result
    result.close()
    qtbot.waitUntil(
        lambda: (
            result.pdf_editor.job is None
            and not any(session.isRunning() for session in result.pdf_editor.sessions)
        ),
        timeout=10000,
    )


def load(qtbot: QtBot, editor: PdfEditor, source: Path) -> None:
    editor.open_paths([str(source)])
    qtbot.waitUntil(lambda: not editor.loading, timeout=15000)
    assert editor.info is not None, editor.status.text()
    qtbot.waitUntil(lambda: bool(editor.model.cache) or bool(editor.model.errors), timeout=15000)
    assert editor.model.cache, editor.model.errors


def test_thumbnails_reorder_rotate_extract_and_split(
    window: Window,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    source = make_pdf(tmp_path / "source.pdf", (110, 120, 130, 140))
    before = source.read_bytes()
    editor = window.pdf_editor
    # Import externe dans la zone PDF.
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(source))])
    editor.dropEvent(
        QDropEvent(
            QPointF(5, 5),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    qtbot.waitUntil(lambda: editor.info is not None, timeout=15000)
    qtbot.waitUntil(lambda: bool(editor.model.cache), timeout=15000)
    assert editor.model.rowCount() == 4
    assert max(editor.model.cache[0].width(), editor.model.cache[0].height()) <= 240
    # Glissement interne : placer la page source 4 avant la page source 1.
    data = editor.model.mimeData([editor.model.index(3)])
    rect = editor.view.visualRect(editor.model.index(0))
    drop = QDropEvent(
        QPointF(rect.left() + 1, rect.top() + 10),
        Qt.DropAction.MoveAction,
        data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    editor.view.dropEvent(drop)
    assert [page.index for page in editor.model.pages] == [3, 0, 1, 2]
    editor.range_selection.setText("1, 3")
    qtbot.mouseClick(editor.select_button, Qt.MouseButton.LeftButton)
    assert editor.selected_rows() == [0, 2]
    qtbot.mouseClick(editor.rotate_button, Qt.MouseButton.LeftButton)
    assert editor.model.pages[0].rotation == 90
    editor.export_mode.setCurrentIndex(1)
    editor.output_name.setText("selection.pdf")
    qtbot.mouseClick(editor.export_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: editor.job is None, timeout=15000)
    result = PdfReader(tmp_path / "selection.pdf", strict=True)
    assert [int(page.mediabox.width) for page in result.pages] == [140, 120]
    assert [page.rotation for page in result.pages] == [90, 90]
    editor.select_rows([1])
    qtbot.mouseClick(editor.remove_button, Qt.MouseButton.LeftButton)
    assert [page.index for page in editor.model.pages] == [3, 1, 2]
    editor.export_mode.setCurrentIndex(2)
    editor.split_ranges.setText("1-2 ; 3")
    editor.output_name.setText("decoupe.pdf")
    editor.export()
    qtbot.waitUntil(lambda: editor.job is None, timeout=15000)
    assert [len(PdfReader(path).pages) for path in editor.output_paths] == [2, 1]
    assert editor.output_paths[0].name == "decoupe - 001.pdf"
    editor.export_mode.setCurrentIndex(3)
    editor.output_name.setText("pages.pdf")
    editor.export()
    qtbot.waitUntil(lambda: editor.job is None, timeout=15000)
    assert len(editor.output_paths) == 3
    assert all(len(PdfReader(path).pages) == 1 for path in editor.output_paths)
    assert source.read_bytes() == before
    assert not list(tmp_path.glob(".atelier-*"))


def test_lazy_cache_navigation_and_release(window: Window, qtbot: QtBot, tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "nombreux.pdf", tuple(range(100, 300)))
    editor = window.pdf_editor
    load(qtbot, editor, source)
    assert editor.model.rowCount() == 200
    assert len(editor.model.cache) < 200
    editor.go_to(195)
    qtbot.waitUntil(lambda: 194 in editor.model.cache, timeout=15000)
    assert len(editor.model.cache) <= CACHE_SIZE
    editor.select_rows([194])
    editor.rotate_pages()
    window._set_mode(Operation.CONVERT)
    qtbot.waitUntil(lambda: not editor.sessions, timeout=10000)
    assert not editor.model.cache
    window._set_mode(Operation.PDF_TOOLS)
    qtbot.waitUntil(lambda: not editor.loading, timeout=15000)
    assert editor.model.pages[194].rotation == 90
    assert editor.info is not None


def test_invalid_input_ranges_and_all_pages_removed(
    window: Window,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    source = make_pdf(tmp_path / "source.pdf", (100, 120))
    editor = window.pdf_editor
    load(qtbot, editor, source)
    editor.export_mode.setCurrentIndex(2)
    editor.split_ranges.setText("1-3")
    editor.export()
    assert editor.job is None
    assert "limites" in editor.status.text()
    editor.select_rows([0, 1])
    editor.remove_pages()
    assert not editor.export_button.isEnabled()
    editor.model.undo()
    assert editor.model.rowCount() == 2
    assert editor.export_button.isEnabled()


def test_protected_preview_refused(window: Window, qtbot: QtBot, tmp_path: Path) -> None:
    source = tmp_path / "chiffre.pdf"
    with PdfWriter() as writer:
        writer.add_blank_page(100, 200)
        writer.encrypt("secret")
        writer.write(source)
    editor = window.pdf_editor
    editor.open_paths([str(source)])
    qtbot.waitUntil(lambda: not editor.loading, timeout=15000)
    assert editor.info is None
    assert "chiffré" in editor.status.text()
    assert not editor.export_button.isEnabled()


def test_cancel_export_and_close_preview(window: Window, qtbot: QtBot, tmp_path: Path) -> None:
    editor = window.pdf_editor
    source = make_pdf(tmp_path / "source.pdf", (100, 120))
    load(qtbot, editor, source)
    editor.export()
    editor.cancel()
    qtbot.waitUntil(lambda: editor.job is None, timeout=10000)
    assert not editor.output_paths
    assert "nnul" in editor.status.text()
    assert not list(tmp_path.glob(".atelier-*"))
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=10000)
    assert not any(session.isRunning() for session in editor.sessions)
