#!/usr/bin/env python3
"""
Interactive TranscriptX CLI entry point.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from transcriptx.cli.main import _main_impl

if __name__ == "__main__":
    _main_impl() 