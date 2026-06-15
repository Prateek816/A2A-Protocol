import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from .model.core import (
    Task, AgentCard, Message, TextPart, TaskRequest,
    TaskStatusUpdateEvent, TaskArtifactUpdateEvent, TaskStatus
)
from .model.other import RequestContext, EventQueue
import uuid
from .agent_executor import AgentExecutor


class A2AServer:
    """
    Base Class for all A2A agent servers.
    Subclass this and implement 'handle_task'.
    """

    def __init__(
        self,
        agent_card: AgentCard,
        executor: AgentExecutor,
        lifespan=None
    ):
        self.card = agent_card
        self.executor = executor
        self.app = FastAPI(
            title=agent_card.name,
            lifespan=lifespan
        )
        self._tasks: dict[str, Task] = {}
        self._queues: dict[str, asyncio.Queue] = {}
        self._event_queues: dict[str, EventQueue] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}

        self._setup_routes()

    def _setup_routes(self):
        app = self.app

        @app.get("/.well-known/agent.json")
        async def get_agent_card():
            return self.card.model_dump()

        @app.get("/health")
        async def health():
            return {
                "status": "ok",
                "agent": self.card.name
            }

        @app.post("/tasks", response_model=Task)
        async def create_task(request: TaskRequest):
            task = Task(
                id=str(uuid.uuid4()),
                sessionId=request.session_id,
                status=TaskStatus(
                    state="submitted",
                    message=request.message,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ),
                history=[request.message],
                artifacts=[],
            )

            self._tasks[task.id] = task
            self._queues[task.id] = asyncio.Queue()
            self._event_queues[task.id] = EventQueue()

            self._running_tasks[task.id] = asyncio.create_task(
                self._run_task(task)
            )
            return task

        @app.get("/tasks/{task_id}")
        async def get_task(task_id: str):
            task = self._tasks.get(task_id)
            if not task:
                raise HTTPException(404, "Task not found")
            return task.model_dump(mode="json")

        @app.get("/tasks/{task_id}/events")
        async def stream_task_events(task_id: str):
            if task_id not in self._queues:
                raise HTTPException(404, "Task not found")
            return StreamingResponse(
                self._event_generator(task_id),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
            )

        @app.post("/tasks/{task_id}/cancel")
        async def cancel_task(task_id: str):
            task = self._tasks.get(task_id)
            if not task:
                raise HTTPException(404, "Task not found")

            context = RequestContext(
                message=task.status.message,
                current_task=task,
                request_id=task.id,
            )
            event_queue = self._event_queues.get(task_id, EventQueue())
            await self.executor.cancel(context=context, event_queue=event_queue)

            running = self._running_tasks.get(task_id)
            if running:
                running.cancel()

            return {"status": "cancel requested"}

    async def _event_generator(self, task_id: str) -> AsyncGenerator[str, None]:
        queue = self._queues[task_id]
        while True:
            update = await queue.get()
            payload = json.dumps(update.model_dump(mode="json"))
            yield f"data: {payload}\n\n"
            if getattr(update, "final", False):
                break

    async def _run_task(self, task: Task):
        task.status = TaskStatus(
            state="working",
            message=task.status.message,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await self._emit(task.id, TaskStatusUpdateEvent(
            id=task.id,
            status=task.status,
            final=False,
            metadata=None
        ))

        try:
            context = RequestContext(
                message=task.status.message,
                current_task=task,
                request_id=task.id,
            )
            event_queue = self._event_queues[task.id]

            # Run executor and event-relay concurrently
            relay = asyncio.create_task(self._relay_events(task, event_queue))
            await self.executor.execute(context=context, event_queue=event_queue)

            # Drain any remaining events, then stop relay
            await event_queue.publish(None)  # sentinel to stop relay
            await relay

            task.status = TaskStatus(
                state="completed",
                message=task.status.message,
                timestamp=datetime.now(timezone.utc).isoformat()
            )

            await self._emit(task.id, TaskStatusUpdateEvent(
                id=task.id,
                status=task.status,
                final=True,
                metadata=None
            ))

        except asyncio.CancelledError:
            task.status = TaskStatus(
                state="canceled",
                message=task.status.message,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            await self._emit(task.id, TaskStatusUpdateEvent(
                id=task.id,
                status=task.status,
                final=True,
                metadata=None
            ))
            raise

        except Exception as e:
            error_message = Message(
                role="agent",
                parts=[TextPart(type="text", text=f"Error: {str(e)}")],
                taskId=task.id,
                metadata={}
            )
            task.status = TaskStatus(
                state="failed",
                message=error_message,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            await self._emit(task.id, TaskStatusUpdateEvent(
                id=task.id,
                status=task.status,
                final=True,
                metadata=None
            ))

        finally:
            self._queues.pop(task.id, None)
            self._event_queues.pop(task.id, None)
            self._running_tasks.pop(task.id, None)

    async def _relay_events(self, task: Task, event_queue: EventQueue):
        """Pull events from the executor's EventQueue and forward to the SSE queue,
        updating task state as artifacts/status events arrive."""
        while True:
            event = await event_queue.next()
            if event is None:
                break

            if isinstance(event, TaskArtifactUpdateEvent):
                task.artifacts.append(event.artifact)
                await self._emit(task.id, TaskStatusUpdateEvent(
                    id=task.id,
                    status=task.status,
                    final=False,
                    metadata=event.metadata
                ))
            elif isinstance(event, TaskStatusUpdateEvent):
                task.status = event.status
                await self._emit(task.id, event)
            elif isinstance(event, Task):
                task.status = event.status
                task.artifacts = event.artifacts
                await self._emit(task.id, TaskStatusUpdateEvent(
                    id=task.id,
                    status=task.status,
                    final=False,
                    metadata=None
                ))

    async def _emit(self, task_id: str, update):
        if task_id in self._queues:
            await self._queues[task_id].put(update)