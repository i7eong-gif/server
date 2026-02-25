# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules
from pathlib import Path

project_root = Path(os.getcwd())
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / 'tickers' / 'kr.json'), 'tickers'),
	    (str(project_root / 'tray.ico'), '.'),
        (str(project_root / 'icon.ico'), '.'),
    ],
    hiddenimports=[
        'pytz',
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'tkinter',
        'tkinter.ttk',
        'concurrent.futures',
    ] + collect_submodules('win11toast'),
    excludes=[
        'tkinter.test',
        'pytest',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Postock',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(project_root / 'icon.ico'),
)
