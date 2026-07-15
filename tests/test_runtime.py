from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import runtime


class GhostscriptRuntimeTests(unittest.TestCase):
    def test_missing_bundled_engine_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(runtime, "resource_root", return_value=Path(directory)):
                with self.assertRaisesRegex(
                    runtime.RuntimeNotFoundError,
                    "程序安装不完整",
                ):
                    runtime.ghostscript_executable()

    def test_resource_root_uses_pyinstaller_resource_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundled_root = Path(directory)
            with patch.object(sys, "_MEIPASS", str(bundled_root), create=True):
                self.assertEqual(runtime.resource_root(), bundled_root)


if __name__ == "__main__":
    unittest.main()
