from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List


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
    id: int
    name: str
    description: str


@dataclass
class User:
    id: int
    username: str
    signature: str
    personality: str
    forum_dedication: float
    active_hours: range

    def get_prompt(self, forum: Forum) -> str:
        return f"Your online username is {self.username}. {self.personality}. You partcipate in the forum '{forum.name}', which is about {forum.topic}. This forum has a stated purpose: '{forum.purpose}'."


@dataclass
class UserRelationship:
    user1: User
    user2: User
    friendship_level: float
    relations: str


@dataclass
class Thread:
    id: int
    title: str
    author: User
    category: ThreadCategory
    created_date: Date = field(default_factory=lambda: Date(datetime.now(), 0))


@dataclass
class Post:
    id: int
    thread: Thread
    author: User
    content: str
    reply_to: List['Post']
    created_date: Date = field(default_factory=lambda: Date(datetime.now(), 0))