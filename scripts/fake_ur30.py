#!/usr/bin/env python3
"""
fake_ur30.py — minimal RTDE handshake listener (scaffold, not a full mock)

Accepts a TCP connection on port 30004, handles the RTDE protocol-version
exchange so `rtde_receive.RTDEReceiveInterface("127.0.0.1")` gets past the
first message, and then LOGS every subsequent request while sending no-op
replies. Enough to prove the bridge can reach a fake endpoint and to
discover what ur-rtde's C++ library actually sends on the wire.

This is NOT a substitute for URSim. The six+ message types needed for a
working DATA_PACKAGE stream (GET_URCONTROL_VERSION,
CONTROL_PACKAGE_SETUP_{OUTPUTS,INPUTS}, CONTROL_PACKAGE_START,
DATA_PACKAGE, TEXT_MESSAGE, ...) are not implemented — they fall through
to the "unhandled" logger. Extend as needed.

Usage:
    python3 scripts/fake_ur30.py                    # default :30004
    python3 scripts/fake_ur30.py --port 30004       # explicit port

Then from another terminal:
    python -m src.bridge --host 127.0.0.1 --dry-run --no-status-poll --log-level DEBUG

Protocol reference:
    https://github.com/UniversalRobots/RTDE_Python_Client_Library/blob/master/rtde/rtde.py
    (message format: 2-byte big-endian size | 1-byte type | payload)
"""
from __future__ import annotations

import argparse
import socket
import struct
import sys

RTDE_REQUEST_PROTOCOL_VERSION = 0x56         # 'V'
RTDE_GET_URCONTROL_VERSION = 0x76            # 'v'
RTDE_TEXT_MESSAGE = 0x4D                     # 'M'
RTDE_DATA_PACKAGE = 0x55                     # 'U'
RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS = 0x4F    # 'O'
RTDE_CONTROL_PACKAGE_SETUP_INPUTS = 0x49     # 'I'
RTDE_CONTROL_PACKAGE_START = 0x53            # 'S'
RTDE_CONTROL_PACKAGE_PAUSE = 0x50            # 'P'

MSG_NAMES = {
    RTDE_REQUEST_PROTOCOL_VERSION: "REQUEST_PROTOCOL_VERSION",
    RTDE_GET_URCONTROL_VERSION: "GET_URCONTROL_VERSION",
    RTDE_TEXT_MESSAGE: "TEXT_MESSAGE",
    RTDE_DATA_PACKAGE: "DATA_PACKAGE",
    RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS: "CONTROL_PACKAGE_SETUP_OUTPUTS",
    RTDE_CONTROL_PACKAGE_SETUP_INPUTS: "CONTROL_PACKAGE_SETUP_INPUTS",
    RTDE_CONTROL_PACKAGE_START: "CONTROL_PACKAGE_START",
    RTDE_CONTROL_PACKAGE_PAUSE: "CONTROL_PACKAGE_PAUSE",
}


def recv_exact(conn: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return b""
        buf += chunk
    return buf


def handle_connection(conn: socket.socket, addr) -> None:
    print(f"[+] client connected: {addr}", flush=True)
    try:
        while True:
            header = recv_exact(conn, 3)
            if not header:
                print("[-] client closed", flush=True)
                return
            (size, msg_type) = struct.unpack(">HB", header)
            payload = recv_exact(conn, size - 3) if size > 3 else b""
            name = MSG_NAMES.get(msg_type, f"0x{msg_type:02x}")
            print(f"[<] {name:34s} size={size:4d} payload={payload.hex() if payload else '-'}",
                  flush=True)

            if msg_type == RTDE_REQUEST_PROTOCOL_VERSION:
                # Client sends desired version (2 bytes). Reply: accepted=1 (1 byte).
                resp = struct.pack(">HBB", 4, msg_type, 1)
                conn.sendall(resp)
                print(f"[>] REQUEST_PROTOCOL_VERSION accepted=1", flush=True)
            elif msg_type == RTDE_GET_URCONTROL_VERSION:
                # Reply: four uint32 fields (major, minor, bugfix, build). Fake a 5.11.0.0.
                resp = struct.pack(">HBIIII", 3 + 16, msg_type, 5, 11, 0, 0)
                conn.sendall(resp)
                print(f"[>] GET_URCONTROL_VERSION 5.11.0.0", flush=True)
            else:
                # Unhandled — client will likely error out soon. That's fine; we're
                # probing what ur-rtde sends.
                print(f"[!] unhandled {name} — sending no reply", flush=True)
                return
    except (ConnectionResetError, BrokenPipeError) as e:
        print(f"[-] connection error: {e}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=30004)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.listen(1)
    print(f"fake_ur30 listening on {args.host}:{args.port} (Ctrl-C to exit)", flush=True)

    try:
        while True:
            conn, addr = sock.accept()
            try:
                handle_connection(conn, addr)
            finally:
                conn.close()
    except KeyboardInterrupt:
        print("\nshutting down", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
