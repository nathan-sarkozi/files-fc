from __future__ import annotations

import os
import stat
from pathlib import Path

from atelier.core.models import UserError


def source_file(path: Path) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise UserError(
            f"{path.name} : choisissez un fichier ordinaire, pas un dossier ou un périphérique."
        )
    return resolved


def output_directory(path: Path) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_dir():
        raise UserError("Le dossier de destination n’existe pas.")
    return resolved


def output_name(name: str) -> str:
    clean = name.strip()
    if not clean or clean in {".", ".."} or any(c in clean for c in "/\\\x00\n\r"):
        raise UserError("Le nom de sortie doit être un nom de fichier, sans chemin.")
    if not clean.lower().endswith(".pdf"):
        clean += ".pdf"
    return clean


def publish(staged: Path, destination: Path, name: str) -> Path:
    """Publication atomique sans écrasement, même en présence d’une course ou d’un lien."""
    if Path(name).name != name or name in {"", ".", ".."}:
        raise UserError("Nom de sortie invalide.")
    # Le temporaire est sur le même système de fichiers que la destination.
    # link() échoue si le nom existe ; aucun test exists()+replace() vulnérable aux courses.
    with staged.open("rb") as stream:
        os.fsync(stream.fileno())
    stem, suffix = Path(name).stem, Path(name).suffix
    counter = 0
    while True:
        candidate = destination / (name if counter == 0 else f"{stem} ({counter}){suffix}")
        try:
            os.link(staged, candidate)
        except FileExistsError:
            counter += 1
            continue
        except OSError as exc:
            raise UserError(
                "Impossible de publier le résultat sans écrasement. "
                "Choisissez un dossier local acceptant les liens physiques "
                f"(par exemple ext4 ou Btrfs). Détail : {exc.strerror}"
            ) from exc
        staged.unlink()
        return candidate
