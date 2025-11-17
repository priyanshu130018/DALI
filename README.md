# Download Vosk models

https://alphacephei.com/vosk/models/

English - vosk-model-en-in-0.5
Hindi - vosk-model-hi-0.22



Online

- STT: Sarvam online recognition (records audio and posts to Sarvam)
- LLM: Sarvam chat completions
- TTS: Sarvam bulbul:v2 with speaker “Anushka” in the detected STT language
- Fallback: If any cloud call fails, it switches to offline for the rest of the awake window
- Where in code:
  - Online STT capture/send: main.py:398-459
  - Online TTS playback: main.py:237-271
  - STT selector in awake loop: main.py:576-581
  - Cloud failure → lock offline: main.py:491-495
  - Cloud check on startup: main.py:221-235
Offline

- STT: Vosk
- NLU/Replies: Rasa if available; otherwise simple rule-based responses
- TTS: pyttsx3
- Never calls Sarvam
- Where in code:
  - Vosk listen: main.py:315-396
  - Offline processing flow: main.py:496-507
  - Rule-based fallback: main.py:509-536
Auto

- STT: Vosk
- LLM: Uses Sarvam when available; falls back to Rasa/rules on failure
- TTS: pyttsx3
- Fallback: If a cloud call fails during the awake window, it locks into offline until the next wake word
- Where in code:
  - Mode read: main.py:124-129
  - Cloud-first reply: main.py:474-490
  - Cloud failure and offline switch: main.py:491-507
  - Offline lock flag checked in STT/TTS selection: main.py:244-266, 576-581