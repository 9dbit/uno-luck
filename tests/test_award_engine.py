"""Rules-v6 regression: real awards, frozen history, exact category budgets."""
import json
import pytest
from fastapi.testclient import TestClient
from app import award_engine, economy, orbit, spin
from app.main import app


def hand(faces=('1','7','9'), colors=('yellow','blue','yellow')):
    return [dict(face=str(f),color=c) for f,c in zip(faces,colors)]


def test_color_pair_is_a_real_win_without_rewriting_v5():
    cfg=economy.PRESET
    cards=hand()
    assert economy.classify(cards,cfg)==('NO_MATCH',0,None)
    assert award_engine.classify(cards,cfg)==('COLOR_PAIR',2,None)
    assert cfg.percentages['COLOR_PAIR']==0  # No implicit configuration publish.


def test_numeric_and_primary_awards_have_priority_no_stacking():
    cfg=economy.PRESET
    assert award_engine.classify(hand(('3','3','2'),('blue',)*3),cfg)==('PAIR_PRODUCT',18,None)
    assert award_engine.classify(hand(('2','2','1'),('red','blue','red')),cfg)==('PAIR_SUM',5,None)
    assert award_engine.classify(hand(('6','0','6'),('blue',)*3),cfg)==('COLOR_MATCH',25,5)
    assert award_engine.classify(hand(('3','4','5'),('blue',)*3),cfg)==('COLOR_MATCH',40,4)
    assert award_engine.classify(hand(('+4',)*3,('wild',)*3),cfg)==('COLOR_MATCH',300,1)
    assert award_engine.classify(hand(('WILD','+4','WILD'),('wild',)*3),cfg)==('NO_MATCH',0,None)


def test_no_match_template_repair_does_not_reroll_probability_lane(monkeypatch):
    calls=[]
    def original(config):
        calls.append(config)
        return hand()
    monkeypatch.setattr(economy,'draw',original)
    for _ in range(100):
        result=award_engine.draw(economy.PRESET)
        assert award_engine.classify(result,economy.PRESET)==('NO_MATCH',0,None)
        assert len({c['color'] for c in result})==3
    assert len(calls)==100


def test_paid_lane_and_configuration_unchanged(monkeypatch):
    cfg=economy.PRESET
    before=cfg.model_dump_json()
    for cards in [hand(('3','3','2'),('blue',)*3),hand(('2','2','1'),('red','blue','red')),
                  hand(('+4',)*3,('wild',)*3),hand(('3','4','5'),('green',)*3)]:
        monkeypatch.setattr(economy,'draw',lambda c, saved=cards:saved)
        assert award_engine.draw(cfg)==cards
    assert cfg.model_dump_json()==before
    assert economy.rtp_percent(cfg)==pytest.approx(91.6621770609319)


def test_catalog_has_fifteen_genuine_nonstacking_patterns():
    rules=orbit.public_rules(economy.PRESET)
    entries=rules['win_catalog']
    assert len(entries)==15
    assert len({e['id'] for e in entries})==15
    assert len([e for e in entries if e['group']=='rank'])==5
    assert rules['color_bonus']['pair_enabled']
    assert not rules['color_bonus']['sequence_enabled']
    assert 'percentages' not in json.dumps(rules)
    for item in entries:
        if not item['enabled']:
            continue
        combo,multiplier,rank=award_engine.classify(item['cards'],economy.PRESET)
        assert multiplier>0
        tier=orbit.rank_details(rank) if rank else None
        assert award_engine.describe(item['cards'],combo,tier,25*multiplier)['id']==item['id']


def test_empty_or_promotional_payout_never_has_winning_edges():
    assert award_engine.describe(hand(),'NO_MATCH',None,0) is None
    assert award_engine.describe(hand(),'NO_MATCH',None,100) is None
    assert award_engine.describe(hand(),'COLOR_PAIR',None,0) is None
    award=award_engine.describe(hand(),'COLOR_PAIR',None,50)
    assert award['color_indices']==[0,2]
    assert award['winning_indices']==[0,2]


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('UNO_SPIN_DB_PATH',str(tmp_path/'awards.sqlite3'))
    monkeypatch.setenv('UNO_QA_BOOTSTRAP_ECONOMY','1')
    spin.INITIALIZED.clear();orbit._initialized.clear()
    with TestClient(app) as c:
        c.get('/api/orbit/state')
        yield c


def pick(c,n):
    return c.post('/api/orbit/pick',headers={'x-uno-client':'spin-ui'},
        json={'stake':25,'request_id':f'award-regression-request-{n}'}).json()


def test_pair_credits_once_and_does_not_leak_early(client,monkeypatch):
    monkeypatch.setattr(award_engine,'draw',lambda cfg:hand())
    first=pick(client,1)
    assert first['round']['rules_version']==6
    assert first['round']['award'] is None and len(first['round']['cards'])==1
    second=pick(client,2)
    assert second['round']['award'] is None
    third=pick(client,3)
    assert third['round']['payout']==50 and third['round']['delta']==25
    assert third['round']['award']['color_indices']==[0,2]
    again=pick(client,3)
    assert again['replayed'] and again['account']['balance']==third['account']['balance']
    with orbit.open_db() as db:
        assert db.execute('SELECT COUNT(*) FROM economy_configs').fetchone()[0]==1
        assert db.execute("SELECT COUNT(*) FROM ledger WHERE reason='orbit_payout'").fetchone()[0]==1


def test_inflight_v5_pair_keeps_original_zero_settlement(client,monkeypatch):
    monkeypatch.setattr(award_engine,'draw',lambda cfg:hand())
    first=pick(client,1)
    rid=first['round']['id']
    # Recreate a genuine paid v5 snapshot from before the rule change.
    db=orbit.open_db()
    try:
        old=json.loads(db.execute('SELECT economy_json FROM orbit_rounds WHERE id=?',(rid,)).fetchone()[0])
        old['multiplier']=0
        db.execute("UPDATE orbit_rounds SET rules_version=5,combo='NO_MATCH',tier=NULL,economy_json=? WHERE id=?",
                   (json.dumps(old),rid))
        db.commit()
    finally:
        db.close()
    pick(client,2)
    third=pick(client,3)
    assert third['round']['payout']==0
    assert third['round']['rules_version']==5
    assert third['round']['award'] is None
    assert pick(client,3)['account']['balance']==third['account']['balance']
