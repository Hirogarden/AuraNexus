"""
AuraNexus web server.

FastAPI + WebSocket streaming backend that wraps the full AuraNexusApp stack
and serves the single-file browser frontend from static/index.html.

Start via launcher:
    python launcher.py serve --model-path /path/to/model.gguf

Or directly:
    python server.py --model-path /path/to/model.gguf
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import uvicorn

from core.app import AuraNexusApp
from core.context_filter import ContextFilter, MemoryMode
from core.guardrails import (
    build_stop_sequences as guardrail_stop_sequences,
    contains_sensitive_text,
    finish_budget_limited_reply,
    find_role_transition,
    redact_sensitive_text,
    sanitize_single_reply,
)
from storage.embedder import embed_text
from storage.lorebook import StoryCard

# ── Runtime configuration (overridden by start_server() before lifespan runs) ─
_MODEL_PATH: Optional[str] = os.environ.get("AURANEXUS_MODEL_PATH")
_WORKSPACE_DIR: str = os.environ.get("AURANEXUS_WORKSPACE", "sandbox_workspace")
_AURA_NAME: str = os.environ.get("AURANEXUS_AURA_NAME", "Aura")
_USER_NAME: str = os.environ.get("AURANEXUS_USER_NAME", "Hiro")
_GPU_LAYERS: Optional[int] = None
_CTX_SIZE: Optional[int] = None
_MAX_TOKENS: Optional[int] = None
_RESPONSE_LENGTH: str = "normal"

# ── Global state ───────────────────────────────────────────────────────────────
_app: Optional[AuraNexusApp] = None
_model_loaded: bool = False
_inference_lock: Optional[asyncio.Lock] = None
_executor = ThreadPoolExecutor(max_workers=2)
_abort_event = threading.Event()  # set by POST /api/abort; cleared at start of each inference

_STATIC_DIR = Path(__file__).parent / "static"


def _require_app() -> AuraNexusApp:
    if _app is None:
        raise HTTPException(status_code=503, detail="AuraNexus app not initialized.")
    return _app


# ── Stop-sequence streaming ───────────────────────────────────────────────────

def _stopping_wrap(
    gen: Iterator[str],
    stop_sequences: List[str],
    *,
    role_boundary_detector: Any | None = None,
) -> Iterator[str]:
    """
    Wraps a token generator and halts emission when any stop sequence appears
    in the accumulated output, discarding everything from the stop point onward.

    Handles stop sequences that straddle token boundaries by maintaining a
    rolling tail buffer for lookback.
    """
    if not stop_sequences and role_boundary_detector is None:
        yield from gen
        return

    pending = ""
    lookback = max(max((len(seq) for seq in stop_sequences), default=0), 96)

    for token in gen:
        pending += token

        cut: int | None = None
        for seq in stop_sequences:
            pos = pending.find(seq)
            if pos >= 0 and (cut is None or pos < cut):
                cut = pos

        if callable(role_boundary_detector):
            boundary = role_boundary_detector(pending)
            if boundary is not None and (cut is None or boundary < cut):
                cut = boundary

        if cut is not None:
            if cut > 0:
                yield pending[:cut]
            return

        safe_length = len(pending) - lookback
        if safe_length > 0:
            yield pending[:safe_length]
            pending = pending[safe_length:]

    if pending:
        yield pending


def _build_stop_sequences(user_name: str, aura_name: str) -> List[str]:
    return guardrail_stop_sequences(user_name, aura_name)


# ── Streaming helper ───────────────────────────────────────────────────────────

async def _stream_tokens(ws: WebSocket, token_gen: Iterator[str]) -> str:
    """
    Runs a synchronous llama.cpp character-generator in a thread pool executor
    and pushes each token to the WebSocket as a JSON frame.  Returns the full
    concatenated text once the generator is exhausted.

    Respects _abort_event: if it is set mid-stream, generation is cut short and
    an 'aborted' frame is sent to the client.
    """
    queue: asyncio.Queue[Optional[str]] = asyncio.Queue(maxsize=1024)
    loop = asyncio.get_event_loop()

    sentinel_error_prefix = "\x00ERR\x00"

    def _producer() -> None:
        try:
            for token in token_gen:
                if _abort_event.is_set():
                    break
                loop.call_soon_threadsafe(queue.put_nowait, token)
        except Exception as exc:  # noqa: BLE001
            loop.call_soon_threadsafe(
                queue.put_nowait, f"{sentinel_error_prefix}{exc}"
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    thread = threading.Thread(target=_producer, daemon=True)
    thread.start()

    full_parts: List[str] = []
    while True:
        # Poll with a short timeout so we can detect abort between tokens
        try:
            token = await asyncio.wait_for(queue.get(), timeout=0.08)
        except asyncio.TimeoutError:
            if _abort_event.is_set():
                # Drain any remaining items the producer may have queued
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except Exception:  # noqa: BLE001
                        pass
                await ws.send_json({"type": "aborted"})
                return "".join(full_parts)
            continue

        if token is None:
            break
        if token.startswith(sentinel_error_prefix):
            error_msg = token[len(sentinel_error_prefix):]
            await ws.send_json({"type": "error", "message": error_msg})
            return "".join(full_parts)
        full_parts.append(token)
        await ws.send_json({"type": "token", "text": token})

    return "".join(full_parts)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def _lifespan(fastapi_app: FastAPI):  # noqa: ARG001
    global _app, _model_loaded, _inference_lock

    _inference_lock = asyncio.Lock()

    _app = AuraNexusApp(
        model_path=_MODEL_PATH or "models/placeholder.gguf",
        workspace_dir=_WORKSPACE_DIR,
        aura_name=_AURA_NAME,
        user_name=_USER_NAME,
        allowed_commands={"python3"},
        require_isolation=False,
    )
    _app.inference_engine.set_response_length_mode(_RESPONSE_LENGTH)

    if _MODEL_PATH and Path(_MODEL_PATH).exists():
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                _executor,
                lambda: _app.load_model(n_gpu_layers=_GPU_LAYERS, ctx_size=_CTX_SIZE),
            )
            if _MAX_TOKENS is not None:
                _app.inference_engine.set_generation_overrides(max_tokens=_MAX_TOKENS)
            _model_loaded = True
            print(f"[AuraNexus] Model loaded from {_MODEL_PATH}")
        except Exception as exc:
            print(
                f"[AuraNexus] WARNING: Model load failed: {exc}\n"
                "  Inference endpoints will return errors until the model is available."
            )
    else:
        if _MODEL_PATH:
            print(f"[AuraNexus] WARNING: Model path '{_MODEL_PATH}' not found. Inference unavailable.")
        else:
            print("[AuraNexus] No model path provided. Inference unavailable. UI and memory features work.")

    print(f"[AuraNexus] Server ready. Open http://127.0.0.1:7860 in your browser.")
    yield

    # Graceful shutdown — save_state() persists both HiRAG stores internally.
    if _app:
        _app.save_state()
    _executor.shutdown(wait=False)


# ── FastAPI application ────────────────────────────────────────────────────────

web = FastAPI(title="AuraNexus", version="0.2.0", lifespan=_lifespan)

if _STATIC_DIR.exists():
    web.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@web.get("/", response_class=FileResponse)
async def root():
    index = _STATIC_DIR / "index.html"
    if not index.exists():
        return HTMLResponse(
            "<h1>AuraNexus</h1>"
            "<p>Frontend not found — expected <code>static/index.html</code> next to server.py.</p>"
        )
    return FileResponse(str(index))


@web.get("/story", response_class=FileResponse)
async def story_root():
    """Serves the dedicated Story Engine window."""
    story_page = _STATIC_DIR / "story.html"
    if not story_page.exists():
        return HTMLResponse(
            "<h1>AuraNexus Story Engine</h1>"
            "<p>Story frontend not found — expected <code>static/story.html</code> next to server.py.</p>"
        )
    return FileResponse(str(story_page))


# ── Status ─────────────────────────────────────────────────────────────────────

@web.get("/api/status")
async def api_status():
    app = _require_app()
    manifest = app.get_bootstrap_manifest()
    g = app.hirag_general.get_hirag_state()
    p = app.hirag_personal.get_hirag_state()
    return {
        "status": "ok",
        "model_loaded": _model_loaded,
        "model_path": _MODEL_PATH,
        "aura_name": _AURA_NAME,
        "user_name": _USER_NAME,
        "app_version": manifest.get("app_version"),
        "memory": {
            "general": {"local_count": g["local_count"], "global_count": g["global_count"]},
            "personal": {"local_count": p["local_count"], "global_count": p["global_count"]},
        },
    }


# ── Chat sessions ──────────────────────────────────────────────────────────────

class NewChatSessionRequest(BaseModel):
    name: str = Field(default="New Conversation", min_length=1, max_length=120)


@web.get("/api/sessions/chat")
async def list_chat_sessions():
    return _require_app().runtime.list_chat_sessions()


@web.post("/api/sessions/chat", status_code=201)
async def new_chat_session(req: NewChatSessionRequest):
    app = _require_app()
    session = app.runtime.start_chat_session(req.name)
    app.runtime.save_active_chat_session()
    return {
        "session_id": session.session_id,
        "name": session.name,
        "created_at": session.created_at,
        "turns": [],
    }


@web.put("/api/sessions/chat/{session_id}")
async def resume_chat_session(session_id: str):
    app = _require_app()
    try:
        session = app.runtime.load_chat_session(session_id)
    except Exception:
        raise HTTPException(
            status_code=404, detail=f"Chat session '{session_id}' not found."
        )
    return {
        "session_id": session.session_id,
        "name": session.name,
        "created_at": session.created_at,
        "turns": [
            {
                "user": t.user_text,
                "assistant": t.assistant_text,
                "timestamp": t.timestamp,
            }
            for t in session.turns
        ],
    }


@web.delete("/api/sessions/chat/{session_id}", status_code=204)
async def delete_chat_session(session_id: str):
    app = _require_app()
    if app.runtime.chat_session_dir is None:
        raise HTTPException(
            status_code=400, detail="Chat session directory not configured."
        )
    path = app.runtime.chat_session_dir / f"{session_id}.json"
    if not path.exists():
        raise HTTPException(
            status_code=404, detail=f"Chat session '{session_id}' not found."
        )
    if (
        app.runtime.active_chat_session is not None
        and app.runtime.active_chat_session.session_id == session_id
    ):
        app.runtime.attach_chat_session(None)
    path.unlink()


# ── Story sessions ─────────────────────────────────────────────────────────────

class NewStorySessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    genre: str = Field(min_length=1, max_length=80)
    tone: str = Field(min_length=1, max_length=80)
    setting: str = Field(min_length=1, max_length=400)
    player_name: str = Field(min_length=1, max_length=80)
    player_desc: str = Field(default="", max_length=400)


@web.get("/api/sessions/story")
async def list_story_sessions():
    return _require_app().runtime.list_story_sessions()


@web.post("/api/sessions/story", status_code=201)
async def new_story_session(req: NewStorySessionRequest):
    app = _require_app()
    story = app.runtime.start_story(
        title=req.title,
        genre=req.genre,
        tone=req.tone,
        setting=req.setting,
        player_name=req.player_name,
        player_desc=req.player_desc,
    )
    app.runtime.save_active_story()
    return {
        "session_id": story.session_id,
        "title": story.title,
        "genre": story.genre,
        "tone": story.tone,
        "setting": story.setting,
        "player_name": story.player_name,
        "created_at": story.created_at,
        "beats": [],
    }


@web.put("/api/sessions/story/{session_id}")
async def resume_story_session(session_id: str):
    app = _require_app()
    try:
        story = app.runtime.load_story_session(session_id)
    except Exception:
        raise HTTPException(
            status_code=404, detail=f"Story session '{session_id}' not found."
        )
    return {
        "session_id": story.session_id,
        "title": story.title,
        "genre": story.genre,
        "tone": story.tone,
        "setting": story.setting,
        "player_name": story.player_name,
        "created_at": story.created_at,
        "beats": [
            {
                "player": b.player_action,
                "narrator": b.narrator_response,
                "timestamp": b.timestamp,
            }
            for b in story.beats
        ],
    }


@web.post("/api/sessions/story/{session_id}/rollback", status_code=200)
async def rollback_story_beat(session_id: str):
    """Remove the last story beat (undo last narrator response)."""
    app = _require_app()
    if app.runtime.active_story is None or app.runtime.active_story.session_id != session_id:
        # Try loading it
        try:
            app.runtime.load_story_session(session_id)
        except Exception:
            raise HTTPException(status_code=404, detail=f"Story session '{session_id}' not found.")
    story = app.runtime.active_story
    if not story.beats:
        raise HTTPException(status_code=400, detail="No beats to roll back.")
    beat = story.beats.pop()
    app.runtime.save_active_story()
    return {"removed_player_action": beat.player_action, "beats_remaining": len(story.beats)}


@web.delete("/api/sessions/story/{session_id}", status_code=204)
async def delete_story_session(session_id: str):
    app = _require_app()
    if app.runtime.story_session_dir is None:
        raise HTTPException(
            status_code=400, detail="Story session directory not configured."
        )
    path = app.runtime.story_session_dir / f"{session_id}.json"
    if not path.exists():
        raise HTTPException(
            status_code=404, detail=f"Story session '{session_id}' not found."
        )
    if (
        app.runtime.active_story is not None
        and app.runtime.active_story.session_id == session_id
    ):
        app.runtime.attach_story(None)
    path.unlink()


# ── Lorebook ───────────────────────────────────────────────────────────────────

class NewLoreCardRequest(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    keys: List[str] = Field(min_length=1)
    content: str = Field(min_length=1, max_length=4000)
    category: str = Field(default="general", max_length=80)
    priority: int = Field(default=10, ge=0, le=100)
    mode: str = Field(default="shared")
    enabled: bool = Field(default=True)


@web.get("/api/lorebook")
async def get_lorebook():
    app = _require_app()
    return [card.to_dict() for card in app.lorebook.cards.values()]


@web.post("/api/lorebook", status_code=201)
async def add_lore_card(req: NewLoreCardRequest):
    app = _require_app()
    if req.id in app.lorebook.cards:
        raise HTTPException(
            status_code=409, detail=f"Lore card '{req.id}' already exists."
        )
    try:
        card = StoryCard(
            id=req.id,
            keys=req.keys,
            content=req.content,
            category=req.category,
            priority=req.priority,
            mode=req.mode,
            enabled=req.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    app.lorebook.add_card(card)
    app.lorebook.save()
    return card.to_dict()


@web.delete("/api/lorebook/{card_id}", status_code=204)
async def delete_lore_card(card_id: str):
    app = _require_app()
    if card_id not in app.lorebook.cards:
        raise HTTPException(
            status_code=404, detail=f"Lore card '{card_id}' not found."
        )
    del app.lorebook.cards[card_id]
    app.lorebook.save()


# ── HiRAG memory ───────────────────────────────────────────────────────────────

_VALID_BUCKETS = {"general", "personal"}


class AddMemoryRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    bucket: str = Field(default="general")


class SearchMemoryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    top_clusters: int = Field(default=2, ge=1, le=10)
    mode: str = Field(default="companion", pattern="^(companion|storyteller|shared)$")
    bucket: str = Field(default="general")


@web.get("/api/memory")
async def get_memory_state():
    """Returns HiRAG state for both buckets."""
    app = _require_app()
    return {
        "general": app.hirag_general.get_hirag_state(),
        "personal": app.hirag_personal.get_hirag_state(),
    }


@web.post("/api/memory/add", status_code=201)
async def add_memory(req: AddMemoryRequest):
    app = _require_app()
    if req.bucket not in _VALID_BUCKETS:
        raise HTTPException(status_code=422, detail=f"bucket must be 'general' or 'personal'.")
    store = app.hirag_personal if req.bucket == "personal" else app.hirag_general
    redacted_text = redact_sensitive_text(req.text)
    vector = embed_text(redacted_text)
    metadata = dict(req.metadata)
    metadata["sensitive"] = bool(metadata.get("sensitive")) or contains_sensitive_text(redacted_text)
    store.add_vector(vector=vector, text=redacted_text, metadata=metadata)
    store.save_index()
    state = store.get_hirag_state()
    return {
        "status": "added",
        "bucket": req.bucket,
        "local_count": state["local_count"],
        "global_count": state["global_count"],
    }


@web.post("/api/memory/search")
async def search_memory(req: SearchMemoryRequest):
    app = _require_app()
    if req.bucket not in _VALID_BUCKETS:
        raise HTTPException(status_code=422, detail=f"bucket must be 'general' or 'personal'.")
    store = app.hirag_personal if req.bucket == "personal" else app.hirag_general
    query_vector = embed_text(req.query)
    results = store.query_hierarchical(
        query_vector=query_vector,
        top_k=req.top_k,
        top_clusters=req.top_clusters,
    )
    # Apply context filter so the UI search respects mode boundaries
    mode = req.mode if req.mode in ("companion", "storyteller") else "companion"
    cf = ContextFilter(MemoryMode(mode))
    results = cf.filter_search_results(results)
    return [
        {
            "text": redact_sensitive_text(text),
            "score": round(score, 4),
            "bucket": req.bucket,
            "cluster_id": meta.get("hirag_cluster_id"),
            "local_id": meta.get("hirag_local_id"),
            "metadata": {
                k: v
                for k, v in meta.items()
                if k not in ("hirag_cluster_id", "hirag_local_id")
            } if not bool(meta.get("sensitive")) else {"sensitive": True},
        }
        for text, meta, score in results
        if not bool(meta.get("sensitive")) and not contains_sensitive_text(text)
    ]

# ── WorldState facts ───────────────────────────────────────────────────────────

class AssertFactRequest(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=1000)
    permanent: bool = Field(default=False)


@web.get("/api/worldstate")
async def get_world_state():
    app = _require_app()
    return [f.to_dict() for f in app.runtime.world_state.all_facts()]


@web.post("/api/worldstate", status_code=201)
async def assert_fact(req: AssertFactRequest):
    app = _require_app()
    app.runtime.world_state.assert_fact(req.key, req.value, source="user", permanent=req.permanent)
    return {"key": req.key, "value": req.value, "permanent": req.permanent}


@web.delete("/api/worldstate/{fact_key}", status_code=204)
async def retract_fact(fact_key: str):
    app = _require_app()
    ok = app.runtime.world_state.retract_fact(fact_key)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Fact '{fact_key}' not found or is permanent.")

# ── Abort ──────────────────────────────────────────────────────────────────────

@web.post("/api/abort", status_code=204)
async def abort_generation():
    """Signal the currently running generation to stop immediately."""
    _abort_event.set()


# ── Skills ─────────────────────────────────────────────────────────────────────

@web.get("/api/skills")
async def list_skills():
    return _require_app().tool_registry.get_tool_schemas()


# ── WebSocket: Companion ───────────────────────────────────────────────────────

@web.websocket("/ws/companion")
async def ws_companion(ws: WebSocket):
    await ws.accept()
    app = _require_app()

    try:
        while True:
            raw = await ws.receive_text()

            try:
                msg: Dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON."})
                continue

            user_text = str(msg.get("message", "")).strip()
            if not user_text:
                await ws.send_json({"type": "error", "message": "Empty message."})
                continue

            if not _model_loaded:
                await ws.send_json(
                    {
                        "type": "error",
                        "message": (
                            "Model not loaded. Start the server with "
                            "--model-path /path/to/model.gguf"
                        ),
                    }
                )
                continue

            session_name: Optional[str] = msg.get("session_name")
            restore_latest: bool = bool(msg.get("restore_latest", True))

            app.ensure_companion_session(
                name=session_name, restore_latest=restore_latest
            )

            _abort_event.clear()
            async with _inference_lock:
                stop_seqs = _build_stop_sequences(
                    app.runtime.user_name, app.runtime.aura_name
                )

                # Phase 1: hidden inner reflection
                await ws.send_json({"type": "start", "phase": "reflection"})
                context = app.runtime.build_prompt(user_text)
                reflection_prompt = app.companion_mode._build_reflection_prompt(
                    context, user_text
                )
                response_detector = lambda text: find_role_transition(
                    text,
                    user_name=app.runtime.user_name,
                    assistant_name=app.runtime.aura_name,
                )
                hidden_reflection = await _stream_tokens(
                    ws,
                    _stopping_wrap(
                        app.runtime.inference_engine.generate(reflection_prompt),
                        stop_seqs,
                        role_boundary_detector=response_detector,
                    ),
                )

                # Phase 2: final response
                await ws.send_json({"type": "start", "phase": "response"})
                final_prompt = app.companion_mode._build_final_prompt(
                    context, hidden_reflection
                )
                raw_response = await _stream_tokens(
                    ws,
                    _stopping_wrap(
                        app.runtime.inference_engine.generate(final_prompt),
                        stop_seqs,
                        role_boundary_detector=response_detector,
                    ),
                )

            response = app.companion_mode._sanitize_response(raw_response)
            if not response:
                response = (
                    "I hear you. Let me keep this simple and stay with you one step at a time."
                )

            app.runtime.post_turn(user_text, response)
            app.runtime.save_active_chat_session()

            await ws.send_json(
                {
                    "type": "done",
                    "response": response,
                    "lore_cards": context.lore_card_ids,
                }
            )

    except WebSocketDisconnect:
        pass


# ── WebSocket: Story ───────────────────────────────────────────────────────────

@web.websocket("/ws/story")
async def ws_story(ws: WebSocket):
    await ws.accept()
    app = _require_app()

    try:
        while True:
            raw = await ws.receive_text()

            try:
                msg: Dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON."})
                continue

            user_text = str(msg.get("message", "")).strip()
            if not user_text:
                continue

            if not _model_loaded:
                await ws.send_json(
                    {"type": "error", "message": "Model not loaded."}
                )
                continue

            # Optional inline story setup in first message
            start_data: Optional[Dict[str, Any]] = msg.get("start_story")
            if start_data:
                try:
                    app.runtime.start_story(
                        title=str(start_data.get("title", "New Story")),
                        genre=str(start_data.get("genre", "Fantasy")),
                        tone=str(start_data.get("tone", "Neutral")),
                        setting=str(start_data.get("setting", "A mysterious world.")),
                        player_name=str(start_data.get("player_name", _USER_NAME)),
                        player_desc=str(start_data.get("player_desc", "")),
                    )
                except Exception as exc:
                    await ws.send_json({"type": "error", "message": str(exc)})
                    continue

            if app.runtime.active_story is None:
                await ws.send_json(
                    {
                        "type": "error",
                        "message": (
                            "No active story session. "
                            "Include start_story payload or resume a story session first."
                        ),
                    }
                )
                continue

            _abort_event.clear()
            async with _inference_lock:
                stop_seqs = _build_stop_sequences(
                    app.runtime.user_name, app.runtime.aura_name
                )
                if app.runtime.active_story is not None:
                    player_name = app.runtime.active_story.player_name
                    stop_seqs.append(f"\n{player_name}:")
                    response_detector = lambda text: find_role_transition(
                        text,
                        user_name=app.runtime.user_name,
                        assistant_name=app.runtime.aura_name,
                        extra_turn_speakers=(
                            app.runtime.active_story.player_name,
                            app.runtime.active_story.narrator_name,
                        ),
                    )
                else:
                    response_detector = lambda text: find_role_transition(
                        text,
                        user_name=app.runtime.user_name,
                        assistant_name=app.runtime.aura_name,
                    )

                await ws.send_json({"type": "start", "phase": "narration"})
                context = app.runtime.build_prompt(user_text)
                response = await _stream_tokens(
                    ws,
                    _stopping_wrap(
                        app.runtime.inference_engine.generate(context.prompt),
                        stop_seqs,
                        role_boundary_detector=response_detector,
                    ),
                )

            response = sanitize_single_reply(
                response,
                user_name=app.runtime.user_name,
                assistant_name=app.runtime.aura_name,
                extra_turn_speakers=(
                    app.runtime.active_story.player_name,
                    app.runtime.active_story.narrator_name,
                ) if app.runtime.active_story is not None else None,
            )
            if getattr(app.runtime.inference_engine, "last_generation_hit_budget", False):
                response = finish_budget_limited_reply(response)

            if response.strip():
                app.runtime.post_turn(user_text, response)
                app.runtime.save_active_story()

            await ws.send_json(
                {
                    "type": "done",
                    "response": response,
                    "lore_cards": context.lore_card_ids,
                }
            )

    except WebSocketDisconnect:
        pass


# ── Programmatic entry point (called by launcher.py) ──────────────────────────

def start_server(
    host: str = "127.0.0.1",
    port: int = 7860,
    model: Optional[str] = None,
    workspace: str = "sandbox_workspace",
    aura_name: str = "Aura",
    user_name: str = "Hiro",
    gpu_layers: Optional[int] = None,
    ctx_size: Optional[int] = None,
    max_tokens: Optional[int] = None,
    response_length: str = "normal",
    cpu_fast: bool = False,
) -> None:
    """Configure and launch the uvicorn server."""
    global _MODEL_PATH, _WORKSPACE_DIR, _AURA_NAME, _USER_NAME
    global _GPU_LAYERS, _CTX_SIZE, _MAX_TOKENS, _RESPONSE_LENGTH

    _MODEL_PATH = model
    _WORKSPACE_DIR = workspace
    _AURA_NAME = aura_name
    _USER_NAME = user_name
    _RESPONSE_LENGTH = response_length

    if cpu_fast:
        _GPU_LAYERS = gpu_layers if gpu_layers is not None else 0
        _CTX_SIZE = ctx_size if ctx_size is not None else 2048
        _MAX_TOKENS = max_tokens if max_tokens is not None else 160
    else:
        _GPU_LAYERS = gpu_layers
        _CTX_SIZE = ctx_size
        _MAX_TOKENS = max_tokens

    # Re-mount static if it wasn't available at import time
    if _STATIC_DIR.exists() and "static" not in {r.name for r in web.routes if hasattr(r, "name")}:
        web.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    uvicorn.run(web, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="AuraNexus web server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=7860)
    p.add_argument("--model-path", default=None)
    p.add_argument("--workspace-dir", default="sandbox_workspace")
    p.add_argument("--aura-name", default="Aura")
    p.add_argument("--user-name", default="Hiro")
    p.add_argument("--cpu-fast", action="store_true")
    p.add_argument("--gpu-layers", type=int, default=None)
    p.add_argument("--ctx-size", type=int, default=None)
    p.add_argument("--max-tokens", type=int, default=None)
    p.add_argument("--response-length", choices=("short", "normal", "long"), default="normal")
    a = p.parse_args()

    start_server(
        host=a.host,
        port=a.port,
        model=a.model_path,
        workspace=a.workspace_dir,
        aura_name=a.aura_name,
        user_name=a.user_name,
        gpu_layers=a.gpu_layers,
        ctx_size=a.ctx_size,
        max_tokens=a.max_tokens,
        response_length=a.response_length,
        cpu_fast=a.cpu_fast,
    )
