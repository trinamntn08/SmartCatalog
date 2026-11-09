"""Validate and package a pristine SmartCatalog one-folder Windows build."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
import zipfile


class ReleaseError(ValueError):
    """The folder is incomplete or contains content unsuitable for delivery."""


def verify_release(release_dir: Path) -> list[Path]:
    if release_dir.is_symlink() or release_dir.is_junction():
        raise ReleaseError(f"Release directory must not be a link: {release_dir}")
    root = release_dir.resolve()
    if not root.is_dir():
        raise ReleaseError(f"Release directory does not exist or is a link: {root}")
    expected = {"SmartCatalog.exe", "_internal", "icons", "README.md"}
    actual = {path.name for path in root.iterdir()}
    if actual != expected:
        raise ReleaseError(
            f"Unexpected release layout in {root}; missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}. Package a fresh build before launching it."
        )
    files: list[Path] = []
    directories = [root]
    while directories:
        for path in sorted(directories.pop().iterdir()):
            if path.is_symlink() or path.is_junction():
                raise ReleaseError(f"Linked content is not allowed in a release: {path}")
            relative = path.relative_to(root)
            if any(part.casefold() in {"config", "to_integrate", "mupdf-devel"} for part in relative.parts):
                raise ReleaseError(f"Runtime data or development content in release: {relative}")
            if path.is_dir():
                directories.append(path)
            elif path.is_file():
                if path.suffix.casefold() in {".db", ".sqlite", ".sqlite3", ".pdf", ".log", ".tmp"}:
                    raise ReleaseError(f"User data or transient file in release: {relative}")
                if path.name.casefold() in {"settings.json", "dictionary.csv"}:
                    raise ReleaseError(f"User settings in release: {relative}")
                files.append(path)
    required_files = [
        root / "SmartCatalog.exe", root / "README.md",
        root / "icons" / "icon.ico", root / "icons" / "bg.jpg",
        root / "_internal" / "base_library.zip",
        root / "_internal" / f"python{sys.version_info.major}{sys.version_info.minor}.dll",
        root / "_internal" / "fitz" / "__init__.py",
        root / "_internal" / "pymupdf" / "__init__.py",
    ]
    for path in required_files:
        if not path.is_file() or not path.stat().st_size:
            raise ReleaseError(f"Missing or empty required release file: {path}")
    with (root / "SmartCatalog.exe").open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ReleaseError("SmartCatalog.exe does not have a Windows executable header")
    internal = root / "_internal"
    for pattern in ("_tkinter.pyd", "pymupdf/*.pyd"):
        if not any(path.is_file() and path.stat().st_size for path in internal.glob(pattern)):
            raise ReleaseError(f"Missing runtime component matching _internal/{pattern}")
    for directory in ("_tcl_data", "_tk_data"):
        if not (internal / directory).is_dir() or not any((internal / directory).iterdir()):
            raise ReleaseError(f"Missing Tcl/Tk runtime directory: {directory}")
    return sorted(files)


def package_release(release_dir: Path, archive: Path) -> tuple[Path, Path]:
    root = release_dir.resolve()
    archive = archive.resolve()
    if archive == root or root in archive.parents:
        raise ReleaseError("Archive must be outside the runnable release folder")
    files = verify_release(release_dir)
    checksum = archive.with_name(archive.name + ".sha256")
    temporary_archive = archive.with_name(archive.name + ".tmp")
    # Never overwrite an earlier delivery or remove it on a failed attempt.
    if any(path.exists() for path in (archive, checksum, temporary_archive)):
        raise ReleaseError(f"Archive/checksum already exists: {archive}")
    archive.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(temporary_archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in files:
                bundle.write(path, Path("SmartCatalog") / path.relative_to(root))
        with zipfile.ZipFile(temporary_archive) as bundle:
            bad_member = bundle.testzip()
            if bad_member is not None:
                raise ReleaseError(f"Archive CRC validation failed: {bad_member}")
        with temporary_archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        temporary_archive.replace(archive)
        checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8", newline="\n")
    finally:
        temporary_archive.unlink(missing_ok=True)
    return archive, checksum


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    try:
        files = verify_release(args.release_dir)
        if args.archive:
            archive, checksum = package_release(args.release_dir, args.archive)
            print(f"Validated {len(files)} release files. Archive: {archive}\nSHA-256: {checksum}")
        else:
            print(f"Validated {len(files)} release files: {args.release_dir.resolve()}")
    except (ReleaseError, OSError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Release validation failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
