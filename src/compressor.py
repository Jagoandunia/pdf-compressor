from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


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
    suffix = 2
    while output.exists():
        output = source.with_name(f"{base_name} ({suffix}){source.suffix}")
        suffix += 1
    return output


def build_compress_command(
    gs_executable: Path,
    input_path: Path,
    output_path: Path,
    profile: CompressionProfile,
) -> list[str]:
    resolution = profile.resolution_dpi
    return [
        str(gs_executable),
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dAutoRotatePages=/None",
        "-dDownsampleColorImages=true",
        "-dColorImageDownsampleType=/Bicubic",
        f"-dColorImageResolution={resolution}",
        "-dDownsampleGrayImages=true",
        "-dGrayImageDownsampleType=/Bicubic",
        f"-dGrayImageResolution={resolution}",
        "-dEncodeColorImages=true",
        "-dAutoFilterColorImages=false",
        "-dColorImageFilter=/DCTEncode",
        "-dEncodeGrayImages=true",
        "-dAutoFilterGrayImages=false",
        "-dGrayImageFilter=/DCTEncode",
        "-dEncodeMonoImages=true",
        "-dAutoFilterMonoImages=false",
        "-dMonoImageFilter=/CCITTFaxEncode",
        f"-dJPEGQ={profile.jpeg_quality}",
        f"-sOutputFile={output_path}",
        str(input_path),
    ]


def compress_pdf(
    input_path: Path,
    level: int,
    gs_executable: Path | None = None,
) -> CompressionResult:
    source = validate_source(input_path)
    profile = get_profile(level)
    if gs_executable is None:
        from runtime import RuntimeNotFoundError, ghostscript_executable

        try:
            engine = ghostscript_executable()
        except RuntimeNotFoundError as error:
            raise CompressionError(str(error)) from error
    else:
        engine = Path(gs_executable)
    if not engine.is_file():
        raise CompressionError("压缩引擎不可用，请重新解压完整发布目录。")
    output = make_output_path(source, level)
    try:
        try:
            completed = subprocess.run(
                build_compress_command(engine, source, output, profile),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as error:
            raise CompressionError("压缩引擎无法启动，请重新解压完整发布目录。") from error
        if completed.returncode != 0:
            raise CompressionError("压缩引擎执行失败，请检查 PDF 是否损坏或受密码保护。")
        if not output.is_file() or output.stat().st_size == 0:
            raise CompressionError("压缩后文件未生成或为空。")
        return CompressionResult(
            input_path=source,
            output_path=output,
            input_bytes=source.stat().st_size,
            output_bytes=output.stat().st_size,
            level=level,
        )
    except Exception:
        output.unlink(missing_ok=True)
        raise
