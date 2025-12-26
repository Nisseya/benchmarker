from __future__ import annotations

import json
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, Optional

import asyncio
import requests


@dataclass(frozen=True)
class SseEvent:
    event: str
    data: Dict


def iter_sse_events(url: str, payload: Dict, timeout_s: int = 3600):
    with requests.post(url, json=payload, stream=True, timeout=timeout_s) as r:
        r.raise_for_status()

        event: Optional[str] = None
        data_lines: list[str] = []

        for raw in r.iter_lines(decode_unicode=True):
            if raw is None:
                continue
            line = raw.strip()

            if line == "":
                if event and data_lines:
                    data_str = "\n".join(data_lines)
                    try:
                        obj = json.loads(data_str)
                    except Exception:
                        obj = {"raw": data_str}
                    yield SseEvent(event=event, data=obj)
                event = None
                data_lines = []
                continue

            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())


async def aiter_sse_events(url: str, payload: Dict) -> AsyncGenerator[SseEvent, None]:
    q: asyncio.Queue[Optional[SseEvent]] = asyncio.Queue()

    def _producer():
        try:
            for ev in iter_sse_events(url, payload):
                q.put_nowait(ev)
        finally:
            q.put_nowait(None)

    await asyncio.to_thread(_producer)

    while True:
        ev = await q.get()
        if ev is None:
            break
        yield ev
