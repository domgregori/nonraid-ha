"""Switch platform for the NonRAID integration.

Only registered for a full-access token - see __init__.py's `_platforms_for_entry`. A read-only
token 403s on every mutating request (start/stop), so there is nothing for these switches to
control; the config flow's "read-only token" field decides this client-side (see the design
handoff's "Open design question" - there is no backend endpoint to ask a token its own scope).

Deliberately limited to Docker/LXC container start-stop for this first pass - array start/stop,
cache setup/replace, and any system-level action are left out as too high-blast-radius for a
single entity toggle (same reasoning already applied when scoping the CLI's TUI action keys).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NonraidHaDataUpdateCoordinator
from .const import DOMAIN
from .entity import NonraidHaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up NonRAID container switches for this config entry."""
    coordinator: NonraidHaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    known_docker_ids: set[str] = set()
    known_lxc_names: set[str] = set()

    @callback
    def _add_new_switches() -> None:
        new_entities: list[SwitchEntity] = []
        for container in coordinator.data.docker_containers:
            container_id = container.get("id")
            if container_id and container_id not in known_docker_ids:
                known_docker_ids.add(container_id)
                new_entities.append(NonraidHaDockerSwitch(coordinator, container_id))
        for container in coordinator.data.lxc_containers:
            name = container.get("name")
            if name and name not in known_lxc_names:
                known_lxc_names.add(name)
                new_entities.append(NonraidHaLxcSwitch(coordinator, name))
        if new_entities:
            async_add_entities(new_entities)

    _add_new_switches()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_switches))


class NonraidHaDockerSwitch(NonraidHaEntity, SwitchEntity):
    """Start/stop switch for one Docker container."""

    _attr_icon = "mdi:docker"

    def __init__(self, coordinator: NonraidHaDataUpdateCoordinator, container_id: str) -> None:
        """Set up the switch for one Docker container id."""
        super().__init__(coordinator)
        self._container_id = container_id
        self._attr_unique_id = f"{self._entry_id}_docker_{container_id}"

    def _find_container(self) -> dict[str, Any] | None:
        for container in self.coordinator.data.docker_containers:
            if container.get("id") == self._container_id:
                return container
        return None

    @property
    def name(self) -> str:
        """Return the container's current name, disambiguated as a Docker container."""
        container = self._find_container()
        label = container["name"] if container else self._container_id
        return f"{label} (Docker)"

    @property
    def available(self) -> bool:
        """Return whether this container still exists."""
        return super().available and self._find_container() is not None

    @property
    def is_on(self) -> bool | None:
        """Return whether the container is currently running."""
        container = self._find_container()
        return container is not None and container.get("state") == "running"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the container's human status string, e.g. "Up 2 hours"."""
        container = self._find_container()
        if container is None:
            return None
        return {"status": container.get("status"), "image": container.get("image")}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the container."""
        await self.coordinator.client.async_start_docker_container(self._container_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the container."""
        await self.coordinator.client.async_stop_docker_container(self._container_id)
        await self.coordinator.async_request_refresh()


class NonraidHaLxcSwitch(NonraidHaEntity, SwitchEntity):
    """Start/stop switch for one LXC container."""

    _attr_icon = "mdi:cube-outline"

    def __init__(self, coordinator: NonraidHaDataUpdateCoordinator, container_name: str) -> None:
        """Set up the switch for one LXC container. LXC containers are keyed by name (no id)."""
        super().__init__(coordinator)
        self._container_name = container_name
        self._attr_unique_id = f"{self._entry_id}_lxc_{container_name}"

    def _find_container(self) -> dict[str, Any] | None:
        for container in self.coordinator.data.lxc_containers:
            if container.get("name") == self._container_name:
                return container
        return None

    @property
    def name(self) -> str:
        """Return the container's name, disambiguated as an LXC container."""
        return f"{self._container_name} (LXC)"

    @property
    def available(self) -> bool:
        """Return whether this container still exists."""
        return super().available and self._find_container() is not None

    @property
    def is_on(self) -> bool | None:
        """Return whether the container is currently running."""
        container = self._find_container()
        return container is not None and container.get("state") == "running"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the container's IP addresses, if any."""
        container = self._find_container()
        if container is None:
            return None
        return {"ips": container.get("ips")}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the container."""
        await self.coordinator.client.async_start_lxc_container(self._container_name)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the container."""
        await self.coordinator.client.async_stop_lxc_container(self._container_name)
        await self.coordinator.async_request_refresh()
