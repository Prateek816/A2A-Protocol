import asyncio
import json
from datetime import datetime ,timezone
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from .model.core import (
    Task , AgentCard,Message,TextPart,TaskRequest,TaskStatusUpdate,TaskStatus
)
import uuid

class A2AServer:
    """
    Base Class for all A2A agent servers.
    Subclass this and implement 'handle task'
    """

    def __init__(self,agent_card:AgentCard,lifespan = None):
        self.card = agent_card
        self.app = FastAPI(title=agent_card.name,lifespan= lifespan)
        self._tasks: dict[str,Task] = {}
        self._queues: dict[str,asyncio.Queue] = {}
        self._setup_routes()

    def _setup_routes(self):
        app = self.app

        @app.get("/.well-known/agent.json")
        async def get_agent_card():
            return self.card.model_dump()

        @app.get("/health")
        async def health():
            return {
                    "status":"ok",
                    "agent":self.card.name
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

            #Run handler in background
            asyncio.create_task(self._run_task(task))
            return task
        
        @app.get("/tasks/{task_id}")
        async def get_task(task_id:str):
            task = self._tasks.get(task_id)
            if not task:
                from fastapi import HTTPException
                raise HTTPException(404,"Task not found")
            return task.model_dump(mode="json")
        
        @app.get("/tasks/{task_id}/events")
        async def stream_task_events(task_id:str):
            if task_id not in self._queues:
                from fastapi import HTTPException
                raise HTTPException(404,"Task Not Found")
            return StreamingResponse(
                self._event_generator(task_id),
                media_type="text/event-stream",
                headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"}
            )
    
    async def _event_generator(self,task_id:str):
        queue = self._queues[task_id]
        while True:
            update = await queue.get()
            yield f"data: {json.dumps(update.model_dump(mode="json"))}\n\n"
            if update.final:
                break
    
    async def _run_task(self,task:Task):
        task.status = TaskStatus(
            state="working",
            message = task.status.message,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await self._emit(task.id,TaskStatusUpdate(
            task_id=task.id,  
            status=TaskStatus(state="working",message = task.status.message,timestamp=datetime.now(timezone.utc).isoformat()),
            final=False
        ))

        try:
            result = await self.handle_task(task)
            task.status = TaskStatus(
                state="completed",
                message = task.status.message,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            # can add more info in task that is to ccomplted at and updated at

            if result:
                task.artifacts.append(result["artifact"])
            await self._emit(task.id,TaskStatusUpdate(
            task_id=task.id,  
            status=TaskStatus(state="completed",message = task.status.message,timestamp=datetime.now(timezone.utc).isoformat()),
            final=True
        ))
        except Exception as e:
            error_message = Message(
                role="agent",
                parts=[
                    TextPart(
                        type="text",
                        text=f"Error: {str(e)}"
                    )
                ],
                taskId=task.id,
                metadata={}
            )
            task.status = TaskStatus(
                state="failed",
                message=error_message,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            await self._emit(
                task.id,
                TaskStatusUpdate(
                    task_id=task.id,
                    status=task.status,
                    message=error_message,
                    final=True
                )
            )
            raise
        finally:
            # Clean up the queue after the task finishes to prevent memory leaks
            self._queues.pop(task.id, None)
    
    async def _emit(self,task_id:str,update:TaskStatusUpdate):
        if task_id in self._queues:
            await self._queues[task_id].put(update)

    async def emit_progress(self,task_id:str,message:str):
        """Call this from handle_task to stream immediate updates."""
        
    
    async def handle_task(self,task:Task):
        """Override in subclass. Return {"artifact":Artifact}"""
        raise NotImplementedError