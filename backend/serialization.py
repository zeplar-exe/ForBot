from typing import Dict, Any, Optional
from data import *
from dataclasses import asdict as dataclass_asdict
from datetime import datetime
import json


class SimulationEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def serialize_user_full(u: User) -> Dict[str, Any]:
    return {
        "id": u.id,
        "username": u.username,
        "profile_picture": u.profile_picture,
        "signature": u.signature,
        "personality": u.personality,
        "voice_profile": u.voice_profile,
        "forum_dedication": u.forum_dedication,
        "active_hours": u.active_hours,
    }


def serialize_thread(t) -> Dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "author_id": t.author.id,
        "created_tick": t.created_tick,
        "summary": t.summary,
    }


def serialize_post(p) -> Dict[str, Any]:
    return {
        "id": p.id,
        "thread_id": p.thread.id,
        "author_id": p.author.id,
        "content": p.content,
        "reply_to": p.reply_to,
        "created_tick": p.created_tick,
    }


def serialize_document(d) -> Dict[str, Any]:
    return {
        "id": d.id,
        "title": d.title,
        "text": d.text,
        "source": d.source,
        "summary": d.summary,
    }


def serialize_stimulus(s) -> Dict[str, Any]:
    return {
        "id": s.id,
        "text": s.text,
        "created_tick": s.created_tick,
    }


def serialize_model_config(sim) -> Optional[Dict[str, Any]]:
    if sim.model_config is None:
        return None
    return dataclass_asdict(sim.model_config)


def sim_to_dict(sim) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "forum": {
            "name": sim.forum.name,
            "topic": sim.forum.topic,
            "topic_summary": sim.forum.topic_summary,
            "created_date": sim.forum.created_date.isoformat(),
            "documents": [serialize_document(d) for d in sim.forum.documents],
        },
        "model_config": None,
        "time": sim._time,
        "thread_creation_chance": sim.thread_creation_chance,
        "users": [],
        "threads": [],
        "posts": [],
        "stimuli": [],
        "documents": [],
    }

    for u in sim.users:
        data["users"].append(serialize_user_full(u))

    for t in sim.threads:
        data["threads"].append(serialize_thread(t))

    for p in sim.posts:
        data["posts"].append(serialize_post(p))

    for s in sim.stimuli:
        data["stimuli"].append(serialize_stimulus(s))

    for d in sim.documents.values():
        data["documents"].append(serialize_document(d))

    if sim.model_config is not None:
        data["model_config"] = serialize_model_config(sim)

    return data
