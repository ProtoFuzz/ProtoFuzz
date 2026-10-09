from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import sys
import os
#import pyshark
from functools import partial
import can
import time
from PyQt5.QtCore import QThread, pyqtSignal
from app.Automotive.CAN.can_fuzzer import CanFuzzer

class CanWorker(QThread):
    new_msg = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

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
        except Exception as exc:
            self.error_occurred.emit(
                f"Capture failed on '{self.interface}': {exc}"
            )
        finally:
            if 'bus' in locals() and bus:
                try:
                    bus.shutdown()
                except Exception as exc:
                    self.error_occurred.emit(
                        f"Failed to close capture interface '{self.interface}': {exc}"
                    )

    def stop(self):
        self.running = False


class Main(QMainWindow):
    def __init__(self):
        super(Main, self).__init__()
        loadUi("app/ui/main.ui", self)
        self.fuzz_b.clicked.connect(lambda: self.start_capture(self.comboBox_3.currentText()))
        self.Stop_b.clicked.connect(self.stop_capture)

        self.fuzz_b.clicked.connect(lambda: self.start_fuzz(self.comboBox_3.currentText()))
        self.Stop_b.clicked.connect(self.stop_fuzz)


    def start_capture(self, interface):
        self.worker = CanWorker(interface)
        self.worker.new_msg.connect(self.can_widget.addItem)  # connect signal to widget
        self.worker.error_occurred.connect(self.show_can_error)
        self.worker.start()

    def stop_capture(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
            print("CAN monitoring stopped cleanly.")


    def start_fuzz(self, interface):
        self.fuzzer = CanFuzzer(
            interface,
            fields_to_fuzz=["data"],
            rate_hz=self.fuzzRateSpinBox.value(),
            frame_limit=self.frameLimitSpinBox.value(),
        )
        self.fuzzer.error_occurred.connect(self.show_can_error)
        self.fuzzer.start()

    def show_can_error(self, message):
        self.can_errors.addItem(f"{time.strftime('%H:%M:%S')} ERROR: {message}")
        while self.can_errors.count() > 200:
            self.can_errors.takeItem(0)

    def stop_fuzz(self):
        if hasattr(self, 'fuzzer') and self.fuzzer.isRunning():
            self.fuzzer.stop()
            self.fuzzer.wait()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = Main()
    ui.show()
    app.exec_()
