# UNO LUCK v0.8 | Single Dragon Wheel Engine

Status: staging-ready gameplay engine update. One wheel; three read-only result cells. Virtual credits only.

## Engine contract

1. The only rotating cards are the 17 individually rendered 3D cards in `#orbit-ring`, fitted to the upper semicircle of the approved stationary dragon wheel illustration.
2. Pressing SPIN starts a 360-degree compositor-only animation while `POST /api/orbit/pick` runs. The server remains authoritative for the selected card, cost, three-spin sequence, and outcome. The motor then eases to the authoritative card at the fixed top pointer. Each selected card receives an independent 360-degree vertical reveal.
3. The three read-only result cells at the top fill left, middle, then right. They never spin or perform reel animations. Idle 6–3–8 cards are illustrations, not a paid round result.
4. Server: one stake charged at pick 1; pick 2 free; pick 3 settles; 80% Color Match chance (as documented in the API) and 2× stake returned on a match. Payment, cash deposit, and withdrawal are NOT implemented. A per-request idempotency key is preserved across uncertain network failures.
5. `Turbo` changes timing only. `Auto` has the existing maximum of ten rounds. They cannot change result probabilities.

## GPU and responsive design

- All active wheel animation writes only `transform` and `opacity`, with geometry cached and invalidated on resize. The dragon is a static 3D render in the approved location and proportion; success uses mild 2.5D transform.
- 8 transparent optimized WebP images are independently versioned under `app/static/art/v2/`; the symbol and numbers are DOM text, not baked into card sprites.
- CSS includes `100dvh`, safe-area insets, explicit min-width zero for grid tracks, no root scrolling and a landscape arrangement. `prefers-reduced-motion` snaps the pointer without rotation.
- The approved metallic betting strip is below the SPIN area; its values animate from the server result.

## Future limitations

- A true independently bendable dragon requires segmented illustration and a skeletal rig (Rive/Spine). The current dragon is one approved artwork, with a light success motion. The game API defines `COLOR_MATCH` and `NO_MATCH`, not an additional jackpot reward tier.
- Persist the staging database via a Railway volume or managed database before relying on continuity through redeploys.
