from __future__ import annotations

import os
from pathlib import Path
from threading import Event

import pytest
from conftest import make_pdf
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from pypdf.errors import PdfReadError
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    NameObject,
    RectangleObject,
    TextStringObject,
)

from atelier.core.models import Event as JobEvent
from atelier.core.models import Operation, PdfOutput, PdfPage, PdfPlan, Request, UserError
from atelier.core.pdf import images_pdf
from atelier.core.pdf_tools import file_stamp, inspect_pdf, parse_pages, parse_split
from atelier.core.runner import execute


@pytest.fixture
def document(tmp_path: Path) -> Path:
    source = make_pdf(tmp_path / "source.pdf", (101, 202, 303, 404), "Texte vectoriel")
    with PdfWriter() as writer:
        writer.append(source)
        writer.pages[1].rotate(90)
        writer.pages[2].cropbox.lower_left = (10, 20)
        writer.add_metadata({"/Title": "Document de test", "/Author": "Atelier"})
        writer.xmp_metadata = (
            b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
            b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            b'<rdf:Description rdf:about=""/></rdf:RDF></x:xmpmeta>'
        )
        writer.add_outline_item("Chapitre trois", 2)
        writer.add_annotation(0, Link(rect=(10, 10, 80, 40), target_page_index=2))
        writer.write(tmp_path / "document.pdf")
    return tmp_path / "document.pdf"


def run_plan(
    source: Path, outputs: tuple[PdfOutput, ...], root: Path, cancel: Event | None = None
) -> list[JobEvent]:
    destination = root / "sorties"
    destination.mkdir(exist_ok=True)
    workspace = destination / "workspace"
    workspace.mkdir(exist_ok=True)
    events: list[JobEvent] = []
    request = Request(
        Operation.PDF_TOOLS, (source,), destination, pdf_plan=PdfPlan(file_stamp(source), outputs)
    )
    execute(request, workspace, cancel or Event(), events.append)
    return events


def test_reorder_extract_remove_rotate_and_preserve(document: Path, tmp_path: Path) -> None:
    before = document.read_bytes()
    pages = (PdfPage(2, 270), PdfPage(0, 180), PdfPage(1, 90))
    events = run_plan(document, (PdfOutput("resultat.pdf", pages),), tmp_path)
    assert events[-1]["kind"] == "finished"
    source = PdfReader(document)
    result = PdfReader(tmp_path / "sorties/resultat.pdf", strict=True)
    assert len(result.pages) == 3
    assert [int(page.mediabox.width) for page in result.pages] == [303, 101, 202]
    assert [page.rotation for page in result.pages] == [270, 180, 180]
    assert result.metadata.title == "Document de test"
    assert result.metadata.author == "Atelier"
    assert result.xmp_metadata is not None
    assert result.get_destination_page_number(result.outline[0]) == 0
    for page, spec in zip(result.pages, pages, strict=True):
        original = source.pages[spec.index]
        assert tuple(page.cropbox) == tuple(original.cropbox)
        assert page.get_contents().get_data() == original.get_contents().get_data()
        assert page.extract_text() == "Texte vectoriel"
    assert document.read_bytes() == before


def test_internal_link_remapped(document: Path, tmp_path: Path) -> None:
    events = run_plan(document, (PdfOutput("liens.pdf", (PdfPage(2), PdfPage(0))),), tmp_path)
    assert events[-1]["kind"] == "finished"
    result = PdfReader(tmp_path / "sorties/liens.pdf")
    annotation = result.pages[1]["/Annots"][0].get_object()
    assert annotation["/Dest"][0] == result.pages[0].indirect_reference


def test_split_and_collisions(document: Path, tmp_path: Path) -> None:
    groups = parse_split("1-2 ; 4 ; 3, 1", 4)
    outputs = tuple(
        PdfOutput(f"lot-{number}.pdf", tuple(PdfPage(index) for index in group))
        for number, group in enumerate(groups)
    )
    before = document.read_bytes()
    events = run_plan(document, outputs, tmp_path)
    assert len([event for event in events if event["kind"] == "output"]) == 3
    for number, group in enumerate(groups):
        reader = PdfReader(tmp_path / f"sorties/lot-{number}.pdf", strict=True)
        assert len(reader.pages) == len(group)
        assert [int(page.mediabox.width) for page in reader.pages] == [
            101 * (index + 1) for index in group
        ]
    run_plan(document, outputs, tmp_path)
    assert len(list((tmp_path / "sorties").glob("*.pdf"))) == 6
    assert document.read_bytes() == before


@pytest.mark.parametrize(
    "text", ["", "0", "5", "2-1", "1-5", "1,,2", "1;2", "a", "-1", "1,1", "1-2,2"]
)
def test_invalid_ranges(text: str) -> None:
    with pytest.raises(UserError):
        parse_pages(text, 4)


def test_range_order_and_split_validation() -> None:
    assert parse_pages("3, 1-2", 4) == (2, 0, 1)
    with pytest.raises(UserError):
        parse_split("1-2 ;", 4)


@pytest.mark.parametrize(
    "pages", [(), (PdfPage(-1),), (PdfPage(4),), (PdfPage(0, 45),), (PdfPage(1), PdfPage(1))]
)
def test_invalid_plan_never_publishes(
    document: Path, tmp_path: Path, pages: tuple[PdfPage, ...]
) -> None:
    events = run_plan(
        document, (PdfOutput("bon.pdf", (PdfPage(0),)), PdfOutput("invalide.pdf", pages)), tmp_path
    )
    assert events[-1]["kind"] == "fatal"
    assert not list((tmp_path / "sorties").glob("*.pdf"))


def test_source_changed_rejected(document: Path, tmp_path: Path) -> None:
    stamp = file_stamp(document)
    stat = document.stat()
    os.utime(document, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    destination = tmp_path / "out"
    destination.mkdir()
    workspace = destination / "work"
    workspace.mkdir()
    events: list[JobEvent] = []
    execute(
        Request(
            Operation.PDF_TOOLS,
            (document,),
            destination,
            pdf_plan=PdfPlan(stamp, (PdfOutput("out.pdf", (PdfPage(0),)),)),
        ),
        workspace,
        Event(),
        events.append,
    )
    assert events[-1]["kind"] == "fatal"
    assert "modifié" in events[-1]["message"]


def test_protected_and_broken_documents(tmp_path: Path) -> None:
    encrypted = tmp_path / "chiffre.pdf"
    signed = tmp_path / "signe.pdf"
    broken = tmp_path / "casse.pdf"
    broken.write_bytes(b"invalide")
    with PdfWriter() as writer:
        writer.add_blank_page(100, 200)
        writer.encrypt("secret")
        writer.write(encrypted)
    with PdfWriter() as writer:
        writer.add_blank_page(100, 200)
        field = DictionaryObject(
            {NameObject("/FT"): NameObject("/Sig"), NameObject("/T"): TextStringObject("signature")}
        )
        writer._root_object[NameObject("/AcroForm")] = writer._add_object(
            DictionaryObject({NameObject("/Fields"): ArrayObject([writer._add_object(field)])})
        )
        writer.write(signed)
    for path, message in ((encrypted, "chiffré"), (signed, "signature")):
        with pytest.raises(UserError, match=message):
            inspect_pdf(path)
        events = run_plan(path, (PdfOutput("out.pdf", (PdfPage(0),)),), tmp_path)
        assert events[-1]["kind"] == "fatal"
    with pytest.raises(PdfReadError):
        inspect_pdf(broken)


def test_cancel_before_publication(document: Path, tmp_path: Path) -> None:
    destination = tmp_path / "output"
    destination.mkdir()
    workspace = destination / "work"
    workspace.mkdir()
    cancel = Event()
    events: list[JobEvent] = []

    def emit(event: JobEvent) -> None:
        events.append(event)
        if event.get("kind") == "progress":
            cancel.set()

    execute(
        Request(
            Operation.PDF_TOOLS,
            (document,),
            destination,
            pdf_plan=PdfPlan(
                file_stamp(document), (PdfOutput("resultat.pdf", (PdfPage(0), PdfPage(1))),)
            ),
        ),
        workspace,
        cancel,
        emit,
    )
    assert events[-1]["kind"] == "cancelled"
    assert not (destination / "resultat.pdf").exists()


def test_standard_form_data_preserved(tmp_path: Path) -> None:
    source = tmp_path / "formulaire.pdf"
    with PdfWriter() as writer:
        page = writer.add_blank_page(200, 300)
        field = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/FT"): NameObject("/Tx"),
                NameObject("/T"): TextStringObject("prenom"),
                NameObject("/V"): TextStringObject("Ada"),
                NameObject("/Rect"): RectangleObject((10, 10, 100, 30)),
                NameObject("/P"): page.indirect_reference,
            }
        )
        reference = writer._add_object(field)
        page[NameObject("/Annots")] = ArrayObject([reference])
        writer._root_object[NameObject("/AcroForm")] = writer._add_object(
            DictionaryObject({NameObject("/Fields"): ArrayObject([reference])})
        )
        writer.write(source)
    assert any("Formulaire" in notice for notice in inspect_pdf(source).notices)
    events = run_plan(source, (PdfOutput("formulaire-tourne.pdf", (PdfPage(0, 90),)),), tmp_path)
    assert events[-1]["kind"] == "finished"
    result = PdfReader(tmp_path / "sorties/formulaire-tourne.pdf")
    assert result.get_fields()["prenom"]["/V"] == "Ada"
    assert result.pages[0]["/Annots"]


def test_embedded_jpeg_not_reencoded_by_pdf_tools(rgb: Path, tmp_path: Path) -> None:
    from PIL import Image

    jpeg = tmp_path / "photo.jpg"
    with Image.open(rgb) as image:
        image.save(jpeg, quality=95)
    source = tmp_path / "image-source.pdf"
    images_pdf((jpeg,), source, Event(), lambda *_: None)
    events = run_plan(source, (PdfOutput("image-tournee.pdf", (PdfPage(0, 270),)),), tmp_path)
    assert events[-1]["kind"] == "finished"
    result = PdfReader(tmp_path / "sorties/image-tournee.pdf")
    encoded = next(iter(result.pages[0]["/Resources"]["/XObject"].values())).get_object()
    assert encoded["/Filter"] == "/DCTDecode"
    assert encoded.get_data() == jpeg.read_bytes()
