# Fsolar Cloud for Home Assistant

Custom Home Assistant integration for Felicity Solar's Fsolar cloud API.

The integration exposes these controls for every supported inverter:

- **Source Priority Charge** (`select`):
  - `CSO` — Solar first
  - `SNU` — Solar and utility
  - `OSO` — Only solar
- **Output source priority** (`select`):
  - `UTI` — Utility first
  - `SUB` — Solar first, then utility, then battery
  - `SBU` — Solar first, then battery, then utility
- **Maximum grid charge current** (`number`): 10–240 A in whole-amp steps.

Every write is sent to the selected inverter only. The integration waits for
the cloud command result and then reads the setting back before reporting the
new state.

## Battery reserve control

Version 0.4.1 includes a SolarAssistant-style reserve controller configured from:

**Settings → Devices & services → Fsolar Cloud → Configure**

The single options screen lets you:

1. Select every Home Assistant sensor that reports an individual battery SOC.
2. Enable or disable automatic reserve control.
3. Configure low and high SOC thresholds at daily points A and B.

Points A and B are expanded on the same screen. The fields explicitly show
which level selects `UTI` (Utility first) and which level selects `SBU`
(Solar/Battery/Utility).

The defaults define a flat 24-hour reserve:

- Point A at 08:00: `UTI` at 50% or lower and `SBU` at 55% or higher.
- Point B at 18:00: `UTI` at 50% or lower and `SBU` at 55% or higher.

Thresholds are linearly interpolated between the two points, including across
midnight. The controller uses the **lowest** selected SOC:

- At or below the current low threshold, all inverters are changed
  individually to `UTI`.
- At or above the current high threshold, all inverters are changed
  individually to `SBU`.
- Between both thresholds, the current priorities are left unchanged to
  provide hysteresis.

Automatic control is disabled by default after upgrading. When it is enabled,
every selected SOC sensor must be available and report a number from 0 to 100.
If any selected sensor is missing or invalid, the controller sends no command.

Home Assistant also creates a **Fsolar Battery Reserve** service device with:

- Reserve control enabled.
- Minimum battery SOC.
- Current low and high thresholds.
- Consensus output priority across the inverters.
- Controller status and error details.
- Time of the last controller-initiated change.

Do not run SolarAssistant Power Management or another automation that changes
output source priority at the same time. Competing controllers can repeatedly
override each other.

## Installation

Copy `custom_components/fsolar` into Home Assistant's
`/config/custom_components` directory and restart Home Assistant. Then add
**Fsolar Cloud** from **Settings → Devices & services**.

For HACS, add this repository as a custom integration repository.

## Notes

This integration uses an undocumented cloud API observed in the official
Fsolar web application. It is not affiliated with Felicity Solar. Cloud API
changes may require an integration update.

Credentials are stored in the Home Assistant config entry. Diagnostic logging
must never include passwords or session tokens.
