"""UNO LUCK v0.2 guest multiplayer staging API.

Room state is ephemeral by design. It does not provide deposits, withdrawals,
real money prizes, user accounts, or cash-value balances.
"""
from __future__ import annotations
import os
import re
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .engine import COLORS, RuleError, UnoGame
from .spin import router as spin_router
from .orbit import router as orbit_router

APP_ROOT = Path(__file__).resolve().parent
app = FastAPI(title="UNO LUCK Spin Staging", version="1.0.0", docs_url=None, redoc_url=None)
app.include_router(spin_router)
app.include_router(orbit_router)
app.mount("/assets", StaticFiles(directory=APP_ROOT / "static"), name="assets")


@app.get("/")
async def homepage():
    return FileResponse(APP_ROOT / "static" / "orbit-index.html")


@app.get("/spin-legacy")
async def legacy_spin_home():
    return FileResponse(APP_ROOT / "static" / "spin-index.html")


@app.get("/classic")
async def classic_home():
    """Preserve Classic implementation for regression checks, not the main game."""
    return FileResponse(APP_ROOT / "static" / "index.html")


@app.get("/health")
async def health():
    return {"ok": True, "version": "0.6.0", "game": "UNO LUCK SPIN", "money_enabled": False, "main_mode": "spin"}


@dataclass
class Member:
    id: str
    token: str
    name: str
    joined_at: float
    bot: bool = False


@dataclass
class Room:
    code: str
    host_id: str
    members: list[Member]
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    game: UnoGame | None = None
    sockets: dict[str, WebSocket] = field(default_factory=dict)
    action_times: dict[str, deque[float]] = field(default_factory=dict)

    def participant(self, pid: str) -> Member | None:
        return next((m for m in self.members if m.id == pid), None)

    def lobby_view(self, pid: str) -> dict[str, Any]:
        return {
            "type": "state", "room": self.code, "host": self.host_id,
            "you": pid, "game_running": self.game is not None,
            "member_count": len(self.members),
            "members": [{"id": m.id, "name": m.name, "bot": m.bot,
                         "online": m.bot or m.id in self.sockets}
                        for m in self.members],
            "game": self.game.view(pid) if self.game else None,
        }


ROOMS: dict[str, Room] = {}
NAME_MAX = 20
ROOM_TTL = 6 * 3600
ROOM_MAX = 1000
BOT_NAMES = ("Mika", "Raka", "Luna")


def valid_name(name: Any) -> str:
    if not isinstance(name, str):
        raise RuleError("Enter a player name")
    # Remove control and formatting characters, and limit length.
    name = " ".join("".join(c for c in name if c.isprintable() and c not in "<>\\/").split())
    if not name or len(name) > NAME_MAX:
        raise RuleError("Player name must contain 1–20 characters")
    return name


def new_member(name: str) -> Member:
    return Member(id="p_" + secrets.token_urlsafe(9), token=secrets.token_urlsafe(32),
                  name=valid_name(name), joined_at=time.time())


def cleanup_rooms() -> None:
    now = time.time()
    for code, room in list(ROOMS.items()):
        if not room.sockets and now - room.last_activity > ROOM_TTL:
            ROOMS.pop(code, None)


def make_room(name: str) -> tuple[Room, Member]:
    cleanup_rooms()
    if len(ROOMS) >= ROOM_MAX:
        raise RuleError("Room capacity reached. Please try later")
    # Avoid easily guessable room codes and ambiguous characters.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(10):
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        if code not in ROOMS:
            break
    else:
        raise RuleError("Cannot allocate a room right now")
    member = new_member(name)
    room = Room(code=code, host_id=member.id, members=[member])
    ROOMS[code] = room
    return room, member


def join_room(code: Any, name: str) -> tuple[Room, Member]:
    if not isinstance(code, str) or not re.fullmatch("[A-HJ-NP-Z2-9]{6}", code.upper()):
        raise RuleError("Enter a valid 6-character room code")
    room = ROOMS.get(code.upper())
    if room is None:
        raise RuleError("Room not found or expired")
    if room.game is not None:
        raise RuleError("Game already started. Rejoin with your existing session")
    if len(room.members) >= 4:
        raise RuleError("This room is full")
    member = new_member(name)
    room.members.append(member)
    room.last_activity = time.time()
    return room, member


def resume_room(code: Any, token: Any) -> tuple[Room, Member]:
    if not isinstance(code, str) or not isinstance(token, str):
        raise RuleError("Session not found. Join a new room")
    room = ROOMS.get(code.upper())
    if not room:
        raise RuleError("Room expired. Start a new room")
    member = next((m for m in room.members if not m.bot and secrets.compare_digest(m.token, token)), None)
    if not member:
        raise RuleError("This session is invalid or has expired")
    room.last_activity = time.time()
    return room, member


def start_game(room: Room, actor: str, *, new_round: bool = False) -> None:
    if room.host_id != actor:
        raise RuleError("Only the room host can start a round")
    if new_round:
        if room.game is None or room.game.phase != "round_over":
            raise RuleError("Finish the current round first")
        previous_scores = room.game.scores
    else:
        if room.game is not None:
            raise RuleError("The game has already started")
        # Fill all unoccupied seats with bots, without taking over humans.
        i = 0
        while len(room.members) < 4:
            name = BOT_NAMES[i % len(BOT_NAMES)]
            room.members.append(Member(id="bot_" + secrets.token_urlsafe(6), token="",
                                       name=name, joined_at=time.time(), bot=True))
            i += 1
        previous_scores = None
    players = [{"id": m.id, "name": m.name, "bot": m.bot} for m in room.members]
    room.game = UnoGame(players, previous_scores=previous_scores)
    room.game.run_bots()
    room.last_activity = time.time()


def handle_action(room: Room, actor: str, data: dict[str, Any]) -> None:
    action = data.get("action")
    if action == "start":
        start_game(room, actor)
        return
    if action == "next_round":
        start_game(room, actor, new_round=True)
        return
    game = room.game
    if game is None:
        raise RuleError("The room host must start the game")
    if game.phase == "round_over":
        raise RuleError("The round is over. Start another round")
    if action == "play":
        card_id = data.get("card_id")
        color = data.get("color")
        if color is not None and color not in COLORS:
            raise RuleError("Invalid Wild color")
        game.play(actor, card_id, color)
    elif action == "draw":
        game.draw(actor)
    elif action == "keep":
        game.keep(actor)
    elif action == "uno":
        game.call_uno(actor)
    elif action == "catch":
        game.catch_uno(actor)
    elif action == "challenge":
        game.plus4_decision(actor, challenge=True)
    elif action == "accept":
        game.plus4_decision(actor, challenge=False)
    else:
        raise RuleError("Unknown game action")
    game.run_bots()
    room.last_activity = time.time()


def check_rate(room: Room, player_id: str) -> None:
    now = time.monotonic()
    q = room.action_times.setdefault(player_id, deque())
    while q and now - q[0] > 10:
        q.popleft()
    if len(q) >= 25:
        raise RuleError("Too many actions. Wait a moment")
    q.append(now)


async def broadcast(room: Room) -> None:
    for pid, socket in list(room.sockets.items()):
        try:
            await socket.send_json(room.lobby_view(pid))
        except Exception:
            if room.sockets.get(pid) is socket:
                room.sockets.pop(pid, None)


@app.websocket("/ws")
async def ws_game(ws: WebSocket):
    # For public deployments, set UNO_ALLOWED_ORIGINS to exact https origins.
    allowed = {item.strip() for item in os.getenv("UNO_ALLOWED_ORIGINS", "").split(",") if item.strip()}
    origin = ws.headers.get("origin", "")
    # Browser clients should originate from the page that hosts the WebSocket.
    # This supports Railway-generated domains without wildcarding other origins.
    host = ws.headers.get("host", "")
    same_origin = origin in {f"https://{host}", f"http://{host}"}
    if origin and not same_origin and origin not in allowed:
        await ws.close(code=1008)
        return
    await ws.accept()
    room: Room | None = None
    member: Member | None = None
    try:
        raw = await ws.receive_text()
        if len(raw) > 2048:
            raise RuleError("Request too large")
        import json
        hello = json.loads(raw)
        if not isinstance(hello, dict):
            raise RuleError("Invalid connection request")
        mode = hello.get("type")
        if mode == "create":
            room, member = make_room(hello.get("name"))
        elif mode == "join":
            room, member = join_room(hello.get("room"), valid_name(hello.get("name")))
        elif mode == "resume":
            room, member = resume_room(hello.get("room"), hello.get("token"))
        else:
            raise RuleError("Create, join or resume a room")
        old_connection = room.sockets.get(member.id)
        if old_connection and old_connection is not ws:
            try:
                await old_connection.close(code=1000, reason="Session reconnected")
            except Exception:
                pass
        room.sockets[member.id] = ws
        await ws.send_json({"type": "welcome", "room": room.code, "player_id": member.id,
                            "token": member.token, "name": member.name})
        await broadcast(room)
        while True:
            text = await ws.receive_text()
            if len(text) > 2048:
                await ws.send_json({"type": "error", "message": "Request too large"})
                continue
            try:
                packet = json.loads(text)
                if not isinstance(packet, dict):
                    raise RuleError("Expected an action")
                if packet.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
                    continue
                check_rate(room, member.id)
                handle_action(room, member.id, packet)
                await broadcast(room)
            except (RuleError, ValueError, TypeError) as e:
                await ws.send_json({"type": "error", "message": str(e)[:150]})
    except WebSocketDisconnect:
        pass
    except (RuleError, ValueError, TypeError) as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)[:150]})
            await ws.close(code=1008)
        except Exception:
            pass
    finally:
        if room and member and room.sockets.get(member.id) is ws:
            room.sockets.pop(member.id, None)
            room.last_activity = time.time()
            await broadcast(room)
