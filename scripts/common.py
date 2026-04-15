"""Shared utilities for SEO automation scripts."""

import json
import os
import sys

from google.oauth2 import service_account


def get_credentials(scopes):
    """Load Google service account credentials from env or file.

    Args:
        scopes: List of OAuth2 scope strings.

    Returns:
        google.oauth2.service_account.Credentials
    """
    key_env = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")
    key_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

    if key_env:
        info = json.loads(key_env)
        return service_account.Credentials.from_service_account_info(info, scopes=scopes)
    elif os.path.exists(key_file):
        return service_account.Credentials.from_service_account_file(key_file, scopes=scopes)
    else:
        print("❌ Ключ сервисного аккаунта не найден.")
        sys.exit(1)
