from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


@pytest.fixture
def rgb(tmp_path: Path) -> Path:
    path = tmp_path / "couleurs.png"
    image = Image.new("RGB", (48, 32))
    image.putdata(
        [(x * 5 % 256, y * 7 % 256, (x + y) * 3 % 256) for y in range(32) for x in range(48)]
    )
    image.save(path)
    return path


def make_pdf(path: Path, widths: tuple[int, ...] = (100,), text: str = "Atelier") -> Path:
    with PdfWriter() as writer:
        for width in widths:
            page = writer.add_blank_page(width=width, height=200)
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
            )
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode("ascii"))
            page[NameObject("/Contents")] = writer._add_object(stream)
        writer.write(path)
    return path


@pytest.fixture
def pdf_pair(tmp_path: Path) -> tuple[Path, Path]:
    return (
        make_pdf(tmp_path / "un.pdf", (100, 110), "Premier"),
        make_pdf(tmp_path / "deux.pdf", (120,), "Second"),
    )
