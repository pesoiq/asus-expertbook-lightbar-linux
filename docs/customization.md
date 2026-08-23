# Color customization

The controller accepts direct RGB triplets for five zones. The shipped daemon intentionally uses
very low-intensity red/green for persistent charging/full indicators and a dim blue-cyan for the
short performance indication.

Edit only the RGB arrays in:

```text
src/asus-expertbook-lightbar.py
```

Relevant arrays:

```text
CHARGING_RED
FULL_GREEN
PERFORMANCE_CYAN
```

RGB order was confirmed on the tested hardware. Reinstall after editing:

```bash
sudo ./install.sh
```

Keep values conservative and test only on matching `ALED0217 / 0B05:0124` hardware. The many
intermediate brightness experiments from development are intentionally not part of the recommended
user path.
