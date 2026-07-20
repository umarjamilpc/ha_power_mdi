# MDI Power Demand

[![Version](https://img.shields.io/github/v/release/umarjamilpc/ha_power_mdi?label=version)](https://github.com/umarjamilpc/ha_power_mdi/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/github/license/umarjamilpc/ha_power_mdi)](LICENSE)

Home Assistant custom integration for tracking **Maximum Demand Indicator (MDI)** from power sensors using **30-minute block averages** aligned to `:00` and `:30`.

Works with:
- **Signed power** (one sensor: positive = import, negative = export)
- **Split power** (separate import and export sensors)

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=mdi_power_demand)

> **Note:** Install the integration via HACS or manually first, then use the button above to open the setup dialog.

## Features

- 30-minute demand blocks synced to clock boundaries (`:00` / `:30`)
- Monthly MDI max tracking (import / export / combined) in **kW**
- Configurable monthly reset day
- Meter reading snapshot on a configurable day and time
- Manual **Capture Reading** button
- Full reconfiguration via **Options** after install (no uninstall needed)
- Persists MDI values across Home Assistant restarts

## Installation

### HACS (recommended)

1. Open **HACS → Integrations → ⋮ → Custom repositories**
2. Add repository URL: `https://github.com/umarjamilpc/ha_power_mdi`
3. Select category: **Integration**
4. Install **MDI Power Demand**
5. Restart Home Assistant
6. Click the **Add Integration** button at the top of this README, or go to **Settings → Devices & Services → Add Integration** and search for **MDI Power Demand**

### Manual

1. Copy `custom_components/mdi_power_demand` into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Use the **Add Integration** button above or add the integration from **Settings → Devices & Services**

## Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| Power source mode | `signed` or `split` | signed |
| Input power unit | `auto`, `W`, or `kW` | auto |
| Monthly MDI reset day | Day of month MDI resets | 1 |
| Capture reading day | Day meter is read | 14 |
| Capture reading time | Auto snapshot time | 18:00 |
| Auto snapshot | Enable scheduled capture | Off |
| Power sampling interval | Minutes between power samples inside each 30-min block | 1 |

## How interval demand is calculated

This matches the utility meter formula:

**Interval Demand (kW) = Energy used in interval (kWh) ÷ Interval time (hours)**

For each 30-minute block (`:00` → `:30` or `:30` → `:00`):

1. Read instantaneous power at your configured sampling interval (default **1 minute**)
2. Convert each sub-interval to energy: `kWh = kW × minutes / 60`
3. Sum energy over the full 30 minutes
4. **Demand = total kWh ÷ 0.5 hours** (30 min = 0.5 h)

Example: if you use **0.383 kWh** import in 30 minutes → demand = **0.383 ÷ 0.5 = 0.766 kW**.

Set **sampling interval = 1 minute** to match typical utility CT meters and your Refoss ~60s updates.

### Signed mode

Use one power sensor where:
- **Positive** values = import
- **Negative** values = export

Example:
`sensor.grid_main_smart_energy_meter_1_a1_b1_c1_phases_power`

### Split mode

Use separate sensors for import and export magnitudes (both typically ≥ 0).

## Entities created

- Import / Export / Combined **30-min avg** (last completed block)
- Import / Export / Combined **MDI (monthly max)**
- Import / Export / Combined **MDI at reading** (snapshot)
- **Capture Reading** button

## 30-minute sync behavior

If the integration starts at **1:15 PM**, the first block begins at **1:30 PM** (next `:00` or `:30` boundary). This keeps MDI aligned with utility billing windows.

## Meter reader window tip

If your meter reader typically visits between **10:00 AM and 6:00 PM**, set:
- **Capture reading time**: `18:00:10` (recommended)
- Or press **Capture Reading** when the reader is at your meter for the most accurate snapshot

## Reconfigure after install

**Settings → Devices & Services → MDI Power Demand → Configure**

You can change power source mode, sensors, reset day, reading day/time, and all other settings without uninstalling.

## Versioning

Versions follow [Semantic Versioning](https://semver.org/):

- **Major** — breaking changes
- **Minor** — new features, backward compatible
- **Patch** — bug fixes

The active version is defined in `custom_components/mdi_power_demand/manifest.json`. HACS reads this file and compares it with [GitHub Releases](https://github.com/umarjamilpc/ha_power_mdi/releases) to show the installed version and available updates.

See [CHANGELOG.md](CHANGELOG.md) for release history.

## License

MIT — see [LICENSE](LICENSE)
