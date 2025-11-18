"""rasa_handler.py
Handles offline natural language understanding using Rasa 3.x
Provides intent recognition and custom action execution.
"""

from rasa.core.agent import Agent
import inspect
import asyncio
import sys
import os
from datetime import datetime
import random
import webbrowser
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_loader import load_config

config = load_config()


class RasaHandler:
    """
    Rasa-based NLU handler for offline intent recognition and action execution.
    """
    
    def __init__(self):
        """Initialize Rasa agent and load intent-to-action mappings."""
        # Initialize instance variables
        self.last_text = ""
        self.agent = None
        self.intent_to_action = {}
        
        try:
            # Load model path from config
            self.model_path = config.get("offline", {}).get("rasa_model")
            
            if not self.model_path:
                raise ValueError("Rasa model path is not configured in config.json under 'offline.rasa_model'")
            
            # Validate model file exists
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(
                    f"Rasa model not found: {self.model_path}\n"
                    f"Please train a Rasa model and update the path in config.json"
                )
            
            # Load the Rasa agent
            logging.info(f"Loading Rasa model from: {self.model_path}")
            self.agent = Agent.load(self.model_path)
            logging.info("Rasa agent loaded successfully")
            
            # Load intent-to-action mapping from domain
            self.intent_to_action = self.load_intent_action_mapping()
            logging.info(f"Loaded {len(self.intent_to_action)} intent-to-action mappings")
            
        except FileNotFoundError as e:
            logging.error(f"File not found: {e}")
            raise
        except ValueError as e:
            logging.error(f"Configuration error: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error loading Rasa model: {type(e).__name__}: {e}")
            raise

    def load_intent_action_mapping(self) -> dict:
        """
        Load intent-to-action mapping from Rasa domain.
        
        Returns:
            Dictionary mapping intent names to action names
        """
        mapping = {}
        
        try:
            # Get domain from agent
            domain = self.agent.domain
            
            # Method 1: Check stories/rules for intent -> action mappings
            if hasattr(domain, 'intent_properties'):
                for intent_name, properties in domain.intent_properties.items():
                    if 'triggers' in properties:
                        mapping[intent_name] = properties['triggers']
                        logging.debug(f"Mapped intent '{intent_name}' -> '{properties['triggers']}'")
            
            # Method 2: Use naming convention (intent: tell_time -> action: action_tell_time)
            for intent in domain.intents:
                # Check if corresponding action exists in domain
                action_name = f"action_{intent}"
                if action_name in domain.action_names_or_texts:
                    # Don't override if already mapped
                    if intent not in mapping:
                        mapping[intent] = action_name
                        logging.debug(f"Auto-mapped intent '{intent}' -> '{action_name}'")
            
        except Exception as e:
            logging.warning(f"Could not load intent-action mapping: {e}")
            mapping = {}
        
        return mapping

    def execute_custom_action(self, action_name: str) -> str:
        """
        Execute a custom action by name.
        
        Converts action_name (e.g., "action_tell_time") to method name 
        (e.g., "_action_tell_time") and executes it.
        
        Args:
            action_name: Name of the action to execute
            
        Returns:
            Response text from the action
        """
        # Convert action name to method name
        method_name = f"_{action_name}"
        
        # Check if method exists
        if hasattr(self, method_name) and callable(getattr(self, method_name)):
            try:
                method = getattr(self, method_name)
                result = method()
                logging.debug(f"Executed action '{action_name}' successfully")
                return result
            except Exception as e:
                error_msg = f"Error executing {action_name}: {type(e).__name__}: {e}"
                logging.error(error_msg)
                return f"Sorry, I encountered an error while processing that request."
        else:
            # Fallback: generate a default response
            action_type = action_name.replace("action_", "").replace("_", " ")
            logging.warning(f"Action method '{method_name}' not found for '{action_name}'")
            return f"I understand you want to {action_type}, but I don't know how to do that yet."
    
    # ========== Action Methods ==========
    # Add any custom action by creating a method starting with _action_
    
    def _action_tell_time(self) -> str:
        """Tell the current time."""
        now = datetime.now()
        current_time = now.strftime("%I:%M %p")
        return f"The current time is {current_time}"
    
    def _action_tell_date(self) -> str:
        """Tell today's date."""
        today = datetime.now()
        date_str = today.strftime("%B %d, %Y")
        return f"Today is {date_str}"
    
    def _action_tell_fact(self) -> str:
        """Share a random fun fact."""
        facts = [
            "Did you know? Honey never spoils!",
            "Octopuses have three hearts and blue blood!",
            "A day on Venus is longer than its year!",
            "Bananas are berries, but strawberries aren't!",
            "The Eiffel Tower can grow up to 6 inches in summer!"
        ]
        return random.choice(facts)
    
    def _action_tell_joke(self) -> str:
        """Tell a random joke."""
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "Why did the scarecrow win an award? He was outstanding in his field!",
            "What do you call a fake noodle? An impasta!",
            "Why don't eggs tell jokes? They'd crack each other up!",
            "What did the ocean say to the beach? Nothing, it just waved!"
        ]
        return random.choice(jokes)
    
    def _action_play_music(self) -> str:
        """Handle music playback request."""
        return "Opening music player"
    
    def _action_change_music(self) -> str:
        """Handle skip to next track."""
        return "Changing to next track"
    
    def _action_open_app(self) -> str:
        """Open an application based on user request."""
        text_lower = self.last_text.lower()
        
        if "youtube" in text_lower:
            try:
                webbrowser.open("https://www.youtube.com/")
                return "Opening YouTube"
            except Exception as e:
                logging.error(f"Failed to open YouTube: {e}")
                return "Sorry, I could not open YouTube"
        
        return "Please specify which app to open"
    
    def _action_close_app(self) -> str:
        """Close an application."""
        return "Please specify which app to close"
    
    def _action_volume_up(self) -> str:
        """Increase system volume."""
        return "Increasing volume"
    
    def _action_volume_down(self) -> str:
        """Decrease system volume."""
        return "Decreasing volume"
    
    def _action_shutdown_pc(self) -> str:
        """Initiate system shutdown."""
        return "Shutting down in 60 seconds"
    
    def _action_restart_pc(self) -> str:
        """Initiate system restart."""
        return "Restarting in 60 seconds"
    
    def _action_switch_language(self) -> str:
        """Switch assistant language."""
        text_lower = self.last_text.lower()
        
        if "hindi" in text_lower:
            return "Switched language to Hindi"
        elif "english" in text_lower:
            return "Switched language to English"
        
        return "I could not identify the language. Please say 'switch to Hindi' or 'switch to English'"

    def get_response(self, text: str) -> str:
        """
        Process user text through Rasa and return response.
        
        Args:
            text: User input text
            
        Returns:
            Response text
        """
        if not text or not text.strip():
            return "I didn't catch that. Could you repeat?"
        
        try:
            # Store last text for use in actions
            self.last_text = text
            
            # Get response from Rasa
            responses = self.agent.handle_text(text)
            
            # Support both sync and async Rasa handlers
            if inspect.isawaitable(responses):
                try:
                    responses = asyncio.run(responses)
                except RuntimeError as e:
                    logging.error(f"Async error: {e}")
                    return "I'm not ready to process that right now."
            
            # Check if responses is empty (action server not running)
            if not responses or (isinstance(responses, list) and len(responses) == 0):
                logging.debug("No responses from Rasa, attempting intent-based fallback")
                
                # Try to get intent from last parse and execute custom action
                try:
                    tracker = self.agent.tracker_store.get_or_create_tracker("default")
                    if inspect.isawaitable(tracker):
                        tracker = asyncio.run(tracker)
                    
                    intent = tracker.latest_message.intent.get("name")
                    logging.debug(f"Detected intent: {intent}")
                    
                    # Use dynamically loaded mapping
                    if intent and intent in self.intent_to_action:
                        action_name = self.intent_to_action[intent]
                        return self.execute_custom_action(action_name)
                    
                except Exception as e:
                    logging.warning(f"Error getting intent from tracker: {type(e).__name__}: {e}")
                
                return "I'm not sure about that. Could you rephrase?"
            
            # Process responses
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
                    logging.debug(f"Generated response: {final_response[:50]}...")
                    return final_response
            
            # Fallback if no valid response
            logging.warning("No valid response extracted from Rasa")
            return "I'm not sure about that. Could you rephrase?"
        
        except Exception as e:
            logging.error(f"Error processing request: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return "Something went wrong while processing your request."