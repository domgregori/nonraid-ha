[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]

Home Assistant integration for [nonraid-webui](https://github.com/domgregori/nonraid-webui). Works
with either a full-access or a read-only `nonraid-tool` API token.

**This component sets up the following platforms.**

| Platform        | Description                                                                 |
| ---------------- | ---------------------------------------------------------------------------- |
| `sensor`        | Array state/health, parity progress, uptime, CLI version, host CPU/mem/temp, cache health/usage, per-pool streams/usage, per-disk temp/SMART/spin/used space. |
| `binary_sensor` | Array in an error/degraded state; any disk failed or missing.               |
| `switch`        | Start/stop a Docker or LXC container, spin a disk up/down (full-access token only). |
| `update`        | Installed/latest release for the driver and WebUI (read-only).              |

{% if not installed %}

## Installation

1. Click install.
1. In the HA UI go to "Settings" -> "Devices & Services" click "+ Add Integration" and search for
   "NonRAID".

{% endif %}

## Configuration is done in the UI

Mint an API token from the nonraid-webui UI (Settings → Security → API tokens) or with
`nonraid-tool login` / `nonraid-tool login --read-only`.

## Credits

This project was generated from [@oncleben31](https://github.com/oncleben31)'s [Home Assistant Custom Component Cookiecutter](https://github.com/oncleben31/cookiecutter-homeassistant-custom-component) template.

Code template was mainly taken from [@Ludeeus](https://github.com/ludeeus)'s [integration_blueprint][integration_blueprint] template

---

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[buymecoffee]: https://www.buymeacoffee.com/ludeeus
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
[license]: https://github.com/domgregori/nonraid-ha/blob/main/LICENSE
[license-shield]: https://img.shields.io/github/license/domgregori/nonraid-ha.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40domgregori-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/domgregori/nonraid-ha.svg?style=for-the-badge
[releases]: https://github.com/domgregori/nonraid-ha/releases
[user_profile]: https://github.com/domgregori
