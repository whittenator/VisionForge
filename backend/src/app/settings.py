from __future__ import annotations

import os


def is_production() -> bool:
    """True when the deployment is explicitly marked production via APP_ENV."""
    return os.getenv("APP_ENV", "development").strip().lower() in ("production", "prod")


def require_secure_setting(name: str, value: str, insecure_values: tuple[str, ...]) -> str:
    """Fail fast on known-insecure default secrets in production.

    In development the insecure default is allowed so `docker-compose up`
    keeps working out of the box.
    """
    if is_production() and (not value or value in insecure_values):
        raise RuntimeError(
            f"{name} is unset or uses an insecure default. "
            f"Set a strong value before running with APP_ENV=production."
        )
    return value
