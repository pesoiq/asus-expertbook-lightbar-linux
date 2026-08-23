# Investigation summary

The front Light Bar did not reproduce its Windows behavior under Fedora, while the normal side
charging indicator continued to work. Linux had no `/sys/class/leds/asus::lightbar` interface for
this front strip.

Kernel enumeration identified an independent controller:

```text
ALED0217:00 0B05:0124
HID-over-I2C
hidraw
```

The relevant HID collection is Usage Page `0xFFB5`, Usage `0x00A0`, Report ID `0x20`, with a
32-byte payload plus report ID.

`andykarpov/expertbook-led` already demonstrated built-in animation/brightness Feature Reports on
the same controller family and was an important reference.

Interoperability-oriented static analysis of ASUS System Control Interface v3 showed a matching
ASUS LED path selected by Vendor `0x0B05`, Usage Page `0xFFB5`, and Usage `0x00A0`, and exposed the
LED-count query, direct RGB path, and off command documented in `protocol.md`. Those commands were
then tested on the physical laptop.

No proprietary ASUS binary is redistributed by this repository.

For Linux integration, repeated tests established:

```text
quiet       -> ASUS thermal policy 2
balanced    -> ASUS thermal policy 0
performance -> ASUS thermal policy 1
```

Therefore the daemon uses `/sys/firmware/acpi/platform_profile` for the temporary performance
indicator and `/sys/class/power_supply/` for charging/full/off state. Instantaneous fan RPM is not
used because it follows temperature/load and can lag behind profile changes.
