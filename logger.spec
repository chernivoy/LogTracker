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

# One-file збірка: бінарники + дані вкладені прямо в EXE (без COLLECT),
# тож на виході один самодостатній dist/logger.exe. У рантаймі PyInstaller
# розпаковує все у %TEMP%\_MEIxxxxx і ставить туди sys._MEIPASS — сідування
# конфігів (PathUtils.user_config_path) і resource_path працюють без змін.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='logger',
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
    icon=os.path.join('src', 'app_icon.ico'),
)
