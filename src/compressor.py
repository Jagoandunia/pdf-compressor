from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
    1: CompressionProfile(1, "清晰优先", 200, 85),
    2: CompressionProfile(2, "均衡推荐", 150, 75),
    3: CompressionProfile(3, "体积优先", 110, 65),
}


class CompressionError(Exception):
    """用户可直接理解的压缩失败原因。"""


def get_profile(level: int) -> CompressionProfile:
    try:
        return PROFILES[level]
    except KeyError as error:
        raise ValueError("压缩等级只能是 1、2 或 3。") from error


def validate_source(input_path: Path) -> Path:
    source = Path(input_path)
    if source.suffix.lower() != ".pdf":
        raise CompressionError("请选择 PDF 文件。")
    if not source.is_file():
        raise CompressionError("找不到所选 PDF 文件。")
    return source


def make_output_path(input_path: Path, level: int) -> Path:
    source = Path(input_path)
    base_name = f"{source.stem}_压缩_L{level}"
    output = source.with_name(f"{base_name}{source.suffix}")
    number = 2
    while output.exists():
        output = source.with_name(f"{base_name} ({number}){source.suffix}")
        number += 1
    return output


def compress_pdf(input_path: Path, level: int) -> CompressionResult:
    source = validate_source(input_path)
    profile = get_profile(level)
    output = make_output_path(source, level)

    try:
        source_document = fitz.open(source)
    except (fitz.FileDataError, fitz.EmptyFileError) as error:
        raise CompressionError("无法读取 PDF，该文件可能损坏或受密码保护。") from error
    if source_document.needs_pass:
        source_document.close()
        raise CompressionError("该 PDF 受密码保护，暂不支持压缩。")

    try:
        with source_document:
            with fitz.open() as result_document:
                for source_page in source_document:
                    image = source_page.get_pixmap(dpi=profile.resolution_dpi, alpha=False)
                    jpeg = image.tobytes("jpeg", jpg_quality=profile.jpeg_quality)
                    result_page = result_document.new_page(
                        width=source_page.rect.width,
                        height=source_page.rect.height,
                    )
                    result_page.insert_image(result_page.rect, stream=jpeg)
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
    except Exception as error:
        output.unlink(missing_ok=True)
        raise CompressionError("无法生成新的 PDF 文件，请检查磁盘空间和文件权限。") from error
