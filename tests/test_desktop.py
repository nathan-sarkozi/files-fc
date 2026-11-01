from atelier.desktop import clean_vscode_snap_environment


def test_only_vscode_snap_paths_removed() -> None:
    env = {
        "GSETTINGS_SCHEMA_DIR": "/home/u/snap/code/268/schemas",
        "GTK_PATH": "/snap/code/268/gtk:/my/custom/gtk",
        "XDG_DATA_DIRS": "/snap/code/268/usr/share:/usr/share:/home/u/.local/share",
        "PATH": "/snap/bin:/usr/bin",
        "OTHER": "unchanged",
    }
    clean_vscode_snap_environment(env)
    assert "GSETTINGS_SCHEMA_DIR" not in env
    assert env["GTK_PATH"] == "/my/custom/gtk"
    assert env["XDG_DATA_DIRS"] == "/usr/share:/home/u/.local/share"
    assert env["PATH"] == "/snap/bin:/usr/bin"
    assert env["OTHER"] == "unchanged"


def test_regular_environment_untouched() -> None:
    env = {"GSETTINGS_SCHEMA_DIR": "/my/schemas", "XDG_DATA_DIRS": "/usr/share"}
    before = env.copy()
    clean_vscode_snap_environment(env)
    assert env == before
