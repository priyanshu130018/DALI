"""Configuration loader and environment validator.

- Loads `config.json`
- Substitutes `${VAR}` from `.env`
- Validates environment variables for optional features
"""

import os
import json
import re
from typing import Any, Dict

from dotenv import load_dotenv


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")


def _substitute_env_variables(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    def repl(match):
        var = match.group(1)
        env_value = os.getenv(var)
        return env_value if env_value is not None else match.group(0)
    return re.sub(r"\$\{([^}]+)\}", repl, value)


def _process_config(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _process_config(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_process_config(x) for x in obj]
    return _substitute_env_variables(obj)


def load_config() -> Dict[str, Any]:
    load_dotenv(os.path.join(ROOT_DIR, ".env"))
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return _process_config(cfg)


def validate_env(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Validate environment variables relevant to optional features.

    Returns a dict of validation flags.
    """
    keys = cfg.get("keys") or {}
    sarvam = os.getenv("SARVAM_API_KEY") or keys.get("sarvam_api_key")
    picovoice = os.getenv("PICOVOICE_ACCESS_KEY") or keys.get("picovoice")
    mysql_host = os.getenv("MYSQL_HOST")
    mysql_user = os.getenv("MYSQL_USER")
    mysql_password = os.getenv("MYSQL_PASSWORD")
    mysql_db = os.getenv("MYSQL_DB")
    openweather = os.getenv("OPENWEATHER_API_KEY") or os.getenv("WEATHER_API_KEY")

    return {

        "sarvam_configured": bool(sarvam and not str(sarvam).startswith("${")),
        "picovoice_configured": bool(picovoice and not str(picovoice).startswith("${")),
        "mysql_configured": all([mysql_host, mysql_user, mysql_password, mysql_db]),
        "weather_api_configured": bool(openweather),
    }