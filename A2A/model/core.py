"""Core Concepts -
Tasks are core concept in A2A proptocol , they are created by the client , the state is maintained by remote server , Multiple Tasks can belong to the same session via optional sessionID
Upon recieving the task request agent can satisfy request , schdule , reject , negotiate a different execution method , request more information from the client and delegate to other agents or systems

"""

from pydantic import BaseModel , JsonValue , Field
from typing import Any , Optional , Literal
from datetime import datetime, timezone
import uuid

TaskState = Literal[
    "submitted",
    "working",
    "input-required",
    "completed",
    "canceled",
    "failed",
    "unknown",
]

class TextPart(BaseModel):
    type: Literal["text", "text/plain"]
    text: str

class FilePart(BaseModel):
    type: str  
    file_name: Optional[str] = None
    file_content: Optional[str] = None #Base64
    uri: Optional[str] = None

class JsonPart(BaseModel):
    type: Literal["json","application/json"]
    json : Any

Part = TextPart | JsonPart | FilePart

class Message(BaseModel):
    role: Literal["user", "agent"]
    parts: list[Part]
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    taskId:Optional[str]
    metadata : dict[str,Any]

"Artifact are the standard way to convey the final output of an agent in the A2A protocol"
class Artifact(BaseModel):
    name:Optional[str]
    description:Optional[str]
    parts:list[Part]
    metadata:Optional[dict[str,Any]]
    index: int = Field(description="Index of the artifact within its owning task")
    append : Optional[bool]
    lastChunk:Optional[bool]

class TaskStatus(BaseModel):
    state:TaskState
    message:Optional[Message]
    timestamp:Optional[str]

"""Tasks are core concept in A2A proptocol , they are created by the client , the state is maintained by remote server , Multiple Tasks can belong to the same session via optional sessionID
Upon recieving the task request agent can satisfy request , schdule , reject , negotiate a different execution method , request more information from the client and delegate to other agents or systems"""
class Task(BaseModel):
    id : str
    sessionId:str
    status:TaskStatus
    history:Optional[list[Message]]
    artifacts:Optional[list[Artifact]]

class PushNotificationConfig(BaseModel):
    config:Optional[dict[str,Any]]

class TaskSendParams(BaseModel):
    id:str
    sessionId:Optional[str]
    message:Message
    historyLength:Optional[int]
    pushNotification:Optional[PushNotificationConfig]
    metadata:Optional[dict[str,Any]]

class TaskStatusUpdateEvent(BaseModel):
    id:str
    status:TaskStatus
    final:bool
    metadata:Optional[dict[str,Any]]

class TaskArtifactUpdateEvent(BaseModel):
    id:str
    artifact:Artifact
    metadata:Optional[dict[str,Any]]

from typing import Optional
from pydantic import BaseModel, Field


class Provider(BaseModel):
    organization: str = Field(
        description="Organization providing the agent."
    )
    url: str = Field(
        description="Provider website URL."
    )


class Capabilities(BaseModel):
    streaming: Optional[bool] = Field(
        default=None,
        description="Whether the agent supports streaming responses (e.g. SSE)."
    )
    pushNotifications: Optional[bool] = Field(
        default=None,
        description="Whether the agent can push task updates to clients."
    )
    stateTransitionHistory: Optional[bool] = Field(
        default=None,
        description="Whether the agent exposes task state transition history."
    )


class Authentication(BaseModel):
    schemes: list[str] = Field(
        description="Supported authentication schemes such as Bearer or Basic."
    )
    credentials: Optional[str] = Field(
        default=None,
        description="Credentials for accessing private agents."
    )


class Skill(BaseModel):
    id: str = Field(
        description="Unique skill identifier."
    )
    name: str = Field(
        description="Human-readable skill name."
    )
    description: str = Field(
        description="Description of the skill."
    )
    tags: list[str] = Field(
        description="Tags describing the skill category."
    )
    examples: Optional[list[str]] = Field(
        default=None,
        description="Example prompts or scenarios for this skill."
    )
    inputModes: Optional[list[str]] = Field(
        default=None,
        description="Supported input MIME types for this skill."
    )
    outputModes: Optional[list[str]] = Field(
        default=None,
        description="Supported output MIME types for this skill."
    )


class AgentCard(BaseModel):
    name: str = Field(
        description="Human-readable agent name."
    )

    description: str = Field(
        description="Description of the agent."
    )

    url: str = Field(
        description="URL where the agent is hosted."
    )

    provider: Optional[Provider] = Field(
        default=None,
        description="Information about the service provider."
    )

    version: str = Field(
        description="Agent version."
    )

    documentationUrl: Optional[str] = Field(
        default=None,
        description="URL to the agent documentation."
    )

    capabilities: Capabilities = Field(
        description="Capabilities supported by the agent."
    )

    authentication: Authentication = Field(
        description="Authentication requirements."
    )

    defaultInputModes: list[str] = Field(
        description="Default supported input MIME types."
    )

    defaultOutputModes: list[str] = Field(
        description="Default supported output MIME types."
    )

    skills: list[Skill] = Field(
        description="Collection of skills supported by the agent."
    )

class TaskRequest(BaseModel):
    session_id: str
    message: Message
    metadata: dict = {}

class TaskStatusUpdate(BaseModel):
    task_id: str
    status: TaskStatus
    message: Optional[Message] = None
    artifact: Optional[Artifact] = None
    confidence: float = 1.0
    final: bool = False