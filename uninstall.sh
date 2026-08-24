#!/usr/bin/env bash
set -euo pipefail

SERVICE="asus-expertbook-lightbar.service"
USER_UNIT="$HOME/.config/systemd/user/asus-expertbook-lightbar-notifications.service"

systemctl --user disable --now asus-expertbook-lightbar-notifications.service >/dev/null 2>&1 || true
rm -f "$USER_UNIT"
systemctl --user daemon-reload

sudo systemctl disable --now "$SERVICE" >/dev/null 2>&1 || true
sudo rm -f \
  /usr/local/libexec/asus-expertbook-lightbar \
  /usr/local/libexec/asus-expertbook-lightbar-notify-watch \
  /usr/local/bin/lightbarctl \
  /etc/systemd/system/asus-expertbook-lightbar.service
sudo systemctl daemon-reload

echo "Persistent pattern state was left in /var/lib/asus-expertbook-lightbar intentionally."
