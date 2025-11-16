# main.py – Thread-safe voice assistant with session management

import time
import threading
import sys
import os
import warnings

# Suppress all warnings and verbose logging
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow warnings

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from offline.recognizer import Recognizer
from offline.tts_engine import speak, shutdown_tts, wait_for_speech_complete
from offline.wake_word import WakeWordDetector
from online.network_utils import is_cloud_available
from online.cloud_connector import get_cloud_response
from offline.rasa_handler import RasaHandler
from config_loader import load_config

import logging
logging.getLogger('rasa').setLevel(logging.CRITICAL)
logging.getLogger('matplotlib').setLevel(logging.CRITICAL)
logging.getLogger('tensorflow').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)


# Load config
config = load_config()
ASSISTANT_NAME = config["assistant"]["name"]
SESSION_TIMEOUT = config["assistant"]["session_timeout"]
LANGUAGE = config["assistant"]["language"].lower()


# Global variables
detector = None
session_active = False
session_timer = None
speech_lock = threading.Lock()  # Prevent concurrent handle_speech execution


# Initialize recognizer 
recognizer = Recognizer()

# Initialize Rasa handler in background (non-blocking)
rasa_handler = None
rasa_ready = threading.Event()

def _init_rasa_background():
    """Load Rasa model in background thread to avoid blocking startup."""
    global rasa_handler
    print("Initializing Rasa model in background...")
    try:
        rasa_handler = RasaHandler()
        print("Rasa model loaded successfully.")
    except Exception as e:
        print(f"Warning: Rasa initialization failed: {e}")
        rasa_handler = None
    finally:
        rasa_ready.set()  # Signal that initialization is complete (success or fail)

# Start Rasa loading in background
rasa_thread = threading.Thread(target=_init_rasa_background, daemon=True)
rasa_thread.start()


def end_session():
    """Called when session timeout expires"""
    global session_active
    
    session_active = False
    print("Session ended. Say wake word to wake me up.")


def reset_session_timer():
    """Reset the session timeout timer"""
    global session_timer
    
    # Cancel existing timer if any
    if session_timer:
        session_timer.cancel()
    
    # Start new timer
    session_timer = threading.Timer(SESSION_TIMEOUT, end_session)
    session_timer.start()
    print(f"Session timer reset")


def get_response(text: str) -> str:
    """
    Tries cloud LLM (OpenAI) first, falls back to Rasa if unavailable.
    Waits for Rasa to initialize if needed.
    """
    if is_cloud_available():
        try:
            reply = get_cloud_response(text)
            return reply
        except Exception:
            # Fall back to Rasa if cloud call fails
            rasa_ready.wait(timeout=60)
            if rasa_handler:
                return rasa_handler.get_response(text)
            return "I'm still loading. Please try again."
    else:
        # Wait longer for Rasa to load (up to 60 seconds)
        if not rasa_ready.is_set():
            rasa_ready.wait(timeout=60)
        
        if rasa_handler:
            return rasa_handler.get_response(text)
        return "I'm still loading. Please try again."
    

def handle_speech():
    """Triggered when wake word is detected - thread-safe version."""
    global session_active, detector
    
    # Try to acquire lock - if already locked, skip this wake word detection
    if not speech_lock.acquire(blocking=False):
        return
    
    try:
        # Stop recognizer stream while responding
        recognizer.stop_stream()
        
        # Activate session and start timer
        session_active = True
        speak("Yes?", recognizer.language, wait=True)  # Wait for speech to complete
        reset_session_timer()
        
        # Restart recognizer stream
        recognizer.start_stream()
        
        # Keep listening while session is active
        while session_active:
            text = recognizer.listen_once(timeout_seconds=config["assistant"]["listen_timeout"])
            
            if not text:
                continue
            
            print(f"You said: {text}")
            
            # Stop listening before responding
            recognizer.stop_stream()
            
            # Exit commands
            if any(x in text.lower() for x in ("exit", "quit", "stop", "goodbye")):
                speak("Goodbye", recognizer.language, wait=True)
                
                session_active = False
                if session_timer:
                    session_timer.cancel()
                if detector:
                    detector.stop()
                shutdown_tts()
                exit(0)
            
            # Sleep command - go back to wake word mode
            if any(x in text.lower() for x in ("sleep", "go to sleep", "that's all")):
                speak("Okay, going to sleep.", recognizer.language, wait=True)
                
                session_active = False
                if session_timer:
                    session_timer.cancel()
                break  # Exit loop, go back to wake word detection
            
            # Get and speak reply
            reply = get_response(text)
            print(f"{ASSISTANT_NAME} ({recognizer.language}): {reply}")
            
            # Speak and WAIT for completion before listening again
            try:
                speak(reply, recognizer.language, wait=True)
            except Exception as e:
                print(f"[ERROR] speak() failed: {e}")
            
            # Small additional buffer
            time.sleep(0.5)
            
            # Reset timer after each interaction
            reset_session_timer()
            
            # Restart recognizer for next input
            recognizer.start_stream()
    
    except Exception as e:
        print(f"[ERROR] {e}")
        session_active = False
    
    finally:
        # Always release the lock when done
        speech_lock.release()


def main():
    global detector
    
    print(f"\n{'='*50}")
    print(f"{ASSISTANT_NAME} Voice Assistant")
    print(f"{'='*50}\n")
    
    # Check cloud LLM status at startup
    if is_cloud_available():
        print("[INFO] Cloud LLM available (using OpenAI)")
    else:
        print("[INFO] Cloud LLM unavailable — Using Rasa offline mode")

    speak(f"Hello, I am {ASSISTANT_NAME}", "en-in", wait=True)
    
    detector = WakeWordDetector(callback=handle_speech)
    detector.start()
    
    speak(f"How can I help you?", "en-in", wait=True)
    print(f"\n[READY] Listening for wake word...\n")
    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[EXIT] Shutting down...")
        if session_timer:
            session_timer.cancel()
        
        if detector:
            detector.stop()
        speak("Goodbye.", "en-in", wait=True)
        shutdown_tts()
        print("[EXIT] Done")


if __name__ == "__main__":
    main()