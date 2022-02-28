from PyQt5.QtWidgets import QApplication, QWidget
from main_window import MainWindow
import sys

app = QApplication(sys.argv)

window = MainWindow()
window.show()

app.exec()