#!/usr/bin/env python3
"""Verify kartograph stage extraction-runtime secret in Vault (hp-fleet KV v2).

Uses the same path ESO reads via SecretStore mount ``hcm-ai`` (app-interface
``resources/hcm-ai/kartograph/secretstore.yml``), NOT the ``hp-fleet`` engine
shown in some Vault UI navigation:
  remoteRef.key: kartograph/stage/extraction-runtime
  API path:      /v1/hcm-ai/data/kartograph/stage/extraction-runtime

Requires a Vault token with read access (create in Vault UI → Copy token).

Usage:
  export VAULT_ADDR=https://vault.devshift.net
  export VAULT_TOKEN=<token-from-vault-ui>
  uv run python scripts/verify-vault-extraction-runtime.py

Exit 0 when reachable and structurally valid; non-zero otherwise.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

VAULT_ADDR = os.environ.get("VAULT_ADDR", "https://vault.devshift.net").rstrip("/")
VAULT_TOKEN = os.environ.get("VAULT_TOKEN", "").strip()
# SecretStore vault-backend (app-interface resources/hcm-ai/kartograph/secretstore.yml)
# uses provider.path "hcm-ai", NOT hp-fleet. ESO reads this mount only.
ESO_VAULT_MOUNT = os.environ.get("KARTOGRAPH_ESO_VAULT_MOUNT", "hcm-ai")
ESO_RELATIVE_KEY = "kartograph/stage/extraction-runtime"
CONTROL_RELATIVE_KEY = "kartograph/stage/postgres"
# Optional: also check hp-fleet (common in Vault UI navigation; may differ from ESO mount)
CHECK_HP_FLEET_MOUNT = os.environ.get("KARTOGRAPH_CHECK_HP_FLEET_MOUNT", "1") != "0"
HP_FLEET_MOUNT = "hp-fleet"
SIGNING_KEY = "KARTOGRAPH_EXTRACTION_RUNTIME_WORKLOAD_TOKEN_SIGNING_KEY"
ADC_KEY = "application_default_credentials.json"
MIN_SIGNING_KEY_BYTES = 32
EXPECTED_VERTEX_PROJECT = os.environ.get(
    "KARTOGRAPH_EXPECTED_VERTEX_PROJECT", "itpc-gcp-hcm-pe-eng-claude"
)
VALID_ADC_TYPES = frozenset({"service_account", "authorized_user", "external_account"})


def _kv_v2_url(mount: str, relative_key: str) -> str:
    return f"{VAULT_ADDR}/v1/{mount}/data/{relative_key}"


def _read_kv_v2(mount: str, relative_key: str) -> tuple[int, dict | None, str]:
    request = urllib.request.Request(
        _kv_v2_url(mount, relative_key),
        headers={"X-Vault-Token": VAULT_TOKEN},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
            return response.status, body, ""
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        return exc.code, payload, raw[:500]
    except urllib.error.URLError as exc:
        return -1, None, str(exc.reason)


def _secret_data(payload: dict | None) -> dict[str, str]:
    if not payload:
        return {}
    inner = payload.get("data", {}).get("data")
    if not isinstance(inner, dict):
        return {}
    return {str(k): "" if v is None else str(v) for k, v in inner.items()}


def _validate_signing_key(value: str) -> list[str]:
    errors: list[str] = []
    normalized = value.strip()
    if not normalized:
        errors.append(f"{SIGNING_KEY}: missing or empty")
        return errors
    byte_len = len(normalized.encode("utf-8"))
    if byte_len < MIN_SIGNING_KEY_BYTES:
        errors.append(
            f"{SIGNING_KEY}: must be at least {MIN_SIGNING_KEY_BYTES} bytes "
            f"(got {byte_len})"
        )
    return errors


def _validate_adc(value: str) -> list[str]:
    errors: list[str] = []
    if not value.strip():
        errors.append(f"{ADC_KEY}: missing or empty")
        return errors
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        errors.append(f"{ADC_KEY}: invalid JSON ({exc})")
        return errors
    if not isinstance(data, dict):
        errors.append(f"{ADC_KEY}: JSON root must be an object")
        return errors
    cred_type = str(data.get("type", ""))
    if cred_type not in VALID_ADC_TYPES:
        errors.append(
            f"{ADC_KEY}: unexpected type {cred_type!r} "
            f"(expected one of {sorted(VALID_ADC_TYPES)})"
        )
    project_id = str(data.get("project_id", "")).strip()
    if cred_type == "service_account":
        for field in ("client_email", "private_key", "project_id"):
            if not str(data.get(field, "")).strip():
                errors.append(f"{ADC_KEY}: service_account missing {field}")
    if project_id and project_id != EXPECTED_VERTEX_PROJECT:
        errors.append(
            f"{ADC_KEY}: project_id is {project_id!r}, "
            f"expected {EXPECTED_VERTEX_PROJECT!r} for stage"
        )
    return errors


def _report_read(label: str, mount: str, relative_key: str, status: int, payload: dict | None, err: str) -> dict[str, str] | None:
    api_path = f"{mount}/data/{relative_key}"
    print(f"\n==> {label}")
    print(f"    API: GET /v1/{api_path}")
    if status == 200:
        data = _secret_data(payload)
        print(f"    HTTP 200 — {len(data)} key(s): {', '.join(sorted(data)) or '(empty)'}")
        return data
    if status == 404:
        print("    HTTP 404 — secret not found OR token lacks read policy (KV hides denial as 404)")
    elif status == 403:
        print("    HTTP 403 — permission denied (token cannot read this path)")
    else:
        print(f"    HTTP {status} — {err or payload}")
    return None


def main() -> int:
    print("Kartograph Vault check — extraction-runtime (stage)")
    print(f"VAULT_ADDR={VAULT_ADDR}")
    print(f"ESO SecretStore mount (app-interface): {ESO_VAULT_MOUNT}")
    print(f"ESO remoteRef.key={ESO_RELATIVE_KEY}")

    if not VAULT_TOKEN:
        print(
            "\nERROR: VAULT_TOKEN is unset.\n"
            "  Vault UI → profile → Copy token (or create token with read on hp-fleet).\n"
            "  export VAULT_TOKEN='...'\n"
            "  uv run python scripts/verify-vault-extraction-runtime.py",
            file=sys.stderr,
        )
        return 2

    control_status, control_payload, control_err = _read_kv_v2(ESO_VAULT_MOUNT, CONTROL_RELATIVE_KEY)
    control_data = _report_read(
        f"Control on ESO mount ({ESO_VAULT_MOUNT}): postgres",
        ESO_VAULT_MOUNT,
        CONTROL_RELATIVE_KEY,
        control_status,
        control_payload,
        control_err,
    )

    ext_status, ext_payload, ext_err = _read_kv_v2(ESO_VAULT_MOUNT, ESO_RELATIVE_KEY)
    ext_data = _report_read(
        f"Target on ESO mount ({ESO_VAULT_MOUNT}): extraction-runtime",
        ESO_VAULT_MOUNT,
        ESO_RELATIVE_KEY,
        ext_status,
        ext_payload,
        ext_err,
    )

    hp_fleet_ext_status: int | None = None
    if CHECK_HP_FLEET_MOUNT:
        hp_fleet_ext_status, hp_fleet_payload, hp_fleet_err = _read_kv_v2(
            HP_FLEET_MOUNT, ESO_RELATIVE_KEY
        )
        _report_read(
            f"Same key on hp-fleet mount (Vault UI path; not used by ESO today)",
            HP_FLEET_MOUNT,
            ESO_RELATIVE_KEY,
            hp_fleet_ext_status,
            hp_fleet_payload,
            hp_fleet_err,
        )

    print("\n==> Diagnosis")
    if control_status != 200 and ext_status != 200:
        print(f"FAIL: Cannot read {ESO_VAULT_MOUNT} mount with this token.")
        return 1
    if control_status == 200 and ext_status == 404:
        if CHECK_HP_FLEET_MOUNT and hp_fleet_ext_status == 200:
            print(
                f"FAIL: Secret exists on {HP_FLEET_MOUNT} but NOT on ESO mount {ESO_VAULT_MOUNT}.\n"
                f"      Copy keys to {ESO_VAULT_MOUNT}/kartograph/stage/extraction-runtime in Vault UI,\n"
                f"      or open an app-interface PR to change SecretStore path to {HP_FLEET_MOUNT}."
            )
        else:
            print(
                f"FAIL: extraction-runtime missing on ESO mount {ESO_VAULT_MOUNT}.\n"
                f"      Create {ESO_VAULT_MOUNT}/kartograph/stage/extraction-runtime in Vault."
            )
        return 1
    if ext_status == 403:
        print("FAIL: Permission denied on extraction-runtime path.")
        return 1
    if ext_status != 200 or ext_data is None:
        print("FAIL: extraction-runtime secret not reachable.")
        return 1

    errors: list[str] = []
    errors.extend(_validate_signing_key(ext_data.get(SIGNING_KEY, "")))
    errors.extend(_validate_adc(ext_data.get(ADC_KEY, "")))
    extra_keys = set(ext_data) - {SIGNING_KEY, ADC_KEY}
    if extra_keys:
        print(f"    Note: extra keys present (ignored): {', '.join(sorted(extra_keys))}")

    print("\n==> Field validation")
    if errors:
        for msg in errors:
            print(f"    FAIL  {msg}")
        print("\nRESULT: Secret exists but values are invalid for kartograph-stage.")
        return 1

    signing_len = len(ext_data[SIGNING_KEY].strip().encode("utf-8"))
    adc = json.loads(ext_data[ADC_KEY])
    print(f"    OK  {SIGNING_KEY} ({signing_len} bytes, redacted)")
    print(
        f"    OK  {ADC_KEY} (type={adc.get('type')}, "
        f"project_id={adc.get('project_id', '(none)')})"
    )
    print("\nRESULT: Secret is reachable on the ESO mount and structurally valid.")
    if CHECK_HP_FLEET_MOUNT and hp_fleet_ext_status == 200 and ext_status == 200:
        print(
            f"Note: Secret also exists on {HP_FLEET_MOUNT}; ESO only reads {ESO_VAULT_MOUNT}."
        )
    print(
        "If ESO still Degraded, re-check SecretStore vault-backend path/role in cluster."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
