"""online/cloud_connector.py
Use OpenAI (Chat Completions) as the cloud LLM backend. Falls back to
raising exceptions so callers can fallback to Rasa.

This module reads the API key from environment variable `OPENAI_API_KEY`
or from `config` if present under `keys.openai_api_key`.
"""

import os
import sys
from openai import OpenAI

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config_loader import load_config

config = None
try:
    config = load_config()
except Exception:
    config = {}

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or (config.get("keys") or {}).get("openai_api_key")
OPENAI_MODEL = (config.get("online") or {}).get("openai_model", "gpt-3.5-turbo")
TIMEOUT = (config.get("online") or {}).get("timeout", 30)


def _ensure_api_key():
    if not OPENAI_API_KEY:
        raise Exception("OpenAI API key not configured. Set OPENAI_API_KEY env var or config['keys']['openai_api_key'].")


def get_cloud_response(prompt: str) -> str:
    """Send prompt to OpenAI via the official SDK and return the assistant reply.

    Raises Exception on network/auth errors so callers can fallback to offline models.
    """
    _ensure_api_key()

    client = OpenAI(api_key=OPENAI_API_KEY)

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=512,
            timeout=TIMEOUT,
        )
    except Exception as e:
        raise Exception(f"OpenAI SDK request failed: {e}")

    try:
        # SDK returns a dict-like object
        choices = resp.get("choices") or []
        if not choices:
            raise Exception("No choices in OpenAI response")
        message = choices[0].get("message") or {}
        content = message.get("content") or choices[0].get("text")
        return content.strip() if content else ""
    except Exception as e:
        raise Exception(f"Unexpected OpenAI response format: {e}")


if __name__ == "__main__":
    try:
        print(get_cloud_response("Say hi"))
    except Exception as e:
        print("Cloud test failed:", e)