from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path

import img2pdf
from pypdf import PdfReader, PdfWriter

from atelier.core.images import open_image
from atelier.core.models import CancelSignal, UserError, checkpoint


def validate_pdf(reader: PdfReader, name: str) -> None:
    if reader.is_encrypted:
        raise UserError(f"{name} est chiffré. Exportez d’abord une copie déverrouillée.")
    if not reader.pages:
        raise UserError(f"{name} ne contient aucune page.")
    fields = reader.get_fields() or {}
    if any(field.get("/FT") == "/Sig" for field in fields.values()):
        raise UserError(
            f"{name} contient une signature numérique : une modification l’invaliderait."
        )


def merge_pdfs(
    sources: tuple[Path, ...],
    staged: Path,
    cancel: CancelSignal,
    progress: Callable[[int, str], None],
) -> None:
    # Les flux restent ouverts jusqu’à l’écriture ; pypdf peut charger des objets à la demande.
    with ExitStack() as stack, PdfWriter() as writer:
        for index, path in enumerate(sources):
            checkpoint(cancel)
            stream = stack.enter_context(path.open("rb"))
            reader = PdfReader(stream, strict=True)
            validate_pdf(reader, path.name)
            fields = reader.get_fields() or {}
            if fields:
                reader.add_form_topname(f"document_{index + 1}")
            writer.append(reader, excluded_fields=["/AA", "/B"])
            progress(index, path.name)
        checkpoint(cancel)
        writer.add_metadata({"/Producer": "Atelier · pypdf"})
        writer.write(staged)
    checkpoint(cancel)
    with staged.open("rb") as stream:
        if not PdfReader(stream, strict=True).pages:
            raise UserError("Le PDF produit ne contient aucune page.")


def images_pdf(
    sources: tuple[Path, ...],
    staged: Path,
    cancel: CancelSignal,
    progress: Callable[[int, str], None],
) -> None:
    # Validation séquentielle sans décoder tous les pixels : JPEG/PNG sont incorporés
    # directement lorsque img2pdf le permet. Aucune conversion intermédiaire en JPEG.
    for index, path in enumerate(sources):
        checkpoint(cancel)
        with open_image(path) as image:
            if image.mode not in {"1", "L", "LA", "P", "RGB", "RGBA", "I;16", "I;16B"}:
                raise UserError(f"{path.name} : mode couleur {image.mode} non pris en charge.")
        progress(index, path.name)
    checkpoint(cancel)
    with staged.open("wb") as output:
        img2pdf.convert(
            *(str(path) for path in sources),
            outputstream=output,
            rotation=img2pdf.Rotation.ifvalid,
            producer="Atelier / img2pdf",
        )
    checkpoint(cancel)
    with staged.open("rb") as stream:
        reader = PdfReader(stream, strict=True)
        if len(reader.pages) != len(sources):
            raise UserError("Le nombre de pages produit ne correspond pas au nombre d’images.")
