"""online/cloud_connector.py
Sarvam-only cloud LLM connector for voice assistant.

API key is read from env `SARVAM_API_KEY` or from config `keys.sarvam_api_key`.
"""

import os
import sys
import requests
from typing import Optional, Tuple
import base64

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config_loader import load_config

config = None
try:
    config = load_config()
except Exception:
    config = {}

ONLINE_CONF = (config.get("online") or {})
PROVIDER = "sarvam"

# Sarvam configuration
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY") or (config.get("keys") or {}).get("sarvam_api_key")
SARVAM_MODEL = ONLINE_CONF.get("sarvam_model", "sarvam-m")

TIMEOUT = ONLINE_CONF.get("timeout", 30)


def _ensure_api_key():
    """Check if selected provider's API key is configured."""
    
    if PROVIDER == "sarvam":
        if not SARVAM_API_KEY or (isinstance(SARVAM_API_KEY, str) and SARVAM_API_KEY.startswith("${")):
            raise Exception("Sarvam API key not configured. Set SARVAM_API_KEY or keys.sarvam_api_key in config.")
    else:
        raise Exception(f"Unknown provider: {PROVIDER}")


def _is_sarvam_available() -> bool:
    try:
        _ensure_api_key()
    except Exception:
        return False
    try:
        url = "https://api.sarvam.ai/v1/chat/completions"
        headers = {
            "api-subscription-key": f"{SARVAM_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": SARVAM_MODEL,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 5,
            "temperature": 0.5
        }
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        if response.status_code == 200 and (response.json().get("choices") or []):
            return True
        return False
    except requests.exceptions.Timeout:
        print("⚠ Sarvam API timeout")
        return False
    except requests.exceptions.ConnectionError:
        print("⚠ Cannot connect to Sarvam API")
        return False
    except Exception as e:
        print(f"⚠ Sarvam availability check failed: {e}")
        return False


def get_cloud_response(prompt: str, system_prompt: Optional[str] = None) -> str:
    """Send prompt to selected provider and return reply text."""
    _ensure_api_key()

    # Build messages array
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    url = "https://api.sarvam.ai/v1/chat/completions"
    headers = {
        "api-subscription-key": f"{SARVAM_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": SARVAM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        code = getattr(e.response, "status_code", None)
        if code == 401:
            raise Exception("Invalid Sarvam API key. Get a key at https://dashboard.sarvam.ai/")
        elif code == 429:
            raise Exception("Sarvam rate limit exceeded. Wait and try again.")
        else:
            raise Exception(f"Sarvam HTTP error: {e}")
    except requests.exceptions.Timeout:
        raise Exception("Sarvam API request timed out. Check your internet connection.")
    except requests.exceptions.ConnectionError:
        raise Exception("Cannot connect to Sarvam API. Check your internet connection.")
    except Exception as e:
        raise Exception(f"Sarvam API request failed: {e}")

    try:
        choices = data.get("choices", [])
        if not choices:
            raise Exception("No choices in response")
        message = choices[0].get("message", {})
        content = message.get("content", "")
        return content.strip() if isinstance(content, str) else ""
    except Exception as e:
        raise Exception(f"Unexpected response format: {e}")


def transcribe_audio(audio_bytes: bytes, language_code: Optional[str] = None, model: str = "saarika:v2.5") -> Tuple[str, Optional[str]]:
    """
    Transcribe audio using Sarvam API.
    
    Returns:
        Tuple of (transcript_text, detected_language_code)
    """
    _ensure_api_key()
    url = "https://api.sarvam.ai/v1/speech-to-text"
    headers = {"api-subscription-key": f"{SARVAM_API_KEY}"}
    files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
    data = {"model": model}
    if language_code:
        data["language_code"] = language_code
    try:
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=TIMEOUT)
        resp.raise_for_status()
        j = resp.json()
        text = j.get("transcript") or j.get("text") or ""
        detected_lang = j.get("language_code") or language_code
        return text.strip(), detected_lang
    except Exception as e:
        raise Exception(f"Sarvam STT failed: {e}")


def synthesize_speech(text: str, language_code: str = "en-IN", speaker: str = "Anushka", model: str = "bulbul:v2", speed: float = 1.0, audio_format: str = "wav") -> bytes:
    """
    Synthesize speech using Sarvam API.
    
    Returns:
        Audio bytes in the specified format
    """
    _ensure_api_key()
    url = "https://api.sarvam.ai/v1/text-to-speech/convert"
    headers = {
        "api-subscription-key": f"{SARVAM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "language_code": language_code,
        "speaker": speaker,
        "speed": speed,
        "format": audio_format,
        "input": [text],
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        audios = data.get("audio") or data.get("audios") or []
        if isinstance(audios, list) and audios:
            b = base64.b64decode(audios[0])
            return b
        elif isinstance(audios, str):
            return base64.b64decode(audios)
        raise Exception("No audio returned")
    except Exception as e:
        raise Exception(f"Sarvam TTS failed: {e}")