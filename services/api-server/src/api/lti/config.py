"""
LTI tool configuration loader.

Loads platform config from JSON and RSA keys from files or PEM strings.
Supports both file paths (local dev) and inline values (K8s secrets).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pylti1p3.tool_config import ToolConfDict

from api.settings import get_settings

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parents[5]  # project root


def _load_key(value: str) -> str:
    """Load a PEM key from a string or file path.

    If *value* starts with ``-----BEGIN``, it's treated as an inline PEM.
    Otherwise it's resolved as a file path (absolute, or relative to the
    project root).
    """
    if value.startswith("-----BEGIN"):
        return value

    path = Path(value)
    if not path.is_absolute():
        path = _BASE_DIR / path

    return path.read_text()


def _load_platform_config(value: str) -> dict:
    """Load platform config from a JSON string or file path."""
    stripped = value.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(stripped)

    path = Path(value)
    if not path.is_absolute():
        path = _BASE_DIR / path

    with open(path) as f:
        return json.load(f)


def get_tool_config() -> ToolConfDict:
    """Load tool configuration from platform JSON and RSA key files."""
    settings = get_settings()

    platform_settings = _load_platform_config(settings.lti_platform_config)
    tool_conf = ToolConfDict(platform_settings)

    try:
        private_key = _load_key(settings.lti_private_key)
        public_key = _load_key(settings.lti_public_key)
    except FileNotFoundError:
        logger.warning(
            "LTI RSA keys not found. "
            "Generate with: openssl genrsa -out configs/lti/private.key 2048 && "
            "openssl rsa -in configs/lti/private.key -pubout -out configs/lti/public.key",
        )
        raise

    # Register keys for each platform issuer
    for iss in platform_settings:
        for reg in platform_settings[iss]:
            client_id = reg.get("client_id")
            tool_conf.set_private_key(iss, private_key, client_id=client_id)
            tool_conf.set_public_key(iss, public_key, client_id=client_id)

    return tool_conf
