"""Persistencia sencilla de preferencias locales de la aplicación."""

from __future__ import annotations

import json
import os
from pathlib import Path


def default_settings_path() -> Path:
    """Devuelve la ubicación de preferencias del usuario en Windows."""
    app_data = os.environ.get("APPDATA")
    base = Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
    return base / "AzaleaCore MPQ Studio" / "settings.json"


def load_workspace_settings(settings_path: Path | str) -> tuple[bool, Path | None]:
    """Devuelve si se recuerda la carpeta y la última ruta válida guardada."""
    try:
        data = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return True, None
    if not isinstance(data, dict):
        return True, None

    remember = data.get("remember_workspace", True)
    if not isinstance(remember, bool):
        remember = True
    saved_path = data.get("last_workspace")
    if not remember or not isinstance(saved_path, str) or not saved_path:
        return remember, None
    workspace = Path(saved_path)
    return remember, workspace if workspace.is_dir() else None


def save_workspace_settings(
    settings_path: Path | str,
    *,
    remember: bool,
    workspace: Path | str | None,
) -> None:
    """Guarda la preferencia sustituyendo el JSON anterior de forma atómica."""
    destination = Path(settings_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    payload = {
        "remember_workspace": remember,
        "last_workspace": str(workspace) if remember and workspace is not None else None,
    }
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
