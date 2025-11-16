import requests
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config_loader import load_config


config = {}
try:
    config = load_config()
except Exception:
    config = {}


def is_cloud_available(timeout=3):
    """Generic cloud LLM availability check.

    Prefer OpenAI (if `OPENAI_API_KEY` env or `keys.openai_api_key` present).
    Returns True if the selected cloud service responds.
    """
    openai_key = os.environ.get("OPENAI_API_KEY") or (config.get("keys") or {}).get("openai_api_key")
    if openai_key:
        try:
            r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {openai_key}"}, timeout=timeout)
            return r.status_code == 200
        except Exception:
            return False

    # No cloud configured
    return False


if __name__ == "__main__":
    print("Cloud availability:", is_cloud_available())