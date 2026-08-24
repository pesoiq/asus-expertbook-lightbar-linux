#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SERVICE="asus-expertbook-lightbar.service"
DAEMON="/usr/local/libexec/asus-expertbook-lightbar"
CTL="/usr/local/bin/lightbarctl"
WATCH="/usr/local/libexec/asus-expertbook-lightbar-notify-watch"
SYSTEM_UNIT="/etc/systemd/system/$SERVICE"
STATE_DIR="/var/lib/asus-expertbook-lightbar"

TARGET_USER="${SUDO_USER:-${USER}}"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
USER_UNIT_DIR="$TARGET_HOME/.config/systemd/user"
USER_UNIT="$USER_UNIT_DIR/asus-expertbook-lightbar-notifications.service"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/var/backups/asus-expertbook-lightbar-before-v2-$STAMP"

sudo -v

for cmd in python3 dbus-monitor systemctl install getent; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: missing command: $cmd"; exit 1; }
done

PRODUCT="$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)"
case "$PRODUCT" in
    *B9400CBA*|*B9450CBA*) ;;
    *) echo "ERROR: unsupported DMI product: $PRODUCT"; exit 2 ;;
esac

python3 -m py_compile "$ROOT/src/asus-expertbook-lightbar.py" "$ROOT/src/lightbarctl.py"
bash -n "$ROOT/src/asus-expertbook-lightbar-notify-watch"
systemd-analyze verify "$ROOT/system/asus-expertbook-lightbar.service" >/dev/null
systemd-analyze --user verify "$ROOT/system/asus-expertbook-lightbar-notifications.service" >/dev/null

sudo install -d -m 0755 "$BACKUP"
for p in "$DAEMON" "$CTL" "$WATCH" "$SYSTEM_UNIT"; do
    if sudo test -e "$p"; then sudo cp -a "$p" "$BACKUP/"; fi
done
if test -e "$USER_UNIT"; then cp -a "$USER_UNIT" "$BACKUP/"; fi
sudo ln -sfn "$BACKUP" /var/backups/asus-expertbook-lightbar-before-v2-latest

sudo systemctl stop "$SERVICE" 2>/dev/null || true
systemctl --user disable --now asus-expertbook-lightbar-notifications.service >/dev/null 2>&1 || true

sudo install -d -m 0755 /usr/local/libexec /usr/local/bin "$STATE_DIR"
sudo install -m 0755 "$ROOT/src/asus-expertbook-lightbar.py" "$DAEMON"
sudo install -m 0755 "$ROOT/src/lightbarctl.py" "$CTL"
sudo install -m 0755 "$ROOT/src/asus-expertbook-lightbar-notify-watch" "$WATCH"
sudo install -m 0644 "$ROOT/system/asus-expertbook-lightbar.service" "$SYSTEM_UNIT"

install -d -m 0755 "$USER_UNIT_DIR"
install -m 0644 "$ROOT/system/asus-expertbook-lightbar-notifications.service" "$USER_UNIT"

if ! sudo test -s "$STATE_DIR/pattern"; then
    echo 5 | sudo tee "$STATE_DIR/pattern" >/dev/null
fi

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE"
systemctl --user daemon-reload
systemctl --user enable --now asus-expertbook-lightbar-notifications.service

printf 'System daemon : '; systemctl is-active "$SERVICE"
printf 'Notification : '; systemctl --user is-active asus-expertbook-lightbar-notifications.service
"$CTL" status

echo "Backup: $BACKUP"
