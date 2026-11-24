# XDPLAY virtual demo release

This release offers only free, non-purchasable, non-redeemable demo credits.
It does not qualify or activate the separate provider/native-wallet integrations.

Deploy to a new production service with one replica and a fresh `/data` volume.
Do not clone staging variables, database, sessions, or mutable sound storage.
The bundled public audio snapshot preserves the eight published cues, trims,
fades, repeat settings and mixer at revision `801acad084900b626931ffa1`.
Startup verifies audio hashes and initializes only the independent demo volume.

Required configuration:

- `UNO_DEPLOYMENT_TIER=production`
- `UNO_RELEASE_MODE=virtual-demo`
- `UNO_VIRTUAL_DEMO_ENABLED=0` until release checks pass; `1` enables virtual demo only.
- `UNO_ALLOWED_ORIGINS=https://uno.xd-play.com,https://uno-demo-web-production.up.railway.app`
- `UNO_SPIN_DB_PATH=/data/game/demo.sqlite3`
- `UNO_SOUND_STORAGE_DIR=/data/sounds`
- `GAMEOPS_BRIDGE_ENABLED=0`, `GAMEOPS_WALLET_COMMANDS_ENABLED=0`
- No Sound Studio master token or provider credentials.

Only successful GET `/play/` may be framed by `https://xd-play.com`.
The root document, APIs, errors and assets deny framing. APIs remain same-origin;
same-site sibling subdomains are not trusted. Writes require a session-derived
CSRF token and exact Origin. Demo cookies use the `__Host-` prefix, Secure,
HttpOnly and SameSite=Lax. Legacy gameplay, admin, editor, publishing and WS
surfaces are not admitted. Payload and request/session budgets are bounded.

`/health` reports the deployment SHA, release, demo admission and money-disabled
flags. Check HTTPS, published audio, assets, real browser audio gesture,
refresh/reconnect, controls, and the portal iframe before activating the registry.

Emergency stop: set `UNO_VIRTUAL_DEMO_ENABLED=0` and redeploy this service,
then close UNO in the portal registry/catalog/status and deploy the portal.
Preserve the production volume. Never point the production domain to staging.
SQLite online backup supports consistent copies; restore only on a separate
volume with admission closed and verify integrity, balances and retry receipts.
This release includes logical restore and container restart tests, not physical
disaster recovery or a qualification for financial use.
