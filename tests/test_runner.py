from __future__ import annotations

import os
from pathlib import Path
from threading import Event

import pytest

from atelier.core.files import output_name, publish, source_file
from atelier.core.models import Event as JobEvent
from atelier.core.models import ImageOptions, Operation, Request, UserError
from atelier.core.runner import execute


def test_batch_continues_after_error_and_no_overwrite(rgb: Path, tmp_path: Path) -> None:
    bad = tmp_path / "faux.png"
    bad.write_text("invalide")
    work = tmp_path / "work"
    work.mkdir()
    before = rgb.read_bytes()
    events: list[JobEvent] = []
    execute(Request(Operation.CONVERT, (bad, rgb), tmp_path), work, Event(), events.append)
    statuses = [event["state"] for event in events if event.get("kind") == "item"]
    assert statuses == ["running", "error", "running", "success"]
    assert events[-1]["kind"] == "finished"
    assert (tmp_path / "couleurs (1).png").is_file()
    assert rgb.read_bytes() == before
    assert list(work.iterdir()) == []


def test_existing_symlink_never_overwritten(tmp_path: Path) -> None:
    original = tmp_path / "original.txt"
    original.write_text("secret")
    link = tmp_path / "sortie.png"
    link.symlink_to(original)
    staged = tmp_path / "stage"
    staged.write_bytes(b"result")
    result = publish(staged, tmp_path, "sortie.png")
    assert result.name == "sortie (1).png"
    assert link.is_symlink()
    assert original.read_text() == "secret"


@pytest.mark.parametrize(
    "name", ["../escape.pdf", "/tmp/test.pdf", "a/b", "a\\b", "", ".", "..", "a\n"]
)
def test_unsafe_output_names_rejected(name: str) -> None:
    # Les espaces extérieurs sont normalisés, les chemins et contrôles sont interdits.
    if name == "a\n":
        assert output_name(name) == "a.pdf"
    else:
        with pytest.raises(UserError):
            output_name(name)


def test_fifo_and_directory_rejected(tmp_path: Path) -> None:
    fifo = tmp_path / "fifo.png"
    os.mkfifo(fifo)
    for path in (tmp_path, fifo):
        with pytest.raises(UserError):
            source_file(path)


def test_cancel_mid_batch_keeps_completed_result(rgb: Path, tmp_path: Path) -> None:
    cancel = Event()
    work = tmp_path / "work"
    work.mkdir()
    events: list[JobEvent] = []

    def emit(event: JobEvent) -> None:
        events.append(event)
        if event.get("state") == "success":
            cancel.set()

    execute(
        Request(Operation.CONVERT, (rgb, rgb), tmp_path, options=ImageOptions("TIFF")),
        work,
        cancel,
        emit,
    )
    assert events[-1]["kind"] == "cancelled"
    assert len(list(tmp_path.glob("*.tiff"))) == 1


def test_failed_assembly_never_published(pdf_pair: tuple[Path, Path], tmp_path: Path) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"broken")
    work = tmp_path / "work"
    work.mkdir()
    events: list[JobEvent] = []
    execute(Request(Operation.MERGE, (pdf_pair[0], bad), tmp_path), work, Event(), events.append)
    assert events[-1]["kind"] == "fatal"
    assert not (tmp_path / "assemblage.pdf").exists()
