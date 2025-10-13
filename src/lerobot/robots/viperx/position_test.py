#!/usr/bin/env python3
# Live position monitor for Dynamixel IDs 2 & 3
from dynamixel_sdk import *   # pip install dynamixel-sdk
import time

PORT_NAME = "/dev/ttyUSB2"
BAUDRATE = 1000000
ADDR_PRESENT_POSITION = 132
PROTOCOL_VERSION = 2.0

# Initialize port and packet handlers
port = PortHandler(PORT_NAME)
packet = PacketHandler(PROTOCOL_VERSION)
if not port.openPort():
    print(f"❌ Failed to open {PORT_NAME}")
    exit(1)
port.setBaudRate(BAUDRATE)

def read_pos(motor_id):
    pos, result, error = packet.read4ByteTxRx(port, motor_id, ADDR_PRESENT_POSITION)
    if result != COMM_SUCCESS:
        print(f"[ID {motor_id}] Comm error: {packet.getTxRxResult(result)}")
    elif error:
        print(f"[ID {motor_id}] Error: {packet.getRxPacketError(error)}")
    return pos

print("Press Ctrl+C to stop.")
try:
    while True:
        p2 = read_pos(2)
        p3 = read_pos(3)
        deg2 = (p2 / 4096) * 360
        deg3 = (p3 / 4096) * 360
        diff = deg3 - deg2
        print(f"\rID2={deg2:8.2f}°,  ID3={deg3:8.2f}°,  Δ={diff:+6.2f}°", end="", flush=True)
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
finally:
    port.closePort()
    print("\n✅ Port closed.")
