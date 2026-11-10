"""
Person 3 Asyncio Event Bus (backend/app/events.py)
Manages WebSocket clients on `/ws/events` and broadcasts typed event envelopes:
  graph_loaded, node_updated, summary_ready, diff_updated, merge_checked,
  coverage_updated, test_run_finished, impact_computed, risk_updated,
  file_changed, error
"""
from __future__ import annotations

import time
from typing import Any, Callable, Awaitable, Dict, List, Set
from fastapi import WebSocket


class EventBus:
    def __init__(self) -> None:
        self.clients: Set[WebSocket] = set()
        self.history: List[Dict[str, Any]] = []
        self._listeners: List[Callable[[str, str, Dict[str, Any]], Awaitable[None]]] = []

    def add_client(self, ws: WebSocket) -> None:
        self.clients.add(ws)

    def remove_client(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    def subscribe(self, listener: Callable[[str, str, Dict[str, Any]], Awaitable[None]]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    async def emit(self, event_type: str, project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        envelope = {
            "type": event_type,
            "project_id": project_id,
            "payload": payload,
            "ts": int(time.time() * 1000),
        }
        self.history.append(envelope)
        if len(self.history) > 500:
            self.history = self.history[-500:]

        for listener in list(self._listeners):
            try:
                await listener(event_type, project_id, payload)
            except Exception:
                pass

        stale: Set[WebSocket] = set()
        for ws in list(self.clients):
            try:
                await ws.send_json(envelope)
            except Exception:
                stale.add(ws)
        for ws in stale:
            self.clients.discard(ws)

        return envelope


event_bus = EventBus()
