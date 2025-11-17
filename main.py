"""main.py
DALI Voice Assistant - Voice-Only Mode
Powered by FREE Groq API for cloud processing.
Listens via microphone, responds with voice.
"""

import os
import sys
import json
import struct
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from config_loader import load_config
    from online.cloud_connector import get_cloud_response
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
    """Voice-only DALI assistant powered by Groq."""
    
    def __init__(self):
        """Initialize the voice assistant."""
        self.config = load_config()
        self.assistant_config = self.config.get("assistant", {})
        self.name = self.assistant_config.get("name", "DALI")
        self.language = self.assistant_config.get("language", "en-in")
        
        self.running = False
        self.cloud_available = False
        self.tts_handler = None
        self.audio = None
        self.porcupine = None
        self.vosk_model = None
        self.recognizer = None
        
        # Check requirements
        if not all([AUDIO_AVAILABLE, TTS_AVAILABLE, VOSK_AVAILABLE]):
            print("\n❌ Voice mode requires: pyaudio, pyttsx3, and vosk")
            print("Install with:")
            print("  pip install pyaudio")
            print("  pip install pyttsx3==2.91")
            print("  pip install vosk")
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
                print(f"✓ Wake word 'Hello {self.name}' initialized")
            else:
                print(f"⚠ Wake word file not found: {wake_word_path}")
        except Exception as e:
            print(f"⚠ Wake word initialization failed: {e}")
            self.porcupine = None
    
    def _check_cloud_availability(self):
        """Check if Groq cloud service is available."""
        print("Checking Groq API...")
        
        groq_key = os.environ.get("GROQ_API_KEY") or \
                   (self.config.get("keys") or {}).get("groq_api_key", "").replace("${GROQ_API_KEY}", "")
        
        if groq_key and not groq_key.startswith("${"):
            try:
                # Quick test call
                test_response = get_cloud_response("Hi")
                if test_response:
                    self.cloud_available = True
                    print("✓ Groq API (FREE) is ready!")
                    return
            except Exception as e:
                print(f"⚠ Groq API test failed: {e}")
        
        self.cloud_available = False
        print("❌ Groq API not available!")
        print("   Get FREE API key: https://console.groq.com/")
        print("   Then set: export GROQ_API_KEY='your-key-here'")
    
    def speak(self, text):
        """Convert text to speech."""
        if not text:
            return
            
        print(f"🔊 {self.name}: {text}")
        
        if not self.tts_handler:
            print("⚠ TTS handler not available")
            return
        
        # Use the TTS handler which creates fresh engine each time
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
            print(f"🎤 Listening for wake word: 'Hello {self.name}'...")
            print(f"{'='*60}")
            
            while self.running:
                pcm = audio_stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                
                keyword_index = self.porcupine.process(pcm)
                if keyword_index >= 0:
                    print(f"✓ Wake word detected!")
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
    
    def process_command(self, command):
        """Process voice command using Groq cloud."""
        if not command:
            self.speak("I didn't catch that. Please try again.")
            return
        
        command_lower = command.lower()
        
        # Check for exit commands
        if any(word in command_lower for word in ["goodbye", "exit", "quit", "stop", "bye"]):
            self.speak("Goodbye! Have a great day!")
            self.running = False
            return
        
        # Try cloud processing with Groq
        if self.cloud_available:
            try:
                print("☁️ Processing with Groq (FREE)...")
                
                # Create a system prompt to define DALI's role
                system_prompt = f"""You are {self.name}, a helpful voice assistant. You are NOT Salvador Dali the artist.
You can access current information and perform tasks. Keep responses concise and conversational (2-3 sentences max) since you're speaking out loud.
For time/date queries, provide the actual current time or date.
Be friendly, helpful, and direct."""
                
                response = get_cloud_response(command, system_prompt=system_prompt)
                
                # Keep only first 2-3 sentences for voice output
                sentences = response.split('. ')
                if len(sentences) > 3:
                    response = '. '.join(sentences[:3]) + '.'
                
                self.speak(response)
                return
            except Exception as e:
                print(f"⚠ Groq processing failed: {e}")
                self.cloud_available = False  # Mark as unavailable
                self.speak("I'm having trouble with the cloud service.")
        
        # Fallback to basic offline responses
        print("💾 Using offline mode...")
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
            return "In offline mode, I can tell you the time and date. For more features, please check the Groq API connection."
        
        # Default
        return "I'm sorry, I need cloud connection for that. Please check if GROQ_API_KEY is set correctly."
    
    def run(self):
        """Run the voice assistant."""
        print(f"\n{'='*60}")
        print(f"  {self.name} Voice Assistant - Voice Mode")
        print(f"  Powered by Groq (FREE)")
        print(f"{'='*60}")
        print(f"Status: {'🟢 Online' if self.cloud_available else '🔴 Offline'}")
        
        if not self.cloud_available:
            print("\n⚠️  Cloud service unavailable!")
            print("   Get FREE Groq API key: https://console.groq.com/")
            print("   Then set: export GROQ_API_KEY='gsk_your_key_here'")
            print("   Continuing in limited offline mode...\n")
        
        print(f"\nPress Ctrl+C to exit\n")
        
        self.speak(f"Hello! I am {self.name}. I'm ready to assist you.")
        
        self.running = True
        
        try:
            while self.running:
                # Wait for wake word or manual activation
                if not self.listen_for_wake_word():
                    continue
                
                if self.porcupine:
                    self.speak("Yes?")
                
                # Listen for command
                command = self.listen_for_command()
                
                # Process command
                if command:
                    self.process_command(command)
                else:
                    self.speak("I didn't hear anything. Please try again.")
                
                time.sleep(0.5)
                
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
    print(f"  Powered by FREE Groq API")
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
    
    # Check Groq API key
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        print("⚠️  WARNING: GROQ_API_KEY not set!")
        print("\n📝 To get FREE Groq API key:")
        print("   1. Go to: https://console.groq.com/")
        print("   2. Sign up (FREE, no credit card)")
        print("   3. Create API key")
        print("   4. Set it:")
        print("      Windows: set GROQ_API_KEY=gsk_your_key_here")
        print("      Linux/Mac: export GROQ_API_KEY=gsk_your_key_here")
        print("\n   Continuing in limited offline mode...\n")
    
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
            print(f"Download from: https://alphacephei.com/vosk/models")
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
        print("🎤 Say something (I'll listen for 10 seconds)...\n")
        
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
            print("\nTroubleshooting:")
            print("1. Check if your microphone is plugged in")
            print("2. Make sure microphone is not muted")
            print("3. Speak louder and closer to the microphone")
            print("4. Check Windows Sound Settings > Input device")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
