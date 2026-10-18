# UNO LUCK SPIN | Color Match Staging

Main mode: **SPIN**. Reference: the supplied mobile Pro screenshot, not turn-based Classic UNO.

Three cards appear after pressing **PLACE**. This first implementation deliberately follows **only the previously confirmed payout**: three cards with the same color return **2×** the selected virtual PLACE cost. Any other color combination returns zero. Each card's color is selected independently and uniformly from four options, giving 6.25% probability of 3 matching colors; numbers and action symbols are cosmetic in this staging paytable. Expected virtual credit return is 12.5% of spend per spin under these assumptions. This is a staging rule, **not a copy of undocumented production probability rules**.

All balances are **non-purchasable, non-transferable, non-redeemable demo credits**. No deposits, fiat top up, monetary stakes, real-value prizes or withdrawals. Balance starts at 1,000; daily bonus 250 and free refill 1,000 are each once per Asia/Jakarta day. Cost choices: 10/25/50/100/250. Max balance 1,000,000. Auto Spin is client-driven with maximum 10 spins per activation; Turbo shortens visual delays and neither changes the server RNG.

## Source structure

- `app/spin.py`: FastAPI guest session and SQLite accounting; per-session cookies are HttpOnly; same-origin write guard, one transaction per spin, unique request idempotency, immutable ledger, and server-side CSPRNG.
- `app/static/spin-index.html`, `spin.css`, `spin.js`: mobile-first responsive Spin UI, including 3D metallic cards, stage, PLACE, Turbo, Auto, coins, gifts, result history, profile, odds modal, and sound effects.
- `app/static/spin-icon.svg` + `spin-avatar.svg`: logo and user-approved generated character portrait.
- `tests/test_spin.py`, `tests/test_spin_ui.py`: spin accounting, probability enumeration, session separation, API guard, bonus caps and UI regressions.
- `/classic` retains the previous multiplayer prototype temporarily. It is not the canonical main game.

## Local run

```bash
pip install -r requirements.txt pytest httpx
pytest -q
UNO_SPIN_DB_PATH=/tmp/uno_spin.sqlite uvicorn app.main:app --host 127.0.0.1 --port 8080
```

The homepage `/` is Spin. `/health` reports `main_mode: spin`. Browser layout audits were run locally on width 320–1440px; mobile content scrolls vertically when necessary rather than positioning controls on top of one another.

## Railway staging persistence

Keep domain target port and `PORT` at **8080**. For persistence across redeploys, attach a Railway Volume to the application at `/data` and set `UNO_SPIN_DB_PATH=/data/uno_luck_spin.sqlite3`. One replica only: SQLite and memory-based Classic rooms are not horizontally scalable. Without a volume, SQLite defaults to `/tmp/uno_luck_spin.sqlite3` and demo balances can reset on redeploy. Classic rooms always reset on restart.

## Release limits

- **Not a real-money or commercial gambling product.** Never accept fiat, deposits, paid top-ups, money equivalents or withdrawal until a separately approved compliance and licensing design exists.
- The Spin paytable is versioned `color-match-v1-staging`; reconfirm any further multipliers with the owner before altering odds.
- Guest sessions live in browser cookies; users may lose access if they clear browser storage. Future release requires account linking and stronger audit/abuse controls.
- UNO is a Mattel trademark. This independent prototype is not affiliated with Mattel and needs an IP review before commercial distribution.
