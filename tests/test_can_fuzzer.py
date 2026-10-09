import unittest
from unittest.mock import Mock, patch

import can

from app.Automotive.CAN.can_fuzzer import CanFuzzer
from main import CanWorker


class CanFuzzerTests(unittest.TestCase):
    def run_fuzzer_once(self, fields_to_fuzz, random_bits=None, random_id=None):
        fuzzer = CanFuzzer("test-interface", fields_to_fuzz=fields_to_fuzz)
        bus = Mock()
        bus.recv.return_value = None

        def stop_after_send(_message):
            fuzzer.stop()

        bus.send.side_effect = stop_after_send
        with patch(
            "app.Automotive.CAN.can_fuzzer.can.interface.Bus", return_value=bus
        ) as bus_factory:
            with patch(
                "app.Automotive.CAN.can_fuzzer.random.getrandbits",
                side_effect=random_bits,
            ) as getrandbits:
                with patch(
                    "app.Automotive.CAN.can_fuzzer.random.randint",
                    return_value=random_id,
                ) as randint:
                    fuzzer.run()

        bus_factory.assert_called_once_with(
            channel="test-interface",
            interface="socketcan",
            receive_own_messages=False,
        )
        bus.send.assert_called_once()
        bus.shutdown.assert_called_once_with()
        return bus.send.call_args.args[0], getrandbits, randint

    def test_default_fuzzes_eight_data_bytes(self):
        message, getrandbits, randint = self.run_fuzzer_once(
            None, random_bits=range(8)
        )

        self.assertEqual(message.data, bytes(range(8)))
        self.assertEqual(message.arbitration_id, 0x123)
        self.assertFalse(message.is_extended_id)
        self.assertEqual(getrandbits.call_count, 8)
        randint.assert_not_called()

    def test_arbitration_id_fuzzing_uses_random_id_and_zero_data(self):
        message, getrandbits, randint = self.run_fuzzer_once(
            ["arbitration_id"], random_id=0x456
        )

        self.assertEqual(message.arbitration_id, 0x456)
        self.assertEqual(message.data, bytes(8))
        self.assertFalse(message.is_extended_id)
        getrandbits.assert_not_called()
        randint.assert_called_once_with(0x100, 0x7FF)

    def test_data_and_arbitration_id_can_both_be_fuzzed(self):
        message, getrandbits, randint = self.run_fuzzer_once(
            ["data", "arbitration_id"], random_bits=range(8), random_id=0x789
        )

        self.assertEqual(message.data, bytes(range(8)))
        self.assertEqual(message.arbitration_id, 0x789)
        self.assertEqual(getrandbits.call_count, 8)
        randint.assert_called_once_with(0x100, 0x7FF)

    def test_frame_limit_and_send_rate_are_enforced(self):
        fuzzer = CanFuzzer("test-interface", rate_hz=100, frame_limit=3)
        bus = Mock()
        bus.recv.return_value = None
        clock = [0.0]

        def advance_clock(delay):
            clock[0] += delay
            return False

        with patch(
            "app.Automotive.CAN.can_fuzzer.can.interface.Bus", return_value=bus
        ):
            with patch(
                "app.Automotive.CAN.can_fuzzer.time.monotonic",
                side_effect=lambda: clock[0],
            ):
                with patch.object(
                    fuzzer._stop_event, "wait", side_effect=advance_clock
                ) as wait:
                    fuzzer.run()

        self.assertEqual(bus.send.call_count, 3)
        self.assertEqual([call.args[0] for call in wait.call_args_list], [0.01, 0.01])
        bus.shutdown.assert_called_once_with()

    def test_rejects_invalid_rate_and_frame_limit(self):
        for invalid_rate in (0, -1, float("nan"), float("inf")):
            with self.subTest(rate_hz=invalid_rate):
                with self.assertRaises(ValueError):
                    CanFuzzer("test-interface", rate_hz=invalid_rate)

        for invalid_limit in (0, -1, 1.5, True):
            with self.subTest(frame_limit=invalid_limit):
                with self.assertRaises(ValueError):
                    CanFuzzer("test-interface", frame_limit=invalid_limit)

        for invalid_timeout in (0, -1, float("nan"), float("inf")):
            with self.subTest(feedback_timeout=invalid_timeout):
                with self.assertRaises(ValueError):
                    CanFuzzer("test-interface", feedback_timeout=invalid_timeout)

    def test_emits_transmitted_frame_when_receive_feedback_arrives(self):
        fuzzer = CanFuzzer("test-interface", frame_limit=1, feedback_timeout=0.01)
        bus = Mock()
        response = can.Message(
            arbitration_id=0x456, data=bytes.fromhex("A1B2"), is_rx=False
        )
        bus.recv.side_effect = [response, None]
        frames = []
        fuzzer.interesting_frame.connect(frames.append)

        with patch(
            "app.Automotive.CAN.can_fuzzer.can.interface.Bus", return_value=bus
        ):
            with patch(
                "app.Automotive.CAN.can_fuzzer.random.getrandbits", return_value=0x11
            ):
                fuzzer.run()

        self.assertEqual(frames, ["TX 123#1111111111111111 -> RX 456#A1B2"])
        bus.shutdown.assert_called_once_with()

    def test_reports_interface_open_failure(self):
        fuzzer = CanFuzzer("missing-interface")
        errors = []
        fuzzer.error_occurred.connect(errors.append)

        with patch(
            "app.Automotive.CAN.can_fuzzer.can.interface.Bus",
            side_effect=can.CanError("interface unavailable"),
        ):
            fuzzer.run()

        self.assertEqual(
            errors,
            ["Fuzzing failed on 'missing-interface': interface unavailable"],
        )

    def test_reports_send_failure_and_closes_bus(self):
        fuzzer = CanFuzzer("test-interface", frame_limit=3)
        bus = Mock()
        bus.send.side_effect = can.CanError("bus went offline")
        errors = []
        fuzzer.error_occurred.connect(errors.append)

        with patch(
            "app.Automotive.CAN.can_fuzzer.can.interface.Bus", return_value=bus
        ):
            fuzzer.run()

        self.assertEqual(bus.send.call_count, 1)
        bus.shutdown.assert_called_once_with()
        self.assertEqual(errors, ["Send failed on 'test-interface': bus went offline"])


class CanWorkerTests(unittest.TestCase):
    def test_reports_unexpected_interface_failure_without_raising(self):
        worker = CanWorker("missing-interface")
        errors = []
        worker.error_occurred.connect(errors.append)

        with patch(
            "main.can.interface.Bus", side_effect=RuntimeError("driver unavailable")
        ):
            worker.run()

        self.assertEqual(
            errors,
            ["Capture failed on 'missing-interface': driver unavailable"],
        )


if __name__ == "__main__":
    unittest.main()