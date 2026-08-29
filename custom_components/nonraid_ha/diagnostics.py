"""Diagnostics support for the NonRAID integration.

Standard HACS/HA convention (Settings -> Devices & Services -> NonRAID -> Download diagnostics) -
gives a bug report the full coordinator snapshot without ever including the bearer token.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import NonraidHaDataUpdateCoordinator
from .const import CONF_HOST, CONF_TOKEN, DOMAIN

TO_REDACT = {CONF_TOKEN, CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: NonraidHaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "coordinator_data": {
            "status": data.status,
            "system": data.system,
            "cache": data.cache,
            "docker_containers": data.docker_containers,
            "lxc_containers": data.lxc_containers,
            "shares": data.shares,
            "disk_labels": data.disk_labels,
            "smart_temperatures": data.smart_temperatures,
            "smart_health": data.smart_health,
            "smart_spin_states": data.smart_spin_states,
        },
    }
