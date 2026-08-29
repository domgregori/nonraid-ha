"""Config flow for the NonRAID integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    NonraidHaApiClient,
    NonraidHaAuthError,
    NonraidHaConnectionError,
    NonraidHaError,
)
from .const import (
    CONF_HOST,
    CONF_READ_ONLY,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
    DEFAULT_READ_ONLY,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _token_selector() -> selector.TextSelector:
    """Return a password-masked text selector for the API token field."""
    return selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    )


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the host/token by making one real authenticated call.

    Returns the `GET /api/system` payload on success. Raises NonraidHaConnectionError,
    NonraidHaAuthError, or NonraidHaError (any other API error) on failure.
    """
    session = async_get_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL))
    client = NonraidHaApiClient(data[CONF_HOST], data[CONF_TOKEN], session)
    return await client.async_validate()


def _normalize_host(host: str) -> str:
    """Strip whitespace/trailing slashes from a user-supplied host URL."""
    return host.strip().rstrip("/")


class NonraidHaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NonRAID."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the initial step: host + token + verify_ssl + read-only."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = _normalize_host(user_input[CONF_HOST])
            if not host.startswith(("http://", "https://")):
                errors[CONF_HOST] = "invalid_host"
            else:
                data = {
                    CONF_HOST: host,
                    CONF_TOKEN: user_input[CONF_TOKEN],
                    CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    CONF_READ_ONLY: user_input[CONF_READ_ONLY],
                }
                try:
                    system = await _validate_input(self.hass, data)
                except NonraidHaAuthError:
                    errors["base"] = "invalid_auth"
                except NonraidHaConnectionError:
                    errors["base"] = "cannot_connect"
                except NonraidHaError:
                    errors["base"] = "unknown"
                except Exception:  # noqa: BLE001 - config flow must never crash on a bad input
                    _LOGGER.exception("Unexpected error validating NonRAID connection")
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(host.lower())
                    self._abort_if_unique_id_configured()
                    hostname = system.get("hostname") if isinstance(system, dict) else None
                    title = f"NonRAID ({hostname})" if hostname else "NonRAID"
                    return self.async_create_entry(title=title, data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str,
                vol.Required(CONF_TOKEN): _token_selector(),
                vol.Required(
                    CONF_VERIFY_SSL,
                    default=(user_input or {}).get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                ): bool,
                vol.Required(
                    CONF_READ_ONLY,
                    default=(user_input or {}).get(CONF_READ_ONLY, DEFAULT_READ_ONLY),
                ): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle re-authentication triggered by a 401 (token revoked/expired)."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Collect a new token and re-validate against the existing host."""
        errors: dict[str, str] = {}
        assert self._reauth_entry is not None

        if user_input is not None:
            data = {
                **self._reauth_entry.data,
                CONF_TOKEN: user_input[CONF_TOKEN],
                CONF_READ_ONLY: user_input[CONF_READ_ONLY],
            }
            try:
                await _validate_input(self.hass, data)
            except NonraidHaAuthError:
                errors["base"] = "invalid_auth"
            except NonraidHaConnectionError:
                errors["base"] = "cannot_connect"
            except NonraidHaError:
                errors["base"] = "unknown"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating NonRAID connection")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(self._reauth_entry, data=data)
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN): _token_selector(),
                vol.Required(
                    CONF_READ_ONLY,
                    default=self._reauth_entry.data.get(CONF_READ_ONLY, DEFAULT_READ_ONLY),
                ): bool,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={CONF_HOST: self._reauth_entry.data.get(CONF_HOST, "")},
        )
