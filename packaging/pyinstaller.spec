# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — PaddleOCR macOS 桌面应用
# 用法: pyinstaller packaging/pyinstaller.spec

import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "resources"), "resources"),
    ],
    hiddenimports=[
        "paddleocr",
        "paddle",
        "PySide6",
        "fitz",
        "docx",
        "openpyxl",
        "reportlab",
        "lxml",
        "PIL",
        "cv2",
        "numpy",
        "yaml",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PaddleOCR",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=str(ROOT / "packaging" / "entitlements.plist"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PaddleOCR",
)

app = BUNDLE(
    coll,
    name="PaddleOCR.app",
    icon=None,  # TODO: 添加 .icns 图标
    bundle_identifier="com.paddleocr.desktop",
    info_plist={
        "CFBundleDisplayName": "PaddleOCR",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
    },
)
