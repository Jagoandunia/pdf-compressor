param(
    [Parameter(Mandatory)]
    [string]$InputPdf
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv-build\Scripts\python.exe"
$artifactRoot = Join-Path $projectRoot "artifacts\verification"
$inputPath = (Resolve-Path $InputPdf).Path

if (-not (Test-Path $python)) {
    throw "Project virtual environment not found. Run scripts/build.ps1 first."
}
if ([IO.Path]::GetExtension($inputPath) -ne ".pdf") {
    throw "The input file must be a PDF."
}

New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null
$verificationInput = Join-Path $artifactRoot "input.pdf"
Copy-Item -LiteralPath $inputPath -Destination $verificationInput -Force

$env:PYTHONPATH = Join-Path $projectRoot "src"
$pythonScript = @"
from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz

from compressor import compress_pdf

source = Path(sys.argv[1])
result_file = Path(sys.argv[2])
items = []
for level in (1, 2, 3):
    result = compress_pdf(source, level)
    with fitz.open(result.output_path) as document:
        page_count = document.page_count
    if not result.output_path.is_file() or result.output_bytes <= 0:
        raise RuntimeError(f"Level {level} did not generate a valid output.")
    items.append(
        {
            "level": level,
            "input_bytes": result.input_bytes,
            "output_bytes": result.output_bytes,
            "page_count": page_count,
            "output": str(result.output_path),
        }
    )
result_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
print(result_file)
"@

$verifierScript = Join-Path $artifactRoot "verify_pdf.py"
Set-Content -LiteralPath $verifierScript -Value $pythonScript -Encoding utf8

& $python $verifierScript $verificationInput (Join-Path $artifactRoot "results.json")
if ($LASTEXITCODE -ne 0) {
    throw "Three-level compression verification failed."
}

Get-Content -Raw (Join-Path $artifactRoot "results.json")
