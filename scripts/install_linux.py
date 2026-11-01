#!/usr/bin/env python3
"""Installer personnel, hors ligne lorsqu’il est utilisé depuis l’archive Linux."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import venv
from pathlib import Path


def desktop_quote(value: str) -> str:
    # L’Exec d’un .desktop a sa propre syntaxe, distincte de celle du shell.
    escaped = (
        value.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    )
    return '"' + escaped.replace("%", "%%") + '"'


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Installer Atelier pour votre compte Linux, sans sudo"
    )
    parser.add_argument("--prefix", type=Path, default=Path.home() / ".local/share/atelier")
    parser.add_argument("--bin-dir", type=Path, default=Path.home() / ".local/bin")
    parser.add_argument(
        "--desktop-dir",
        type=Path,
        default=Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
        / "applications",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    if platform.system() != "Linux":
        parser.error("Cet installateur est destiné à Linux.")
    manifest = root / "bundle.json"
    if not manifest.is_file() or not (root / "wheelhouse").is_dir():
        parser.error("Utilisez cet installateur depuis l’archive produite par build_linux.py.")
    target = json.loads(manifest.read_text())
    if (
        target["python"] != f"{sys.version_info.major}.{sys.version_info.minor}"
        or target["machine"] != platform.machine()
    ):
        parser.error(f"Archive prévue pour Python {target['python']} / {target['machine']}.")
    prefix = args.prefix.expanduser().resolve()
    bindir = args.bin_dir.expanduser().resolve()
    desktopdir = args.desktop_dir.expanduser().resolve()
    launcher = bindir / "atelier"
    desktop = desktopdir / "fr.atelierlocal.Atelier.desktop"
    # Une installation existante n’est jamais supprimée automatiquement.
    if any(path.exists() or path.is_symlink() for path in (prefix, launcher, desktop)):
        parser.error(
            "Une destination existe déjà. Choisissez d’autres chemins "
            "ou retirez votre ancienne installation."
        )
    if any(c in str(path) for path in (prefix, bindir, desktopdir) for c in "\n\r\x00"):
        parser.error("Chemin contenant un caractère de contrôle.")
    print(f"Installation hors ligne : {prefix}\nLanceur : {launcher}\nMenu : {desktop}")
    print("Aucune dépendance système ne sera installée ou modifiée.")
    created: list[Path] = []
    try:
        prefix.mkdir(parents=True)
        created.append(prefix)
        venv.EnvBuilder(with_pip=True).create(prefix / "venv")
        subprocess.run(
            [
                str(prefix / "venv/bin/python"),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-cache-dir",
                "--find-links",
                str(root / "wheelhouse"),
                "--requirement",
                str(root / "requirements.lock"),
                f"atelier-fichiers=={target['version']}",
            ],
            check=True,
        )
        shutil.copy2(root / "atelier.svg", prefix / "atelier.svg")
        shutil.copytree(root / "docs", prefix / "docs")
        shutil.copy2(root / "README.md", prefix / "README.md")
        bindir.mkdir(parents=True, exist_ok=True)
        # Les fichiers de lancement sont créés en mode exclusif.
        with launcher.open("x") as stream:
            created.append(launcher)
            stream.write(
                "#!/bin/sh\nexec " + shlex.quote(str(prefix / "venv/bin/atelier")) + ' "$@"\n'
            )
        launcher.chmod(0o755)
        desktopdir.mkdir(parents=True, exist_ok=True)
        with desktop.open("x") as stream:
            created.append(desktop)
            stream.write(
                "[Desktop Entry]\nType=Application\nVersion=1.0\nName=Atelier\n"
                "Comment=Convertir des images et assembler des PDF, localement\n"
                f"Exec={desktop_quote(str(launcher))} %F\n"
                f"Icon={prefix / 'atelier.svg'}\nTerminal=false\n"
                "Categories=Graphics;\nStartupNotify=true\n"
            )
    except Exception:
        for path in reversed(created):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        raise
    print(f"Installation terminée. Lancez {launcher} ou cherchez Atelier dans le menu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
