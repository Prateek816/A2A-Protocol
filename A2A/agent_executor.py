from abc import ABC , abstractmethod
from .model.other import EventQueue , RequestContext

class AgentExecutor(ABC):
    """Every Agent should be wrap AgentExecutor"""

    @abstractmethod
    async def execute(self , context: RequestContext , event_queue:EventQueue):
        """Execute the agent's logic for a given request context
            The agent should read necessay information from the 'context' and publish 'Task' or 'Message Events,or
            'TaskStatusUpdateEvent'/'TaskArtifactUpdateEvent' to the 'event_queue'.This method should return once
            the agent 's execution for this request is complete or yields control(e.g., enters an input-required state).

            Args:
                context: The request context containing message,task ID , etc.
                event_queue: The queue to publish events to.
        """

    @abstractmethod
    async def cancel(self , context: RequestContext, event_queue:EventQueue):
        """Request the agent to cancel on ongoing task.
        
            The agent should attempt to stop the task identified by the task_id
            in the context and publish a 'TaskStatusUpdateEvent' with state
            'TaskState.canceled to the 'event_queue'

            Args:
                context: The request context containing message,task ID , etc.
                event_queue: The queue to publish events to.
        """



