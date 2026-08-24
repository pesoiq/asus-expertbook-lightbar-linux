#!/usr/bin/env python3

import colorsys
import fcntl
import glob
import grp
import math
import os
import queue
import signal
import socket
import threading
import time

# ============================================================
# ASUS ExpertBook B9400CBA / B9450CBA Light Bar v2
#
# Charging pattern selection:
#   1 = Liquid Rainbow v0.2 video-dither
#   2 = Center Bloom
#   3 = Hard-edge constant-luminance flow
#   4 = Hardware Effect 14
#   5 = Static Red (v1 behavior)
#
# Global state:
#   AC disconnected -> OFF
#   AC + battery >= 100 -> static green
#   AC + Charging + battery < 100 -> selected charging pattern
#   Enter performance -> cyan for 3 seconds, then restore
#   Desktop notification -> dim yellow for 1 second, then restore
#
# Pattern choice is persisted in /var/lib and survives reboot.
# ============================================================

REPORT_SIZE = 33
REPORT_ID = 0x20
RGB_GAIN = 0x20
ZONE_COUNT = 5

AC_PATH = "/sys/class/power_supply/AC0/online"
BAT_STATUS = "/sys/class/power_supply/BAT0/status"
BAT_CAPACITY = "/sys/class/power_supply/BAT0/capacity"
PROFILE_PATH = "/sys/firmware/acpi/platform_profile"

STATE_FILE = "/var/lib/asus-expertbook-lightbar/pattern"
SOCKET_PATH = "/run/asus-expertbook-lightbar/control.sock"

POLL_INTERVAL = 0.25
FRAME_INTERVAL = 1.0 / 60.0
RECONNECT_SECONDS = 2.0
PERFORMANCE_SECONDS = 3.0
NOTIFICATION_SECONDS = 1.0

HW_BRIGHTNESS_DIRECT = 32
HW_BRIGHTNESS_ANIM = 1

PATTERN_NAMES = {
    1: "Liquid Rainbow v0.2 Video Dither",
    2: "Center Bloom",
    3: "Hard-edge Constant-Luminance Flow",
    4: "Hardware Effect 14",
    5: "Static Red v1",
}

# Exact v1 static packets.
OFF = [0x20, 0x07]

CHARGING_RED = [
    0x20, 0x80, 0x00, RGB_GAIN,
    0x0D, 0x00, 0x00,
    0x0D, 0x00, 0x00,
    0x0D, 0x00, 0x00,
    0x0D, 0x00, 0x00,
    0x0D, 0x00, 0x00,
]

FULL_GREEN = [
    0x20, 0x80, 0x00, RGB_GAIN,
    0x00, 0x0D, 0x00,
    0x00, 0x0D, 0x00,
    0x00, 0x0D, 0x00,
    0x00, 0x0D, 0x00,
    0x00, 0x0D, 0x00,
]

PERFORMANCE_CYAN = [
    0x20, 0x80, 0x00, RGB_GAIN,
    0x00, 0x1A, 0x33,
    0x06, 0x22, 0x33,
    0x0A, 0x26, 0x33,
    0x06, 0x22, 0x33,
    0x00, 0x1A, 0x33,
]

NOTIFICATION_YELLOW = [
    0x20, 0x80, 0x00, RGB_GAIN,
    0x06, 0x06, 0x00,
    0x06, 0x06, 0x00,
    0x06, 0x06, 0x00,
    0x06, 0x06, 0x00,
    0x06, 0x06, 0x00,
]

# Hardware Effect 14.
EFFECT14_INFINITE = [0x20, 0x02, 0x02]
EFFECT14_START = [0x20, 0x01, 0x0E]

# ============================================================
# Pattern 1 - exact uploaded Liquid Rainbow v0.2 video-dither
# ============================================================

P1_TARGET_LEVEL = 0.12
P1_VIDEO_FLOOR = True
P1_CYCLE_SECONDS = 19.0
P1_HUE_SPAN_DEG = 185.0
P1_SAMPLES_PER_ZONE = 81
P1_SAMPLE_RADIUS = 0.27
P1_GAUSSIAN_SIGMA = 0.105
P1_NEIGHBOR_HUE_BLEND = 0.14
P1_SMOOTHING_TC = 0.070
P1_SATURATION = 1.0
P1_VALUE = 1.0
P1_RED_GAIN = 1.00
P1_GREEN_GAIN = 1.00
P1_BLUE_GAIN = 0.70
P1_RED_ANCHOR = 0.0
P1_RED_WIDTH = 38.0
P1_RED_STRENGTH = 0.30
P1_GREEN_ANCHOR = 120.0
P1_GREEN_WIDTH = 34.0
P1_GREEN_STRENGTH = 0.27
P1_DITHER_SEQUENCE = (0, 4, 2, 6, 1, 5, 3, 7)

# ============================================================
# Pattern 2 - exact uploaded Center Bloom
# ============================================================

P2_SOFTWARE_LEVEL = 0.20
P2_CENTER_COLOR_CYCLE = 18.0
P2_EDGE_TRAVEL_SECONDS = 3.20
P2_RADIAL_EXPONENT = 1.30
P2_WAVE_A_DEG = 6.0
P2_WAVE_B_DEG = 2.5
P2_SAMPLES_PER_ZONE = 101
P2_SAMPLE_RADIUS = 0.26
P2_GAUSSIAN_SIGMA = 0.100
P2_NEIGHBOR_HUE_BLEND = 0.10
P2_SMOOTHING_TC = 0.060
P2_SATURATION = 1.0
P2_VALUE = 1.0
P2_RED_GAIN = 1.00
P2_GREEN_GAIN = 1.00
P2_BLUE_GAIN = 0.70
P2_RED_ANCHOR = 0.0
P2_RED_WIDTH = 38.0
P2_RED_STRENGTH = 0.30
P2_GREEN_ANCHOR = 120.0
P2_GREEN_WIDTH = 34.0
P2_GREEN_STRENGTH = 0.27

# ============================================================
# Pattern 3 - exact uploaded Hard-edge constant-luminance flow
# ============================================================

P3_SOFTWARE_LEVEL = 0.20
P3_ZONE_DELAY = 0.24
P3_COLOR_PERIOD = 1.20
P3_PALETTE = (0.0, 55.0, 120.0, 180.0, 235.0, 300.0)
P3_SATURATION = 1.0
P3_VALUE = 1.0
P3_RED_GAIN = 1.00
P3_GREEN_GAIN = 1.00
P3_BLUE_GAIN = 0.70

TAU = math.tau

# ============================================================
# Globals / synchronization
# ============================================================

stop_requested = False
state_lock = threading.Lock()
selected_pattern = 5
notification_sequence = 0

runtime_status = {
    "mode": "STARTING",
    "ac": "",
    "battery_status": "",
    "capacity": -1,
    "profile": "",
}

# ============================================================
# Signals / logging
# ============================================================

def log(message):
    print(message, flush=True)


def signal_handler(signum, frame):
    global stop_requested
    stop_requested = True


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# ============================================================
# HID ioctl
# ============================================================

IOC_TYPESHIFT = 8
IOC_SIZESHIFT = 16
IOC_DIRSHIFT = 30
IOC_WRITE = 1
IOC_READ = 2


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
# Generic helpers
# ============================================================

def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


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


def sleep_interruptible(seconds):
    deadline = time.monotonic() + seconds
    while not stop_requested:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.1, remaining))

# ============================================================
# Persistent pattern state
# ============================================================

def load_pattern():
    try:
        value = int(read_text(STATE_FILE))
        if value in PATTERN_NAMES:
            return value
    except Exception:
        pass
    return 5


def save_pattern(value):
    directory = os.path.dirname(STATE_FILE)
    os.makedirs(directory, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write(f"{value}\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE_FILE)

# ============================================================
# Controller discovery / HID
# ============================================================

def locate_device():
    devices = glob.glob("/sys/bus/hid/devices/0018:0B05:0124.*")

    if len(devices) != 1:
        raise RuntimeError(
            f"ALED0217 0B05:0124 unavailable (found {len(devices)})"
        )

    dev = devices[0]

    with open(os.path.join(dev, "report_descriptor"), "rb") as f:
        descriptor = f.read()

    signature = bytes([
        0x06, 0xB5, 0xFF,
        0x09, 0xA0,
        0xA1, 0x01,
        0x85, 0x20,
    ])

    if signature not in descriptor:
        raise RuntimeError("ALED0217 descriptor mismatch")

    nodes = glob.glob(os.path.join(dev, "hidraw", "hidraw*"))

    if len(nodes) != 1:
        raise RuntimeError(f"ALED0217 hidraw unavailable (found {len(nodes)})")

    return "/dev/" + os.path.basename(nodes[0])


def send_feature(fd, data):
    buf = bytearray(REPORT_SIZE)
    buf[:len(data)] = bytes(data)

    result = fcntl.ioctl(
        fd,
        HIDIOCSFEATURE(REPORT_SIZE),
        buf,
        True,
    )

    if result != REPORT_SIZE:
        raise RuntimeError(
            f"HID SET_FEATURE returned {result}; expected {REPORT_SIZE}"
        )


def get_report20(fd):
    buf = bytearray(REPORT_SIZE)
    buf[0] = REPORT_ID

    fcntl.ioctl(
        fd,
        HIDIOCGFEATURE(REPORT_SIZE),
        buf,
        True,
    )

    return bytes(buf)


def verify_controller(fd):
    send_feature(fd, [REPORT_ID, 0xC1, 0x02])
    time.sleep(0.15)
    response = get_report20(fd)

    if response[:4] != bytes([0x20, 0xC1, 0x02, 0x05]):
        got = " ".join(f"{x:02X}" for x in response[:4])
        raise RuntimeError(f"ALED0217 handshake mismatch: {got}")

    return response


def open_controller():
    node = locate_device()
    fd = os.open(node, os.O_RDWR | os.O_CLOEXEC)
    response = verify_controller(fd)
    log(
        f"[DEVICE] {node} "
        f"[HANDSHAKE] {' '.join(f'{x:02X}' for x in response[:4])}"
    )
    return fd


def set_hw_brightness(fd, value):
    if not 1 <= value <= 32:
        raise ValueError("hardware brightness must be 1..32")
    send_feature(fd, [REPORT_ID, 0x04, value])

# ============================================================
# Hardware Effect 14 reset path
# ============================================================

def locate_i2c_driver_device():
    matches = glob.glob(
        "/sys/bus/i2c/drivers/i2c_hid_acpi/*ALED0217*"
    )
    matches = [
        p for p in matches
        if os.path.basename(p) not in ("bind", "unbind")
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"ALED0217 i2c_hid_acpi device not unique (found {len(matches)})"
        )
    return os.path.basename(matches[0])


def reset_after_effect14(fd):
    devname = locate_i2c_driver_device()

    try:
        os.close(fd)
    except Exception:
        pass

    log(f"[RESET] leaving Effect 14 via i2c_hid_acpi rebind ({devname})")

    with open("/sys/bus/i2c/drivers/i2c_hid_acpi/unbind", "w") as f:
        f.write(devname)

    # Proven stable timing on the physical B9400CBA:
    # allow the ALED0217 controller to fully detach.
    time.sleep(2.00)

    with open("/sys/bus/i2c/drivers/i2c_hid_acpi/bind", "w") as f:
        f.write(devname)

    # The HID node can reappear before the controller has
    # completely finished its internal reset. The physical
    # hardware test required this stabilization interval
    # before sending direct RGB again.
    time.sleep(3.00)

    deadline = time.monotonic() + 5.0
    last_error = None

    while time.monotonic() < deadline and not stop_requested:
        try:
            return open_controller()
        except Exception as exc:
            last_error = exc
            time.sleep(0.10)

    raise RuntimeError(
        f"ALED0217 did not reappear after Effect 14 reset: {last_error}"
    )

# ============================================================
# Circular hue helpers shared by patterns 1 / 2
# ============================================================

def circular_difference(a, b):
    return ((b - a + 180.0) % 360.0) - 180.0


def circular_blend(a, b, amount):
    amount = clamp(amount)
    return (a + circular_difference(a, b) * amount) % 360.0


def circular_distance(a, b):
    return abs(circular_difference(a, b))


def circular_mean(samples):
    x = 0.0
    y = 0.0
    total = 0.0

    for hue, weight in samples:
        angle = math.radians(hue)
        x += math.cos(angle) * weight
        y += math.sin(angle) * weight
        total += weight

    if total <= 0.0:
        return 0.0

    return math.degrees(math.atan2(y / total, x / total)) % 360.0

# ============================================================
# Pattern 1 renderer
# ============================================================

def p1_anchor_weight(hue, anchor, width):
    distance = circular_distance(hue, anchor)
    return math.exp(-0.5 * (distance / width) ** 2)


def p1_enrich(hue):
    red_weight = (
        P1_RED_STRENGTH
        * p1_anchor_weight(hue, P1_RED_ANCHOR, P1_RED_WIDTH)
    )
    hue = circular_blend(hue, P1_RED_ANCHOR, red_weight)

    green_weight = (
        P1_GREEN_STRENGTH
        * p1_anchor_weight(hue, P1_GREEN_ANCHOR, P1_GREEN_WIDTH)
    )
    return circular_blend(hue, P1_GREEN_ANCHOR, green_weight)


def p1_hue_field(x, t):
    base = 360.0 * t / P1_CYCLE_SECONDS
    spatial = P1_HUE_SPAN_DEG * x

    wave_a = 15.0 * math.sin(
        TAU * (x * 0.77 - t / (P1_CYCLE_SECONDS * 1.65))
    )
    wave_b = 7.0 * math.sin(
        TAU * (x * 1.33 + t / (P1_CYCLE_SECONDS * 2.60))
    )
    wave_c = 3.0 * math.sin(
        TAU * (x * 2.07 - t / (P1_CYCLE_SECONDS * 3.35))
    )

    return p1_enrich((base + spatial + wave_a + wave_b + wave_c) % 360.0)


def p1_gaussian(distance):
    return math.exp(
        -0.5 * (distance / P1_GAUSSIAN_SIGMA) ** 2
    )


def p1_render_zone_hue(zone, t):
    center = (zone + 0.5) / ZONE_COUNT
    samples = []

    for i in range(P1_SAMPLES_PER_ZONE):
        fraction = i / (P1_SAMPLES_PER_ZONE - 1)
        offset = (
            -P1_SAMPLE_RADIUS
            + 2.0 * P1_SAMPLE_RADIUS * fraction
        )
        x = center + offset
        samples.append((p1_hue_field(x, t), p1_gaussian(offset)))

    return circular_mean(samples)


def p1_render_hues(t):
    raw = [
        p1_render_zone_hue(zone, t)
        for zone in range(ZONE_COUNT)
    ]

    output = []

    for i in range(ZONE_COUNT):
        hue = raw[i]

        if i > 0:
            hue = circular_blend(
                hue, raw[i - 1], P1_NEIGHBOR_HUE_BLEND
            )

        if i < ZONE_COUNT - 1:
            hue = circular_blend(
                hue, raw[i + 1], P1_NEIGHBOR_HUE_BLEND
            )

        output.append(p1_enrich(hue))

    return output


def p1_temporal_alpha(dt):
    if dt <= 0.0:
        return 1.0
    return 1.0 - math.exp(-dt / P1_SMOOTHING_TC)


def p1_saturated_rgb(hue):
    return colorsys.hsv_to_rgb(
        hue / 360.0,
        P1_SATURATION,
        P1_VALUE,
    )


def p1_dither_channel(source, frame, zone, channel):
    source_255 = clamp(source) * 255.0
    desired = source_255 * P1_TARGET_LEVEL

    base = math.floor(desired)
    fraction = desired - base

    phase_offset = (zone * 3 + channel * 5) & 7
    phase = (frame + phase_offset) & 7

    threshold = (P1_DITHER_SEQUENCE[phase] + 0.5) / 8.0

    value = int(base)

    if fraction > threshold:
        value += 1

    if (
        P1_VIDEO_FLOOR
        and source_255 > 0.5
        and desired > 0.0
        and value == 0
    ):
        value = 1

    return max(0, min(255, value))


def p1_encode_zone(rgb, frame, zone):
    r, g, b = rgb

    r *= P1_RED_GAIN
    g *= P1_GREEN_GAIN
    b *= P1_BLUE_GAIN

    peak = max(r, g, b, 1.0)

    if peak > 1.0:
        r /= peak
        g /= peak
        b /= peak

    return (
        p1_dither_channel(r, frame, zone, 0),
        p1_dither_channel(g, frame, zone, 1),
        p1_dither_channel(b, frame, zone, 2),
    )


def p1_build_packet(hues, frame):
    packet = [REPORT_ID, 0x80, 0x00, RGB_GAIN]

    for zone, hue in enumerate(hues):
        packet.extend(
            p1_encode_zone(p1_saturated_rgb(hue), frame, zone)
        )

    while len(packet) < REPORT_SIZE:
        packet.append(0)

    return packet

# ============================================================
# Pattern 2 renderer
# ============================================================

def p2_anchor_weight(hue, anchor, width):
    distance = circular_distance(hue, anchor)
    return math.exp(-0.5 * (distance / width) ** 2)


def p2_enrich(hue):
    red_weight = (
        P2_RED_STRENGTH
        * p2_anchor_weight(hue, P2_RED_ANCHOR, P2_RED_WIDTH)
    )
    hue = circular_blend(hue, P2_RED_ANCHOR, red_weight)

    green_weight = (
        P2_GREEN_STRENGTH
        * p2_anchor_weight(hue, P2_GREEN_ANCHOR, P2_GREEN_WIDTH)
    )
    return circular_blend(hue, P2_GREEN_ANCHOR, green_weight)


def p2_radial_distance(x):
    return clamp(abs(x - 0.5) * 2.0)


def p2_propagation_delay(x):
    return (
        P2_EDGE_TRAVEL_SECONDS
        * (p2_radial_distance(x) ** P2_RADIAL_EXPONENT)
    )


def p2_center_bloom_hue(x, t):
    local_t = t - p2_propagation_delay(x)
    base_hue = 360.0 * local_t / P2_CENTER_COLOR_CYCLE
    r = p2_radial_distance(x)

    wave_a = P2_WAVE_A_DEG * math.sin(
        TAU
        * (
            local_t / (P2_CENTER_COLOR_CYCLE * 1.45)
            + r * 0.65
        )
    )

    wave_b = P2_WAVE_B_DEG * math.sin(
        TAU
        * (
            local_t / (P2_CENTER_COLOR_CYCLE * 2.30)
            - r * 1.20
        )
    )

    return p2_enrich((base_hue + wave_a + wave_b) % 360.0)


def p2_gaussian(distance):
    return math.exp(
        -0.5 * (distance / P2_GAUSSIAN_SIGMA) ** 2
    )


def p2_render_zone_hue(zone, t):
    center = (zone + 0.5) / ZONE_COUNT
    samples = []

    for i in range(P2_SAMPLES_PER_ZONE):
        fraction = i / (P2_SAMPLES_PER_ZONE - 1)
        offset = (
            -P2_SAMPLE_RADIUS
            + 2.0 * P2_SAMPLE_RADIUS * fraction
        )
        x = center + offset
        samples.append((p2_center_bloom_hue(x, t), p2_gaussian(offset)))

    return circular_mean(samples)


def p2_render_hues(t):
    raw = [
        p2_render_zone_hue(zone, t)
        for zone in range(ZONE_COUNT)
    ]

    output = []

    for i in range(ZONE_COUNT):
        hue = raw[i]

        if i > 0:
            hue = circular_blend(
                hue, raw[i - 1], P2_NEIGHBOR_HUE_BLEND
            )

        if i < ZONE_COUNT - 1:
            hue = circular_blend(
                hue, raw[i + 1], P2_NEIGHBOR_HUE_BLEND
            )

        output.append(p2_enrich(hue))

    inner = circular_mean([(output[1], 1.0), (output[3], 1.0)])
    outer = circular_mean([(output[0], 1.0), (output[4], 1.0)])

    return [outer, inner, output[2], inner, outer]


def p2_temporal_alpha(dt):
    if dt <= 0.0:
        return 1.0
    return 1.0 - math.exp(-dt / P2_SMOOTHING_TC)


def p2_saturated_rgb(hue):
    return colorsys.hsv_to_rgb(
        hue / 360.0,
        P2_SATURATION,
        P2_VALUE,
    )


def p2_encode_rgb(rgb):
    r, g, b = rgb

    r *= P2_RED_GAIN
    g *= P2_GREEN_GAIN
    b *= P2_BLUE_GAIN

    peak = max(r, g, b, 1.0)

    if peak > 1.0:
        r /= peak
        g /= peak
        b /= peak

    scale = 255.0 * P2_SOFTWARE_LEVEL

    return (
        int(round(clamp(r) * scale)),
        int(round(clamp(g) * scale)),
        int(round(clamp(b) * scale)),
    )


def p2_build_packet(hues):
    packet = [REPORT_ID, 0x80, 0x00, RGB_GAIN]

    for hue in hues:
        packet.extend(p2_encode_rgb(p2_saturated_rgb(hue)))

    while len(packet) < REPORT_SIZE:
        packet.append(0)

    return packet

# ============================================================
# Pattern 3 renderer
# ============================================================

def p3_pure_rgb(hue):
    return colorsys.hsv_to_rgb(
        hue / 360.0,
        P3_SATURATION,
        P3_VALUE,
    )


def p3_encode_rgb(rgb):
    r, g, b = rgb

    r *= P3_RED_GAIN
    g *= P3_GREEN_GAIN
    b *= P3_BLUE_GAIN

    peak = max(r, g, b, 1.0)

    if peak > 1.0:
        r /= peak
        g /= peak
        b /= peak

    scale = 255.0 * P3_SOFTWARE_LEVEL

    return (
        int(round(clamp(r) * scale)),
        int(round(clamp(g) * scale)),
        int(round(clamp(b) * scale)),
    )


def p3_zone_palette_index(zone, t):
    distance_from_right = (ZONE_COUNT - 1) - zone
    local_time = t - distance_from_right * P3_ZONE_DELAY
    return math.floor(local_time / P3_COLOR_PERIOD) % len(P3_PALETTE)


def p3_build_packet(t):
    packet = [REPORT_ID, 0x80, 0x00, RGB_GAIN]

    for zone in range(ZONE_COUNT):
        hue = P3_PALETTE[p3_zone_palette_index(zone, t)]
        packet.extend(p3_encode_rgb(p3_pure_rgb(hue)))

    while len(packet) < REPORT_SIZE:
        packet.append(0)

    return packet

# ============================================================
# Control socket
# ============================================================

def control_server():
    global selected_pattern, notification_sequence

    try:
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(SOCKET_PATH)

        wheel_gid = grp.getgrnam("wheel").gr_gid
        os.chown(SOCKET_PATH, 0, wheel_gid)
        os.chmod(SOCKET_PATH, 0o660)

        server.listen(8)
        server.settimeout(0.5)

        log(f"[CONTROL] socket ready: {SOCKET_PATH}")

        while not stop_requested:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                if stop_requested:
                    break
                raise

            with conn:
                try:
                    raw = conn.recv(512)
                    command = raw.decode("utf-8", errors="replace").strip()

                    if command in {"1", "2", "3", "4", "5"}:
                        value = int(command)
                        save_pattern(value)

                        with state_lock:
                            selected_pattern = value

                        response = (
                            f"OK pattern={value} "
                            f"name={PATTERN_NAMES[value]}\n"
                        )

                    elif command == "notify":
                        with state_lock:
                            notification_sequence += 1
                        response = "OK notification queued\n"

                    elif command == "status":
                        with state_lock:
                            p = selected_pattern
                            status = dict(runtime_status)

                        response = (
                            f"pattern={p}\n"
                            f"name={PATTERN_NAMES[p]}\n"
                            f"mode={status['mode']}\n"
                            f"ac={status['ac']}\n"
                            f"battery_status={status['battery_status']}\n"
                            f"capacity={status['capacity']}\n"
                            f"profile={status['profile']}\n"
                        )

                    elif command == "list":
                        response = "".join(
                            f"{i}: {PATTERN_NAMES[i]}\n"
                            for i in sorted(PATTERN_NAMES)
                        )

                    else:
                        response = (
                            "ERROR usage: lightbarctl "
                            "{1|2|3|4|5|status|list}\n"
                        )

                    conn.sendall(response.encode("utf-8"))

                except Exception as exc:
                    try:
                        conn.sendall(
                            f"ERROR {exc}\n".encode("utf-8")
                        )
                    except Exception:
                        pass

    except Exception as exc:
        log(f"[CONTROL-ERROR] {exc}")

    finally:
        try:
            server.close()
        except Exception:
            pass

        try:
            if os.path.exists(SOCKET_PATH):
                os.unlink(SOCKET_PATH)
        except Exception:
            pass

# ============================================================
# Base-state decision
# ============================================================

def read_base_state(pattern):
    ac = read_text(AC_PATH)
    status = read_text(BAT_STATUS)
    capacity = read_capacity()

    if ac != "1":
        return "OFF", ac, status, capacity

    if capacity >= 100:
        return "FULL_GREEN", ac, status, capacity

    if 0 <= capacity < 100 and status == "Charging":
        return f"PATTERN_{pattern}", ac, status, capacity

    return "OFF", ac, status, capacity

# ============================================================
# Mode transitions / animation
# ============================================================

def enter_mode(fd, old_mode, new_mode, now):
    # Effect 14 ignores direct RGB until its controller state is reset.
    if old_mode == "PATTERN_4" and new_mode != "PATTERN_4":
        fd = reset_after_effect14(fd)

    anim = None

    if new_mode == "OFF":
        set_hw_brightness(fd, HW_BRIGHTNESS_DIRECT)
        send_feature(fd, OFF)

    elif new_mode == "FULL_GREEN":
        set_hw_brightness(fd, HW_BRIGHTNESS_DIRECT)
        send_feature(fd, FULL_GREEN)

    elif new_mode == "PERFORMANCE":
        set_hw_brightness(fd, HW_BRIGHTNESS_DIRECT)
        send_feature(fd, PERFORMANCE_CYAN)

    elif new_mode == "NOTIFICATION":
        set_hw_brightness(fd, HW_BRIGHTNESS_DIRECT)
        send_feature(fd, NOTIFICATION_YELLOW)

    elif new_mode == "PATTERN_1":
        set_hw_brightness(fd, HW_BRIGHTNESS_ANIM)
        hues = p1_render_hues(0.0)
        anim = {
            "start": now,
            "previous": now,
            "frame": 0,
            "hues": hues,
        }
        send_feature(fd, p1_build_packet(hues, 0))

    elif new_mode == "PATTERN_2":
        set_hw_brightness(fd, HW_BRIGHTNESS_ANIM)
        hues = p2_render_hues(0.0)
        anim = {
            "start": now,
            "previous": now,
            "frame": 0,
            "hues": hues,
        }
        send_feature(fd, p2_build_packet(hues))

    elif new_mode == "PATTERN_3":
        set_hw_brightness(fd, HW_BRIGHTNESS_ANIM)
        anim = {
            "start": now,
            "previous": now,
            "frame": 0,
        }
        send_feature(fd, p3_build_packet(0.0))

    elif new_mode == "PATTERN_4":
        set_hw_brightness(fd, HW_BRIGHTNESS_ANIM)
        send_feature(fd, EFFECT14_INFINITE)
        send_feature(fd, EFFECT14_START)

    elif new_mode == "PATTERN_5":
        set_hw_brightness(fd, HW_BRIGHTNESS_DIRECT)
        send_feature(fd, CHARGING_RED)

    else:
        raise RuntimeError(f"Unknown light bar mode: {new_mode}")

    log(f"[MODE] {old_mode} -> {new_mode}")
    return fd, anim


def animate_mode(fd, mode, anim, now):
    if mode == "PATTERN_1":
        elapsed = now - anim["start"]
        dt = now - anim["previous"]
        anim["previous"] = now

        targets = p1_render_hues(elapsed)
        alpha = p1_temporal_alpha(dt)

        anim["hues"] = [
            circular_blend(old, target, alpha)
            for old, target in zip(anim["hues"], targets)
        ]

        frame = anim["frame"]
        send_feature(
            fd,
            p1_build_packet(anim["hues"], frame),
        )
        anim["frame"] = frame + 1

    elif mode == "PATTERN_2":
        elapsed = now - anim["start"]
        dt = now - anim["previous"]
        anim["previous"] = now

        targets = p2_render_hues(elapsed)
        alpha = p2_temporal_alpha(dt)

        anim["hues"] = [
            circular_blend(old, target, alpha)
            for old, target in zip(anim["hues"], targets)
        ]

        send_feature(fd, p2_build_packet(anim["hues"]))
        anim["frame"] += 1

    elif mode == "PATTERN_3":
        elapsed = now - anim["start"]
        send_feature(fd, p3_build_packet(elapsed))
        anim["frame"] += 1

# ============================================================
# One hardware session
# ============================================================

def controller_session():
    global runtime_status

    fd = open_controller()
    current_mode = None
    anim = None

    now = time.monotonic()

    with state_lock:
        pattern = selected_pattern
        seen_notification_sequence = notification_sequence

    base_mode, ac, battery_status, capacity = read_base_state(pattern)

    last_profile = read_text(PROFILE_PATH)
    performance_until = 0.0
    notification_until = 0.0
    pending_notification = False

    last_poll = 0.0
    next_frame = now

    try:
        while not stop_requested:
            now = time.monotonic()

            with state_lock:
                pattern = selected_pattern
                current_notification_sequence = notification_sequence

            # A new notification request.
            if current_notification_sequence != seen_notification_sequence:
                seen_notification_sequence = current_notification_sequence

                if now < performance_until:
                    pending_notification = True
                else:
                    notification_until = max(
                        notification_until,
                        now + NOTIFICATION_SECONDS,
                    )

            # AC / battery / profile polling.
            if now - last_poll >= POLL_INTERVAL:
                last_poll = now

                base_mode, ac, battery_status, capacity = read_base_state(
                    pattern
                )

                profile = read_text(PROFILE_PATH)

                if profile != last_profile:
                    log(f"[PROFILE] {last_profile} -> {profile}")

                    if (
                        profile == "performance"
                        and last_profile != "performance"
                    ):
                        if now < notification_until:
                            pending_notification = True
                            notification_until = 0.0

                        performance_until = (
                            now + PERFORMANCE_SECONDS
                        )

                        log(
                            "[LIGHTBAR] Performance activated "
                            "=> BLUE-CYAN for 3 seconds"
                        )

                    last_profile = profile

                with state_lock:
                    runtime_status.update({
                        "ac": ac,
                        "battery_status": battery_status,
                        "capacity": capacity,
                        "profile": profile,
                    })

            # Deliver one deferred notification after performance.
            if (
                pending_notification
                and now >= performance_until
            ):
                pending_notification = False
                notification_until = (
                    now + NOTIFICATION_SECONDS
                )

            # Priority: performance > notification > base.
            if now < performance_until:
                target_mode = "PERFORMANCE"
            elif now < notification_until:
                target_mode = "NOTIFICATION"
            else:
                # Refresh base mode immediately when terminal changes pattern.
                base_mode, ac, battery_status, capacity = read_base_state(
                    pattern
                )
                target_mode = base_mode

            if target_mode != current_mode:
                fd, anim = enter_mode(
                    fd,
                    current_mode,
                    target_mode,
                    now,
                )
                current_mode = target_mode
                next_frame = now

                with state_lock:
                    runtime_status["mode"] = current_mode

            # 60 FPS only for the three software-rendered patterns.
            if (
                current_mode in {"PATTERN_1", "PATTERN_2", "PATTERN_3"}
                and now >= next_frame
            ):
                animate_mode(fd, current_mode, anim, now)

                # Keep a monotonic 60 Hz schedule.
                next_frame += FRAME_INTERVAL

                if next_frame < now - FRAME_INTERVAL:
                    next_frame = now + FRAME_INTERVAL

            # Static / hardware modes need no 60 Hz traffic.
            if current_mode in {"PATTERN_1", "PATTERN_2", "PATTERN_3"}:
                sleep_for = max(
                    0.001,
                    min(0.010, next_frame - time.monotonic()),
                )
            else:
                sleep_for = 0.020

            time.sleep(sleep_for)

    finally:
        # If Effect 14 is active, a plain OFF is not enough.
        try:
            if current_mode == "PATTERN_4":
                fd = reset_after_effect14(fd)
        except Exception:
            pass

        try:
            set_hw_brightness(fd, HW_BRIGHTNESS_DIRECT)
            send_feature(fd, OFF)
        except Exception:
            pass

        try:
            os.close(fd)
        except Exception:
            pass

# ============================================================
# Main
# ============================================================

def main():
    global selected_pattern

    selected_pattern = load_pattern()

    # Guarantee a persistent initial state. v1 red is the safe default.
    try:
        save_pattern(selected_pattern)
    except Exception as exc:
        log(f"[STATE-ERROR] cannot persist initial pattern: {exc}")

    log("ASUS ExpertBook Light Bar v2 starting")
    log(
        f"[STATE] selected pattern={selected_pattern} "
        f"({PATTERN_NAMES[selected_pattern]})"
    )

    control_thread = threading.Thread(
        target=control_server,
        name="lightbar-control",
        daemon=True,
    )
    control_thread.start()

    while not stop_requested:
        try:
            controller_session()
        except Exception as exc:
            if stop_requested:
                break

            log(f"[ERROR] {exc}")

            with state_lock:
                runtime_status["mode"] = "RECONNECTING"

            log(
                f"[RECONNECT] retry in {RECONNECT_SECONDS:.0f}s"
            )
            sleep_interruptible(RECONNECT_SECONDS)

    log("ASUS ExpertBook Light Bar v2 stopped")


if __name__ == "__main__":
    main()
