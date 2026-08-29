"""Binary sensor platform for the NonRAID integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NonraidHaData, NonraidHaDataUpdateCoordinator
from .const import ARRAY_HEALTHY_STATUSES, DOMAIN
from .entity import NonraidHaEntity


def _array(data: NonraidHaData) -> dict:
    return (data.status or {}).get("array", {}) or {}


def _array_has_problem(data: NonraidHaData) -> bool | None:
    """Return whether the array's health status indicates an error/degraded state."""
    if data.status is None:
        return None
    status = _array(data).get("health", {}).get("status")
    if status is None:
        return None
    return status not in ARRAY_HEALTHY_STATUSES


def _any_disk_failed_or_missing(data: NonraidHaData) -> bool | None:
    """Return whether nmdctl's own counters show any missing/invalid/wrong/disabled disk."""
    if data.status is None:
        return None
    counters = _array(data).get("counters", {}) or {}
    return any(
        (counters.get(key) or 0) > 0
        for key in ("missing", "invalid", "wrong", "disabled")
    )


@dataclass(frozen=True, kw_only=True)
class NonraidHaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a NonRAID binary sensor."""

    value_fn: Callable[[NonraidHaData], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[NonraidHaBinarySensorEntityDescription, ...] = (
    NonraidHaBinarySensorEntityDescription(
        key="array_problem",
        name="Array Problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_array_has_problem,
    ),
    NonraidHaBinarySensorEntityDescription(
        key="disk_failed_or_missing",
        name="Disk Failed or Missing",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_any_disk_failed_or_missing,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up NonRAID binary sensors for this config entry."""
    coordinator: NonraidHaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        NonraidHaBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class NonraidHaBinarySensor(NonraidHaEntity, BinarySensorEntity):
    """A NonRAID array-health binary sensor."""

    entity_description: NonraidHaBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: NonraidHaDataUpdateCoordinator,
        entity_description: NonraidHaBinarySensorEntityDescription,
    ) -> None:
        """Set up the binary sensor from its description."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._entry_id}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return whether the array's status is currently known.

        Unavailable (not "off") on a fresh install with no array ever created - see
        NonraidHaApiClient.async_get_status().
        """
        return super().available and self.coordinator.data.status is not None

    @property
    def is_on(self) -> bool | None:
        """Return whether this problem condition is currently true."""
        return self.entity_description.value_fn(self.coordinator.data)
