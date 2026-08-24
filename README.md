# ASUS ExpertBook B9400CBA/B9450CBA Light Bar Support for Linux

Linux userspace support for the `ALED0217` / `0B05:0124` front Light Bar on ASUS ExpertBook B9400CBA/B9450CBA.

## Releases

- **v1.0.0 — Windows-parity baseline:** conservative charging/full-charge and performance-profile behavior modeled after the useful stock behavior.
- **v2.0.0 — Linux-enhanced edition:** keeps the v1 safety/base-state logic and adds persistent terminal-selectable charging patterns plus KDE notification indication.

v1.0.0 remains permanently available from its Git tag. v2.0.0 is the recommended enhanced Linux release for the tested hardware.

## Tested hardware/software

- ASUS EXPERTBOOK B9400CBA_B9450CBA
- ALED0217:00 `0B05:0124`, HID-over-I2C / hidraw
- 5 LED zones, report ID `0x20`
- Fedora Linux 44 KDE Plasma
- Kernel `7.1.9-200.fc44.x86_64`
- KDE Plasma `6.7.4`, Wayland
- systemd `259`

## v2 behavior

| State | Light Bar behavior |
|---|---|
| AC disconnected | Off |
| AC + battery at 100% | Static low-intensity green |
| AC + charging + battery below 100% | Persistently selected charging pattern |
| Enter performance profile | Blue-cyan for 3 seconds, then restore |
| KDE/Freedesktop notification | Very-dim yellow for 1 second, then restore |

Charging patterns:

1. Liquid Rainbow v0.2 Video Dither
2. Center Bloom
3. Hard-edge Constant-Luminance Flow
4. ASUS hardware Effect 14
5. Static Red v1

Pattern 4 requires the validated ALED0217 HID reset path when leaving the hardware effect. v2.0.0 uses the physically validated `2 s` detach + `3 s` post-bind stabilization timing before returning to direct RGB.

## Install

```bash
git clone https://github.com/pesoiq/asus-expertbook-lightbar-linux.git
cd asus-expertbook-lightbar-linux
git checkout v2.0.0
./install.sh
```

## Terminal control

```bash
lightbarctl list
lightbarctl status
lightbarctl 1
lightbarctl 2
lightbarctl 3
lightbarctl 4
lightbarctl 5
```

The selected pattern is persisted in `/var/lib/asus-expertbook-lightbar/pattern` and survives reboot/shutdown until explicitly changed.

## Installed components

- `/usr/local/libexec/asus-expertbook-lightbar` — root hardware daemon
- `/usr/local/bin/lightbarctl` — terminal control client
- `/usr/local/libexec/asus-expertbook-lightbar-notify-watch` — session notification watcher
- `/etc/systemd/system/asus-expertbook-lightbar.service` — hardware daemon service
- `~/.config/systemd/user/asus-expertbook-lightbar-notifications.service` — per-user KDE/Freedesktop notification bridge

## v1 vs v2

See `docs/v1-v2-comparison.md` and `RELEASE_NOTES_v2.0.0.md`.

## Safety / scope

This project does not modify GRUB, kernel command-line parameters, BIOS/UEFI, firmware, initramfs, or module blacklists. The hardware-effect exit path temporarily unbinds/rebinds only the matching `ALED0217` HID-over-I2C device through `i2c_hid_acpi`.

## Development and validation disclosure

Development, diagnostics, protocol analysis, implementation, integration, and documentation were assisted by **OpenAI ChatGPT (GPT-5.6 Sol)**. Physical hardware observations and acceptance testing were performed on the actual ASUS ExpertBook by the project maintainer and were not simulated by the AI.

## License

MIT. Independent community project; not affiliated with or endorsed by ASUSTeK Computer Inc.
