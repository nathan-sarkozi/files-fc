from __future__ import annotations

from pathlib import Path
from threading import Event

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject

from atelier.core.models import UserError
from atelier.core.pdf import images_pdf, merge_pdfs


def test_merge_preserves_order_text_dimensions_and_sources(
    pdf_pair: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    before = [path.read_bytes() for path in pdf_pair]
    output = tmp_path / "fusion.pdf"
    merge_pdfs(tuple(reversed(pdf_pair)), output, Event(), lambda *_: None)
    with output.open("rb") as stream:
        result = PdfReader(stream, strict=True)
        assert [page.mediabox.width for page in result.pages] == [120, 100, 110]
        assert [page.extract_text() for page in result.pages] == ["Second", "Premier", "Premier"]
    assert [path.read_bytes() for path in pdf_pair] == before


def test_images_pdf_embeds_jpeg_unchanged(rgb: Path, tmp_path: Path) -> None:
    jpeg = tmp_path / "photo.jpg"
    with Image.open(rgb) as image:
        image.save(jpeg, quality=94)
    output = tmp_path / "images.pdf"
    images_pdf((jpeg, rgb), output, Event(), lambda *_: None)
    with output.open("rb") as stream:
        result = PdfReader(stream, strict=True)
        assert len(result.pages) == 2
        resources = result.pages[0]["/Resources"]["/XObject"]
        encoded = next(iter(resources.values())).get_object()
        assert encoded["/Filter"] == "/DCTDecode"
        assert encoded.get_data() == jpeg.read_bytes()
        assert encoded["/Width"] == 48
        assert encoded["/Height"] == 32


def test_transparent_png_pdf_valid(tmp_path: Path) -> None:
    source = tmp_path / "alpha.png"
    Image.new("RGBA", (12, 8), (20, 40, 60, 128)).save(source)
    output = tmp_path / "out.pdf"
    images_pdf((source,), output, Event(), lambda *_: None)
    reader = PdfReader(output)
    image = next(iter(reader.pages[0]["/Resources"]["/XObject"].values())).get_object()
    assert "/SMask" in image


def test_encrypted_pdf_rejected(pdf_pair: tuple[Path, Path], tmp_path: Path) -> None:
    encrypted = tmp_path / "chiffre.pdf"
    with PdfWriter() as writer:
        writer.add_blank_page(100, 200)
        writer.encrypt("secret")
        writer.write(encrypted)
    with pytest.raises(UserError, match="chiffré"):
        merge_pdfs((pdf_pair[0], encrypted), tmp_path / "out.pdf", Event(), lambda *_: None)


def test_signature_rejected(tmp_path: Path) -> None:
    signed = tmp_path / "signature.pdf"
    with PdfWriter() as writer:
        writer.add_blank_page(100, 200)
        field = DictionaryObject(
            {NameObject("/FT"): NameObject("/Sig"), NameObject("/T"): TextStringObject("signature")}
        )
        writer._root_object[NameObject("/AcroForm")] = writer._add_object(
            DictionaryObject({NameObject("/Fields"): ArrayObject([writer._add_object(field)])})
        )
        writer.write(signed)
    with pytest.raises(UserError, match="signature"):
        merge_pdfs((signed,), tmp_path / "out.pdf", Event(), lambda *_: None)


def test_corrupt_pdf_rejected(tmp_path: Path) -> None:
    source = tmp_path / "invalide.pdf"
    source.write_bytes(b"not a PDF")
    with pytest.raises(PdfReadError):
        merge_pdfs((source,), tmp_path / "out.pdf", Event(), lambda *_: None)
    assert not (tmp_path / "out.pdf").exists()
