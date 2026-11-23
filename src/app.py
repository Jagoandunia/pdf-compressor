from __future__ import annotations

import inspect
import os
import subprocess
import tkinter as tk
from pathlib import Path
from threading import Thread
from tkinter import filedialog, font as tkfont

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    HAS_DND = True
except ImportError:
    DND_FILES = None
    TkinterDnD = None
    HAS_DND = False

from compressor import CompressionError, CompressionResult, compress_pdf

# Fluent Design Windows 11 Color Palette
BG_APP = "#F8FAFC"
BG_CARD = "#FFFFFF"
BG_SUBTLE = "#F1F5F9"
PRIMARY = "#2563EB"
PRIMARY_HOVER = "#1D4ED8"
PRIMARY_LIGHT = "#EFF6FF"
PRIMARY_BORDER = "#93C5FD"
BORDER = "#E5E7EB"
BORDER_HOVER = "#CBD5E1"
TEXT_PRIMARY = "#0F172A"
TEXT_SECONDARY = "#64748B"
INFO_BG = "#EFF6FF"
INFO_BORDER = "#DBEAFE"
INFO_TEXT = "#1E40AF"
SUCCESS = "#22C55E"
SUCCESS_BG = "#F0FDF4"
SUCCESS_BORDER = "#BBF7D0"
SUCCESS_TEXT = "#15803D"
DANGER = "#EF4444"
DANGER_BG = "#FEF2F2"
DANGER_BORDER = "#FECACA"
DANGER_TEXT = "#B91C1C"

LEVEL_OPTIONS = (
    (1, "Kualitas", "200 DPI", "JPEG 85"),
    (2, "Seimbang", "150 DPI", "JPEG 75"),
    (3, "Kecil", "110 DPI", "JPEG 65"),
)


def pick_font_family(root: tk.Tk) -> str:
    available = {name.lower(): name for name in tkfont.families(root)}
    for candidate in (
        "Segoe UI Variable Text",
        "Segoe UI Variable",
        "Segoe UI",
        "Inter",
        "Arial",
    ):
        if candidate.lower() in available:
            return available[candidate.lower()]
    return "Segoe UI"


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.2f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def format_savings(input_bytes: int, output_bytes: int) -> tuple[str, str]:
    if input_bytes <= 0:
        return "0%", "Penghematan"
    diff = input_bytes - output_bytes
    percent = abs(diff) / input_bytes * 100
    if diff >= 0:
        return f"{percent:.0f}%", "Penghematan"
    return f"+{percent:.0f}%", "Perubahan"


def draw_rounded_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    *,
    fill: str = "",
    outline: str = "",
    width: float = 1.0,
    dash: tuple[int, ...] | None = None,
    tags: str = "shape",
) -> None:
    r = max(0.0, min(radius, (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    points = [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]
    kwargs: dict[str, object] = {
        "smooth": True,
        "splinesteps": 24,
        "fill": fill,
        "outline": outline,
        "width": width,
        "tags": tags,
    }
    if dash is not None:
        kwargs["dash"] = dash
    canvas.create_polygon(points, **kwargs)


class RoundedCard(tk.Canvas):
    """Fluent Design Card dengan sudut membulat dan penyesuaian tinggi otomatis."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        bg_outer: str = BG_APP,
        bg_card: str = BG_CARD,
        border_color: str = BORDER,
        border_width: float = 1.0,
        radius: int = 12,
        padding: int = 20,
        min_height: int = 0,
        shadow: bool = True,
    ) -> None:
        super().__init__(
            parent,
            background=bg_outer,
            highlightthickness=0,
            bd=0,
        )
        self.bg_outer = bg_outer
        self.bg_card = bg_card
        self.border_color = border_color
        self.border_width = border_width
        self.radius = radius
        self.padding = padding
        self.min_height = min_height
        self.shadow = shadow

        self.inner = tk.Frame(self, background=bg_card)
        self._win_id = self.create_window(
            padding,
            padding,
            window=self.inner,
            anchor="nw",
        )
        self.bind("<Configure>", self._on_canvas_configure)
        self.inner.bind("<Configure>", self._on_inner_configure)

    def set_appearance(
        self,
        *,
        bg_card: str | None = None,
        border_color: str | None = None,
        border_width: float | None = None,
    ) -> None:
        if bg_card is not None:
            self.bg_card = bg_card
            self.inner.configure(background=bg_card)
        if border_color is not None:
            self.border_color = border_color
        if border_width is not None:
            self.border_width = border_width
        self._redraw()

    def _on_inner_configure(self, _event: tk.Event) -> None:
        req_h = self.inner.winfo_reqheight() + self.padding * 2 + (2 if self.shadow else 0)
        target_h = max(req_h, self.min_height)
        if int(self.cget("height") or 0) != target_h:
            self.configure(height=target_h)
        self._redraw()

    def _on_canvas_configure(self, event: tk.Event) -> None:
        inner_w = max(event.width - self.padding * 2, 60)
        self.itemconfigure(self._win_id, width=inner_w)
        req_h = self.inner.winfo_reqheight() + self.padding * 2 + (2 if self.shadow else 0)
        target_h = max(req_h, self.min_height)
        if int(self.cget("height") or 0) != target_h:
            self.configure(height=target_h)
        self._redraw()

    def _redraw(self) -> None:
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 4 or h <= 4:
            return
        self.delete("card_bg")
        bottom_offset = 2 if self.shadow else 0
        if self.shadow:
            draw_rounded_rect(
                self,
                1,
                3,
                w - 1,
                h - 1,
                self.radius,
                fill="#EEF2F6",
                outline="",
                tags="card_bg",
            )
        inset = self.border_width / 2.0
        draw_rounded_rect(
            self,
            inset,
            inset,
            w - inset,
            h - bottom_offset - inset,
            self.radius,
            fill=self.bg_card,
            outline=self.border_color,
            width=self.border_width,
            tags="card_bg",
        )
        self.tag_lower("card_bg")


class FluentButton(tk.Canvas):
    """Tombol modern dengan sudut membulat 10px, hover state, dan disabled state."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        text: str,
        command: callable,
        font_tuple: tuple[str, int, str] | tuple[str, int],
        bg_outer: str = BG_APP,
        bg_normal: str = PRIMARY,
        bg_hover: str = PRIMARY_HOVER,
        fg_normal: str = "#FFFFFF",
        border_color: str = "",
        radius: int = 10,
        height: int = 48,
        min_width: int = 220,
        padx: int = 20,
    ) -> None:
        super().__init__(
            parent,
            background=bg_outer,
            height=height,
            width=min_width,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.text = text
        self.command = command
        self.font_tuple = font_tuple
        self.bg_normal = bg_normal
        self.bg_hover = bg_hover
        self.fg_normal = fg_normal
        self.border_color = border_color
        self.radius = radius
        self.btn_height = height
        self.min_width = min_width
        self.padx = padx
        self.hovered = False
        self.enabled = True

        self._measure_and_resize()
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonRelease-1>", self._on_click)

    def _measure_and_resize(self) -> None:
        f = tkfont.Font(font=self.font_tuple)
        text_w = f.measure(self.text)
        target_w = max(self.min_width, text_w + self.padx * 2)
        self.configure(width=target_w, height=self.btn_height)

    def set_text(self, text: str) -> None:
        self.text = text
        self._measure_and_resize()
        self._redraw()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        if not enabled:
            self.hovered = False
        self._redraw()

    def _on_enter(self, _event: tk.Event) -> None:
        if self.enabled:
            self.hovered = True
            self._redraw()

    def _on_leave(self, _event: tk.Event) -> None:
        self.hovered = False
        self._redraw()

    def _on_click(self, event: tk.Event) -> None:
        if not self.enabled:
            return
        if 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            self.command()

    def _redraw(self) -> None:
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 4 or h <= 4:
            return
        self.delete("all")
        if not self.enabled:
            fill = "#93C5FD" if self.bg_normal == PRIMARY else "#F1F5F9"
            fg = "#FFFFFF" if self.bg_normal == PRIMARY else "#94A3B8"
            outline = "" if self.bg_normal == PRIMARY else BORDER
        else:
            fill = self.bg_hover if self.hovered else self.bg_normal
            fg = self.fg_normal
            outline = self.border_color

        inset = 0.5 if outline else 0.0
        draw_rounded_rect(
            self,
            inset,
            inset,
            w - inset,
            h - inset,
            self.radius,
            fill=fill,
            outline=outline,
            width=1.0 if outline else 0.0,
        )
        self.create_text(
            w / 2.0,
            h / 2.0,
            text=self.text,
            fill=fg,
            font=self.font_tuple,
        )


class ChoiceCard(tk.Canvas):
    """Choice Card horizontal modern pengganti RadioButton klasik."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        level: int,
        title: str,
        dpi_text: str,
        quality_text: str,
        font_family: str,
        on_select: callable,
    ) -> None:
        super().__init__(
            parent,
            background=BG_APP,
            height=96,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.level = level
        self.title = title
        self.dpi_text = dpi_text
        self.quality_text = quality_text
        self.font_family = font_family
        self.on_select = on_select
        self.selected = False
        self.hovered = False
        self.enabled = True

        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonRelease-1>", self._on_click)

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        self._redraw()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        if not enabled:
            self.hovered = False
        self._redraw()

    def _on_enter(self, _event: tk.Event) -> None:
        if self.enabled:
            self.hovered = True
            self._redraw()

    def _on_leave(self, _event: tk.Event) -> None:
        self.hovered = False
        self._redraw()

    def _on_click(self, _event: tk.Event) -> None:
        if self.enabled:
            self.on_select(self.level)

    def _redraw(self) -> None:
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 4 or h <= 4:
            return
        self.delete("all")

        if self.selected:
            bg = PRIMARY_LIGHT
            border = PRIMARY
            bw = 2.0
            title_color = PRIMARY
        elif self.hovered:
            bg = "#FFFFFF"
            border = BORDER_HOVER
            bw = 1.5
            title_color = TEXT_PRIMARY
        else:
            bg = BG_CARD
            border = BORDER
            bw = 1.0
            title_color = TEXT_PRIMARY

        if self.hovered or self.selected:
            draw_rounded_rect(
                self,
                1,
                3,
                w - 1,
                h - 1,
                12,
                fill="#E2E8F0" if self.selected else "#EDF2F7",
                outline="",
            )

        inset = bw / 2.0
        draw_rounded_rect(
            self,
            inset,
            inset,
            w - inset,
            h - 2 - inset,
            12,
            fill=bg,
            outline=border,
            width=bw,
        )

        pad_x = 16
        header_text = f"{self.title}  ✅" if self.selected else self.title
        self.create_text(
            pad_x,
            24,
            text=header_text,
            anchor="w",
            fill=title_color,
            font=(self.font_family, 11, "bold"),
        )
        self.create_text(
            pad_x,
            51,
            text=self.dpi_text,
            anchor="w",
            fill=TEXT_SECONDARY,
            font=(self.font_family, 9),
        )
        self.create_text(
            pad_x,
            71,
            text=self.quality_text,
            anchor="w",
            fill=TEXT_SECONDARY,
            font=(self.font_family, 9),
        )


class SmoothProgressBar(tk.Canvas):
    """Animated linear progress bar dengan sudut membulat."""

    def __init__(self, parent: tk.Misc, *, bg_outer: str = BG_CARD, height: int = 10) -> None:
        super().__init__(
            parent,
            background=bg_outer,
            height=height,
            highlightthickness=0,
            bd=0,
        )
        self.bar_height = height
        self.value = 0.0
        self.bind("<Configure>", lambda _e: self._redraw())

    def set_progress(self, percent: float) -> None:
        self.value = max(0.0, min(100.0, percent))
        self._redraw()

    def _redraw(self) -> None:
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 4 or h <= 4:
            return
        self.delete("all")
        r = h / 2.0
        draw_rounded_rect(self, 0, 0, w, h, r, fill="#E2E8F0", outline="")
        if self.value > 0:
            fill_w = max(h, w * (self.value / 100.0))
            draw_rounded_rect(self, 0, 0, min(w, fill_w), h, r, fill=PRIMARY, outline="")


class PdfCompressorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.font_family = pick_font_family(root)
        self.selected_path: Path | None = None
        self.output_path: Path | None = None
        self.is_busy = False
        self.is_dragging = False
        self.selected_level = 2
        self.auto_compress_drop = tk.BooleanVar(value=True)

        self.target_progress = 0.0
        self.display_progress = 0.0
        self._anim_job: str | None = None

        self.root.title("PDF Compressor")
        self.root.geometry("760x820")
        self.root.minsize(520, 620)
        self.root.configure(background=BG_APP)

        self._build_scrollable_shell()
        self._build_ui()
        self._setup_dnd()
        self._select_level(2)

    def _build_scrollable_shell(self) -> None:
        """Membungkus konten dalam area gulir bersih agar tetap responsif saat window diperkecil."""
        self.scroll_canvas = tk.Canvas(
            self.root,
            background=BG_APP,
            highlightthickness=0,
            bd=0,
        )
        self.scrollbar = tk.Scrollbar(
            self.root,
            orient="vertical",
            command=self.scroll_canvas.yview,
        )
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scroll_canvas.pack(side="left", fill="both", expand=True)

        self.page = tk.Frame(self.scroll_canvas, background=BG_APP)
        self._page_win = self.scroll_canvas.create_window((0, 0), window=self.page, anchor="nw")

        self.page.bind("<Configure>", self._sync_scroll_region)
        self.scroll_canvas.bind("<Configure>", self._sync_page_width)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

    def _sync_page_width(self, event: tk.Event) -> None:
        self.scroll_canvas.itemconfigure(self._page_win, width=event.width)
        self._toggle_scrollbar()

    def _sync_scroll_region(self, _event: tk.Event) -> None:
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
        self._toggle_scrollbar()

    def _toggle_scrollbar(self) -> None:
        canvas_h = self.scroll_canvas.winfo_height()
        content_h = self.page.winfo_reqheight()
        if content_h > canvas_h + 4:
            if not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(side="right", fill="y")
        else:
            if self.scrollbar.winfo_ismapped():
                self.scrollbar.pack_forget()
            self.scroll_canvas.yview_moveto(0.0)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self.scrollbar.winfo_ismapped():
            self.scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    @staticmethod
    def _bind_responsive_wrap(container: tk.Widget, label: tk.Label, horizontal_margin: int = 0) -> None:
        def _update(event: tk.Event) -> None:
            avail = max(event.width - horizontal_margin, 140)
            if int(label.cget("wraplength") or 0) != avail:
                label.configure(wraplength=avail)

        container.bind("<Configure>", _update, add="+")

    def _build_ui(self) -> None:
        # Padding halaman 32px
        container = tk.Frame(self.page, background=BG_APP)
        container.pack(fill="both", expand=True, padx=32, pady=32)

        # =================================================================
        # HEADER
        # =================================================================
        header = tk.Frame(container, background=BG_APP)
        header.pack(fill="x")

        icon_badge = tk.Canvas(header, width=48, height=48, background=BG_APP, highlightthickness=0, bd=0)
        icon_badge.pack(side="left", anchor="n")
        draw_rounded_rect(icon_badge, 0, 0, 48, 48, 12, fill=PRIMARY_LIGHT, outline=INFO_BORDER, width=1.0)
        draw_rounded_rect(icon_badge, 14, 10, 34, 38, 3, fill=PRIMARY, outline="")
        icon_badge.create_text(24, 25, text="PDF", fill="#FFFFFF", font=(self.font_family, 7, "bold"))

        header_text = tk.Frame(header, background=BG_APP)
        header_text.pack(side="left", fill="x", expand=True, padx=(14, 0))

        title_lbl = tk.Label(
            header_text,
            text="PDF Compressor",
            background=BG_APP,
            foreground=TEXT_PRIMARY,
            anchor="w",
            justify="left",
            font=(self.font_family, 22, "bold"),
        )
        title_lbl.pack(fill="x")
        self._bind_responsive_wrap(header_text, title_lbl)

        subtitle_lbl = tk.Label(
            header_text,
            text="Kompresi PDF cepat dan aman langsung di perangkat Anda",
            background=BG_APP,
            foreground=TEXT_SECONDARY,
            anchor="w",
            justify="left",
            font=(self.font_family, 10),
        )
        subtitle_lbl.pack(fill="x", pady=(2, 0))
        self._bind_responsive_wrap(header_text, subtitle_lbl)

        # =================================================================
        # SECTION 1 - DRAG DROP AREA (Jarak antar section: 24px)
        # =================================================================
        self.drop_card = RoundedCard(
            container,
            bg_outer=BG_APP,
            bg_card=BG_CARD,
            border_color=BORDER,
            border_width=1.0,
            radius=14,
            padding=20,
            min_height=200,
            shadow=True,
        )
        self.drop_card.pack(fill="x", pady=(24, 0))

        self.drop_zone = tk.Canvas(
            self.drop_card.inner,
            background=BG_CARD,
            height=160,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.drop_zone.pack(fill="both", expand=True)
        self.drop_zone.bind("<Configure>", lambda _e: self._redraw_drop_zone())
        self.drop_zone.bind("<ButtonRelease-1>", self._on_drop_zone_click)

        # Opsi otomatis kompres saat drag & drop
        auto_row = tk.Frame(container, background=BG_APP)
        auto_row.pack(fill="x", pady=(10, 0))
        self.auto_check = tk.Checkbutton(
            auto_row,
            text="Otomatis langsung kompres saat file di-drag & drop",
            variable=self.auto_compress_drop,
            background=BG_APP,
            activebackground=BG_APP,
            foreground=TEXT_SECONDARY,
            activeforeground=TEXT_PRIMARY,
            selectcolor=BG_CARD,
            cursor="hand2",
            anchor="w",
            justify="left",
            font=(self.font_family, 9),
        )
        self.auto_check.pack(fill="x")
        self._bind_responsive_wrap(auto_row, self.auto_check, horizontal_margin=24)

        # =================================================================
        # SECTION 2 - TINGKAT KOMPRESI (Choice Cards)
        # =================================================================
        sec2_frame = tk.Frame(container, background=BG_APP)
        sec2_frame.pack(fill="x", pady=(24, 0))

        sec2_title = tk.Label(
            sec2_frame,
            text="Tingkat Kompresi",
            background=BG_APP,
            foreground=TEXT_PRIMARY,
            anchor="w",
            justify="left",
            font=(self.font_family, 11, "bold"),
        )
        sec2_title.pack(fill="x", pady=(0, 10))

        cards_grid = tk.Frame(sec2_frame, background=BG_APP)
        cards_grid.pack(fill="x")
        self.choice_cards: dict[int, ChoiceCard] = {}
        for idx, (lvl, title, dpi_txt, qual_txt) in enumerate(LEVEL_OPTIONS):
            cards_grid.grid_columnconfigure(idx, weight=1, uniform="choice_col")
            card = ChoiceCard(
                cards_grid,
                level=lvl,
                title=title,
                dpi_text=dpi_txt,
                quality_text=qual_txt,
                font_family=self.font_family,
                on_select=self._select_level,
            )
            card.grid(row=0, column=idx, sticky="ew", padx=(0, 12) if idx < 2 else 0)
            self.choice_cards[lvl] = card

        # =================================================================
        # SECTION 3 - INFORMASI (Info Card #EFF6FF)
        # =================================================================
        info_card = RoundedCard(
            container,
            bg_outer=BG_APP,
            bg_card=INFO_BG,
            border_color=INFO_BORDER,
            border_width=1.0,
            radius=12,
            padding=20,
            shadow=False,
        )
        info_card.pack(fill="x", pady=(24, 0))

        info_row = tk.Frame(info_card.inner, background=INFO_BG)
        info_row.pack(fill="x")

        info_icon = tk.Label(
            info_row,
            text="ℹ",
            background=INFO_BG,
            foreground=PRIMARY,
            font=(self.font_family, 13, "bold"),
            anchor="n",
        )
        info_icon.pack(side="left", anchor="n", padx=(0, 12))

        info_text = tk.Label(
            info_row,
            text=(
                "Kompresi dilakukan secara lokal di komputer Anda.\n"
                "PDF hasil akan dikonversi menjadi PDF berbasis gambar untuk mendapatkan ukuran file yang lebih kecil."
            ),
            background=INFO_BG,
            foreground=INFO_TEXT,
            anchor="w",
            justify="left",
            font=(self.font_family, 9),
        )
        info_text.pack(side="left", fill="x", expand=True)
        self._bind_responsive_wrap(info_row, info_text, horizontal_margin=36)

        # =================================================================
        # SECTION 4 - ACTION BUTTON
        # =================================================================
        action_frame = tk.Frame(container, background=BG_APP)
        action_frame.pack(fill="x", pady=(24, 0))

        self.compress_btn = FluentButton(
            action_frame,
            text="🗜️  Kompres PDF",
            command=self.start_compression,
            font_tuple=(self.font_family, 11, "bold"),
            bg_outer=BG_APP,
            bg_normal=PRIMARY,
            bg_hover=PRIMARY_HOVER,
            fg_normal="#FFFFFF",
            radius=10,
            height=48,
            min_width=220,
            padx=24,
        )
        self.compress_btn.pack(side="left")

        self.ghost_folder_btn = FluentButton(
            action_frame,
            text="📁  Buka Folder Hasil",
            command=self.open_output_folder,
            font_tuple=(self.font_family, 10, "bold"),
            bg_outer=BG_APP,
            bg_normal=BG_APP,
            bg_hover=BG_SUBTLE,
            fg_normal=TEXT_SECONDARY,
            radius=10,
            height=48,
            min_width=170,
            padx=16,
        )
        self.ghost_folder_btn.pack(side="left", padx=(12, 0))
        self.ghost_folder_btn.set_enabled(False)

        # =================================================================
        # PROGRESS SECTION (Tersembunyi saat idle)
        # =================================================================
        self.progress_card = RoundedCard(
            container,
            bg_outer=BG_APP,
            bg_card=BG_CARD,
            border_color=BORDER,
            border_width=1.0,
            radius=12,
            padding=20,
            shadow=True,
        )
        prog_header = tk.Frame(self.progress_card.inner, background=BG_CARD)
        prog_header.pack(fill="x", pady=(0, 10))

        self.prog_title_lbl = tk.Label(
            prog_header,
            text="Mengompresi PDF...",
            background=BG_CARD,
            foreground=TEXT_PRIMARY,
            font=(self.font_family, 10, "bold"),
            anchor="w",
        )
        self.prog_title_lbl.pack(side="left")

        self.prog_pct_lbl = tk.Label(
            prog_header,
            text="0%",
            background=BG_CARD,
            foreground=PRIMARY,
            font=(self.font_family, 10, "bold"),
            anchor="e",
        )
        self.prog_pct_lbl.pack(side="right")

        self.progress_bar = SmoothProgressBar(self.progress_card.inner, bg_outer=BG_CARD, height=10)
        self.progress_bar.pack(fill="x")

        # =================================================================
        # SUCCESS STATE CARD (Tersembunyi sampai selesai)
        # =================================================================
        self.success_card = RoundedCard(
            container,
            bg_outer=BG_APP,
            bg_card=SUCCESS_BG,
            border_color=SUCCESS_BORDER,
            border_width=1.0,
            radius=12,
            padding=20,
            shadow=False,
        )
        self.success_header_lbl = tk.Label(
            self.success_card.inner,
            text="✅  Kompresi Berhasil",
            background=SUCCESS_BG,
            foreground=SUCCESS_TEXT,
            anchor="w",
            font=(self.font_family, 12, "bold"),
        )
        self.success_header_lbl.pack(fill="x")

        metrics_row = tk.Frame(self.success_card.inner, background=SUCCESS_BG)
        metrics_row.pack(fill="x", pady=(14, 16))
        for i in range(3):
            metrics_row.grid_columnconfigure(i, weight=1, uniform="metric_col")

        self.metric_before_val = self._build_metric_box(metrics_row, 0, "Ukuran Awal", "-")
        self.metric_after_val = self._build_metric_box(metrics_row, 1, "Ukuran Akhir", "-")
        self.metric_saved_lbl, self.metric_saved_val = self._build_metric_box_with_title(
            metrics_row, 2, "Penghematan", "-", highlight=True
        )

        success_btns = tk.Frame(self.success_card.inner, background=SUCCESS_BG)
        success_btns.pack(fill="x")

        self.open_file_btn = FluentButton(
            success_btns,
            text="Buka File",
            command=self.open_output_file,
            font_tuple=(self.font_family, 10, "bold"),
            bg_outer=SUCCESS_BG,
            bg_normal=SUCCESS,
            bg_hover="#16A34A",
            fg_normal="#FFFFFF",
            radius=10,
            height=40,
            min_width=130,
            padx=18,
        )
        self.open_file_btn.pack(side="left")

        self.open_folder_btn = FluentButton(
            success_btns,
            text="Buka Folder",
            command=self.open_output_folder,
            font_tuple=(self.font_family, 10, "bold"),
            bg_outer=SUCCESS_BG,
            bg_normal="#FFFFFF",
            bg_hover="#F8FAFC",
            fg_normal=TEXT_PRIMARY,
            border_color=SUCCESS_BORDER,
            radius=10,
            height=40,
            min_width=135,
            padx=18,
        )
        self.open_folder_btn.pack(side="left", padx=(10, 0))

        # =================================================================
        # ERROR BANNER (Tersembunyi kecuali ada kesalahan)
        # =================================================================
        self.error_card = RoundedCard(
            container,
            bg_outer=BG_APP,
            bg_card=DANGER_BG,
            border_color=DANGER_BORDER,
            border_width=1.0,
            radius=12,
            padding=16,
            shadow=False,
        )
        self.error_lbl = tk.Label(
            self.error_card.inner,
            text="",
            background=DANGER_BG,
            foreground=DANGER_TEXT,
            anchor="w",
            justify="left",
            font=(self.font_family, 9, "bold"),
        )
        self.error_lbl.pack(fill="x")
        self._bind_responsive_wrap(self.error_card.inner, self.error_lbl, horizontal_margin=16)

    def _build_metric_box(self, parent: tk.Frame, col: int, title: str, value: str) -> tk.Label:
        _, val_lbl = self._build_metric_box_with_title(parent, col, title, value, highlight=False)
        return val_lbl

    def _build_metric_box_with_title(
        self,
        parent: tk.Frame,
        col: int,
        title: str,
        value: str,
        *,
        highlight: bool,
    ) -> tuple[tk.Label, tk.Label]:
        box = tk.Frame(parent, background=SUCCESS_BG)
        box.grid(row=0, column=col, sticky="w", padx=(0, 12) if col < 2 else 0)
        t_lbl = tk.Label(
            box,
            text=title,
            background=SUCCESS_BG,
            foreground=TEXT_SECONDARY,
            font=(self.font_family, 9),
            anchor="w",
        )
        t_lbl.pack(anchor="w")
        v_lbl = tk.Label(
            box,
            text=value,
            background=SUCCESS_BG,
            foreground=SUCCESS_TEXT if highlight else TEXT_PRIMARY,
            font=(self.font_family, 13, "bold"),
            anchor="w",
        )
        v_lbl.pack(anchor="w", pady=(2, 0))
        return t_lbl, v_lbl

    # =====================================================================
    # DROP ZONE RENDERING & INTERACTION
    # =====================================================================
    def _redraw_drop_zone(self) -> None:
        w = self.drop_zone.winfo_width()
        h = self.drop_zone.winfo_height()
        if w <= 10 or h <= 10:
            return
        self.drop_zone.delete("all")

        bg = PRIMARY_LIGHT if self.is_dragging else BG_CARD
        dash_color = PRIMARY if self.is_dragging else "#CBD5E1"
        self.drop_zone.configure(background=bg)
        self.drop_card.set_appearance(
            bg_card=bg,
            border_color=PRIMARY if self.is_dragging else BORDER,
            border_width=2.0 if self.is_dragging else 1.0,
        )

        draw_rounded_rect(
            self.drop_zone,
            1,
            1,
            w - 1,
            h - 1,
            10,
            fill=bg,
            outline=dash_color,
            width=1.5,
            dash=(5, 4),
        )

        cx = w / 2.0
        if self.selected_path is None:
            self.drop_zone.create_text(
                cx,
                34,
                text="📄",
                font=(self.font_family, 22),
                fill=PRIMARY,
            )
            self.drop_zone.create_text(
                cx,
                68,
                text="Seret file PDF ke sini",
                font=(self.font_family, 12, "bold"),
                fill=TEXT_PRIMARY,
            )
            self.drop_zone.create_text(
                cx,
                91,
                text="atau",
                font=(self.font_family, 9),
                fill=TEXT_SECONDARY,
            )
            self.drop_zone.create_text(
                cx,
                113,
                text="Klik untuk memilih file",
                font=(self.font_family, 10, "bold"),
                fill=PRIMARY,
                tags="pick_link",
            )
            self.drop_zone.create_text(
                cx,
                140,
                text="Maksimal file sesuai kapasitas perangkat",
                font=(self.font_family, 8),
                fill=TEXT_SECONDARY,
            )
        else:
            size_str = format_bytes(self.selected_path.stat().st_size)
            display_name = self.selected_path.name
            max_chars = max(22, int((w - 60) / 8))
            if len(display_name) > max_chars:
                display_name = display_name[: max_chars - 3] + "..."

            self.drop_zone.create_text(
                cx,
                38,
                text=f"📄  {display_name}",
                font=(self.font_family, 12, "bold"),
                fill=TEXT_PRIMARY,
            )
            self.drop_zone.create_text(
                cx,
                68,
                text=f"Ukuran:  {size_str}",
                font=(self.font_family, 10),
                fill=TEXT_SECONDARY,
            )
            btn_w = 116
            btn_h = 34
            bx1 = cx - btn_w / 2.0
            by1 = 96
            bx2 = cx + btn_w / 2.0
            by2 = by1 + btn_h
            draw_rounded_rect(
                self.drop_zone,
                bx1,
                by1,
                bx2,
                by2,
                8,
                fill=PRIMARY_LIGHT,
                outline=PRIMARY_BORDER,
                width=1.0,
                tags="change_btn",
            )
            self.drop_zone.create_text(
                cx,
                by1 + btn_h / 2.0,
                text="Ganti File",
                font=(self.font_family, 9, "bold"),
                fill=PRIMARY,
                tags="change_btn",
            )

    def _on_drop_zone_click(self, _event: tk.Event) -> None:
        if not self.is_busy:
            self.choose_file()

    def _setup_dnd(self) -> None:
        if not HAS_DND:
            return
        for target in (self.root, self.drop_zone, self.drop_card):
            if hasattr(target, "drop_target_register"):
                try:
                    target.drop_target_register(DND_FILES)
                    target.dnd_bind("<<DropEnter>>", self._on_drag_enter)
                    target.dnd_bind("<<DropLeave>>", self._on_drag_leave)
                    target.dnd_bind("<<Drop>>", self._on_drop)
                except Exception:
                    pass

    def _on_drag_enter(self, _event: tk.Event) -> None:
        if not self.is_busy and not self.is_dragging:
            self.is_dragging = True
            self._redraw_drop_zone()

    def _on_drag_leave(self, _event: tk.Event) -> None:
        if self.is_dragging:
            self.is_dragging = False
            self._redraw_drop_zone()

    def _on_drop(self, event: tk.Event) -> None:
        self.is_dragging = False
        self._redraw_drop_zone()
        if self.is_busy:
            return
        raw_data = getattr(event, "data", "")
        if not raw_data:
            return
        try:
            paths = self.root.tk.splitlist(raw_data)
        except tk.TclError:
            paths = [raw_data.strip("{}")]

        if not paths:
            return

        dropped_path = Path(paths[0])
        if dropped_path.suffix.lower() != ".pdf":
            self._show_error(f"Format tidak didukung ({dropped_path.name}). Harap seret file .pdf.")
            return
        if not dropped_path.is_file():
            self._show_error("File PDF yang diseret tidak dapat diakses.")
            return

        self._load_selected_file(dropped_path)
        if self.auto_compress_drop.get():
            self.start_compression()

    # =====================================================================
    # STATE & ACTIONS
    # =====================================================================
    def _select_level(self, level: int) -> None:
        if self.is_busy:
            return
        self.selected_level = level
        for lvl, card in self.choice_cards.items():
            card.set_selected(lvl == level)
        self._hide_feedback_cards()

    def _hide_feedback_cards(self) -> None:
        self.output_path = None
        self.ghost_folder_btn.set_enabled(False)
        self.progress_card.pack_forget()
        self.success_card.pack_forget()
        self.error_card.pack_forget()

    def _load_selected_file(self, path: Path) -> None:
        self.selected_path = path
        self._hide_feedback_cards()
        self._redraw_drop_zone()

    def choose_file(self) -> None:
        if self.is_busy:
            return
        selected = filedialog.askopenfilename(
            title="Pilih file PDF",
            filetypes=[("File PDF", "*.pdf")],
        )
        if not selected:
            return
        self._load_selected_file(Path(selected))

    def start_compression(self) -> None:
        if self.is_busy:
            return
        if self.selected_path is None:
            self._show_error("Silakan pilih atau seret file PDF terlebih dahulu.")
            return

        source = self.selected_path
        level = self.selected_level
        self._set_busy(True)

        Thread(
            target=self._compress_worker,
            args=(source, level),
            daemon=True,
        ).start()

    def _on_worker_progress(self, current: int, total: int) -> None:
        if total <= 0:
            return
        pct = min(92.0, (current / total) * 92.0)
        self.target_progress = max(self.target_progress, pct)

    def _animate_progress(self) -> None:
        if not self.is_busy:
            return
        if self.target_progress < 88.0:
            self.target_progress = min(88.0, self.target_progress + 0.6)
        diff = self.target_progress - self.display_progress
        if abs(diff) > 0.1:
            self.display_progress += diff * 0.25
        else:
            self.display_progress = self.target_progress

        pct_int = int(round(self.display_progress))
        self.prog_pct_lbl.configure(text=f"{pct_int}%")
        self.progress_bar.set_progress(self.display_progress)
        self._anim_job = self.root.after(30, self._animate_progress)

    def _compress_worker(self, source: Path, level: int) -> None:
        try:
            sig = inspect.signature(compress_pdf)
            if "progress_callback" in sig.parameters:
                result = compress_pdf(
                    source,
                    level,
                    progress_callback=lambda cur, tot: self.root.after(
                        0, lambda c=cur, t=tot: self._on_worker_progress(c, t)
                    ),
                )
            else:
                result = compress_pdf(source, level)
        except (CompressionError, ValueError) as error:
            self.root.after(0, lambda: self._finish_with_error(str(error)))
        except Exception:
            self.root.after(
                0,
                lambda: self._finish_with_error("Terjadi kesalahan saat kompresi, periksa file lalu coba lagi."),
            )
        else:
            self.root.after(0, lambda: self._finish_with_success(result))

    def _set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        self.compress_btn.set_enabled(not busy)
        self.auto_check.configure(state="disabled" if busy else "normal")
        for card in self.choice_cards.values():
            card.set_enabled(not busy)

        if busy:
            self._hide_feedback_cards()
            self.target_progress = 8.0
            self.display_progress = 0.0
            self.prog_pct_lbl.configure(text="0%")
            self.progress_bar.set_progress(0.0)
            self.progress_card.pack(fill="x", pady=(24, 0))
            self._animate_progress()
        else:
            if self._anim_job is not None:
                self.root.after_cancel(self._anim_job)
                self._anim_job = None

    def _finish_with_success(self, result: CompressionResult) -> None:
        self.display_progress = 100.0
        self.prog_pct_lbl.configure(text="100%")
        self.progress_bar.set_progress(100.0)
        self.root.after(180, lambda: self._render_success_state(result))

    def _render_success_state(self, result: CompressionResult) -> None:
        self._set_busy(False)
        self.progress_card.pack_forget()
        self.error_card.pack_forget()

        self.output_path = result.output_path
        self.ghost_folder_btn.set_enabled(True)

        saved_val, saved_title = format_savings(result.input_bytes, result.output_bytes)
        self.metric_before_val.configure(text=format_bytes(result.input_bytes))
        self.metric_after_val.configure(text=format_bytes(result.output_bytes))
        self.metric_saved_lbl.configure(text=saved_title)
        self.metric_saved_val.configure(text=saved_val)

        self.success_card.pack(fill="x", pady=(24, 0))

    def _finish_with_error(self, message: str) -> None:
        self._set_busy(False)
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self.progress_card.pack_forget()
        self.success_card.pack_forget()
        self.error_lbl.configure(text=f"⚠  {message}")
        self.error_card.pack(fill="x", pady=(24, 0))

    def open_output_file(self) -> None:
        if self.output_path is None or not self.output_path.exists():
            return
        if hasattr(os, "startfile"):
            os.startfile(str(self.output_path))
        else:
            subprocess.run(["explorer.exe", str(self.output_path)], check=False)

    def open_output_folder(self) -> None:
        if self.output_path is None:
            return
        subprocess.run(
            ["explorer.exe", "/select,", str(self.output_path)],
            check=False,
        )


def main() -> None:
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    PdfCompressorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
