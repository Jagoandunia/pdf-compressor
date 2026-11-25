import ast

compressor_pyqt_code = r'''from __future__ import annotations

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
'''

app_pyqt_code = r'''from __future__ import annotations

import ctypes
import gc
import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from compressor import (
    CompressionError,
    CompressionResult,
    PdfInfo,
    compress_pdf,
    estimate_compressed_size,
    inspect_pdf_info,
)

LEVEL_CARDS = (
    (1, "Kualitas", "200 DPI", "Kualitas terbaik", "leaf"),
    (2, "Seimbang", "150 DPI", "Rekomendasi", "scale"),
    (3, "Kecil", "110 DPI", "Ukuran minimum", "bars"),
)


def trim_working_set() -> None:
    gc.collect()
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetCurrentProcess()
            kernel32.SetProcessWorkingSetSize(handle, ctypes.c_size_t(-1), ctypes.c_size_t(-1))
        except Exception:
            pass


def format_size_parts(size_bytes: int) -> tuple[str, str]:
    """Mengembalikan angka dengan koma desimal (gaya Indonesia) dan satuan."""
    if size_bytes < 1024:
        return f"{size_bytes}", "B"
    if size_bytes < 1024 * 1024:
        val = f"{size_bytes / 1024:.1f}".replace(".", ",")
        return val, "KB"
    val = f"{size_bytes / (1024 * 1024):.1f}".replace(".", ",")
    return val, "MB"


def format_size_inline(size_bytes: int) -> str:
    num, unit = format_size_parts(size_bytes)
    return f"{num} {unit}"


def make_vector_icon(kind: str, size: int = 24, color: str = "#2563EB") -> QIcon:
    """Membuat ikon vektor tajam menggunakan QPainter tanpa ketergantungan file eksternal."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    c = QColor(color)
    pen = QPen(c, max(1.6, size * 0.075))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    s = float(size)
    if kind == "app_pdf":
        # Dokumen biru dengan lipatan sudut & tulisan PDF
        path = QPainterPath()
        m = s * 0.14
        fold = s * 0.24
        path.moveTo(m, m)
        path.lineTo(s - m - fold, m)
        path.lineTo(s - m, m + fold)
        path.lineTo(s - m, s - m)
        path.lineTo(m, s - m)
        path.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2563EB"))
        p.drawPath(path)

        p.setBrush(QColor("#93C5FD"))
        fold_path = QPainterPath()
        fold_path.moveTo(s - m - fold, m)
        fold_path.lineTo(s - m - fold, m + fold)
        fold_path.lineTo(s - m, m + fold)
        fold_path.closeSubpath()
        p.drawPath(fold_path)

        p.setPen(QColor("#FFFFFF"))
        f = QFont("Segoe UI", max(6, int(s * 0.21)), QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(QRectF(0, s * 0.34, s, s * 0.5), Qt.AlignmentFlag.AlignCenter, "PDF")

    elif kind == "red_pdf":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#EF4444"))
        p.drawRoundedRect(QRectF(2, 2, s - 4, s - 4), 8, 8)
        p.setPen(QColor("#FFFFFF"))
        f = QFont("Segoe UI", max(7, int(s * 0.24)), QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, "PDF")

    elif kind == "doc_plus":
        # Dokumen garis biru dengan lencana + bulat di kanan bawah
        doc_rect = QRectF(s * 0.22, s * 0.12, s * 0.48, s * 0.64)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(doc_rect, 4, 4)
        p.drawLine(QPointF(s * 0.33, s * 0.33), QPointF(s * 0.56, s * 0.33))
        p.drawLine(QPointF(s * 0.33, s * 0.47), QPointF(s * 0.50, s * 0.47))

        cx, cy, r = s * 0.68, s * 0.68, s * 0.19
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2563EB"))
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.setPen(QPen(QColor("#FFFFFF"), max(1.8, s * 0.06), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(cx - r * 0.48, cy), QPointF(cx + r * 0.48, cy))
        p.drawLine(QPointF(cx, cy - r * 0.48), QPointF(cx, cy + r * 0.48))

    elif kind == "folder_white" or kind == "folder_gray":
        stroke = "#FFFFFF" if kind == "folder_white" else "#475569"
        p.setPen(QPen(QColor(stroke), max(1.6, s * 0.08), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        path = QPainterPath()
        path.moveTo(s * 0.15, s * 0.28)
        path.lineTo(s * 0.42, s * 0.28)
        path.lineTo(s * 0.50, s * 0.36)
        path.lineTo(s * 0.85, s * 0.36)
        path.lineTo(s * 0.85, s * 0.76)
        path.lineTo(s * 0.15, s * 0.76)
        path.closeSubpath()
        if kind == "folder_white":
            p.setBrush(QColor("#FFFFFF"))
        p.drawPath(path)

    elif kind == "leaf":
        path = QPainterPath()
        path.moveTo(s * 0.22, s * 0.78)
        path.quadTo(s * 0.22, s * 0.24, s * 0.78, s * 0.22)
        path.quadTo(s * 0.76, s * 0.76, s * 0.22, s * 0.78)
        p.drawPath(path)
        p.drawLine(QPointF(s * 0.22, s * 0.78), QPointF(s * 0.62, s * 0.38))

    elif kind == "scale":
        p.drawLine(QPointF(s * 0.50, s * 0.20), QPointF(s * 0.50, s * 0.80))
        p.drawLine(QPointF(s * 0.32, s * 0.80), QPointF(s * 0.68, s * 0.80))
        p.drawLine(QPointF(s * 0.20, s * 0.32), QPointF(s * 0.80, s * 0.32))
        # Left pan
        p.drawLine(QPointF(s * 0.20, s * 0.32), QPointF(s * 0.12, s * 0.54))
        p.drawLine(QPointF(s * 0.20, s * 0.32), QPointF(s * 0.28, s * 0.54))
        p.drawArc(QRectF(s * 0.10, s * 0.46, s * 0.20, s * 0.16), 180 * 16, 180 * 16)
        # Right pan
        p.drawLine(QPointF(s * 0.80, s * 0.32), QPointF(s * 0.72, s * 0.54))
        p.drawLine(QPointF(s * 0.80, s * 0.32), QPointF(s * 0.88, s * 0.54))
        p.drawArc(QRectF(s * 0.70, s * 0.46, s * 0.20, s * 0.16), 180 * 16, 180 * 16)

    elif kind == "bars":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(QRectF(s * 0.20, s * 0.54, s * 0.14, s * 0.26), 2, 2)
        p.drawRoundedRect(QRectF(s * 0.43, s * 0.38, s * 0.14, s * 0.42), 2, 2)
        p.drawRoundedRect(QRectF(s * 0.66, s * 0.22, s * 0.14, s * 0.58), 2, 2)

    elif kind == "shield_check":
        shield = QPainterPath()
        shield.moveTo(s * 0.50, s * 0.14)
        shield.lineTo(s * 0.80, s * 0.26)
        shield.lineTo(s * 0.80, s * 0.52)
        shield.quadTo(s * 0.80, s * 0.76, s * 0.50, s * 0.88)
        shield.quadTo(s * 0.20, s * 0.76, s * 0.20, s * 0.52)
        shield.lineTo(s * 0.20, s * 0.26)
        shield.closeSubpath()
        p.drawPath(shield)
        p.drawLine(QPointF(s * 0.38, s * 0.51), QPointF(s * 0.47, s * 0.60))
        p.drawLine(QPointF(s * 0.47, s * 0.60), QPointF(s * 0.64, s * 0.42))

    elif kind == "compress_action":
        p.setPen(QPen(QColor("#FFFFFF"), max(1.8, s * 0.08), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawRoundedRect(QRectF(s * 0.22, s * 0.22, s * 0.46, s * 0.56), 3, 3)
        p.drawLine(QPointF(s * 0.78, s * 0.54), QPointF(s * 0.78, s * 0.80))
        p.drawLine(QPointF(s * 0.69, s * 0.71), QPointF(s * 0.78, s * 0.80))
        p.drawLine(QPointF(s * 0.87, s * 0.71), QPointF(s * 0.78, s * 0.80))

    elif kind == "green_down":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#16A34A"))
        p.drawRoundedRect(QRectF(s * 0.38, s * 0.14, s * 0.24, s * 0.10), 2, 2)
        p.drawRoundedRect(QRectF(s * 0.38, s * 0.28, s * 0.24, s * 0.32), 2, 2)
        tri = QPainterPath()
        tri.moveTo(s * 0.22, s * 0.58)
        tri.lineTo(s * 0.78, s * 0.58)
        tri.lineTo(s * 0.50, s * 0.88)
        tri.closeSubpath()
        p.drawPath(tri)

    elif kind == "gear":
        cx, cy = s * 0.50, s * 0.50
        p.drawEllipse(QPointF(cx, cy), s * 0.14, s * 0.14)
        p.drawEllipse(QPointF(cx, cy), s * 0.28, s * 0.28)

    p.end()
    return QIcon(pm)


class CompressionWorker(QThread):
    progress_changed = pyqtSignal(int)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, source: Path, level: int) -> None:
        super().__init__()
        self.source = source
        self.level = level

    def run(self) -> None:
        try:
            result = compress_pdf(
                self.source,
                self.level,
                progress_callback=self._on_page_progress,
            )
        except (CompressionError, ValueError) as err:
            self.failed.emit(str(err))
        except Exception:
            self.failed.emit("Terjadi kesalahan saat mengompresi PDF. Periksa file lalu coba lagi.")
        else:
            self.progress_changed.emit(100)
            self.succeeded.emit(result)
        finally:
            trim_working_set()

    def _on_page_progress(self, current: int, total: int) -> None:
        if total <= 0:
            return
        pct = min(95, int((current / total) * 95))
        self.progress_changed.emit(pct)


class DropZoneFrame(QFrame):
    file_dropped = pyqtSignal(Path)
    clicked = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("dropInner")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile():
                self.setProperty("dragActive", True)
                self.style().unpolish(self)
                self.style().polish(self)
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, _event) -> None:
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event) -> None:
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self.file_dropped.emit(Path(urls[0].toLocalFile()))
            event.acceptProposedAction()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class LevelChoiceCard(QFrame):
    selected_signal = pyqtSignal(int)

    def __init__(self, level: int, title: str, dpi: str, desc: str, icon_kind: str) -> None:
        super().__init__()
        self.level = level
        self.icon_kind = icon_kind
        self.is_selected = False
        self.setObjectName("choiceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(96)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(26, 26)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.icon_lbl, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("choiceTitle")
        self.dpi_lbl = QLabel(dpi)
        self.dpi_lbl.setObjectName("choiceSub")
        self.desc_lbl = QLabel(desc)
        self.desc_lbl.setObjectName("choiceSub")

        text_col.addWidget(self.title_lbl)
        text_col.addWidget(self.dpi_lbl)
        text_col.addWidget(self.desc_lbl)
        layout.addLayout(text_col, 1)

        self.radio_dot = QLabel()
        self.radio_dot.setFixedSize(20, 20)
        layout.addWidget(self.radio_dot, 0, Qt.AlignmentFlag.AlignTop)

        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        self.is_selected = selected
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

        icon_color = "#2563EB" if selected else "#475569"
        self.icon_lbl.setPixmap(make_vector_icon(self.icon_kind, 24, icon_color).pixmap(24, 24))
        self.radio_dot.setPixmap(self._draw_radio_pixmap(selected))

    @staticmethod
    def _draw_radio_pixmap(selected: bool) -> QPixmap:
        pm = QPixmap(20, 20)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if selected:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#2563EB"))
            p.drawEllipse(1, 1, 18, 18)
            p.setBrush(QColor("#FFFFFF"))
            p.drawEllipse(7, 7, 6, 6)
        else:
            p.setPen(QPen(QColor("#94A3B8"), 1.5))
            p.setBrush(QColor("#FFFFFF"))
            p.drawEllipse(2, 2, 16, 16)
        p.end()
        return pm

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.selected_signal.emit(self.level)
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.selected_info: PdfInfo | None = None
        self.output_path: Path | None = None
        self.selected_level = 2
        self.auto_compress_on_drop = True
        self.worker: CompressionWorker | None = None

        self.setWindowTitle("PDF Compressor")
        self.setWindowIcon(make_vector_icon("app_pdf", 32))
        self.resize(680, 820)
        self.setMinimumSize(480, 620)
        self.setAcceptDrops(True)

        self._apply_stylesheet()
        self._build_ui()
        self._select_level(2)
        trim_working_set()

    def _apply_stylesheet(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QScrollArea, QWidget#scrollContent {
                background-color: #F4F7FB;
                font-family: "Segoe UI Variable Text", "Segoe UI", "Inter", Arial;
            }
            QFrame#whiteCard {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 14px;
            }
            QFrame#dropInner {
                background-color: #F8FAFC;
                border: 1.5px dashed #CBD5E1;
                border-radius: 10px;
            }
            QFrame#dropInner:hover, QFrame#dropInner[dragActive="true"] {
                background-color: #EFF6FF;
                border: 1.5px dashed #2563EB;
            }
            QPushButton#pickBtn {
                background-color: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton#pickBtn:hover {
                background-color: #1D4ED8;
            }
            QPushButton#gearBtn {
                background-color: #E2E8F0;
                border: none;
                border-radius: 18px;
            }
            QPushButton#gearBtn:hover {
                background-color: #CBD5E1;
            }
            QPushButton#clearFileBtn {
                background-color: #F1F5F9;
                color: #475569;
                border: none;
                border-radius: 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton#clearFileBtn:hover {
                background-color: #E2E8F0;
                color: #0F172A;
            }
            QFrame#choiceCard {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
            QFrame#choiceCard:hover {
                border: 1.5px solid #93C5FD;
                background-color: #F8FAFC;
            }
            QFrame#choiceCard[selected="true"] {
                background-color: #F5F9FF;
                border: 2px solid #2563EB;
            }
            QLabel#choiceTitle {
                color: #0F172A;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#choiceSub {
                color: #64748B;
                font-size: 11.5px;
            }
            QFrame#savingsBadge {
                background-color: #DCFCE7;
                border-radius: 10px;
            }
            QFrame#infoCard {
                background-color: #EDF2F7;
                border: 1px solid #E2E8F0;
                border-radius: 12px;
            }
            QFrame#errorCard {
                background-color: #FEF2F2;
                border: 1px solid #FECACA;
                border-radius: 12px;
            }
            QPushButton#primaryActionBtn {
                background-color: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                min-height: 48px;
                padding: 0 24px;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton#primaryActionBtn:hover {
                background-color: #1D4ED8;
            }
            QPushButton#primaryActionBtn:disabled {
                background-color: #93C5FD;
            }
            QPushButton#secondaryActionBtn {
                background-color: #FFFFFF;
                color: #334155;
                border: 1px solid #CBD5E1;
                border-radius: 10px;
                min-height: 48px;
                padding: 0 20px;
                font-size: 13.5px;
                font-weight: 600;
            }
            QPushButton#secondaryActionBtn:hover {
                background-color: #F8FAFC;
                border-color: #94A3B8;
            }
            QPushButton#secondaryActionBtn:disabled {
                color: #94A3B8;
                border-color: #E2E8F0;
            }
            QProgressBar {
                background-color: #E2E8F0;
                border: none;
                border-radius: 4px;
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: #2563EB;
                border-radius: 4px;
            }
            """
        )

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.setCentralWidget(scroll)

        content = QWidget()
        content.setObjectName("scrollContent")
        scroll.setWidget(content)

        root_layout = QVBoxLayout(content)
        root_layout.setContentsMargins(28, 24, 28, 20)
        root_layout.setSpacing(18)

        # =================================================================
        # HEADER
        # =================================================================
        header_row = QHBoxLayout()
        header_row.setSpacing(14)

        badge = QLabel()
        badge.setFixedSize(48, 48)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet("background-color: #EFF6FF; border-radius: 12px;")
        badge.setPixmap(make_vector_icon("app_pdf", 32).pixmap(32, 32))
        header_row.addWidget(badge)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("PDF Compressor")
        title_lbl.setStyleSheet("color: #0F172A; font-size: 22px; font-weight: 700;")
        sub_lbl = QLabel("Kompresi PDF cepat dan aman langsung di perangkat Anda")
        sub_lbl.setStyleSheet("color: #64748B; font-size: 12.5px;")
        sub_lbl.setWordWrap(True)
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        header_row.addLayout(title_box, 1)

        self.gear_btn = QPushButton()
        self.gear_btn.setObjectName("gearBtn")
        self.gear_btn.setFixedSize(36, 36)
        self.gear_btn.setIcon(make_vector_icon("gear", 18, "#475569"))
        self.gear_btn.setIconSize(QSize(18, 18))
        self.gear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gear_btn.setToolTip("Pengaturan Drag & Drop")
        self.gear_btn.clicked.connect(self._show_settings_menu)
        header_row.addWidget(self.gear_btn, 0, Qt.AlignmentFlag.AlignTop)

        root_layout.addLayout(header_row)

        # =================================================================
        # SECTION 1 - DRAG & DROP AREA
        # =================================================================
        drop_outer = QFrame()
        drop_outer.setObjectName("whiteCard")
        drop_outer_lay = QVBoxLayout(drop_outer)
        drop_outer_lay.setContentsMargins(14, 14, 14, 14)

        self.drop_zone = DropZoneFrame()
        self.drop_zone.setMinimumHeight(176)
        self.drop_zone.file_dropped.connect(self._load_pdf_file)
        self.drop_zone.clicked.connect(self._choose_file)

        dz_lay = QVBoxLayout(self.drop_zone)
        dz_lay.setContentsMargins(16, 18, 16, 18)
        dz_lay.setSpacing(6)
        dz_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        dz_icon = QLabel()
        dz_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_icon.setPixmap(make_vector_icon("doc_plus", 42).pixmap(42, 42))
        dz_lay.addWidget(dz_icon)

        dz_title = QLabel("Seret file PDF ke sini")
        dz_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_title.setStyleSheet("color: #0F172A; font-size: 14px; font-weight: 700; background: transparent;")
        dz_lay.addWidget(dz_title)

        dz_or = QLabel("atau")
        dz_or.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_or.setStyleSheet("color: #64748B; font-size: 12px; background: transparent;")
        dz_lay.addWidget(dz_or)

        self.pick_btn = QPushButton("  Pilih File PDF")
        self.pick_btn.setObjectName("pickBtn")
        self.pick_btn.setIcon(make_vector_icon("folder_white", 16))
        self.pick_btn.setIconSize(QSize(16, 16))
        self.pick_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pick_btn.clicked.connect(self._choose_file)
        dz_lay.addWidget(self.pick_btn, 0, Qt.AlignmentFlag.AlignCenter)

        dz_hint = QLabel("Maksimal file sesuai kapasitas perangkat")
        dz_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_hint.setStyleSheet("color: #64748B; font-size: 11px; margin-top: 2px; background: transparent;")
        dz_lay.addWidget(dz_hint)

        drop_outer_lay.addWidget(self.drop_zone)
        root_layout.addWidget(drop_outer)

        # =================================================================
        # FILE SELECTED CARD (Muncul saat file sudah dipilih)
        # =================================================================
        self.file_card = QFrame()
        self.file_card.setObjectName("whiteCard")
        fc_lay = QHBoxLayout(self.file_card)
        fc_lay.setContentsMargins(16, 14, 16, 14)
        fc_lay.setSpacing(14)

        red_badge = QLabel()
        red_badge.setFixedSize(40, 40)
        red_badge.setPixmap(make_vector_icon("red_pdf", 40).pixmap(40, 40))
        fc_lay.addWidget(red_badge)

        file_meta = QVBoxLayout()
        file_meta.setSpacing(2)
        self.file_name_lbl = QLabel("")
        self.file_name_lbl.setStyleSheet("color: #0F172A; font-size: 13.5px; font-weight: 700;")
        self.file_name_lbl.setWordWrap(True)
        self.file_sub_lbl = QLabel("")
        self.file_sub_lbl.setStyleSheet("color: #64748B; font-size: 12px;")
        file_meta.addWidget(self.file_name_lbl)
        file_meta.addWidget(self.file_sub_lbl)
        fc_lay.addLayout(file_meta, 1)

        self.clear_btn = QPushButton("✕")
        self.clear_btn.setObjectName("clearFileBtn")
        self.clear_btn.setFixedSize(32, 32)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setToolTip("Hapus file terpilih")
        self.clear_btn.clicked.connect(self._clear_selected_file)
        fc_lay.addWidget(self.clear_btn)

        self.file_card.hide()
        root_layout.addWidget(self.file_card)

        # =================================================================
        # SECTION 2 - TINGKAT KOMPRESI
        # =================================================================
        sec2_lbl = QLabel("Tingkat Kompresi")
        sec2_lbl.setStyleSheet("color: #0F172A; font-size: 14px; font-weight: 700;")
        root_layout.addWidget(sec2_lbl)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        self.level_cards: dict[int, LevelChoiceCard] = {}
        for lvl, title, dpi, desc, icon_kind in LEVEL_CARDS:
            card = LevelChoiceCard(lvl, title, dpi, desc, icon_kind)
            card.selected_signal.connect(self._select_level)
            cards_row.addWidget(card, 1)
            self.level_cards[lvl] = card
        root_layout.addLayout(cards_row)

        # =================================================================
        # SECTION 3 - PERKIRAAN HASIL / HASIL KOMPRESI
        # =================================================================
        self.estimate_section = QWidget()
        est_sec_lay = QVBoxLayout(self.estimate_section)
        est_sec_lay.setContentsMargins(0, 0, 0, 0)
        est_sec_lay.setSpacing(10)

        self.estimate_heading = QLabel("Perkiraan Hasil")
        self.estimate_heading.setStyleSheet("color: #0F172A; font-size: 14px; font-weight: 700;")
        est_sec_lay.addWidget(self.estimate_heading)

        est_card = QFrame()
        est_card.setObjectName("whiteCard")
        est_lay = QHBoxLayout(est_card)
        est_lay.setContentsMargins(22, 16, 18, 16)
        est_lay.setSpacing(16)

        # Kolom 1: Ukuran Asli
        col_orig = QVBoxLayout()
        col_orig.setSpacing(2)
        lbl_orig_title = QLabel("Ukuran Asli")
        lbl_orig_title.setStyleSheet("color: #64748B; font-size: 11.5px;")
        self.lbl_orig_val = QLabel("-")
        self.lbl_orig_val.setStyleSheet("color: #0F172A; font-size: 20px; font-weight: 700;")
        col_orig.addWidget(lbl_orig_title)
        col_orig.addWidget(self.lbl_orig_val)
        est_lay.addLayout(col_orig, 1)

        # Panah tengah
        arrow_lbl = QLabel("→")
        arrow_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow_lbl.setStyleSheet("color: #64748B; font-size: 20px; font-weight: 600;")
        est_lay.addWidget(arrow_lbl)

        # Kolom 2: Setelah Kompres
        col_after = QVBoxLayout()
        col_after.setSpacing(1)
        lbl_after_title = QLabel("Setelah Kompres")
        lbl_after_title.setStyleSheet("color: #64748B; font-size: 11.5px;")
        self.lbl_after_val = QLabel("-")
        self.lbl_after_val.setStyleSheet("color: #2563EB; font-size: 20px; font-weight: 700;")
        self.lbl_after_note = QLabel("(perkiraan)")
        self.lbl_after_note.setStyleSheet("color: #64748B; font-size: 11px;")
        col_after.addWidget(lbl_after_title)
        col_after.addWidget(self.lbl_after_val)
        col_after.addWidget(self.lbl_after_note)
        est_lay.addLayout(col_after, 1)

        # Kolom 3: Badge Hijau Penghematan
        savings_box = QFrame()
        savings_box.setObjectName("savingsBadge")
        sav_lay = QHBoxLayout(savings_box)
        sav_lay.setContentsMargins(16, 10, 18, 10)
        sav_lay.setSpacing(10)

        green_arrow = QLabel()
        green_arrow.setFixedSize(26, 26)
        green_arrow.setPixmap(make_vector_icon("green_down", 26).pixmap(26, 26))
        sav_lay.addWidget(green_arrow)

        sav_text_col = QVBoxLayout()
        sav_text_col.setSpacing(0)
        self.lbl_pct_val = QLabel("68%")
        self.lbl_pct_val.setStyleSheet("color: #16A34A; font-size: 20px; font-weight: 800;")
        self.lbl_pct_sub = QLabel("Lebih kecil")
        self.lbl_pct_sub.setStyleSheet("color: #15803D; font-size: 11px; font-weight: 600;")
        sav_text_col.addWidget(self.lbl_pct_val)
        sav_text_col.addWidget(self.lbl_pct_sub)
        sav_lay.addLayout(sav_text_col)

        est_lay.addWidget(savings_box)
        est_sec_lay.addWidget(est_card)

        self.estimate_section.hide()
        root_layout.addWidget(self.estimate_section)

        # =================================================================
        # PROGRESS BAR (Muncul saat proses kompresi berjalan)
        # =================================================================
        self.progress_wrap = QFrame()
        self.progress_wrap.setObjectName("whiteCard")
        pw_lay = QVBoxLayout(self.progress_wrap)
        pw_lay.setContentsMargins(18, 14, 18, 14)
        pw_lay.setSpacing(8)

        pw_top = QHBoxLayout()
        self.prog_status_lbl = QLabel("Mengompresi PDF...")
        self.prog_status_lbl.setStyleSheet("color: #0F172A; font-size: 12.5px; font-weight: 600;")
        self.prog_pct_lbl = QLabel("0%")
        self.prog_pct_lbl.setStyleSheet("color: #2563EB; font-size: 12.5px; font-weight: 700;")
        pw_top.addWidget(self.prog_status_lbl)
        pw_top.addStretch()
        pw_top.addWidget(self.prog_pct_lbl)
        pw_lay.addLayout(pw_top)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        pw_lay.addWidget(self.progress_bar)

        self.progress_wrap.hide()
        root_layout.addWidget(self.progress_wrap)

        # =================================================================
        # ERROR BANNER (Muncul hanya jika terjadi galat)
        # =================================================================
        self.error_card = QFrame()
        self.error_card.setObjectName("errorCard")
        err_lay = QHBoxLayout(self.error_card)
        err_lay.setContentsMargins(16, 12, 16, 12)
        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet("color: #B91C1C; font-size: 12.5px; font-weight: 600;")
        self.error_lbl.setWordWrap(True)
        err_lay.addWidget(self.error_lbl)
        self.error_card.hide()
        root_layout.addWidget(self.error_card)

        # =================================================================
        # SECTION 4 - INFO PRIVASI
        # =================================================================
        info_card = QFrame()
        info_card.setObjectName("infoCard")
        info_lay = QHBoxLayout(info_card)
        info_lay.setContentsMargins(16, 14, 16, 14)
        info_lay.setSpacing(12)

        shield_lbl = QLabel()
        shield_lbl.setFixedSize(24, 24)
        shield_lbl.setPixmap(make_vector_icon("shield_check", 24).pixmap(24, 24))
        info_lay.addWidget(shield_lbl, 0, Qt.AlignmentFlag.AlignTop)

        info_text_col = QVBoxLayout()
        info_text_col.setSpacing(2)
        info_t1 = QLabel("Seluruh proses dilakukan secara lokal di komputer Anda.")
        info_t1.setStyleSheet("color: #0F172A; font-size: 12.5px; font-weight: 600;")
        info_t1.setWordWrap(True)
        info_t2 = QLabel("Tidak ada file yang dikirim ke internet. Privasi Anda tetap terjaga.")
        info_t2.setStyleSheet("color: #64748B; font-size: 11.5px;")
        info_t2.setWordWrap(True)
        info_text_col.addWidget(info_t1)
        info_text_col.addWidget(info_t2)
        info_lay.addLayout(info_text_col, 1)

        root_layout.addWidget(info_card)

        # =================================================================
        # SECTION 5 - ACTION BUTTONS
        # =================================================================
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.compress_btn = QPushButton("  Kompres PDF")
        self.compress_btn.setObjectName("primaryActionBtn")
        self.compress_btn.setIcon(make_vector_icon("compress_action", 20))
        self.compress_btn.setIconSize(QSize(20, 20))
        self.compress_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.compress_btn.clicked.connect(self._start_compression)
        btn_row.addWidget(self.compress_btn, 3)

        self.folder_btn = QPushButton("  Buka Folder Hasil")
        self.folder_btn.setObjectName("secondaryActionBtn")
        self.folder_btn.setIcon(make_vector_icon("folder_gray", 18))
        self.folder_btn.setIconSize(QSize(18, 18))
        self.folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_btn.setEnabled(False)
        self.folder_btn.clicked.connect(self._open_output_folder)
        btn_row.addWidget(self.folder_btn, 2)

        root_layout.addLayout(btn_row)
        root_layout.addStretch(1)

        # =================================================================
        # FOOTER BAR
        # =================================================================
        footer_line = QFrame()
        footer_line.setFixedHeight(1)
        footer_line.setStyleSheet("background-color: #E2E8F0;")
        root_layout.addWidget(footer_line)

        footer_row = QHBoxLayout()
        footer_left = QLabel("ⓘ  Mendukung file PDF dengan berbagai ukuran")
        footer_left.setStyleSheet("color: #64748B; font-size: 11px;")
        footer_right = QLabel("<span style='color:#EF4444;'>♡</span>  Ringan. Aman. Cepat.")
        footer_right.setStyleSheet("color: #64748B; font-size: 11px;")
        footer_row.addWidget(footer_left)
        footer_row.addStretch()
        footer_row.addWidget(footer_right)
        root_layout.addLayout(footer_row)

    # =====================================================================
    # INTERACTIONS & LOGIC
    # =====================================================================
    def _show_settings_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            """
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding: 6px;
                font-size: 12.5px;
                color: #0F172A;
            }
            QMenu::item {
                padding: 8px 14px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: #EFF6FF;
                color: #2563EB;
            }
            """
        )
        auto_act = QAction("Otomatis kompres saat file di-drag & drop", self)
        auto_act.setCheckable(True)
        auto_act.setChecked(self.auto_compress_on_drop)
        auto_act.triggered.connect(self._toggle_auto_drop)
        menu.addAction(auto_act)
        menu.exec(self.gear_btn.mapToGlobal(self.gear_btn.rect().bottomLeft()))

    def _toggle_auto_drop(self, checked: bool) -> None:
        self.auto_compress_on_drop = checked

    def _select_level(self, level: int) -> None:
        self.selected_level = level
        for lvl, card in self.level_cards.items():
            card.set_selected(lvl == level)
        self._update_estimate_card()

    def _choose_file(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih File PDF",
            "",
            "File PDF (*.pdf)",
        )
        if file_path:
            self._load_pdf_file(Path(file_path), from_drop=False)

    def _load_pdf_file(self, path: Path, from_drop: bool = True) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self.error_card.hide()
        self.progress_wrap.hide()
        self.output_path = None
        self.folder_btn.setEnabled(False)

        try:
            info = inspect_pdf_info(path)
        except CompressionError as err:
            self._show_error(str(err))
            return

        self.selected_info = info
        self.file_name_lbl.setText(info.path.name)
        self.file_sub_lbl.setText(f"{format_size_inline(info.size_bytes)}  •  {info.page_count} halaman")
        self.file_card.show()
        self._update_estimate_card()

        if from_drop and self.auto_compress_on_drop:
            self._start_compression()

    def _clear_selected_file(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self.selected_info = None
        self.output_path = None
        self.file_card.hide()
        self.estimate_section.hide()
        self.progress_wrap.hide()
        self.error_card.hide()
        self.folder_btn.setEnabled(False)
        trim_working_set()

    def _update_estimate_card(self) -> None:
        if self.selected_info is None:
            self.estimate_section.hide()
            return
        est_bytes = estimate_compressed_size(
            self.selected_info.size_bytes,
            self.selected_info.page_count,
            self.selected_level,
        )
        self._render_comparison(
            orig_bytes=self.selected_info.size_bytes,
            new_bytes=est_bytes,
            is_actual=False,
        )

    def _render_comparison(self, orig_bytes: int, new_bytes: int, is_actual: bool) -> None:
        self.estimate_heading.setText("Hasil Kompresi" if is_actual else "Perkiraan Hasil")
        self.lbl_orig_val.setText(format_size_inline(orig_bytes))
        self.lbl_after_val.setText(format_size_inline(new_bytes))
        self.lbl_after_note.setText("(selesai)" if is_actual else "(perkiraan)")

        if orig_bytes > 0 and new_bytes <= orig_bytes:
            saved_pct = int(round((orig_bytes - new_bytes) / orig_bytes * 100))
            self.lbl_pct_val.setText(f"{saved_pct}%")
            self.lbl_pct_sub.setText("Lebih kecil")
        else:
            inc_pct = int(round(abs(new_bytes - orig_bytes) / max(orig_bytes, 1) * 100))
            self.lbl_pct_val.setText(f"+{inc_pct}%")
            self.lbl_pct_sub.setText("Perubahan")

        self.estimate_section.show()

    def _start_compression(self) -> None:
        if self.selected_info is None:
            self._show_error("Silakan pilih atau seret file PDF terlebih dahulu.")
            return
        if self.worker is not None and self.worker.isRunning():
            return

        self.error_card.hide()
        self.output_path = None
        self.folder_btn.setEnabled(False)
        self._set_busy(True)

        self.worker = CompressionWorker(self.selected_info.path, self.selected_level)
        self.worker.progress_changed.connect(self._on_progress)
        self.worker.succeeded.connect(self._on_success)
        self.worker.failed.connect(self._on_error)
        self.worker.start()

    def _set_busy(self, busy: bool) -> None:
        self.compress_btn.setEnabled(not busy)
        self.pick_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)
        for card in self.level_cards.values():
            card.setEnabled(not busy)

        if busy:
            self.progress_bar.setValue(0)
            self.prog_pct_lbl.setText("0%")
            self.prog_status_lbl.setText("Mengompresi PDF...")
            self.progress_wrap.show()

    def _on_progress(self, pct: int) -> None:
        self.progress_bar.setValue(pct)
        self.prog_pct_lbl.setText(f"{pct}%")

    def _on_success(self, result: CompressionResult) -> None:
        self._set_busy(False)
        self.progress_wrap.hide()
        self.output_path = result.output_path
        self.folder_btn.setEnabled(True)
        self._render_comparison(
            orig_bytes=result.input_bytes,
            new_bytes=result.output_bytes,
            is_actual=True,
        )
        trim_working_set()

    def _on_error(self, message: str) -> None:
        self._set_busy(False)
        self.progress_wrap.hide()
        self._show_error(message)
        trim_working_set()

    def _show_error(self, message: str) -> None:
        self.error_lbl.setText(f"⚠  {message}")
        self.error_card.show()

    def _open_output_folder(self) -> None:
        if self.output_path is None:
            return
        if sys.platform == "win32":
            subprocess.run(["explorer.exe", "/select,", str(self.output_path)], check=False)
        elif hasattr(os, "startfile"):
            os.startfile(str(self.output_path.parent))

    # Terima drop di area mana pun pada jendela utama
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile():
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self._load_pdf_file(Path(urls[0].toLocalFile()), from_drop=True)
            event.acceptProposedAction()


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
'''

ast.parse(compressor_pyqt_code)
ast.parse(app_pyqt_code)

with open("compressor-pyqt6.py", "w", encoding="utf-8") as f:
    f.write(compressor_pyqt_code)

with open("app-pyqt6.py", "w", encoding="utf-8") as f:
    f.write(app_pyqt_code)

print("PYQT6_AST_OK")
