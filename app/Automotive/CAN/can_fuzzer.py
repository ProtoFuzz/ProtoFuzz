from PyQt5.QtCore import QThread
import can, random

class CanFuzzer(QThread):
    def __init__(self, interface, fields_to_fuzz=None):
        super().__init__()
        self.interface = interface
        self.fields_to_fuzz = fields_to_fuzz or ["data"]
        self.running = True

    def run(self):
        bus = can.interface.Bus(channel=self.interface, bustype="socketcan")
        while self.running:
            data = bytes(random.getrandbits(8) for _ in range(8)) if "data" in self.fields_to_fuzz else b"\x00"*8
            arb_id = random.randint(0x100, 0x7FF) if "arbitration_id" in self.fields_to_fuzz else 0x123
            msg = can.Message(arbitration_id=arb_id, data=data, is_extended_id=False)
            try:
                bus.send(msg)
            except can.CanError:
                pass

    def stop(self):
        self.running = False
