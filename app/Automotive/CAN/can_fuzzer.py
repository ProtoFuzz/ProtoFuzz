from PyQt5.QtCore import QThread
import math
import random
import threading
import time

import can

class CanFuzzer(QThread):
    def __init__(self, interface, fields_to_fuzz=None, rate_hz=100, frame_limit=1000):
        super().__init__()
        if not isinstance(rate_hz, (int, float)) or not math.isfinite(rate_hz) or rate_hz <= 0:
            raise ValueError("rate_hz must be a finite positive number")
        if not isinstance(frame_limit, int) or isinstance(frame_limit, bool) or frame_limit <= 0:
            raise ValueError("frame_limit must be a positive integer")

        self.interface = interface
        self.fields_to_fuzz = fields_to_fuzz or ["data"]
        self.rate_hz = rate_hz
        self.frame_limit = frame_limit
        self.running = True
        self._stop_event = threading.Event()

    def run(self):
        bus = can.interface.Bus(channel=self.interface, bustype="socketcan")
        interval = 1 / self.rate_hz
        frames_attempted = 0
        next_send = time.monotonic()
        try:
            while self.running and frames_attempted < self.frame_limit:
                delay = next_send - time.monotonic()
                if delay > 0 and self._stop_event.wait(delay):
                    break
                if not self.running:
                    break

                data = (
                    bytes(random.getrandbits(8) for _ in range(8))
                    if "data" in self.fields_to_fuzz
                    else b"\x00" * 8
                )
                arb_id = (
                    random.randint(0x100, 0x7FF)
                    if "arbitration_id" in self.fields_to_fuzz
                    else 0x123
                )
                msg = can.Message(arbitration_id=arb_id, data=data, is_extended_id=False)
                try:
                    bus.send(msg)
                except can.CanError:
                    pass

                frames_attempted += 1
                next_send = time.monotonic() + interval
        finally:
            bus.shutdown()

    def stop(self):
        self.running = False
        self._stop_event.set()
