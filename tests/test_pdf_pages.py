from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QImage

from atelier.ui.pdf_pages import CACHE_SIZE, MIME, PageModel


def test_page_order_rotation_removal_and_undo() -> None:
    model = PageModel()
    model.reset_document(6)
    assert model.move([1, 3], 6) == [4, 5]
    assert [page.index for page in model.pages] == [0, 2, 4, 5, 1, 3]
    model.rotate([4, 5], 270)
    assert model.pages[4].rotation == 270
    model.remove([1, 4])
    assert [page.index for page in model.pages] == [0, 4, 5, 3]
    model.undo()
    assert len(model.pages) == 6
    assert model.pages[4].rotation == 270
    assert model.step([4, 5], -1) == [3, 4]
    assert [page.index for page in model.pages] == [0, 2, 4, 1, 3, 5]
    assert model.data(model.index(3), Qt.ItemDataRole.DisplayRole) == "4 · source 2"


def test_bounded_cache_and_mime_validation() -> None:
    model = PageModel()
    model.reset_document(1000)
    for index in range(CACHE_SIZE + 10):
        model.store_image(index, QImage(20, 30, QImage.Format.Format_RGB888))
    assert len(model.cache) == CACHE_SIZE
    assert 0 not in model.cache
    mime = model.mimeData([model.index(2), model.index(5)])
    assert model.mime_rows(mime) == [2, 5]
    other = PageModel()
    assert not other.mime_rows(mime)
    invalid = QMimeData()
    invalid.setData(MIME, b'{"rows": [-1]}')
    assert not model.mime_rows(invalid)
