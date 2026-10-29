# UNO LUCK DEV-08 v1.1.74 - UI layout checkpoint

Date: 2026-10-30 WIB
Base commit: 896879f6384c623136afa8e8a935a3ae8c1c0f52 (DEV-07 sound recovery)
Branch: feat/uno-v1174-portrait-card-spin-layout-20261030
Scope: isolated CSS-only visual layout. No live deploy/merge.

## Request
- Smaller DRAGON SPIN X1000 artwork
- Move BET panel down so all three cards are fully seen
- Enlarge 3-card results, spinning LED dragon area and SPIN/AUTO/TURBO buttons

## Changes
- New app/static/art/dev08-card-spin-layout.css loaded after dev06-title-cards.css
- Portrait six-row grid: header 8.2%, title 7.4%, cards 25.1%, BET 4.8%, total BET + payout drawer 6.7%, wheel 47.8%
- Prior portrait: header 8.6%, title 9%, cards 21.1%, BET 4.8%, drawer 8.1%, wheel 48.4%; BET starts lower overall
- Card area uses 2:3 ratio, card-size cap and bottom padding; title image retains approved graphic, with smaller available title space
- Spin control grows to 39% of wheel, side controls grow while staying separated from SPIN
- Narrow, short portrait and landscape overrides included
- HTML stylesheet cache version v1174; no JS/game logic edits.

## Preservation rules
- No RNG, virtual wallet, betting/payout rules, promotional entitlements, account data, Sound Cloud settings or media changes.
- DEV-07 audio recovery and DEV-06 title visuals stay in the base.
- DRAGON SPIN X1000 is only branding, not a configured real payout multiplier.

## Verification and next steps
- GitHub write and file reads only. No full Chromium/WebKit screenshots were executed in this turn.
- Verify geometry at 320x568, 393x852, 430x932, 852x393 and standalone PWA safe area.
- Confirm all 3 cards, BET frame, drawer, wheel and AUTO/TURBO buttons remain visible and tappable.
- Confirm imported audio cue manifest in independent DEV07/DEV08 QA before any release.
- No merge, no production deployment; keep the PR draft pending visual QA.
