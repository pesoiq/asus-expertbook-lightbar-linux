#!/usr/bin/env bash
set -euo pipefail

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "Run as root: sudo ./install.sh"
    exit 1
fi

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$ROOT/src/asus-expertbook-lightbar.py"
UNIT="$ROOT/system/asus-expertbook-lightbar.service"

PRODUCT="$(cat /sys/devices/virtual/dmi/id/product_name 2>/dev/null || true)"
case "$PRODUCT" in
    *B9400CBA*|*B9450CBA*) ;;
    *) echo "ERROR: unsupported/unverified laptop product: $PRODUCT"; exit 1 ;;
esac

mapfile -t DEVICES < <(compgen -G '/sys/bus/hid/devices/0018:0B05:0124.*' || true)
if [ "${#DEVICES[@]}" -ne 1 ]; then
    echo "ERROR: expected exactly one ALED0217 0B05:0124 HID device; found ${#DEVICES[@]}"
    exit 1
fi
DEV="${DEVICES[0]}"

python3 - "$DEV/report_descriptor" <<'PY'
import sys
with open(sys.argv[1], 'rb') as f:
    d = f.read()
sig = bytes([0x06,0xB5,0xFF,0x09,0xA0,0xA1,0x01,0x85,0x20])
if sig not in d:
    raise SystemExit('ERROR: HID descriptor does not match FFB5/A0/Report20')
print('Hardware descriptor: MATCH')
PY

for p in \
    /sys/class/power_supply/AC0/online \
    /sys/class/power_supply/BAT0/status \
    /sys/class/power_supply/BAT0/capacity \
    /sys/firmware/acpi/platform_profile
do
    [ -r "$p" ] || { echo "ERROR: required interface missing: $p"; exit 1; }
done

python3 -m py_compile "$SOURCE"

install -d -m 0755 /usr/local/libexec
install -m 0755 "$SOURCE" /usr/local/libexec/asus-expertbook-lightbar
install -m 0644 "$UNIT" /etc/systemd/system/asus-expertbook-lightbar.service

systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/asus-expertbook-lightbar.service
systemctl enable --now asus-expertbook-lightbar.service

echo
systemctl status asus-expertbook-lightbar.service --no-pager -l
