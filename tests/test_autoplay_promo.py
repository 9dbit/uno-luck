"""Color prizes and transparent AUTO promotional session contracts."""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from app import economy, orbit, spin
from app.main import app

CLIENT_HEADERS = {"x-uno-client": "spin-ui"}
ADMIN_KEY = "local-qa-only-virtual-economy-admin"
ADMIN_HEADERS = {"x-uno-sound-admin": ADMIN_KEY}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("UNO_SPIN_DB_PATH", str(tmp_path / "auto_test.sqlite3"))
    monkeypatch.setenv("UNO_SOUND_ADMIN_TOKEN", ADMIN_KEY)
    spin.INITIALIZED.clear()
    orbit._initialized.clear()
    with TestClient(app) as c:
        assert c.get("/api/orbit/state").status_code == 200
        yield c


def request_pick(c, seq, phase, stake, session_id):
    return c.post("/api/orbit/pick", headers=CLIENT_HEADERS,
        json={"request_id": f"autoplay-round-{seq}-phase-{phase}-unique",
              "stake": stake, "auto_session_id": session_id})


def color_config():
    data = economy.PRESET.model_dump(mode="json")
    data["percentages"].update({
        "NO_MATCH": "89.4847", "COLOR_PAIR": "1.0000",
        "COLOR_SEQUENCE": "0.2500",
    })
    return economy.Config.model_validate(data)


def test_existing_economy_upgrades_with_color_lanes_disabled():
    old = economy.PRESET.model_dump(mode="json")
    old["percentages"].pop("COLOR_PAIR")
    old["percentages"].pop("COLOR_SEQUENCE")
    migrated = economy.Config.model_validate(old)
    assert migrated.percentages["COLOR_PAIR"] == 0
    assert migrated.percentages["COLOR_SEQUENCE"] == 0
    assert economy.rtp_percent(migrated) == pytest.approx(economy.rtp_percent(economy.PRESET))


def test_color_sequence_pair_zonk_and_rank_priority():
    cfg = color_config()
    make = lambda faces, colors: [dict(face=f, color=c) for f,c in zip(faces, colors)]
    assert economy.classify(make(["1","8","5"], ["red","red","blue"]),cfg) == ("COLOR_PAIR",2,None)
    assert economy.classify(make(["2","3","9"], ["red","red","blue"]),cfg) == ("COLOR_SEQUENCE",4,None)
    assert economy.classify(make(["2","3","4"], ["red"]*3),cfg) == ("COLOR_MATCH",40,4)
    assert economy.classify(make(["2","2","4"], ["red","red","blue"]),cfg) == ("PAIR_SUM",8,None)
    assert economy.classify(make(["1","8","5"], ["red","green","blue"]),cfg) == ("NO_MATCH",0,None)
    out = economy.simulate(economy.Simulation(config=cfg, stake=10, turnover_rp=400000,
                                            auto_sessions=2, auto_paid_rounds=10))
    assert out["projection"]["promotional_cost_expected_rp"] > 0
    assert out["projection"]["auto_bonus_min_rp"] < out["projection"]["auto_bonus_max_rp"]
    assert out["projection"]["net_result_rp"] == pytest.approx(
        out["projection"]["period_expected_surplus_rp"])
    assert out["projection"]["max_auto_sessions_expected"] >= 0
    assert out["projection"]["max_auto_sessions_high_gift"] <= out["projection"]["max_auto_sessions_expected"]
    assert out["projection"]["max_auto_by_paid_turnover"] == 100
    assert out["projection"]["available_extra_auto_sessions_expected"] == max(
        0, out["projection"]["max_auto_sessions_expected"] - 2)

    impossible=economy.simulate(economy.Simulation(
        config=cfg, stake=10, turnover_rp=4000,auto_sessions=5,auto_paid_rounds=10))
    assert impossible["projection"]["planned_auto_exceeds_paid_turnover"] is True
    assert impossible["projection"]["feasible_expected_pool"] is False


def test_all_ten_free_spins_and_five_independent_promotional_credits(client, monkeypatch):
    monkeypatch.setattr(orbit, "choose_cards", lambda: [
        {"color":"red","face":"1"}, {"color":"yellow","face":"4"},
        {"color":"green","face":"8"}])
    request = {"request_id": "auto-start-test-unique-001", "stake":10, "paid_rounds":1}
    started = client.post("/api/auto/start", headers=CLIENT_HEADERS, json=request)
    assert started.status_code == 200, started.text
    opened = started.json()
    assert opened["created"] is True
    assert opened["gift"]["free_spins"] == 10
    assert opened["gift"]["voice"] == "Free Spiinnn!"
    session_id = opened["session"]["id"]

    state_before = client.get("/api/auto/state").json()["session"]
    assert state_before["reserved_bonus_coin"] >= 15
    resumed = client.post("/api/auto/start", headers=CLIENT_HEADERS,
        json={**request,"request_id":"auto-resume-test-unique-002"}).json()
    assert resumed["resumed"] is True
    assert resumed["session"]["id"] == session_id

    outputs = []
    for index in range(1, 12):
        for phase in range(1,4):
            result = request_pick(client,index,phase,10,session_id)
            assert result.status_code == 200, (index,phase,result.text)
            body = result.json()
        assert body["round"]["complete"] is True
        assert body["round"]["combo"] == "NO_MATCH"
        assert body["round"]["payout"] == 0
        assert body["round"]["free_spin"] is (index > 1)
        outputs.append(body)
    assert client.get("/api/auto/state").json()["session"] is None
    assert outputs[0]["account"]["balance"] == 990
    gifts = [x["round"]["promo_coin"] for x in outputs]
    assert gifts[0] == 0
    assert sum(value > 0 for value in gifts) == 5
    assert 15 <= sum(gifts) <= 50
    assert outputs[-1]["account"]["balance"] == 990 + sum(gifts)

    replay = request_pick(client,11,3,10,session_id)
    assert replay.status_code == 200 and replay.json()["replayed"] is True

    db = orbit.open_db()
    summary = db.execute("""SELECT COUNT(*) total, SUM(charged_stake) paid,
        SUM(payout) card_payout, SUM(promo_coin) gift_payout,
        SUM(CASE WHEN charged_stake=0 THEN 1 ELSE 0 END) free
        FROM orbit_rounds""").fetchone()
    assert summary["total"] == 11
    assert summary["paid"] == 10
    assert summary["free"] == 10
    assert summary["card_payout"] == 0
    assert summary["gift_payout"] == sum(gifts)
    assert db.execute("SELECT COUNT(*) FROM spins").fetchone()[0] == 1
    assert db.execute(
        "SELECT COUNT(*) FROM ledger WHERE reason='auto_promotional_gift'"
    ).fetchone()[0] == 5
    db.close()

    report = client.get("/api/admin/economy/performance?days=1",
                        headers=ADMIN_HEADERS)
    assert report.status_code == 200, report.text
    metrics = report.json()
    assert metrics["turnover_coin"] == 10
    assert metrics["regular_payout_coin"] == 0
    assert metrics["promotional_payout_coin"] == sum(gifts)
    assert metrics["free_rounds"] == 10
    assert metrics["gross_coin"] == 10 - sum(gifts)
    assert metrics["pending_bonus_liability_coin"] == 0
    wallet = client.get("/api/orbit/state").json()["recent"]
    assert len(wallet) == 8 and all(round_["free_spin"] for round_ in wallet)


def test_period_margin_target_accounts_for_guaranteed_promotions():
    cfg = economy.PRESET
    result = economy.target_config(economy.Target(
        config=cfg, margin_percent="10", turnover_rp=1000000,
        costs_rp=0, auto_sessions=1, auto_paid_rounds=10, stake=10))
    assert abs(result["actual_period_margin_percent"] - 10) < .05
    assert result["actual_margin_percent"] > 10
    assert result["actual_period_surplus_rp"] > 0

    with pytest.raises(Exception):
        economy.target_config(economy.Target(
            config=cfg, margin_percent="10", turnover_rp=1000000,
            costs_rp=0, auto_sessions=100, auto_paid_rounds=10, stake=10))
