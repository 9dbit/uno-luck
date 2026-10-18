# UNO LUCK | Online Multiplayer Prototype

Mobile-first, lightweight **2–4-player private room** card game. Server-authoritative FastAPI + WebSocket rules, polished metallic card UI, optional bots, and reconnect tokens. Python 3.12, zero client build step. Prototype for testing only.

## Features

- Six-character private room codes and shareable invitation links.
- Host starts the round; empty seats fill with bots.
- Real-time private hands (other players' hands never transmitted).
- Classic 108-card rules, seven dealt, number-only first discard, no draw stacking. Skip, Reverse, +2, Wild, challenge +4, call/catch UNO, scoring and rematches.
- Soft web-audio cues; sound toggle; metallic cards; responsive touch UI; PWA manifest.
- Session reconnect via per-player token in browser local storage, never in invitation URLs.
- `/health` returns service status. Built-in 25-actions/10 seconds per room participant rate check.

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt pytest httpx
python -m pytest -q
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000. Use two separate browser profiles, create a room in the first, then join with its room code from the second. The host starts and remaining seats fill with bots.

## Railway

This repository includes a `Dockerfile` and `railway.json`. Railway should use **one replica only** and a single Uvicorn worker because rooms are stored in process memory. A deploy/restart clears rooms and game progress. For durable production multiplayer, add Redis or PostgreSQL state plus shared events before enabling multiple replicas.

- Runtime port: explicitly set Railway service variable `PORT=8080` and keep the Railway service domain target port **8080**. The Dockerfile exposes 8080 and Uvicorn binds `0.0.0.0:${PORT:-8080}`. A mismatch causes HTTP 502 `connection refused` despite a `SUCCESS` deployment.
- Build: Dockerfile, listening on `${PORT}` (default 8080).
- Healthcheck: `/health`.
- Optional `UNO_ALLOWED_ORIGINS`: comma-separated extra exact URL origins. The served same-origin origin is allowed by default.

## Safety and scope

**Play-money prototype only.** No deposits, real-money purchases, staking, wagering, redeemable prizes, cashout, or withdrawals. No real accounts and no cross-device account persistence. Name and reconnect token are stored in the user's current browser. Rooms expire when empty after six hours or on redeploy.

UNO is a trademark of Mattel. This independent demonstration is not affiliated with or endorsed by Mattel. Resolve trademark, content, game-rule licensing, consumer protection, and local regulatory requirements before any commercial public release.

## QA

Run `python -m pytest -q` for engine and WebSocket acceptance tests. Test live via two devices, refresh during a turn, try illegal cards/actions, challenge +4, and confirm hand secrecy. For launch, add load testing, persistent storage, observability, and accessibility coverage.
