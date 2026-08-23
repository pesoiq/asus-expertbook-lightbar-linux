# Upstream / posting plan

Keep this independent repository because it contains the complete Linux integration: power state,
platform profile, systemd lifecycle, and reconnect handling.

After v1.0.0 is public, also share the protocol findings with:

- https://github.com/andykarpov/expertbook-led
- https://github.com/andykarpov/expertbook-led/issues/1

Useful upstream findings:

- `20 C1 02` LED-count query and `20 C1 02 05` five-zone response
- direct `20 80 ...` per-zone RGB
- `20 07` off command
- selector evidence: Vendor `0x0B05`, Usage Page `0xFFB5`, Usage `0x00A0`

Do not attach or commit proprietary ASUS binaries.
