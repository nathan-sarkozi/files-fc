from __future__ import annotations

import math
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, PngImagePlugin, TiffImagePlugin

from atelier.core.models import CancelSignal, ImageOptions, UserError, checkpoint

TARGETS = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "TIFF": ".tiff", "BMP": ".bmp"}
INPUT_FORMATS = {"PNG", "JPEG", "WEBP", "TIFF", "BMP", "GIF"}


def input_extensions() -> tuple[str, ...]:
    Image.init()
    return tuple(
        sorted(
            ext
            for ext, fmt in Image.registered_extensions().items()
            if fmt in INPUT_FORMATS and fmt in Image.OPEN
        )
    )


def available_targets() -> tuple[str, ...]:
    Image.init()
    return tuple(fmt for fmt in TARGETS if fmt in Image.SAVE)


@contextmanager
def open_image(path: Path) -> Iterator[Image.Image]:
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(path) as image:
                if image.format not in INPUT_FORMATS:
                    raise UserError("Ce format d’image n’est pas pris en charge.")
                if image.format == "PNG":
                    with path.open("rb") as stream:
                        header = stream.read(26)
                    if len(header) == 26 and header[24] > 8 and header[25] != 0:
                        raise UserError(
                            "PNG couleur 16 bits : le décodeur réduirait la profondeur à 8 bits. "
                            "Traitement refusé pour préserver la qualité."
                        )
                if isinstance(image, TiffImagePlugin.TiffImageFile):
                    depths = image.tag_v2.get(258, (8,))
                    if isinstance(depths, int):
                        depths = (depths,)
                    if any(depth > 8 for depth in depths) and image.mode not in {"I;16", "I;16B"}:
                        raise UserError(
                            "TIFF haute profondeur non compatible : aucune réduction à 8 bits "
                            "n’est effectuée."
                        )
                if getattr(image, "n_frames", 1) != 1:
                    raise UserError(
                        "Image animée ou multipage : traitement refusé pour ne perdre aucune image."
                    )
                yield image
        except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise UserError(
                "Image dépassant le seuil de sécurité du décodeur Pillow. "
                "Les protections contre les bombes de décompression restent actives."
            ) from exc


def convert_image(
    source: Path,
    staged: Path,
    options: ImageOptions,
    cancel: CancelSignal,
) -> list[str]:
    if options.target not in available_targets():
        raise UserError("Ce format cible n’est pas disponible dans cette installation.")
    if not 1 <= options.quality <= 100:
        raise UserError("La qualité doit être comprise entre 1 et 100.")
    notices: list[str] = []
    checkpoint(cancel)
    with open_image(source) as original:
        if original.mode not in {"1", "L", "LA", "P", "RGB", "RGBA", "I;16", "I;16B"}:
            raise UserError(
                f"Mode {original.mode} non pris en charge : conversion colorimétrique "
                "ou de profondeur nécessaire. Aucune conversion implicite n’a été effectuée."
            )
        if original.mode.startswith("I;16") and options.target not in {"PNG", "TIFF"}:
            raise UserError("Image 16 bits : choisissez PNG ou TIFF pour préserver sa profondeur.")
        original.load()
        checkpoint(cancel)
        if (
            options.copy_same_format
            and options.keep_metadata
            and original.format == options.target
            and original.getexif().get(274, 1) == 1
        ):
            with source.open("rb") as source_stream, staged.open("wb") as destination_stream:
                while chunk := source_stream.read(1024 * 1024):
                    checkpoint(cancel)
                    destination_stream.write(chunk)
            checkpoint(cancel)
            return ["Format identique : copie binaire, sans réencodage."]
        with ImageOps.exif_transpose(original) as image:
            kwargs: dict[str, Any] = {}
            original_mode = image.mode
            metadata = image.info.copy()
            exif = image.getexif()
            has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
            if options.target in {"JPEG", "BMP"}:
                if has_alpha:
                    rgba = image.convert("RGBA")
                    background = Image.new("RGB", image.size, "white")
                    background.paste(rgba, mask=rgba.getchannel("A"))
                    rgba.close()
                    image.close()
                    image = background
                    notices.append("Transparence composée sur un fond blanc.")
                elif image.mode not in {"RGB", "L"}:
                    converted = image.convert("RGB")
                    image.close()
                    image = converted
            elif (options.target == "WEBP" and image.mode not in {"RGB", "RGBA"}) or (
                options.target == "TIFF" and "transparency" in image.info
            ):
                converted = image.convert("RGBA" if has_alpha else "RGB")
                image.close()
                image = converted
            try:
                if options.target == "JPEG":
                    kwargs.update(quality=options.quality, subsampling=0, optimize=True)
                    notices.append("JPEG : réencodage avec perte, même à qualité 100.")
                elif options.target == "WEBP":
                    kwargs.update(lossless=options.webp_lossless, quality=options.quality, method=4)
                    if options.webp_lossless:
                        kwargs["exact"] = (
                            True  # Préserve aussi les couleurs des pixels transparents.
                        )
                    else:
                        notices.append("WebP : compression avec perte.")
                elif options.target == "TIFF":
                    kwargs["compression"] = "tiff_deflate"
                if options.keep_metadata:
                    if options.target in {"PNG", "JPEG", "WEBP", "TIFF"}:
                        if exif:
                            kwargs["exif"] = exif.tobytes()
                        if metadata.get("icc_profile"):
                            if original_mode == image.mode or original_mode == "P":
                                kwargs["icc_profile"] = metadata["icc_profile"]
                            else:
                                notices.append("Profil ICC omis après changement de mode couleur.")
                    dpi = metadata.get("dpi")
                    if (
                        options.target in {"PNG", "JPEG", "TIFF", "BMP"}
                        and isinstance(dpi, tuple)
                        and len(dpi) == 2
                        and all(
                            isinstance(d, (int, float)) and math.isfinite(d) and d > 0 for d in dpi
                        )
                    ):
                        kwargs["dpi"] = dpi
                    if options.target == "PNG":
                        text = PngImagePlugin.PngInfo()
                        for key, value in metadata.items():
                            if isinstance(key, str) and isinstance(value, str):
                                text.add_text(key, value)
                        kwargs["pnginfo"] = text
                else:
                    # Pillow réutilise implicitement certaines données de image.info.
                    transparency = image.info.get("transparency")
                    image.info.clear()
                    if transparency is not None:
                        image.info["transparency"] = transparency
                    image.getexif().clear()
                checkpoint(cancel)
                image.save(staged, format=options.target, **kwargs)
            finally:
                image.close()
    checkpoint(cancel)
    # Réouverture réelle : un encodage ayant produit un fichier invalide n’est pas publié.
    with Image.open(staged) as result:
        result.verify()
    return notices
