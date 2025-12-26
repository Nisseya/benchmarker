from __future__ import annotations

import json
from typing import Any, Dict

def sse(event: str, data: Dict[str, Any]) -> str:
    print(f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n")
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
