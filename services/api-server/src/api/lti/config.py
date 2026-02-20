"""
LTI tool configuration loader.

Loads platform config from JSON and RSA keys from files.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from pylti1p3.tool_config import ToolConfDict

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parents[5]  # project root
_LTI_CONFIG_DIR = _BASE_DIR / "configs" / "lti"


def get_tool_config() -> ToolConfDict:
    """Load tool configuration from platform JSON and RSA key files."""
    platform_config_path = os.getenv(
        "LTI_PLATFORM_CONFIG",
        str(_LTI_CONFIG_DIR / "platform.json"),
    )

    with open(platform_config_path) as f:
        settings = json.load(f)

    tool_conf = ToolConfDict(settings)

    # Load RSA keys
    private_key_path = os.getenv(
        "LTI_PRIVATE_KEY", str(_LTI_CONFIG_DIR / "private.key")
    )
    public_key_path = os.getenv(
        "LTI_PUBLIC_KEY", str(_LTI_CONFIG_DIR / "public.key")
    )

    try:
        with open(private_key_path) as f:
            private_key = f.read()
        with open(public_key_path) as f:
            public_key = f.read()
    except FileNotFoundError:
        logger.warning(
            "LTI RSA keys not found at %s / %s. "
            "Generate with: openssl genrsa -out configs/lti/private.key 2048 && "
            "openssl rsa -in configs/lti/private.key -pubout -out configs/lti/public.key",
            private_key_path,
            public_key_path,
        )
        raise

    # Register keys for each platform issuer
    for iss in settings:
        for reg in settings[iss]:
            client_id = reg.get("client_id")
            tool_conf.set_private_key(iss, private_key, client_id=client_id)
            tool_conf.set_public_key(iss, public_key, client_id=client_id)

    return tool_conf
