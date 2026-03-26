from PySide6.QtWidgets import QApplication, QMainWindow
from vivembed import CrimewView
import sys

app = QApplication(sys.argv)

win = QMainWindow()
view = CrimewView()

view.load_url("https://google.com")

win.setCentralWidget(view)
win.resize(1024, 768)
win.show()

sys.exit(app.exec())