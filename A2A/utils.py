from .model.core import Message, TextPart
from typing import Optional

from a2a.server import request_handlers 


def new_agent_text_message(
    text: str,
    task_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Message:
    """
    Create a new agent message containing a single TextPart.
    """

    return Message(
        role="agent",
        parts=[
            TextPart(
                type="text",
                text=text,
            )
        ],
        taskId=task_id,
        metadata=metadata or {},
    )