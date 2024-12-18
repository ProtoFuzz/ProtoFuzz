from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import sys
import os
import pyshark
from functools import partial

class Main(QMainWindow):
    def __init__(self):
        super(Main, self).__init__()
        loadUi("app/ui/main.ui",self)
        self.Error_CAN.setHidden(True)
        self.fuzz_b.clicked.connect(partial(self.capture_can_packets, 'vcan0'))
        entries = ['one', 'two', 'three']
        #self.can_widget.addItems(entries)

        
    def capture_can_packets(self, interface):
        capture = pyshark.LiveCapture(interface=interface)
        try:
            for packet in capture.sniff_continuously():
                print(packet)
                
                entries = [str(packet)]
            
                self.can_widget.addItems(entries)
                # Process the packet here
        except KeyboardInterrupt:
            print("Capture stopped.")



if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = Main()
    ui.show()
    app.exec_()

