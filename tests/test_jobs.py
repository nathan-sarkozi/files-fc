from __future__ import annotations

import time
from multiprocessing.connection import Connection
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

import atelier.jobs
from atelier.core.models import CancelSignal, Event, Operation, Request
from atelier.jobs import Job


def blocked_encoder(
    request: Request, workspace: str, cancel: CancelSignal, pipe: Connection
) -> None:
    # Double de test d’un encodeur natif qui ne coopère pas avec l’annulation.
    (Path(workspace) / "partial").write_bytes(b"partial")
    time.sleep(30)


def test_forced_cancellation_cleans_partial_files(
    qtbot: QtBot,
    rgb: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(atelier.jobs, "child_main", blocked_encoder)
    job = Job(Request(Operation.CONVERT, (rgb,), tmp_path))
    events: list[Event] = []
    job.update.connect(events.append)
    job.start()
    try:
        qtbot.waitUntil(lambda: bool(list(tmp_path.glob(".atelier-*/partial"))), timeout=10000)
        job.cancel()
        qtbot.waitUntil(lambda: not job.isRunning(), timeout=5000)
        assert any(event["kind"] == "cancelled" for event in events)
        assert not list(tmp_path.glob(".atelier-*"))
        assert not (tmp_path / "couleurs (1).png").exists()
    finally:
        job.cancel()
        job.wait(5000)
