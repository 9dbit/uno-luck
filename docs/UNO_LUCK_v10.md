# UNO LUCK v1.0 · Five-tier celebration and sound system

## Scope and reference lock
- UNO LUCK GitHub `9dbit/uno-luck`, Railway staging only. No Sites.
- Dragon image stays fixed; only content within nine metallic LED placeholders scrolls from left to right. Three result cards are top-only displays and reveal left / center / right after three server picks.
- TURBO/AUTO controls are ~2x wider than prior layout, retain separated actions and minimum practical tap areas. Betting bar is balanced across three columns, with real server-derived amounts.
- Game title is neutral `DRAGON SPIN`. `COLOR MATCH` is an outcome, with tier celebration and animation only after a server-confirmed third pick.

## Server-authoritative probability and multipliers
- Each round: 3 SPIN, 1 stake charged on first pick, unchanged 80% Color Match and 20% no-match, via cryptographically secure `secrets`.
- If winning, **one** tier is independently chosen at round creation. The tier is hidden until third pick and remains durable in SQLite. No frontend tier rolls or payout calculations.

| Rank | Display | Bonus to cost | Weight among winning rounds | Probability among all rounds |
|---|---|---:|---:|---:|
| 1 | DRAGON KING JACKPOT | 200x | 0.01% | 0.008% |
| 2 | IMPERIAL FORTUNE | 80x | 0.09% | 0.072% |
| 3 | PHOENIX COLOR BLAST | 30x | 0.40% | 0.320% |
| 4 | GOLDEN MATCH | 10x | 3.00% | 2.400% |
| 5 | LUCKY COLOR WIN | 2x | 96.50% | 77.200% |
| No match | none | 0x | n/a | 20.000% |

- Ranking is random **per independent round**, not secretly forced per 10/100/1000 cycles. Published probabilities are mathematical frequencies, not scheduled/personalized guarantees. This is crucial to integrity and prevents balance-sensitive manipulation.
- Uncapped mathematical expected payout is **195.36%** of stake (virtual currency only); because 80% of rounds win and minimum reward is 2x, this has strongly inflationary play-money economics and **must not** be described as a commercial cash-betting payout model. Wallet cap = 1,000,000 virtual coins; actual credited payout is capped and explicitly shown in UI.
- Koin virtual have **no monetary value** and cannot be deposited, bought, withdrawn, converted to cash, or used to claim money prizes. This prototype is not officially affiliated with UNO.
- Existing v0.9 `orbit_rounds` migrated with nullable `tier`; an older unfinished matching round safely retains former 2x settlement.
- Idempotency keys and ledger transactions remain; replaying an earlier phase does not reveal the secret tier or duplicate credit.

## Audio and VFX
- New original procedural music loop, impact / LED tick SFX and 5 separate fanfares in `app/static/audio/`. Independent sound themes by rarity. This is original synthesized audio, not extracted from any existing casino game.
- Web Audio decoded playback: compressor, volume 0-100, visibility pause, opt-in unlock using user gesture. iOS Safari requires a user tap for sound. Physical-device loudness depends on volume and hardware; don't promise a particular SPL or bypass user volume settings.
- Overlay art is derived from five approved storyboards with feathered transparent edges and downsized WebP. Animation uses composited transforms, rarity-specific glow, particles, audio ducking, reduced-motion respect, and auto-close with `LANJUTKAN` override.
- Menu: `Galeri 5 Celebration (demo)` previews every rank without changing player balances, cards, or outcomes. For real play, overlay appears only for a completed winning round with matching server tier metadata.

## QA / release
- Run `python -m pytest -q` and `node --check` for `orbit.js`, `sound.js`, `celebrations.js`.
- Run `python qa_v10.py` for eight Chromium viewport sizes (offline image/data-backed). Test live iOS Safari separately for audio timing, GPU frames, vibration, click accuracy, and screen safe-area.
- All changes must deploy to Railway **staging** linked to GitHub `main` and only count as released after terminal `SUCCESS` + HTTP 200 healthcheck.
