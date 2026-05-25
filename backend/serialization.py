from typing import Dict, Any, Optional, List
from data import *
from dataclasses import asdict as dataclass_asdict
from datetime import datetime
from io import BytesIO
import base64
from PIL import Image


def serialize_profile_picture_b64(img: Optional[Image.Image]) -> Optional[str]:
    if img is None:
        return None
    
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def deserialize_profile_picture_b64(data: Optional[str]) -> Optional[Image.Image]:
    if not data:
        return None
    
    raw = base64.b64decode(data)
    img = Image.open(BytesIO(raw))
    img.load()
    
    return img


def parse_date(iso_str: Optional[str]) -> Optional[Date]:
    if iso_str is None:
        return None
    dt = datetime.fromisoformat(str(iso_str))
    return Date(date=dt, hour=dt.hour)


def serialize_user_full(u: User) -> Dict[str, Any]:
    return {
        "id": u.id,
        "username": u.username,
        "profile_picture": serialize_profile_picture_b64(u.profile_picture),
        "signature": u.signature,
        "personality": u.personality,
        "voice_profile": u.voice_profile,
        "forum_dedication": u.forum_dedication,
        "active_hours": u.active_hours,
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
        data["threads"].append(dataclass_asdict(t))

    for p in sim.posts:
        data["posts"].append(dataclass_asdict(p))

    if sim.model_config is not None:
        data["model_config"] = dataclass_asdict(sim.model_config)

    return data


def serialize_model_config(sim) -> Optional[Dict[str, Any]]:
    if sim.model_config is None:
        return None
    return dataclass_asdict(sim.model_config)