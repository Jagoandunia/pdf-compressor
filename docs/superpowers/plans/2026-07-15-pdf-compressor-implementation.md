# PDF 压缩工具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建可离线运行的 Windows PDF 压缩程序，支持选择本地文件和 1–3 级压缩并生成新文件。

**Architecture:** Tkinter 只负责窗口和线程调度；`compressor.py` 负责所有无 UI 的 PDF 校验、Ghostscript 命令、输出路径和结果验证。Ghostscript 作为发布目录中的私有运行时，通过子进程执行 `pdfwrite`，避免用户预装依赖。

**Tech Stack:** Python 3.10、标准库 Tkinter/unittest、Ghostscript 10.07.1、PyInstaller 6.x、PowerShell 5.1+。

## Global Constraints

- 仅支持一个本地 `.pdf` 文件，默认等级为 `2`；不做批处理、上传、解密、OCR 或原文件覆盖。
- 三档必须固定为：L1=200 DPI/JPEG 85，L2=150 DPI/JPEG 75，L3=110 DPI/JPEG 65；黑白图保持无损压缩。
- 输出必须为 `<原文件名>_压缩_L<等级>.pdf`，重名时追加 ` (2)`、` (3)`；失败不保留不完整文件。
- UI、日志和异常面向用户的文字全部使用中文。
- 发布目录必须包含 `PDF压缩工具.exe` 和运行所需 Ghostscript 文件，用户无需预装 Python 或 Ghostscript。
- Ghostscript 使用 GPL/AGPL 或商业许可证；发行目录必须包含许可与来源说明。

---

## 文件结构

| 路径 | 职责 |
| --- | --- |
| `src/runtime.py` | 找出开发/打包环境中的 Ghostscript 可执行文件。 |
| `src/compressor.py` | 压缩等级、路径生成、命令拼装、压缩、输出读取验证。 |
| `src/app.py` | Tkinter 单窗口、文件选择、后台压缩与结果展示。 |
| `tests/test_compressor.py` | 核心压缩模块的无 UI 单测。 |
| `tests/test_runtime.py` | 打包资源路径解析单测。 |
| `requirements-build.txt` | 仅列 PyInstaller 构建依赖。 |
| `scripts/build.ps1` | 创建 venv、准备 Ghostscript、打包发布目录。 |
| `scripts/verify.ps1` | 对真实 PDF 三档压缩并校验输出。 |
| `README.md` | 使用、构建、许可证和局限。 |
| `THIRD_PARTY_NOTICES.md` | Ghostscript 下载来源与许可证提示。 |

### Task 1: 核心压缩模块

**Files:**
- Create: `src/runtime.py`
- Create: `src/compressor.py`
- Create: `tests/test_compressor.py`
- Create: `tests/test_runtime.py`

**Interfaces:**
- Produces `CompressionProfile(level: int, label: str, resolution_dpi: int, jpeg_quality: int)`。
- Produces `CompressionResult(input_path: Path, output_path: Path, input_bytes: int, output_bytes: int, level: int)`。
- Produces `compress_pdf(input_path: Path, level: int, gs_executable: Path | None = None) -> CompressionResult`。
- Produces `ghostscript_executable() -> Path`。

- [ ] **Step 1: 写出等级、路径和命令的失败测试**

```python
def test_profile_uses_requested_quality_values():
    assert get_profile(1).resolution_dpi == 200
    assert get_profile(2).jpeg_quality == 75
    assert get_profile(3).resolution_dpi == 110

def test_unique_output_path_keeps_source_file(tmp_path):
    source = tmp_path / '资料.pdf'
    source.write_bytes(b'%PDF-1.4')
    first = make_output_path(source, 2)
    first.write_bytes(b'old')
    assert make_output_path(source, 2).name == '资料_压缩_L2 (2).pdf'

def test_command_uses_pdfwrite_and_profile(tmp_path):
    command = build_compress_command(Path('gswin64c.exe'), tmp_path/'in.pdf', tmp_path/'out.pdf', get_profile(3))
    assert '-sDEVICE=pdfwrite' in command
    assert '-dColorImageResolution=110' in command
    assert '-dJPEGQ=65' in command
```

- [ ] **Step 2: 运行测试，确认缺少模块时失败**

Run: `python -m unittest tests.test_compressor -v`

Expected: FAIL，提示 `ModuleNotFoundError: No module named 'compressor'`。

- [ ] **Step 3: 实现核心数据与命令构建**

```python
@dataclass(frozen=True)
class CompressionProfile:
    level: int
    label: str
    resolution_dpi: int
    jpeg_quality: int

PROFILES = {
    1: CompressionProfile(1, '清晰优先', 200, 85),
    2: CompressionProfile(2, '均衡推荐', 150, 75),
    3: CompressionProfile(3, '体积优先', 110, 65),
}

def get_profile(level: int) -> CompressionProfile:
    try:
        return PROFILES[level]
    except KeyError as error:
        raise ValueError('压缩等级只能是 1、2 或 3。') from error
```

`make_output_path` 使用 `Path.stem`、`Path.suffix` 与递增序号；`build_compress_command` 返回参数数组，至少包含 `-dSAFER`、`-dBATCH`、`-dNOPAUSE`、`-sDEVICE=pdfwrite`、彩色/灰度图片下采样与 JPEG 参数、`-sOutputFile=<输出>`、`<输入>`，不要拼接 shell 字符串。

- [ ] **Step 4: 运行核心测试**

Run: `python -m unittest tests.test_compressor -v`

Expected: 三个测试 PASS。

- [ ] **Step 5: 写出压缩失败清理和读取验证的失败测试**

```python
def test_failed_engine_removes_partial_output(self):
    source = self.make_pdf('in.pdf')
    output = self.temp_dir / 'in_压缩_L2.pdf'
    with patch('compressor.subprocess.run', fake_failed_run_creating(output)):
        with self.assertRaisesRegex(CompressionError, '压缩引擎执行失败'):
            compress_pdf(source, 2, Path('gswin64c.exe'))
    self.assertFalse(output.exists())
```

测试同时覆盖：非 `.pdf` 后缀拒绝、输入不存在、引擎路径不存在和验证命令失败。

- [ ] **Step 6: 实现执行、验证和运行时路径解析**

```python
def compress_pdf(input_path: Path, level: int, gs_executable: Path | None = None) -> CompressionResult:
    source = validate_source(input_path)
    engine = gs_executable or ghostscript_executable()
    output = make_output_path(source, level)
    try:
        run_checked(build_compress_command(engine, source, output, get_profile(level)))
        validate_output(engine, output)
        return CompressionResult(source, output, source.stat().st_size, output.stat().st_size, level)
    except Exception:
        output.unlink(missing_ok=True)
        raise
```

`runtime.py` 以 `Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))` 为根，查找 `runtime/ghostscript/bin/gswin64c.exe`；找不到时抛出“程序安装不完整，请重新解压完整发布目录”。`run_checked` 必须用 `subprocess.run(..., capture_output=True, text=True, encoding='utf-8', errors='replace', check=False)`，非零退出码抛中文 `CompressionError`，但不得向 UI 回显完整命令行。

- [ ] **Step 7: 运行完整核心测试**

Run: `python -m unittest discover -s tests -v`

Expected: 全部 PASS；临时目录中没有失败后残留的输出 PDF。

- [ ] **Step 8: 提交核心模块**

```powershell
git add src/runtime.py src/compressor.py tests/test_compressor.py tests/test_runtime.py
git commit -m 'feat: add PDF compression core'
```

### Task 2: 桌面交互界面

**Files:**
- Create: `src/app.py`
- Modify: `tests/test_compressor.py`（只在需要为 UI 提供纯函数格式化测试时修改）

**Interfaces:**
- Consumes `compress_pdf`, `CompressionResult`, `CompressionError`。
- Produces `PdfCompressorApp(root: tk.Tk)` 和入口 `main() -> None`。

- [ ] **Step 1: 写出不依赖窗口的格式化测试**

```python
def test_format_bytes_and_ratio_are_user_readable():
    assert format_bytes(1024) == '1.00 KB'
    assert format_ratio(1000, 750) == '缩小 25.0%'
    assert format_ratio(1000, 1200) == '增大 20.0%'
```

- [ ] **Step 2: 运行格式化测试，确认失败**

Run: `python -m unittest tests.test_compressor.PresentationTests -v`

Expected: FAIL，提示 `format_bytes` 未定义。

- [ ] **Step 3: 实现响应式中文单窗口**

```python
class PdfCompressorApp:
    def start_compression(self) -> None:
        if self.selected_path is None:
            self.show_error('请先选择一个 PDF 文件。')
            return
        self.set_busy(True, '正在压缩，请稍候…')
        Thread(target=self._compress_worker, daemon=True).start()

    def _compress_worker(self) -> None:
        try:
            result = compress_pdf(self.selected_path, self.level.get())
            self.root.after(0, lambda: self.show_success(result))
        except CompressionError as error:
            self.root.after(0, lambda: self.show_error(str(error)))
        finally:
            self.root.after(0, lambda: self.set_busy(False, ''))
```

窗口包含“选择 PDF”按钮、三个绑定到 `IntVar(value=2)` 的单选项、“开始压缩”按钮、状态文本、结果文本和初始隐藏的“打开所在文件夹”按钮。文件选择器限定 `('PDF 文件', '*.pdf')`；打开目录使用 `subprocess.run(['explorer.exe', '/select,', str(result.output_path)])`。后台期间禁用选择、等级与开始按钮，任何 UI 更新只经 `root.after`。

- [ ] **Step 4: 运行单测与语法检查**

Run: `python -m unittest discover -s tests -v; python -m py_compile src/app.py src/compressor.py src/runtime.py`

Expected: 单测 PASS，且没有语法错误。

- [ ] **Step 5: 手动检查窗口**

Run: `python src/app.py`

Expected: 显示中文窗口，默认选中 2 级；未选文件点击开始会提示“请先选择一个 PDF 文件”。

- [ ] **Step 6: 提交桌面界面**

```powershell
git add src/app.py tests/test_compressor.py
git commit -m 'feat: add Windows desktop interface'
```

### Task 3: 构建、运行时与文档

**Files:**
- Create: `requirements-build.txt`
- Create: `scripts/build.ps1`
- Create: `README.md`
- Create: `THIRD_PARTY_NOTICES.md`
- Modify: `src/runtime.py`

**Interfaces:**
- `scripts/build.ps1` 产出 `dist/PDF压缩工具/PDF压缩工具.exe`。
- 发行运行时目录为 `dist/PDF压缩工具/runtime/ghostscript/`。

- [ ] **Step 1: 添加构建依赖与发行说明**

```text
# requirements-build.txt
pyinstaller==6.16.0
```

`README.md` 明确说明使用步骤、输出命名、三档效果、已优化 PDF 可能变大、只支持不受密码保护的 PDF；`THIRD_PARTY_NOTICES.md` 写入 Ghostscript 官方下载页、版本 `10.07.1`、AGPL/GPL 或商业许可提醒和完整运行时随包分发要求。

- [ ] **Step 2: 实现可重复打包脚本**

```powershell
$venv = Join-Path $PSScriptRoot '..\.venv'
$python = Join-Path $venv 'Scripts\python.exe'
& python -m venv $venv
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $PSScriptRoot '..\requirements-build.txt')
```

脚本接收可选 `[string]$GhostscriptHome`。参数为空时从 `runtime/ghostscript` 或系统 `gswin64c.exe` 查找；找到后复制 `bin`、`lib`、`Resource`（若存在）和许可证到 `runtime/ghostscript`。在临时 `build` 目录调用：

```powershell
& $python -m PyInstaller --noconfirm --clean --windowed --name 'PDF压缩工具' `
  --add-data "$runtimeSource;runtime/ghostscript" `
  (Join-Path $PSScriptRoot '..\src\app.py')
```

脚本完成后断言 `dist/PDF压缩工具/PDF压缩工具.exe` 与 `dist/PDF压缩工具/runtime/ghostscript/bin/gswin64c.exe` 均存在，否则抛错。

- [ ] **Step 3: 运行构建并检查发布内容**

Run: `powershell -ExecutionPolicy Bypass -File scripts/build.ps1 -GhostscriptHome <本机 Ghostscript 根目录>`

Expected: 输出 `dist/PDF压缩工具/PDF压缩工具.exe`，并且运行时目录含 Ghostscript 可执行文件、DLL/库文件与许可证。

- [ ] **Step 4: 提交发行配置**

```powershell
git add requirements-build.txt scripts/build.ps1 README.md THIRD_PARTY_NOTICES.md src/runtime.py
git commit -m 'build: package standalone Windows application'
```

### Task 4: 端到端验证与交付检查

**Files:**
- Create: `scripts/verify.ps1`
- Modify: `README.md`（记录已验证的样本体积与运行方式）

**Interfaces:**
- `scripts/verify.ps1 -InputPdf <路径>` 依次运行 L1、L2、L3 并在 `artifacts/verification/` 留下输出与 `results.json`。

- [ ] **Step 1: 实现真实 PDF 验证脚本**

```powershell
param([Parameter(Mandatory)][string]$InputPdf)
$env:PYTHONPATH = (Resolve-Path "$PSScriptRoot\..\src")
& python -c "from pathlib import Path; from compressor import compress_pdf; import json; p=Path(r'$InputPdf'); print(json.dumps([{'level': i, 'output': str((r:=compress_pdf(p,i)).output_path), 'input_bytes': r.input_bytes, 'output_bytes': r.output_bytes} for i in (1,2,3)], ensure_ascii=False))"
if ($LASTEXITCODE -ne 0) { throw '三档压缩验证失败。' }
```

实际版本必须把 JSON 写到 `artifacts/verification/results.json`，并检查每个输出存在、非空、扩展名为 `.pdf`。

- [ ] **Step 2: 执行单测与三档真实压缩**

Run: `python -m unittest discover -s tests -v; powershell -ExecutionPolicy Bypass -File scripts/verify.ps1 -InputPdf <真实图片型PDF>`

Expected: 单测全绿；`results.json` 有三个不同等级条目，三个输出都存在且非空。

- [ ] **Step 3: 验证打包版运行时**

Run: `dist\PDF压缩工具\PDF压缩工具.exe`

Expected: 界面可以启动；使用同一 PDF、任一等级完成压缩并显示输出路径，发行目录外没有 Python 或系统 Ghostscript 依赖。

- [ ] **Step 4: 最终提交与状态检查**

```powershell
git add scripts/verify.ps1 README.md artifacts/verification/results.json
git commit -m 'test: verify PDF compression levels'
git status --short
```

Expected: 工作树干净；若 `artifacts` 体积过大，仅提交 `results.json`，不提交来源和压缩后的 PDF。

## 自检结果

- 覆盖范围：Task 1/2 实现选择、等级、压缩、错误与新文件；Task 3 负责无需预装运行时的发布目录和许可证；Task 4 以真实 PDF、三档和打包运行时证明交付。
- 占位检查：没有未填写的占位标记或“后续补充”步骤。
- 类型一致性：UI 只调用 `compress_pdf(Path, int)` 并消费 `CompressionResult`；所有 Ghostscript 路径由 `ghostscript_executable` 或显式注入的 `Path` 获取。
