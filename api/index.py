"""Vercel Python serverless entry point.

Vercel's ``@vercel/python`` runtime detects the exported ASGI ``app`` and serves
it. The ``vercel.json`` rewrite sends every ``/api/*`` request here; FastAPI then
routes it using the ``/api/...`` paths defined in ``server/main.py``.

Mutable state (portfolio, price cache) is persisted via ``server/storage.py``,
which uses the KV/Upstash REST API when its env vars are present (see README /
CLAUDE.md). The committed holdings DB under ``data/`` is bundled with this
function via ``functions.includeFiles`` in ``vercel.json``.
"""

from server.main import app  # noqa: F401  (re-exported for the Vercel runtime)
