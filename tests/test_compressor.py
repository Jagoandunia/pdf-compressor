from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import runtime

from compressor import (
    CompressionError,
    build_compress_command,
    compress_pdf,
    get_profile,
    make_output_path,
    validate_source,
)


class CompressionProfileTests(unittest.TestCase):
    def test_profiles_have_requested_quality_values(self) -> None:
        self.assertEqual(get_profile(1).resolution_dpi, 200)
        self.assertEqual(get_profile(1).jpeg_quality, 85)
        self.assertEqual(get_profile(2).resolution_dpi, 150)
        self.assertEqual(get_profile(2).jpeg_quality, 75)
        self.assertEqual(get_profile(3).resolution_dpi, 110)
        self.assertEqual(get_profile(3).jpeg_quality, 65)

    def test_invalid_level_has_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "压缩等级只能是 1、2 或 3"):
            get_profile(4)

    def test_output_path_never_overwrites_an_existing_compressed_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "资料.pdf"
            source.write_bytes(b"%PDF-1.4")
            existing_output = make_output_path(source, 2)
            existing_output.write_bytes(b"old output")

            self.assertEqual(
                make_output_path(source, 2).name,
                "资料_压缩_L2 (2).pdf",
            )

    def test_command_uses_pdfwrite_and_selected_profile(self) -> None:
        command = build_compress_command(
            Path("gswin64c.exe"),
            Path("input.pdf"),
            Path("output.pdf"),
            get_profile(3),
        )

        self.assertIn("-sDEVICE=pdfwrite", command)
        self.assertIn("-dColorImageResolution=110", command)
        self.assertIn("-dGrayImageResolution=110", command)
        self.assertIn("-dJPEGQ=65", command)
        self.assertIn("-sOutputFile=output.pdf", command)


class SourceValidationTests(unittest.TestCase):
    def test_non_pdf_file_is_rejected_with_a_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "资料.txt"
            source.write_text("not a PDF", encoding="utf-8")

            with self.assertRaisesRegex(CompressionError, "请选择 PDF 文件"):
                validate_source(source)

    def test_missing_pdf_is_rejected_with_a_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "不存在.pdf"

            with self.assertRaisesRegex(CompressionError, "找不到所选 PDF 文件"):
                validate_source(source)


class CompressionExecutionTests(unittest.TestCase):
    def test_missing_engine_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "资料.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            missing_engine = Path(directory) / "missing-gs.exe"

            with self.assertRaisesRegex(CompressionError, "压缩引擎不可用"):
                compress_pdf(source, 2, missing_engine)

    def test_engine_failure_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "资料.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            engine = Path(directory) / "gswin64c.cmd"
            engine.write_text("@echo off\r\nexit /b 1\r\n", encoding="utf-8")

            with self.assertRaisesRegex(CompressionError, "压缩引擎执行失败"):
                compress_pdf(source, 2, engine)

    def test_engine_failure_removes_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "资料.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            engine = Path(directory) / "gswin64c.exe"
            engine.write_bytes(b"engine")
            output = Path(directory) / "资料_压缩_L2.pdf"

            def failed_run(command: list[str], **_: object) -> CompletedProcess[str]:
                output.write_bytes(b"partial output")
                return CompletedProcess(command, 1, "", "broken PDF")

            with patch("compressor.subprocess.run", side_effect=failed_run):
                with self.assertRaisesRegex(CompressionError, "压缩引擎执行失败"):
                    compress_pdf(source, 2, engine)

            self.assertFalse(output.exists())

    def test_successful_engine_run_returns_new_file_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "资料.pdf"
            source.write_bytes(b"%PDF-1.4\nsource")
            engine = Path(directory) / "gswin64c.exe"
            engine.write_bytes(b"engine")

            def successful_run(command: list[str], **_: object) -> CompletedProcess[str]:
                output_argument = next(arg for arg in command if arg.startswith("-sOutputFile="))
                Path(output_argument.removeprefix("-sOutputFile=")).write_bytes(b"%PDF-1.4\ncompressed")
                return CompletedProcess(command, 0, "", "")

            with patch("compressor.subprocess.run", side_effect=successful_run):
                result = compress_pdf(source, 2, engine)

            self.assertEqual(result.input_path, source)
            self.assertEqual(result.output_path.name, "资料_压缩_L2.pdf")
            self.assertEqual(result.input_bytes, source.stat().st_size)
            self.assertEqual(result.output_bytes, result.output_path.stat().st_size)

    def test_success_without_output_file_is_not_reported_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "资料.pdf"
            source.write_bytes(b"%PDF-1.4\nsource")
            engine = Path(directory) / "gswin64c.exe"
            engine.write_bytes(b"engine")

            with patch(
                "compressor.subprocess.run",
                return_value=CompletedProcess([], 0, "", ""),
            ):
                with self.assertRaisesRegex(CompressionError, "压缩后文件未生成或为空"):
                    compress_pdf(source, 2, engine)

    def test_default_engine_comes_from_bundled_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "资料.pdf"
            source.write_bytes(b"%PDF-1.4\nsource")
            engine = Path(directory) / "gswin64c.exe"
            engine.write_bytes(b"engine")

            def successful_run(command: list[str], **_: object) -> CompletedProcess[str]:
                output_argument = next(arg for arg in command if arg.startswith("-sOutputFile="))
                Path(output_argument.removeprefix("-sOutputFile=")).write_bytes(b"%PDF-1.4\ncompressed")
                return CompletedProcess(command, 0, "", "")

            with patch("runtime.ghostscript_executable", return_value=engine):
                with patch("compressor.subprocess.run", side_effect=successful_run):
                    result = compress_pdf(source, 2)

            self.assertEqual(result.output_path.name, "资料_压缩_L2.pdf")

    def test_missing_bundled_runtime_is_reported_as_compression_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "资料.pdf"
            source.write_bytes(b"%PDF-1.4\nsource")

            with patch(
                "runtime.ghostscript_executable",
                side_effect=runtime.RuntimeNotFoundError("程序安装不完整，请重新解压完整发布目录。"),
            ):
                with self.assertRaisesRegex(CompressionError, "程序安装不完整"):
                    compress_pdf(source, 2)


if __name__ == "__main__":
    unittest.main()
