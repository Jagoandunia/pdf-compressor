# PDF 压缩工具 Implementation Plan（修订版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 制作一个无需用户预装依赖的 Windows PDF 压缩工具，支持本地选择 PDF 和 1–3 级压缩后生成新文件。

**Architecture:** 使用 PyMuPDF 在内存中逐页渲染 PDF，并以不同 DPI/JPEG 质量重新组成图片 PDF；Tkinter 只承担交互和后台任务调度。PyInstaller 将 Python 与 PyMuPDF 组成单个 onedir 发布目录。

**Tech Stack:** Python 3.10、PyMuPDF 1.26.7、Tkinter、unittest、PyInstaller 6.16.0、PowerShell 5.1+。

## Global Constraints

- 默认 2 级；L1=200 DPI/JPEG 85、L2=150 DPI/JPEG 75、L3=110 DPI/JPEG 65。
- 新文件命名不得覆盖原文件；处理失败必须删除本次输出。
- 输出是图片 PDF，文本搜索、表单、链接、书签和可编辑内容不保留；UI 与 README 必须明确说明。
- 发行目录不依赖 Ghostscript、Python 安装或管理员权限。
- PyMuPDF 使用 AGPL-3.0 或商业许可，发行中须保留第三方说明。

---

### Task 1: 以 PyMuPDF 实现并验证压缩核心

**Files:**
- Modify: `src/compressor.py`
- Delete: `src/runtime.py`
- Modify: `tests/test_compressor.py`
- Delete: `tests/test_runtime.py`
- Create: `requirements.txt`

**Interfaces:**
- `compress_pdf(input_path: Path, level: int) -> CompressionResult`
- `CompressionResult(input_path: Path, output_path: Path, input_bytes: int, output_bytes: int, level: int, page_count: int)`
- `get_profile(level: int) -> CompressionProfile`
- `make_output_path(input_path: Path, level: int) -> Path`

- [ ] 写一个使用 PyMuPDF 创建两页样本 PDF 的测试；调用 `compress_pdf(sample, 1)` 后断言输出存在、非空、页数为 2、可重新打开。
- [ ] 运行该测试并确认它因当前 Ghostscript 参数或函数签名不匹配而失败。
- [ ] 只实现使该测试通过的渲染循环：`fitz.open(input)`、`page.get_pixmap(dpi=profile.resolution_dpi, alpha=False)`、`pix.tobytes('jpeg', jpg_quality=profile.jpeg_quality)`、`new_page.insert_image(new_page.rect, stream=jpeg)`、`output.save(...)`。
- [ ] 为输出页数不一致、打开失败和密码 PDF 写失败测试；实现中文 `CompressionError` 和不完整输出清理。
- [ ] 运行 `python -m unittest discover -s tests -v`，预期全部通过。
- [ ] 提交：`git add src/compressor.py tests/test_compressor.py requirements.txt; git rm src/runtime.py tests/test_runtime.py; git commit -m 'feat: use embedded PDF compression engine'`。

### Task 2: 建立桌面界面

**Files:**
- Create: `src/app.py`
- Modify: `tests/test_compressor.py`

**Interfaces:**
- `PdfCompressorApp(root: tk.Tk)`
- `format_bytes(size: int) -> str`
- `format_ratio(input_bytes: int, output_bytes: int) -> str`

- [ ] 先写 `format_bytes(1024) == '1.00 KB'`、缩小/增大比例格式化测试，运行确认失败。
- [ ] 实现格式化函数并让测试通过。
- [ ] 实现窗口：PDF 文件选择、三档单选、图片化压缩提示、后台线程、处理时禁用控件、中文错误、结果大小和打开输出目录。
- [ ] 运行单测与 `python -m py_compile src/app.py src/compressor.py`；手动启动界面验证默认选中 2 级和未选文件提示。
- [ ] 提交：`git add src/app.py tests/test_compressor.py; git commit -m 'feat: add PDF compressor desktop interface'`。

### Task 3: 打包、真实验证与交付

**Files:**
- Create: `requirements-build.txt`
- Create: `scripts/build.ps1`
- Create: `scripts/verify.ps1`
- Create: `README.md`
- Create: `THIRD_PARTY_NOTICES.md`

**Interfaces:**
- `scripts/build.ps1` 输出 `dist/PDF压缩工具/PDF压缩工具.exe`。
- `scripts/verify.ps1 -InputPdf <path>` 输出 `artifacts/verification/results.json`。

- [ ] 构建脚本创建 `.venv`、安装 `requirements.txt` 和 `requirements-build.txt`，调用 `PyInstaller --onedir --windowed --name 'PDF压缩工具' src/app.py`，并断言 EXE 存在。
- [ ] 验证脚本对真实样本运行 L1/L2/L3，写入源/输出体积和页数，并重新打开每个输出。
- [ ] README 说明使用方式、输出命名、图片化限制和无管理员依赖；第三方文件说明 PyMuPDF 1.26.7 的 AGPL/商业许可。
- [ ] 运行 `python -m unittest discover -s tests -v`、三档真实验证和打包版启动检查。
- [ ] 提交：`git add requirements.txt requirements-build.txt scripts README.md THIRD_PARTY_NOTICES.md; git commit -m 'build: package standalone PDF compressor'`。

## 自检

- 三档压缩、选择本地文件、生成新文件、错误清理、输出可读和无用户依赖均有对应实现和验证任务。
- 不使用外置 Ghostscript，避免管理员权限与运行时缺失。
