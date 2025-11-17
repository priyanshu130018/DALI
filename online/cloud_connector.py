"""online/cloud_connector.py
Use Groq (FREE) as the cloud LLM backend for voice assistant.
Fast, free, and powerful - perfect for voice applications.

This module reads the API key from environment variable `GROQ_API_KEY`
or from `config` if present under `keys.groq_api_key`.
"""

import os
import sys
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config_loader import load_config

config = None
try:
    config = load_config()
except Exception:
    config = {}

GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or (config.get("keys") or {}).get("groq_api_key")
# Use Llama 3.3 70B - Fast and powerful, completely FREE
GROQ_MODEL = (config.get("online") or {}).get("groq_model", "llama-3.3-70b-versatile")
TIMEOUT = (config.get("online") or {}).get("timeout", 30)


def _ensure_api_key():
    """Check if Groq API key is configured."""
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("${"):
        raise Exception("Groq API key not configured. Set GROQ_API_KEY env var or config['keys']['groq_api_key'].")


def is_groq_available():
    """Quick check if Groq API is available and working.
    
    Returns:
        bool: True if Groq API is accessible, False otherwise
    """
    try:
        _ensure_api_key()
    except Exception:
        return False
    
    try:
        # Quick test with minimal token usage (5 tokens)
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 5,
            "temperature": 0.5
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        
        # Check if request was successful
        if response.status_code == 200:
            data = response.json()
            # Verify response has expected structure
            if data.get("choices") and len(data["choices"]) > 0:
                return True
        
        return False
        
    except requests.exceptions.Timeout:
        print("⚠ Groq API timeout")
        return False
    except requests.exceptions.ConnectionError:
        print("⚠ Cannot connect to Groq API")
        return False
    except Exception as e:
        print(f"⚠ Groq availability check failed: {e}")
        return False


def get_cloud_response(prompt: str, system_prompt: str = None) -> str:
    """Send prompt to Groq API and return the assistant reply.

    Uses Llama 3.3 70B via Groq - FREE with generous rate limits.
    Perfect for voice assistant applications.
    
    Args:
        prompt: User's message/query
        system_prompt: Optional system instruction to guide the AI's behavior
    
    Returns:
        str: The AI's response text
        
    Raises:
        Exception: On network/auth errors so callers can fallback to offline models.
    """
    _ensure_api_key()

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Build messages array
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512,
        "stream": False
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise Exception("Invalid Groq API key. Get a free key at https://console.groq.com/")
        elif e.response.status_code == 429:
            raise Exception("Rate limit exceeded. Wait a moment and try again.")
        else:
            raise Exception(f"Groq API HTTP error: {e}")
    except requests.exceptions.Timeout:
        raise Exception("Groq API request timed out. Check your internet connection.")
    except requests.exceptions.ConnectionError:
        raise Exception("Cannot connect to Groq API. Check your internet connection.")
    except Exception as e:
        raise Exception(f"Groq API request failed: {e}")

    try:
        choices = data.get("choices", [])
        if not choices:
            raise Exception("No choices in Groq response")
        
        message = choices[0].get("message", {})
        content = message.get("content", "")
        
        return content.strip() if content else ""
        
    except Exception as e:
        raise Exception(f"Unexpected Groq response format: {e}")


def test_groq_api():
    """Test the Groq API connection and configuration.
    
    Returns:
        bool: True if test successful, False otherwise
    """
    try:
        print("Testing Groq API (FREE)...")
        print(f"Model: {GROQ_MODEL}")
        
        # Test availability first
        print("Checking availability...", end=" ")
        if not is_groq_available():
            print("✗ Failed")
            return False
        print("✓ Available")
        
        # Test actual response
        print("Testing response...", end=" ")
        response = get_cloud_response("Say hello in 5 words")
        print("✓ Success")
        print(f"Response: {response}")
        
        print("\n✅ Groq API is working perfectly!")
        return True
        
    except Exception as e:
        print(f"\n❌ Cloud test failed: {e}")
        print("\nTo fix:")
        print("1. Go to https://console.groq.com/")
        print("2. Sign up (FREE, no credit card)")
        print("3. Create API key")
        print("4. Set: export GROQ_API_KEY='gsk_your_key_here'")
        print("5. Restart your terminal and try again")
        return False


if __name__ == "__main__":
    # Run test when executed directly
    test_groq_api()
