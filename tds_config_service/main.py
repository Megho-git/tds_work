from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent

DEFAULTS: dict[str, Any] = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

app = FastAPI(title="TDS Config Precedence API")

# The grader calls this API from the course page's browser context.
# No credentials are used, so wildcard origins are appropriate here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _normalise_key(key: str) -> str:
    return key.strip().lower()


def _apply_env_mapping(target: dict[str, Any], key: str, value: Any) -> None:
    """Map .env / OS environment names into canonical config keys."""
    if value is None:
        return

    env_key = key.strip().upper()
    if env_key == "APP_ENV":
        # Selects the YAML file; it is not itself an application setting.
        return
    if env_key == "NUM_WORKERS":
        target["workers"] = value
        return
    if env_key.startswith("APP_"):
        target[_normalise_key(env_key[4:])] = value


def _as_bool(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value for {key}: {value!r}")


def _coerce(key: str, value: Any) -> Any:
    key = _normalise_key(key)
    if key in {"port", "workers"}:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid integer value for {key}: {value!r}") from exc
    if key == "debug":
        return _as_bool(value, key)
    return "" if value is None else str(value)


def _effective_config(overrides: list[str] | None = None) -> dict[str, Any]:
    """Merge config from lowest to highest precedence."""
    merged: dict[str, Any] = dict(DEFAULTS)

    # Layer 2: environment-specific YAML. APP_ENV defaults to development.
    environment = os.environ.get("APP_ENV", "development").strip() or "development"
    yaml_path = BASE_DIR / f"config.{environment}.yaml"
    if yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as handle:
            yaml_config = yaml.safe_load(handle) or {}
        if not isinstance(yaml_config, dict):
            raise RuntimeError(f"{yaml_path.name} must contain a YAML object")
        merged.update({_normalise_key(str(k)): v for k, v in yaml_config.items()})

    # Layer 3: .env file. Read it as a layer without mutating process env.
    env_file_path = BASE_DIR / ".env"
    if env_file_path.exists():
        for key, value in dotenv_values(env_file_path).items():
            _apply_env_mapping(merged, key, value)

    # Layer 4: process / OS environment variables using APP_* names.
    for key, value in os.environ.items():
        _apply_env_mapping(merged, key, value)

    # Layer 5: CLI overrides represented by repeated ?set=key=value params.
    for item in overrides or []:
        key, separator, value = item.partition("=")
        key = _normalise_key(key)
        if not separator or not key:
            raise HTTPException(
                status_code=400,
                detail="Each 'set' parameter must have the form key=value",
            )
        try:
            merged[key] = _coerce(key, value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Enforce expected types regardless of which layer supplied the value.
    result: dict[str, Any] = {}
    for key, value in merged.items():
        try:
            result[key] = _coerce(key, value)
        except ValueError as exc:
            # Invalid CLI values are already handled above; this indicates a
            # malformed deployment configuration rather than a bad request.
            raise HTTPException(status_code=500, detail=f"Invalid configuration: {exc}") from exc

    # Never reveal the actual secret, even if it came from a CLI override.
    result["api_key"] = "****"
    return result


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "TDS Config Precedence API", "endpoint": "/effective-config"}


@app.get("/effective-config")
def effective_config(set_overrides: list[str] | None = Query(default=None, alias="set")) -> dict[str, Any]:
    return _effective_config(set_overrides)
