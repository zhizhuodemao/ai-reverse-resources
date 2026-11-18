#!/usr/bin/env bash
set -euo pipefail

if ! python3 -c "import pymobiledevice3" >/dev/null 2>&1; then
  echo "ERROR: pymobiledevice3 is not installed for $(command -v python3)" >&2
  exit 1
fi

python3 - <<'PY'
import json
import subprocess
import sys

out = subprocess.check_output(
    [sys.executable, "-m", "pymobiledevice3", "usbmux", "list"],
    text=True,
)
devices = json.loads(out)
print(json.dumps({
    "device_count": len(devices),
    "devices": [
        {
            "udid": d.get("Identifier") or d.get("UniqueDeviceID"),
            "name": d.get("DeviceName"),
            "product_type": d.get("ProductType"),
            "ios_version": d.get("ProductVersion"),
            "connection": d.get("ConnectionType"),
            "needs_ios17_tunnel": (
                int((d.get("ProductVersion") or "0").split(".")[0]) >= 17
            ),
        }
        for d in devices
    ],
}, ensure_ascii=False, indent=2))
PY
