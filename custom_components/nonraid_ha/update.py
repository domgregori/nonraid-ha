"""Update platform for the NonRAID integration.

Read-only: neither entity supports installing (no `UpdateEntityFeature.INSTALL`). The driver's
own update needs a manual "reload from Settings > Services" follow-up that nonraid-webui itself
prompts for, and the webui's own update self-restarts the backend (dropping every client's
connection) - both too disruptive for a single HA entity action, same reasoning as everything left
out of switch.py. Use nonraid-webui's own Settings > Update page to actually apply an update; this
integration only reports whether one is available.

The CLI's own version has no independent latest/update state here - it ships from the same
release as the webui and is always rebuilt+reinstalled alongside it - see sensor.py's plain
"CLI Version" sensor instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NonraidHaDataUpdateCoordinator
from .const import DOMAIN
from .entity import NonraidHaEntity


@dataclass(frozen=True, kw_only=True)
class NonraidHaUpdateEntityDescription(UpdateEntityDescription):
    """Describes one updatable NonRAID component."""

    component_key: str  # "nonraid" or "nonraidWebui" - matches UpdateStatus's own keys.


UPDATE_DESCRIPTIONS: tuple[NonraidHaUpdateEntityDescription, ...] = (
    NonraidHaUpdateEntityDescription(
        key="nonraid_driver_update",
        name="NonRAID Driver",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        component_key="nonraid",
    ),
    NonraidHaUpdateEntityDescription(
        key="nonraid_webui_update",
        name="NonRAID WebUI",
        icon="mdi:web",
        entity_category=EntityCategory.DIAGNOSTIC,
        component_key="nonraidWebui",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up NonRAID update entities for this config entry."""
    coordinator: NonraidHaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(NonraidHaUpdateEntity(coordinator, description) for description in UPDATE_DESCRIPTIONS)


class NonraidHaUpdateEntity(NonraidHaEntity, UpdateEntity):
    """Reports one NonRAID component's installed/latest release tag. Installing isn't supported."""

    entity_description: NonraidHaUpdateEntityDescription

    def __init__(
        self,
        coordinator: NonraidHaDataUpdateCoordinator,
        entity_description: NonraidHaUpdateEntityDescription,
    ) -> None:
        """Set up the entity from its description."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._entry_id}_{entity_description.key}"

    def _component(self) -> dict[str, Any]:
        return self.coordinator.data.update_status.get(self.entity_description.component_key) or {}

    @property
    def installed_version(self) -> str | None:
        """Return the release tag this component was actually built/installed from.

        None until the repo's first tag is pushed and a fresh install/update is built from it -
        true for every install today (see ComponentUpdateStatus.installed's own doc comment in
        nonraid-webui's backend/src/update/service.ts).
        """
        return self._component().get("installed")

    @property
    def latest_version(self) -> str | None:
        """Return the newest release tag currently pushed to the component's repo, if known."""
        return self._component().get("latest")

    @property
    def available(self) -> bool:
        """Return whether an update check has ever completed."""
        return super().available and self.coordinator.data.update_status.get("checkedAt") is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Surface the raw up-to-date/check-error fields underlying this entity's computed state."""
        component = self._component()
        return {"up_to_date": component.get("upToDate"), "check_error": component.get("checkError")}
