from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import sys
import os
import pyshark
from functools import partial
import can
import time
from PyQt5.QtCore import QThread, pyqtSignal


class CanWorker(QThread):
    new_msg = pyqtSignal(str)

    def __init__(self, interface):
        super().__init__()
        self.interface = interface
        self.running = True

    def run(self):
        try:
            bus = can.interface.Bus(channel=self.interface, bustype='socketcan', bitrate=500000)
            print(f"Connected to {bus.channel_info}")
            for msg in bus:
                if not self.running:
                    break
                msg_str = (
                    f"Timestamp: {msg.timestamp:.2f} "
                    f"ID: {msg.arbitration_id:03X} "
                    f"DLC: {msg.dlc} "
                    f"Data: {msg.data.hex()}"
                )
                self.new_msg.emit(msg_str)  # send to GUI
        except can.CanError as e:
            print(f"CAN bus error: {e}")
        finally:
            if 'bus' in locals() and bus:
                bus.shutdown()

    def stop(self):
        self.running = False


class Main(QMainWindow):
    def __init__(self):
        super(Main, self).__init__()
        loadUi("app/ui/main.ui", self)
        self.Error_CAN.setHidden(True)
        self.fuzz_b.clicked.connect(lambda: self.start_capture(self.comboBox_3.currentText()))
        self.Stop_b.clicked.connect(self.stop_capture)

    def start_capture(self, interface):
        self.worker = CanWorker(interface)
        self.worker.new_msg.connect(self.can_widget.addItem)  # connect signal to widget
        self.worker.start()

    def stop_capture(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
            print("CAN monitoring stopped cleanly.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = Main()
    ui.show()
    app.exec_()
