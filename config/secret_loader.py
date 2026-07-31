import json
import os
from typing import Any


def _get_streamlit_secrets() -> dict[str, Any]:
    try:
        import streamlit as st
    except Exception:
        return {}

    try:
        return dict(st.secrets)
    except Exception:
        return {}


def get_secret(name: str, default: Any = None) -> Any:
    value = os.getenv(name)
    if value not in (None, ""):
        return value

    secrets = _get_streamlit_secrets()
    if name in secrets:
        return secrets[name]

    return default


def get_secret_with_aliases(*names: str, default: Any = None) -> Any:
    for name in names:
        value = get_secret(name)
        if value not in (None, ""):
            return value
    return default


def get_service_account_info() -> dict[str, Any] | None:
    raw_json = get_secret_with_aliases(
        "GOOGLE_SERVICE_ACCOUNT_JSON",
        "SERVICE_ACCOUNT_JSON",
    )
    if raw_json:
        if isinstance(raw_json, dict):
            return raw_json
        return json.loads(raw_json)

    secrets = _get_streamlit_secrets()
    nested = secrets.get("google_service_account")
    if nested:
        return dict(nested)

    return None


def get_service_account_source() -> str | dict[str, Any] | None:
    info = get_service_account_info()
    if info:
        return info

    service_account_file = get_secret("SERVICE_ACCOUNT_FILE", "credentials/service_account.json")
    if service_account_file and os.path.exists(service_account_file):
        return service_account_file

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cred_dir = os.path.join(base_dir, "credentials")
    if os.path.exists(cred_dir):
        jsons = [f for f in os.listdir(cred_dir) if f.endswith(".json")]
        if jsons:
            return os.path.join(cred_dir, jsons[0])

    return None
