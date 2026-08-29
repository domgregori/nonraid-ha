"""Constants for the NonRAID integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "nonraid_ha"
NAME = "NonRAID"
MANUFACTURER = "NonRAID"

ISSUE_URL = "https://github.com/domgregori/nonraid-ha/issues"

# Config entry data keys
CONF_HOST = "host"
CONF_TOKEN = "token"
CONF_VERIFY_SSL = "verify_ssl"
CONF_READ_ONLY = "read_only"

DEFAULT_VERIFY_SSL = True
DEFAULT_READ_ONLY = False

# A local NAS on the LAN, not a cloud service - see hacs.json/manifest.json's iot_class.
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

# Platforms this integration provides. Sensor and binary_sensor are always registered; switch is
# skipped at setup time for a read-only token (see __init__.py).
PLATFORM_SENSOR = "sensor"
PLATFORM_BINARY_SENSOR = "binary_sensor"
PLATFORM_SWITCH = "switch"
PLATFORMS = [PLATFORM_SENSOR, PLATFORM_BINARY_SENSOR, PLATFORM_SWITCH]

# nmdctl array health statuses (backend/src/nmd/types.ts's ArrayHealthStatus) that represent a
# genuinely healthy/expected-idle state. Anything else is surfaced as "array has a problem".
ARRAY_HEALTHY_STATUSES = {"READY", "HEALTHY", "NEW", "NEW_DISK"}

# nmdctl per-disk statuses (backend/src/nmd/types.ts's DiskStatus) that represent a disk in good
# standing. Anything else (missing, disabled, wrong, invalid, ...) counts as failed/missing.
DISK_OK_STATUSES = {"DISK_OK", "DISK_NEW"}
