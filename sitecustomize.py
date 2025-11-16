"""Suppress all deprecation warnings and verbose logging at startup"""
import warnings
import os
import sys

# Suppress all deprecation warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=PendingDeprecationWarning)
warnings.filterwarnings('ignore')

# Set TensorFlow logging
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Suppress verbose module loading
sys.dont_write_bytecode = False
