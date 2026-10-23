# Virtual economy editor (1152)

`/admin` → Economy Lab. Uses the existing admin token through the authenticated
`/api/admin/economy` endpoints. No audio manifest writes. Credentials stay in
page memory; the password input is cleared after use. Public rules expose
payout rules and stake choices, never category probabilities or config snapshots.

1 Coin represents Rp40 **virtual**; no money, purchases, withdrawals, or currency
conversion. Existing balances, welcome credit, gifts, ledger and account cap
remain unchanged. Minimum stake is 10 Coin = Rp400 virtual. Draft steps are
Rp400 / 800 / 1,000 / 2,000 / 4,000 / 10,000. Steps can be edited in the admin.

## Draft, not automatic activation

Existing behavior remains active on deploy until an authenticated administrator
presses Apply. The initial draft is intentionally distinct from the old prototype:

| Outcome | Unconditional probability | Gross payout × BET |
|---|---:|---:|
| No match | 93.359% | 0 |
| Numeric pair, mixed colors | 5% | Sum, cap 10 |
| Numeric pair, same color | 1% | Product, cap 20 |
| Lucky Color Win | 0.5% | 25 |
| Golden Match | 0.1% | 40 |
| Phoenix Color Blast | 0.03% | 80 |
| Imperial Fortune | 0.01% | 150 |
| Dragon King Jackpot | 0.001% | 300 |

Exact draft RTP is **79.025%** before the account balance cap. Old prototype RTP
is **195.36%**, not 80%: 80% was probability of a winning category, not RTP.
The simulator separates positive payout from net profit (payout > stake).
All 280 ordered numeric triples with at least one duplicate are equiprobable
inside each numeric category, including triples and zeros. It is a weighted
virtual generator, not a physical UNO deck. 0 products may pay zero.
Sum 2,2,1 pays 5×BET; same-color 3,3,2 pays 18×BET; 9,9,9 is capped at 20×BET.
Numeric bonuses take precedence over broad Color Match and do not stack prizes.

Validation requires exactly 100% across categories (four decimal places), each
numeric category more frequent than Lucky, strict descending rank multipliers,
and Lucky above both bonus caps. Admin may change all these values within
validated bounds. A fresh response recalculates exact probability distribution,
expected gross/net return, and 300 seeded bankroll sessions (up to 1,000 rounds).
Sessions stop when balance is insufficient and apply the same 1,000,000 Coin cap.
The chart is one sample path; quantiles and exhaustion rate are empirical, not
promises. Simulation RNG is isolated from cryptographic gameplay RNG.

Publishing is atomic with expected-revision conflict protection, retains all
config revisions, and snapshots full config plus derived multiplier into every
new paid round. Changing or removing a stake never blocks completion/replay of
an already paid round. Legacy rounds keep old payouts. Settlement independently
classifies saved cards against the snapshot and blocks inconsistent records.
Retries preserve the existing idempotent ledger transaction. No schema rebuild
or balance migration. Tournament points remain the existing fixed rank scores;
numeric bonuses earn zero tournament points and no celebration.

Player feedback uses a small +Coin popup, existing animated wallet numbers,
and a separate synthesized tadaa respecting master/SFX settings. Safari media
fallback uses a silently gesture-primed original MP3 audio element; published cues are
not reset or overwritten. Physical iPhone verification remains separate from
simulated WebKit tests.

Configured celebration payouts use existing clean 3D trophy artwork because the
legacy tier illustrations contain baked-in 2×/10×/... labels. The five rank
animations and audio cues remain. The HUD range is derived from public rules.
