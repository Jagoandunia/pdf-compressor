from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import fitz


@dataclass(frozen=True)
class CompressionProfile:
    level: int
    label: str
    resolution_dpi: int
    jpeg_quality: int


@dataclass(frozen=True)
class CompressionResult:
    input_path: Path
    output_path: Path
    input_bytes: int
    output_bytes: int
    level: int
    page_count: int


PROFILES = {
    1: CompressionProfile(1, "Kualitas", 200, 85),
    2: CompressionProfile(2, "Seimbang", 150, 75),
    3: CompressionProfile(3, "Kecil", 110, 65),
}


class CompressionError(Exception):
    """Penyebab kegagalan kompresi yang dapat langsung dipahami pengguna."""


def get_profile(level: int) -> CompressionProfile:
    try:
        return PROFILES[level]
    except KeyError as error:
        raise ValueError("Tingkat kompresi hanya boleh 1, 2, atau 3.") from error


def validate_source(input_path: Path) -> Path:
    source = Path(input_path)
    if source.suffix.lower() != ".pdf":
        raise CompressionError("Silakan pilih file PDF.")
    if not source.is_file():
        raise CompressionError("File PDF yang dipilih tidak ditemukan.")
    return source


def make_output_path(input_path: Path, level: int) -> Path:
    source = Path(input_path)
    base_name = f"{source.stem}_kompres_L{level}"
    output = source.with_name(f"{base_name}{source.suffix}")
    number = 2
    while output.exists():
        output = source.with_name(f"{base_name} ({number}){source.suffix}")
        number += 1
    return output


def compress_pdf(
    input_path: Path,
    level: int,
    progress_callback: Callable[[int, int], None] | None = None,
) -> CompressionResult:
    source = validate_source(input_path)
    profile = get_profile(level)
    output = make_output_path(source, level)

    try:
        source_document = fitz.open(source)
    except (fitz.FileDataError, fitz.EmptyFileError) as error:
        raise CompressionError("Tidak dapat membaca PDF, file mungkin rusak atau dilindungi kata sandi.") from error
    if source_document.needs_pass:
        source_document.close()
        raise CompressionError("PDF ini dilindungi kata sandi, kompresi belum didukung.")

    try:
        with source_document:
            total_pages = max(source_document.page_count, 1)
            if progress_callback is not None:
                progress_callback(0, total_pages)
            with fitz.open() as result_document:
                for index, source_page in enumerate(source_document, start=1):
                    image = source_page.get_pixmap(dpi=profile.resolution_dpi, alpha=False)
                    jpeg = image.tobytes("jpeg", jpg_quality=profile.jpeg_quality)
                    result_page = result_document.new_page(
                        width=source_page.rect.width,
                        height=source_page.rect.height,
                    )
                    result_page.insert_image(result_page.rect, stream=jpeg)
                    if progress_callback is not None:
                        progress_callback(index, total_pages)
                result_document.save(output, garbage=4, deflate=True)

        with fitz.open(output) as validated_document:
            page_count = validated_document.page_count
        return CompressionResult(
            input_path=source,
            output_path=output,
            input_bytes=source.stat().st_size,
            output_bytes=output.stat().st_size,
            level=level,
            page_count=page_count,
        )
    except CompressionError:
        output.unlink(missing_ok=True)
        raise
    except Exception as error:
        output.unlink(missing_ok=True)
        raise CompressionError("Gagal membuat file PDF baru, periksa ruang penyimpanan dan izin akses file.") from error
