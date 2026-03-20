"""
Platform detection for cross-platform compatibility.
Detected once at import time and exposed as module-level constants.
"""

import platform
from pathlib import Path

PLATFORM = platform.system()  # "Windows", "Darwin", "Linux"
IS_WINDOWS = PLATFORM == "Windows"
IS_MAC = PLATFORM == "Darwin"
IS_LINUX = PLATFORM == "Linux"
HOME_DIR = str(Path.home())
