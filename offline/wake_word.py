# Wake-word detection using custom Porcupine .ppn file

import pvporcupine
import pyaudio
import struct
import threading
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_loader import load_config

config = load_config()
WAKE_PATH = config["assistant"]["wake_word_path"]
ACCESS_KEY = config["keys"]["picovoice"]

class WakeWordDetector:
    def __init__(self, callback):
        """Initialize wakeup word detector"""
        
        self.keyword_path = WAKE_PATH
        self.access_key = ACCESS_KEY
        self.callback = callback
       
        if not os.path.exists(self.keyword_path):
            raise FileNotFoundError(f"Wakeup word file not found: {self.keyword_path}")

        self.porcupine = None
        self.pa = None
        self.audio_stream = None
        self.running = False
        self.thread = None

    def start(self):
        """Start wakeup word detection in a background thread"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self.listen_for_wake_word, daemon=True)
        self.thread.start()

        
    def stop(self):
        """Stop wake word detection"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
        
        if self.porcupine:
            self.porcupine.delete()
        
        if self.pa:
            self.pa.terminate()

    def listen_for_wake_word(self):
        """Internal method that runs in background thread"""
        try:
            self.porcupine = pvporcupine.create(
                access_key=self.access_key,
                keyword_paths=[self.keyword_path]
            )
            
            self.pa = pyaudio.PyAudio()
            self.audio_stream = self.pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length
            )
            
            while self.running:
                pcm = self.audio_stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                
                keyword_index = self.porcupine.process(pcm)
                
                if keyword_index >= 0:
                    if self.callback:
                        self.callback()
                        
        except Exception as e:
            self.running = False
        