# UNO LUCK approved 3D art v1

All files are optimized WebP assets from the approved reference art. The runtime path is `/assets/art/v1/<file>.webp`, under FastAPI static mount.

- Use the separately exported `spin.webp`, `turbo.webp`, `auto.webp`, `gift.webp`, `avatar.webp`, and `menu.webp` for independent hit targets.
- Dynamic cards must render text and face color in the DOM. `card-blue-8-reference.webp` is an art reference, never a server result.
- `betting-frame-empty.webp` has its baked value glyphs removed, allowing live accessible numeric labels and count-up; `betting-bar-reference.webp` is only the original visual reference.
- `dragon-wheel-reference.webp` is a flat composition; `dragon-head-fx.webp` is a derived head layer for compositor animation. True body deformation requires separate head/spine/tail layers or skeletal mesh animation (Rive/Spine).
- Only server-confirmed results can trigger win, payout, or jackpot visuals. The current API has COLOR_MATCH and NO_MATCH; it does not offer a jackpot prize tier.
- Keep reduced-motion, audio toggle, no-scroll safe areas, and virtual-only coin constraints.
