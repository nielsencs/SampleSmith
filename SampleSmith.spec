# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build recipe for SampleSmith."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path.cwd()

asset_datas = [
    (str(path), str(Path("samplesmith_app") / "assets"))
    for path in (ROOT / "samplesmith_app" / "assets").iterdir()
]

# librosa uses package data in some dependency paths; keep PyInstaller explicit.
datas = asset_datas + collect_data_files("librosa")


a = Analysis(
    ["samplesmith.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SampleSmith",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SampleSmith",
)
