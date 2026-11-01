from __future__ import annotations

import logging
import multiprocessing as mp
import tempfile
import threading
import time
from multiprocessing.connection import Connection
from pathlib import Path
from typing import cast

from PySide6.QtCore import QThread, Signal

from atelier.core.models import CancelSignal, Event, Request
from atelier.core.runner import error_message, execute


def child_main(request: Request, workspace: str, cancel: CancelSignal, pipe: Connection) -> None:
    logging.basicConfig(level=logging.WARNING)
    try:
        execute(request, Path(workspace), cancel, pipe.send)
    finally:
        pipe.close()


class Job(QThread):
    """Supervise un processus isolé ; le thread ne touche jamais aux widgets."""

    update = Signal(dict)

    def __init__(self, request: Request) -> None:
        super().__init__()
        self.request = request
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        context = mp.get_context("spawn")
        reader, writer = context.Pipe(duplex=False)
        cancel = context.Event()
        process = None
        terminal = False
        stopping_since: float | None = None
        try:
            with tempfile.TemporaryDirectory(
                prefix=".atelier-",
                dir=self.request.destination,
            ) as workspace:
                process = context.Process(
                    target=child_main,
                    args=(self.request, workspace, cancel, writer),
                    daemon=True,
                )
                process.start()
                writer.close()
                while True:
                    if self._cancel.is_set() and stopping_since is None:
                        cancel.set()
                        stopping_since = time.monotonic()
                    if stopping_since is not None and time.monotonic() - stopping_since > 0.8:
                        break
                    if reader.poll(0.05):
                        try:
                            event = cast(Event, reader.recv())
                        except EOFError:
                            break
                        self.update.emit(event)
                        if event.get("kind") in {"finished", "cancelled", "fatal"}:
                            terminal = True
                            break
                    elif not process.is_alive():
                        break
                if not terminal:
                    if self._cancel.is_set():
                        self.update.emit(
                            {
                                "kind": "cancelled",
                                "message": "Annulé. Les résultats déjà terminés sont conservés.",
                            }
                        )
                    else:
                        self.update.emit(
                            {
                                "kind": "fatal",
                                "message": "Le moteur s’est arrêté de façon inattendue.",
                            }
                        )
                # Toujours arrêter le processus AVANT de nettoyer son dossier de travail.
                process.join(timeout=0.2)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=1)
                if process.is_alive():
                    process.kill()
                    process.join()
        except Exception as exc:
            self.update.emit({"kind": "fatal", "message": error_message(exc)})
        finally:
            if process is not None and process.pid is not None and process.is_alive():
                process.kill()
                process.join()
            reader.close()
            writer.close()
