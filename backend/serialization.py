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


def parse_date(iso_str) -> Optional[Date]:
    if iso_str is None:
        return None
    if isinstance(iso_str, dict):
        dt = datetime.fromisoformat(str(iso_str["date"]))
        return Date(date=dt, hour=int(iso_str.get("hour", dt.hour)))
    dt = datetime.fromisoformat(str(iso_str))
    return Date(date=dt, hour=dt.hour)


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


def date_to_iso(d) -> str:
    return d.date.isoformat()


def serialize_thread(t) -> Dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "author_id": t.author.id,
        "category": dataclass_asdict(t.category) if t.category else None,
        "created_date": date_to_iso(t.created_date),
    }


def serialize_post(p) -> Dict[str, Any]:
    return {
        "id": p.id,
        "thread_id": p.thread.id,
        "author_id": p.author.id,
        "content": p.content,
        "reply_to": p.reply_to,
        "created_date": date_to_iso(p.created_date),
    }


def sim_to_dict(sim) -> Dict[str, Any]:
    data = {
        "forum": dataclass_asdict(sim.forum),
        "model_config": None,
        "time": sim._time,
        "thread_creation_chance": sim.thread_creation_chance,
        "users": [],
        "threads": [],
        "posts": [],
    }

    for u in sim.users:
        data["users"].append(dataclass_asdict(u))

    for t in sim.threads:
        data["threads"].append(serialize_thread(t))

    for p in sim.posts:
        data["posts"].append(serialize_post(p))

    if sim.model_config is not None:
        data["model_config"] = dataclass_asdict(sim.model_config)

    return data


def serialize_model_config(sim) -> Optional[Dict[str, Any]]:
    if sim.model_config is None:
        return None
    return dataclass_asdict(sim.model_config)
