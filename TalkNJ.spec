# Build natively on Windows or macOS with: python build_portable.py
import sys
from importlib.metadata import distribution
from pathlib import PurePosixPath

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

if sys.platform not in ('win32', 'darwin'):
    raise SystemExit('TalkNJ portable builds support Windows and macOS only.')

macos = sys.platform == 'darwin'
native_imports = (
    ['AppKit', 'Foundation', 'Quartz', 'ApplicationServices', 'CoreFoundation',
     'talknj._native_macos'] if macos else []
)

# Windows pywhispercpp 1.5.1 installs delvewheel-renamed whisper/ggml/VC
# DLLs beside its top-level _pywhispercpp extension, not inside the package.
# Package-only collect_dynamic_libs would silently omit all of them.
whisper_distribution = distribution('pywhispercpp')
whisper_binaries = [
    (str(whisper_distribution.locate_file(file)), str(PurePosixPath(str(file)).parent))
    for file in whisper_distribution.files or ()
    if str(file).lower().endswith(('.dll', '.so', '.dylib'))
]


a = Analysis(
    ['launch.py'],
    # pkg_resources adds this vendored-dependency path dynamically; PyInstaller
    # cannot infer it and otherwise omits the jaraco namespace at startup.
    pathex=[str(distribution('setuptools').locate_file('setuptools/_vendor'))],
    binaries=(collect_dynamic_libs('ctranslate2') + collect_dynamic_libs('onnxruntime')
              + collect_dynamic_libs('sherpa_onnx') + collect_dynamic_libs('pywhispercpp')
              + whisper_binaries),
    datas=(collect_data_files('faster_whisper') + collect_data_files('sherpa_onnx')
           + collect_data_files('pywhispercpp') + copy_metadata('pywhispercpp')
           + copy_metadata('sherpa-onnx') + copy_metadata('sherpa-onnx-core')
           + collect_data_files('talknj', includes=[
               'assets/*.svg', 'assets/*.png', 'assets/*.ico', 'assets/*.icns'])),
    hiddenimports=['_pywhispercpp', 'sherpa_onnx.lib._sherpa_onnx', 'talknj._whispercpp']
                  + native_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml',
              'PySide6.QtQuick', 'tkinter', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='TalkNJ',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
    icon=None if macos else 'talknj/assets/talknj.ico',
    entitlements_file='packaging/macos-entitlements.plist' if macos else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='TalkNJ')
if macos:
    app = BUNDLE(
        coll, name='TalkNJ.app', bundle_identifier='app.talknj.desktop', version='0.1.0',
        icon='talknj/assets/talknj.icns',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSMicrophoneUsageDescription':
                'TalkNJ records your microphone for private, on-device voice dictation.',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '14.0',
        },
    )
