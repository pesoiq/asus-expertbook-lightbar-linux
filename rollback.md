# Rollback

```bash
sudo systemctl disable --now asus-expertbook-lightbar.service
sudo rm -f /etc/systemd/system/asus-expertbook-lightbar.service
sudo rm -f /usr/local/libexec/asus-expertbook-lightbar
sudo systemctl daemon-reload
sudo systemctl reset-failed asus-expertbook-lightbar.service 2>/dev/null || true
```

No kernel, GRUB, BIOS, firmware, initramfs, or driver-blacklist rollback is required.
