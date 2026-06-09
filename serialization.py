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


def sim_to_dict(sim, sim_id: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "id": sim_id,
        "forum": {
            "name": sim.forum.name,
            "topic": sim.forum.topic,
            "topic_summary": sim.forum.topic_summary,
            "created_date": sim.forum.created_date.isoformat(),
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
        data["users"].append(dataclass_asdict(u))

    for t in sim.threads:
        data["threads"].append(dataclass_asdict(t))

    for p in sim.posts:
        data["posts"].append(dataclass_asdict(p))

    for s in sim.stimuli:
        data["stimuli"].append(dataclass_asdict(s))

    for d in sim.documents.values():
        data["documents"].append(dataclass_asdict(d))

    if sim.model_config is not None:
        data["model_config"] = dataclass_asdict(sim.model_config)

    return data
