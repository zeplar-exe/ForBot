from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
import uuid
from PIL import Image


type UserId = str
type ThreadId = str
type PostId = str


@dataclass
class AIConfig:
    model: str = "ollama_chat/llama3"
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    max_tokens: int = 2500
    whitelist: List[str] = field(default_factory=list)
    thinking: str = "medium"  # one of: low, medium, high


@dataclass
class Date:
    date: datetime
    hour: int

    def add_hours(self, hours: int) -> 'Date':
        new_datetime = self.date + timedelta(hours=hours)
        return Date(date=new_datetime, hour=new_datetime.hour)


@dataclass
class ForumDocumentReference:
    title: str
    summary: str
    source: str


@dataclass
class Forum:
    name: str
    topic: str
    created_date: Date = field(default_factory=lambda: Date(datetime.now(), 0))
    topic_summary: str = "Empty Summary"
    documents: List[ForumDocumentReference] = field(default_factory=list)


@dataclass
class ThreadCategory:
    name: str
    description: str
    id: ThreadId = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class ViewedPost:
    post_id: PostId
    view_date: Date
    summary: Optional[str] = None


@dataclass
class UserSummary:
    user_id: UserId
    last_updated: Date
    summary: str


@dataclass
class User:
    username: str
    profile_picture: Image.Image
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
    category: Optional[ThreadCategory]
    created_date: Date = field(default_factory=lambda: Date(datetime.now(), 0))
    id: ThreadId = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Post:
    thread: Thread
    author: User
    content: str
    reply_to: List['Post']
    created_date: Date = field(default_factory=lambda: Date(datetime.now(), 0))
    id: PostId = field(default_factory=lambda: str(uuid.uuid4()))