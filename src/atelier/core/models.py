from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol, TypedDict


class Operation(StrEnum):
    CONVERT = "convert"
    MERGE = "merge"
    IMAGES_PDF = "images_pdf"
    PDF_TOOLS = "pdf_tools"


class CancelSignal(Protocol):
    def is_set(self) -> bool: ...


class Cancelled(Exception):
    """Annulation demandée par l’utilisateur."""


class UserError(Exception):
    """Erreur affichable dans l’interface."""


class Event(TypedDict, total=False):
    kind: str
    index: int
    progress: int
    message: str
    path: str
    state: str


@dataclass(frozen=True)
class ImageOptions:
    target: str = "PNG"
    quality: int = 92
    webp_lossless: bool = True
    keep_metadata: bool = True
    copy_same_format: bool = True


@dataclass(frozen=True)
class PdfPage:
    index: int
    rotation: int = 0


@dataclass(frozen=True)
class PdfOutput:
    name: str
    pages: tuple[PdfPage, ...]


@dataclass(frozen=True)
class PdfPlan:
    source_stamp: tuple[int, int, int, int]
    outputs: tuple[PdfOutput, ...]


@dataclass(frozen=True)
class Request:
    operation: Operation
    sources: tuple[Path, ...]
    destination: Path
    name: str = "assemblage.pdf"
    options: ImageOptions = ImageOptions()
    pdf_plan: PdfPlan | None = None


def checkpoint(cancel: CancelSignal) -> None:
    if cancel.is_set():
        raise Cancelled
