"""Persistence backend for ETF Tracker mutable state.

The portfolio and the price cache are small JSON blobs. Locally (and in tests)
they live as files under ``~/.tradingagents/``. On Vercel — where the filesystem
is ephemeral — they are stored in a Redis-compatible KV store (Upstash / Vercel
KV) accessed over its HTTP REST API, which works cleanly from serverless
functions and needs no extra dependencies (stdlib ``urllib`` only).

The KV backend activates automatically when the integration's environment
variables are present; otherwise the file backend is used. This keeps local dev
and the test suite (which patch the module-level file paths in ``server.main``)
working unchanged.

Recognised env vars (either naming scheme works):
- ``KV_REST_API_URL`` / ``KV_REST_API_TOKEN``            (Vercel KV)
- ``UPSTASH_REDIS_REST_URL`` / ``UPSTASH_REDIS_REST_TOKEN`` (Upstash)
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

_KV_TIMEOUT = 5  # seconds — KV REST calls must answer quickly


def _kv_url() -> str | None:
    return os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")


def _kv_token() -> str | None:
    return os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")


def kv_configured() -> bool:
    """True when a KV/Upstash REST endpoint is configured via env vars."""
    return bool(_kv_url() and _kv_token())


def _kv_request(path: str, data: bytes | None = None) -> dict:
    url = f"{_kv_url().rstrip('/')}/{path}"
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {_kv_token()}"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=_KV_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _kv_get(key: str) -> dict | None:
    result = _kv_request(f"get/{key}").get("result")
    if not result:
        return None
    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return None


def _kv_set(key: str, value: dict) -> None:
    # Upstash REST: POST /set/{key} with the value as the request body.
    _kv_request(f"set/{key}", data=json.dumps(value, ensure_ascii=False).encode("utf-8"))


def read_blob(key: str, file_path: Path) -> dict | None:
    """Return the stored JSON blob for ``key`` (KV) or ``file_path`` (file), or None."""
    if kv_configured():
        try:
            return _kv_get(key)
        except Exception:
            return None
    if not file_path.exists():
        return None
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_blob(key: str, data: dict, file_path: Path) -> None:
    """Persist the JSON blob ``data`` under ``key`` (KV) or to ``file_path`` (file)."""
    if kv_configured():
        _kv_set(key, data)
        return
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
