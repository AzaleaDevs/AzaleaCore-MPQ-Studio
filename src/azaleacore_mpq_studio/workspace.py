"""Carpeta de trabajo y extracción segura de archivos MPQ."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .mpq import MPQArchive, MPQError


@dataclass(frozen=True)
class Workspace:
    root: Path
    export_dir: Path
    package_dir: Path


@dataclass(frozen=True)
class ExportRequest:
    source_mpq: Path
    internal_path: str


@dataclass(frozen=True)
class ExportResult:
    source_mpq: str
    internal_path: str
    output_path: str
    size: int
    sha256: str


def prepare_workspace(root: Path | str) -> Workspace:
    resolved = Path(root).resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    export_dir = resolved / "exportar"
    package_dir = resolved / "empaquetar"
    export_dir.mkdir(exist_ok=True)
    package_dir.mkdir(exist_ok=True)
    return Workspace(resolved, export_dir, package_dir)


def safe_internal_destination(base: Path, internal_path: str) -> Path:
    normalized = internal_path.replace("/", "\\")
    parts = [part for part in normalized.split("\\") if part]
    if not parts or any(part in (".", "..") for part in parts):
        raise ValueError(f"Ruta interna MPQ no segura: {internal_path}")
    candidate = base.joinpath(*parts).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise ValueError(f"La ruta sale de la carpeta de exportación: {internal_path}") from exc
    return candidate


def export_files(
    requests: Iterable[ExportRequest],
    workspace: Workspace,
    *,
    overwrite: bool = False,
) -> tuple[ExportResult, ...]:
    planned = [
        (request, safe_internal_destination(workspace.export_dir, request.internal_path))
        for request in requests
    ]
    collisions = [destination for _, destination in planned if destination.exists()]
    if collisions and not overwrite:
        raise FileExistsError(str(collisions[0]))

    payloads: list[tuple[ExportRequest, Path, bytes]] = []
    for request, destination in planned:
        with MPQArchive(request.source_mpq) as archive:
            payload = archive.read_file(request.internal_path)
        if payload is None:
            raise MPQError(
                f"Ya no se encuentra {request.internal_path} en {request.source_mpq}."
            )
        payloads.append((request, destination, payload))

    results: list[ExportResult] = []
    for request, destination, payload in payloads:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if destination.exists() and not overwrite:
                raise FileExistsError(str(destination))
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        results.append(
            ExportResult(
                source_mpq=str(request.source_mpq),
                internal_path=request.internal_path,
                output_path=str(destination),
                size=len(payload),
                sha256=hashlib.sha256(payload).hexdigest().upper(),
            )
        )

    manifest = workspace.root / "azaleacore-export-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "export_directory": str(workspace.export_dir),
                "files": [asdict(result) for result in results],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return tuple(results)
