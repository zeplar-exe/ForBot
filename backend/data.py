from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
import uuid


@dataclass
class Date:
    date: datetime
    hour: int

    def add_hours(self, hours: int) -> 'Date':
        new_datetime = self.date + timedelta(hours=hours)
        return Date(date=new_datetime, hour=new_datetime.hour)


@dataclass
class Forum:
    name: str
    purpose: str
    topic: str
    created_date: Date = field(default_factory=lambda: Date(datetime.now(), 0))


@dataclass
class ThreadCategory:
    name: str
    description: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class User:
    username: str
    signature: str
    personality: str
    forum_dedication: float
    active_hours: range
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class UserRelationship:
    user1: User
    user2: User
    friendship_level: float
    relations: str


@dataclass
class Thread:
    title: str
    author: User
    category: Optional[ThreadCategory]
    created_date: Date = field(default_factory=lambda: Date(datetime.now(), 0))
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Post:
    thread: Thread
    author: User
    content: str
    reply_to: List['Post']
    created_date: Date = field(default_factory=lambda: Date(datetime.now(), 0))
    id: str = field(default_factory=lambda: str(uuid.uuid4()))