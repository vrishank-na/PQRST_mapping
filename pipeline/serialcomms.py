import rclpy
import serial
from rclpy.node import Node
from std_msgs.msg import String
USB_PORT = '/dev/ttyUSB0' # as far as RPi is concerned


# define usb interface connection
def connect_usb_interface():
    try:
        serial = serial.serial(USB_PORT, baud_rate=115200, timeout=1)
        return serial
    except serial.SerialException as e:
        print("USB not connected: {e}")

def send_datastream(data, time):
    try:
        serial.write(data.encode())
        print(f"Data sent: {data} at time: {time}")
    except serial.SerialException as e:
        print(f"Error sending data: {e}")