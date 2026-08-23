# ASUS ExpertBook B9400CBA/B9450CBA Light Bar Support for Linux

Working Linux userspace support for the front **Light Bar** on the ASUS ExpertBook
B9400CBA/B9450CBA using the `ALED0217` HID-over-I2C controller.

## Recommended path for new users

This README contains the **final tested installation path only**. Development experiments,
reverse-engineering notes, and diagnostic history are kept separately under [`docs/`](docs/).

### Tested hardware

- Laptop: `ASUS EXPERTBOOK B9400CBA_B9450CBA`
- Controller: `ALED0217:00 0B05:0124`
- HID VID:PID: `0B05:0124`
- Transport: HID-over-I2C / `hidraw`
- Light Bar collection: Usage Page `0xFFB5`, Usage `0x00A0`, Report ID `0x20`
- Feature report size: 33 bytes including Report ID
- Detected LED-zone count on the tested machine: 5

### Tested software

- Fedora Linux 44 KDE Plasma Desktop Edition
- Kernel `7.1.9-200.fc44.x86_64`
- KDE Plasma `6.7.4`
- Wayland / `kwin_wayland`
- systemd `259`

## Final behavior

| Linux state | Light Bar behavior |
|---|---|
| AC disconnected | Off |
| AC connected + battery below 100% + `Charging` | Pure red, low intensity |
| AC connected + battery at 100% | Pure green, low intensity |
| Transition into `performance` platform profile | Blue-cyan for 3 seconds |
| After the performance indication | Restore current red / green / off state |

The blue-cyan indication appears **only when entering** `performance`. Starting the service while
the laptop is already in `performance` does not create an extra flash.

## 1. Confirm the hardware first

```bash
cat /sys/devices/virtual/dmi/id/product_name

grep -RHiE 'HID_ID=0018:00000B05:00000124|HID_NAME=ALED0217' \
  /sys/bus/hid/devices/*/uevent 2>/dev/null
```

Expected hardware includes:

```text
ASUS EXPERTBOOK B9400CBA_B9450CBA
HID_ID=0018:00000B05:00000124
HID_NAME=ALED0217:00 0B05:0124
```

Stop if your hardware does not match. Do not apply this project blindly to another ASUS RGB/HID device.

## 2. Clone to the documented project path

The path used throughout this project is:

```text
$HOME/src/asus-expertbook-lightbar-linux
```

```bash
mkdir -p "$HOME/src"

git clone \
  https://github.com/pesoiq/asus-expertbook-lightbar-linux.git \
  "$HOME/src/asus-expertbook-lightbar-linux"

cd "$HOME/src/asus-expertbook-lightbar-linux"
git checkout --detach v1.0.0
```

## 3. Install

```bash
cd "$HOME/src/asus-expertbook-lightbar-linux"
sudo ./install.sh
```

Permanent installed paths:

```text
/usr/local/libexec/asus-expertbook-lightbar
/etc/systemd/system/asus-expertbook-lightbar.service
```

The installer verifies the laptop, HID device, descriptor, required sysfs interfaces, Python
syntax, and systemd unit before enabling the service.

## 4. Verify the service

```bash
systemctl status asus-expertbook-lightbar.service --no-pager -l

sudo journalctl \
  -u asus-expertbook-lightbar.service \
  -b --no-pager -n 50
```

A matching tested controller returns:

```text
20 C1 02 05
```

## 5. Functional test

Do not call the installation successful only because systemd started. Verify the original behavior:

1. AC connected + battery at 100% -> green.
2. Disconnect AC -> Light Bar off.
3. AC connected + below 100% + actively charging -> red.
4. Change KDE/Fedora from `quiet` or `balanced` to `performance` -> blue-cyan for 3 seconds, then restore the base state.

On the tested laptop:

```text
quiet       -> ASUS thermal policy 2 (silent)
balanced    -> ASUS thermal policy 0 (default)
performance -> ASUS thermal policy 1 (overboost)
```

The daemon watches `/sys/firmware/acpi/platform_profile`. It deliberately does not use instantaneous
fan RPM as the trigger.

## 6. Rollback

```bash
cd "$HOME/src/asus-expertbook-lightbar-linux"
sudo ./uninstall.sh
```

This project does not modify the kernel, GRUB, BIOS, firmware, initramfs, or driver blacklists.

## Color customization

The controller supports direct RGB control for five zones. The shipped persistent red/green values
are intentionally dim, and the short performance indication is a dim blue-cyan. Users can customize
RGB values in `src/asus-expertbook-lightbar.py`; see [`docs/customization.md`](docs/customization.md).

The README intentionally does not reproduce the many brightness/color experiments used during
development because they are not needed by a new user following the working path.

## Documentation

- [`docs/protocol.md`](docs/protocol.md) — confirmed HID protocol used by the final solution
- [`docs/investigation-summary.md`](docs/investigation-summary.md) — concise diagnostic/reverse-engineering history
- [`docs/test-results.md`](docs/test-results.md) — validated tests on the physical laptop
- [`docs/customization.md`](docs/customization.md) — concise color customization notes
- [`rollback.md`](rollback.md) — manual rollback
- [`tested-versions.txt`](tested-versions.txt) — tested environment

## Related work / upstream

This work was informed by [`andykarpov/expertbook-led`](https://github.com/andykarpov/expertbook-led),
which documented built-in effects and brightness control for the same `0B05:0124` controller family.
The direct RGB and LED-count findings here are also relevant to its custom-color investigation.

No proprietary ASUS executable, DLL, driver, firmware, or extracted Windows binary is included.

## License

MIT — see [`LICENSE`](LICENSE).

## Disclaimer

Independent community project; not affiliated with or endorsed by ASUSTeK Computer Inc.
Use only on matching hardware and review the source before installation.
