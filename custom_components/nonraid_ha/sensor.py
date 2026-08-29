"""Sensor platform for the NonRAID integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
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
        value_fn=lambda data: _percent(
            data.system.get("memUsedBytes"), data.system.get("memTotalBytes")
        ),
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
        key="cache_used_percent",
        name="Cache Usage",
        icon="mdi:memory",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        available_fn=lambda data: data.cache.get("health") not in (None, "not-configured"),
        value_fn=lambda data: _percent(data.cache.get("usedBytes"), data.cache.get("totalBytes")),
        attributes_fn=lambda data: {
            "used_bytes": data.cache.get("usedBytes"),
            "total_bytes": data.cache.get("totalBytes"),
        },
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
)


def _disk_label(disk: dict[str, Any]) -> str:
    """Return a human-friendly label for a disk (its nmdctl name, or a Parity/slot fallback).

    Confirmed live against a real array: nmdctl reports the parity slot's own `disk_name` as the
    literal string "none" (not JSON null), so that value has to be excluded explicitly here or a
    parity disk's sensors end up named "none Temperature" instead of "Parity Temperature".
    """
    name = disk.get("disk_name")
    if name and name != "none":
        return str(name)
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

    host_entities = [
        NonraidHaSensor(coordinator, description) for description in HOST_SENSOR_DESCRIPTIONS
    ]
    async_add_entities(host_entities)

    _add_new_disk_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_disk_sensors))


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
        label = _disk_label(disk) if disk else self._device
        return f"{label} {self.entity_description.name}"

    @property
    def available(self) -> bool:
        """Return whether this disk is still present in the array."""
        return super().available and self._find_disk() is not None

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data, self._device)
