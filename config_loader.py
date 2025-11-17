import json
import os
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Path to config.json
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

def substitute_env_variables(value):
    
    # Replace ${VAR_NAME} with .env values
    if not isinstance(value, str):
        return value
    
    def replace_var(match):
        var_name = match.group(1)
        env_value = os.getenv(var_name)
        if env_value is None:
            return match.group(0)
        return env_value
    
    # Replace ${VAR_NAME} with actual value
    return re.sub(r'\$\{([^}]+)\}', replace_var, value)


def process_config(obj):
    
    # Recursively process config to substitute environment variables
    if isinstance(obj, dict):
        return {key: process_config(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [process_config(item) for item in obj]
    else:
        return substitute_env_variables(obj)


def load_config():
    
    # Load JSON config from config/config.json
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")
    
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    return process_config(config)
    
