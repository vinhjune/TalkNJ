# Build with: .venv\Scripts\python -m PyInstaller --noconfirm TalkNJ.spec
from importlib.metadata import distribution
from pathlib import PurePosixPath

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata


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
           + copy_metadata('sherpa-onnx') + copy_metadata('sherpa-onnx-core')),
    hiddenimports=['_pywhispercpp', 'sherpa_onnx.lib._sherpa_onnx', 'talknj._whispercpp'],
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
