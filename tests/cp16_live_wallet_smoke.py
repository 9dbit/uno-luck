"""Read-only integration probe with one fresh virtual guest on isolated CP16 Railway pilot.

No admin authentication, no direct balance changes, no forced game outcomes.
Only emits a guest welcome bonus that the game itself gives every new session.
"""
import http.cookiejar
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

SOURCE = "https://uno-game-data-pilot-staging.up.railway.app"
ADMIN = "https://playground-admin-production.up.railway.app"
OUT = Path("cp16-live-evidence")
OUT.mkdir(exist_ok=True)
checks = []

def call(base, path, opener=None):
    request=urllib.request.Request(base+path,headers={"Accept":"application/json","User-Agent":"Playground-CP16-Nonmonetary-QA/1.0"},method="GET")
    open_fn = opener.open if opener else urllib.request.urlopen
    try:
        with open_fn(request,timeout=12) as r:
            data=r.read(65536)
            return r.status,json.loads(data)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read(8192))
    except (TimeoutError, OSError) as e:
        return 503, {"error":"temporary_network_failure"}

def check(name, **details):
    checks.append({"name":name,"status":"PASS",**details})
    print("LIVE_CP16_PASS "+name,flush=True)

def main():
    status,health=call(ADMIN,"/health")
    assert status==200 and health.get("version")=="0.16.0",(status,health)
    check("admin_release",version=health.get("version"))
    status,anonymous=call(ADMIN,"/api/admin/source-wallet/summary?environment=staging&game=uno-luck")
    assert status==401,(status,anonymous)
    check("anonymous_source_wallet_denied",status=401)
    status,source_health=call(SOURCE,"/health")
    assert status==200 and source_health.get("ok") is True,(status,source_health)
    check("source_game_health_preserved",virtual_only=source_health.get("money_enabled") is False)
    status,not_guest=call(SOURCE,"/api/gameops/wallet-status")
    assert status==401,(status,not_guest)
    check("anonymous_guest_wallet_denied",status=401)
    jar=http.cookiejar.CookieJar()
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),urllib.request.ProxyHandler({}))
    status,game=call(SOURCE,"/api/orbit/state",opener)
    assert status==200 and game["account"]["balance"]==1000,(status,game)
    assert any(x.name=="ul_spin_guest" for x in jar)
    check("new_guest_source_bonus",virtual_coins=1000,currency="DEMO_COIN")
    deadline=time.monotonic()+95
    status,sync=0,{}
    while time.monotonic()<deadline:
        status,sync=call(SOURCE,"/api/gameops/wallet-status",opener)
        if (status==200 and sync.get("version")=="1" and sync.get("balance")==1000 and
            isinstance(sync.get("sync"),dict) and int(sync["sync"].get("ack_version") or 0)>=1 and
            sync["sync"].get("last_status")=="matched"):
            break
        time.sleep(3)
    assert status==200 and sync.get("version")=="1" and sync.get("balance")==1000,(status,sync)
    assert isinstance(sync.get("sync"),dict) and sync["sync"].get("last_status")=="matched" and int(sync["sync"]["ack_version"])>=1,(status,sync)
    check("actual_live_signed_wallet_reconciliation",source_balance=1000,ledger_version="1",receipt_version=int(sync["sync"]["ack_version"]),state="matched")
    return {"result":"PASS","scope":"isolated_UNO_staging_virtual_credits_only","admin":ADMIN,"pilot":SOURCE,
        "checks":checks,"originalUnoModified":False,"cashOperations":False,
        "timestamp":datetime.now(timezone.utc).isoformat()}

if __name__=="__main__":
    result={"result":"FAIL","scope":"isolated_UNO_staging_virtual_credits_only","checks":checks}
    try:
        result=main()
    finally:
        (OUT/"report.json").write_text(json.dumps(result,indent=2))
        print(json.dumps(result),flush=True)
