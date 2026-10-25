# UNO LUCK DEV-02 / v1.1.68

Separate branch: feat/uno-v1168-dev02-rules-20261025.
Parent: fd3232744cc16d70dd8b4daebd3aad043d9f6e8a (DEV-01 application plus one test fix).
DEV-01 service and URL MUST NOT be redeployed or repointed by this revision.

## Scope

Informative redesign of both Game Rules and Rank Info using one guide:
- Rank & Bonus, Cara Main and Ketentuan tabs; keyboard navigation and fixed modal close/back.
- All 15 real award patterns, ordered by attainable maximum payout descending.
- Display position 01-15 is NOT an extra settlement rank. Existing rank IDs 1-5 and jackpot sounds stay intact.
- Exact maximum for triple Draw Two: product 8x, sum 6x, subject to a smaller configured cap.
- Read-only BET examples update illustrative WIN and NET. They never change game stake, account, RNG or wallet.
- Sampling-active flags are derived from the configured category weight without exposing percentages.
- Twin Color support is not confused with a nonzero sampling weight. Inactive color lanes are visibly labeled.
- Explains numeric-before-rank priority, no stacking, zero-product fallback, virtual credits and conditional AUTO promotions.

## Isolation

No economy publishing, Sound Cloud writes, data migrations, primary staging changes or merges.
New QA must use a new service, URL, local database and sound storage scope. A new origin does not retain the old guest balance.
Runtime preset bootstrap, if used, is new isolated demo data and is not a copy of authenticated old runtime configuration.

## QA

Dedicated workflow qa-rules-v1168.yml checks metadata, examples and settlement invariants, then actual profile-menu navigation in Chromium/WebKit at five viewport sizes.
Existing Full Visual CI timeout in visual_qa_player_panels.py is inherited and remains a separate release gate; this task does not silently remove it.
Exact SHA, screenshot review, CI result and new service URL are to be recorded in a new DEV-02 checkpoint after verification.
