from __future__ import annotations

import sys
from pathlib import Path


class RuntimeNotFoundError(RuntimeError):
    """发布目录缺少必需运行时。"""


def resource_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parents[1]


def ghostscript_executable() -> Path:
    executable = resource_root() / "runtime" / "ghostscript" / "bin" / "gswin64c.exe"
    if not executable.is_file():
        raise RuntimeNotFoundError("程序安装不完整，请重新解压完整发布目录。")
    return executable
