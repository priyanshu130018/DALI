# Handles offline natural language understanding using Rasa 3.x

from rasa.core.agent import Agent
import inspect
import asyncio
import sys
import os
from datetime import datetime
import random
import webbrowser
import warnings

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_loader import load_config

config = load_config()

class RasaHandler:
    
    def __init__(self):
        """Find and return the path to the latest .tar.gz model"""
        try:
            # Load from config
            self.model_path = config["offline"]["rasa_model"]
                        
            if not self.model_path:
                raise ValueError("Rasa model path is not configured in config.json")
            
            # Check if the path exists
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Rasa model path not found: {self.model_path}")
            
            # Load the Rasa agent (suppress output)
            self.agent = Agent.load(self.model_path)
            
            # Load intent-to-action mapping from domain
            self.intent_to_action = self.load_intent_action_mapping()
            
        except FileNotFoundError as e:
            print(f"File Error: {e}")
            raise
        except ValueError as e:
            print(f"Configuration Error: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error loading Rasa model: {e}")
            raise

    def load_intent_action_mapping(self) -> dict:
        """Load intent-to-action mapping from Rasa domain and stories"""
        mapping = {}
        
        try:
            # Get domain from agent
            domain = self.agent.domain
            
            # Method 1: Check stories/rules for intent -> action mappings
            if hasattr(domain, 'intent_properties'):
                for intent_name, properties in domain.intent_properties.items():
                    if 'triggers' in properties:
                        mapping[intent_name] = properties['triggers']
            
            # Method 2: Use naming convention (intent: tell_time -> action: action_tell_time)
            # This works if you follow the pattern: intent_name -> action_{intent_name}
            for intent in domain.intents:
                # Check if corresponding action exists in domain
                action_name = f"action_{intent}"
                if action_name in domain.action_names_or_texts:
                    mapping[intent] = action_name
            
            # Method 3: Fallback - check stories programmatically
            # (This requires parsing the training data, which is more complex)
            
        except Exception as e:
            # Silently fail - mapping will be empty
            mapping = {}
        
        return mapping

    def execute_custom_action(self, action_name: str) -> str:
        """
        Universal action executor - automatically finds and calls the matching method.
        Converts action_name (e.g., "action_tell_time") to method name (e.g., "_action_tell_time")
        """
        # Convert action name to method name
        method_name = f"_{action_name}"
        
        # Check if method exists
        if hasattr(self, method_name) and callable(getattr(self, method_name)):
            try:
                method = getattr(self, method_name)
                return method()
            except Exception as e:
                print(f"Error executing {action_name}: {e}")
                return f"Sorry, I encountered an error while executing {action_name}"
        else:
            # Fallback: generate a default response
            action_type = action_name.replace("action_", "").replace("_", " ")
            return f"I understand you want to {action_type}, but I don't know how to do that yet"
    
    # Individual action methods - just add any method starting with _action_
    def _action_tell_time(self) -> str:
        now = datetime.now()
        current_time = now.strftime("%I:%M %p")
        return f"The current time is {current_time}"
    
    def _action_tell_date(self) -> str:
        today = datetime.now()
        date_str = today.strftime("%B %d, %Y")
        return f"Today is {date_str}"
    
    def _action_tell_fact(self) -> str:
        facts = [
            "Did you know? Honey never spoils!",
            "Octopuses have three hearts and blue blood!",
            "A day on Venus is longer than its year!",
            "Bananas are berries, but strawberries aren't!",
            "The Eiffel Tower can grow up to 6 inches in summer!"
        ]
        return random.choice(facts)
    
    def _action_tell_joke(self) -> str:
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "Why did the scarecrow win an award? He was outstanding in his field!",
            "What do you call a fake noodle? An impasta!",
            "Why don't eggs tell jokes? They'd crack each other up!",
            "What did the ocean say to the beach? Nothing, it just waved!"
        ]
        return random.choice(jokes)
    
    def _action_play_music(self) -> str:
        return "Opening music player"
    
    def _action_change_music(self) -> str:
        return "Changing to next track"
    
    def _action_open_app(self) -> str:
        t = getattr(self, "last_text", "") or ""
        tl = t.lower()
        if "youtube" in tl:
            try:
                webbrowser.open("https://www.youtube.com/")
                return "Opening YouTube"
            except Exception:
                return "Could not open YouTube"
        return "Please specify which app to open"
    
    def _action_close_app(self) -> str:
        return "Please specify which app to close"
    
    def _action_volume_up(self) -> str:
        return "Increasing volume"
    
    def _action_volume_down(self) -> str:
        return "Decreasing volume"
    
    def _action_shutdown_pc(self) -> str:
        return "Shutting down in 60 seconds"
    
    def _action_restart_pc(self) -> str:
        return "Restarting in 60 seconds"

    def get_response(self, text: str) -> str:
        """Send user text to Rasa model and return best response."""
        try:
            self.last_text = text
            responses = self.agent.handle_text(text)

            # Support both sync and async Rasa handlers
            if inspect.isawaitable(responses):
                try:
                    responses = asyncio.run(responses)
                except RuntimeError:
                    return "I'm not ready to process that right now."

            # Check if responses is empty or None - action server not running
            if not responses or (isinstance(responses, list) and len(responses) == 0):
                # Try to get intent from last parse
                try:
                    tracker = self.agent.tracker_store.get_or_create_tracker("default")
                    if inspect.isawaitable(tracker):
                        tracker = asyncio.run(tracker)
                    intent = tracker.latest_message.intent.get("name")
                    
                    # Use dynamically loaded mapping
                    if intent in self.intent_to_action:
                        action_name = self.intent_to_action[intent]
                        return self.execute_custom_action(action_name)
                except Exception:
                    pass
                
                return "I'm not sure about that."
            
            if responses and isinstance(responses, list):
                response_texts = []
                
                for item in responses:
                    if isinstance(item, dict):
                        # Check for text response (most common)
                        if "text" in item:
                            response_texts.append(item["text"])
                        
                        # Check for recipient_id (sometimes present)
                        elif "recipient_id" in item and "text" in item:
                            response_texts.append(item["text"])
                        
                        # Check for custom action result
                        elif "custom" in item:
                            custom_data = item.get("custom", {})
                            if "text" in custom_data:
                                response_texts.append(custom_data["text"])
                            elif "action" in custom_data:
                                action_name = custom_data["action"]
                                custom_response = self.execute_custom_action(action_name)
                                response_texts.append(custom_response)
                    
                    # Handle string responses
                    elif isinstance(item, str):
                        response_texts.append(item)
                
                # Return combined response or first available
                if response_texts:
                    final_response = " ".join(response_texts)
                    return final_response
            
            # Fallback if no valid response
            return "I'm not sure about that."
        
        except Exception as e:
            return "Something went wrong while processing your request."

    def _action_switch_language(self) -> str:
        t = getattr(self, "last_text", "") or ""
        tl = t.lower()
        if "hindi" in tl:
            return "Switched language to hindi"
        if "english" in tl:
            return "Switched language to english"
        return "I could not switch language"