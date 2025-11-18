import requests
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import load_config


config = {}
try:
    config = load_config()
except Exception as e:
    print(f"Warning: Could not load config: {e}")
    config = {}


def has_internet(timeout=3):
    """Check if internet connection is available."""
    try:
        r = requests.get("https://www.google.com/generate_204", timeout=timeout)
        return r.status_code == 204
    except requests.exceptions.Timeout:
        print("⚠ Internet check timed out")
        return False
    except requests.exceptions.ConnectionError:
        print("⚠ No internet connection")
        return False
    except Exception as e:
        print(f"⚠ Internet check failed: {e}")
        return False


def is_cloud_available(timeout=3):
    """Check if Sarvam cloud API is available."""
    sarvam_key = os.environ.get("SARVAM_API_KEY") or (config.get("keys") or {}).get("sarvam_api_key")
    model = (config.get("online") or {}).get("sarvam_model", "sarvam-m")

    if not sarvam_key:
        print("⚠ Sarvam API key not configured")
        return False
    
    if isinstance(sarvam_key, str) and sarvam_key.startswith("${"):
        print("⚠ Sarvam API key is a placeholder")
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
        else:
            print(f"⚠ Sarvam API returned status {r.status_code}")
        return False
    except requests.exceptions.Timeout:
        print("⚠ Sarvam API timeout")
        return False
    except requests.exceptions.ConnectionError:
        print("⚠ Cannot connect to Sarvam API")
        return False
    except Exception as e:
        print(f"⚠ Sarvam API check failed: {e}")
        return False


if __name__ == "__main__":
    print("Internet:", has_internet())
    print("Sarvam cloud availability:", is_cloud_available())