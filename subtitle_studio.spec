# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all, copy_metadata

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
    'transformers.models',
    'transformers.models.auto',
    'transformers.models.whisper',
    'transformers.models.qwen2',
    'transformers.models.qwen2_audio',
    'transformers.processing_utils',
    'transformers.feature_extraction_utils',
    'transformers.tokenization_utils',
    'transformers.tokenization_utils_fast',
    'transformers.audio_utils',
    'transformers.image_processing_utils',
    'accelerate',
    'qwen_asr',
    'qwen_asr.core',
    'qwen_asr.core.transformers_backend',
    'qwen_asr.inference',
    'qwen_asr.inference.qwen3_asr',
    'qwen_asr.inference.qwen3_forced_aligner',
    'qwen_asr.inference.utils',
    'nagisa',
    'nagisa.prepro',
    'nagisa.model',
    'nagisa.mecab_system_eval',
    'nagisa.tagger',
    'nagisa.train',
    'nagisa_utils',
    'soynlp',
    'soynlp.tokenizer',
    'soynlp.normalizer',
    'soynlp.hangle',
    'soundfile',
    'librosa',
    'scipy',
    'scipy.signal',
    'scipy.io',
    'scipy.io.wavfile',
    'huggingface_hub',
    'tokenizers',
    'safetensors',
    'safetensors.torch',
    'psutil',
]

# Include bin folder (FFmpeg executables) if present
bin_folder = os.path.join(project_dir, 'bin')
if os.path.exists(bin_folder):
    datas.append(('bin', 'bin'))

# Collect package distribution metadata for dynamic entry-point and version discovery
packages_for_metadata = [
    'transformers',
    'qwen_asr',
    'nagisa',
    'soynlp',
    'huggingface_hub',
    'torch',
    'torchaudio',
    'safetensors',
    'tokenizers',
    'accelerate',
    'tqdm',
    'regex',
    'requests',
    'packaging',
    'filelock',
    'scipy',
    'soundfile',
    'librosa',
    'psutil',
    'numpy',
]

for pkg in packages_for_metadata:
    try:
        datas.extend(copy_metadata(pkg))
    except Exception as e:
        print(f"Warning: could not copy metadata for {pkg}: {e}")

# Collect data, binaries, and hidden submodules for dynamic AI and audio packages
packages_to_collect = [
    'transformers',
    'qwen_asr',
    'nagisa',
    'soynlp',
    'accelerate',
    'huggingface_hub',
    'tokenizers',
    'safetensors',
    'soundfile',
    'librosa',
    'scipy',
    'torch',
    'torchaudio',
]

for pkg in packages_to_collect:
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas.extend(pkg_datas)
        binaries.extend(pkg_binaries)
        hiddenimports.extend(pkg_hidden)
    except Exception as e:
        print(f"Warning: collect_all failed for {pkg}: {e}")

runtime_hooks = []
rth_nagisa = os.path.join(project_dir, 'pyi_rth_nagisa.py')
if os.path.exists(rth_nagisa):
    runtime_hooks.append(rth_nagisa)

a = Analysis(
    [os.path.join(src_dir, 'main.py')],
    pathex=[project_dir, src_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=list(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
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
