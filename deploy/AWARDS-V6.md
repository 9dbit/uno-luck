# UNO LUCK v1167 / rules v6

Scope: isolated PR23 QA, virtual non-purchasable/non-redeemable credits only.

## Player presentation

Header wallet shows the balance and its existing actions, without the Coin label
or virtual-Rp subtitle. The virtual-credit disclosure remains in the wallet,
About and Rules. Normal bottom hints and no-win copy do not consume space.
Recoverable network/balance errors remain visible. The wheel uses the recovered
caption clearance; safe-area boundaries and the independent PAYOUT line remain.

Successful settled hands receive an SVG yellow-gold edge runner and a diagonal
gloss. Only confirmed positive *game* payout qualifies. A NO_MATCH with a separate
promo grant never receives winning-card glow. Pending and next-round states clear
all effects. Reduced-motion users receive a static outline.

The menu contains five primary ranks and ten named bonus variants (15 patterns),
not 15 invented payout levels. Numeric sum/product each has twin/triple number
and twin/triple Draw Two variants. Color Sequence and Twin Color complete the
catalog. Variable bonus values are explicitly not a strict rank order. Disabled
categories are labeled as such. Wild +4/Skip/Reverse pairs are not newly invented
as paying outcomes.

## Versioned color-pair rule

With an active economy, a new v6 hand containing at least two colored cards of
the same color pays its configured COLOR_PAIR multiplier unless an existing
rank/numeric/sequence award already takes precedence. Exactly one base prize.
The v5 classifier remains unchanged for old snapshots. No history is rewritten.
The unconfigured legacy prototype continues its pre-economy behavior.

Published probabilities, multipliers, config revision and theoretical payout
distribution are NOT automatically changed. In particular a color lane with
0% weight remains unsampled until an administrator reviews and publishes new
weights. The generator preserves each chosen lane; if an old NO_MATCH template
would now visibly contain a winning color pair, it replaces only that template
with a real NO_MATCH hand, never rerolls the prize category.

Thus these changes do not silently fund more wins or publish a new economic
preset. They make displayed hands, the award classification and the catalog
consistent. More frequent standalone Twin Color awards require an explicit
reviewed odds configuration, separately from this release.

## Verification

`tests/test_award_engine.py` checks the pair rule, no stacking, 15 valid catalog
patterns, unchanged theoretical RTP, single credit and replay, and a paid v5
zero-win snapshot completing under its old rules. `tests/qa_awards.py` tests
Chromium/WebKit mobile and landscape, gold outlines, reduced motion, false promo
win rejection, hidden header labels, error visibility and sound-manifest equality.
Physical iPhone acceptance and full historical visual suite remain separate.
