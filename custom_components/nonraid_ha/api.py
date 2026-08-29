"""Async client for the nonraid-webui REST API.

Mirrors the request/auth/error handling of the project's own reference TypeScript client
(nonraid-webui's cli/src/api/client.ts): base URL + "/api" + path, `Authorization: Bearer <token>`
header, and a `{"error": string}` JSON error body. Every route except `/api/health` and
`/api/auth/*` requires that header - see nonraid-webui's backend/API.md and
backend/src/auth/middleware.ts's requireAuth.

Uses aiohttp exclusively (never the synchronous `requests` library) via a ClientSession handed in
by the caller - see homeassistant.helpers.aiohttp_client.async_get_clientsession.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 20


class NonraidHaError(Exception):
    """Base error for the nonraid-webui API client."""


class NonraidHaConnectionError(NonraidHaError):
    """Raised when the host can't be reached at all (DNS, TCP, TLS, timeout)."""


class NonraidHaApiError(NonraidHaError):
    """Raised for an HTTP error response from the API."""

    def __init__(self, status: int, message: str, code: str | None = None) -> None:
        """Set up the error with the HTTP status, message, and optional machine-readable code."""
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


class NonraidHaAuthError(NonraidHaApiError):
    """Raised on 401 - missing, invalid, or expired token."""


class NonraidHaReadOnlyError(NonraidHaApiError):
    """Raised on 403 - a read-only token attempted a request that mutates state."""


class NonraidHaApiClient:
    """Thin async wrapper over nonraid-webui's REST API."""

    def __init__(self, host: str, token: str, session: aiohttp.ClientSession) -> None:
        """Set up the client. `host` is scheme+host[:port], no trailing slash, no /api."""
        self._base_url = host.rstrip("/")
        self._token = token
        self._session = session

    @property
    def base_url(self) -> str:
        """Return the configured host's base URL (no trailing slash, no /api)."""
        return self._base_url

    async def _request(
        self, method: str, path: str, json_body: dict[str, Any] | None = None
    ) -> Any:
        """Make one authenticated request and return the parsed JSON body (or None)."""
        url = f"{self._base_url}/api{path}"
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                response = await self._session.request(
                    method, url, json=json_body, headers=headers
                )
                text = await response.text()
        except TimeoutError as err:
            raise NonraidHaConnectionError(f"Timed out contacting {url}") from err
        except aiohttp.ClientError as err:
            raise NonraidHaConnectionError(str(err)) from err

        content: Any = None
        if text:
            try:
                content = json.loads(text)
            except ValueError:
                content = None

        if response.status >= 400:
            message = response.reason or f"HTTP {response.status}"
            code = None
            if isinstance(content, dict):
                if isinstance(content.get("error"), str) and content["error"]:
                    message = content["error"]
                if isinstance(content.get("code"), str):
                    code = content["code"]

            if response.status == 401:
                raise NonraidHaAuthError(response.status, message, code)
            if response.status == 403 and "read-only" in message.lower():
                raise NonraidHaReadOnlyError(response.status, message, code)
            raise NonraidHaApiError(response.status, message, code)

        return content

    async def get(self, path: str) -> Any:
        """Issue a GET request."""
        return await self._request("GET", path)

    async def post(self, path: str, json_body: dict[str, Any] | None = None) -> Any:
        """Issue a POST request."""
        return await self._request("POST", path, json_body or {})

    async def put(self, path: str, json_body: dict[str, Any] | None = None) -> Any:
        """Issue a PUT request."""
        return await self._request("PUT", path, json_body or {})

    # -- Status & Array --

    async def async_get_status(self) -> dict[str, Any] | None:
        """Return `nmdctl status -o json` (array/resync/disks), or None if never configured.

        A fresh install with no array ever created answers 404 with
        `code: "ARRAY_NOT_CONFIGURED"` (not an error worth failing the whole coordinator update
        over) - see backend/src/routes/status.ts.
        """
        try:
            return await self.get("/status")
        except NonraidHaApiError as err:
            if err.status == 404 and err.code == "ARRAY_NOT_CONFIGURED":
                return None
            raise

    # -- Disks --

    async def async_spin_up_disk(self, slot: int) -> dict[str, Any]:
        """Spin up the disk in this slot. Requires a full-access token."""
        return await self.post(f"/disks/{slot}/spin-up")

    async def async_spin_down_disk(self, slot: int) -> dict[str, Any]:
        """Spin down the disk in this slot. Requires a full-access token.

        A 409 from the backend (a parity check/clear is active) surfaces as a normal
        NonraidHaApiError - the caller decides whether/how to report it.
        """
        return await self.post(f"/disks/{slot}/spin-down")

    # -- SMART --

    async def async_get_smart_temperatures(self) -> dict[str, float | None]:
        """Return `{device: temperature_celsius}` for every disk currently in the array."""
        return await self.get("/smart/temperatures") or {}

    async def async_get_smart_health(self) -> dict[str, str | None]:
        """Return `{device: "passed" | "failed" | None}` for every disk currently in the array."""
        return await self.get("/smart/health") or {}

    async def async_get_smart_spin_states(self) -> dict[str, str]:
        """Return `{device: "active" | "standby" | "unknown"}` for every disk currently in the array.

        Never spins up a sleeping disk to check (smartctl's `-n standby` early-exit) - safe to
        poll on every coordinator refresh.
        """
        return await self.get("/smart/spin-states") or {}

    # -- System --

    async def async_get_system(self) -> dict[str, Any]:
        """Return host stats: hostname, uptime, cpu/mem, boot disk, ..."""
        return await self.get("/system")

    # -- Cache --

    async def async_get_cache_status(self) -> dict[str, Any]:
        """Return the mirrored cache pool's health/usage."""
        return await self.get("/cache/status")

    # -- Docker --

    async def async_get_docker_containers(self) -> list[dict[str, Any]]:
        """Return every Docker container's current summary."""
        return await self.get("/docker/containers") or []

    async def async_start_docker_container(self, container_id: str) -> dict[str, Any]:
        """Start a Docker container. Requires a full-access token."""
        return await self.post(f"/docker/containers/{container_id}/start")

    async def async_stop_docker_container(self, container_id: str) -> dict[str, Any]:
        """Stop a Docker container. Requires a full-access token."""
        return await self.post(f"/docker/containers/{container_id}/stop")

    # -- LXC --

    async def async_get_lxc_containers(self) -> list[dict[str, Any]]:
        """Return every LXC container's current summary."""
        return await self.get("/lxc/containers") or []

    async def async_start_lxc_container(self, name: str) -> dict[str, Any]:
        """Start an LXC container. Requires a full-access token."""
        return await self.post(f"/lxc/containers/{name}/start")

    async def async_stop_lxc_container(self, name: str) -> dict[str, Any]:
        """Stop an LXC container. Requires a full-access token."""
        return await self.post(f"/lxc/containers/{name}/stop")

    # -- Shares (Pools) --

    async def async_get_shares(self) -> list[dict[str, Any]]:
        """Return every pool's config, live usage stats, and active SMB connection count."""
        return await self.get("/shares") or []

    # -- Settings --

    async def async_get_disk_labels(self) -> dict[str, str]:
        """Return the user's disk_id -> nickname map from /settings (empty if none are set)."""
        settings = await self.get("/settings")
        labels = settings.get("diskLabels") if isinstance(settings, dict) else None
        return labels if isinstance(labels, dict) else {}

    # -- Validation (used by the config flow) --

    async def async_validate(self) -> dict[str, Any]:
        """Make one real authenticated read call, to confirm the host/token actually work.

        `GET /system` is used rather than `GET /status` because it has no "array not configured"
        edge case (it works before an array has ever been created) and is cheap on every backend
        state.
        """
        return await self.async_get_system()
