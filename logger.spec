# logger.spec

# -*- mode: python ; coding: utf-8 -*-

import glob
import os

# Пакуємо всю теку src (іконки + ini) — шляхи резолвляться через
# PathUtils.resource_path(os.path.join("src", ...)), тому цільова тека саме 'src'.
src_datas = [(f, 'src') for f in glob.glob(os.path.join('src', '*')) if os.path.isfile(f)]

# Теми вантажаться динамічно (ThemeManager.load_theme → importlib.import_module),
# тому статичний аналіз PyInstaller їх не бачить — перелічуємо явно.
theme_imports = [
    'themes.' + os.path.splitext(os.path.basename(f))[0]
    for f in glob.glob(os.path.join('themes', '*_theme.py'))
]

a = Analysis(
    ['logger.py'],
    pathex=['.'],
    binaries=[],
    datas=src_datas,
    hiddenimports=theme_imports,
    hookspath=[],
    runtime_hooks=['rthook_logfile.py'],
    excludes=[],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='logger',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=os.path.join('src', 'Header.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='logger'
)
