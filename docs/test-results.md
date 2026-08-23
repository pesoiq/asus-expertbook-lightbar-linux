# Test results — v1.0.0

Tests were performed on the physical ASUS ExpertBook B9400CBA/B9450CBA.

| Test | Result |
|---|---|
| ALED0217 `0B05:0124` enumeration | PASS |
| HID FFB5/A0/Report20 descriptor match | PASS |
| Feature Report writes | PASS |
| LED-count handshake | PASS — `20 C1 02 05` |
| Five-zone direct RGB | PASS |
| Pure red / green / blue / white | PASS |
| Off command | PASS |
| AC connected + 100% -> green | PASS |
| AC disconnect -> off | PASS |
| Enter `performance` -> blue-cyan for 3 seconds | PASS |
| Restore base state after 3 seconds | PASS |
| `quiet/balanced/performance` ASUS policy mapping | PASS |
| Python syntax validation | PASS |
| systemd unit validation | PASS |
| systemd enable/start | PASS |
| Production-service handshake | PASS |

The final daemon uses `AC=1 + status=Charging + capacity<100 -> red`. The red command itself was
visually validated, while the final automatic state machine switches to green at 100% and off as
soon as AC is removed.

The installed service logged:

```text
[DEVICE] /dev/hidraw1
[HANDSHAKE] 20 C1 02 05
[BASE] AC=1 BAT=Full CAP=100% => FULL_GREEN_5
```

and was `enabled` and `active (running)`.
