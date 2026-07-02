"""Environment loading. Loads the repo-root .env once (inline comments/quotes
handled by python-dotenv) so both the API server and scripts see the same config.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

_loaded = False


def load_env() -> None:
    global _loaded
    if _loaded:
        return
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(root, ".env"), override=False)
    _loaded = True
