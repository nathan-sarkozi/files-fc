from __future__ import annotations

from collections.abc import MutableMapping


def clean_vscode_snap_environment(environment: MutableMapping[str, str]) -> None:
    """Ne transmet pas les schémas/modules privés de VS Code Snap au GTK de l’hôte.

    Cette correction ne change que l’environnement de l’application, jamais celui du shell.
    Les chemins utilisateur et les réglages sans lien avec VS Code restent intacts.
    """

    def is_code_snap(value: str) -> bool:
        return "/snap/code/" in value or "/snap/code-insiders/" in value

    for key in (
        "GSETTINGS_SCHEMA_DIR",
        "GTK_PATH",
        "GTK_EXE_PREFIX",
        "GTK_DATA_PREFIX",
        "GIO_MODULE_DIR",
        "GIO_EXTRA_MODULES",
    ):
        value = environment.get(key, "")
        if is_code_snap(value):
            remaining = ":".join(part for part in value.split(":") if not is_code_snap(part))
            if remaining:
                environment[key] = remaining
            else:
                environment.pop(key, None)
    if is_code_snap(environment.get("XDG_DATA_DIRS", "")):
        data_paths = [
            part
            for part in environment["XDG_DATA_DIRS"].split(":")
            if part and not is_code_snap(part)
        ]
        environment["XDG_DATA_DIRS"] = ":".join(data_paths) or "/usr/local/share:/usr/share"
