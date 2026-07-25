from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BackupManifest:
    backup_dir: Path
    database_path: Path
    assets_path: Path | None
    catalog_pdfs_path: Path | None


class BackupError(RuntimeError):
    """Raised when a catalog backup step cannot be completed."""


def backup_catalog(
    *,
    database_path: str | Path,
    assets_dir: str | Path,
    catalog_pdfs_dir: str | Path,
    backup_dir: str | Path,
) -> BackupManifest:
    source_database = Path(database_path)
    destination = Path(backup_dir)
    if not source_database.is_file():
        raise BackupError(f"Backup database does not exist: {source_database}")
    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BackupError(
            f"Could not create backup directory '{destination}': {exc}"
        ) from exc

    backup_database = destination / "catalog.db"
    try:
        source_connection = sqlite3.connect(str(source_database))
        try:
            destination_connection = sqlite3.connect(str(backup_database))
            try:
                source_connection.backup(destination_connection)
            finally:
                destination_connection.close()
        finally:
            source_connection.close()
    except sqlite3.Error as exc:
        raise BackupError(
            f"Could not back up database '{source_database}' "
            f"to '{backup_database}': {exc}"
        ) from exc

    assets_source = Path(assets_dir)
    assets_destination: Path | None = None
    if assets_source.exists():
        assets_destination = destination / "assets"
        try:
            shutil.copytree(
                assets_source,
                assets_destination,
                dirs_exist_ok=True,
            )
        except OSError as exc:
            raise BackupError(
                f"Could not back up assets '{assets_source}' "
                f"to '{assets_destination}': {exc}"
            ) from exc

    pdfs_source = Path(catalog_pdfs_dir)
    pdfs_destination: Path | None = None
    if pdfs_source.exists():
        pdfs_destination = destination / "catalog_pdfs"
        try:
            shutil.copytree(
                pdfs_source,
                pdfs_destination,
                dirs_exist_ok=True,
            )
        except OSError as exc:
            raise BackupError(
                f"Could not back up catalog PDFs '{pdfs_source}' "
                f"to '{pdfs_destination}': {exc}"
            ) from exc

    return BackupManifest(
        backup_dir=destination,
        database_path=backup_database,
        assets_path=assets_destination,
        catalog_pdfs_path=pdfs_destination,
    )
