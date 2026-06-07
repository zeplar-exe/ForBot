# The frontend elements of this file were written with Claude Code

from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from generate_det import generate_profile_picture
from simulation import Simulation
from data import *
from serialization import (
    sim_to_dict,
    SimulationEncoder,
)
import json
import os
import secrets
import dspy
from pathlib import Path
import mlflow
import ollama
from dotenv import load_dotenv

load_dotenv()

STORAGE_DIR = Path(__file__).parent / "simulations"
STORAGE_DIR.mkdir(exist_ok=True)
BACKUP_DIR = Path(__file__).parent / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

LOG_FILE = os.getenv("LOG_FILE", "forbot.log")
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")

app = FastAPI(title="ForBot Simulation Server")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

lm = dspy.LM("ollama/qwen2.5-abliterated-q4", api_base=OLLAMA_API_BASE, temperature=0.7,
             stop=["### User:", "### Human:", "\nHuman:", "\nUser:"])
embed = dspy.Embedder("nomic-embed-text", api_base=OLLAMA_API_BASE)
dspy.configure(lm=lm, embedder=embed)
dspy.enable_logging()



mlflow.set_tracking_uri("http://127.0.0.1:5001")
mlflow.autolog()
mlflow.set_experiment("ForBot")

os.environ["OLLAMA_NUM_PARALLEL"] = "4"

logger = logging.getLogger("forbot")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
_fh = logging.FileHandler(LOG_FILE)
_fh.setFormatter(_fmt)
_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)
logger.addHandler(_fh)
logger.addHandler(_sh)
logger.propagate = False  # don't double-log via root

simulations: Dict[str, Simulation] = {}
simulations_running: set[str] = set()
simulations_generating: set[str] = set()
simulations_advancing: set[str] = set()


def generate_sim_id() -> str:
    return secrets.token_hex(8)


class SummarizeForumPrompt(dspy.Signature):
    """
    Generate a summary of the 'document'.
    Use complete sentences and do not be brief.
    Include information relevant to user discussion.
    Do not include any extra headings or commentary.
    """
    document: str = dspy.InputField()
    summary: str = dspy.OutputField()


def sim_filepath(sim_id: str) -> Path:
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
        kwargs["stop"] = ["### User:", "### Human:", "\nHuman:", "\nUser:"]
        built = dspy.LM(cfg.model, api_base=OLLAMA_API_BASE, api_key="ollama", **kwargs)
    elif is_anthropic:
        built = dspy.LM(cfg.model, api_key=os.getenv("CLAUDE_API_KEY", ""), **kwargs)
    else:
        built = dspy.LM(cfg.model, **kwargs)

    logger.info(f"Built LM: {cfg.model}")
    return built


def chunk_document(title: str, text: str, max_chars: int = 600, overlap_chars: int = 100) -> list[str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    chunks = []
    current = []
    current_len = 0
    
    for line in lines:
        if current_len + len(line) > max_chars and current:
            chunk_text = " ".join(current)
            chunks.append(f"[{title}]\n{chunk_text}")
            overlap = chunk_text[-overlap_chars:]
            current = [overlap, line]
            current_len = len(overlap) + len(line)
        else:
            current.append(line)
            current_len += len(line)
        
    if current:
        chunks.append(f"[{title}]\n{' '.join(current)}")
    
    return chunks


def build_document_embeddings(sim: Simulation) -> Optional[dspy.Embeddings]:
    corpus = []
    for doc in sim.documents.values():
        corpus.extend(chunk_document(doc.title, doc.text))
    if len(corpus) < 2:
        return None
    return dspy.Embeddings(corpus=corpus, embedder=embed, k=20)


def save_simulation(sim_id: str):
    sim = simulations.get(sim_id)
    
    if sim is None:
        logger.warning(f"No simulation {sim_id} to save")
        return
    
    try:
        fp = sim_filepath(sim_id)
        
        if fp.exists():
            time = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            backup_dir = fp.parent / "backups"
            backup_dir.mkdir(exist_ok=True)
            backup_fp = backup_dir / f"sim_{sim_id}_{time}.json"
            backup_fp.write_bytes(fp.read_bytes())
            
            existing = sorted(backup_dir.glob(f"sim_{sim_id}_*.json"))
            
            for old in existing[:-15]:
                old.unlink()
        
        with fp.open("w", encoding="utf-8") as f:
            json.dump(sim_to_dict(sim, sim_id), f, indent=2, cls=SimulationEncoder)
        logger.info(f"Saved simulation {sim_id} to {fp}")
    except Exception as e:
        logger.exception(f"Failed to save simulation {sim_id}: {e}")


def load_simulation_from_dict(data: Dict[str, Any]) -> Simulation:
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
        logger.exception(f"Failed to parse simulation time: {e}")
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
            reply_to=str(p.get("reply_to", "")),
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
    for fp in STORAGE_DIR.glob("sim_*.json"):
        try:
            with fp.open("r", encoding="utf-8") as f:
                data = json.load(f)
            sim_id = data.get("id")
            if not sim_id:
                sim_id = fp.stem.removeprefix("sim_")
            sim = load_simulation_from_dict(data)
            simulations[sim_id] = sim
            logger.info(f"Loaded simulation {sim_id} from {fp}")
        except Exception as e:
            logger.exception(f"Failed to load simulation from {fp}: {e}")


load_all_simulations()


def get_sim_or_404(sim_id: str) -> Simulation:
    sim = simulations.get(sim_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim


def get_sim_or_404_running(sim_id: str, require_running: bool = False) -> Simulation:
    sim = simulations.get(sim_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    if require_running and sim_id not in simulations_running:
        raise HTTPException(status_code=409, detail="Simulation is stopped")
    return sim


# ---------------------------------------------------------------------------
# JSON: model list (used to populate the AI-settings model dropdown server-side)
# ---------------------------------------------------------------------------

@app.get("/models")
def api_list_models():
    ollama_models = get_installed_ollama_models()
    return {"models": CLOUD_MODELS + ollama_models}


# ===========================================================================
# View helpers — shape in-memory objects into plain dicts for templates.
# ===========================================================================

def _display_date(forum: Forum, tick: int) -> str:
    return (forum.created_date + timedelta(hours=tick)).strftime("%b %d, %Y %H:%M")


def _avatar(raw: Optional[str]) -> str:
    if not raw:
        return ""
    if raw.startswith("data:"):
        return raw
    return f"data:image/png;base64,{raw}"


def _sims_view() -> List[Dict[str, Any]]:
    return [
        {
            "id": sid,
            "name": sim.forum.name,
            "topic": sim.forum.topic,
            "created_display": sim.forum.created_date.strftime("%b %d, %Y"),
            "users": len(sim.users),
            "threads": len(sim.threads),
            "posts": len(sim.posts),
            "running": sid in simulations_running,
        }
        for sid, sim in sorted(simulations.items())
    ]


def _threads_view(sim: Simulation) -> List[Dict[str, Any]]:
    post_counts: Dict[str, int] = {}
    for p in sim.posts:
        post_counts[p.thread.id] = post_counts.get(p.thread.id, 0) + 1
    return [
        {
            "id": t.id,
            "title": t.title,
            "summary": t.summary or "",
            "author": t.author.username,
            "created_display": _display_date(sim.forum, t.created_tick),
            "post_count": post_counts.get(t.id, 0),
        }
        for t in sorted(sim.threads, key=lambda t: t.created_tick, reverse=True)
    ]


def _users_view(sim: Simulation) -> List[Dict[str, Any]]:
    return [
        {
            "id": u.id,
            "username": u.username,
            "signature": u.signature,
            "personality": u.personality,
            "forum_dedication": u.forum_dedication,
            "active_start": u.active_hours[0] if u.active_hours else 0,
            "active_end": u.active_hours[1] if len(u.active_hours) > 1 else 23,
            "avatar": _avatar(u.profile_picture),
        }
        for u in sim.users
    ]


def _stimuli_view(sim: Simulation) -> List[Dict[str, Any]]:
    return [{"id": s.id, "text": s.text, "created_tick": s.created_tick} for s in sim.stimuli]


def _documents_view(sim: Simulation) -> List[Dict[str, Any]]:
    return [
        {"id": d.id, "title": d.title, "source": d.source, "summary": d.summary}
        for d in sim.documents.values()
    ]


def _sim_status(sim_id: str) -> Dict[str, Any]:
    sim = simulations[sim_id]
    return {
        "sim_id": sim_id,
        "running": sim_id in simulations_running,
        "advancing": sim_id in simulations_advancing,
        "generating": sim_id in simulations_generating,
        "current_time_display": _display_date(sim.forum, sim._time),
    }


def _ctx(request: Request, **kw) -> Dict[str, Any]:
    base = {"request": request}
    base.update(kw)
    return base


# ===========================================================================
# HTML pages
# ===========================================================================

@app.get("/", response_class=HTMLResponse)
def web_home(request: Request):
    return templates.TemplateResponse("home.html", _ctx(request, sims=_sims_view()))


@app.get("/sim/{sim_id}", response_class=HTMLResponse)
def web_simulation(request: Request, sim_id: str):
    sim = get_sim_or_404(sim_id)
    forum = sim.forum
    return templates.TemplateResponse(
        "simulation.html",
        _ctx(
            request,
            sim_id=sim_id,
            status=_sim_status(sim_id),
            forum={
                "name": forum.name,
                "topic": forum.topic,
                "created_display": forum.created_date.strftime("%b %d, %Y"),
            },
            threads=_threads_view(sim),
            stimuli=_stimuli_view(sim),
            documents=_documents_view(sim),
        ),
    )


@app.get("/sim/{sim_id}/thread/{thread_id}", response_class=HTMLResponse)
def web_thread(request: Request, sim_id: str, thread_id: str):
    sim = get_sim_or_404(sim_id)
    forum = sim.forum

    thread = next((t for t in sim.threads if t.id == thread_id), None)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    thread_posts = sorted(sim.get_posts_in_thread(thread), key=lambda p: p.created_tick)
    posts = [
        {
            "author": p.author.username,
            "avatar": _avatar(p.author.profile_picture),
            "content": p.content,
            "signature": p.author.signature,
            "created_display": _display_date(forum, p.created_tick),
        }
        for p in thread_posts
    ]

    return templates.TemplateResponse(
        "thread.html",
        _ctx(
            request,
            sim_id=sim_id,
            status=_sim_status(sim_id),
            forum={"name": forum.name},
            thread={
                "title": thread.title,
                "author": thread.author.username,
                "summary": thread.summary,
                "created_display": _display_date(forum, thread.created_tick),
            },
            posts=posts,
        ),
    )


@app.get("/sim/{sim_id}/users", response_class=HTMLResponse)
def web_users(request: Request, sim_id: str):
    sim = get_sim_or_404(sim_id)
    return templates.TemplateResponse(
        "users.html",
        _ctx(
            request,
            sim_id=sim_id,
            status=_sim_status(sim_id),
            forum={"name": sim.forum.name},
            users=_users_view(sim),
        ),
    )


@app.get("/sim/{sim_id}/ai-settings", response_class=HTMLResponse)
def web_ai_settings(request: Request, sim_id: str):
    sim = get_sim_or_404(sim_id)
    cfg = sim.model_config
    models = CLOUD_MODELS + get_installed_ollama_models()
    return templates.TemplateResponse(
        "ai_settings.html",
        _ctx(
            request,
            sim_id=sim_id,
            status=_sim_status(sim_id),
            forum={"name": sim.forum.name},
            models=models,
            cfg={
                "model": cfg.model,
                "temperature": cfg.temperature,
                "top_p": cfg.top_p,
                "top_k": cfg.top_k,
                "frequency_penalty": cfg.frequency_penalty,
                "presence_penalty": cfg.presence_penalty,
                "thinking": cfg.thinking,
                "thread_creation_chance": sim.thread_creation_chance,
            },
        ),
    )


# ===========================================================================
# HTMX fragment / action endpoints
# ===========================================================================

def _render(request: Request, name: str, **kw) -> HTMLResponse:
    return templates.TemplateResponse(name, _ctx(request, **kw))


# --- Home: simulation list, create, start/stop -----------------------------

@app.get("/sim-rows", response_class=HTMLResponse)
def htmx_sim_rows(request: Request):
    return _render(request, "partials/sim_rows.html", sims=_sims_view())


@app.post("/sim/create", response_class=HTMLResponse)
def htmx_create_sim(
    request: Request,
    name: str = Form(""),
    topic: str = Form(""),
    created_date: str = Form(""),
):
    name = name.strip() or "Default Forum Name"
    topic = topic.strip() or "Default Forum Topic"

    summarize_forum = dspy.ChainOfThought(SummarizeForumPrompt)
    topic_summary = summarize_forum(document=topic).summary

    cd = datetime.now()
    if created_date:
        try:
            cd = datetime.fromisoformat(created_date)
        except ValueError:
            pass

    forum = Forum(name, topic, created_date=cd, topic_summary=topic_summary)
    sim = Simulation(forum)

    sim_id = generate_sim_id()
    simulations[sim_id] = sim

    logger.info(f"Created simulation {sim_id} with forum: {sim.forum}")
    save_simulation(sim_id)

    resp = Response(status_code=204)
    resp.headers["HX-Redirect"] = f"/sim/{sim_id}"
    return resp


@app.post("/sim/{sim_id}/state", response_class=HTMLResponse)
def htmx_toggle_state(request: Request, sim_id: str, running: str = Form("")):
    get_sim_or_404(sim_id)
    want_running = running.lower() in ("1", "true", "on", "start")
    if want_running:
        simulations_running.add(sim_id)
        simulations[sim_id]._lm = build_lm(simulations[sim_id].model_config)
        simulations[sim_id]._document_embeddings = build_document_embeddings(simulations[sim_id])
    else:
        simulations_running.discard(sim_id)
    save_simulation(sim_id)
    return _render(request, "partials/sim_rows.html", sims=_sims_view())


# --- Per-sim header (current time + advance) -------------------------------

@app.get("/sim/{sim_id}/status-bar", response_class=HTMLResponse)
def htmx_status_bar(request: Request, sim_id: str):
    get_sim_or_404(sim_id)
    return _render(request, "partials/status_bar.html", status=_sim_status(sim_id))


@app.post("/sim/{sim_id}/advance", response_class=HTMLResponse)
def htmx_advance(request: Request, sim_id: str, hours: int = Form(1)):
    get_sim_or_404_running(sim_id, require_running=True)
    simulations_advancing.add(sim_id)
    try:
        sim = simulations[sim_id]
        for _ in range(max(1, hours)):
            new_threads, new_posts = sim.advance_one_hour()
            
            if new_threads or new_posts:
                save_simulation(sim_id)
    finally:
        simulations_advancing.discard(sim_id)
    return _render(request, "partials/status_bar.html", status=_sim_status(sim_id))


# --- Threads list (polled) -------------------------------------------------

@app.get("/sim/{sim_id}/threads-fragment", response_class=HTMLResponse)
def htmx_threads(request: Request, sim_id: str):
    sim = get_sim_or_404(sim_id)
    return _render(request, "partials/thread_rows.html", sim_id=sim_id, threads=_threads_view(sim))


# --- Forum topic edit ------------------------------------------------------

@app.post("/sim/{sim_id}/forum", response_class=HTMLResponse)
def htmx_update_topic(request: Request, sim_id: str, topic: str = Form(...)):
    sim = get_sim_or_404_running(sim_id, require_running=True)
    sim.forum.topic = topic
    save_simulation(sim_id)
    logger.info(f"Updated topic for simulation {sim_id}")
    return _render(
        request,
        "partials/topic_block.html",
        sim_id=sim_id,
        status=_sim_status(sim_id),
        forum={"topic": sim.forum.topic},
    )


# --- Stimuli ---------------------------------------------------------------

@app.post("/sim/{sim_id}/stimuli", response_class=HTMLResponse)
def htmx_create_stimulus(request: Request, sim_id: str, text: str = Form(...)):
    sim = get_sim_or_404(sim_id)
    s = Stimulus(text=text.strip(), created_tick=sim._time)
    sim.stimuli.append(s)
    save_simulation(sim_id)
    
    return _render(request, "partials/stimulus_list.html", sim_id=sim_id, stimuli=_stimuli_view(sim))


@app.delete("/sim/{sim_id}/stimuli/{stimulus_id}", response_class=HTMLResponse)
def htmx_delete_stimulus(request: Request, sim_id: str, stimulus_id: str):
    sim = get_sim_or_404(sim_id)
    sim.stimuli = [s for s in sim.stimuli if s.id != stimulus_id]
    save_simulation(sim_id)
    return _render(request, "partials/stimulus_list.html", sim_id=sim_id, stimuli=_stimuli_view(sim))


# --- Documents -------------------------------------------------------------

@app.post("/sim/{sim_id}/documents", response_class=HTMLResponse)
def htmx_create_document(
    request: Request,
    sim_id: str,
    title: str = Form(...),
    text: str = Form(...),
    source: str = Form(""),
):
    sim = get_sim_or_404(sim_id)
    summarize = dspy.ChainOfThought(SummarizeForumPrompt)
    summary = summarize(document=text).summary
    doc = SimulationDocument(title=title.strip(), text=text.strip(), source=source.strip(), summary=summary)
    sim.documents[doc.id] = doc
    sim.forum.documents.append(
        ForumDocumentReference(id=doc.id, title=doc.title, summary=doc.summary, source=doc.source)
    )
    save_simulation(sim_id)
    sim._document_embeddings = build_document_embeddings(sim)
    return _render(request, "partials/document_list.html", sim_id=sim_id, documents=_documents_view(sim))


@app.delete("/sim/{sim_id}/documents/{doc_id}", response_class=HTMLResponse)
def htmx_delete_document(request: Request, sim_id: str, doc_id: str):
    sim = get_sim_or_404(sim_id)
    if doc_id in sim.documents:
        del sim.documents[doc_id]
    sim.forum.documents = [d for d in sim.forum.documents if d.id != doc_id]
    save_simulation(sim_id)
    sim._document_embeddings = build_document_embeddings(sim)
    return _render(request, "partials/document_list.html", sim_id=sim_id, documents=_documents_view(sim))


# --- Users -----------------------------------------------------------------

@app.post("/sim/{sim_id}/users", response_class=HTMLResponse)
def htmx_create_user(
    request: Request,
    sim_id: str,
    username: str = Form(""),
    signature: str = Form(""),
    personality: str = Form(""),
    forum_dedication: float = Form(0.5),
    active_start: int = Form(0),
    active_end: int = Form(23),
):
    sim = get_sim_or_404_running(sim_id, require_running=True)
    user = User(
        username=username.strip() or f"user{len(sim.users) + 1}",
        profile_picture=generate_profile_picture(),
        signature=signature,
        personality=personality,
        forum_dedication=float(forum_dedication),
        active_hours=[int(active_start), int(active_end)],
        voice_profile="",
    )
    sim.users.append(user)
    logger.info(f"Manually created user {user.username} (id={user.id}) in sim {sim_id}")
    save_simulation(sim_id)
    return _render(request, "partials/user_rows.html", sim_id=sim_id, status=_sim_status(sim_id), users=_users_view(sim))


@app.post("/sim/{sim_id}/user-update", response_class=HTMLResponse)
def htmx_update_user(
    request: Request,
    sim_id: str,
    user_id: str = Form(...),
    username: str = Form(""),
    signature: str = Form(""),
    personality: str = Form(""),
    forum_dedication: float = Form(0.5),
    active_start: int = Form(0),
    active_end: int = Form(23),
):
    sim = get_sim_or_404_running(sim_id, require_running=True)
    user = next((u for u in sim.users if u.id == user_id), None)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.username = username.strip() or user.username
    user.signature = signature
    user.personality = personality
    user.forum_dedication = float(forum_dedication)
    user.active_hours = [int(active_start), int(active_end)]
    logger.info(f"Updated user {user.id} in sim {sim_id}")
    save_simulation(sim_id)
    return _render(request, "partials/user_rows.html", sim_id=sim_id, status=_sim_status(sim_id), users=_users_view(sim))


@app.get("/sim/{sim_id}/generate-controls", response_class=HTMLResponse)
def htmx_generate_controls(request: Request, sim_id: str):
    get_sim_or_404(sim_id)
    return _render(request, "partials/generate_controls.html", sim_id=sim_id, status=_sim_status(sim_id))


@app.post("/sim/{sim_id}/generate-users", response_class=HTMLResponse)
def htmx_generate_users(request: Request, sim_id: str, count: int = Form(1)):
    sim = get_sim_or_404_running(sim_id, require_running=True)
    simulations_generating.add(sim_id)
    try:
        sim.generate_users(max(1, count))
        save_simulation(sim_id)
    finally:
        simulations_generating.discard(sim_id)
    return _render(request, "partials/user_rows.html", sim_id=sim_id, status=_sim_status(sim_id), users=_users_view(sim))


# --- AI settings -----------------------------------------------------------

@app.post("/sim/{sim_id}/ai-settings", response_class=HTMLResponse)
def htmx_save_ai_settings(
    request: Request,
    sim_id: str,
    model: str = Form(""),
    temperature: float = Form(0.7),
    top_p: float = Form(0.9),
    top_k: int = Form(40),
    frequency_penalty: float = Form(0.0),
    presence_penalty: float = Form(0.0),
    thinking: str = Form("medium"),
    thread_creation_chance: float = Form(0.25),
):
    sim = get_sim_or_404(sim_id)
    cfg = sim.model_config
    if model:
        cfg.model = model
    cfg.temperature = float(temperature)
    cfg.top_p = float(top_p)
    cfg.top_k = int(top_k)
    cfg.frequency_penalty = float(frequency_penalty)
    cfg.presence_penalty = float(presence_penalty)
    if thinking in ("low", "medium", "high"):
        cfg.thinking = thinking
    sim.thread_creation_chance = float(thread_creation_chance)

    sim._lm = build_lm(cfg)
    save_simulation(sim_id)

    resp = Response(status_code=204)
    resp.headers["HX-Redirect"] = f"/sim/{sim_id}"
    return resp
