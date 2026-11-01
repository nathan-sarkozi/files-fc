from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from atelier.core.files import output_name, publish, source_file
from atelier.core.models import CancelSignal, Event, PdfOutput, PdfPlan, UserError, checkpoint
from atelier.core.pdf import validate_pdf


@dataclass(frozen=True)
class PdfInfo:
    path: Path
    page_count: int
    stamp: tuple[int, int, int, int]
    notices: tuple[str, ...]


def file_stamp(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def check_source(path: Path, expected: tuple[int, int, int, int]) -> None:
    if file_stamp(path) != expected:
        raise UserError(
            "Le PDF source a été modifié depuis son ouverture. Réimportez-le avant de continuer."
        )


def inspect_pdf(path: Path) -> PdfInfo:
    path = source_file(path)
    stamp = file_stamp(path)
    with path.open("rb") as stream:
        reader = PdfReader(stream, strict=True)
        validate_pdf(reader, path.name)
        notices = []
        if reader.get_fields():
            notices.append(
                "Formulaire présent : aperçu des champs incomplet ; vérifiez après export."
            )
        if "/Outlines" in reader.root_object:
            notices.append("Les signets compatibles vers des pages conservées seront importés.")
        if "/StructTreeRoot" in reader.root_object:
            notices.append("Le balisage d’accessibilité n’est pas garanti après manipulation.")
        info = PdfInfo(path, len(reader.pages), stamp, tuple(notices))
    check_source(path, stamp)
    return info


def parse_pages(text: str, count: int) -> tuple[int, ...]:
    """Positions humaines 1-based → indices, ordre saisi, sans répétition implicite."""
    if count <= 0 or not text.strip():
        raise UserError("Indiquez des positions, par exemple 1-3, 5.")
    result: list[int] = []
    seen: set[int] = set()
    for part in text.split(","):
        match = re.fullmatch(r"\s*([0-9]+)\s*(?:-\s*([0-9]+))?\s*", part)
        if not match:
            raise UserError(f"Plage invalide : « {part.strip()} ». Exemple : 1-3, 5.")
        start = int(match[1])
        end = int(match[2]) if match[2] else start
        if not 1 <= start <= end <= count:
            raise UserError(f"Positions hors limites ou inversées : {start}-{end} (1 à {count}).")
        for index in range(start - 1, end):
            if index in seen:
                raise UserError(f"La position {index + 1} apparaît plusieurs fois.")
            seen.add(index)
            result.append(index)
    return tuple(result)


def parse_split(text: str, count: int) -> tuple[tuple[int, ...], ...]:
    if not text.strip():
        raise UserError("Séparez les fichiers par un point-virgule : 1-3 ; 4-6.")
    return tuple(parse_pages(group, count) for group in text.split(";"))


def validate_output(output: PdfOutput, count: int) -> str:
    name = output_name(output.name)
    if not output.pages:
        raise UserError("Un PDF de sortie doit contenir au moins une page.")
    indices = set()
    for page in output.pages:
        if type(page.index) is not int or not 0 <= page.index < count:
            raise UserError("Une page demandée n’existe pas dans le PDF source.")
        if type(page.rotation) is not int or page.rotation not in {0, 90, 180, 270}:
            raise UserError("Rotation invalide : utilisez 0°, 90°, 180° ou 270°.")
        if page.index in indices:
            raise UserError("Une même page apparaît plusieurs fois dans un fichier de sortie.")
        indices.add(page.index)
    return name


def export_pdf(
    source: Path,
    plan: PdfPlan,
    destination: Path,
    workspace: Path,
    cancel: CancelSignal,
    emit: Callable[[Event], None],
) -> None:
    if not plan.outputs:
        raise UserError("Aucun document de sortie n’est demandé.")
    check_source(source, plan.source_stamp)
    with source.open("rb") as stream:
        reader = PdfReader(stream, strict=True)
        validate_pdf(reader, source.name)
        names = [validate_output(output, len(reader.pages)) for output in plan.outputs]
        total = sum(len(output.pages) for output in plan.outputs)
        done = 0
        last_progress = -1
        staged_files: list[Path] = []
        for number, output in enumerate(plan.outputs):
            checkpoint(cancel)
            staged = workspace / f"pdf-{number}.pdf"
            with PdfWriter() as writer:
                # append remappe les destinations et formulaires compatibles.
                writer.append(
                    reader,
                    pages=[page.index for page in output.pages],
                    import_outline=True,
                    excluded_fields=["/AA", "/B"],
                )
                for position, page in enumerate(output.pages):
                    checkpoint(cancel)
                    if page.rotation:
                        writer.pages[position].rotate(page.rotation)
                    done += 1
                    percentage = done * 80 // total
                    if percentage != last_progress:
                        emit(
                            {
                                "kind": "progress",
                                "progress": percentage,
                                "message": f"Préparation de la page {done} sur {total}",
                            }
                        )
                        last_progress = percentage
                if reader.metadata:
                    writer.add_metadata(
                        {
                            key: str(value)
                            for key, value in reader.metadata.items()
                            if value is not None
                        }
                    )
                if reader.xmp_metadata is not None:
                    writer.xmp_metadata = reader.xmp_metadata
                writer.add_metadata({"/Producer": "Atelier 0.2 / pypdf"})
                writer.write(staged)
            checkpoint(cancel)
            with staged.open("rb") as result_stream:
                result = PdfReader(result_stream, strict=True)
                if len(result.pages) != len(output.pages):
                    raise UserError(
                        "Le nombre de pages produit ne correspond pas à l’export demandé."
                    )
                for result_page, spec in zip(result.pages, output.pages, strict=True):
                    checkpoint(cancel)
                    original = reader.pages[spec.index]
                    if (
                        tuple(result_page.mediabox) != tuple(original.mediabox)
                        or tuple(result_page.cropbox) != tuple(original.cropbox)
                        or result_page.rotation != (original.rotation + spec.rotation) % 360
                    ):
                        raise UserError(
                            "Les dimensions ou la rotation du PDF produit sont incohérentes."
                        )
            staged_files.append(staged)
        check_source(source, plan.source_stamp)
        # Tout est écrit et validé avant la première publication. Chaque fichier est atomique.
        # Plusieurs sorties ne constituent pas une transaction globale : les sorties déjà
        # publiées restent disponibles en cas d’annulation ou d’erreur de disque ultérieure.
        for number, (staged, name) in enumerate(zip(staged_files, names, strict=True)):
            checkpoint(cancel)
            result_path = publish(staged, destination, name)
            emit(
                {
                    "kind": "output",
                    "index": number,
                    "path": str(result_path),
                    "message": f"{len(plan.outputs[number].pages)} page(s) exportée(s).",
                }
            )
            emit({"kind": "progress", "progress": 80 + (number + 1) * 20 // len(names)})
