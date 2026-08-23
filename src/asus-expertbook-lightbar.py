#!/usr/bin/env python3

import os
import glob
import fcntl
import time
import signal

# ============================================================
# ASUS ExpertBook B9400CBA/B9450CBA Light Bar
#
# FINAL VERIFIED BEHAVIOR
#
# AC disconnected
#   -> OFF
#
# AC connected + Charging + battery < 100%
#   -> Pure Red ~5%
#
# AC connected + battery >= 100%
#   -> Pure Green ~5%
#
# Transition INTO Performance
#   -> Blue-Cyan ~20% for 3 seconds only
#   -> then restore RED / GREEN / OFF
# ============================================================

AC_PATH      = "/sys/class/power_supply/AC0/online"
BAT_STATUS   = "/sys/class/power_supply/BAT0/status"
BAT_CAPACITY = "/sys/class/power_supply/BAT0/capacity"
PROFILE_PATH = "/sys/firmware/acpi/platform_profile"

POLL_INTERVAL = 0.25
PERFORMANCE_SECONDS = 3.0
RECONNECT_SECONDS = 2.0

GAIN = 0x20

stop_requested = False


# ============================================================
# Signals
# ============================================================

def signal_handler(signum, frame):
    global stop_requested
    stop_requested = True


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def sleep_interruptible(seconds):
    end = time.monotonic() + seconds

    while not stop_requested:
        remaining = end - time.monotonic()

        if remaining <= 0:
            break

        time.sleep(min(0.10, remaining))


# ============================================================
# HIDRAW ioctl definitions
# ============================================================

IOC_TYPESHIFT = 8
IOC_SIZESHIFT = 16
IOC_DIRSHIFT  = 30

IOC_WRITE = 1
IOC_READ  = 2


def HIDIOCSFEATURE(length):
    return (
        ((IOC_READ | IOC_WRITE) << IOC_DIRSHIFT)
        | (ord("H") << IOC_TYPESHIFT)
        | 0x06
        | (length << IOC_SIZESHIFT)
    )


def HIDIOCGFEATURE(length):
    return (
        ((IOC_READ | IOC_WRITE) << IOC_DIRSHIFT)
        | (ord("H") << IOC_TYPESHIFT)
        | 0x07
        | (length << IOC_SIZESHIFT)
    )


# ============================================================
# Logging
# ============================================================

def log(message):
    print(message, flush=True)


# ============================================================
# System-state helpers
# ============================================================

def read_text(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return ""


def read_capacity():
    try:
        return int(read_text(BAT_CAPACITY))
    except ValueError:
        return -1


# ============================================================
# Locate exact ASUS ALED0217 controller
# ============================================================

def locate_device():

    devices = glob.glob(
        "/sys/bus/hid/devices/0018:0B05:0124.*"
    )

    if len(devices) != 1:
        raise RuntimeError(
            "ALED0217 0B05:0124 not currently available "
            f"(found {len(devices)})"
        )

    dev = devices[0]

    descriptor_path = os.path.join(
        dev,
        "report_descriptor"
    )

    with open(descriptor_path, "rb") as f:
        descriptor = f.read()

    # Exact collection recovered from AsusOptimization.exe:
    #
    # UsagePage = 0xFFB5
    # Usage     = 0x00A0
    # Report ID = 0x20
    signature = bytes([
        0x06, 0xB5, 0xFF,
        0x09, 0xA0,
        0xA1, 0x01,
        0x85, 0x20
    ])

    if signature not in descriptor:
        raise RuntimeError(
            "ALED0217 descriptor does not match ASUS Light Bar"
        )

    raws = glob.glob(
        os.path.join(
            dev,
            "hidraw",
            "hidraw*"
        )
    )

    if len(raws) != 1:
        raise RuntimeError(
            f"ALED0217 hidraw node unavailable "
            f"(found {len(raws)})"
        )

    return "/dev/" + os.path.basename(raws[0])


# ============================================================
# HID communication
# ============================================================

def send_feature(fd, data):

    buf = bytearray(33)
    buf[:len(data)] = data

    ret = fcntl.ioctl(
        fd,
        HIDIOCSFEATURE(33),
        buf,
        True
    )

    if ret != 33:
        raise RuntimeError(
            f"SET_FEATURE returned {ret}; expected 33"
        )


def get_report20(fd):

    buf = bytearray(33)
    buf[0] = 0x20

    fcntl.ioctl(
        fd,
        HIDIOCGFEATURE(33),
        buf,
        True
    )

    return bytes(buf)


def verify_controller(fd):

    send_feature(
        fd,
        [0x20, 0xC1, 0x02]
    )

    time.sleep(0.15)

    response = get_report20(fd)

    if response[:4] != bytes(
        [0x20, 0xC1, 0x02, 0x05]
    ):
        raise RuntimeError(
            "ALED0217 handshake mismatch; "
            "expected 20 C1 02 05"
        )

    return response


# ============================================================
# FINAL VERIFIED LIGHT BAR PACKETS
# ============================================================

OFF = [
    0x20, 0x07
]


# Pure Red ~5%
CHARGING_RED = [
    0x20, 0x80, 0x00, GAIN,

    0x0D, 0x00, 0x00,
    0x0D, 0x00, 0x00,
    0x0D, 0x00, 0x00,
    0x0D, 0x00, 0x00,
    0x0D, 0x00, 0x00,
]


# Pure Green ~5%
FULL_GREEN = [
    0x20, 0x80, 0x00, GAIN,

    0x00, 0x0D, 0x00,
    0x00, 0x0D, 0x00,
    0x00, 0x0D, 0x00,
    0x00, 0x0D, 0x00,
    0x00, 0x0D, 0x00,
]


# Blue-Cyan ~20%, deliberately more blue than white.
PERFORMANCE_CYAN = [
    0x20, 0x80, 0x00, GAIN,

    0x00, 0x1A, 0x33,
    0x06, 0x22, 0x33,
    0x0A, 0x26, 0x33,
    0x06, 0x22, 0x33,
    0x00, 0x1A, 0x33,
]


# ============================================================
# Base state
# ============================================================

def determine_base_state():

    ac = read_text(AC_PATH)
    status = read_text(BAT_STATUS)
    capacity = read_capacity()

    # Absolutely no persistent charging/full color without AC.
    if ac != "1":
        return "OFF", OFF, ac, status, capacity

    # AC connected and battery complete.
    if capacity >= 100:
        return (
            "FULL_GREEN_5",
            FULL_GREEN,
            ac,
            status,
            capacity
        )

    # AC connected, below 100%, actively charging.
    if (
        0 <= capacity < 100
        and status == "Charging"
    ):
        return (
            "CHARGING_RED_5",
            CHARGING_RED,
            ac,
            status,
            capacity
        )

    # Unknown/intermediate state: do not invent a color.
    return "OFF", OFF, ac, status, capacity


def apply_base_state(fd):

    (
        name,
        packet,
        ac,
        status,
        capacity
    ) = determine_base_state()

    send_feature(fd, packet)

    log(
        f"[BASE] "
        f"AC={ac} "
        f"BAT={status} "
        f"CAP={capacity}% "
        f"=> {name}"
    )

    return name


# ============================================================
# One controller session
# ============================================================

def controller_session():

    node = locate_device()

    log(f"[DEVICE] {node}")

    fd = os.open(
        node,
        os.O_RDWR | os.O_CLOEXEC
    )

    try:

        response = verify_controller(fd)

        log(
            "[HANDSHAKE] "
            + " ".join(
                f"{x:02X}"
                for x in response[:4]
            )
        )

        # Apply current AC/battery state immediately.
        last_base = apply_base_state(fd)

        # Important:
        # Starting while already in Performance does NOT
        # generate a blue/cyan flash.
        last_profile = read_text(PROFILE_PATH)

        log(
            f"[PROFILE] initial={last_profile}"
        )

        while not stop_requested:

            sleep_interruptible(POLL_INTERVAL)

            if stop_requested:
                break

            # -----------------------------------------------
            # AC / Battery changes
            # -----------------------------------------------

            (
                current_base,
                _,
                _,
                _,
                _
            ) = determine_base_state()

            if current_base != last_base:

                last_base = apply_base_state(fd)

            # -----------------------------------------------
            # KDE/Fedora platform profile changes
            # -----------------------------------------------

            profile = read_text(PROFILE_PATH)

            if profile != last_profile:

                log(
                    f"[PROFILE] "
                    f"{last_profile} -> {profile}"
                )

                # Cyan ONLY on entering performance.
                if (
                    profile == "performance"
                    and
                    last_profile != "performance"
                ):

                    log(
                        "[LIGHTBAR] "
                        "Performance activated "
                        "=> BLUE-CYAN for 3 seconds"
                    )

                    send_feature(
                        fd,
                        PERFORMANCE_CYAN
                    )

                    sleep_interruptible(
                        PERFORMANCE_SECONDS
                    )

                    if stop_requested:
                        break

                    # Re-read current AC/battery state after
                    # the three-second indication.
                    last_base = apply_base_state(fd)

                last_profile = profile

    finally:

        # Try to leave the strip off whenever this particular
        # controller session ends.
        try:
            send_feature(fd, OFF)
        except Exception:
            pass

        try:
            os.close(fd)
        except Exception:
            pass


# ============================================================
# Daemon main loop
# ============================================================

def main():

    log(
        "ASUS ExpertBook Light Bar service starting"
    )

    while not stop_requested:

        try:

            controller_session()

        except Exception as e:

            if stop_requested:
                break

            log(
                f"[ERROR] {e}"
            )

            log(
                f"[RECONNECT] retry in "
                f"{RECONNECT_SECONDS:.0f}s"
            )

            sleep_interruptible(
                RECONNECT_SECONDS
            )

    log(
        "ASUS ExpertBook Light Bar service stopped"
    )


if __name__ == "__main__":
    main()
