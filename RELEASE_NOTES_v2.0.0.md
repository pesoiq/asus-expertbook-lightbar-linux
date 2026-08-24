# Release Notes — v2.0.0

## Linux-enhanced edition

v2.0.0 builds on the conservative v1.0.0 Windows-parity baseline and adds Linux-native enhancements while retaining the validated AC/battery and performance-state behavior.

### Added

- Five persistent charging patterns selectable from the terminal with `lightbarctl 1..5`.
- Persistent selected-pattern state across reboot/shutdown.
- Liquid Rainbow v0.2 Video Dither.
- Center Bloom.
- Hard-edge Constant-Luminance Flow.
- ASUS hardware Effect 14.
- v1 Static Red as a selectable compatibility/baseline pattern.
- KDE/Freedesktop notification bridge: very-dim static yellow for 1 second, then restore.
- `lightbarctl status` and `lightbarctl list`.
- Root hardware daemon + unprivileged wheel-group Unix-socket control architecture.

### Preserved from v1

- AC disconnected -> off.
- Battery 100% on AC -> low-intensity green.
- Enter performance profile -> blue-cyan for 3 seconds, then restore.
- No performance flash merely because the service starts while already in performance.
- Exact ALED0217 descriptor validation and `20 C1 02 05` five-zone handshake.

### Effect 14 reliability fix

Leaving hardware Effect 14 uses the validated ALED0217 `i2c_hid_acpi` reset sequence with a 2-second detach wait and a 3-second post-bind stabilization wait before direct RGB resumes. This fixes the observed direct-RGB state being cleared after returning from Effect 14.

### Compatibility

Validated on ASUS EXPERTBOOK B9400CBA_B9450CBA, Fedora Linux 44 KDE Plasma, kernel `7.1.9-200.fc44.x86_64`, Plasma `6.7.4`, systemd `259`.

### AI-assisted development disclosure

This release was developed with assistance from **OpenAI ChatGPT (GPT-5.6 Sol)** for diagnostics, protocol analysis, code integration, and documentation. Hardware observations and visual/functional validation came from the physical laptop and were not simulated by the AI.
