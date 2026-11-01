from __future__ import annotations

from pathlib import Path
from threading import Event

import pytest
from PIL import Image, ImageCms, PngImagePlugin

from atelier.core.images import convert_image
from atelier.core.models import Cancelled, ImageOptions, UserError


@pytest.mark.parametrize("target", ["PNG", "WEBP", "TIFF", "BMP"])
def test_lossless_pixels_dimensions_and_original(rgb: Path, tmp_path: Path, target: str) -> None:
    before = rgb.read_bytes()
    output = tmp_path / "sortie"
    convert_image(rgb, output, ImageOptions(target=target), Event())
    with Image.open(rgb) as source, Image.open(output) as result:
        assert result.format == target
        assert result.size == source.size
        assert result.tobytes() == source.tobytes()
    assert rgb.read_bytes() == before


@pytest.mark.parametrize("target", ["PNG", "WEBP", "TIFF"])
def test_alpha_pixels_preserved(tmp_path: Path, target: str) -> None:
    source = tmp_path / "alpha.png"
    image = Image.new("RGBA", (8, 8), (123, 45, 67, 0))
    image.putpixel((0, 0), (23, 65, 45, 128))
    image.save(source)
    output = tmp_path / "output"
    convert_image(source, output, ImageOptions(target=target), Event())
    with Image.open(output) as result:
        assert result.convert("RGBA").tobytes() == image.tobytes()


@pytest.mark.parametrize("target", ["JPEG", "BMP"])
def test_alpha_flattening_is_explicit(tmp_path: Path, target: str) -> None:
    source = tmp_path / "alpha.png"
    Image.new("RGBA", (20, 20), (0, 0, 0, 0)).save(source)
    output = tmp_path / "output"
    notices = convert_image(source, output, ImageOptions(target=target), Event())
    assert any("fond blanc" in notice for notice in notices)
    with Image.open(output) as image:
        assert image.mode == "RGB"
        assert image.getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.parametrize("target", ["JPEG", "WEBP"])
def test_lossy_warning(rgb: Path, tmp_path: Path, target: str) -> None:
    notices = convert_image(
        rgb, tmp_path / "output", ImageOptions(target, 100, webp_lossless=False), Event()
    )
    assert any("perte" in notice for notice in notices)


def test_orientation_metadata_and_strip(tmp_path: Path) -> None:
    source = tmp_path / "orientation.jpg"
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "Auteur de test"
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (40, 20), "red").save(source, exif=exif, icc_profile=profile, dpi=(144, 144))
    for keep in (True, False):
        output = tmp_path / str(keep)
        convert_image(source, output, ImageOptions(keep_metadata=keep), Event())
        with Image.open(output) as image:
            assert image.size == (20, 40)
            assert image.getexif().get(274, 1) == 1
            assert bool(image.getexif().get(315)) is keep
            assert bool(image.info.get("icc_profile")) is keep
            if keep:
                assert image.info["dpi"][0] == pytest.approx(144, abs=0.1)


def test_metadata_survives_alpha_compositing(tmp_path: Path) -> None:
    source = tmp_path / "rgba.png"
    exif = Image.Exif()
    exif[315] = "Atelier"
    Image.new("RGBA", (20, 20), (20, 30, 40, 128)).save(source, exif=exif, dpi=(96, 96))
    output = tmp_path / "out.jpg"
    convert_image(source, output, ImageOptions("JPEG"), Event())
    with Image.open(output) as image:
        assert image.getexif()[315] == "Atelier"
        assert image.info["dpi"] == (96, 96)


def test_png_text_preserved_or_removed(tmp_path: Path) -> None:
    source = tmp_path / "texte.png"
    text = PngImagePlugin.PngInfo()
    text.add_text("Description", "Métadonnée utile")
    Image.new("RGB", (10, 10)).save(source, pnginfo=text)
    for keep in (True, False):
        output = tmp_path / str(keep)
        convert_image(source, output, ImageOptions(keep_metadata=keep), Event())
        with Image.open(output) as result:
            assert ("Description" in result.info) is keep


@pytest.mark.parametrize("target", ["PNG", "TIFF"])
def test_16_bit_preserved(tmp_path: Path, target: str) -> None:
    source = tmp_path / "16bits.png"
    image = Image.frombytes("I;16", (2, 2), b"\x00\x00\xff\xff\x00\x80\x34\x12")
    image.save(source)
    output = tmp_path / "out"
    convert_image(source, output, ImageOptions(target), Event())
    with Image.open(output) as result:
        assert [result.getpixel((x, y)) for y in range(2) for x in range(2)] == [
            image.getpixel((x, y)) for y in range(2) for x in range(2)
        ]


def test_animation_and_depth_rejected(tmp_path: Path) -> None:
    source = tmp_path / "animation.gif"
    Image.new("RGB", (8, 8), "red").save(
        source, save_all=True, append_images=[Image.new("RGB", (8, 8), "blue")]
    )
    with pytest.raises(UserError, match="multipage"):
        convert_image(source, tmp_path / "out", ImageOptions(), Event())
    depth = tmp_path / "depth.png"
    Image.new("I;16", (10, 10), 32000).save(depth)
    with pytest.raises(UserError, match="16 bits"):
        convert_image(depth, tmp_path / "out", ImageOptions("JPEG"), Event())


def test_cmyk_rejected(tmp_path: Path) -> None:
    source = tmp_path / "cmyk.jpg"
    Image.new("CMYK", (10, 10)).save(source)
    with pytest.raises(UserError, match="CMYK"):
        convert_image(source, tmp_path / "out", ImageOptions(), Event())


def test_decoder_bomb_guard(rgb: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    with pytest.raises(UserError, match="sécurité"):
        convert_image(rgb, tmp_path / "out", ImageOptions(), Event())


def test_cancellation_before_encoding(rgb: Path, tmp_path: Path) -> None:
    cancel = Event()
    cancel.set()
    output = tmp_path / "out"
    with pytest.raises(Cancelled):
        convert_image(rgb, output, ImageOptions(), cancel)
    assert not output.exists()


@pytest.mark.parametrize("target", ["PNG", "TIFF", "WEBP"])
@pytest.mark.parametrize("keep", [True, False])
def test_palette_transparency_preserved(tmp_path: Path, target: str, keep: bool) -> None:
    source = tmp_path / "palette.png"
    image = Image.new("P", (10, 10), 1)
    image.putpalette([255, 0, 0, 0, 255, 0] + [0] * 762)
    image.putpixel((0, 0), 0)
    image.save(source, transparency=0)
    output = tmp_path / "out"
    convert_image(source, output, ImageOptions(target, keep_metadata=keep), Event())
    with Image.open(source) as original, Image.open(output) as result:
        assert result.convert("RGBA").tobytes() == original.convert("RGBA").tobytes()


@pytest.mark.parametrize("source_format", ["JPEG", "WEBP", "TIFF", "BMP", "GIF"])
def test_input_decoders(tmp_path: Path, source_format: str) -> None:
    source = tmp_path / "input"
    Image.new("RGB", (32, 16), (80, 100, 120)).save(source, format=source_format)
    output = tmp_path / "out.png"
    convert_image(source, output, ImageOptions("PNG"), Event())
    with Image.open(output) as result:
        assert result.size == (32, 16)
        assert result.format == "PNG"


def test_avif_deferred_instead_of_implicit_depth_loss(tmp_path: Path) -> None:
    source = tmp_path / "image.avif"
    Image.new("RGB", (8, 8)).save(source)
    with pytest.raises(UserError, match="pas pris en charge"):
        convert_image(source, tmp_path / "out", ImageOptions(), Event())


def test_color_16bit_png_rejected_before_silent_downcast(tmp_path: Path) -> None:
    import struct
    import zlib

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload))
        )

    source = tmp_path / "rgb16.png"
    source.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 16, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\x12\x34\x56\x78\x9a\xbc"))
        + chunk(b"IEND", b"")
    )
    with Image.open(source) as image:
        assert image.mode == "RGB"  # Le mode seul masque la réduction de profondeur.
        image.load()
    with pytest.raises(UserError, match="PNG couleur 16 bits"):
        convert_image(source, tmp_path / "out", ImageOptions(), Event())


def test_color_16bit_tiff_rejected_before_silent_downcast(tmp_path: Path) -> None:
    import struct

    tags = [
        (256, 4, 1, 1),
        (257, 4, 1, 1),
        (258, 3, 3, 134),
        (259, 3, 1, 1),
        (262, 3, 1, 2),
        (273, 4, 1, 140),
        (277, 3, 1, 3),
        (278, 4, 1, 1),
        (279, 4, 1, 6),
        (284, 3, 1, 1),
    ]
    source = tmp_path / "rgb16.tiff"
    source.write_bytes(
        b"II\x2a\x00"
        + struct.pack("<I", 8)
        + struct.pack("<H", len(tags))
        + b"".join(struct.pack("<HHII", *tag) for tag in tags)
        + b"\x00" * 4
        + struct.pack("<HHH", 16, 16, 16)
        + b"\x34\x12\x78\x56\xbc\x9a"
    )
    with Image.open(source) as image:
        assert image.mode == "RGB"
        image.load()
    with pytest.raises(UserError, match="TIFF haute profondeur"):
        convert_image(source, tmp_path / "out", ImageOptions(), Event())
