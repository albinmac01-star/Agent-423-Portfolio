"""
pytest.ini equivalent — configure pytest for the local package.
Run all tests from the local/ directory.
"""
# This file allows pytest to find the executor and config packages

import sys
import os

# Add local/ to sys.path so tests can import executor, config, schemas
sys.path.insert(0, os.path.dirname(__file__))
