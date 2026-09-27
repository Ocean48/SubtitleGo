# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all, copy_metadata

block_cipher = None

# Project paths
project_dir = os.path.abspath(SPECPATH)
src_dir = os.path.join(project_dir, 'src')

# Environment variable controlling whether to statically bundle AI weights/runtime or keep lean
bundle_ai_runtime = os.environ.get("SUBTITLEGO_BUNDLE_AI", os.environ.get("SUBTITLE_STUDIO_BUNDLE_AI", "0")) == "1"

datas = []
binaries = []
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'psutil',
    'requests',
    'urllib3',
    # Standard library modules required by dynamic runtime, PyTorch & transformers
    'unittest',
    'unittest.mock',
    'unittest.case',
    'unittest.suite',
    'unittest.loader',
    'unittest.main',
    'unittest.result',
    'unittest.runner',
    'unittest.signals',
    'unittest.util',
    'tracemalloc',
    'cProfile',
    'profile',
    'pstats',
    'timeit',
    'pdb',
    'bdb',
    'cmd',
    'code',
    'codeop',
    'doctest',
    'pydoc',
    'linecache',
    'shlex',
    'configparser',
    'optparse',
    'argparse',
    'opcode',
    'filecmp',
    'difflib',
    'unicodedata',
    'inspect',
    'csv',
    'tarfile',
    'zipfile',
    'lzma',
    'bz2',
    'gzip',
    'pathlib',
    'dataclasses',
    'uuid',
    'platform',
    'socket',
    'ssl',
    'hmac',
    'hashlib',
    'base64',
    'typing_extensions',
    'copy',
    'tempfile',
    'shutil',
    'subprocess',
    'glob',
    'fnmatch',
    'webbrowser',
    'mimetypes',
    'numbers',
    'cmath',
    'decimal',
    'fractions',
    'secrets',
    'contextlib',
    'functools',
    'itertools',
    'collections',
    'collections.abc',
    'operator',
    'reprlib',
    'enum',
    'types',
    'weakref',
    'pickle',
    'shelve',
    'marshal',
    'queue',
    'threading',
    'traceback',
    'warnings',
    'gc',
    'sysconfig',
    'site',
    'pkgutil',
    'struct',
    'codecs',
    'dis',
    'token',
    'tokenize',
    'ast',
    'symtable',
    'ensurepip',
    'venv',
]

# Collect all submodules for complex standard library packages
stdlib_pkgs_to_collect = [
    'unittest',
    'multiprocessing',
    'concurrent',
    'asyncio',
    'logging',
    'urllib',
    'http',
    'email',
    'xml',
    'xmlrpc',
    'importlib',
    'ctypes',
    'sqlite3',
    'json',
]
for std_pkg in stdlib_pkgs_to_collect:
    try:
        hiddenimports.extend(collect_submodules(std_pkg))
    except Exception as e:
        print(f"Notice: collect_submodules for {std_pkg}: {e}")

# Include bin folder (FFmpeg executables) if present
bin_folder = os.path.join(project_dir, 'bin')
if os.path.exists(bin_folder):
    datas.append(('bin', 'bin'))

# Bundle Python C API headers if present (required for Triton / C-extension JIT on Linux CUDA)
import sysconfig
py_inc = sysconfig.get_path('include')
py_ver_tag = f"python{sys.version_info.major}.{sys.version_info.minor}"
if py_inc and os.path.isdir(py_inc):
    datas.append((py_inc, f"include/{py_ver_tag}"))
    datas.append((py_inc, f"_internal/include/{py_ver_tag}"))
plat_inc = sysconfig.get_path('platinclude')
if plat_inc and os.path.isdir(plat_inc) and plat_inc != py_inc:
    datas.append((plat_inc, f"include/{py_ver_tag}"))
    datas.append((plat_inc, f"_internal/include/{py_ver_tag}"))

excludes = ['tkinter', 'matplotlib', 'IPython', 'notebook', 'pytest']

if bundle_ai_runtime:
    # Full offline packaging mode
    packages_for_metadata = [
        'transformers', 'qwen_asr', 'nagisa', 'soynlp', 'huggingface_hub',
        'torch', 'torchaudio', 'safetensors', 'tokenizers', 'accelerate',
        'tqdm', 'regex', 'requests', 'packaging', 'filelock', 'scipy',
        'soundfile', 'librosa', 'psutil', 'numpy'
    ]
    for pkg in packages_for_metadata:
        try:
            datas.extend(copy_metadata(pkg))
        except Exception as e:
            print(f"Warning: could not copy metadata for {pkg}: {e}")

    packages_to_collect = [
        'transformers', 'qwen_asr', 'nagisa', 'soynlp', 'accelerate',
        'huggingface_hub', 'tokenizers', 'safetensors', 'soundfile',
        'librosa', 'scipy', 'torch', 'torchaudio'
    ]
    for pkg in packages_to_collect:
        try:
            pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
            datas.extend(pkg_datas)
            binaries.extend(pkg_binaries)
            hiddenimports.extend(pkg_hidden)
        except Exception as e:
            print(f"Warning: collect_all failed for {pkg}: {e}")
else:
    # Lightweight dynamic setup mode (Default): exclude heavy AI libraries from PyInstaller bundle
    excludes.extend([
        'torch',
        'torchaudio',
        'transformers',
        'accelerate',
        'qwen_asr',
        'scipy',
        'librosa',
        'soundfile',
        'safetensors',
        'tokenizers',
        'nagisa',
        'soynlp',
    ])

runtime_hooks = []
rth_nagisa = os.path.join(project_dir, 'pyi_rth_nagisa.py')
if os.path.exists(rth_nagisa) and bundle_ai_runtime:
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
    excludes=excludes,
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
    name='SubtitleGo',
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
    name='SubtitleGo',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='SubtitleGo.app',
        icon=None,
        bundle_identifier='com.subtitlego.app',
        info_plist={
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleVersion': '1.0.0',
            'NSHighResolutionCapable': 'True',
        },
    )
