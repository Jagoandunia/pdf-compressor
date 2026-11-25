# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src/app.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter', 'unittest', 'pydoc', 'doctest', 'sqlite3',
        'PyQt6.QtNetwork', 'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtSql',
        'PyQt6.QtMultimedia', 'PyQt6.QtBluetooth', 'PyQt6.QtNfc',
        'PyQt6.QtPositioning', 'PyQt6.QtSensors', 'PyQt6.QtSerialPort',
        'PyQt6.QtTest', 'PyQt6.QtXml', 'PyQt6.QtDBus', 'PyQt6.QtDesigner',
        'PyQt6.QtHelp', 'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets',
        'PyQt6.QtPdf', 'PyQt6.QtPdfWidgets', 'PyQt6.QtPrintSupport',
        'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets',
    ],
    noarchive=False,
)

# Hapus DLL berat milik Qt6 yang tidak terpakai oleh aplikasi
UNUSED_BINARIES = (
    'opengl32sw.dll',
    'd3dcompiler_47.dll',
    'qt6network.dll',
    'qt6svg.dll',
    'qt6pdf.dll',
    'qt6qml',
    'qt6quick',
    'qt6sql.dll',
    'qt6opengl.dll',
    'qt6printsupport.dll',
    'qsvg.dll',
    'qwebp.dll',
    'qtiff.dll',
    'qgif.dll',
    'qjpeg.dll',
)

a.binaries = [
    b for b in a.binaries
    if not any(tag in b[0].lower() for tag in UNUSED_BINARIES)
]

# Hapus paket bahasa bawaan Qt6 yang tidak diperlukan
a.datas = [
    d for d in a.datas
    if 'qt6\\translations' not in d[0].lower()
    and 'qt6/translations' not in d[0].lower()
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Kompresor-PDF-Ringan',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
