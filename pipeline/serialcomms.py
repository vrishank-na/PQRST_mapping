import csv
import json
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


def _select_serial_port(preferred_port=None, available_ports=None):
    requested_port = preferred_port or USB_PORT
    if not requested_port:
        return requested_port

    if available_ports is None:
        try:
            from serial.tools import list_ports

            available_ports = [port.device for port in list_ports.comports()]
        except Exception:
            return requested_port

    if requested_port in available_ports:
        return requested_port

    preferred_keywords = ("ttyUSB", "ttyACM", "usbmodem", "cu.usbmodem", "tty.usbmodem")
    for candidate in available_ports:
        if any(keyword in candidate for keyword in preferred_keywords):
            return candidate

    return requested_port


def connect_usb_interface(
    port=USB_PORT,
    baud_rate=BAUD_RATE,
    timeout=TIMEOUT_SECONDS,
    settle_seconds=2.0,
):
    # open serial connection
    if serial is None:
        raise ConnectionError("pyserial is required for USB communication: pip install pyserial")

    selected_port = _select_serial_port(port)

    try:
        connection = serial.Serial(selected_port, baudrate=baud_rate, timeout=timeout)
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


def _normalize_window(window, unit="ms"):
    if isinstance(window, Mapping):
        start = window.get("start_ms", window.get("start", window.get("in", window.get("on"))))
        end = window.get("end_ms", window.get("end", window.get("out", window.get("off"))))
    else:
        start, end = window

    if unit in {"s", "sec", "second", "seconds"}:
        start_ms = _time_to_ms(start)
        end_ms = _time_to_ms(end)
    else:
        start_ms = int(round(float(start)))
        end_ms = int(round(float(end)))
    if end_ms <= start_ms:
        raise ValueError(f"PQRST window end must be after start: {window}")
    return [start_ms, end_ms]


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


def format_pqrst_packet(data, packet_format="json"):
    """Convert model output into a serial packet.

    JSON firmware format:
    {"type":"ecg_pqrst","unit":"ms","labels":["P","Q","R","S","T"],"matrix":[[Pin,Pout],...]}

    Legacy format remains available with packet_format="legacy":
    P:0,Q:80,R:120,S:160,T:320
    """
    if isinstance(data, str):
        if os.path.exists(data):
            data = _events_from_csv(data)
        else:
            line = data.strip()
            return line if line.endswith("\n") else f"{line}\n"

    if isinstance(data, Mapping) and "matrix" in data:
        labels = tuple(data.get("labels", PQRST_ORDER))
        if tuple(labels) != PQRST_ORDER:
            raise ValueError(f"PQRST matrix labels must be {PQRST_ORDER}")
        unit = str(data.get("unit", "ms")).lower()
        matrix = [_normalize_window(window, unit=unit) for window in data["matrix"]]
        if len(matrix) != len(PQRST_ORDER):
            raise ValueError("PQRST matrix must contain five [in,out] windows")
        first_time = min(start for start, _ in matrix)
        normalized_matrix = [[start - first_time, end - first_time] for start, end in matrix]
        if packet_format == "legacy":
            return _legacy_packet_from_matrix(normalized_matrix)
        return _json_packet(normalized_matrix)

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
    matrix = _event_times_to_windows(events, first_time)
    if packet_format == "legacy":
        return _legacy_packet_from_matrix(matrix)
    return _json_packet(matrix)


def _event_times_to_windows(events, first_time):
    starts = [events[event] - first_time for event in PQRST_ORDER]
    defaults = [80, 40, 55, 55, 200]
    matrix = []
    for idx, start in enumerate(starts):
        next_start = starts[idx + 1] if idx + 1 < len(starts) else start + defaults[idx]
        end = max(start + 1, min(start + defaults[idx], next_start))
        matrix.append([start, end])
    return matrix


def _legacy_packet_from_matrix(matrix):
    packet = ",".join(f"{event}:{matrix[idx][0]}" for idx, event in enumerate(PQRST_ORDER))
    return f"{packet}\n"


def _json_packet(matrix):
    compact_matrix = [[int(start), int(end)] for start, end in matrix]
    packet = {
        "m": compact_matrix,
    }
    return json.dumps(packet, separators=(",", ":")) + "\n"


def format_packets(results, packet_format="json"):
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

    return [format_pqrst_packet(beat, packet_format=packet_format) for beat in beats]


def send_datastream(data, timestamp=None, connection=None, close_after_send=False, packet_format="json"):
    # single pqrst packet
    serial_connection = connection or connect_usb_interface()
    packet = format_pqrst_packet(data, packet_format=packet_format)

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


def stream_packets(data_packets, port=USB_PORT, baud_rate=BAUD_RATE, inter_packet_delay=0.05, packet_format="json"):
    with connect_usb_interface(port=port, baud_rate=baud_rate) as connection:
        sent_packets = []
        for index, packet_data in enumerate(data_packets):
            sent_packets.append(
                send_datastream(
                    packet_data,
                    connection=connection,
                    close_after_send=False,
                    packet_format=packet_format,
                )
            )
            if index < len(data_packets) - 1 and inter_packet_delay > 0:
                time.sleep(inter_packet_delay)

    return sent_packets


def send_results(
    results,
    port=USB_PORT,
    baud_rate=BAUD_RATE,
    inter_packet_delay=0.05,
    packet_format="json",
    pace_by_real_time=True,
    max_gap_seconds=3.0,
):
    """Send model2 output to the firmware, one packet per beat.

    By default (pace_by_real_time=True) the wait *between* beats is derived
    from each beat's real "r_time_ms" (its absolute R-peak time within the
    recording), not a fixed inter_packet_delay. The firmware's playback of a
    single PQRST cycle takes ~500-600ms; a fixed 50ms gap dumps every
    detected beat almost instantly, overflowing the firmware's small
    playback queue (MAX_PENDING_PACKETS=4) and silently dropping the rest -
    which is why only the first couple of beats were ever visible.

    max_gap_seconds caps how long we'll wait for a single beat-to-beat gap,
    in case of bad/missing timestamps or a big gap in the recording.
    """
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
        previous_send_time = None
        previous_r_ms = None

        for beat in beats:
            r_ms = beat.get("r_time_ms") if isinstance(beat, Mapping) else None
            have_real_gap = (
                pace_by_real_time
                and previous_send_time is not None
                and previous_r_ms is not None
                and r_ms is not None
            )

            if have_real_gap:
                target_gap = max(0.0, (r_ms - previous_r_ms) / 1000.0)
                target_gap = min(target_gap, max_gap_seconds)
                already_elapsed = time.time() - previous_send_time
                wait_time = target_gap - already_elapsed
                if wait_time > 0:
                    time.sleep(wait_time)
            elif previous_send_time is not None:
                # Fallback for data without real timestamps (legacy single
                # dict/tuple beats, CSV rows, etc.) - old fixed-delay behavior.
                time.sleep(inter_packet_delay)

            send_time = time.time()
            sent_packets.append(
                send_datastream(
                    beat,
                    connection=connection,
                    close_after_send=False,
                    packet_format=packet_format,
                )
            )
            previous_send_time = send_time
            if r_ms is not None:
                previous_r_ms = r_ms

    return sent_packets
