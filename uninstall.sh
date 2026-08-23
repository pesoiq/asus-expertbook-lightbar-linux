#!/usr/bin/env bash
set -euo pipefail

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "Run as root: sudo ./uninstall.sh"
    exit 1
fi

systemctl disable --now asus-expertbook-lightbar.service 2>/dev/null || true
rm -f /etc/systemd/system/asus-expertbook-lightbar.service
rm -f /usr/local/libexec/asus-expertbook-lightbar
systemctl daemon-reload
systemctl reset-failed asus-expertbook-lightbar.service 2>/dev/null || true

echo "ASUS ExpertBook Light Bar integration removed."
