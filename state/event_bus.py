import asyncio
from typing import Callable, List, Dict, Any, Optional
from state.schemas import Event

class EventBus:
    def __init__(self):
        self.subscribers: List[Callable[[Event], Any]] = []
        self.events: List[Event] = []
        self._lock = asyncio.Lock()

    def subscribe(self, callback: Callable[[Event], Any]) -> None:
        self.subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Event], Any]) -> None:
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    async def emit(self, event_type: str, agent: str, payload: Dict[str, Any] = None) -> Event:
        evt = Event(
            type=event_type,  # type: ignore
            agent=agent,
            payload=payload or {}
        )
        async with self._lock:
            self.events.append(evt)

        # Notify subscribers
        for sub in self.subscribers:
            try:
                res = sub(evt)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
        return evt

    def get_events(self) -> List[Event]:
        return list(self.events)

    def clear(self) -> None:
        self.events.clear()
