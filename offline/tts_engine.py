import threading
import queue
import pyttsx3
import time

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_loader import load_config

config = load_config()
RATE = config["assistant"]["voice_rate"]
VOICE_CONFIG = config.get("voices", {})

# Single engine and a dedicated worker thread
engine = None
engine_lock = threading.Lock()

tts_queue = queue.Queue()
worker_thread = None
worker_lock = threading.Lock()

# Event to signal when speech is complete
speech_complete = threading.Event()


def get_engine():
    """Get or create TTS engine safely"""
    global engine

    with engine_lock:
        if engine is None:
            engine = pyttsx3.init()
            engine.setProperty('rate', RATE)
        return engine


def get_voice_id_for_language_from_engine(engine, lang_code):
    """Find the best voice for a language"""
    
    voices = engine.getProperty('voices')
    target = VOICE_CONFIG.get(lang_code)

    if not voices:
        return None
    
    if not target:
        return voices[0].id

    target_l = target.lower()
    for v in voices:
        try:
            name = (v.name or "").lower()
            vid = (v.id or "").lower()
        except Exception:
            continue
        if target_l in name or target_l in vid:
            return v.id
    return voices[0].id


def tts_worker():
    """Background thread that speaks queued text"""
    engine = get_engine()
    
    while True:
        item = tts_queue.get()
        
        # Check for shutdown sentinel
        if item is None:
            tts_queue.task_done()
            break
        
        text, lang_code = item
        
        try:
            voice_id = get_voice_id_for_language_from_engine(engine, lang_code)
            if voice_id:
                try:
                    engine.setProperty('voice', voice_id)
                except Exception as e:
                    # Voice setting failed, but continue with default
                    pass
            
            engine.say(text)
            engine.runAndWait()
            
            # Add small delay to ensure audio finishes
            time.sleep(0.3)

        except Exception as e:
            # Log error to stderr so user can see it
            import sys
            print(f"[TTS ERROR] {e}", file=sys.stderr)
        
        finally:
            # Signal completion after each item
            speech_complete.set()
            tts_queue.task_done()


def ensure_worker():
    """Make sure worker thread is running (thread-safe)"""
    global worker_thread
    
    with worker_lock:
        if worker_thread is None or not worker_thread.is_alive():
            worker_thread = threading.Thread(target=tts_worker, daemon=False)  # Changed to False
            worker_thread.start()


def speak(text, lang_code="en-in", wait=False):
    """
    Non-blocking: enqueue text to be spoken
    
    Args:
        text: Text to speak
        lang_code: Language code
        wait: If True, block until speech completes
    """
    
    if not text:
        return
    
    ensure_worker()
    
    # Clear previous completion status
    speech_complete.clear()
    
    # Add to queue
    tts_queue.put((text, lang_code))
    
    # Wait if requested
    if wait:
        speech_complete.wait(timeout=30)  # Wait max 30 seconds


def wait_for_speech_complete(timeout=30):
    """Wait for current speech to complete"""
    return speech_complete.wait(timeout=timeout)


def is_speaking():
    """Check if TTS is currently speaking"""
    return not speech_complete.is_set() and tts_queue.qsize() > 0


def shutdown_tts():
    """Gracefully shutdown TTS worker thread"""
    global worker_thread
    
    # Send sentinel to stop worker
    tts_queue.put(None)
    
    # Wait for worker to finish
    if worker_thread and worker_thread.is_alive():
        worker_thread.join(timeout=2)