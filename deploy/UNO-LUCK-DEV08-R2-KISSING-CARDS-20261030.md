# UNO LUCK DEV-08 r2 | Kissing Cards + Gold Emissive

Date: 2026-10-30 (WIB)
Version: v1.1.74r2
Repo: 9dbit/uno-luck
Branch: `feat/uno-v1174-portrait-card-spin-layout-20261030`
PR: https://github.com/9dbit/uno-luck/pull/31
Existing QA URL: https://uno-luck-dev08-layout-qa-staging.up.railway.app/
QA service: `uno-luck-dev08-layout-qa` (Railway, staging)
Target environment ID: `c22194d6-35a2-4297-8eb6-c9f455a27f08`
QA service ID: `0324b622-bcc8-4420-bcd2-79ba11c9e676`

## User-requested visual change

1. Lower the three result cards while keeping all three complete and in the original 2:3 aspect ratio.
2. Make the bottom card edges "kiss" the upper rim of the BET/WIN/NET metal panel, with no visible empty band or clipping.
3. Make the existing DRAGON SPIN X1000 3D gold artwork noticeably brighter and emissive.

## Source edits

- `app/static/art/dev08-card-spin-layout.css`
  - Root cause: `.result-cell` inherited `place-items:center`, so the card itself stayed vertically centered even after its parent was moved to the bottom.
  - Explicitly set `place-items:end center` on the three result cells.
  - Use `gap:.6%` and nearly edge-to-edge horizontal result area padding to enlarge all three cards without changing card shape.
  - Cap card width by both container width and available height with `100cqw`, `100cqh` in supported browsers; keep viewport fallback.
  - Reduce result-card bottom padding to `clamp(2px,.32dvh,3px)` to align the card bottom near the upper decorative BET frame. Extra short portrait uses `clamp(2px,.3dvh,3px)`.
  - Apply static image `brightness(1.34) contrast(1.2) saturate(1.42)` and layered warm-white/gold/amber drop-shadows for HDR emissive artwork. No animated filter loops (iPhone GPU safeguard).
  - Keep accessible semantic text emissive in the artwork-error fallback.
- `app/static/orbit-index.html`
  - Mark `DEV-08 v1.1.74r2`.
  - Cache bust the visual CSS asset with `?v=1174r2`.
- `tests/qa_dev08_card_kiss.py`
  - Chromium/WebKit screenshot and geometry checks on 320x568, 393x659, 393x852, 430x932 portrait.
  - Require intact three cards, no horizontal overflow, card-to-BET decorative frame clearance, emissive filter, clickable controls.
- `.github/workflows/qa-dev08-card-kiss.yml`
  - Execute the browser QA against an isolated local test server; keep artifact screenshots attached to CI.

## Preservation & release gates

- No gameplay JavaScript, RNG, odds, bet configuration, payout, wallet, coin balance, or Sound Cloud mixer changes.
- Preserve original approved title art, Dragon Spin wheel asset, 3-card behavior and iPhone/PWA dimensions.
- Preserve the DEV-07 pinned read-only sound snapshot mechanism (staging scope only).
- `X1000` remains decorative branding and **does not** change an active payout multiplier.
- Use the existing Railway staging QA service and existing public URL. Production and earlier DEV services remain untouched.
- Re-pin the QA service to the final branch HEAD to deploy this CSS revision.
- Verify terminal Railway `SUCCESS`, the commit SHA, and service `/health` before announcing as deployed.
- Physical iPhone acceptance remains separate from automated browser geometry tests.

## Follow-up

Review screenshot evidence in the `uno-dev08-card-kiss-visual-qa` GitHub Actions artifact (when the workflow runs), and check the live mobile game on an iPhone 15 Pro. If a render mismatch remains, patch only this DEV-08 QA branch until visually accepted.
