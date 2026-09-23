# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all

block_cipher = None

# Project paths
project_dir = os.path.abspath(SPECPATH)
src_dir = os.path.join(project_dir, 'src')

# Collect all resources and submodules for heavy libraries
datas = []
binaries = []
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'torch',
    'torchaudio',
    'transformers',
    'accelerate',
    'qwen_asr',
    'soundfile',
    'librosa',
    'huggingface_hub',
]

# Include bin folder (FFmpeg executables) if present
bin_folder = os.path.join(project_dir, 'bin')
if os.path.exists(bin_folder):
    datas.append(('bin', 'bin'))

# Collect data and submodules for dynamic AI libraries
for pkg in ['transformers', 'qwen_asr', 'accelerate', 'huggingface_hub']:
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas.extend(pkg_datas)
        binaries.extend(pkg_binaries)
        hiddenimports.extend(pkg_hidden)
    except Exception:
        pass

# Ensure torch and torchaudio dependencies are gathered
try:
    torch_datas, torch_binaries, torch_hidden = collect_all('torch')
    datas.extend(torch_datas)
    binaries.extend(torch_binaries)
    hiddenimports.extend(torch_hidden)
except Exception:
    pass

try:
    ta_datas, ta_binaries, ta_hidden = collect_all('torchaudio')
    datas.extend(ta_datas)
    binaries.extend(ta_binaries)
    hiddenimports.extend(ta_hidden)
except Exception:
    pass

a = Analysis(
    [os.path.join(src_dir, 'main.py')],
    pathex=[project_dir, src_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=list(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'IPython', 'notebook', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SubtitleStudio',
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SubtitleStudio',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='SubtitleStudio.app',
        icon=None,
        bundle_identifier='com.subtitlego.app',
        info_plist={
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleVersion': '1.0.0',
            'NSHighResolutionCapable': 'True',
        },
    )
