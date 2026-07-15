# PDF 轻压

一个简单的 Windows PDF 压缩工具。选择一个本地 PDF、选择 1–3 级压缩，程序会在原文件同目录生成新文件，原文件不会被改写。

## 使用

1. 打开发布目录中的 PDF压缩工具.exe。
2. 点击“选择 PDF”。
3. 选择压缩等级：
   - 1 级：清晰优先（200 DPI，JPEG 质量 85）
   - 2 级：均衡推荐（150 DPI，JPEG 质量 75）
   - 3 级：体积优先（110 DPI，JPEG 质量 65）
4. 点击“开始压缩”。
5. 程序生成 原文件名_压缩_L等级.pdf。若同名文件已存在，会自动生成 (2)、(3) 等新文件。

## 重要限制

为了稳定压缩扫描件和图片型 PDF，输出会重新生成为图片 PDF：

- 文本无法再搜索、复制或编辑。
- 超链接、表单、书签、附件和原始矢量内容不会保留。
- 已经高度优化的 PDF 不保证变小；界面会显示实际大小和比例。
- 受密码保护、损坏或格式异常的 PDF 暂不支持。

## 构建

需要 Windows、Python 3.13 和网络访问（或预备好的离线 wheel）。构建脚本会使用独立的 `.venv-build` 环境。

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
~~~

如果已在 wheelhouse/ 放置依赖 wheel，可离线构建：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1 -Offline
~~~

构建产物：dist/PDF压缩工具/PDF压缩工具.exe。

## 验证三档压缩

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1 -InputPdf <本地PDF路径>
~~~

验证结果写到 artifacts/verification/results.json，不会修改传入的源文件。
