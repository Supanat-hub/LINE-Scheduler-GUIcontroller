# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Specification File for LINE Scheduler
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# หา Root Directory ของโปรเจกต์
SPEC_DIR = Path(SPECPATH).resolve()
ROOT_DIR = SPEC_DIR.parent if SPEC_DIR.name == "installer" else SPEC_DIR

# รวบรวม assets และ theme json files ทั้งหมดของ CustomTkinter
ctk_datas = collect_data_files('customtkinter')

# เพิ่มไอคอนและ assets ของโปรเจกต์
project_datas = [
    (str(ROOT_DIR / 'assets'), 'assets')
] + ctk_datas

a = Analysis(
    [str(ROOT_DIR / 'app' / 'main.py')],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=project_datas,
    hiddenimports=[
        'customtkinter',
        'pywinauto',
        'pywinauto.backend',
        'pywinauto.controls.uia_controls',
        'pywinauto.controls.uiawrapper',
        'pyautogui',
        'pyperclip',
        'pystray',
        'pystray._win32',
        'apscheduler',
        'apscheduler.triggers.cron',
        'apscheduler.triggers.date',
        'apscheduler.triggers.interval',
        'apscheduler.schedulers.background',
        'PIL',
        'PIL.ImageGrab',
        'win32service',
        'win32gui',
        'win32process',
        'win32con',
        'win32api',
        'sqlite3',
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
    name='LineScheduler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # ไม่แสดงหน้าต่าง Console สีดำ
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT_DIR / 'assets' / 'icon.ico')
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LineScheduler',
)
