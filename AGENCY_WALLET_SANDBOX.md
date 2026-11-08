# UNO native wallet sandbox — 8 November 2026

This opt-in runtime uses the Playground central wallet for the actual three-card Orbit game. The ordinary guest service is unchanged when `AGENCY_WALLET_MODE` is unset. No legacy local balances are migrated.

## Deployment

Use a separate service with the default `Dockerfile`, which drops privileges before serving both guest and sandbox modes. The optional `Dockerfile.agency` is sandbox-only. Run one Uvicorn worker and one replica, and a persistent volume mounted at `/data`. Set:

- `AGENCY_WALLET_MODE=sandbox` (live mode is rejected on startup)
- `UNO_AGENCY_DB_PATH=/data/agency.sqlite3`
- `AGENCY_WALLET_ORIGIN`: HTTPS Playground sandbox backend origin
- `AGENCY_WALLET_KEY_ID` and `AGENCY_WALLET_SECRET`: a server-only, game `uno-luck`, environment `sandbox` key registered in Playground
- `PORT=8000`

Railway start: `python -m app.agency_start`. The sandbox image sets ownership of the dedicated volume directory and drops to UID/GID 10001 before importing the app. Startup and `/health` validate the database. For local non-Railway QA use `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log`.

`AGENCY_WALLET_LOCAL_QA=1` allows a loopback HTTP wallet for isolated tests only; never set it on Railway. Keep the volume when updating the deployment. Back up SQLite with its online backup API; do not copy only the main file while WAL transactions are active. SQLite serializes reservation/settlement requests, including network waits; this sandbox is not a horizontally scalable production runtime.

## Launch and transaction contract

The storefront obtains a short-lived token from Playground and navigates to `/#playground_launch=…`. Browser code removes the fragment, retains it in sessionStorage only while redemption is pending, then POSTs it to the same-origin native server. HMAC credentials never reach browser code. Redemption retries use a durable request identity; the opaque session cookie is HttpOnly, SameSite Strict, Secure on HTTPS.

Canonical identity is `tenant_id + player_id`, not a guest account or browser cookie. A new launch resumes that player's incomplete round. UNO accepts `coin_scale=0` only; other precision is rejected explicitly. The UI is driven by authoritative central balance and reserved balance. Daily gifts, refill, guest-spin APIs and local profile writes are unavailable on this service.

Before any wallet request, SQLite commits the selected three cards, tier, full payout, round reference and requested phase. The first click reserves the stake and maximum 200× payout. Second click reveals card two; third click settles the immutable outcome. Unknown timeouts retain the same intent, with no reroll, local refund or local credit. Duplicates must match stake, phase and round ID. The maximum reservation is conservative and independent of the hidden outcome.

A background worker checks every 30 seconds. Rounds abandoned for 15 minutes settle using the stored outcome, including losing rounds. They are never selectively refunded. The worker resumes after process restart; prolonged service outage delays completion but does not erase the round. Failed settlement stays pending for retry/reconciliation. Definitively rejected initial reservations reveal no cards and do not create a paid round.

## Validation

- 118 pytest tests pass, including pre-existing guest tests and 11 native scenarios: duplicate payloads, unknown responses after central commit, concurrent clicks, restart/new launch, cross-tenant isolation, precision, denied guest APIs, settlement on abandonment and live-mode rejection.
- Playground `tests/agency-native-uno.cjs` runs the real FastAPI server, signed central API and SQLite with Chromium at 393×852. It restarts the game server after card one, completes the same round and checks the central settlement journal and reconciliation.
- Run from Playground with `UNO_NATIVE_PATH=/path/to/uno-luck NATIVE_PYTHON=/path/to/venv/bin/python npm run test:agency`.
- Tests use disposable balances and PGlite. They do not transfer money, mutate customer wallets or certify external payment settlement.

## Economic boundary

Existing native math is unchanged: 80% Color Match and weighted 2×/10×/30×/80×/200× tiers. Expected gross return from these constants is 195.36% of stake before any legacy guest cap. Agency settlement does not apply the guest balance cap. This economics is suitable only for the explicitly labeled simulator until an operator-approved game economics decision and further certification. No live activation is implemented by this PR.
