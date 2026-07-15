param(
    [switch]$Offline
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPath = Join-Path $projectRoot ".venv-build"
$python = Join-Path $venvPath "Scripts\python.exe"
$distPath = Join-Path $projectRoot "dist"
$workPath = Join-Path $projectRoot "build"
$specPath = Join-Path $projectRoot "pyinstaller"
$applicationName = "PDF$([char]0x538B)$([char]0x7F29)$([char]0x5DE5)$([char]0x5177)"
$application = Join-Path $distPath "$applicationName\$applicationName.exe"

if (-not (Test-Path $python)) {
    & py -3.13 -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.13 is required to build this application."
    }
}

$installArguments = @("-m", "pip", "install")
if ($Offline) {
    $wheelhouse = Join-Path $projectRoot "wheelhouse"
    if (-not (Test-Path $wheelhouse)) {
        throw "Offline build requires the wheelhouse directory."
    }
    $installArguments += @("--no-index", "--find-links", $wheelhouse)
}
$installArguments += @(
    "-r", (Join-Path $projectRoot "requirements.txt"),
    "-r", (Join-Path $projectRoot "requirements-build.txt")
)
& $python @installArguments
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install build dependencies."
}

$pyInstallerArguments = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--onedir",
    "--name", $applicationName,
    "--paths", (Join-Path $projectRoot "src"),
    "--distpath", $distPath,
    "--workpath", $workPath,
    "--specpath", $specPath,
    (Join-Path $projectRoot "src\app.py")
)
& $python -m PyInstaller @pyInstallerArguments
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

if (-not (Test-Path $application)) {
    throw "The packaged executable was not found."
}

Write-Host "Build complete: $application"
