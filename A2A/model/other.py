import asyncio
from typing import Union
from A2A.model.core import Task, TaskArtifactUpdateEvent, TaskStatusUpdateEvent , Message


Event = Union[
    Task,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
]

class EventQueue:
    def __init__(self):
        self._queue = asyncio.Queue()

    async def enqueue_event(self, event: Event) -> None:
        await self._queue.put(event)

    async def get_event(self) -> Event:
        return await self._queue.get()
    
class RequestContext:
    message: Message
    current_task: Task | None
    request_id: str
    requested_extensions: set[str]