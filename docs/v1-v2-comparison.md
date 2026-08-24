# v1.0.0 vs v2.0.0

| Area | v1.0.0 | v2.0.0 |
|---|---|---|
| Goal | Windows-parity baseline | Linux-enhanced edition |
| Charging below 100% | Static red | User-selected persistent pattern |
| Charging patterns | 1 | 5 |
| Terminal control | No | `lightbarctl 1..5`, `status`, `list` |
| Pattern persists across reboot | N/A | Yes |
| Full charge | Static green | Static green |
| AC disconnected | Off | Off |
| Performance indication | Cyan 3 s | Cyan 3 s |
| Notification indication | No | Yellow 1 s |
| Hardware Effect 14 | Not part of production behavior | Selectable pattern with validated reset path |
| Session component | None | KDE/Freedesktop notification bridge |

v1.0.0 remains the intentionally simple baseline. v2.0.0 is an additive Linux-oriented release rather than a replacement of the historical v1 design goal.
