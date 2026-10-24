# Home Assistant Architecture & "Frenck Review" Quality Standards

Whenever writing, modifying, or reviewing code for Home Assistant integrations (custom or core), agents MUST adhere to these architectural standards. These rules reflect the strict criteria enforced by core maintainers (e.g., @frenck) and the Home Assistant Architectural Decision Records (ADRs).

---

## 1. Zero Unbounded Recursion & Authentication Storm Prevention
- **No Infinite Error Recursion**:
  - Never allow API client methods (`login`, `get_telemetry`, `control_device`) to call themselves recursively on error without a strictly bounded counter (e.g. `retry_on_auth: bool = True`, defaulting to `False` on the next call).
- **Strict Distinction between Auth and Network Failures**:
  - Distinguish between **Authentication Failures** (invalid credentials, expired token that cannot renew, changed password) and **Network Failures** (DNS failure, timeout, socket reset).
  - Define explicit exceptions: `OukitelAuthError` vs `OukitelConnectionError`.
- **Handling Auth Failures**:
  - On auth failure: **Halt immediately**. Do not retry on polling cycles.
  - Raise `ConfigEntryAuthFailed` from coordinators or setup, or call `config_entry.async_start_reauth(hass)`.
  - In `config_flow.py`, **always provide `async_step_reauth` and `async_step_reauth_confirm`** so users can update credentials without deleting/re-adding the integration.
- **Handling Network Errors**:
  - Apply **exponential backoff** (e.g. 60s → 120s → 240s … max 900s) on background reconnections.
  - Raise `UpdateFailed` during polling to let DataUpdateCoordinator handle retry intervals.

---

## 2. Offline-First Boot & Branch Import Integrity
- **The "Unplugged Router" Test**:
  - Every integration MUST cleanly handle starting up when the internet is dead, when local LAN is dead, or when both are dead.
  - Offline startup must NEVER crash with uncaught exceptions or `NameError`.
  - If a device is unreachable on boot, raise `ConfigEntryNotReady` so Home Assistant automatically retries in the background.
- **Import Verification in Infrequent Branches**:
  - Verify all modules used in error handling and offline fallbacks (e.g., `import asyncio` when calling `await asyncio.sleep()`) are imported at the top of the file.
  - Do not assume global built-ins exist for module-level functions.

---

## 3. Privacy-First & Zero External Frontend Requests (ADR-0014)
- **Zero Third-Party CDN Calls**:
  - Never load external stylesheets, fonts, or scripts (e.g., `fonts.googleapis.com`, unpkg, cdnjs) on dashboard page loads.
  - External calls violate Home Assistant privacy policies and fail completely in isolated/offline local setups.
- **Local Asset Bundling**:
  - All web fonts (`.woff2`), icons, and scripts must be bundled locally inside `custom_components/<domain>/frontend/` and served via `hass.http.async_register_static_paths`.
  - Maintain system font fallbacks: `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace, sans-serif`.

---

## 4. Multi-Version Python Compatibility & Typing
- **Explicit Typing Imports**:
  - Always import all type hints (`from typing import Any, Mapping, cast`).
  - Do not rely on Python 3.14+ deferred annotation evaluation when `manifest.json` or `hacs.json` supports Home Assistant versions running Python 3.12 or 3.13.
- **Minimum HA Version Compliance**:
  - Ensure syntax is valid for the lowest Home Assistant version declared in `hacs.json` and `manifest.json`.

---

## 5. Unsuppressed CI / Catalog Validation
- **No Check Suppression in CI**:
  - Never use `ignore: ...` flags in GitHub Actions workflows (e.g. `ignore: license`) to bypass HACS action checks.
  - The HACS default catalog requires all validation workflows to run fully unsuppressed.

---

## 6. Pre-Commit Static Analysis Routine
- Before finalizing any release or submitting PRs, run automated syntax and undefined name checks across the entire codebase to catch `F821 undefined name` or broken imports across every branch.
