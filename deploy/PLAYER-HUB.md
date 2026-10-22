# Player hub and Dragon Daily (Render staging)

Based on deployed audio correction f928fae. Keep the Railway source branch
untouched while its ephemeral SQLite backup remains blocked.

## Player experience
- Ruby/gold menu tiles, dedicated daily tournament entry, retained player-only
  rules/profile/sound/BET navigation. Gift remains exclusive to the header gift.
- Five visual Coin chips retain approved stakes 10/25/50/100/250. Draft changes
  apply only after confirmation. During a paid round/AUTO, the choice is queued
  for the next round after the current round and AUTO batch finish; the existing
  stake and uncertain-request retry stay unchanged.
- Animated header logo opens About UNO LUCK and Soft Tech. Explicitly distinguishes
  this custom virtual-credit game from official Mattel UNO.
- Fixed close/back and confirmation controls; scrollable content; reduced-motion
  support; safe viewport bounds and keyboard focus indicators.

## Tournament scope
Dragon Daily is an opt-in, guest-session score competition with no entry charge
or additional coin/prize settlement. Existing round stakes and payouts remain.
The server counts the first ten completed, current-rules rounds that START after
joining and FINISH before the next midnight Asia/Jakarta. Score uses the existing
server rank multiplier; bet size does not multiply points. Tied scores share rank.
Only profile names, scores and completed-round counts are public after opt-in.
The top twenty and the requesting player's own row are returned; hidden cards,
account IDs, balances and session tokens are not exposed.

Entries use a new additive SQLite table on the existing persistent disk.
No edits to old accounts/rounds/ledger/audio. Repeated joins retain joined_at.
Read requests never enroll players. Existing guest cookies remain origin-bound.
This staging competition has no anti-multi-account identity verification or
prize distribution. Future prizes/entry fees need separately approved rules.

## Validation
- 174 pytest passed, one Docker-generated branding-asset test skipped locally.
- RDC Chrome preview: eight viewport sizes, cancel/confirm BET, About tabs,
  tournament explicit join, own rank outside top twenty, fixed footer, network
  errors and delayed-response suppression. Tournament and write responses are
  browser-only fixtures; zero live game/audio/tournament writes.
- Sound manifest matches pre-test baseline (801acad084900b626931ffa1).
- New tests/qa_player_hub.cjs runs Chromium and WebKit in CI alongside the
  existing audio, LED, PWA recovery, viewport and mounted-disk suites.
- Two stale audio source assertions from the already-deployed f928fae were
  updated to require wheel-owned start/stop and sustained SPIN audio while
  preserving the music repeat preference checks.

Reference screenshot containing tournament UI could not be resolved. Available
21 October 00:30 screenshots show Railway infrastructure, not a tournament.
The new visual treatment is an original continuation of the approved game theme.
Physical iPhone acceptance remains necessary.
