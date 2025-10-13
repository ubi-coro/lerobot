#!/usr/bin/env python3
from dynamixel_sdk import PortHandler, PacketHandler
import time

PORT="/dev/ttyUSB2"; BAUD=1000000; PROTO=2.0
ID2, ID3 = 2, 3
ADDR_POS=132; ADDR_CUR=126; ADDR_DM=10; ADDR_SID=12; ADDR_HWERR=70

ph_port = PortHandler(PORT); ph = PacketHandler(PROTO)
ph_port.openPort(); ph_port.setBaudRate(BAUD)

def read4(id, addr): return ph.read4ByteTxRx(ph_port, id, addr)[0]
def read2s(id, addr):
    v, _, _ = ph.read2ByteTxRx(ph_port, id, addr)
    if v > 32767: v -= 65536
    return v
def read1(id, addr): return ph.read1ByteTxRx(ph_port, id, addr)[0]

try:
    for _ in range(5):
        p2 = read4(ID2, ADDR_POS); p3 = read4(ID3, ADDR_POS)
        cur2 = read2s(ID2, ADDR_CUR); cur3 = read2s(ID3, ADDR_CUR)
        dm2 = read1(ID2, ADDR_DM); dm3 = read1(ID3, ADDR_DM)
        sid2 = read1(ID2, ADDR_SID); sid3 = read1(ID3, ADDR_SID)
        hw2 = read1(ID2, ADDR_HWERR); hw3 = read1(ID3, ADDR_HWERR)
        deg2 = p2 * 360.0 / 4096.0; deg3 = p3 * 360.0 / 4096.0
        print(f"ID2: {deg2:7.2f}°  cur={cur2*2.69:6.1f}mA  DM=0x{dm2:02X}  SID={sid2}  HWerr=0x{hw2:02X}")
        print(f"ID3: {deg3:7.2f}°  cur={cur3*2.69:6.1f}mA  DM=0x{dm3:02X}  SID={sid3}  HWerr=0x{hw3:02X}")
        print(f"Δpos = {(deg3-deg2):+.3f}°\n")
        time.sleep(0.2)
finally:
    ph_port.closePort()
