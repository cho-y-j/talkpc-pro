# -*- mode: python ; coding: utf-8 -*-
# TalkPC Pro 빌드 spec — talk-local TalkPC-Local.spec 기반 + auth/ui 추가

from PyInstaller.utils.hooks import (
    collect_submodules, collect_data_files, collect_dynamic_libs, copy_metadata
)


def _safe_collect_submodules(pkg, exclude_prefixes=()):
    try:
        mods = collect_submodules(pkg)
    except Exception:
        return [pkg]
    return [m for m in mods
            if not any(m == p or m.startswith(p + '.') for p in exclude_prefixes)]


paddle_excludes = ['paddle.jit.sot']
paddle_hiddens = _safe_collect_submodules('paddle', paddle_excludes)
paddle_datas = collect_data_files('paddle', include_py_files=True)
paddle_binaries = collect_dynamic_libs('paddle')

ocr_hiddens = _safe_collect_submodules('paddleocr')
ocr_datas = collect_data_files('paddleocr', include_py_files=True)
ocr_binaries = collect_dynamic_libs('paddleocr')

PADDLEOCR_RUNTIME_DEPS = [
    'imghdr',
    'skimage', 'skimage.morphology', 'skimage.morphology._skeletonize',
    'scipy', 'scipy.io', 'scipy.special', 'scipy.signal', 'scipy.ndimage',
    'scipy.spatial', 'scipy.sparse', 'scipy.linalg', 'scipy.optimize',
    'scipy.cluster', 'scipy.stats', 'scipy.interpolate',
    'imageio', 'imgaug', 'imgaug.augmenters', 'lazy_loader',
    'astor', 'tqdm', 'rich', 'click', 'colorama', 'pygments',
    'requests', 'urllib3', 'idna', 'certifi', 'chardet', 'charset_normalizer',
    'httpx', 'httpcore', 'h11', 'anyio', 'sniffio',
    'six', 'decorator', 'opt_einsum', 'typing_extensions', 'packaging',
    'shapely', 'shapely.geometry', 'pyclipper', 'lmdb', 'rapidfuzz',
    'openpyxl', 'lxml', 'bs4', 'premailer', 'visualdl',
]

cython_datas = collect_data_files('Cython', include_py_files=True)

METADATA_PKGS = [
    'imageio', 'imgaug', 'scipy', 'lazy_loader',
    'scikit-image',
    'tqdm', 'rich', 'astor', 'opt_einsum',
    'paddleocr', 'paddlepaddle',
    'httpx',
]
metadata_datas = []
for _p in METADATA_PKGS:
    try:
        metadata_datas += copy_metadata(_p)
    except Exception:
        pass


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=paddle_binaries + ocr_binaries,
    datas=[
        ('config/default_config.json', 'config'),
        ('config/learned_positions.json', 'config'),
        ('config/tessdata', 'config/tessdata'),
        ('data', 'data'),
        ('paddle_models', 'paddle_models'),
        ('version.py', '.'),
    ] + paddle_datas + ocr_datas + cython_datas + metadata_datas,
    hiddenimports=[
        'win32gui', 'win32con', 'win32api', 'win32clipboard', 'pywintypes',
        'customtkinter', 'PIL', 'pyautogui', 'pytesseract',
        'openpyxl', 'pymysql', 'dotenv',
        'shapely', 'pyclipper', 'lmdb', 'rapidfuzz', 'numpy', 'cv2',
        'httpx', 'auth', 'auth.api_client', 'auth.session', 'auth.hwid',
        'auth.heartbeat', 'auth.sync_client', 'auth.updater',
        'ui.login_page',
    ] + paddle_hiddens + ocr_hiddens + PADDLEOCR_RUNTIME_DEPS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'paddle.jit.sot',
        'pdf2docx', 'docx', 'fitz', 'pymupdf',
        'matplotlib',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TalkPC-Pro',
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
    name='TalkPC-Pro',
)
