from fastapi import FastAPI, HTTPException
import logging
from pydantic import BaseModel
from typing import Dict, Any, List, Optional, cast
from simulation import Simulation
from data import Forum, Thread, ThreadCategory, User, Post, Date
from datetime import datetime
from dataclasses import asdict
from fastapi.middleware.cors import CORSMiddleware
import json
from pathlib import Path

# Directory to persist simulation state
STORAGE_DIR = Path(__file__).parent / "simulations"
STORAGE_DIR.mkdir(exist_ok=True)

app = FastAPI(title="ForBot Simulation Server")

LOG_FILE = "forbot.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ],
)

logger = logging.getLogger("forbot")

app.add_middleware(
    CORSMiddleware,
    # Allow the local Vite dev servers (common ports 5173 and 5174)
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

simulations: Dict[int, Simulation] = {}
next_sim_id = 1


def sim_filepath(sim_id: int) -> Path:
    return STORAGE_DIR / f"sim_{sim_id}.json"


def sim_to_dict(sim: Simulation) -> Dict[str, Any]:
    # serialize forum
    data = {
        "forum": serialize_forum(sim.forum),
        "model": getattr(sim, "model", None),
        "time": getattr(sim, "_time", 0),
        "users": [],
        "threads": [],
        "posts": [],
    }

    for u in sim.users:
        data["users"].append({
            "id": u.id,
            "username": u.username,
            "signature": u.signature,
            "personality": u.personality,
            "forum_dedication": u.forum_dedication,
            "active_hours": serialize_active_hours(u.active_hours),
        })

    for t in sim.threads:
        data["threads"].append({
            "id": t.id,
            "title": t.title,
            "author_id": t.author.id,
            "category": None,
            "created_date": serialize_date(getattr(t, "created_date", None)),
        })

    for p in sim.posts:
        data["posts"].append({
            "id": p.id,
            "thread_id": p.thread.id,
            "author_id": p.author.id,
            "content": p.content,
            "reply_to": [r.id for r in p.reply_to] if p.reply_to else [],
            "created_date": serialize_date(getattr(p, "created_date", None)),
        })

    return data


def serialize_forum(f: Forum) -> Dict[str, Any]:
    return {"name": f.name, "purpose": f.purpose, "topic": f.topic, "created_date": serialize_date(getattr(f, "created_date", None))}


def serialize_user(u: User) -> Dict[str, Any]:
    return asdict(u)


def serialize_thread(t: Thread) -> Dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "author": t.author.id,
        "category": t.category.id if t.category else None,
        "created_date": serialize_date(getattr(t, "created_date", None)),
    }


def serialize_post(p: Post) -> Dict[str, Any]:
    return {
        "id": p.id,
        "thread_id": p.thread.id,
        "author": p.author.id,
        "content": p.content,
        "reply_to": [r.id for r in p.reply_to] if p.reply_to else [],
        "created_date": serialize_date(getattr(p, "created_date", None)),
    }


def serialize_active_hours(r: range):
    try:
        return [r.start, r.stop]
    except Exception:
        return []


def serialize_date(d: Optional[Date]) -> Optional[str]:
    """Return an ISO string for a Date or None."""
    try:
        if d is None:
            return None
        return d.date.isoformat()
    except Exception:
        return None


def parse_date(iso_str: Optional[str]) -> Optional[Date]:
    """Parse an ISO date string into a Date object, or return None on failure."""
    try:
        if iso_str is None:
            return None
        dt = datetime.fromisoformat(str(iso_str))
        return Date(date=dt, hour=dt.hour)
    except Exception:
        return None


def serialize_user_full(u: User) -> Dict[str, Any]:
    return {
        "id": u.id,
        "username": u.username,
        "signature": u.signature,
        "personality": u.personality,
        "forum_dedication": u.forum_dedication,
        "active_hours": serialize_active_hours(u.active_hours),
    }



def save_simulation(sim_id: int):
    sim = simulations.get(sim_id)
    if sim is None:
        logger.warning(f"No simulation {sim_id} to save")
        return
    try:
        fp = sim_filepath(sim_id)
        with fp.open("w", encoding="utf-8") as f:
            json.dump(sim_to_dict(sim), f, indent=2)
        logger.info(f"Saved simulation {sim_id} to {fp}")
    except Exception as e:
        logger.exception(f"Failed to save simulation {sim_id}: {e}")


def load_simulation_from_dict(sim_id: int, data: Dict[str, Any]) -> Simulation:
    forum_data = data.get("forum", {})
    # parse created_date if present
    forum_created = parse_date(forum_data.get("created_date"))
    if forum_created is not None:
        forum = Forum(forum_data.get("name", ""), forum_data.get("purpose", ""), forum_data.get("topic", ""), created_date=forum_created)
    else:
        forum = Forum(forum_data.get("name", ""), forum_data.get("purpose", ""), forum_data.get("topic", ""))
    sim = Simulation(forum)
    # restore metadata
    # restore model if present
    if "model" in data and data.get("model") is not None:
        try:
            sim.model = str(data.get("model"))
        except Exception:
            pass
    try:
        sim._time = int(data.get("time", 0))
    except Exception:
        sim._time = 0

    # users
    users_by_id: Dict[int, User] = {}
    for u in data.get("users", []):
        ah = u.get("active_hours")
        if isinstance(ah, list) and len(ah) >= 2:
            try:
                active_hours = range(int(ah[0]), int(ah[1]))
            except Exception:
                active_hours = range(0, 24)
        else:
            active_hours = range(0, 24)
        user = User(id=int(u.get("id")), username=u.get("username", ""), signature=u.get("signature", ""), personality=u.get("personality", ""), forum_dedication=float(u.get("forum_dedication", 0.5)), active_hours=active_hours)
        sim.users.append(user)
        users_by_id[user.id] = user

    # threads
    threads_by_id: Dict[int, Thread] = {}
    for t in data.get("threads", []):
        auth_id = t.get("author_id")
        if auth_id is None or int(auth_id) not in users_by_id:
            # skip threads whose author is missing
            continue
        author = users_by_id[int(auth_id)]
        # parse created_date for thread if present
        thread_created = parse_date(t.get("created_date"))
        if thread_created is not None:
            thread = Thread(id=int(t.get("id")), title=t.get("title", ""), author=author, category=cast(ThreadCategory, None), created_date=thread_created)
        else:
            thread = Thread(id=int(t.get("id")), title=t.get("title", ""), author=author, category=cast(ThreadCategory, None))
        sim.threads.append(thread)
        threads_by_id[thread.id] = thread

    # posts (first pass)
    posts_by_id: Dict[int, Post] = {}
    for p in data.get("posts", []):
        tid = p.get("thread_id")
        aid = p.get("author_id")
        if tid is None or aid is None:
            continue
        if int(tid) not in threads_by_id or int(aid) not in users_by_id:
            # skip posts with missing thread or author
            continue
        thread = threads_by_id[int(tid)]
        author = users_by_id[int(aid)]
        # parse created_date for post if present
        post_created = parse_date(p.get("created_date"))
        if post_created is not None:
            post = Post(id=int(p.get("id")), thread=thread, author=author, content=p.get("content", ""), reply_to=[], created_date=post_created)
        else:
            post = Post(id=int(p.get("id")), thread=thread, author=author, content=p.get("content", ""), reply_to=[])
        sim.posts.append(post)
        posts_by_id[post.id] = post

    # resolve reply_to
    for p in data.get("posts", []):
        pid = int(p.get("id"))
        post = posts_by_id.get(pid)
        if post is None:
            continue
        reply_ids = p.get("reply_to") or []
        resolved: List[Post] = []
        for rid in reply_ids:
            try:
                rid_int = int(rid)
            except Exception:
                continue
            if rid_int in posts_by_id:
                resolved.append(posts_by_id[rid_int])
        post.reply_to = resolved

    return sim


def load_all_simulations():
    global next_sim_id
    sims = {}
    max_id = 0
    for fp in STORAGE_DIR.glob("sim_*.json"):
        try:
            sim_id_str = fp.stem.split("_")[-1]
            sim_id = int(sim_id_str)
            with fp.open("r", encoding="utf-8") as f:
                data = json.load(f)
            sim = load_simulation_from_dict(sim_id, data)
            sims[sim_id] = sim
            if sim_id > max_id:
                max_id = sim_id
            logger.info(f"Loaded simulation {sim_id} from {fp}")
        except Exception as e:
            logger.exception(f"Failed to load simulation from {fp}: {e}")
    if sims:
        simulations.update(sims)
        next_sim_id = max_id + 1


# load persisted simulations at startup
load_all_simulations()


class CreateSimulationResponse(BaseModel):
    id: int


class CreateSimulationRequest(BaseModel):
    name: Optional[str] = None
    purpose: Optional[str] = None
    topic: Optional[str] = None
    created_date: Optional[str] = None


class GenerateUsersRequest(BaseModel):
    num_users: int


class AdvanceRequest(BaseModel):
    hours: int


class UpdateForumRequest(BaseModel):
    name: Optional[str] = None
    purpose: Optional[str] = None
    topic: Optional[str] = None
    created_date: Optional[str] = None


@app.post("/simulations", response_model=CreateSimulationResponse)
def create_simulation(body: CreateSimulationRequest):
    """Create a new simulation. Optionally provide forum name, purpose, and topic to override defaults."""
    global next_sim_id
    
    name = body.name if body.name is not None else "Default Forum Name"
    purpose = body.purpose if body.purpose is not None else "Default Forum Purpose"
    topic = body.topic if body.topic is not None else "Default Forum Topic"
    
    # if a created_date was provided, try to parse and set it on the forum
    if body.created_date:
        cd = parse_date(body.created_date)
        if cd is not None:
            forum = Forum(name, purpose, topic, created_date=cd)
        else:
            forum = Forum(name, purpose, topic)
    else:
        forum = Forum(name, purpose, topic)

    sim = Simulation(forum)

    sim_id = next_sim_id
    simulations[sim_id] = sim
    next_sim_id += 1

    logger.info(f"Created simulation {sim_id} with forum: {sim.forum}")

    # persist new simulation
    try:
        save_simulation(sim_id)
    except Exception:
        logger.exception(f"Failed to persist simulation {sim_id} after creation")

    return CreateSimulationResponse(id=sim_id)


@app.get("/simulations")
def list_simulations() -> List[Dict[str, Any]]:
    return [{"id": sid, "users": len(sim.users), "threads": len(sim.threads), "posts": len(sim.posts)} for sid, sim in simulations.items()]


def get_sim_or_404(sim_id: int) -> Simulation:
    sim = simulations.get(sim_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim


@app.post("/simulations/{sim_id}/generate_users")
def api_generate_users(sim_id: int, body: GenerateUsersRequest):
    sim = get_sim_or_404(sim_id)
    # mark simulation as generating so clients can poll status
    try:
        setattr(sim, "_is_generating", True)
    except Exception:
        pass
    try:
        sim.generate_users(body.num_users)
        # persist updated simulation
        save_simulation(sim_id)
        return {"status": "ok", "generated": body.num_users}
    finally:
        try:
            setattr(sim, "_is_generating", False)
        except Exception:
            pass


@app.post("/simulations/{sim_id}/advance")
def api_advance(sim_id: int, body: AdvanceRequest):
    sim = get_sim_or_404(sim_id)
    # mark simulation as advancing so clients can poll status
    try:
        setattr(sim, "_is_advancing", True)
    except Exception:
        pass
    try:
        sim.advance_time(body.hours)
        # persist updated simulation
        save_simulation(sim_id)
        return {"status": "ok", "advanced_hours": body.hours}
    finally:
        try:
            setattr(sim, "_is_advancing", False)
        except Exception:
            pass


@app.get("/simulations/{sim_id}")
def get_simulation_summary(sim_id: int):
    sim = get_sim_or_404(sim_id)
    return {"id": sim_id, "users": len(sim.users), "threads": len(sim.threads), "posts": len(sim.posts)}


@app.get("/simulations/{sim_id}/forum")
def get_sim_forum(sim_id: int):
    sim = get_sim_or_404(sim_id)
    return serialize_forum(sim.forum)


@app.get("/simulations/{sim_id}/status")
def get_sim_status(sim_id: int):
    """Return whether the simulation is currently generating users or advancing time."""
    sim = get_sim_or_404(sim_id)
    is_generating = bool(getattr(sim, "_is_generating", False))
    is_advancing = bool(getattr(sim, "_is_advancing", False))
    # attempt to compute current simulated datetime from forum.created_date + sim._time
    current_time_iso = None
    try:
        base = getattr(sim.forum, "created_date", None)
        if base is not None and hasattr(base, "add_hours"):
            ct = base.add_hours(getattr(sim, "_time", 0))
            current_time_iso = serialize_date(ct)
    except Exception:
        current_time_iso = None

    return {"generating": is_generating, "advancing": is_advancing, "current_time": current_time_iso}


@app.patch("/simulations/{sim_id}/forum")
def update_sim_forum(sim_id: int, body: UpdateForumRequest):
    """Partially update forum metadata for a simulation."""
    sim = get_sim_or_404(sim_id)
    updated = False
    if body.name is not None:
        sim.forum.name = body.name
        updated = True
    if body.purpose is not None:
        sim.forum.purpose = body.purpose
        updated = True
    if body.topic is not None:
        sim.forum.topic = body.topic
        updated = True
    if hasattr(body, "created_date") and body.created_date is not None:
        cd = parse_date(body.created_date)
        if cd is not None:
            sim.forum.created_date = cd
            updated = True

    if updated:
        logger.info(f"Updated forum for simulation {sim_id}: {sim.forum}")
        save_simulation(sim_id)

    return serialize_forum(sim.forum)


@app.get("/simulations/{sim_id}/users")
def get_sim_users(sim_id: int):
    sim = get_sim_or_404(sim_id)
    return [serialize_user_full(u) for u in sim.users]


@app.post("/simulations/{sim_id}/users")
def create_user_manual(sim_id: int, body: Dict[str, Any]):
    """Create a user manually by specifying all fields in the request body.
    Expected fields: username, signature, personality, forum_dedication (float), active_hours: [start, stop]
    """
    sim = get_sim_or_404(sim_id)
    uid = (max([u.id for u in sim.users]) + 1) if sim.users else 1
    username = body.get("username", f"user{uid}")
    signature = body.get("signature", "")
    personality = body.get("personality", "")
    forum_dedication = float(body.get("forum_dedication", 0.5))
    ah = body.get("active_hours")
    if isinstance(ah, list) and len(ah) >= 2:
        try:
            start = int(ah[0])
            stop = int(ah[1])
            active_hours = range(start, stop)
        except Exception:
            active_hours = range(0, 24)
    else:
        active_hours = range(0, 24)

    user = User(id=uid, username=username, signature=signature, personality=personality, forum_dedication=forum_dedication, active_hours=active_hours)
    sim.users.append(user)
    logger.info(f"Manually created user {user.username} (id={user.id}) in sim {sim_id}")
    save_simulation(sim_id)
    return serialize_user_full(user)


@app.patch("/simulations/{sim_id}/users/{user_id}")
def update_user_manual(sim_id: int, user_id: int, body: Dict[str, Any]):
    sim = get_sim_or_404(sim_id)
    user = next((u for u in sim.users if u.id == user_id), None)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if "username" in body:
        user.username = body["username"]
    if "signature" in body:
        user.signature = body["signature"]
    if "personality" in body:
        user.personality = body["personality"]
    if "forum_dedication" in body:
        try:
            user.forum_dedication = float(body["forum_dedication"])
        except Exception:
            pass
    if "active_hours" in body:
        ah = body["active_hours"]
        if isinstance(ah, list) and len(ah) >= 2:
            try:
                user.active_hours = range(int(ah[0]), int(ah[1]))
            except Exception:
                pass
    logger.info(f"Updated user {user.id} in sim {sim_id}")
    save_simulation(sim_id)
    return serialize_user_full(user)


@app.delete("/simulations/{sim_id}/users/{user_id}")
def delete_user(sim_id: int, user_id: int):
    sim = get_sim_or_404(sim_id)
    user = next((u for u in sim.users if u.id == user_id), None)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    # remove user's posts and threads
    sim.posts = [p for p in sim.posts if p.author != user]
    sim.threads = [t for t in sim.threads if t.author != user]
    sim.users = [u for u in sim.users if u != user]
    logger.info(f"Deleted user {user_id} from sim {sim_id}")
    save_simulation(sim_id)
    return {"status": "ok"}


@app.get("/simulations/{sim_id}/threads")
def get_sim_threads(sim_id: int):
    sim = get_sim_or_404(sim_id)
    return [serialize_thread(t) for t in sim.threads]


@app.get("/simulations/{sim_id}/posts")
def get_sim_posts(sim_id: int):
    sim = get_sim_or_404(sim_id)
    return [serialize_post(p) for p in sim.posts]


@app.get("/simulations/{sim_id}/posts/{post_id}")
def get_sim_post(sim_id: int, post_id: int):
    sim = get_sim_or_404(sim_id)
    for p in sim.posts:
        if p.id == post_id:
            return serialize_post(p)
    raise HTTPException(status_code=404, detail="Post not found")
