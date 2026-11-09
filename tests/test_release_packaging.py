from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from tools.release import ReleaseError, package_release, verify_release


class ReleasePackagingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="smartcatalog-release-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.release = self.root / "SmartCatalog"
        self.files = [
            "SmartCatalog.exe", "README.md", "icons/icon.ico", "icons/bg.jpg",
            "_internal/base_library.zip", "_internal/python313.dll", "_internal/_tkinter.pyd",
            "_internal/fitz/__init__.py", "_internal/pymupdf/__init__.py",
            "_internal/pymupdf/_mupdf.pyd", "_internal/_tcl_data/init.tcl",
            "_internal/_tk_data/tk.tcl",
        ]
        for name in self.files:
            path = self.release / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"MZ-fixture" if name.endswith(".exe") else b"fixture")

    def test_archive_preserves_complete_folder_and_checksum_matches(self):
        archive, checksum = package_release(self.release, self.root / "SmartCatalog-Windows.zip")
        with zipfile.ZipFile(archive) as bundle:
            self.assertEqual(set(bundle.namelist()), {f"SmartCatalog/{name}" for name in self.files})
            self.assertIsNone(bundle.testzip())
            self.assertEqual(bundle.read("SmartCatalog/SmartCatalog.exe"), b"MZ-fixture")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertEqual(checksum.read_text(encoding="utf-8"), f"{digest}  {archive.name}\n")

    def test_every_required_runtime_component_is_checked(self):
        for name in self.files:
            path = self.release / name
            original = path.read_bytes()
            with self.subTest(name=name):
                path.unlink()
                with self.assertRaises(ReleaseError):
                    verify_release(self.release)
                path.write_bytes(original)

    def test_runtime_and_agent_content_is_rejected_without_deleting_it(self):
        for name in (
            "config/database/sql/catalog.db", "_internal/config/settings.json",
            "_internal/extra.sqlite3", "_internal/catalog.pdf", "_internal/agent.log",
            "_internal/settings.json", "_internal/pymupdf/mupdf-devel/header.h",
        ):
            path = self.release / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"keep")
            with self.subTest(name=name), self.assertRaises(ReleaseError):
                verify_release(self.release)
            self.assertEqual(path.read_bytes(), b"keep")
            path.unlink()
            # Remove only the fixture's newly empty ancestor directories.
            parent = path.parent
            while parent != self.release and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent

    def test_invalid_executable_and_empty_assets_are_rejected(self):
        (self.release / "SmartCatalog.exe").write_bytes(b"not an executable")
        with self.assertRaisesRegex(ReleaseError, "executable header"):
            verify_release(self.release)
        (self.release / "SmartCatalog.exe").write_bytes(b"MZ-fixture")
        (self.release / "icons/bg.jpg").write_bytes(b"")
        with self.assertRaisesRegex(ReleaseError, "empty required"):
            verify_release(self.release)

    def test_existing_delivery_and_archive_inside_release_are_preserved(self):
        archive = self.root / "delivery.zip"
        archive.write_bytes(b"keep previous delivery")
        with self.assertRaises(ReleaseError):
            package_release(self.release, archive)
        self.assertEqual(archive.read_bytes(), b"keep previous delivery")
        with self.assertRaisesRegex(ReleaseError, "outside"):
            package_release(self.release, self.release / "delivery.zip")

    @unittest.skipUnless(sys.platform == "win32", "Windows build script")
    def test_build_refuses_nonempty_custom_output_without_changing_it(self):
        output = self.root / "existing-output"
        output.mkdir()
        sentinel = output / "keep.txt"
        sentinel.write_text("previous output", encoding="utf-8")
        script = Path(__file__).resolve().parents[1] / "build_exe.ps1"
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-File", str(script), "-OutputRoot", str(output)],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be a new or empty directory", result.stdout + result.stderr)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "previous output")


if __name__ == "__main__":
    unittest.main()
