# Confirmed ALED0217 Light Bar protocol

Only protocol elements validated on the physical test machine are documented here.

## HID identity

```text
HID name:       ALED0217:00 0B05:0124
Vendor ID:      0x0B05
Product ID:     0x0124
Transport:      HID-over-I2C / hidraw
Usage Page:     0xFFB5
Usage:          0x00A0
Report ID:      0x20
Feature report: 33 bytes including Report ID
```

## LED-count handshake

Send a Feature Report beginning with:

```text
20 C1 02
```

Then read Feature Report `0x20`. The tested machine returns:

```text
20 C1 02 05
```

The ASUS code path uses `05` for the five-zone variant.

## Direct RGB

Validated form:

```text
20 80 <state> <gain> R1 G1 B1 R2 G2 B2 R3 G3 B3 R4 G4 B4 R5 G5 B5 ...zero padding...
```

The production daemon uses the tested `state=0x00`, `gain=0x20` form. Pure red, green, blue,
and white were separately validated during development, confirming RGB channel order.

## Off

```text
20 07
```

with zero padding to the Feature Report length.

Unknown Report `0x20` subcommands are not used. Do not assume this protocol is safe on unrelated
ASUS HID/RGB devices.
