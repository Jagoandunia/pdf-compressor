from __future__ import annotations

import gc
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
class PdfInfo:
    path: Path
    size_bytes: int
    page_count: int


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


def inspect_pdf_info(input_path: Path) -> PdfInfo:
    """Membaca ukuran file dan jumlah halaman PDF secara cepat tanpa memuat seluruh halaman ke RAM."""
    source = validate_source(input_path)
    try:
        doc = fitz.open(source)
    except (fitz.FileDataError, fitz.EmptyFileError) as error:
        raise CompressionError("Tidak dapat membaca PDF, file mungkin rusak atau dilindungi kata sandi.") from error
    if doc.needs_pass:
        doc.close()
        raise CompressionError("PDF ini dilindungi kata sandi, kompresi belum didukung.")
    with doc:
        pages = doc.page_count
    return PdfInfo(path=source, size_bytes=source.stat().st_size, page_count=pages)


def estimate_compressed_size(size_bytes: int, page_count: int, level: int) -> int:
    """Menghitung perkiraan ukuran hasil kompresi berdasarkan DPI & kualitas JPEG target."""
    if size_bytes <= 0:
        return 0
    # Rata-rata rasio kompresi raster per level
    ratio_map = {
        1: 0.52,  # 200 DPI, JPEG 85
        2: 0.32,  # 150 DPI, JPEG 75
        3: 0.19,  # 110 DPI, JPEG 65
    }
    ratio = ratio_map.get(level, 0.32)
    estimated = int(size_bytes * ratio)
    min_floor = max(page_count * 18 * 1024, int(size_bytes * 0.08))
    return min(size_bytes, max(estimated, min_floor))


def make_output_path(input_path: Path, level: int) -> Path:
    source = Path(input_path)
    base_name = f"{source.stem}_kompres_L{level}"
    output = source.with_name(f"{base_name}{source.suffix}")
    number = 2
    while output.exists():
        output = source.with_name(f"{base_name} ({number}){source.suffix}")
        number += 1
    return output


def _release_fitz_memory() -> None:
    try:
        fitz.TOOLS.store_shrink(100)
    except Exception:
        pass
    gc.collect()


def compress_pdf(
    input_path: Path,
    level: int,
    progress_callback: Callable[[int, int], None] | None = None,
) -> CompressionResult:
    source = validate_source(input_path)
    profile = get_profile(level)
    output = make_output_path(source, level)

    try:
        fitz.TOOLS.set_store_max(16 * 1024 * 1024)
    except Exception:
        pass

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
                    rect = source_page.rect
                    image = source_page.get_pixmap(dpi=profile.resolution_dpi, alpha=False)
                    jpeg = image.tobytes("jpeg", jpg_quality=profile.jpeg_quality)
                    del image

                    result_page = result_document.new_page(
                        width=rect.width,
                        height=rect.height,
                    )
                    result_page.insert_image(result_page.rect, stream=jpeg)
                    del jpeg

                    if index % 5 == 0:
                        _release_fitz_memory()

                    if progress_callback is not None:
                        progress_callback(index, total_pages)

                result_document.save(output, garbage=3, deflate=True)

        _release_fitz_memory()

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
    finally:
        _release_fitz_memory()
