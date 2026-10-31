# PyInstaller spec: a windowed one-folder build named FlowVoice.
# Build with packaging\build.ps1 (it sets up its own environment); not meant to be run by hand.
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = collect_data_files("faster_whisper")            # silero VAD model used by vad_filter
datas += collect_data_files("_sounddevice_data")        # PortAudio DLL
datas += [("../tests/data/hello.wav", "samples")]       # for --selftest
binaries = collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("onnxruntime")

# The app only uses QtCore / QtGui / QtWidgets: leave the rest of PySide6 out (hundreds of MB).
UNUSED_QT = [
    "Qt3DAnimation", "Qt3DCore", "Qt3DExtras", "Qt3DInput", "Qt3DLogic", "Qt3DRender",
    "QtBluetooth", "QtCharts", "QtDataVisualization", "QtDesigner", "QtHelp", "QtLocation",
    "QtMultimedia", "QtMultimediaWidgets", "QtNetworkAuth", "QtNfc", "QtOpenGL",
    "QtOpenGLWidgets", "QtPdf", "QtPdfWidgets", "QtPositioning", "QtQml", "QtQuick",
    "QtQuick3D", "QtQuickControls2", "QtQuickWidgets", "QtRemoteObjects", "QtScxml",
    "QtSensors", "QtSerialBus", "QtSerialPort", "QtSpatialAudio", "QtSql", "QtStateMachine",
    "QtSvg", "QtSvgWidgets", "QtTest", "QtTextToSpeech", "QtUiTools", "QtWebChannel",
    "QtWebEngineCore", "QtWebEngineQuick", "QtWebEngineWidgets", "QtWebSockets", "QtWebView",
    "QtXml",
]
excludes = [f"PySide6.{m}" for m in UNUSED_QT] + ["tkinter", "pytest", "matplotlib", "IPython"]

a = Analysis(
    ["flowvoice_entry.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=["win32com.client", "pythoncom", "pywintypes", "win32timezone"],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="FlowVoice",
          console=False, disable_windowed_traceback=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="FlowVoice", upx=False)
