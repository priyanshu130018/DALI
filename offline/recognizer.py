import json
import queue
import os
import time
import vosk
import pyaudio
from langdetect import detect
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import load_config

config = load_config()
MODELS = config["offline"]["vosk_models"]   
SAMPLE_RATE = 16000
FRAMES_PER_BUFFER = 4000

class Recognizer:
    def __init__(self):
        try:
            # Load default language from config
            self.language = config["assistant"]["language"].lower()
            self.model_path = MODELS.get(self.language)
            
            # Validate models configuration exists
            if not MODELS:
                raise ValueError("No Vosk models configured in config.json")
            
            # If language not found, use first available model
            if not self.model_path:
                print(f"Model for '{self.language}' not found, using default")
                self.model_path = list(MODELS.values())[0]
                self.language = list(MODELS.keys())[0]
            
            # Validate model path exists
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Vosk model path not found: {self.model_path}")
            
            # Load the Vosk model
            print(f"Loading Vosk model from {self.model_path} ...")
            self.model = vosk.Model(self.model_path)
            self.rec = vosk.KaldiRecognizer(self.model, SAMPLE_RATE)
            
            # Initialize PyAudio
            self.pa = pyaudio.PyAudio()
            self.stream = None
            self.q = queue.Queue()
            self.running = False
            
            print(f"Vosk model loaded successfully ({self.language})")
            
        except FileNotFoundError as e:
            print(f"File Error: {e}")
            raise
        except ValueError as e:
            print(f"Configuration Error: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error loading Vosk model: {e}")
            raise


    def audio_callback(self, indata, frames, time, status):
        """Callback for audio stream (called from separate thread)"""
        self.q.put(indata)
        # return the captured data and continue
        return (indata, pyaudio.paContinue)

    def start_stream(self):
        try:
            if self.stream:
                return
            self.stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=FRAMES_PER_BUFFER,
                stream_callback=self.audio_callback
            )
            self.stream.start_stream()
            self.running = True
        except Exception as e:
            print(f"Error starting audio stream: {e}")
            raise

    def stop_stream(self):
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            self.running = False
        except Exception as e:
            print(f"Error stopping stream: {e}")

    def reload_model(self, new_lang):
       """Reload Vosk model if language changes"""
       try:
           if new_lang != self.language:
               # Validate new language exists in config
               if new_lang not in MODELS:
                   print(f"Model for '{new_lang}' not available, keeping '{self.language}'")
                   return
               
               new_model_path = MODELS[new_lang]
               
               # Validate new model path exists
               if not os.path.exists(new_model_path):
                   print(f"Model path not found: {new_model_path}, keeping current model")
                   return
               
               print(f"Switching model: {self.language} → {new_lang}")
               self.language = new_lang
               self.model_path = new_model_path
               self.model = vosk.Model(self.model_path)
               self.rec = vosk.KaldiRecognizer(self.model, SAMPLE_RATE)
               print(f"Model switched to {new_lang}")
               
       except Exception as e:
           print(f"Error reloading model: {e}")

    def listen_once(self, timeout_seconds=None):
        """Listen for speech and detect language automatically"""
        if timeout_seconds is None:
            timeout_seconds = config["assistant"]["listen_timeout"]
            
        try:
            if not self.stream:
                self.start_stream()

            start = time.time()
            text = ""
            
            while True:
                try:
                    data = self.q.get(timeout=0.5)
                except queue.Empty:
                    data = None

                if data:
                    if self.rec.AcceptWaveform(data):
                        result = json.loads(self.rec.Result())
                        text = result.get("text", "")
                        break
                        
                if time.time() - start > timeout_seconds:
                    result = json.loads(self.rec.FinalResult())
                    text = result.get("text", "")
                    break

            if not text:
                return ""

            # Detect language using text
            if text.strip():
                lang_guess = detect(text)
            else:
                lang_guess = "en"

            # Map langdetect output to our config models
            if lang_guess.startswith("hi"):
                new_lang = "hi-in"
            else:
                new_lang = "en-in"

            # Reload model if necessary
            if new_lang != self.language:
                self.reload_model(new_lang)

            print(f"Detected Language: {new_lang} | Text: {text}")
            return text.lower()
            
        except Exception as e:
            print(f"Error during listening: {e}")
            return ""


    def __del__(self):
        try:
            self.stop_stream()
        except Exception:
            pass
        try:
            self.pa.terminate()
        except Exception:
            pass
        print("Audio stream closed.")