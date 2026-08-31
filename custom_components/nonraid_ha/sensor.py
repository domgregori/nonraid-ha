"""Sensor platform for the NonRAID integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NonraidHaData, NonraidHaDataUpdateCoordinator
from .const import DOMAIN
from .entity import NonraidHaEntity


def _array(data: NonraidHaData) -> dict[str, Any]:
    return (data.status or {}).get("array", {}) or {}


def _health(data: NonraidHaData) -> dict[str, Any]:
    return _array(data).get("health", {}) or {}


def _counters(data: NonraidHaData) -> dict[str, Any]:
    return _array(data).get("counters", {}) or {}


def _resync(data: NonraidHaData) -> dict[str, Any]:
    return (data.status or {}).get("resync", {}) or {}


def _percent(used: float | None, total: float | None) -> float | None:
    if used is None or not total:
        return None
    return round(100 * used / total, 1)


def _share_by_name(data: NonraidHaData, name: str) -> dict[str, Any] | None:
    for share in data.shares:
        if share.get("name") == name:
            return share
    return None


def _share_stat(data: NonraidHaData, name: str, key: str) -> float | None:
    stats = (_share_by_name(data, name) or {}).get("stats") or {}
    return stats.get(key)


def _disk_by_device(data: NonraidHaData, device: str) -> dict[str, Any] | None:
    for disk in data.disks:
        if disk.get("device") == device:
            return disk
    return None


_USAGE_PCT_RE = re.compile(r"(\d+)%")


def _disk_used_percent(data: NonraidHaData, device: str) -> int | None:
    """Return a data disk's filesystem usage percent, or None for parity (has no filesystem).

    Mirrors the webui frontend's own `parseUsagePct()` (src/selectors/disks.ts) - nmdctl reports
    usage as a free-text string like "45%", not a structured number.
    """
    disk = _disk_by_device(data, device)
    if not disk or disk.get("type") in ("P", "Q"):
        return None
    match = _USAGE_PCT_RE.search((disk.get("filesystem") or {}).get("usage") or "")
    return int(match.group(1)) if match else 0


def _disk_free_gb(data: NonraidHaData, device: str) -> float | None:
    """Return a data disk's free space in GB, or None for parity."""
    disk = _disk_by_device(data, device)
    used_pct = _disk_used_percent(data, device)
    if not disk or used_pct is None:
        return None
    return round(disk.get("size_gb", 0) * (1 - used_pct / 100), 1)


@dataclass(frozen=True, kw_only=True)
class NonraidHaSensorEntityDescription(SensorEntityDescription):
    """Describes a host-level NonRAID sensor."""

    value_fn: Callable[[NonraidHaData], Any]
    attributes_fn: Callable[[NonraidHaData], dict[str, Any] | None] | None = None
    available_fn: Callable[[NonraidHaData], bool] = lambda data: True


HOST_SENSOR_DESCRIPTIONS: tuple[NonraidHaSensorEntityDescription, ...] = (
    NonraidHaSensorEntityDescription(
        key="array_state",
        name="Array State",
        icon="mdi:harddisk",
        available_fn=lambda data: data.status is not None,
        value_fn=lambda data: _array(data).get("state"),
    ),
    NonraidHaSensorEntityDescription(
        key="array_health",
        name="Array Health",
        icon="mdi:heart-pulse",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "ERROR",
            "NEW",
            "NEW_DISK",
            "OFFLINE",
            "PARTIAL",
            "DEGRADED",
            "WARNING",
            "READY",
            "HEALTHY",
        ],
        available_fn=lambda data: data.status is not None,
        value_fn=lambda data: _health(data).get("status"),
        attributes_fn=lambda data: {"details": _health(data).get("details")},
    ),
    NonraidHaSensorEntityDescription(
        key="array_missing_disks",
        name="Array Missing Disks",
        icon="mdi:harddisk-remove",
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda data: data.status is not None,
        value_fn=lambda data: _counters(data).get("missing"),
    ),
    NonraidHaSensorEntityDescription(
        key="array_disk_errors",
        name="Array Disk Errors",
        icon="mdi:alert-circle-outline",
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda data: data.status is not None,
        value_fn=lambda data: _counters(data).get("disk_errors"),
    ),
    NonraidHaSensorEntityDescription(
        key="parity_check_progress",
        name="Parity Check Progress",
        icon="mdi:progress-check",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda data: data.status is not None,
        value_fn=lambda data: _resync(data).get("progress_percent"),
        attributes_fn=lambda data: {
            "active": _resync(data).get("active"),
            "paused": _resync(data).get("paused"),
            "pending": _resync(data).get("pending"),
            "action": _resync(data).get("action"),
            "rate_mb_s": _resync(data).get("rate_mb_s"),
            "eta_seconds": _resync(data).get("eta_seconds"),
        },
    ),
    NonraidHaSensorEntityDescription(
        key="uptime",
        name="Uptime",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (data.system.get("uptimeSeconds") or 0) / 3600,
    ),
    NonraidHaSensorEntityDescription(
        key="cpu_percent",
        name="CPU Usage",
        icon="mdi:cpu-64-bit",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.system.get("cpuPercent"),
    ),
    NonraidHaSensorEntityDescription(
        key="cpu_temperature",
        name="CPU Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.system.get("cpuTempCelsius"),
    ),
    NonraidHaSensorEntityDescription(
        key="memory_used_percent",
        name="Memory Usage",
        icon="mdi:memory",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _percent(data.system.get("memUsedBytes"), data.system.get("memTotalBytes")),
        attributes_fn=lambda data: {
            "used_bytes": data.system.get("memUsedBytes"),
            "total_bytes": data.system.get("memTotalBytes"),
        },
    ),
    NonraidHaSensorEntityDescription(
        key="cache_health",
        name="Cache Health",
        icon="mdi:memory",
        device_class=SensorDeviceClass.ENUM,
        options=["not-configured", "healthy", "degraded", "unavailable"],
        value_fn=lambda data: data.cache.get("health"),
    ),
    NonraidHaSensorEntityDescription(
        key="cli_version",
        name="CLI Version",
        icon="mdi:console-line",
        entity_category=EntityCategory.DIAGNOSTIC,
        # No latest/upToDate of its own - the CLI ships from the same release as the webui and is
        # always rebuilt+reinstalled alongside it (see nonraid-webui's backend/src/update/
        # service.ts, ComponentUpdateStatus.cliTool's doc comment). See the `update` platform for
        # the webui/driver's own installed-vs-latest reporting.
        value_fn=lambda data: data.update_status.get("cliTool"),
    ),
    NonraidHaSensorEntityDescription(
        key="cache_used_percent",
        name="Cache Usage",
        icon="mdi:memory",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda data: (data.cache.get("health") not in (None, "not-configured")),
        value_fn=lambda data: _percent(data.cache.get("usedBytes"), data.cache.get("totalBytes")),
        attributes_fn=lambda data: {
            "used_bytes": data.cache.get("usedBytes"),
            "total_bytes": data.cache.get("totalBytes"),
        },
    ),
)


@dataclass(frozen=True, kw_only=True)
class NonraidHaShareSensorEntityDescription(SensorEntityDescription):
    """Describes a per-pool (share) NonRAID sensor."""

    value_fn: Callable[[NonraidHaData, str], Any]


SHARE_SENSOR_DESCRIPTIONS: tuple[NonraidHaShareSensorEntityDescription, ...] = (
    NonraidHaShareSensorEntityDescription(
        key="active_connections",
        name="Active Streams",
        icon="mdi:folder-network",
        state_class=SensorStateClass.MEASUREMENT,
        # Live SMB tree-connections right now, from the backend's own smbstatus-backed count -
        # NFS has no reliable equivalent on the host, so this only ever reflects SMB clients (see
        # ShareWithStats.activeConnections's doc comment in nonraid-webui's backend/src/shares/types.ts).
        value_fn=lambda data, name: (_share_by_name(data, name) or {}).get("activeConnections"),
    ),
    NonraidHaShareSensorEntityDescription(
        key="used_percent",
        name="Used",
        icon="mdi:folder-percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data, name: _percent(
            _share_stat(data, name, "usedBytes"), _share_stat(data, name, "totalBytes")
        ),
    ),
)


@dataclass(frozen=True, kw_only=True)
class NonraidHaDiskSensorEntityDescription(SensorEntityDescription):
    """Describes a per-disk NonRAID sensor."""

    value_fn: Callable[[NonraidHaData, str], Any]


DISK_SENSOR_DESCRIPTIONS: tuple[NonraidHaDiskSensorEntityDescription, ...] = (
    NonraidHaDiskSensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data, device: data.smart_temperatures.get(device),
    ),
    NonraidHaDiskSensorEntityDescription(
        key="smart_health",
        name="SMART Health",
        icon="mdi:heart-pulse",
        device_class=SensorDeviceClass.ENUM,
        options=["passed", "failed"],
        value_fn=lambda data, device: data.smart_health.get(device),
    ),
    NonraidHaDiskSensorEntityDescription(
        key="spin_state",
        name="Spin State",
        icon="mdi:sync",
        device_class=SensorDeviceClass.ENUM,
        options=["active", "standby", "unknown"],
        value_fn=lambda data, device: data.smart_spin_states.get(device, "unknown"),
    ),
    NonraidHaDiskSensorEntityDescription(
        key="used_percent",
        name="Used",
        icon="mdi:harddisk",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_disk_used_percent,
    ),
    NonraidHaDiskSensorEntityDescription(
        key="free_space",
        name="Free Space",
        icon="mdi:harddisk",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_disk_free_gb,
    ),
)


def _disk_label(disk: dict[str, Any], disk_labels: dict[str, str]) -> str:
    """Return this disk's user-chosen nickname, or a "Disk N"/Parity fallback.

    nmdctl's own `disk_name` isn't a reliable human label - it's unpopulated for data disks and
    comes back as the literal string "none" for the parity slot - so it's never used here. The
    real nickname source is nonraid-webui's disk-labels setting (`GET /settings`'s `diskLabels`,
    keyed by the stable `disk_id`, see backend/src/settings/types.ts).
    """
    disk_id = disk.get("disk_id")
    nickname = disk_labels.get(disk_id) if disk_id else None
    if nickname:
        return nickname
    disk_type = disk.get("type")
    if disk_type == "P":
        return "Parity"
    if disk_type == "Q":
        return "Parity 2"
    return f"Disk {disk.get('slot')}"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up NonRAID sensors for this config entry."""
    coordinator: NonraidHaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    known_disk_devices: set[str] = set()

    @callback
    def _add_new_disk_sensors() -> None:
        new_entities: list[SensorEntity] = []
        for disk in coordinator.data.disks:
            device = disk.get("device")
            if not device or device in known_disk_devices:
                continue
            known_disk_devices.add(device)
            new_entities.extend(
                NonraidHaDiskSensor(coordinator, device, description)
                for description in DISK_SENSOR_DESCRIPTIONS
            )
        if new_entities:
            async_add_entities(new_entities)

    known_share_names: set[str] = set()

    @callback
    def _add_new_share_sensors() -> None:
        new_entities: list[SensorEntity] = []
        for share in coordinator.data.shares:
            name = share.get("name")
            if not name or name in known_share_names:
                continue
            known_share_names.add(name)
            new_entities.extend(
                NonraidHaShareSensor(coordinator, name, description)
                for description in SHARE_SENSOR_DESCRIPTIONS
            )
        if new_entities:
            async_add_entities(new_entities)

    host_entities = [NonraidHaSensor(coordinator, description) for description in HOST_SENSOR_DESCRIPTIONS]
    async_add_entities(host_entities)

    _add_new_disk_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_disk_sensors))

    _add_new_share_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_share_sensors))


class NonraidHaSensor(NonraidHaEntity, SensorEntity):
    """A host-level NonRAID sensor (array/system/cache)."""

    entity_description: NonraidHaSensorEntityDescription

    def __init__(
        self,
        coordinator: NonraidHaDataUpdateCoordinator,
        entity_description: NonraidHaSensorEntityDescription,
    ) -> None:
        """Set up the sensor from its description."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._entry_id}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return whether this sensor's underlying data is currently present."""
        return super().available and self.entity_description.available_fn(self.coordinator.data)

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes, if this sensor defines any."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)


class NonraidHaDiskSensor(NonraidHaEntity, SensorEntity):
    """A per-disk NonRAID sensor (temperature/SMART health/spin state)."""

    entity_description: NonraidHaDiskSensorEntityDescription

    def __init__(
        self,
        coordinator: NonraidHaDataUpdateCoordinator,
        device: str,
        entity_description: NonraidHaDiskSensorEntityDescription,
    ) -> None:
        """Set up the sensor for one array disk device (e.g. "/dev/sdb")."""
        super().__init__(coordinator)
        self._device = device
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._entry_id}_disk_{device}_{entity_description.key}"

    def _find_disk(self) -> dict[str, Any] | None:
        for disk in self.coordinator.data.disks:
            if disk.get("device") == self._device:
                return disk
        return None

    @property
    def name(self) -> str:
        """Return this disk's current label plus the sensor kind, e.g. "Disk 1 Temperature"."""
        disk = self._find_disk()
        label = _disk_label(disk, self.coordinator.data.disk_labels) if disk else self._device
        return f"{label} {self.entity_description.name}"

    @property
    def available(self) -> bool:
        """Return whether this disk is still present in the array."""
        return super().available and self._find_disk() is not None

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data, self._device)


class NonraidHaShareSensor(NonraidHaEntity, SensorEntity):
    """A per-pool (share) NonRAID sensor (currently just active SMB stream count)."""

    entity_description: NonraidHaShareSensorEntityDescription

    def __init__(
        self,
        coordinator: NonraidHaDataUpdateCoordinator,
        share_name: str,
        entity_description: NonraidHaShareSensorEntityDescription,
    ) -> None:
        """Set up the sensor for one pool (share)."""
        super().__init__(coordinator)
        self._share_name = share_name
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._entry_id}_pool_{share_name}_{entity_description.key}"

    @property
    def name(self) -> str:
        """Return this pool's name plus the sensor kind, e.g. "media Active Streams"."""
        return f"{self._share_name} {self.entity_description.name}"

    @property
    def available(self) -> bool:
        """Return whether this pool still exists."""
        return super().available and _share_by_name(self.coordinator.data, self._share_name) is not None

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data, self._share_name)
