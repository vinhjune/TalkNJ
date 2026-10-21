# Build with: .venv\Scripts\python -m PyInstaller --noconfirm TalkNJ.spec
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


a = Analysis(
    ['launch.py'],
    pathex=[],
    binaries=collect_dynamic_libs('ctranslate2') + collect_dynamic_libs('onnxruntime'),
    datas=collect_data_files('faster_whisper'),
    hiddenimports=[],
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
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='TalkNJ')
