#!/usr/bin/env python3
"""Prépare une archive Linux avec wheels pour installation hors ligne, sans sudo."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wheelhouse", type=Path, help="Réutiliser hors ligne un dossier de wheels"
    )
    args = parser.parse_args()
    if platform.system() != "Linux":
        raise SystemExit("Construisez l’archive sur Linux.")
    root = Path(__file__).resolve().parent.parent
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--no-isolation"], cwd=root, check=True
    )
    python_tag = f"{sys.version_info.major}{sys.version_info.minor}"
    name = f"atelier-{version}-linux-{platform.machine()}-py{python_tag}"
    with tempfile.TemporaryDirectory(prefix="atelier-bundle-") as raw:
        bundle = Path(raw) / name
        (bundle / "wheelhouse").mkdir(parents=True)
        download = [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--no-cache-dir",
            "--only-binary=:all:",
            "--dest",
            str(bundle / "wheelhouse"),
            "-r",
            str(root / "requirements.lock"),
        ]
        if args.wheelhouse:
            download.extend(["--no-index", "--find-links", str(args.wheelhouse.resolve())])
        subprocess.run(download, check=True)
        shutil.copy2(
            root / f"dist/atelier_fichiers-{version}-py3-none-any.whl", bundle / "wheelhouse"
        )
        for file in ("README.md", "requirements.lock"):
            shutil.copy2(root / file, bundle / file)
        shutil.copytree(root / "docs", bundle / "docs")
        (bundle / "scripts").mkdir()
        shutil.copy2(root / "scripts/install_linux.py", bundle / "scripts/install_linux.py")
        shutil.copy2(root / "src/atelier/assets/atelier.svg", bundle / "atelier.svg")
        (bundle / "bundle.json").write_text(
            json.dumps(
                {
                    "python": f"{sys.version_info.major}.{sys.version_info.minor}",
                    "machine": platform.machine(),
                    "version": version,
                },
                indent=2,
            )
            + "\n"
        )
        archive = root / "dist" / (name + ".tar.gz")
        with tarfile.open(archive, "w:gz") as output:
            output.add(bundle, arcname=name)
        print(f"Archive prête : {archive}")


if __name__ == "__main__":
    main()
