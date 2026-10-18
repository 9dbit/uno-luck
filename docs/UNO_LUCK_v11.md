# UNO LUCK v1.1: Server-triggered COLOR MATCH

**Frontend-only visual/audio release.** The jackpot ranks, RNG distribution, virtual settlement, database, and payout service are unchanged from v1.0.

## Trigger sequence

1. Idle: neutral `DRAGON SPIN` header, `color-match-burst` hidden.
2. Each SPIN selects exactly one backend-issued card. The LED wheel injects the selected card at left and stops it at the center pointer, then transfers to the next of three result slots.
3. After SPIN 3, `confirmed.round.complete` is checked. A valid `COLOR_MATCH` and matching three card colors permit `UNOLuckMatch.reveal()` to animate the **separate** `art/v4/color-match.webp` title asset.
4. Then `UNOLuckCelebration.present()` shows rank 1 fullscreen, or ranks 2–5 inside the Dragon Spin area. Preview gallery *never* activates the conditional title or credits.
5. Continue, timeout, visibility change, or next SPIN clears the title and celebration. Refreshing a previous winning round does not replay the title.

## Mobile visual safeguards

- `art/v4/lava-temple.webp` optimized from the approved fire-temple reference, with blurred radial light and no hard-edged conic wedges.
- Three result cards preserve their perspective and never become a second spin engine.
- Nine fixed LED sockets with bright full-frame faces; color/number content alone travels left to right.
- BET/PAYOUT/WIN labels retain the existing server-confirmed numeric IDs.
- TURBO/AUTO raised higher without displacing the SPIN center or dragon.
- Local celebration overlays share the exact `.wheel-area` bounds; global Rank 1 alone covers the viewport.

## Audio

`UNOLuckSound.celebration(rank)` mixes the matching tier fanfare with a gentle compressor-controlled 180Hz/330Hz impact transient. Test through **Menu → Tes Suara Meriah** after enabling sound from a gesture. Check iOS media volume and silent-mode behavior; browser audio cannot override hardware/system mute.

## Validation

Run `python -m pytest -q tests`, `node --check app/static/orbit.js`, `node --check app/static/art/match-announce.js`, `node --check app/static/art/celebrations.js`, `node --check app/static/art/sound.js`. An additional Playwright offline QA harness verifies 8 viewports and state transitions using embedded real artwork.

### Reduced-motion correctness correction

Previously, `settle()` called `complete()` (which cleared `this.pending`) before returning it when Reduce Motion was enabled. This caused completed server picks to appear as failures in reduced-motion browsers. The revised implementation saves the acknowledgment Promise before resolving/clearing it, so the 3-SPIN state machine works in both animation modes. The browser QA includes an end-to-end 6→3→8 result with all three picks and a real conditional match title.
