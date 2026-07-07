import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline import serialcomms


def test_select_serial_port_uses_requested_port_when_available():
    available = ["/dev/ttyUSB0", "/dev/cu.usbmodem11201"]
    assert serialcomms._select_serial_port("/dev/ttyUSB0", available) == "/dev/ttyUSB0"


def test_select_serial_port_falls_back_to_matching_modem():
    available = ["/dev/cu.usbmodem11201"]
    assert serialcomms._select_serial_port("/dev/ttyUSB0", available) == "/dev/cu.usbmodem11201"


def test_format_pqrst_packet_uses_compact_json_payload():
    packet = serialcomms.format_pqrst_packet({"P": 0, "Q": 80, "R": 120, "S": 160, "T": 320})
    assert packet.startswith('{"m":[[')
    assert packet.endswith('}\n')

def test_stream_packets_writes_multiple_packets(monkeypatch):
    class DummyConnection:
        def __init__(self):
            self.writes = []

        def write(self, data):
            self.writes.append(data.decode("ascii"))

        def flush(self):
            return None

        def close(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()

    connection = DummyConnection()
    monkeypatch.setattr(serialcomms, "connect_usb_interface", lambda **kwargs: connection)

    packets = serialcomms.stream_packets(
        [{"P": 0, "Q": 80, "R": 120, "S": 160, "T": 320}, {"P": 20, "Q": 100, "R": 140, "S": 180, "T": 340}],
        inter_packet_delay=0,
    )

    assert len(packets) == 2
    assert len(connection.writes) == 2
    assert all(packet.endswith("\n") for packet in connection.writes)
