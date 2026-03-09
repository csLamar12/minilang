#!/usr/bin/env python3
"""
Launcher script for NovaScript GUI
"""

import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gui import main

if __name__ == "__main__":
    main()