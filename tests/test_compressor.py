from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app import LEVEL_OPTIONS, format_bytes, format_ratio
from compressor import CompressionError, compress_pdf, get_profile


class PdfCompressionTests(unittest.TestCase):
    def _create_sample_pdf(self, path: Path, page_count: int = 2) -> None:
        original = fitz.open()
        for page_number in range(page_count):
            page = original.new_page(width=595, height=842)
            page.insert_text((72, 72), f"PDF compression sample {page_number + 1}", fontsize=28)
            page.draw_rect(fitz.Rect(72, 120, 520, 640), color=(0.1, 0.3, 0.7), fill=(0.7, 0.85, 1.0))
        original.save(path)
        original.close()

    def test_profiles_keep_the_requested_three_compression_levels(self) -> None:
        self.assertEqual((get_profile(1).resolution_dpi, get_profile(1).jpeg_quality), (200, 85))
        self.assertEqual((get_profile(2).resolution_dpi, get_profile(2).jpeg_quality), (150, 75))
        self.assertEqual((get_profile(3).resolution_dpi, get_profile(3).jpeg_quality), (110, 65))

    def test_compresses_two_page_pdf_into_a_readable_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "资料.pdf"
            self._create_sample_pdf(source)

            result = compress_pdf(source, 1)

            self.assertTrue(result.output_path.is_file())
            self.assertGreater(result.output_bytes, 0)
            self.assertEqual(result.page_count, 2)
            with fitz.open(result.output_path) as compressed:
                self.assertEqual(compressed.page_count, 2)

    def test_second_compression_never_overwrites_first_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "资料.pdf"
            self._create_sample_pdf(source, page_count=1)

            first = compress_pdf(source, 2)
            second = compress_pdf(source, 2)

            self.assertEqual(first.output_path.name, "资料_压缩_L2.pdf")
            self.assertEqual(second.output_path.name, "资料_压缩_L2 (2).pdf")
            self.assertTrue(first.output_path.is_file())
            self.assertTrue(second.output_path.is_file())

    def test_non_pdf_file_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "资料.txt"
            source.write_text("not a PDF", encoding="utf-8")

            with self.assertRaisesRegex(CompressionError, "请选择 PDF 文件"):
                compress_pdf(source, 2)

    def test_missing_pdf_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "不存在.pdf"

            with self.assertRaisesRegex(CompressionError, "找不到所选 PDF 文件"):
                compress_pdf(source, 2)

    def test_damaged_pdf_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "损坏.pdf"
            source.write_bytes(b"not a PDF")

            with self.assertRaisesRegex(CompressionError, "无法读取 PDF"):
                compress_pdf(source, 2)

    def test_write_failure_has_clear_error_and_no_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "资料.pdf"
            self._create_sample_pdf(source, page_count=1)
            output = Path(directory) / "missing-directory" / "资料_压缩_L2.pdf"

            with patch("compressor.make_output_path", return_value=output):
                with self.assertRaisesRegex(CompressionError, "无法生成新的 PDF 文件"):
                    compress_pdf(source, 2)

            self.assertFalse(output.exists())

    def test_password_protected_pdf_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "加密.pdf"
            original = fitz.open()
            original.new_page().insert_text((72, 72), "secret")
            original.save(
                source,
                encryption=fitz.PDF_ENCRYPT_AES_256,
                owner_pw="owner-password",
                user_pw="user-password",
            )
            original.close()

            with self.assertRaisesRegex(CompressionError, "受密码保护"):
                compress_pdf(source, 2)


class PresentationTests(unittest.TestCase):
    def test_file_sizes_and_ratio_are_readable(self) -> None:
        self.assertEqual(format_bytes(1024), "1.00 KB")
        self.assertEqual(format_ratio(1_000, 750), "缩小 25.0%")
        self.assertEqual(format_ratio(1_000, 1_200), "增大 20.0%")

    def test_level_options_explain_all_three_levels(self) -> None:
        self.assertEqual(
            LEVEL_OPTIONS,
            (
                (1, "1 级 · 清晰优先", "200 DPI · JPEG 质量 85"),
                (2, "2 级 · 均衡推荐", "150 DPI · JPEG 质量 75"),
                (3, "3 级 · 体积优先", "110 DPI · JPEG 质量 65"),
            ),
        )


if __name__ == "__main__":
    unittest.main()
