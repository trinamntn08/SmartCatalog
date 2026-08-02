# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all


pymupdf_datas, pymupdf_binaries, pymupdf_hiddenimports = collect_all("pymupdf")
fitz_datas, fitz_binaries, fitz_hiddenimports = collect_all("fitz")

# PyMuPDF publishes C/C++ development headers as package data. They are not
# needed at runtime and add several megabytes to the client distribution.
pymupdf_datas = [
    item for item in pymupdf_datas
    if "mupdf-devel" not in item[0].replace("\\", "/")
]

datas = [
    ("icons/icon.ico", "icons"),
    ("icons/bg.jpg", "icons"),
]
datas += pymupdf_datas + fitz_datas

binaries = pymupdf_binaries + fitz_binaries

hiddenimports = sorted(
    set(
        pymupdf_hiddenimports
        + fitz_hiddenimports
        + [
            "fitz",
            "pymupdf",
            "PIL._tkinter_finder",
            "openpyxl",
            "openpyxl.drawing.image",
            "openpyxl.drawing.spreadsheet_drawing",
        ]
    )
)


a = Analysis(
    ["run.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "IPython",
        "matplotlib",
        "notebook",
        "pytest",
        "scipy",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SmartCatalog",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icons/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SmartCatalog",
)
