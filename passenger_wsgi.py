"""
Passenger entry point for cPanel "Setup Python App".

cPanel points the application to this file and expects a module level
`application` callable. The virtualenv is already active when Passenger
imports this file, so no interpreter switching is done here.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

from config.wsgi import application  # noqa: E402,F401
