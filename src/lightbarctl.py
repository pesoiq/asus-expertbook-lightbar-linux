#!/usr/bin/env python3

import socket
import sys

SOCKET_PATH = "/run/asus-expertbook-lightbar/control.sock"

USAGE = """Usage:
  lightbarctl 1
  lightbarctl 2
  lightbarctl 3
  lightbarctl 4
  lightbarctl 5
  lightbarctl status
  lightbarctl list
"""

def main():
    if len(sys.argv) != 2:
        print(USAGE, end="", file=sys.stderr)
        return 2

    command = sys.argv[1].strip()

    if command not in {
        "1", "2", "3", "4", "5",
        "status", "list", "notify",
    }:
        print(USAGE, end="", file=sys.stderr)
        return 2

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    try:
        sock.connect(SOCKET_PATH)
        sock.sendall((command + "\n").encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)

        chunks = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)

        response = b"".join(chunks).decode(
            "utf-8",
            errors="replace",
        )

        if command != "notify":
            print(response, end="")

        return 1 if response.startswith("ERROR") else 0

    except FileNotFoundError:
        print(
            "ERROR: Light Bar control socket is not available. "
            "Check asus-expertbook-lightbar.service.",
            file=sys.stderr,
        )
        return 1
    except PermissionError:
        print(
            "ERROR: Permission denied opening Light Bar control socket. "
            "The user must be in the wheel group.",
            file=sys.stderr,
        )
        return 1
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
