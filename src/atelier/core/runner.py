from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from atelier.core.files import output_directory, output_name, publish, source_file
from atelier.core.images import TARGETS, convert_image
from atelier.core.models import Cancelled, CancelSignal, Event, Operation, Request, checkpoint
from atelier.core.pdf import images_pdf, merge_pdfs
from atelier.core.pdf_tools import export_pdf

logger = logging.getLogger(__name__)


def error_message(exc: Exception) -> str:
    if isinstance(exc, MemoryError):
        return "Mémoire insuffisante pour ce fichier. Les originaux sont préservés."
    if isinstance(exc, PermissionError):
        return "Accès refusé : vérifiez les permissions du fichier et du dossier de sortie."
    if isinstance(exc, FileNotFoundError):
        return "Un fichier ou le dossier de sortie n’existe plus."
    return str(exc) or type(exc).__name__


def execute(
    request: Request,
    workspace: Path,
    cancel: CancelSignal,
    emit: Callable[[Event], None],
) -> None:
    """Une conversion échouée n’interrompt pas le lot ; un assemblage est indivisible."""
    try:
        destination = output_directory(request.destination)
        if not request.sources:
            raise ValueError("Ajoutez au moins un fichier.")
        if workspace.resolve().parent != destination:
            raise ValueError("Le dossier temporaire doit être dans le dossier de sortie.")
        if request.operation == Operation.CONVERT:
            for index, source in enumerate(request.sources):
                checkpoint(cancel)
                emit({"kind": "item", "index": index, "state": "running", "message": "Conversion…"})
                staged = workspace / "image.tmp"
                try:
                    validated = source_file(source)
                    notices = convert_image(validated, staged, request.options, cancel)
                    checkpoint(cancel)
                    result = publish(
                        staged, destination, source.stem + TARGETS[request.options.target]
                    )
                    emit(
                        {
                            "kind": "item",
                            "index": index,
                            "state": "success",
                            "path": str(result),
                            "message": " · ".join(notices) or "Conversion terminée.",
                        }
                    )
                except Cancelled:
                    raise
                except Exception as exc:
                    logger.exception("Conversion échouée : %s", source.name)
                    emit(
                        {
                            "kind": "item",
                            "index": index,
                            "state": "error",
                            "message": error_message(exc),
                        }
                    )
                finally:
                    staged.unlink(missing_ok=True)
                emit({"kind": "progress", "progress": (index + 1) * 100 // len(request.sources)})
        elif request.operation == Operation.PDF_TOOLS:
            if len(request.sources) != 1 or request.pdf_plan is None:
                raise ValueError("Les outils PDF nécessitent un document et un plan d’export.")
            export_pdf(
                source_file(request.sources[0]),
                request.pdf_plan,
                destination,
                workspace,
                cancel,
                emit,
            )
        elif request.operation in {Operation.MERGE, Operation.IMAGES_PDF}:
            sources = tuple(source_file(source) for source in request.sources)
            name = output_name(request.name)
            staged = workspace / "assemblage.pdf"

            def progress(index: int, filename: str) -> None:
                emit(
                    {
                        "kind": "item",
                        "index": index,
                        "state": "running",
                        "message": "Préparé · assemblage en cours",
                    }
                )
                emit(
                    {
                        "kind": "progress",
                        "progress": (index + 1) * 85 // len(sources),
                        "message": filename,
                    }
                )

            engine = merge_pdfs if request.operation == Operation.MERGE else images_pdf
            engine(sources, staged, cancel, progress)
            checkpoint(cancel)
            result = publish(staged, destination, name)
            for index in range(len(sources)):
                emit(
                    {
                        "kind": "item",
                        "index": index,
                        "state": "success",
                        "path": str(result),
                        "message": "Assemblage terminé.",
                    }
                )
            emit({"kind": "progress", "progress": 100})
        else:
            raise ValueError("Opération non prise en charge.")
        emit({"kind": "finished"})
    except Cancelled:
        emit(
            {
                "kind": "cancelled",
                "message": "Traitement annulé. Les résultats déjà terminés sont conservés.",
            }
        )
    except Exception as exc:
        logger.exception("Traitement échoué")
        emit({"kind": "fatal", "message": error_message(exc)})
