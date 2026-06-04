from fastapi import FastAPI, HTTPException
import logging
from pydantic import BaseModel
from typing import Dict, Any, List, Optional, cast
from datetime import datetime, timedelta
from generate_det import generate_profile_picture
from simulation import Simulation
from data import *
from serialization import (
    sim_to_dict,
    serialize_user_full,
    serialize_model_config,
    serialize_thread,
    serialize_post,
    serialize_stimulus,
    serialize_document,
    SimulationEncoder,
)
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import dspy
from pathlib import Path
import mlflow
import ollama
from dataclasses import asdict as dataclass_asdict
from dotenv import load_dotenv

load_dotenv()

STORAGE_DIR = Path(__file__).parent / "simulations"
STORAGE_DIR.mkdir(exist_ok=True)
BACKUP_DIR = Path(__file__).parent / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

LOG_FILE = "forbot.log"
OLLAMA_API_BASE = "http://157.157.221.177:10902"

app = FastAPI(title="ForBot Simulation Server")

lm = dspy.LM("ollama/qwen2.5-abliterated-q4", api_base=OLLAMA_API_BASE, temperature=0.7)
dspy.configure(lm=lm, adapter=dspy.JSONAdapter())
dspy.enable_logging()


mlflow.set_tracking_uri("http://127.0.0.1:5001")
mlflow.autolog()
mlflow.set_experiment("ForBot")

os.environ["OLLAMA_NUM_PARALLEL"] = "4"

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
simulations_running = set()
simulations_generating = set()
simulations_advancing = set()
next_sim_id = 1


class SummarizeForumPrompt(dspy.Signature):
    """
    Generate a summary of the 'document'.
    Use complete sentences and do not be brief.
    Include information relevant to user discussion.
    Do not include any extra headings or commentary.
    """
    document: str = dspy.InputField()
    summary: str = dspy.OutputField()


def sim_filepath(sim_id: int) -> Path:
    return STORAGE_DIR / f"sim_{sim_id}.json"


def get_installed_ollama_models() -> List[str]:
    try:
        return [m.model for m in ollama.list()["models"]]
    except Exception:
        return []


CLOUD_MODELS = [
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/o1",
    "openai/o3-mini",
    "anthropic/claude-opus-4-7",
    "anthropic/claude-sonnet-4-6",
    "anthropic/claude-haiku-4-5",
]


def build_lm(cfg: AIConfig) -> dspy.LM:
    is_anthropic = cfg.model.startswith("anthropic/")

    kwargs: dict = {"temperature": cfg.temperature}
    if not is_anthropic:
        kwargs["top_p"] = cfg.top_p
    if is_anthropic and cfg.top_k > 0:
        kwargs["top_k"] = cfg.top_k
    if cfg.frequency_penalty != 0.0:
        kwargs["frequency_penalty"] = cfg.frequency_penalty
    if cfg.presence_penalty != 0.0:
        kwargs["presence_penalty"] = cfg.presence_penalty

    if cfg.model.startswith("ollama"):
        built = dspy.LM(cfg.model, api_base=OLLAMA_API_BASE, api_key="", **kwargs)
    elif is_anthropic:
        built = dspy.LM(cfg.model, api_key=os.getenv("CLAUDE_API_KEY", ""), **kwargs)
    else:
        built = dspy.LM(cfg.model, **kwargs)

    logger.info(f"Built LM: {cfg.model}")
    return built


class AISettingsRequest(BaseModel):
    model: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    whitelist: Optional[List[str]] = None
    thinking: Optional[str] = None
    thread_creation_chance: Optional[float] = None


@app.get("/models")
def api_list_models():
    ollama_models = get_installed_ollama_models()
    return {"models": CLOUD_MODELS + ollama_models}


@app.get("/simulations/{sim_id}/ai_settings")
def api_get_ai_settings(sim_id: int):
    sim = get_sim_or_404(sim_id)
    cfg = dataclass_asdict(sim.model_config)
    cfg["thread_creation_chance"] = sim.thread_creation_chance
    return cfg


@app.patch("/simulations/{sim_id}/ai_settings")
def api_update_ai_settings(sim_id: int, body: AISettingsRequest):
    sim = get_sim_or_404(sim_id)
    cfg = sim.model_config

    if body.model is not None:
        cfg.model = body.model
    if body.temperature is not None:
        cfg.temperature = body.temperature
    if body.top_p is not None:
        cfg.top_p = body.top_p
    if body.top_k is not None:
        cfg.top_k = body.top_k
    if body.frequency_penalty is not None:
        cfg.frequency_penalty = body.frequency_penalty
    if body.presence_penalty is not None:
        cfg.presence_penalty = body.presence_penalty
    if body.whitelist is not None:
        cfg.whitelist = [x.strip() for x in body.whitelist if x.strip()]
    if body.thinking is not None:
        if body.thinking in ("low", "medium", "high"):
            cfg.thinking = body.thinking
    if body.thread_creation_chance is not None:
        sim.thread_creation_chance = body.thread_creation_chance

    sim._lm = build_lm(cfg)
    save_simulation(sim_id)

    result = dataclass_asdict(cfg)
    result["thread_creation_chance"] = sim.thread_creation_chance
    return result


def save_simulation(sim_id: int):
    sim = simulations.get(sim_id)
    if sim is None:
        logger.warning(f"No simulation {sim_id} to save")
        return
    try:
        fp = sim_filepath(sim_id)
        if fp.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_fp = BACKUP_DIR / f"sim_{sim_id}_{ts}.json"
            backup_fp.write_bytes(fp.read_bytes())
            existing = sorted(BACKUP_DIR.glob(f"sim_{sim_id}_*.json"))
            for old in existing[:-15]:
                old.unlink()
        with fp.open("w", encoding="utf-8") as f:
            json.dump(sim_to_dict(sim), f, indent=2, cls=SimulationEncoder)
        logger.info(f"Saved simulation {sim_id} to {fp}")
    except Exception as e:
        logger.exception(f"Failed to save simulation {sim_id}: {e}")


def load_simulation_from_dict(sim_id: int, data: Dict[str, Any]) -> Simulation:
    forum_data = data.get("forum", {})
    topic_summary = forum_data.get("topic_summary")

    raw_created = forum_data.get("created_date")
    if isinstance(raw_created, dict):
        # old format: {"date": "2025-01-01T00:00:00", "hour": N}
        forum_created = datetime.fromisoformat(str(raw_created["date"]))
    elif raw_created:
        forum_created = datetime.fromisoformat(str(raw_created))
    else:
        forum_created = datetime.now()

    forum = Forum(
        name=forum_data.get("name", ""),
        topic=forum_data.get("topic", ""),
        created_date=forum_created,
        topic_summary=topic_summary or "Empty Summary",
    )

    sim = Simulation(forum)

    try:
        sim._time = int(data.get("time", 0))
    except Exception as e:
        logger.exception(f"Failed to parse simulation time: [{sim_id}] {e}")
        sim._time = 0

    mc = data.get("model_config")
    if isinstance(mc, dict):
        sim.model_config = AIConfig(
            model=str(mc.get("model", "openai/gpt-4o-mini")),
            temperature=float(mc.get("temperature", 0.7)),
            top_p=float(mc.get("top_p", 0.9)),
            top_k=int(mc.get("top_k", 40)),
            frequency_penalty=float(mc.get("frequency_penalty", 0.0)),
            presence_penalty=float(mc.get("presence_penalty", 0.0)),
            whitelist=list(mc.get("whitelist", [])),
            thinking=str(mc.get("thinking", "medium")),
        )

    sim.thread_creation_chance = float(data.get("thread_creation_chance", 0.25))

    users_by_id: Dict[str, User] = {}

    for u in data.get("users", []):
        ah = u.get("active_hours")

        if isinstance(ah, list) and len(ah) >= 2:
            active_hours = [int(ah[0]), int(ah[1])]
        else:
            active_hours = [0, 24]

        profile_picture = u.get("profile_picture") or generate_profile_picture()

        user = User(
            username=u.get("username", ""),
            profile_picture=profile_picture,
            signature=u.get("signature", ""),
            personality=u.get("personality", ""),
            forum_dedication=float(u.get("forum_dedication", 0.5)),
            active_hours=active_hours,
            voice_profile=u.get("voice_profile", ""),
            id=str(u.get("id")),
        )
        sim.users.append(user)
        users_by_id[user.id] = user

    threads_by_id: Dict[str, Thread] = {}

    for t in data.get("threads", []):
        auth_id = t.get("author_id")

        if auth_id is None or str(auth_id) not in users_by_id:
            continue

        author = users_by_id[str(auth_id)]
        thread = Thread(
            title=t.get("title", ""),
            author=author,
            category=cast(ThreadCategory, None),
            created_tick=int(t.get("created_tick", 0)),
            summary=t.get("summary", None),
            id=str(t.get("id")),
        )

        sim.threads.append(thread)
        threads_by_id[thread.id] = thread

    posts_by_id: Dict[str, Post] = {}

    for p in data.get("posts", []):
        tid = p.get("thread_id")
        aid = p.get("author_id")

        if tid is None or aid is None:
            continue

        if str(tid) not in threads_by_id or str(aid) not in users_by_id:
            continue

        thread = threads_by_id[str(tid)]
        author = users_by_id[str(aid)]
        post = Post(
            thread=thread,
            author=author,
            content=p.get("content", ""),
            reply_to=p.get("reply_to", []),
            created_tick=int(p.get("created_tick", 0)),
            id=str(p.get("id")),
        )

        sim.posts.append(post)
        posts_by_id[post.id] = post

    for s in data.get("stimuli", []):
        stimulus = Stimulus(
            text=s.get("text", ""),
            created_tick=int(s.get("created_tick", 0)),
            id=str(s.get("id")),
        )
        sim.stimuli.append(stimulus)

    for d in data.get("documents", []):
        doc = SimulationDocument(
            title=d.get("title", ""),
            text=d.get("text", ""),
            source=d.get("source", ""),
            summary=d.get("summary", ""),
            id=str(d.get("id")),
        )
        sim.documents[doc.id] = doc
        # Rebuild forum document references from the document store
        sim.forum.documents = [
            ForumDocumentReference(
                id=doc.id,
                title=doc.title,
                summary=doc.summary,
                source=doc.source,
            )
            for doc in sim.documents.values()
        ]

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


load_all_simulations()


class CreateSimulationResponse(BaseModel):
    id: int


class CreateSimulationRequest(BaseModel):
    name: Optional[str] = None
    topic: Optional[str] = None
    created_date: Optional[str] = None


class GenerateUsersRequest(BaseModel):
    num_users: int


class AdvanceRequest(BaseModel):
    hours: int


class UpdateForumRequest(BaseModel):
    name: Optional[str] = None
    topic: Optional[str] = None
    created_date: Optional[str] = None


class StateRequest(BaseModel):
    running: bool


@app.patch("/simulations/{sim_id}/state")
def api_set_simulation_state(sim_id: int, body: StateRequest):
    sim = get_sim_or_404(sim_id)
    if body.running:
        simulations_running.add(sim_id)
        sim._lm = build_lm(sim.model_config)
    else:
        simulations_running.discard(sim_id)
    save_simulation(sim_id)
    return {"running": body.running}


@app.post("/simulations", response_model=CreateSimulationResponse)
def create_simulation(body: CreateSimulationRequest):
    global next_sim_id
    
    name = body.name if body.name is not None else "Default Forum Name"
    topic = body.topic if body.topic is not None else "Default Forum Topic"
    
    summarize_forum = dspy.ChainOfThought(SummarizeForumPrompt)
    topic_summary = summarize_forum(
        document=topic
    ).summary

    cd: datetime = datetime.now()
    if body.created_date:
        cd = datetime.fromisoformat(body.created_date)

    forum = Forum(name, topic, created_date=cd, topic_summary=topic_summary)

    sim = Simulation(forum)

    sim_id = next_sim_id
    simulations[sim_id] = sim
    next_sim_id += 1

    logger.info(f"Created simulation {sim_id} with forum: {sim.forum}")
    save_simulation(sim_id)
    return CreateSimulationResponse(id=sim_id)


@app.get("/simulations")
def list_simulations() -> List[Dict[str, Any]]:
    out = []
    for sid, sim in simulations.items():
        out.append({
            "id": sid,
            "users": len(sim.users),
            "threads": len(sim.threads),
            "posts": len(sim.posts),
            "running": sid in simulations_running,
        })
    return out


def get_sim_or_404(sim_id: int) -> Simulation:
    sim = simulations.get(sim_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim


def get_sim_or_404_running(sim_id: int, require_running: bool = False) -> Simulation:
    sim = simulations.get(sim_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    if require_running and sim_id not in simulations_running:
        raise HTTPException(status_code=409, detail="Simulation is stopped")
    return sim


@app.post("/simulations/{sim_id}/generate_users")
def api_generate_users(sim_id: int, body: GenerateUsersRequest):
    sim = get_sim_or_404_running(sim_id, require_running=True)
    simulations_generating.add(sim_id)
    try:
        sim.generate_users(body.num_users)
        save_simulation(sim_id)
        return {"status": "ok", "generated": body.num_users}
    finally:
        simulations_generating.discard(sim_id)


@app.post("/simulations/{sim_id}/advance")
def api_advance(sim_id: int, body: AdvanceRequest):
    sim = get_sim_or_404_running(sim_id, require_running=True)
    simulations_advancing.add(sim_id)
    try:
        for _ in range(body.hours):
            new_threads, new_posts = sim.advance_one_hour()
            if new_threads or new_posts:
                save_simulation(sim_id)
        return {"status": "ok", "advanced_hours": body.hours}
    finally:
        simulations_advancing.discard(sim_id)


@app.get("/simulations/{sim_id}")
def get_simulation_summary(sim_id: int):
    sim = get_sim_or_404(sim_id)
    return {"id": sim_id, "users": len(sim.users), "threads": len(sim.threads), "posts": len(sim.posts)}


@app.get("/simulations/{sim_id}/forum")
def get_sim_forum(sim_id: int):
    sim = get_sim_or_404(sim_id)
    f = sim.forum
    return {
        "name": f.name,
        "topic": f.topic,
        "topic_summary": f.topic_summary,
        "created_date": f.created_date.isoformat(),
        "documents": [dataclass_asdict(d) for d in f.documents],
    }


@app.get("/simulations/{sim_id}/status")
def get_sim_status(sim_id: int):
    sim = get_sim_or_404(sim_id)
    is_generating = sim_id in simulations_generating
    is_advancing = sim_id in simulations_advancing
    current_time_iso = (sim.forum.created_date + timedelta(hours=sim._time)).isoformat()
    running = sim_id in simulations_running
    return {"generating": is_generating, "advancing": is_advancing, "current_time": current_time_iso, "running": running}


@app.patch("/simulations/{sim_id}/forum")
def update_sim_forum(sim_id: int, body: UpdateForumRequest):
    sim = get_sim_or_404_running(sim_id, require_running=True)
    updated = False

    if body.name is not None:
        sim.forum.name = body.name
        updated = True
    if body.topic is not None:
        sim.forum.topic = body.topic
        updated = True
    if body.created_date is not None:
        sim.forum.created_date = datetime.fromisoformat(body.created_date)
        updated = True

    if updated:
        logger.info(f"Updated forum for simulation {sim_id}: {sim.forum}")
        save_simulation(sim_id)

    f = sim.forum
    return {
        "name": f.name,
        "topic": f.topic,
        "topic_summary": f.topic_summary,
        "created_date": f.created_date.isoformat(),
        "documents": [dataclass_asdict(d) for d in f.documents],
    }


@app.get("/simulations/{sim_id}/users")
def get_sim_users(sim_id: int):
    sim = get_sim_or_404(sim_id)
    return [dataclass_asdict(u) for u in sim.users]


@app.post("/simulations/{sim_id}/users")
def create_user_manual(sim_id: int, body: Dict[str, Any]):
    """
    Expected fields: username, signature, personality, forum_dedication (float), active_hours: [start, stop]
    """
    sim = get_sim_or_404_running(sim_id, require_running=True)
    username = body.get("username", f"user{len(sim.users) + 1}")
    signature = body.get("signature", "")
    personality = body.get("personality", "")
    forum_dedication = float(body.get("forum_dedication", 0.5))
    activity = body.get("active_hours")

    if isinstance(activity, list) and len(activity) >= 2:
        try:
            start = int(activity[0])
            stop = int(activity[1])
            active_hours = [start, stop]
        except Exception:
            active_hours = [0, 24]
    else:
        active_hours = [0, 24]

    voice_profile = body.get("voice_profile", "")
    user = User(
        username=username, 
        profile_picture=generate_profile_picture(), 
        signature=signature, 
        personality=personality, 
        forum_dedication=forum_dedication,
        active_hours=active_hours, 
        voice_profile=voice_profile)
    sim.users.append(user)
    
    logger.info(f"Manually created user {user.username} (id={user.id}) in sim {sim_id}")
    save_simulation(sim_id)

    return dataclass_asdict(user)


@app.patch("/simulations/{sim_id}/users/{user_id}")
def update_user_manual(sim_id: int, user_id: str, body: Dict[str, Any]):
    sim = get_sim_or_404_running(sim_id, require_running=True)
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
        user.forum_dedication = float(body["forum_dedication"])
    if "active_hours" in body:
        ah = body["active_hours"]
        if isinstance(ah, list) and len(ah) >= 2:
            user.active_hours = [int(ah[0]), int(ah[1])]
    if "voice_profile" in body:
        user.voice_profile = str(body["voice_profile"])
    
    logger.info(f"Updated user {user.id} in sim {sim_id}")
    save_simulation(sim_id)

    return dataclass_asdict(user)


@app.get("/simulations/{sim_id}/threads")
def get_sim_threads(sim_id: int):
    sim = get_sim_or_404(sim_id)
    return [serialize_thread(t) for t in sim.threads]


@app.get("/simulations/{sim_id}/posts")
def get_sim_posts(sim_id: int):
    sim = get_sim_or_404(sim_id)
    return [serialize_post(p) for p in sim.posts]


@app.get("/simulations/{sim_id}/posts/{post_id}")
def get_sim_post(sim_id: int, post_id: str):
    sim = get_sim_or_404(sim_id)
    for p in sim.posts:
        if p.id == post_id:
            return serialize_post(p)
    raise HTTPException(status_code=404, detail="Post not found")


class CreateStimulusRequest(BaseModel):
    text: str


@app.get("/simulations/{sim_id}/stimuli")
def get_sim_stimuli(sim_id: int):
    sim = get_sim_or_404(sim_id)
    return [serialize_stimulus(s) for s in sim.stimuli]


@app.post("/simulations/{sim_id}/stimuli")
def create_stimulus(sim_id: int, body: CreateStimulusRequest):
    sim = get_sim_or_404(sim_id)
    s = Stimulus(text=body.text.strip(), created_tick=sim._time)
    sim.stimuli.append(s)
    save_simulation(sim_id)
    return serialize_stimulus(s)


class CreateDocumentRequest(BaseModel):
    title: str
    text: str
    source: str = ""


@app.get("/simulations/{sim_id}/documents")
def get_sim_documents(sim_id: int):
    sim = get_sim_or_404(sim_id)
    return [serialize_document(d) for d in sim.documents.values()]


@app.post("/simulations/{sim_id}/documents")
def create_document(sim_id: int, body: CreateDocumentRequest):
    sim = get_sim_or_404(sim_id)
    summarize = dspy.ChainOfThought(SummarizeForumPrompt)
    summary = summarize(document=body.text).summary
    doc = SimulationDocument(
        title=body.title,
        text=body.text,
        source=body.source,
        summary=summary,
    )
    sim.documents[doc.id] = doc
    sim.forum.documents.append(ForumDocumentReference(
        id=doc.id,
        title=doc.title,
        summary=doc.summary,
        source=doc.source,
    ))
    save_simulation(sim_id)
    return serialize_document(doc)


@app.delete("/simulations/{sim_id}/documents/{doc_id}")
def delete_document(sim_id: int, doc_id: str):
    sim = get_sim_or_404(sim_id)
    if doc_id not in sim.documents:
        raise HTTPException(status_code=404, detail="Document not found")
    del sim.documents[doc_id]
    sim.forum.documents = [d for d in sim.forum.documents if d.id != doc_id]
    save_simulation(sim_id)
    return {"status": "ok"}


@app.delete("/simulations/{sim_id}/stimuli/{stimulus_id}")
def delete_stimulus(sim_id: int, stimulus_id: str):
    sim = get_sim_or_404(sim_id)
    before = len(sim.stimuli)
    sim.stimuli = [s for s in sim.stimuli if s.id != stimulus_id]
    if len(sim.stimuli) == before:
        raise HTTPException(status_code=404, detail="Stimulus not found")
    save_simulation(sim_id)
    return {"status": "ok"}
