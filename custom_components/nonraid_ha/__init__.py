"""The NonRAID integration.

Integrates the nonraid-webui NAS dashboard's REST API with Home Assistant - array/disk/SMART
sensors, docker/LXC container switches. See https://github.com/domgregori/nonraid-ha.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    NonraidHaApiClient,
    NonraidHaAuthError,
    NonraidHaError,
)
from .const import (
    CONF_HOST,
    CONF_READ_ONLY,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLATFORM_SWITCH,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class NonraidHaData:
    """One coordinator refresh's worth of data, aggregated from several endpoints."""

    status: dict[str, Any] | None
    system: dict[str, Any]
    cache: dict[str, Any]
    docker_containers: list[dict[str, Any]]
    lxc_containers: list[dict[str, Any]]
    shares: list[dict[str, Any]] = field(default_factory=list)
    update_status: dict[str, Any] = field(default_factory=dict)
    smart_temperatures: dict[str, float | None] = field(default_factory=dict)
    smart_health: dict[str, str | None] = field(default_factory=dict)
    smart_spin_states: dict[str, str] = field(default_factory=dict)
    disk_labels: dict[str, str] = field(default_factory=dict)

    @property
    def disks(self) -> list[dict[str, Any]]:
        """Return only the array's real, currently-assigned disks (skip empty slots).

        Mirrors the backend's own filter (`d.device && d.device !== 'none'`, see
        backend/src/routes/smart.ts).
        """
        if not self.status:
            return []
        return [
            disk
            for disk in self.status.get("disks", [])
            if disk.get("device") and disk["device"] != "none"
        ]


def _platforms_for_entry(entry: ConfigEntry) -> list[str]:
    """Return the platforms to set up for this entry.

    Switch (container start/stop) is only registered for a full-access token - a read-only token
    gets 403 on every mutating request, so there is nothing for it to control. See the config
    flow's "read-only token" field and the design handoff's open question about token scope.
    """
    if entry.data.get(CONF_READ_ONLY, False):
        return [p for p in PLATFORMS if p != PLATFORM_SWITCH]
    return list(PLATFORMS)


class NonraidHaDataUpdateCoordinator(DataUpdateCoordinator[NonraidHaData]):
    """Coordinates polling nonraid-webui for every entity this integration exposes."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: NonraidHaApiClient) -> None:
        """Set up the coordinator."""
        self.client = client
        self.entry_id = entry.entry_id
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> NonraidHaData:
        """Fetch a fresh snapshot of everything this integration's entities need."""
        try:
            status, system, cache, docker_containers, lxc_containers, disk_labels, shares, update_status = (
                await asyncio.gather(
                    self.client.async_get_status(),
                    self.client.async_get_system(),
                    self.client.async_get_cache_status(),
                    self.client.async_get_docker_containers(),
                    self.client.async_get_lxc_containers(),
                    self.client.async_get_disk_labels(),
                    self.client.async_get_shares(),
                    self.client.async_get_update_status(),
                )
            )

            smart_temperatures: dict[str, float | None] = {}
            smart_health: dict[str, str | None] = {}
            smart_spin_states: dict[str, str] = {}
            if status and status.get("disks"):
                smart_temperatures, smart_health, smart_spin_states = await asyncio.gather(
                    self.client.async_get_smart_temperatures(),
                    self.client.async_get_smart_health(),
                    self.client.async_get_smart_spin_states(),
                )
        except NonraidHaAuthError as err:
            # Invalid/revoked token - prompt the user to re-authenticate rather than retrying
            # forever with a token that will never work again.
            raise ConfigEntryAuthFailed(err.message) from err
        except NonraidHaError as err:
            raise UpdateFailed(str(err)) from err

        return NonraidHaData(
            status=status,
            system=system,
            cache=cache,
            docker_containers=docker_containers,
            lxc_containers=lxc_containers,
            shares=shares,
            update_status=update_status,
            smart_temperatures=smart_temperatures,
            smart_health=smart_health,
            smart_spin_states=smart_spin_states,
            disk_labels=disk_labels,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NonRAID from a config entry."""
    session = async_get_clientsession(
        hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
    )
    client = NonraidHaApiClient(entry.data[CONF_HOST], entry.data[CONF_TOKEN], session)

    coordinator = NonraidHaDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _platforms_for_entry(entry))

    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, _platforms_for_entry(entry)
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options/data change (e.g. token rotated via reauth)."""
    await hass.config_entries.async_reload(entry.entry_id)
