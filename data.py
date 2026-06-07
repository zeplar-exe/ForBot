from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import uuid


type UserId = str
type ThreadId = str
type PostId = str
type StimulusId = str
type DocumentId = str


@dataclass
class AIConfig:
    model: str = "ollama/qwen2.5-abliterated-q4"
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    thinking: str = "medium"  # one of: low, medium, high


@dataclass
class SimulationDocument:
    title: str
    text: str
    source: str = ""
    summary: str = ""
    id: DocumentId = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class ForumDocumentReference:
    id: DocumentId
    title: str
    summary: str
    source: str = ""


@dataclass
class Forum:
    name: str
    topic: str
    created_date: datetime = field(default_factory=datetime.now)
    topic_summary: str = "Empty Summary"
    documents: List[ForumDocumentReference] = field(default_factory=list)


@dataclass
class ViewedPost:
    post_id: PostId
    view_date: int
    summary: Optional[str] = None


@dataclass
class UserSummary:
    user_id: UserId
    update_tick: int
    last_updated: int
    summary: str


@dataclass
class User:
    username: str
    profile_picture: str
    signature: str
    personality: str
    forum_dedication: float
    active_hours: list[int]
    voice_profile: str
    viewed_posts: dict[PostId, ViewedPost] = field(default_factory=dict)
    user_summaries: dict[UserId, UserSummary] = field(default_factory=dict)
    id: UserId = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Thread:
    title: str
    author: User
    created_tick: int = 0
    summary: Optional[str] = None
    id: ThreadId = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Post:
    thread: Thread
    author: User
    content: str
    reply_to: str = ""
    created_tick: int = 0
    id: PostId = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Stimulus:
    text: str
    created_tick: int = 0
    id: StimulusId = field(default_factory=lambda: str(uuid.uuid4()))
