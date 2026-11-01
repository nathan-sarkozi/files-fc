from __future__ import annotations

import multiprocessing as mp
import threading
from contextlib import closing
from dataclasses import dataclass
from multiprocessing.connection import Connection
from pathlib import Path
from typing import cast

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from atelier.core.pdf_tools import check_source, inspect_pdf
from atelier.core.runner import error_message

THUMBNAIL_EDGE = 240


@dataclass(frozen=True)
class Raster:
    index: int
    width: int
    height: int
    pixels: bytes


def render_process(path: Path, pipe: Connection) -> None:
    # PDFium n’est jamais appelé depuis plusieurs threads ; les handles restent dans ce processus.
    import pypdfium2 as pdfium

    try:
        info = inspect_pdf(path)
        with pdfium.PdfDocument(path) as document:
            if len(document) != info.page_count:
                raise ValueError("Les moteurs PDF ne s’accordent pas sur le nombre de pages.")
            pipe.send(("ready", info))
            while True:
                index = cast(int | None, pipe.recv())
                if index is None:
                    break
                check_source(path, info.stamp)
                try:
                    with closing(document[index]) as page:
                        width, height = page.get_size()
                        if width <= 0 or height <= 0:
                            raise ValueError("Dimensions de page invalides.")
                        with closing(
                            page.render(
                                scale=THUMBNAIL_EDGE / max(width, height), may_draw_forms=False
                            )
                        ) as bitmap:
                            with bitmap.to_pil().convert("RGB") as image:
                                image.thumbnail((THUMBNAIL_EDGE, THUMBNAIL_EDGE))
                                raster = Raster(index, image.width, image.height, image.tobytes())
                    check_source(path, info.stamp)
                    pipe.send(("image", raster))
                except Exception as exc:
                    check_source(path, info.stamp)
                    pipe.send(("page_error", (index, error_message(exc))))
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:
        try:
            pipe.send(("error", error_message(exc)))
        except (EOFError, BrokenPipeError):
            pass
    finally:
        pipe.close()


class PreviewSession(QThread):
    loaded = Signal(object)
    thumbnail = Signal(int, QImage)
    failed = Signal(str)
    page_failed = Signal(int, str)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._wanted: tuple[int, ...] = ()

    def request(self, indices: tuple[int, ...]) -> None:
        # Remplace la demande, plutôt qu’accumuler les pages de positions déjà quittées.
        with self._lock:
            self._wanted = indices[:64]

    def cancel(self) -> None:
        self._stop.set()

    def run(self) -> None:
        context = mp.get_context("spawn")
        parent, child = context.Pipe()
        process = context.Process(target=render_process, args=(self.path, child), daemon=True)
        try:
            process.start()
            child.close()
            ready = False
            in_flight: int | None = None
            while not self._stop.is_set():
                if parent.poll(0.04):
                    kind, payload = parent.recv()
                    if kind == "ready":
                        ready = True
                        self.loaded.emit(payload)
                    elif kind == "image":
                        raster = cast(Raster, payload)
                        image = QImage(
                            raster.pixels,
                            raster.width,
                            raster.height,
                            raster.width * 3,
                            QImage.Format.Format_RGB888,
                        ).copy()
                        self.thumbnail.emit(raster.index, image)
                        in_flight = None
                        with self._lock:
                            self._wanted = tuple(
                                index for index in self._wanted if index != raster.index
                            )
                    elif kind == "page_error":
                        index, message = payload
                        self.page_failed.emit(index, message)
                        in_flight = None
                    elif kind == "error":
                        self.failed.emit(str(payload))
                        return
                elif not process.is_alive():
                    self.failed.emit("Le moteur de prévisualisation s’est arrêté.")
                    return
                if ready and in_flight is None:
                    with self._lock:
                        if self._wanted:
                            in_flight = self._wanted[0]
                            self._wanted = self._wanted[1:]
                    if in_flight is not None:
                        parent.send(in_flight)
        except (EOFError, OSError) as exc:
            if not self._stop.is_set():
                self.failed.emit(error_message(exc))
        finally:
            if process.pid is not None:
                if process.is_alive():
                    try:
                        parent.send(None)
                    except (OSError, BrokenPipeError):
                        pass
                    process.join(timeout=0.15)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=1)
                if process.is_alive():
                    process.kill()
                    process.join()
            parent.close()
            child.close()
