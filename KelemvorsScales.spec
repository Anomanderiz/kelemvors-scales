# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:\\Downloads\\boss_balance_desktop_encounter_v3_resized.py'],
    pathex=[],
    binaries=[],
    datas=[('E:/Downloads/Untitled design (1).ico', '.')],
    hiddenimports=['numpy._core._exceptions'],
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
    a.binaries,
    a.datas,
    [],
    name="Kelemvor's Scales",
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
    icon=['E:\\Downloads\\Untitled design (1).ico'],
)
