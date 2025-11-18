"""Sarvam service wrapper.

Provides a stable service-layer API by delegating to existing online cloud connector.
"""

from typing import Optional, Tuple

from online.cloud_connector import (
    get_cloud_response as _get_cloud_response,
    transcribe_audio as _transcribe_audio,
    synthesize_speech as _synthesize_speech,
)


def get_cloud_response(prompt: str, system_prompt: Optional[str] = None) -> str:
    return _get_cloud_response(prompt, system_prompt)


def transcribe_audio(audio_bytes: bytes, language_code: Optional[str] = None, model: str = "saarika:v2.5") -> Tuple[str, Optional[str]]:
    return _transcribe_audio(audio_bytes, language_code, model)


def synthesize_speech(text: str, language_code: str = "en-IN", speaker: str = "Anushka", model: str = "bulbul:v2", speed: float = 1.0, audio_format: str = "wav") -> bytes:
    return _synthesize_speech(text, language_code, speaker, model, speed, audio_format)