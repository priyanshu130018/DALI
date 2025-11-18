import threading
import queue
import pyttsx3
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import load_config

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
    """Get or create TTS engine safely with COM initialization"""
    global engine
    
    # Initialize COM for Windows threading
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except ImportError:
        pass  # Not on Windows or pythoncom not available
    
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
    
    target_lower = target.lower()
    for voice in voices:
        if target_lower in voice.name.lower():
            return voice.id
    
    return voices[0].id

def tts_worker():
    """Background thread to process TTS queue"""
    # Initialize COM for this thread on Windows
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except ImportError:
        pass  # Not on Windows
    
    try:
        engine = get_engine()
        
        while True:
            item = tts_queue.get()
            
            if item is None:
                break
            
            text, lang_code, wait = item
            
            if not text:
                tts_queue.task_done()
                continue
            
            # Set voice for language
            voice_id = get_voice_id_for_language_from_engine(engine, lang_code)
            if voice_id:
                engine.setProperty('voice', voice_id)
            
            # Clear speech complete event
            speech_complete.clear()
            
            # Speak
            engine.say(text)
            engine.runAndWait()
            
            # Signal completion
            speech_complete.set()
            
            tts_queue.task_done()
            
    except Exception as e:
        print(f"TTS Worker Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Uninitialize COM on thread exit
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except ImportError:
            pass

def ensure_worker_started():
    """Make sure TTS worker thread is running"""
    global worker_thread
    
    with worker_lock:
        if worker_thread is None or not worker_thread.is_alive():
            worker_thread = threading.Thread(target=tts_worker, daemon=True)
            worker_thread.start()

def speak(text, lang_code="en-in", wait=False):
    """Queue text for speech (thread-safe)"""
    if not text:
        return
    
    ensure_worker_started()
    tts_queue.put((text, lang_code, wait))
    
    if wait:
        wait_for_speech_complete()

def wait_for_speech_complete(timeout=10):
    """Wait for current speech to complete"""
    speech_complete.wait(timeout=timeout)

def shutdown_tts():
    """Gracefully shutdown TTS system"""
    global engine, worker_thread
    
    # Signal worker to stop
    tts_queue.put(None)
    
    # Wait for worker to finish
    if worker_thread and worker_thread.is_alive():
        worker_thread.join(timeout=2)
    
    # Cleanup engine
    with engine_lock:
        if engine:
            try:
                engine.stop()
            except:
                pass
            engine = None
    
    print("TTS engine shutdown complete")

# Auto-start worker on import
ensure_worker_started()
