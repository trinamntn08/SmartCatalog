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
    settings_path: Path | None


def backup_catalog(
    *,
    database_path: str | Path,
    assets_dir: str | Path,
    catalog_pdfs_dir: str | Path,
    settings_path: str | Path,
    backup_dir: str | Path,
) -> BackupManifest:
    source_database = Path(database_path)
    destination = Path(backup_dir)
    destination.mkdir(parents=True, exist_ok=True)

    backup_database = destination / "catalog.db"
    source_connection = sqlite3.connect(str(source_database))
    try:
        destination_connection = sqlite3.connect(str(backup_database))
        try:
            source_connection.backup(destination_connection)
        finally:
            destination_connection.close()
    finally:
        source_connection.close()

    assets_source = Path(assets_dir)
    assets_destination: Path | None = None
    if assets_source.exists():
        assets_destination = destination / "assets"
        shutil.copytree(
            assets_source,
            assets_destination,
            dirs_exist_ok=True,
        )

    pdfs_source = Path(catalog_pdfs_dir)
    pdfs_destination: Path | None = None
    if pdfs_source.exists():
        pdfs_destination = destination / "catalog_pdfs"
        shutil.copytree(
            pdfs_source,
            pdfs_destination,
            dirs_exist_ok=True,
        )

    settings_source = Path(settings_path)
    settings_destination: Path | None = None
    if settings_source.exists():
        settings_destination = destination / "settings.json"
        shutil.copy2(settings_source, settings_destination)

    return BackupManifest(
        backup_dir=destination,
        database_path=backup_database,
        assets_path=assets_destination,
        catalog_pdfs_path=pdfs_destination,
        settings_path=settings_destination,
    )
