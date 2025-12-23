"""
Pytest configuration for the test suite.

This file is automatically loaded by pytest and handles:
- Adding project root to Python path
- Shared fixtures across all tests
"""

import sys
from pathlib import Path

# Add project root to Python path for all tests
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))