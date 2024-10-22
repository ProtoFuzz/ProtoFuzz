from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import sys


class Main(QMainWindow):
    def __init__(self):
        super(Main, self).__init__()
        loadUi("app/ui/main.ui",self)





if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = Main()
    ui.show()
    app.exec_()

