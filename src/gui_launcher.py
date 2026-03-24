#!/usr/bin/env python3
# File        : gui_launcher.py
# Description : Launcher script for NovaScript GUI
# =============================================================================
# Authors     : Rachjaye Gayle      - 2100400
#             : Rushane  Green      - 2006930
#             : Abbygayle Higgins   - 2106327
#             : Lamar Haye          - 2111690
# -----------------------------------------------------------------------------
# Institution : University of Technology, Jamaica
# Faculty     : School of Computing & Information Technology (FENC)
# Course      : Analysis of Programming Languages | CIT4004
# Tutor       : Dr. David White
# =============================================================================

import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gui import main

if __name__ == "__main__":
    main()