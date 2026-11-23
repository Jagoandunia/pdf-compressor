from __future__ import annotations

import subprocess
import tkinter as tk
from pathlib import Path
from threading import Thread
from tkinter import filedialog, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    HAS_DND = True
except ImportError:
    DND_FILES = None
    TkinterDnD = None
    HAS_DND = False

from compressor import CompressionError, CompressionResult, compress_pdf

LEVEL_OPTIONS = (
    (1, "Level 1 · Prioritas Jernih", "200 DPI · Kualitas JPEG 85"),
    (2, "Level 2 · Seimbang (Rekomendasi)", "150 DPI · Kualitas JPEG 75"),
    (3, "Level 3 · Prioritas Ukuran Kecil", "110 DPI · Kualitas JPEG 65"),
)

BACKGROUND = "#F4F7FB"
CARD = "#FFFFFF"
DROP_HOVER = "#EEF5FF"
INK = "#102A43"
MUTED = "#627D98"
ACCENT = "#1769E0"
ACCENT_DARK = "#0F4EA8"
SUCCESS = "#138A5B"
DANGER = "#C2415A"
NOTICE = "#FFF4D6"
NOTICE_INK = "#7A4B00"


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.2f} KB"
    return f"{size / (1024 * 1024):.2f} MB"


def format_ratio(input_bytes: int, output_bytes: int) -> str:
    if input_bytes <= 0:
        return "Rasio tidak dapat dihitung"
    percent = abs(output_bytes - input_bytes) / input_bytes * 100
    action = "Berkurang" if output_bytes <= input_bytes else "Bertambah"
    return f"{action} {percent:.1f}%"


class PdfCompressorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.selected_path: Path | None = None
        self.output_path: Path | None = None
        self.is_busy = False
        self.level = tk.IntVar(value=2)
        self.auto_compress_drop = tk.BooleanVar(value=True)
        self.file_text = tk.StringVar(value="Belum ada file yang dipilih")
        default_detail = (
            "Tarik & lepas (drag & drop) file PDF ke area ini, atau klik Pilih PDF"
            if HAS_DND
            else "Mendukung file PDF lokal"
        )
        self.file_detail = tk.StringVar(value=default_detail)
        self.status_text = tk.StringVar(value="Pilih atau seret file PDF dan tentukan tingkat kompresi.")
        self.result_text = tk.StringVar(value="")

        self.root.title("Kompresor PDF Ringan")
        self.root.geometry("760x680")
        self.root.minsize(480, 580)
        self.root.configure(background=BACKGROUND)
        self._configure_style()
        self._build()
        self._setup_dnd()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor=BACKGROUND,
            background=ACCENT,
            bordercolor=BACKGROUND,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )

    @staticmethod
    def _card(parent: tk.Misc, *, background: str = CARD) -> tk.Frame:
        return tk.Frame(
            parent,
            background=background,
            highlightbackground="#D9E2EC",
            highlightthickness=1,
            padx=22,
            pady=18,
        )

    @staticmethod
    def _bind_responsive_wrap(container: tk.Widget, label: tk.Label, horizontal_margin: int = 0) -> None:
        def _update_wrap(event: tk.Event) -> None:
            available = max(event.width - horizontal_margin, 120)
            if int(label.cget("wraplength") or 0) != available:
                label.configure(wraplength=available)

        container.bind("<Configure>", _update_wrap, add="+")

    def _build(self) -> None:
        main = tk.Frame(self.root, background=BACKGROUND)
        main.pack(fill="both", expand=True, padx=28, pady=24)

        title_label = tk.Label(
            main,
            text="Kompresor PDF Ringan",
            background=BACKGROUND,
            foreground=INK,
            anchor="w",
            justify="left",
            font=("Segoe UI Semibold", 24),
        )
        title_label.pack(fill="x")
        self._bind_responsive_wrap(main, title_label)

        subtitle_label = tk.Label(
            main,
            text="Kompresi lokal · File asli tidak diubah · Otomatis membuat file baru",
            background=BACKGROUND,
            foreground=MUTED,
            anchor="w",
            justify="left",
            font=("Segoe UI", 10),
        )
        subtitle_label.pack(fill="x", pady=(2, 16))
        self._bind_responsive_wrap(main, subtitle_label)

        self.file_card = self._card(main)
        self.file_card.pack(fill="x")
        self.file_step_label = tk.Label(
            self.file_card,
            text="① Pilih atau Seret (Drag & Drop) File PDF",
            background=CARD,
            foreground=INK,
            anchor="w",
            justify="left",
            font=("Segoe UI Semibold", 12),
        )
        self.file_step_label.pack(fill="x")
        self._bind_responsive_wrap(self.file_card, self.file_step_label, horizontal_margin=44)

        self.file_row = tk.Frame(self.file_card, background=CARD)
        self.file_row.pack(fill="x", pady=(12, 0))
        self.file_button = tk.Button(
            self.file_row,
            text="Pilih PDF",
            command=self.choose_file,
            cursor="hand2",
            background="#E8F1FF",
            foreground=ACCENT_DARK,
            activebackground="#D7E8FF",
            activeforeground=ACCENT_DARK,
            relief="flat",
            padx=16,
            pady=8,
            font=("Segoe UI Semibold", 10),
        )
        self.file_button.pack(side="left", anchor="n")

        self.labels_frame = tk.Frame(self.file_row, background=CARD)
        self.labels_frame.pack(side="left", fill="x", expand=True, padx=(14, 0))
        self.file_name_label = tk.Label(
            self.labels_frame,
            textvariable=self.file_text,
            background=CARD,
            foreground=INK,
            anchor="w",
            justify="left",
            font=("Segoe UI Semibold", 10),
        )
        self.file_name_label.pack(fill="x")
        self._bind_responsive_wrap(self.labels_frame, self.file_name_label)

        self.file_detail_label = tk.Label(
            self.labels_frame,
            textvariable=self.file_detail,
            background=CARD,
            foreground=MUTED,
            anchor="w",
            justify="left",
            font=("Segoe UI", 9),
        )
        self.file_detail_label.pack(fill="x", pady=(2, 0))
        self._bind_responsive_wrap(self.labels_frame, self.file_detail_label)

        self.auto_drop_check = tk.Checkbutton(
            self.file_card,
            text="Otomatis langsung kompres saat file di-drag & drop",
            variable=self.auto_compress_drop,
            cursor="hand2",
            background=CARD,
            activebackground=CARD,
            foreground=INK,
            selectcolor="#DCEBFF",
            anchor="w",
            justify="left",
            font=("Segoe UI", 9),
        )
        self.auto_drop_check.pack(fill="x", pady=(12, 0))
        self._bind_responsive_wrap(self.file_card, self.auto_drop_check, horizontal_margin=64)

        level_card = self._card(main)
        level_card.pack(fill="x", pady=(14, 0))
        level_step_label = tk.Label(
            level_card,
            text="② Pilih Tingkat Kompresi",
            background=CARD,
            foreground=INK,
            anchor="w",
            justify="left",
            font=("Segoe UI Semibold", 12),
        )
        level_step_label.pack(fill="x")
        self._bind_responsive_wrap(level_card, level_step_label, horizontal_margin=44)

        self.level_controls: list[tk.Radiobutton] = []
        level_row = tk.Frame(level_card, background=CARD)
        level_row.pack(fill="x", pady=(12, 0))
        for index, (level, title, detail) in enumerate(LEVEL_OPTIONS):
            item = tk.Frame(
                level_row,
                background="#F8FAFD",
                highlightbackground="#D9E2EC",
                highlightthickness=1,
                padx=10,
                pady=9,
            )
            item.grid(row=0, column=index, sticky="nsew", padx=(0, 8) if index < 2 else 0)
            level_row.grid_columnconfigure(index, weight=1, uniform="level_col")
            control = tk.Radiobutton(
                item,
                text=title,
                variable=self.level,
                value=level,
                command=self._clear_result,
                background="#F8FAFD",
                activebackground="#F8FAFD",
                foreground=INK,
                selectcolor="#DCEBFF",
                font=("Segoe UI Semibold", 10),
                anchor="w",
                justify="left",
            )
            control.pack(fill="x")
            self._bind_responsive_wrap(item, control, horizontal_margin=42)

            detail_lbl = tk.Label(
                item,
                text=detail,
                background="#F8FAFD",
                foreground=MUTED,
                anchor="w",
                justify="left",
                font=("Segoe UI", 8),
            )
            detail_lbl.pack(fill="x", padx=(24, 0), pady=(3, 0))
            self._bind_responsive_wrap(item, detail_lbl, horizontal_margin=44)
            self.level_controls.append(control)

        notice = self._card(main, background=NOTICE)
        notice.pack(fill="x", pady=(14, 0))
        notice_label = tk.Label(
            notice,
            text="Catatan: Hasil kompresi akan dikonversi menjadi PDF berbasis gambar, sehingga teks tidak lagi dapat dicari, disalin, atau diedit.",
            background=NOTICE,
            foreground=NOTICE_INK,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
        )
        notice_label.pack(fill="x")
        self._bind_responsive_wrap(notice, notice_label, horizontal_margin=44)

        action_row = tk.Frame(main, background=BACKGROUND)
        action_row.pack(fill="x", pady=(18, 0))
        self.start_button = tk.Button(
            action_row,
            text="Mulai Kompresi",
            command=self.start_compression,
            cursor="hand2",
            background=ACCENT,
            foreground="white",
            activebackground=ACCENT_DARK,
            activeforeground="white",
            relief="flat",
            padx=22,
            pady=10,
            font=("Segoe UI Semibold", 11),
        )
        self.start_button.pack(side="left")
        self.open_button = tk.Button(
            action_row,
            text="Buka Folder Lokasi",
            command=self.open_output_folder,
            cursor="hand2",
            background=BACKGROUND,
            foreground=ACCENT_DARK,
            activebackground=BACKGROUND,
            activeforeground=ACCENT_DARK,
            relief="flat",
            font=("Segoe UI Semibold", 10),
            state="disabled",
        )
        self.open_button.pack(side="left", padx=(12, 0))

        self.progress = ttk.Progressbar(
            main,
            mode="indeterminate",
            style="Accent.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x", pady=(16, 0))
        self.progress.pack_forget()

        self.status_label = tk.Label(
            main,
            textvariable=self.status_text,
            background=BACKGROUND,
            foreground=MUTED,
            anchor="w",
            justify="left",
            font=("Segoe UI", 10),
        )
        self.status_label.pack(fill="x", pady=(14, 0))
        self._bind_responsive_wrap(main, self.status_label)

        self.result_label = tk.Label(
            main,
            textvariable=self.result_text,
            background=BACKGROUND,
            foreground=INK,
            anchor="w",
            justify="left",
            font=("Segoe UI", 10),
        )
        self.result_label.pack(fill="x", pady=(5, 0))
        self._bind_responsive_wrap(main, self.result_label)

    def _setup_dnd(self) -> None:
        if not HAS_DND or not hasattr(self.root, "drop_target_register"):
            return
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<DropEnter>>", self._on_drag_enter)
        self.root.dnd_bind("<<DropLeave>>", self._on_drag_leave)
        self.root.dnd_bind("<<Drop>>", self._on_drop)

    def _set_drop_highlight(self, active: bool) -> None:
        bg = DROP_HOVER if active else CARD
        border = ACCENT if active else "#D9E2EC"
        self.file_card.configure(background=bg, highlightbackground=border)
        for widget in (
            self.file_step_label,
            self.file_row,
            self.labels_frame,
            self.file_name_label,
            self.file_detail_label,
        ):
            widget.configure(background=bg)
        self.auto_drop_check.configure(background=bg, activebackground=bg)

    def _on_drag_enter(self, _event: tk.Event) -> None:
        if not self.is_busy:
            self._set_drop_highlight(True)

    def _on_drag_leave(self, _event: tk.Event) -> None:
        self._set_drop_highlight(False)

    def _on_drop(self, event: tk.Event) -> None:
        self._set_drop_highlight(False)
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

    def _load_selected_file(self, path: Path) -> None:
        self.selected_path = path
        self.file_text.set(self.selected_path.name)
        self.file_detail.set(f"Ukuran file asli: {format_bytes(self.selected_path.stat().st_size)}")
        self._clear_result()
        self.status_text.set("File siap, silakan pilih tingkat kompresi.")
        self.status_label.configure(foreground=MUTED)

    def choose_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="Pilih PDF yang akan dikompres",
            filetypes=[("File PDF", "*.pdf")],
        )
        if not selected:
            return
        self._load_selected_file(Path(selected))

    def start_compression(self) -> None:
        if self.selected_path is None:
            self._show_error("Silakan pilih atau seret file PDF terlebih dahulu.")
            return
        source = self.selected_path
        level = self.level.get()
        self._set_busy(True)
        self.status_text.set("Sedang mengompres, harap tunggu…")
        self.status_label.configure(foreground=ACCENT_DARK)
        Thread(
            target=self._compress_worker,
            args=(source, level),
            daemon=True,
        ).start()

    def _compress_worker(self, source: Path, level: int) -> None:
        try:
            result = compress_pdf(source, level)
        except (CompressionError, ValueError) as error:
            self.root.after(0, lambda: self._show_error(str(error)))
        except Exception:
            self.root.after(0, lambda: self._show_error("Terjadi kesalahan saat kompresi, periksa file lalu coba lagi."))
        else:
            self.root.after(0, lambda: self._show_success(result))
        finally:
            self.root.after(0, lambda: self._set_busy(False))

    def _set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        state = "disabled" if busy else "normal"
        self.file_button.configure(state=state)
        self.start_button.configure(state=state)
        self.auto_drop_check.configure(state=state)
        for control in self.level_controls:
            control.configure(state=state)
        if busy:
            self.progress.pack(fill="x", pady=(16, 0))
            self.progress.start(10)
        else:
            self.progress.stop()
            self.progress.pack_forget()

    def _clear_result(self) -> None:
        self.output_path = None
        self.result_text.set("")
        self.open_button.configure(state="disabled")

    def _show_success(self, result: CompressionResult) -> None:
        self.output_path = result.output_path
        self.status_text.set("Kompresi selesai, file baru telah dibuat.")
        self.status_label.configure(foreground=SUCCESS)
        self.result_text.set(
            f"File asli: {format_bytes(result.input_bytes)}    "
            f"File baru: {format_bytes(result.output_bytes)}    "
            f"{format_ratio(result.input_bytes, result.output_bytes)}\n"
            f"Lokasi output: {result.output_path}"
        )
        self.open_button.configure(state="normal")

    def _show_error(self, message: str) -> None:
        self._clear_result()
        self.status_text.set(message)
        self.status_label.configure(foreground=DANGER)

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
