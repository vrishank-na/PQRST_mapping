import serial
import time

# Change COM port to your ESP32 port
ser = serial.Serial('COM5', 115200)
time.sleep(2)

def send_phase(p):
    ser.write(p.encode())
    print("Sent:", p)
