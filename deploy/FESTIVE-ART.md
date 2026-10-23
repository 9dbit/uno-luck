# Festive player panels — assets 1151

The player lounge now shares a ruby/gold 3D art collection with Gift, Dragon Daily,
Auto Play, Bet Setting, Coin, Game Rules and Profile. About keeps the existing UNO
LUCK and Soft Tech branding, with the same festive light treatment. Sound remains
a direct toggle and uses a 3D headphone icon.

## Art source and packaging

Created with the built-in image generation tool from original prompts inspired by
the user's references. No reference branding, prize promises or odds were copied.
The five production assets are `app/static/art/festive/{gift,trophy,coins,cards,sound}.svg`.
These are image containers with embedded transparent WebP rasters, not vector art.
The generated PNGs were resized to 480px and encoded at WebP quality 84; artwork
was not redrawn during packaging. Total embedded WebP payload is 287,122 bytes.
Images are decorative, have empty alt text and explicit dimensions, and are reused
between heroes and icons. There are no perpetual animation loops or extra scripts.

## Prompt set

Shared direction: production transparent hero and 3D UI icon for UNO LUCK, centered
three-quarter view, full object with transparent margins, glossy gold metal, ruby
enamel, warm rim lighting, controlled sparkles and polished bevels. Readable as a
small icon and detailed enough for a popup hero. No text, numbers, logos, watermark,
background panel or UI. True transparent background.

- Gift: open ruby gift box, generous golden ribbon, star coins and celebratory sparkles.
- Trophy: gold/ruby championship trophy with dragon handles, crown and gold coins.
- Coins: stacked gold star coins with ruby inlays and blue/red chips.
- Cards: fan of red, blue and green UNO-inspired cards, white oval motifs, gold edges,
  and a curved clockwise gold arrow. Decorative only; never used for game outcomes.
- Sound: glossy ruby/gold headphones with floating gold music notes.

## Scope and verification

Only presentation and versioned UI URLs change. Current round stakes, queued BET,
AUTO accounting, server outcomes, payout rules and published audio are unchanged.
Hero content scrolls; modal header/close and confirmation footer remain accessible.
Coin total stays fixed above the independently scrollable history. Auto Play uses
a compact horizontal hero so round choices remain close to the opening viewport.

Local pytest: 174 passed, one existing generated-branding skip. RDC Chromium and
WebKit preview checks cover eight sizes (320x568 through desktop and landscape),
image decoding, no horizontal overflow, footer visibility, BET cancel/confirm,
tournament states/stale responses, and unchanged published audio. UI/account and
tournament responses are browser fixtures; no live ledger or gift writes.
One initial WebKit run timed out at the existing audio splash; the repeat passed.
This is simulated WebKit validation, not physical iPhone validation.

`tests/qa_player_hub.cjs` captures every panel in both engines in CI. The existing
`tests/qa_bet_next_round.cjs` additionally checks AUTO budgets, next-round BET and
one push-button cue per tap. Images are served locally with no new third-party hosts.

Render staging still uses manual specific-commit deploys because its linked branch
is older than the player-hub branch. Do not deploy the linked branch's old HEAD.
