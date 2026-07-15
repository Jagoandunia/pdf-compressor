from __future__ import annotations

import subprocess
import tkinter as tk
from pathlib import Path
from threading import Thread
from tkinter import filedialog, ttk

from compressor import CompressionError, CompressionResult, compress_pdf

LEVEL_OPTIONS = (
    (1, "1 级 · 清晰优先", "200 DPI · JPEG 质量 85"),
    (2, "2 级 · 均衡推荐", "150 DPI · JPEG 质量 75"),
    (3, "3 级 · 体积优先", "110 DPI · JPEG 质量 65"),
)

BACKGROUND = "#F4F7FB"
CARD = "#FFFFFF"
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
        return "无法计算比例"
    percent = abs(output_bytes - input_bytes) / input_bytes * 100
    action = "缩小" if output_bytes <= input_bytes else "增大"
    return f"{action} {percent:.1f}%"


class PdfCompressorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.selected_path: Path | None = None
        self.output_path: Path | None = None
        self.level = tk.IntVar(value=2)
        self.file_text = tk.StringVar(value="尚未选择文件")
        self.file_detail = tk.StringVar(value="支持本地 PDF 文件")
        self.status_text = tk.StringVar(value="选择文件和压缩等级后开始处理。")
        self.result_text = tk.StringVar(value="")

        self.root.title("PDF 轻压")
        self.root.geometry("760x660")
        self.root.minsize(680, 620)
        self.root.configure(background=BACKGROUND)
        self._configure_style()
        self._build()

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

    def _build(self) -> None:
        main = tk.Frame(self.root, background=BACKGROUND)
        main.pack(fill="both", expand=True, padx=32, pady=26)

        tk.Label(
            main,
            text="PDF 轻压",
            background=BACKGROUND,
            foreground=INK,
            font=("Segoe UI Semibold", 26),
        ).pack(anchor="w")
        tk.Label(
            main,
            text="本地压缩 · 原文件不改写 · 自动生成新文件",
            background=BACKGROUND,
            foreground=MUTED,
            font=("Segoe UI", 11),
        ).pack(anchor="w", pady=(2, 18))

        file_card = self._card(main)
        file_card.pack(fill="x")
        tk.Label(
            file_card,
            text="① 选择 PDF 文件",
            background=CARD,
            foreground=INK,
            font=("Segoe UI Semibold", 12),
        ).pack(anchor="w")
        file_row = tk.Frame(file_card, background=CARD)
        file_row.pack(fill="x", pady=(12, 0))
        self.file_button = tk.Button(
            file_row,
            text="选择 PDF",
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
        self.file_button.pack(side="left")
        labels = tk.Frame(file_row, background=CARD)
        labels.pack(side="left", fill="x", expand=True, padx=(14, 0))
        tk.Label(
            labels,
            textvariable=self.file_text,
            background=CARD,
            foreground=INK,
            anchor="w",
            font=("Segoe UI Semibold", 10),
        ).pack(fill="x")
        tk.Label(
            labels,
            textvariable=self.file_detail,
            background=CARD,
            foreground=MUTED,
            anchor="w",
            font=("Segoe UI", 9),
        ).pack(fill="x", pady=(2, 0))

        level_card = self._card(main)
        level_card.pack(fill="x", pady=(14, 0))
        tk.Label(
            level_card,
            text="② 选择压缩等级",
            background=CARD,
            foreground=INK,
            font=("Segoe UI Semibold", 12),
        ).pack(anchor="w")
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
            level_row.grid_columnconfigure(index, weight=1)
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
            )
            control.pack(anchor="w")
            tk.Label(
                item,
                text=detail,
                background="#F8FAFD",
                foreground=MUTED,
                font=("Segoe UI", 8),
            ).pack(anchor="w", padx=(25, 0), pady=(3, 0))
            self.level_controls.append(control)

        notice = self._card(main, background=NOTICE)
        notice.pack(fill="x", pady=(14, 0))
        tk.Label(
            notice,
            text="说明：输出会转换为图片 PDF，文字将无法再搜索、复制或编辑。",
            background=NOTICE,
            foreground=NOTICE_INK,
            font=("Segoe UI", 10),
            justify="left",
            wraplength=650,
        ).pack(anchor="w")

        action_row = tk.Frame(main, background=BACKGROUND)
        action_row.pack(fill="x", pady=(18, 0))
        self.start_button = tk.Button(
            action_row,
            text="开始压缩",
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
            text="打开所在文件夹",
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
            font=("Segoe UI", 10),
        )
        self.status_label.pack(fill="x", pady=(14, 0))
        self.result_label = tk.Label(
            main,
            textvariable=self.result_text,
            background=BACKGROUND,
            foreground=INK,
            anchor="w",
            justify="left",
            wraplength=675,
            font=("Segoe UI", 10),
        )
        self.result_label.pack(fill="x", pady=(5, 0))

    def choose_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="选择要压缩的 PDF",
            filetypes=[("PDF 文件", "*.pdf")],
        )
        if not selected:
            return
        self.selected_path = Path(selected)
        self.file_text.set(self.selected_path.name)
        self.file_detail.set(f"原文件大小：{format_bytes(self.selected_path.stat().st_size)}")
        self._clear_result()
        self.status_text.set("文件已准备好，请选择压缩等级。")
        self.status_label.configure(foreground=MUTED)

    def start_compression(self) -> None:
        if self.selected_path is None:
            self._show_error("请先选择一个 PDF 文件。")
            return
        source = self.selected_path
        level = self.level.get()
        self._set_busy(True)
        self.status_text.set("正在压缩，请稍候…")
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
            self.root.after(0, lambda: self._show_error("压缩异常，请检查文件后重试。"))
        else:
            self.root.after(0, lambda: self._show_success(result))
        finally:
            self.root.after(0, lambda: self._set_busy(False))

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.file_button.configure(state=state)
        self.start_button.configure(state=state)
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
        self.status_text.set("压缩完成，已生成新文件。")
        self.status_label.configure(foreground=SUCCESS)
        self.result_text.set(
            f"原文件：{format_bytes(result.input_bytes)}    "
            f"新文件：{format_bytes(result.output_bytes)}    "
            f"{format_ratio(result.input_bytes, result.output_bytes)}\n"
            f"输出位置：{result.output_path}"
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
    root = tk.Tk()
    PdfCompressorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

