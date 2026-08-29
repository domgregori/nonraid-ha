"""Shared entity base classes for the NonRAID integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME

if TYPE_CHECKING:
    from . import NonraidHaDataUpdateCoordinator


class NonraidHaEntity(CoordinatorEntity["NonraidHaDataUpdateCoordinator"]):
    """Base entity for anything belonging to the single NonRAID host device.

    Every entity this integration creates - host-level sensors, per-disk sensors, container
    switches - shares one Home Assistant device representing the NAS itself (`config_entry.entry_id`
    as its identifier). There is deliberately no per-disk/per-container HA device: that adds real
    complexity (device registry cleanup as disks/containers come and go) for limited benefit on a
    single-host integration - see the "Suggested first-pass scope" section of the design handoff.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: "NonraidHaDataUpdateCoordinator") -> None:
        """Set up the entity against its coordinator."""
        super().__init__(coordinator)
        self._entry_id = coordinator.entry_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the single NonRAID host device every entity belongs to."""
        system = (self.coordinator.data.system if self.coordinator.data else None) or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=system.get("hostname") or NAME,
            manufacturer=MANUFACTURER,
            model="NonRAID NAS",
            sw_version=system.get("version"),
            configuration_url=self.coordinator.client.base_url,
        )
