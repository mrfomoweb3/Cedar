"""Environment loading. Loads the repo-root .env once (inline comments/quotes
handled by python-dotenv) so both the API server and scripts see the same config.

Also materializes secrets provided as env vars (the way a PaaS host injects
them) into the files the rest of the app expects — so nothing sensitive is ever
committed to the repo or baked into an image.
"""
from __future__ import annotations

import base64
import logging
import os

from dotenv import load_dotenv

log = logging.getLogger("cedar.config")
_loaded = False


def load_env() -> None:
    global _loaded
    if _loaded:
        return
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(root, ".env"), override=False)
    _materialize_secret_key(root)
    _loaded = True


def _materialize_secret_key(root: str) -> None:
    """If CASPER_SECRET_KEY_B64 is set (a base64-encoded secret_key.pem, the
    portable way to pass the signing key to a host), decode it to a file and
    point CASPER_SECRET_KEY at it. Never logs the key contents."""
    b64 = os.getenv("CASPER_SECRET_KEY_B64", "").strip()
    if not b64:
        return
    target = os.getenv("CASPER_SECRET_KEY_PATH",
                       os.path.join(root, "data", "agent_secret_key.pem"))
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f:
            f.write(base64.b64decode(b64))
        os.chmod(target, 0o600)
        os.environ["CASPER_SECRET_KEY"] = target
        log.info("materialized Casper signing key from CASPER_SECRET_KEY_B64")
    except Exception:  # noqa: BLE001
        log.exception("failed to materialize CASPER_SECRET_KEY_B64")
