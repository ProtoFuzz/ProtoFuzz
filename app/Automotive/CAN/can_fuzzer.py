from PyQt5.QtCore import QThread, pyqtSignal
import math
import random
import threading
import time

import can

class CanFuzzer(QThread):
    error_occurred = pyqtSignal(str)
    interesting_frame = pyqtSignal(str)

    def __init__(
        self,
        interface,
        fields_to_fuzz=None,
        rate_hz=100,
        frame_limit=1000,
        feedback_timeout=0.01,
    ):
        super().__init__()
        if not isinstance(rate_hz, (int, float)) or not math.isfinite(rate_hz) or rate_hz <= 0:
            raise ValueError("rate_hz must be a finite positive number")
        if not isinstance(frame_limit, int) or isinstance(frame_limit, bool) or frame_limit <= 0:
            raise ValueError("frame_limit must be a positive integer")
        if not isinstance(feedback_timeout, (int, float)) or not math.isfinite(feedback_timeout) or feedback_timeout <= 0:
            raise ValueError("feedback_timeout must be a finite positive number")

        self.interface = interface
        self.fields_to_fuzz = fields_to_fuzz or ["data"]
        self.rate_hz = rate_hz
        self.frame_limit = frame_limit
        self.feedback_timeout = feedback_timeout
        self.running = True
        self._stop_event = threading.Event()

    def run(self):
        bus = None
        try:
            bus = can.interface.Bus(
                channel=self.interface,
                interface="socketcan",
                receive_own_messages=False,
            )
            interval = 1 / self.rate_hz
            frames_attempted = 0
            next_send = time.monotonic()
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
                sent_at = time.monotonic()
                try:
                    bus.send(msg)
                except can.CanError as exc:
                    self.error_occurred.emit(
                        f"Send failed on '{self.interface}': {exc}"
                    )
                    break

                frames_attempted += 1
                next_send = sent_at + interval
                responses = []
                feedback_deadline = time.monotonic() + self.feedback_timeout
                while self.running:
                    remaining = feedback_deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    response = bus.recv(timeout=remaining)
                    if response is None:
                        break
                    responses.append(response)

                if responses:
                    sent_frame = f"{msg.arbitration_id:03X}#{msg.data.hex().upper()}"
                    received_frames = ", ".join(
                        f"{response.arbitration_id:03X}#{response.data.hex().upper()}"
                        for response in responses
                    )
                    self.interesting_frame.emit(
                        f"TX {sent_frame} -> RX {received_frames}"
                    )
        except Exception as exc:
            self.error_occurred.emit(f"Fuzzing failed on '{self.interface}': {exc}")
        finally:
            self.running = False
            if bus is not None:
                try:
                    bus.shutdown()
                except Exception as exc:
                    self.error_occurred.emit(
                        f"Failed to close CAN interface '{self.interface}': {exc}"
                    )

    def stop(self):
        self.running = False
        self._stop_event.set()
