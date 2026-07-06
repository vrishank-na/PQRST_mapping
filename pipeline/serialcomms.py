import csv
import os
import time
from collections.abc import Iterable, Mapping

try:
    import serial
except ImportError:
    serial = None


USB_PORT = os.getenv("ECG_USB_PORT", "/dev/ttyUSB0")
BAUD_RATE = int(os.getenv("ECG_BAUD_RATE", "115200"))
TIMEOUT_SECONDS = 1
PQRST_ORDER = ("P", "Q", "R", "S", "T")


def connect_usb_interface(
    port=USB_PORT,
    baud_rate=BAUD_RATE,
    timeout=TIMEOUT_SECONDS,
    settle_seconds=2.0,
):
    # open serial connection
    if serial is None:
        raise ConnectionError("pyserial is required for USB communication: pip install pyserial")

    try:
        connection = serial.Serial(port, baudrate=baud_rate, timeout=timeout)
        time.sleep(settle_seconds)
        return connection
    except serial.SerialException as exc:
        raise ConnectionError(f"USB serial device not available on {port}: {exc}") from exc


def _time_to_ms(value):
    numeric = float(value)
    if numeric < 0:
        raise ValueError(f"PQRST event time cannot be negative: {value}")

    # model code commonly emits seconds, while firmware expects milliseconds.
    return int(round(numeric * 1000 if numeric <= 10 else numeric))


def _normalize_event_name(name):
    key = str(name).strip().upper()
    if key == "QRS":
        key = "R"
    elif key in {"T_START", "TSTART"}:
        key = "T"

    if key not in PQRST_ORDER:
        raise ValueError(f"Unsupported ECG event name: {name}")
    return key


def _events_from_csv(csv_path):
    with open(csv_path, newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    if not rows:
        raise ValueError(f"No rows found in {csv_path}")

    if all(event in rows[0] for event in PQRST_ORDER):
        return {event: rows[-1][event] for event in PQRST_ORDER}

    event_field = next(
        (field for field in ("event", "phase", "label", "wave") if field in rows[0]),
        None,
    )
    time_field = next(
        (field for field in ("time_ms", "time", "timestamp", "sample", "idx") if field in rows[0]),
        None,
    )

    if not event_field or not time_field:
        raise ValueError(
            "CSV must contain P,Q,R,S,T columns or event/phase plus time columns"
        )

    return {
        _normalize_event_name(row[event_field]): row[time_field]
        for row in rows
        if row.get(event_field)
    }


def format_pqrst_packet(data):
    """Convert model output into firmware format: P:0,Q:80,R:120,S:160,T:320."""
    if isinstance(data, str):
        if os.path.exists(data):
            data = _events_from_csv(data)
        else:
            line = data.strip()
            return line if line.endswith("\n") else f"{line}\n"

    if isinstance(data, Mapping):
        events = {
            _normalize_event_name(event): _time_to_ms(value)
            for event, value in data.items()
        }
    elif isinstance(data, Iterable):
        events = {}
        for item in data:
            if isinstance(item, Mapping):
                event = item.get("event", item.get("phase", item.get("label", item.get("wave"))))
                event_time = item.get(
                    "time_ms",
                    item.get("time", item.get("timestamp", item.get("sample", item.get("idx")))),
                )
            else:
                event, event_time = item

            events[_normalize_event_name(event)] = _time_to_ms(event_time)
    else:
        raise TypeError("PQRST data must be a mapping, iterable, string packet, or CSV path")

    missing = [event for event in PQRST_ORDER if event not in events]
    if missing:
        raise ValueError(f"Missing PQRST event times: {', '.join(missing)}")

    first_time = min(events.values())
    packet = ",".join(
        f"{event}:{events[event] - first_time}"
        for event in PQRST_ORDER
    )
    return f"{packet}\n"


def send_datastream(data, timestamp=None, connection=None, close_after_send=False):
    # single pqrst packet
    serial_connection = connection or connect_usb_interface()
    packet = format_pqrst_packet(data)

    try:
        serial_connection.write(packet.encode("ascii"))
        serial_connection.flush()
        sent_at = timestamp if timestamp is not None else time.time()
        print(f"Data sent: {packet.strip()} at time: {sent_at}")
        return packet
    except OSError as exc:
        raise IOError(f"Error sending serial data: {exc}") from exc
    finally:
        if close_after_send or connection is None:
            serial_connection.close()


def send_results(results, port=USB_PORT, baud_rate=BAUD_RATE, inter_packet_delay=0.05):
    # model2 output, dict or list of dicts, or CSV path, or single packet string
    if isinstance(results, (str, Mapping)):
        beats = [results]
    else:
        beats = list(results)
        event_keys = {"event", "phase", "label", "wave"}
        looks_like_event_dicts = all(
            isinstance(item, Mapping) and event_keys.intersection(item)
            for item in beats
        )
        looks_like_event_tuples = all(
            isinstance(item, tuple) and len(item) == 2
            for item in beats
        )

        if beats and (looks_like_event_dicts or looks_like_event_tuples):
            beats = [beats]

    with connect_usb_interface(port=port, baud_rate=baud_rate) as connection:
        sent_packets = []
        for beat in beats:
            sent_packets.append(
                send_datastream(beat, connection=connection, close_after_send=False)
            )
            time.sleep(inter_packet_delay)

    return sent_packets
