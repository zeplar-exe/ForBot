from typing import Dict, Any
from data import *
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
        data["users"].append({
            "id": u.id,
            "username": u.username,
            "profile_picture": u.profile_picture,
            "signature": u.signature,
            "personality": u.personality,
            "forum_dedication": u.forum_dedication,
            "active_hours": u.active_hours,
            "voice_profile": u.voice_profile,
            "viewed_posts": {
                pid: {
                    "post_id": vp.post_id,
                    "view_date": vp.view_date,
                    "author_username": vp.author_username,
                }
                for pid, vp in u.viewed_posts.items()
            },
            "user_summaries": {
                uid: {
                    "user_id": us.user_id,
                    "update_tick": us.update_tick,
                    "last_updated": us.last_updated,
                    "summarized_user_username": us.summarized_user_username,
                    "summary": us.summary,
                }
                for uid, us in u.user_summaries.items()
            },
        })

    for t in sim.threads:
        data["threads"].append({
            "id": t.id,
            "title": t.title,
            "author_id": t.author.id,
            "created_tick": t.created_tick,
            "summary": t.summary,
        })

    for p in sim.posts:
        data["posts"].append({
            "id": p.id,
            "thread_id": p.thread.id,
            "author_id": p.author.id,
            "content": p.content,
            "reply_to": p.reply_to,
            "created_tick": p.created_tick,
        })

    for s in sim.stimuli:
        data["stimuli"].append({
            "id": s.id,
            "text": s.text,
            "created_tick": s.created_tick,
        })

    for d in sim.documents.values():
        data["documents"].append({
            "id": d.id,
            "title": d.title,
            "text": d.text,
            "source": d.source,
            "summary": d.summary,
        })

    if sim.model_config is not None:
        data["model_config"] = {
            "model": sim.model_config.model,
            "temperature": sim.model_config.temperature,
            "top_p": sim.model_config.top_p,
            "top_k": sim.model_config.top_k,
            "frequency_penalty": sim.model_config.frequency_penalty,
            "presence_penalty": sim.model_config.presence_penalty,
            "thinking": sim.model_config.thinking,
        }

    return data
