# Fsolar Cloud for Home Assistant

Custom Home Assistant integration for Felicity Solar's Fsolar cloud API.

The integration exposes these controls for every supported inverter:

- **Source Priority Charge** (`select`):
  - `CSO` — Solar first
  - `SNU` — Solar and utility
  - `OSO` — Only solar
- **Maximum grid charge current** (`number`): 10–240 A in whole-amp steps.

Every write is sent to the selected inverter only. The integration waits for
the cloud command result and then reads the setting back before reporting the
new state.

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
