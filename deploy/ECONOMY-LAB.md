# Virtual economy editor (1156)

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

For a reviewed first-time staging activation, an operator may run
`python -m app.activate_economy_preset` from the service shell. The command
publishes revision 1 only when no active revision exists; it never overwrites an
existing configuration. All later changes continue through authenticated,
versioned Economy Lab publishing.

| Outcome | Unconditional probability | Gross payout × BET |
|---|---:|---:|
| No match | 90.7347% | 0 |
| Numeric pair, mixed colors | 8.5656% | Sum, cap 10 |
| Numeric pair, same color | 0.4% | Product, cap 20 |
| Lucky Color Win | 0.25% | 25 |
| Golden Match | 0.04% | 40 |
| Phoenix Color Blast | 0.008% | 80 |
| Imperial Fortune | 0.0015% | 150 |
| Dragon King Jackpot | 0.0002% | 300 |

Exact draft RTP is **89.9995229%** before the account balance cap (10.0004771%
operator margin). A positive payout occurs on approximately 9.1561% of rounds,
or once per 10.92 rounds on average; this is a long-run expectation, not a timer.
Old prototype RTP
is **195.36%**, not 80%: 80% was probability of a winning category, not RTP.
The simulator separates positive payout from net profit (payout > stake).
All 280 ordered numeric triples with at least one duplicate are equiprobable
inside each numeric category, including triples and zeros. It is a weighted
virtual generator, not a physical UNO deck. 0 products may pay zero.
Sum 2,2,1 pays 5×BET; same-color 3,3,2 pays 18×BET; 9,9,9 is capped at 20×BET.
Numeric bonuses take precedence over broad Color Match and do not stack prizes.

Gameplay uses a fixed, independent server CSPRNG table. It has no per-player
odds, loss-chasing, daily quota, or adaptive outcome selection. Validation
requires exactly 100% across categories (four decimal places), each
numeric category more frequent than Lucky, strict descending rank multipliers,
and Lucky above both bonus caps. Admin may change all these values within
validated bounds. A fresh response recalculates exact probability distribution,
expected gross/net return, and 300 seeded bankroll sessions (up to 1,000 rounds).
Sessions stop when balance is insufficient and apply the same 1,000,000 Coin cap.
The chart is one sample path; quantiles and exhaustion rate are empirical, not
promises. Simulation RNG is isolated from cryptographic gameplay RNG.

Publishing is restricted to theoretical RTP 85–98% (operator margin 2–15%). It
is atomic with expected-revision conflict protection, retains all
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


## Operator target and projection

The default draft has theoretical RTP 89.9995229%, so the operator's expected gross virtual result is approximately 10.0004771% of actual BET turnover. This is not real-money revenue. The legacy active configuration has RTP 195.36%; deploying the editor does not activate the new draft.

The editor accepts a target margin or a target net virtual amount. Net target converts to margin using `(net target + entered costs) / turnover * 100`. Turnover is total stakes, not wallet balances or deposits. Costs include only values entered by the admin; omitted bonuses, infrastructure costs and other expenses are not automatically counted. Projections are expectations before the account cap, not guaranteed profit.

`POST /api/admin/economy/target` is authenticated and read-only. It scales all seven reward category probabilities proportionally toward the desired RTP, rounds to four decimals, and assigns the remainder to NO_MATCH. Stake steps, multipliers and caps remain unchanged. The result reports the actual margin and rounding difference, rejects invalid/out-of-range targets and any target that would silently remove a previously nonzero category. It never publishes. Admin must review the updated simulation and explicitly apply the draft. Arbitrary later odds/multiplier edits recompute actual results but do not silently force the draft back to its target.

`GET /api/admin/economy/performance?days=30` is authenticated and read-only. It
aggregates completed rounds across all guest accounts for 1–365 days: distinct
players, rounds, BET turnover, payout, gross result, actual RTP, active revision,
and combo totals. This is the operator-wide result, not a single player's wallet.
The admin UI compares it with theoretical RTP and explicitly warns that small
samples can diverge. No probability data is added to player-facing responses.

## Admin password

Economy Lab and Sound Studio accept an optional password configured exclusively as
`UNO_ADMIN_PASSWORD_HASH` on the service. The hash uses PBKDF2-SHA256, 600,000
iterations and a random 16-byte salt. No password or deployed hash belongs in Git.
The existing `UNO_SOUND_ADMIN_TOKEN` remains valid and still requires 32 characters.
Same-origin checks apply to both methods. Password checks allow eight attempts per
server-observed client address per 60 seconds, per worker; successful checks reset
the counter. This limiter is process-local and resets on restart. Forwarding
headers are not trusted as identities. Proxied clients may share a limit.
Browser credentials live only in memory and must be re-entered after reload.
Adding or rotating the password does not publish audio or economy configuration.
