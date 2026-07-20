# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.5] - 2026-07-20

### Fixed

- Setup failure caused by calling `dt.now(hass)` — HA's `now()` expects a timezone, not a HomeAssistant instance

## [0.1.4] - 2026-07-20

### Fixed

- Setup failure on Home Assistant 2026.7+ caused by deprecated `storage_version` argument to `Store`
- Storage now uses the current `Store(hass, version, key)` API

## [0.1.3] - 2026-07-20

### Fixed

- Config flow 500 on Home Assistant 2026.7 caused by `cv.time` failing schema JSON serialization
- Restored native HA selectors (`TimeSelector`, `EntitySelector`, `SelectSelector`, etc.) which serialize correctly
- Config flow now registers via `domain=DOMAIN` class syntax

## [0.1.2] - 2026-07-20

### Fixed

- Config flow 500 caused by selector schema recursion in Home Assistant JSON preparation
- Replaced selector widgets with standard `vol.In`, `cv.entity_id`, and `cv.time` validators
- Registered config flow with `@config_entries.HANDLERS.register` for broader compatibility

## [0.1.1] - 2026-07-20

### Fixed

- Config flow 500 error caused by non-serializable time defaults
- Config entry now stores reading time as `HH:MM:SS` string
- Entity selectors use native Home Assistant selectors
- Coordinator safely parses stored reading time values

## [0.1.0] - 2026-07-20

### Added

- Initial release of MDI Power Demand integration
- Signed and split power source modes
- 30-minute block averages synced to `:00` / `:30`
- Monthly MDI max tracking for import, export, and combined demand (kW)
- Configurable monthly reset day and meter reading day/time
- Automatic reading snapshot and manual Capture Reading button
- Full post-install reconfiguration via Options
- Persistent MDI storage across Home Assistant restarts

[0.1.5]: https://github.com/umarjamilpc/ha_power_mdi/releases/tag/v0.1.5
[0.1.4]: https://github.com/umarjamilpc/ha_power_mdi/releases/tag/v0.1.4
[0.1.3]: https://github.com/umarjamilpc/ha_power_mdi/releases/tag/v0.1.3
[0.1.2]: https://github.com/umarjamilpc/ha_power_mdi/releases/tag/v0.1.2
[0.1.1]: https://github.com/umarjamilpc/ha_power_mdi/releases/tag/v0.1.1
[0.1.0]: https://github.com/umarjamilpc/ha_power_mdi/releases/tag/v0.1.0
