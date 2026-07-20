# MDI Power Demand

Home Assistant custom integration for tracking **Maximum Demand Indicator (MDI)** from power sensors using **30-minute block averages** aligned to `:00` and `:30`.

Works with:
- **Signed power** (one sensor: positive = import, negative = export)
- **Split power** (separate import and export sensors)

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

1. Add this repository as a custom HACS integration:
   - Repository URL: `https://github.com/umarjamilpc/ha_power_mdi`
2. Install **MDI Power Demand** from HACS
3. Restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration**
5. Search for **MDI Power Demand**

### Manual

Copy `custom_components/mdi_power_demand` into your Home Assistant `config/custom_components/` directory, then restart Home Assistant.

## Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| Power source mode | `signed` or `split` | signed |
| Input power unit | `auto`, `W`, or `kW` | auto |
| Monthly MDI reset day | Day of month MDI resets | 1 |
| Capture reading day | Day meter is read | 14 |
| Capture reading time | Auto snapshot time | 18:00 |
| Auto snapshot | Enable scheduled capture | Off |

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

## License

MIT — see [LICENSE](LICENSE)
