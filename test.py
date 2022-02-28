import socket
import os
import subprocess
import queue
from threading import Thread
from open_see_data import parse_open_see_data
from pythonosc import udp_client

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OPENSEEFACE_DIR = os.path.join(SCRIPT_DIR, "OpenSeeface-v1.20.4")
FACETRACKER_BINARY = os.path.join(OPENSEEFACE_DIR, "Binary", "facetracker.exe")
PACKET_SIZE = 1785
OUTPUT_PORT = 7600

sock = socket.socket(socket.AF_INET,
                     socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 0))
socket_port = sock.getsockname()[1]
process = subprocess.Popen([FACETRACKER_BINARY, "-c", "0", "-v", "1", "--model", "3", "--gaze-tracking", "1", "--port", str(socket_port)], stdout=subprocess.DEVNULL)
osc_client = udp_client.SimpleUDPClient("127.0.0.1", OUTPUT_PORT)

print(f"Binding to port {socket_port}")



while True:
    try:
        data, addr = sock.recvfrom(PACKET_SIZE)
    except Exception as e:
        print(f"Bad packet received: {e}")
        continue
    print(f"message size: {len(data)}")
    parsed = parse_open_see_data(data)
    pitch = parsed.rotation.x
    yaw = parsed.rotation.y
    roll = parsed.rotation.z
    osc_client.send_message("/SceneRotator/pitch", pitch)
    osc_client.send_message("/SceneRotator/yaw", yaw)
    osc_client.send_message("/SceneRotator/roll", roll)