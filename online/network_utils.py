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


def has_internet(timeout=3):
    try:
        r = requests.get("https://www.google.com/generate_204", timeout=timeout)
        return r.status_code == 204
    except Exception:
        return False


def is_cloud_available(timeout=3):
    sarvam_key = os.environ.get("SARVAM_API_KEY") or (config.get("keys") or {}).get("sarvam_api_key")
    model = (config.get("online") or {}).get("sarvam_model", "sarvam-m")

    if not sarvam_key:
        return False

    url = "https://api.sarvam.ai/v1/chat/completions"
    headers = {
        "api-subscription-key": f"{sarvam_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1,
        "temperature": 0.2,
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            return bool(data.get("choices"))
        return False
    except Exception:
        return False


if __name__ == "__main__":
    print("Internet:", has_internet())
    print("Sarvam cloud availability:", is_cloud_available())