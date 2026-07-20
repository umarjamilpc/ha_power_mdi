# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/umarjamilpc/ha_power_mdi/releases/tag/v0.1.0
