# NonRAID-HA

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]

Home Assistant integration for [nonraid-webui](https://github.com/domgregori/nonraid-webui), the
NonRAID NAS dashboard's REST API. Authenticates with a `nonraid-tool` API bearer token (the same
token mechanism the CLI uses) and works with either a full-access or a read-only token - a
read-only token just skips the container start/stop switches, since it can't perform them.

**This component sets up the following platforms.**

| Platform        | Description                                                                 |
| ---------------- | ---------------------------------------------------------------------------- |
| `sensor`        | Array state/health, parity check progress, uptime, installed CLI version, host CPU/memory/temperature, cache pool health/usage, per-pool active SMB streams/usage, per-disk temperature/SMART health/spin state/used space (nicknamed per the webui's own disk-labels setting when one is set). |
| `binary_sensor` | Array in an error/degraded state; any disk failed or missing.               |
| `switch`        | Start/stop a Docker container or an LXC container, spin an HDD up/down (SSDs don't get this control) (full-access token only). |
| `update`        | Installed/latest release for the NonRAID driver and the WebUI itself. Read-only - use nonraid-webui's own Settings → Update page to actually apply one. |

Array start/stop, cache setup/replace, and system-level actions (reboot, hostname/timezone) are
deliberately left out of this first pass as too high-blast-radius for a single entity toggle.
Diagnostics (Settings → Devices & Services → NonRAID → Download diagnostics) are supported and
never include the bearer token or host.

## Installation

### HACS (recommended)

This repository isn't in the default HACS store yet, so add it as a custom repository.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=domgregori&repository=nonraid-ha&category=integration)

1. Click the button above (or, in HACS, open the three-dot menu (top right) → **Custom
   repositories** and add `https://github.com/domgregori/nonraid-ha` with type **Integration**).
2. Search HACS for "NonRAID" and install it.
3. Restart Home Assistant.
4. In the HA UI go to "Settings" -> "Devices & Services" click "+ Add Integration" and search for
   "NonRAID".

### Manual

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `nonraid_ha`.
4. Download _all_ the files from the `custom_components/nonraid_ha/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. In the HA UI go to "Settings" -> "Devices & Services" click "+ Add Integration" and search for
   "NonRAID"

## Configuration is done in the UI

Mint an API token from the nonraid-webui UI (Settings → Security → API tokens) or with
`nonraid-tool login` / `nonraid-tool login --read-only`, then enter your host (e.g.
`https://nonraid.lan`) and that token when adding the integration.

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

## Credits

This project was generated from [@oncleben31](https://github.com/oncleben31)'s [Home Assistant Custom Component Cookiecutter](https://github.com/oncleben31/cookiecutter-homeassistant-custom-component) template.

Code template was mainly taken from [@Ludeeus](https://github.com/ludeeus)'s [integration_blueprint][integration_blueprint] template

---

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[black]: https://github.com/psf/black
[black-shield]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/domgregori
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/domgregori/nonraid-ha.svg?style=for-the-badge
[commits]: https://github.com/domgregori/nonraid-ha/commits/main
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg?style=for-the-badge
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/domgregori/nonraid-ha.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40domgregori-blue.svg?style=for-the-badge
[pre-commit]: https://github.com/pre-commit/pre-commit
[pre-commit-shield]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/domgregori/nonraid-ha.svg?style=for-the-badge
[releases]: https://github.com/domgregori/nonraid-ha/releases
[user_profile]: https://github.com/domgregori
