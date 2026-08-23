# v1.0.0 — First tested release

First public tested release of Linux userspace support for the front Light Bar on the ASUS
ExpertBook B9400CBA/B9450CBA.

Included:

- ALED0217 / `0B05:0124` hardware and descriptor checks
- `20 C1 02 05` five-zone handshake
- five-zone direct RGB control
- charging/full/off automatic state machine
- 3-second blue-cyan indication when entering Linux `performance`
- dynamic hidraw discovery and reconnect loop
- graceful service stop
- systemd integration
- installer, uninstaller, rollback, protocol notes, and test documentation

The README is the recommended path for new users. Development experiments are kept outside the
installation path.
