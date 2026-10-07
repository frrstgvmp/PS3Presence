# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

diagnostic = os.environ.get('PS3_RELEASE_DIAGNOSTIC') == '1'
project_dir = Path(SPECPATH)
sys.path.insert(0, str(project_dir))
from packaging_policy import runtime_data, runtime_data_is_used
python_dlls = Path(sys.base_prefix) / 'DLLs'
openssl_names = ('libssl-3-x64.dll', 'libcrypto-3-x64.dll')
for name in openssl_names:
    if not (python_dlls / name).is_file():
        raise RuntimeError(f'Required Python runtime DLL is missing: {name}')


a = Analysis(
    [str(project_dir / 'gui.py')],
    pathex=[],
    binaries=[],
    datas=runtime_data(project_dir),
    hiddenimports=[],
    hookspath=[str(project_dir / 'hooks')],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtMultimediaWidgets'],
    noarchive=False,
    optimize=0,
)
# Qt 6.11 uses Windows' unversioned ICU entry points. The ICU 78 DLL from
# document tools exports suffixed names and breaks QtCore at import time.
# Also pin OpenSSL to Python's matching pair, not a DLL found on the host PATH.
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.casefold()
              not in {'icuuc.dll', 'icudt78.dll', *openssl_names}]
a.binaries += [(name, str(python_dlls / name), 'BINARY') for name in openssl_names]
a.datas = [entry for entry in a.datas if runtime_data_is_used(entry[0])]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PS3PresenceDiagnostic' if diagnostic else 'PS3Presence',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=diagnostic,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(project_dir / 'packaging' / 'version_info.txt'),
    icon=[str(project_dir / 'assets' / 'ps3-presence.ico')],
)
if not diagnostic:
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='PS3Presence',
    )
