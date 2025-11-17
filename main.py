"""main.py
DALI Voice Assistant - Voice-Only Mode
Uses Sarvam API for cloud processing when available.
Listens via microphone, responds with voice.
"""

import os
import sys
import json
import struct
import time
import io
import wave
import audioop
import platform
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from config_loader import load_config
    from online.cloud_connector import get_cloud_response, transcribe_audio, synthesize_speech
    try:
        from offline.rasa_handler import RasaHandler
        RASA_AVAILABLE = True
    except Exception:
        RASA_AVAILABLE = False
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

# Required imports for voice mode
try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False
    print("WARNING: pvporcupine not installed. Wake word detection disabled.")

try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("ERROR: pyaudio not installed!")
    print("Install with: pip install pyaudio")

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    print("ERROR: pyttsx3 not installed!")
    print("Install with: pip install pyttsx3==2.91")

try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    print("ERROR: vosk not installed!")
    print("Install with: pip install vosk")


class TTSHandler:
    """Wrapper for pyttsx3 to handle speaking issues."""
    
    def __init__(self, config):
        self.config = config
        self.assistant_config = config.get("assistant", {})
        self.language = self.assistant_config.get("language", "en-in")
        print("✓ Text-to-speech handler initialized")
    
    def speak(self, text):
        """Speak text using fresh engine instance each time."""
        if not text:
            return
        
        try:
            # Create new engine for each speech to avoid hanging
            if os.name == 'nt':
                engine = pyttsx3.init(driverName='sapi5')
            else:
                engine = pyttsx3.init()
            
            # Configure engine
            rate = self.assistant_config.get("voice_rate", 160)
            engine.setProperty('rate', rate)
            engine.setProperty('volume', 1.0)
            
            # Set voice if specified in config
            voices_config = self.config.get("voices", {})
            voice_name = voices_config.get(self.language)
            if voice_name:
                voices = engine.getProperty('voices')
                for voice in voices:
                    if voice_name.lower() in voice.name.lower():
                        engine.setProperty('voice', voice.id)
                        break
            
            # Speak the text
            engine.say(text)
            engine.runAndWait()
            
            # Cleanup
            engine.stop()
            del engine
            
            # Small delay after speaking
            time.sleep(0.2)
            
        except Exception as e:
            print(f"⚠ TTS error: {e}")
            import traceback
            traceback.print_exc()


class VoiceAssistant:
    """Voice-only DALI assistant with optional Sarvam cloud."""
    
    def __init__(self):
        """Initialize the voice assistant."""
        self.config = load_config()
        self.assistant_config = self.config.get("assistant", {})
        self.name = self.assistant_config.get("name", "DALI")
        self.language = self.assistant_config.get("language", "en-in")
        self.mode = self.assistant_config.get("mode", "auto").lower()
        
        self.running = False
        self.cloud_available = False
        self.tts_handler = None
        self.audio = None
        self.porcupine = None
        self.vosk_model = None
        self.recognizer = None
        self.rasa_handler = None
        self.offline_fallback_active = False
        
        # Check requirements
        if not all([AUDIO_AVAILABLE, TTS_AVAILABLE, VOSK_AVAILABLE]):
            sys.exit(1)
        
        self._init_tts()
        self._init_audio()
        self._init_speech_recognition()
        self._init_wake_word()
        self._check_cloud_availability()
        
    def _init_tts(self):
        """Initialize text-to-speech handler."""
        try:
            self.tts_handler = TTSHandler(self.config)
            
            # Test the TTS
            print("🔊 Testing TTS...")
            self.tts_handler.speak("System ready")
            
        except Exception as e:
            print(f"❌ TTS initialization failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    def _init_audio(self):
        """Initialize PyAudio."""
        try:
            self.audio = pyaudio.PyAudio()
            print("✓ Audio system initialized")
        except Exception as e:
            print(f"❌ Audio initialization failed: {e}")
            sys.exit(1)
    
    def _init_speech_recognition(self):
        """Initialize Vosk speech recognition."""
        try:
            offline_config = self.config.get("offline", {})
            vosk_models = offline_config.get("vosk_models", {})
            model_path = vosk_models.get(self.language, "models/vosk-model-en-in-0.5")
            
            if not os.path.exists(model_path):
                print(f"❌ Vosk model not found at: {model_path}")
                print(f"Download from: https://alphacephei.com/vosk/models")
                print(f"Extract to: {model_path}")
                sys.exit(1)
            
            self.vosk_model = Model(model_path)
            self.recognizer = KaldiRecognizer(self.vosk_model, 16000)
            print(f"✓ Speech recognition initialized ({self.language})")
        except Exception as e:
            print(f"❌ Speech recognition initialization failed: {e}")
            sys.exit(1)
    
    def _init_wake_word(self):
        """Initialize Porcupine wake word detection."""
        if not PORCUPINE_AVAILABLE:
            print("⚠ Wake word detection not available (will use manual activation)")
            return
        
        try:
            picovoice_key = os.environ.get("PICOVOICE_ACCESS_KEY") or \
                           (self.config.get("keys") or {}).get("picovoice", "").replace("${PICOVOICE_ACCESS_KEY}", "")
            
            if not picovoice_key or picovoice_key.startswith("${"):
                print("⚠ Picovoice key not set - using manual activation")
                print("  Set PICOVOICE_ACCESS_KEY for wake word 'Hello DALI'")
                return
            
            wake_word_path = self.assistant_config.get("wake_word_path")
            if wake_word_path and os.path.exists(wake_word_path):
                self.porcupine = pvporcupine.create(
                    access_key=picovoice_key,
                    keyword_paths=[wake_word_path]
                )
                print(f"✓ Wake word initialized: {os.path.basename(wake_word_path)}")
            else:
                print(f"⚠ Wake word file not found: {wake_word_path}")
        except Exception as e:
            print(f"⚠ Wake word initialization failed: {e}")
            self.porcupine = None
    
    def _check_cloud_availability(self):
        """Check if cloud service is available (Sarvam)."""
        print("Checking Cloud API...")
        try:
            test_response = get_cloud_response("Hi")
            if test_response:
                self.cloud_available = True
                print("✓ Cloud API is ready!")
                return
        except Exception as e:
            print(f"⚠ Cloud API test failed: {e}")
        
        self.cloud_available = False
        print("❌ Cloud API not available!")
        print("   Set SARVAM_API_KEY in your environment or .env")
    
    def speak(self, text):
        """Convert text to speech."""
        if not text:
            return
            
        print(f"🔊 {self.name}: {text}")
        
        if self.mode == "online" and self.cloud_available and not self.offline_fallback_active:
            try:
                lang = getattr(self, "last_detected_lang", None) or self.language
                lang = lang.replace("_", "-")
                if len(lang) == 5 and lang[2] == '-':
                    lang = lang[:2] + '-' + lang[3:].upper()
                audio_bytes = synthesize_speech(text, language_code=lang)
                if platform.system().lower().startswith("win"):
                    import winsound
                    winsound.PlaySound(audio_bytes, winsound.SND_MEMORY)
                else:
                    buf = io.BytesIO(audio_bytes)
                    with wave.open(buf, 'rb') as wf:
                        stream = self.audio.open(format=pyaudio.paInt16, channels=wf.getnchannels(), rate=wf.getframerate(), output=True)
                        data = wf.readframes(1024)
                        while data:
                            stream.write(data)
                            data = wf.readframes(1024)
                        stream.stop_stream()
                        stream.close()
                return
            except Exception as e:
                print(f"⚠ Online TTS failed: {e}")
        
        if not self.tts_handler:
            print("⚠ TTS handler not available")
            return
        self.tts_handler.speak(text)
    
    def listen_for_wake_word(self):
        """Listen for wake word using Porcupine."""
        if not self.porcupine:
            # No wake word, use manual activation
            print(f"\n{'='*60}")
            print("🎤 Press ENTER when ready to speak, then say your command...")
            print(f"{'='*60}")
            input()
            return True
        
        try:
            audio_stream = self.audio.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length
            )
            
            print(f"\n{'='*60}")
            display_kw = os.path.basename(self.assistant_config.get("wake_word_path") or "") if self.assistant_config.get("wake_word_path") else f"Hello {self.name}"
            print(f"🎤 Listening for wake word: {display_kw}...")
            print(f"{'='*60}")
            
            while self.running:
                pcm = audio_stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                
                keyword_index = self.porcupine.process(pcm)
                if keyword_index >= 0:
                    print(f"✓ Wake word detected!")
                    # Reset any previous offline fallback for this awake window
                    self.offline_fallback_active = False
                    audio_stream.stop_stream()
                    audio_stream.close()
                    return True
            
            audio_stream.stop_stream()
            audio_stream.close()
            return False
            
        except Exception as e:
            print(f"⚠ Wake word detection error: {e}")
            return True  # Continue anyway
    
    def listen_for_command(self, timeout=15):
        """Listen for voice command using Vosk."""
        audio_stream = None
        try:
            audio_stream = self.audio.open(
                rate=16000,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=4000
            )
            
            print("🎤 Listening... (speak now)")
            self.recognizer.Reset()
            
            start_time = time.time()
            final_text = ""
            has_speech = False
            silence_after_speech = 0
            silence_threshold = 1.5  # seconds of silence AFTER speech before finalizing
            
            while time.time() - start_time < timeout:
                try:
                    data = audio_stream.read(4000, exception_on_overflow=False)
                except Exception:
                    continue
                
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "").strip()
                    
                    if text:
                        has_speech = True
                        final_text = text
                        silence_after_speech = 0
                        print(f"   📝 Captured: {text}")
                
                # Check partial results to detect ongoing speech
                partial = json.loads(self.recognizer.PartialResult())
                partial_text = partial.get("partial", "").strip()
                
                if partial_text:
                    # User is currently speaking
                    has_speech = True
                    silence_after_speech = 0
                    print(f"   🎙️ Speaking: {partial_text}", end='\r')
                elif has_speech:
                    # Count silence after we've detected speech
                    silence_after_speech += 0.25  # approximately 250ms per chunk
                    
                    if silence_after_speech >= silence_threshold:
                        # User stopped speaking for threshold duration
                        print()  # New line after partial text
                        break
            
            print()  # Ensure we're on a new line
            
            # Get any remaining text
            if not final_text:
                result = json.loads(self.recognizer.FinalResult())
                final_text = result.get("text", "").strip()
            
        except Exception as e:
            print(f"⚠ Speech recognition error: {e}")
            final_text = None
        finally:
            # ALWAYS close the audio stream before returning
            if audio_stream:
                try:
                    audio_stream.stop_stream()
                    audio_stream.close()
                    # Give time for audio resources to be released
                    time.sleep(0.2)
                except Exception as e:
                    print(f"⚠ Error closing audio stream: {e}")
        
        if final_text:
            print(f"✓ You said: {final_text}")
            return final_text
        else:
            print("⚠ No speech detected")
            return None

    def listen_for_command_online(self, timeout=15):
        audio_stream = None
        try:
            audio_stream = self.audio.open(
                rate=16000,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=4000
            )
            print("🎤 Listening... (online mode)")
            start_time = time.time()
            frames = []
            started = False
            silence_start = None
            while time.time() - start_time < timeout:
                data = audio_stream.read(4000, exception_on_overflow=False)
                rms = audioop.rms(data, 2)
                if rms > 300:
                    started = True
                    silence_start = None
                    frames.append(data)
                elif started:
                    if silence_start is None:
                        silence_start = time.time()
                    frames.append(data)
                    if time.time() - silence_start > 1.0:
                        break
            if not frames:
                return None
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b''.join(frames))
            audio_bytes = buf.getvalue()
            try:
                text, detected_lang = transcribe_audio(audio_bytes, language_code=None)
                if text:
                    if detected_lang:
                        self.last_detected_lang = detected_lang
                    print(f"✓ You said: {text}")
                else:
                    print("⚠ No speech detected")
                return text or None
            except Exception as e:
                print(f"⚠ Online STT failed: {e}")
                return None
        except Exception as e:
            print(f"⚠ Microphone error: {e}")
            return None
        finally:
            if audio_stream:
                try:
                    audio_stream.stop_stream()
                    audio_stream.close()
                    time.sleep(0.2)
                except Exception:
                    pass
    
    def process_command(self, command):
        """Process voice command using cloud backend if available."""
        if not command:
            self.speak("I didn't catch that. Please try again.")
            return
        
        command_lower = command.lower()
        
        # Check for exit commands
        if any(word in command_lower for word in ["goodbye", "exit", "quit", "stop", "bye"]):
            self.speak("Goodbye! Have a great day!")
            self.running = False
            return
        
        # Try cloud processing with selected provider
        if self.cloud_available and not self.offline_fallback_active:
            try:
                print("☁️ Processing with Cloud API...")
                
                # Create a system prompt to define DALI's role
                system_prompt = f"""You are {self.name}, a helpful voice assistant"""
                
                response = get_cloud_response(command, system_prompt=system_prompt)
                
                # Keep only first 2-3 sentences for voice output
                sentences = response.split('. ')
                if len(sentences) > 3:
                    response = '. '.join(sentences[:3]) + '.'
                
                self.speak(response)
                return
            except Exception as e:
                print(f"⚠ Cloud processing failed: {e}")
                self.cloud_available = False
                self.offline_fallback_active = True
                self.speak("Cloud service unavailable. Falling back to offline mode.")
        
        print("💾 Using offline mode...")
        response = None
        if RASA_AVAILABLE:
            try:
                if self.rasa_handler is None:
                    self.rasa_handler = RasaHandler()
                response = self.rasa_handler.get_response(command)
            except Exception:
                response = None
        if not response:
            response = self._offline_response(command)
        self.speak(response)
    
    def _offline_response(self, query):
        """Simple offline responses when cloud is unavailable."""
        query_lower = query.lower()
        
        # Greetings
        if any(word in query_lower for word in ["hello", "hi", "hey", "namaste"]):
            return f"Hello! I'm {self.name}. Cloud service is unavailable, but I can still help with basic queries."
        
        # Time
        if "time" in query_lower:
            from datetime import datetime
            return f"The time is {datetime.now().strftime('%I:%M %p')}"
        
        # Date
        if "date" in query_lower or "today" in query_lower:
            from datetime import datetime
            return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}"
        
        # Who are you
        if "who are you" in query_lower or "your name" in query_lower:
            return f"I am {self.name}, your voice assistant. I'm currently in offline mode."
        
        # What can you do
        if "what can you" in query_lower or "help" in query_lower:
            return "In offline mode, I can tell you the time and date. For more features, enable the cloud connection."
        
        # Default
        return "I'm sorry, I need cloud connection for that. Please set SARVAM_API_KEY if you want online features."
    
    def run(self):
        """Run the voice assistant."""
        print(f"\n{'='*60}")
        print(f"  {self.name} Voice Assistant - Voice Mode")
        print(f"  Uses Sarvam cloud when available")
        print(f"{'='*60}")
        mode_label = {"online": "Online only", "offline": "Offline only", "auto": "Auto"}.get(self.mode, "Auto")
        print(f"Mode: {mode_label}")
        print(f"Status: {'🟢 Online' if self.cloud_available else '🔴 Offline'}")
        
        if self.mode == "online" and not self.cloud_available:
            print("\n⚠️  Cloud service unavailable in Online mode!")
            print("   Set SARVAM_API_KEY and check internet connection")
            print("   Offline fallback is disabled in this mode.\n")
        elif not self.cloud_available:
            print("\n⚠️  Cloud service unavailable!")
            print("   Set SARVAM_API_KEY to enable cloud responses")
            print("   Continuing in offline mode...\n")
        
        print(f"\nPress Ctrl+C to exit\n")
        
        self.speak(f"Hello! I am {self.name}. I'm ready to assist you.")
        
        self.running = True
        
        try:
            while self.running:
                if not self.listen_for_wake_word():
                    continue

                if self.porcupine:
                    self.speak("Yes?")

                active_window = self.assistant_config.get("sleep_timeout", 300)
                listen_timeout = self.assistant_config.get("listen_timeout", 30)
                last_activity = time.time()
                print(f"🕑 Awake for up to {int(active_window/60)} minutes. Say a command.")

                while self.running and (time.time() - last_activity) < active_window:
                    if self.mode == "online" and self.cloud_available and not self.offline_fallback_active:
                        command = self.listen_for_command_online(timeout=listen_timeout)
                    else:
                        command = self.listen_for_command(timeout=listen_timeout)

                    if command:
                        last_activity = time.time()
                        self.process_command(command)
                    else:
                        print("… No speech detected. Staying awake until timeout.", end='\r')

                    time.sleep(0.2)

                print("\n😴 No voice activity. Going back to sleep.")
                
        except KeyboardInterrupt:
            print("\n\n⏹ Interrupted by user")
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources."""
        print("\n🧹 Cleaning up...")
        
        if self.porcupine:
            self.porcupine.delete()
        
        if self.audio:
            self.audio.terminate()
        
        print(f"{self.name} stopped.\n")


def main():
    """Main entry point."""
    print(f"\n{'='*60}")
    print(f"  DALI Voice Assistant")
    print(f"  Voice-only mode with cloud optional")
    print(f"{'='*60}\n")
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("❌ Error: Python 3.7+ required")
        sys.exit(1)
    
    # Check for test mode
    if len(sys.argv) > 1 and sys.argv[1] in ["--test", "-t"]:
        print("🎤 Microphone Test Mode\n")
        test_microphone()
        return
    
    # Cloud API key is optional; runs in offline mode without it
    
    # Initialize and run assistant
    try:
        assistant = VoiceAssistant()
        assistant.run()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def test_microphone():
    """Test microphone and speech recognition."""
    print("Testing your microphone and speech recognition...\n")
    
    if not VOSK_AVAILABLE:
        print("❌ Vosk not installed. Install with: pip install vosk")
        return
    
    if not AUDIO_AVAILABLE:
        print("❌ PyAudio not installed. Install with: pip install pyaudio")
        return
    
    try:
        config = load_config()
        assistant_config = config.get("assistant", {})
        language = assistant_config.get("language", "en-in")
        
        offline_config = config.get("offline", {})
        vosk_models = offline_config.get("vosk_models", {})
        model_path = vosk_models.get(language, "models/vosk-model-en-in-0.5")
        
        if not os.path.exists(model_path):
            print(f"❌ Vosk model not found at: {model_path}")
            return
        
        print("✓ Loading speech model...")
        model = Model(model_path)
        recognizer = KaldiRecognizer(model, 16000)
        
        print("✓ Opening microphone...")
        audio = pyaudio.PyAudio()
        stream = audio.open(
            rate=16000,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=4000
        )
        
        print("\n✓ Microphone is working!")
        print("🎤 Say something...\n")
        
        start_time = time.time()
        recognized_text = ""
        
        while time.time() - start_time < 10:
            data = stream.read(4000, exception_on_overflow=False)
            
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
                if text:
                    recognized_text = text
                    print(f"✓ I heard: {text}")
            else:
                partial = json.loads(recognizer.PartialResult())
                partial_text = partial.get("partial", "").strip()
                if partial_text:
                    print(f"   Listening: {partial_text}", end='\r')
        
        print("\n")
        
        if not recognized_text:
            result = json.loads(recognizer.FinalResult())
            recognized_text = result.get("text", "").strip()
        
        stream.stop_stream()
        stream.close()
        audio.terminate()
        
        if recognized_text:
            print(f"✅ SUCCESS! Final text: {recognized_text}\n")
            print("Your microphone and speech recognition are working perfectly!")
        else:
            print("⚠️  No speech detected.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
