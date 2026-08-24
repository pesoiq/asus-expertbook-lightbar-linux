# Rollback / uninstall

## Uninstall v2

Run `./uninstall.sh` from the v2.0.0 source tree.

The uninstall script intentionally leaves `/var/lib/asus-expertbook-lightbar/pattern` so the selected pattern can be reused after reinstall. Remove that directory manually only if you explicitly want to erase saved state.

## Return to v1.0.0

The v1 source remains available from Git tag `v1.0.0`. Check out that tag and run its documented installer after uninstalling v2.

If v2 was installed over an existing local production v1, `install.sh` also creates a timestamped backup under `/var/backups/asus-expertbook-lightbar-before-v2-*`.
