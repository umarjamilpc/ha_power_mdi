# MDI Power Demand

[![Version](https://img.shields.io/github/v/release/umarjamilpc/ha_power_mdi?label=version)](https://github.com/umarjamilpc/ha_power_mdi/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/github/license/umarjamilpc/ha_power_mdi)](LICENSE)

Home Assistant custom integration for **Maximum Demand Indicator (MDI)** tracking from grid power sensors.

It mirrors typical utility meter behavior:

- **Configurable demand blocks** (15, 30, or 60 minutes) aligned to clock boundaries
- **Interval demand** using the utility formula: **kW = kWh ÷ hours**
- **Monthly peak MDI** that only increases when a new block beats the previous peak
- **Reading snapshot** for comparing with your utility bill on meter-reading day

Works with:

- **Signed power** — one sensor (positive = import, negative = export)
- **Split power** — separate import and export sensors

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=mdi_power_demand)

> Install via HACS or manually first, then use the button above to open the setup dialog.

---

## Features

- Utility-style **interval demand** calculation (kWh-based, not raw power averaging)
- **Instantaneous sampling** on every power entity state update
- Configurable **demand block duration** (15, 30, or 60 minutes)
- **Import** and **export** MDI tracked separately
- Monthly MDI resets on a configurable **reset day** (default: 1st)
- **Capture reading** snapshot on a configurable day/time (default: 14th at 18:00)
- Manual **Capture MDI Reading** button
- Full **Configure** flow after install — change everything without uninstalling
- All entities grouped under one **MDI Power Demand** device
- Values **persist across Home Assistant restarts**

---

## Requirements

- Home Assistant **2024.6+** (tested on **2026.7**)
- A live **power sensor** (W or kW) from your meter or energy monitor
- HACS (recommended) or manual install

---

## Installation

### HACS (recommended)

1. **HACS → Integrations → ⋮ → Custom repositories**
2. Add: `https://github.com/umarjamilpc/ha_power_mdi`
3. Category: **Integration**
4. Install **MDI Power Demand**
5. **Restart Home Assistant**
6. **Settings → Devices & Services → Add Integration → MDI Power Demand**  
   (or use the [Add Integration](https://my.home-assistant.io/redirect/config_flow_start/?domain=mdi_power_demand) button above)

### Manual

1. Copy `custom_components/mdi_power_demand` into your HA `config/custom_components/` folder
2. Restart Home Assistant
3. Add the integration from **Settings → Devices & Services**

### Updates

**HACS → MDI Power Demand → Update**, then **restart Home Assistant**.

---

## Quick start

1. Add the integration
2. Choose **signed** mode (one power sensor) or **split** mode (separate import/export)
3. Select your power sensor(s)
4. Leave defaults unless you know your billing cycle:
   - **Reset day:** `1` (monthly MDI cycle starts on the 1st)
   - **Reading day:** `14` (meter reader visit day)
   - **Block duration:** `30` minutes (match your utility; use 15 or 60 if needed)
5. Wait for the first demand block to complete (up to your block duration)
6. Check `sensor.import_mdi` and `sensor.import_monthly_mdi`

---

## Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| Integration name | Display name in HA | MDI Power Demand |
| Power source mode | `signed` or `split` | signed |
| Input power unit | `auto`, `W`, or `kW` | auto |
| Monthly MDI reset day | Day of month the MDI peak resets (1–28) | 1 |
| Capture reading day | Day to auto-snapshot MDI for billing (1–28) | 14 |
| Capture reading time | Time for auto-snapshot | 18:00 |
| Auto snapshot | Automatically capture MDI on reading day/time | Off |
| Demand block duration | Length of each demand interval (15, 30, or 60 min) | 30 |

> **Reading day** must be on or after **reset day**.

### Reconfigure after install

**Settings → Devices & Services → MDI Power Demand → Configure**

Change mode, sensors, block duration, reset day, reading day/time, and all other settings without uninstalling.

---

## Power source modes

### Signed mode (recommended for Refoss / single meter)

One power sensor where:

| Sign | Meaning |
|------|---------|
| **Positive** | Import from grid |
| **Negative** | Export to grid |

Example entity:

`sensor.grid_main_smart_energy_meter_1_a1_b1_c1_phases_power`

### Split mode

Separate sensors for import and export magnitudes (both typically ≥ 0).

---

## Entities

All entities appear under device **MDI Power Demand**.

| Entity ID | Name | What it shows |
|-----------|------|---------------|
| `sensor.import_mdi` | IMPORT-MDI | Last completed block **import** demand (kW) |
| `sensor.export_mdi` | EXPORT-MDI | Last completed block **export** demand (kW) |
| `sensor.import_monthly_mdi` | IMPORT-MONTHLY-MDI | **Peak import MDI** this billing cycle (kW) — your “MDI display” |
| `sensor.export_monthly_mdi` | EXPORT-MONTHLY-MDI | **Peak export MDI** this billing cycle (kW) |
| `sensor.import_monthly_mdi_at_reading` | IMPORT-MONTHLY-MDI-AT-READING | Frozen import MDI at last capture |
| `sensor.export_monthly_mdi_at_reading` | EXPORT-MONTHLY-MDI-AT-READING | Frozen export MDI at last capture |
| `button.capture_mdi_reading` | CAPTURE-MDI-READING | Press when meter reader arrives |

All power sensors use unit **kW**.

### Which entity is which?

| Question | Entity |
|----------|--------|
| What was the last demand block? | `sensor.import_mdi` |
| What is my peak MDI this month (live)? | `sensor.import_monthly_mdi` |
| What was MDI when the reader came? | `sensor.import_monthly_mdi_at_reading` |

---

## How it works

### 1. Interval demand (each block)

At the end of each demand block, the integration calculates:

$$\text{Interval Demand (kW)} = \frac{\text{Energy used in interval (kWh)}}{\text{Interval time (hours)}}$$

For a 30-minute block, interval time = **0.5 hours**. For 15 min use **0.25 h**; for 60 min use **1.0 h**.

**Steps inside each block:**

1. Sample power **instantaneously whenever the source entity updates**
2. Convert each sub-interval to energy: `kWh = kW × seconds ÷ 3600`
3. Sum import and export energy separately over the full block
4. Divide by block duration in hours → interval demand in kW

**Example (30 min):** 0.383 kWh import → **0.383 ÷ 0.5 = 0.766 kW**

This updates `sensor.import_mdi` / `sensor.export_mdi`.

### 2. Monthly peak MDI (provider-style)

At the end of every demand block, the integration compares that block’s kW with the existing monthly peak:

- If the new block is **higher** → monthly MDI is **overwritten** with the new value
- If lower or equal → monthly MDI **stays unchanged**

This matches typical utility meter MDI display behavior and updates `sensor.import_monthly_mdi`.

### 3. Monthly reset

On your configured **reset day** (default **1st**), import/export monthly MDI peaks reset to zero and a new billing cycle begins.

### 4. Reading snapshot

On **reading day** (default **14th**):

- With **auto snapshot off:** press **Capture MDI Reading** when the meter reader arrives
- With **auto snapshot on:** MDI is captured automatically at **reading time** (default 18:00)

The current monthly peak is copied to `sensor.import_monthly_mdi_at_reading` for bill comparison.

---

## Demand block timing

Blocks align to clock boundaries for your chosen duration:

| Duration | Boundaries | Example blocks |
|----------|------------|----------------|
| **15 min** | `:00`, `:15`, `:30`, `:45` | 1:00→1:15, 1:15→1:30 |
| **30 min** | `:00`, `:30` | 1:00→1:30, 1:30→2:00 |
| **60 min** | `:00` each hour | 1:00→2:00, 2:00→3:00 |

If you add the integration at **1:15 PM** with 30-min blocks, the first tracked block starts at **1:30 PM** (next boundary).

`IMPORT-MDI` updates when each block completes.

---

## Power sampling

Power is sampled **on every state change** of your configured power entity (or import/export entities in split mode). Energy between updates is calculated using the elapsed time and the last known power reading — no fixed polling interval.

This works well with meters like Refoss that publish roughly every 60 seconds. More frequent updates give finer energy integration within each block.

---

## Typical billing workflow

1. Let the integration run through the month
2. Watch **`sensor.import_monthly_mdi`** as your live peak MDI
3. On meter-reading day (e.g. 14th), press **Capture MDI Reading** when the reader visits  
   (or enable **auto snapshot** at 18:00)
4. Compare **`sensor.import_monthly_mdi_at_reading`** with the value on your utility bill
5. Monthly MDI resets on your **reset day** (e.g. 1st)

### Meter reader window tip

If your reader visits between **10:00 AM and 6:00 PM**:

- Set **capture reading time** to **18:00** (end of window), or
- Press **Capture MDI Reading** manually when they arrive (most accurate)

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `import_mdi` shows `unknown` | No completed demand block yet — wait for the next block boundary |
| Monthly MDI stuck at `0.0` | No block completed since install, or only export (no import) |
| Configure gives 500 error | Update to latest version (v0.1.7+) and restart HA |
| Values differ slightly from utility meter | Small differences are normal due to sensor update timing vs meter internal sampling |
| After update, old long entity names remain | Delete orphaned old entities from **Settings → Entities** |

---

## Example dashboard cards

**Last block + live monthly peak:**

```yaml
type: entities
entities:
  - entity: sensor.import_mdi
  - entity: sensor.export_mdi
  - entity: sensor.import_monthly_mdi
  - entity: sensor.export_monthly_mdi
  - entity: sensor.import_monthly_mdi_at_reading
  - entity: button.capture_mdi_reading
```

---

## Versioning

Versions follow [Semantic Versioning](https://semver.org/):

- **Major** — breaking changes
- **Minor** — new features
- **Patch** — bug fixes

Current version is in `custom_components/mdi_power_demand/manifest.json`. HACS compares it with [GitHub Releases](https://github.com/umarjamilpc/ha_power_mdi/releases).

See [CHANGELOG.md](CHANGELOG.md) for release history.

---

## Support

- [GitHub Issues](https://github.com/umarjamilpc/ha_power_mdi/issues)
- [Releases](https://github.com/umarjamilpc/ha_power_mdi/releases)

## License

MIT — see [LICENSE](LICENSE)
