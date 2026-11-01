from pathlib import Path
from threading import Event

from PIL import Image

from atelier.core.images import convert_image
from atelier.core.models import ImageOptions


def test_same_jpeg_copied_without_reencoding(rgb: Path, tmp_path: Path) -> None:
    source = tmp_path / "original.jpg"
    with Image.open(rgb) as image:
        image.save(source, quality=95)
    output = tmp_path / "copie.jpg"
    notices = convert_image(source, output, ImageOptions("JPEG", quality=20), Event())
    assert output.read_bytes() == source.read_bytes()
    assert any("sans réencodage" in notice for notice in notices)
    recoded = tmp_path / "encode.jpg"
    convert_image(
        source, recoded, ImageOptions("JPEG", quality=20, copy_same_format=False), Event()
    )
    assert recoded.read_bytes() != source.read_bytes()
