# UNO LUCK v0.9 | Approved LED wheel and transfer engine

## Visual lock

- Master reference: `IMG_3035(1).png`, portrait 9:16, one top-left winged UNO LUCK logo.
- Preserve dragon/wheel illustration aspect ratio and red/black background. No second rotating slot device.
- Three metal cards on top are **read-only results**. The user-approved Biaya/Kembali/Selisih bar stays between results and wheel.
- Nine permanent gold wheel placeholders are overlaid with LED-style color, pixel grid and animated text; **no DOM wheel-position transforms**.
- Pointer fixed at the top-center LED window. SPIN is the sole trigger.

## Client animation contract

1. Tap SPIN: animate the candy button, start shifting the LED card contents **left-to-right**.
2. POST `/api/orbit/pick` with an idempotency key. If network delays, LED keeps rolling, but never invents a paid result.
3. On confirmed server card, inject it into the leftmost LED window and shift four more frames; card stops under the center gold pointer.
4. Animate a single flying metal card from that pointer into the left, center, or right top result cell. Only then paint the server-confirmed result cell.
5. SPIN #1 charges one full round stake, SPIN #2 and #3 charge nothing; SPIN #3 settles. Colour-match animation and dynamic amounts follow server payout.
6. The original 80% Colour Match chance and 2x stake payout are unchanged and apply to **non-redeemable virtual credits only**. No cash transfers, top-ups for money or withdrawals.

## Performance and safety

- Frame geometry is all percentages within a non-stretched square wheel image.
- Max nine DOM text/face updates per LED tick (~50–116ms), not expensive 3D transforms on the ring.
- WAAPI `transform` animates just one flying card; optional `prefers-reduced-motion` immediately locks it.
- Small screens and landscape are hardened for no root scroll.
- Reconnect uses existing pending request id/recovery and only server-confirmed cards.

## Verification

Run `python -m pytest -q`, `node --check app/static/orbit.js`, `node --check app/static/art/ledwheel.js`; optional `python qa_v09.py` tests browser viewport and simulated three-spin result. Actual iOS Safari sound and FPS still require device testing.
