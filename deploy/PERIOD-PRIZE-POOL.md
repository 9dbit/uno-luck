# UNO LUCK | Period Prize Pool (virtual credits only)

Design record for staging review. No real money, deposits, cash-out, or external prizes.

## Gameplay and classification
Each round shows three server-drawn cards. Apply exactly one prize in descending
priority: numeric pair / Draw Two, existing Rank 1-5, matching-color numeric
sequence, two-color match, otherwise ZONK (zero game payout).
Existing three-color straight remains Golden Match. A two-color numeric
sequence requires adjacent displayed cards of the same color, with consecutive
numeric faces; an unordered pair does not qualify for the sequence prize.
Color pairs and sequences are distinct probability categories in Economy Lab.
Historical rounds keep the settlement rules and multiplier snapshot they started with.

## Auto Play promotion
The requested promotion contains ten free spins and five promotional awards
of 30%, 50%, or 100% of the paid Auto batch's total nominal BET.
The award count and funding are promotional entitlements, not RNG outcomes.
Only placement within the ten free spins is randomized server-side.
The separate free spin rounds themselves retain independent game RNG.
The player must be told that the five promotional awards are guaranteed
and that an ordinary ZONK still yields zero **game** payout.

## Economics by period
Paid turnover = sum of actually debited BET. Payout = sum of regular and free
round prizes actually credited. Promotional credits are a separate expense.
Net virtual operator result = paid turnover - game payout - promotional credits.
RTP (regular) and effective RTP including promotions must be shown separately.
Period choices: 1, 7, and 30 days. Margins are expectations or observations,
not guaranteed operator profit; no selection of which player loses to maintain
a pool target.

For illustration, 10 paid rounds at 10 Coin each generate 100 Coin turnover.
Five bonuses each at 30% cost 150 Coin before free spin prizes.
A 10% expected regular margin cannot fund this offer if every player uses it.
The Economy Lab must show deficit and forecast the maximum sustainable
promotional participation given external non-promo turnover and promotion costs.
Do not secretly reduce any player's chance, change RNG by account, or mislabel
promotional rewards as ordinary random wins.

## Release gates
Use a feature flag, server-side authorization, persisted idempotency keys,
cap checks, database/ledger audit trail, a reproducible period simulator,
and a complete Chromium/WebKit test run. Do not publish an unbudgeted
promotion or alter the active Sound Cloud catalog.
