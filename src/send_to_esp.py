import os
import time

import serial


DEFAULT_PORT = os.getenv("ECG_USB_PORT", "/dev/ttyUSB0")
BAUD_RATE = int(os.getenv("ECG_BAUD_RATE", "115200"))


def _select_serial_port(preferred_port=DEFAULT_PORT):
    if preferred_port and os.path.exists(preferred_port):
        return preferred_port

    try:
        from serial.tools import list_ports
    except Exception:
        return preferred_port

    available_ports = [port.device for port in list_ports.comports()]
    if preferred_port in available_ports:
        return preferred_port

    for candidate in available_ports:
        if any(token in candidate for token in ("ttyUSB", "ttyACM", "usbmodem", "cu.usbmodem", "tty.usbmodem")):
            return candidate

    return preferred_port


def _connect_serial():
    port = _select_serial_port()
    ser = serial.Serial(port, BAUD_RATE, timeout=1)
    time.sleep(2)
    return ser


ser = _connect_serial()


def send_phase(p):
    ser.write(p.encode())
    ser.flush()
    print("Sent:", p)
