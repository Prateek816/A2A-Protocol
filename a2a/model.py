from pydantic import BaseModel , JsonValue , Field
from typing import Any , Optional , Literal
from datetime import datetime, timezone
import uuid

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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata : dict[str,Any]

class Artifact(BaseModel):
    name:Optional[str]
    description:Optional[str]
    parts:list[Part]
    metadata:Optional[dict[str,Any]]
    index: int = Field(description="Index of the artifact within its owning task")
    append : Optional[bool]
    lastChunk:Optional[bool]

