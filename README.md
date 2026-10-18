# UNO LUCK SPIN v0.4 | Color Match Staging

Main mode: **SPIN**. Reference: the supplied mobile Pro screenshot, not turn-based Classic UNO.

Three cards appear after pressing **PLACE**. This first implementation deliberately follows **only the previously confirmed payout**: three cards with the same color return **2×** the selected virtual PLACE cost. Any other color combination returns zero. Each card's color is selected independently and uniformly from four options, giving 6.25% probability of 3 matching colors; numbers and action symbols are cosmetic in this staging paytable. Expected virtual credit return is 12.5% of spend per spin under these assumptions. This is a staging rule, **not a copy of undocumented production probability rules**.

All balances are **non-purchasable, non-transferable, non-redeemable demo credits**. No deposits, fiat top up, monetary stakes, real-value prizes or withdrawals. Balance starts at 1,000; daily bonus 250 and free refill 1,000 are each once per Asia/Jakarta day. Cost choices: 10/25/50/100/250. Max balance 1,000,000. Auto Spin is client-driven with maximum 10 spins per activation; Turbo shortens visual delays and neither changes the server RNG.

## Source structure

- `app/spin.py`: FastAPI guest session and SQLite accounting; per-session cookies are HttpOnly; same-origin write guard, one transaction per spin, unique request idempotency, immutable ledger, and server-side CSPRNG.
- `app/static/spin-index.html`, `spin.css`, `spin.js`: bright primary-color 3D slot-card reels, progressively stopping left to right; candy PLACE; server-confirmed Color Match burst shards/confetti and coin chimes; procedural arcade background music and separate Music/SFX toggles; fixed single-viewport mobile layout with Safari safe areas. Turbo, capped Auto, coins, gifts, history, profile, and odds modal.
- `app/static/spin-icon.svg` + `spin-avatar.svg`: logo and user-approved generated character portrait.
- `tests/test_spin.py`, `tests/test_spin_ui.py`: spin accounting, probability enumeration, session separation, API guard, bonus caps and UI regressions.
- `/classic` retains the previous multiplayer prototype temporarily. It is not the canonical main game.

## Local run

```bash
pip install -r requirements.txt pytest httpx
pytest -q
UNO_SPIN_DB_PATH=/tmp/uno_spin.sqlite uvicorn app.main:app --host 127.0.0.1 --port 8080
```

The homepage `/` is Spin. `/health` reports `main_mode: spin`. The main game uses `100dvh`, `overflow:hidden`, and portrait/landscape media queries. A Chromium interaction and viewport audit covered 11 sizes from 320×480 through 1440×900, found no page overflow, and checked that HUD, reels, summary, action buttons, and utility row do not overlap. Content stays visible in a single viewport without page scroll. Help/rules dialogs have internal scrolling only if required for accessibility. Web Audio starts after the first user gesture, in accordance with mobile browser autoplay restrictions.

## Railway staging persistence

Keep domain target port and `PORT` at **8080**. For persistence across redeploys, attach a Railway Volume to the application at `/data` and set `UNO_SPIN_DB_PATH=/data/uno_luck_spin.sqlite3`. One replica only: SQLite and memory-based Classic rooms are not horizontally scalable. Without a volume, SQLite defaults to `/tmp/uno_luck_spin.sqlite3` and demo balances can reset on redeploy. Classic rooms always reset on restart.

## Release limits

- **Not a real-money or commercial gambling product.** Never accept fiat, deposits, paid top-ups, money equivalents or withdrawal until a separately approved compliance and licensing design exists.
- The Spin paytable is versioned `color-match-v1-staging`; reconfirm any further multipliers with the owner before altering odds.
- Guest sessions live in browser cookies; users may lose access if they clear browser storage. Future release requires account linking and stronger audit/abuse controls.
- UNO is a Mattel trademark. This independent prototype is not affiliated with Mattel and needs an IP review before commercial distribution.

## v0.4 release QA

- Automated test suite: 56 tests passing for Classic regression, Spin payouts, idempotency, guest session isolation, free virtual bonuses, API rules, and UI contracts.
- Chromium visual audit: viewport sizes 320×480, 320×568, 360×740, 375×667, 390×620, 390×844, 430×932, 667×375, 768×1024, 1024×768, and 1440×900. Page viewport matches document scrollWidth/scrollHeight, no overlaps among major elements, no JavaScript exceptions.
- Three vertical reels use client-only preview symbols while awaiting server-authoritative results; final symbols and virtual credits come only from POST /api/spin/place.
- Winner animation plays only when server returns COLOR_MATCH. Current server rules do not include Wild cards or UNO Classic hand-play effects.
- Soundtrack is original synthetic Web Audio, not a copyrighted recording. Separate music and SFX preference toggles live in this browser.
- Do not deploy multiple Railway replicas before moving session and balance state to a shared datastore.


## v0.5 Boot Splash and iPhone Audio

- The user-supplied **Soft Tech** neon mark first appears on solid black, fades fully to black, then the original **UNO LUCK** red-dragon banner appears with a loading bar.
- Bundled local WebP art is served at `/assets/boot-softtech.webp` and `/assets/boot-uno-banner.webp`. No external image dependencies or third-party tracking.
- The loading bar never reports **100%** before artwork and the `/health` readiness check settle (with bounded timeouts). A timed fallback prevents a stranded loading screen. After the bar reaches 100%, the player can tap **MAIN DENGAN SUARA**, tap **LANJUT**, or let the intro finish automatically.
- Safari/iOS browsers disallow first-load audio autoplay. **MAIN DENGAN SUARA** resumes `AudioContext` during the tap gesture; on automatic entry, the first real touch or PLACE click attempts to unlock music and SFX. The app must not claim that music starts by itself without user interaction.
- Audio uses separate music and effects buses, a shared volume limiter, and stronger level-balanced synthesizer effects. Both toggles retain the player's preferences.
- All boot layers are fixed at `100dvh`; the underlying game remains hidden until the overlay fully closes. The splash CTA, panel, and progress bar stay within the safe viewport; full page scrolling is disabled.
- Quality checks: `python -m pytest -q`, then execute `tests/visual_boot_v05.py` locally when Chromium Playwright is present (uses a simulated API, browser gesture checks and responsive screenshots).
- The wallet is **demo virtual coins only**, not redeemable or withdrawable. State is currently SQLite-backed without a persistent Railway volume.


## UNO LUCK v0.6 · 3-Spin Circular Card Carousel (main route)

The `/` screen uses the approved black-red / gold design reference. One UNO LUCK
winged crest lives in the upper-left, with an orbit of 13 dynamic card fronts
rotating around the candy-red SPIN button. Individual card results use large
standalone 3D cards in a horizontal tray, **not a mechanical slot reel**.

- `POST /api/orbit/pick`: First click selects the left card and charges one
  stake. Second click selects the center card, third click selects the right
  card and settles the round. Each request uses an idempotency key. No hidden
  card is revealed before its pick.
- Color Match: exactly **80%** win probability per round, generated securely on
  the server (80 in 100 branch), with three cards sharing the same color. Winning
  payout is **2× stake**. In the remaining 20%, cards do not all share one
  color and there is no payout. This is a custom demo rule, not official UNO.
- Stakes 10, 25, 50, 100, 250 koin can be chosen from Menu before a round.
  One stake is charged for all three spin actions.
- `GET /api/orbit/state` restores unfinished rounds after reload. The server
  validates game state and changes credit balances atomically in SQLite; no
  frontend animation or client-supplied card changes the result.
- Animated orbit carousel, CSS card vibration, win shards, turbo, auto (max 10
  rounds), synthesized background music and sound effects unlocked on gesture.
- Single-screen `100dvh` layout tested at 10 sizes including 320×480 mobile and
  667×375 landscape. No horizontal or vertical body scroll.
- Original Classic at `/classic`; previous Spin at `/spin-legacy`.

**Staging virtual-only notice:** 1,000 starting demo credits, daily +250,
refill +1,000. No paid purchases, withdrawals, conversions to fiat, or cash
rewards. The current SQLite database defaults to `/tmp` and is not durable on
Railway without mounting a persistent volume and setting `UNO_SPIN_DB_PATH`.

To test: `python -m pytest -q`. UI QA uses an isolated Chromium snapshot test
with mocked APIs because HTTP localhost is blocked in the test environment;
backend state transitions are independently tested with FastAPI TestClient.
