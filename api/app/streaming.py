"""Format NDJSON des flux envoyés au navigateur."""

from __future__ import annotations

import json


def event(**kw) -> bytes:
    return (json.dumps(kw, ensure_ascii=False) + "\n").encode()
