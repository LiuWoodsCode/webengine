import importlib
import sys
import types
import unittest


def _install_pyside6_stubs():
    if "PySide6" in sys.modules:
        return

    class Dummy:
        def __init__(self, *args, **kwargs):
            pass

        def __getattr__(self, name):
            return Dummy()

        def __call__(self, *args, **kwargs):
            return Dummy()

    class DummySignal:
        def connect(self, *args, **kwargs):
            return None

    class QDialogButtonBox(Dummy):
        Ok = 1
        Apply = 2
        Cancel = 4
        ActionRole = 5

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.accepted = DummySignal()
            self.rejected = DummySignal()

        def button(self, *args, **kwargs):
            return Dummy()

    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtcore = types.ModuleType("PySide6.QtCore")
    qtgui = types.ModuleType("PySide6.QtGui")

    for name in [
        "QApplication",
        "QMainWindow",
        "QWidget",
        "QVBoxLayout",
        "QHBoxLayout",
        "QLineEdit",
        "QPushButton",
        "QLabel",
        "QScrollArea",
        "QFrame",
        "QDialog",
        "QCheckBox",
        "QFormLayout",
        "QMessageBox",
        "QMenu",
        "QSizePolicy",
        "QComboBox",
        "QTextEdit",
    ]:
        setattr(qtwidgets, name, Dummy)

    qtwidgets.QDialogButtonBox = QDialogButtonBox

    qtcore.Qt = types.SimpleNamespace(AlignTop=1, ShortcutFocusReason=2)
    qtcore.QByteArray = bytes
    qtcore.QObject = Dummy
    qtcore.Signal = lambda *args, **kwargs: DummySignal()

    for name in ["QPixmap", "QAction", "QIcon"]:
        setattr(qtgui, name, Dummy)

    pyside6 = types.ModuleType("PySide6")
    pyside6.QtWidgets = qtwidgets
    pyside6.QtCore = qtcore
    pyside6.QtGui = qtgui

    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtWidgets"] = qtwidgets
    sys.modules["PySide6.QtCore"] = qtcore
    sys.modules["PySide6.QtGui"] = qtgui


class MainExtractTitleTests(unittest.TestCase):
    def test_extract_title(self):
        _install_pyside6_stubs()
        main = importlib.import_module("main")
        self.assertEqual(main.extract_title("<title>Hello</title>"), "Hello")


if __name__ == "__main__":
    unittest.main()
