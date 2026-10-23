"""Versioned admin economy, independent payout math and ledger safety."""
import itertools
import json
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app import economy, orbit, spin
from app.main import app

TOKEN='test-only-economy-admin-secret-not-for-production'
HEAD={'x-uno-sound-admin':TOKEN}

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('UNO_SPIN_DB_PATH',str(tmp_path/'economy.sqlite3'))
    monkeypatch.setenv('UNO_SOUND_ADMIN_TOKEN',TOKEN)
    spin.INITIALIZED.clear();orbit._initialized.clear()
    with TestClient(app) as c:
        c.get('/api/orbit/state')
        yield c


def config(): return economy.PRESET.model_dump(mode='json')
def publish(c,cfg=None,revision=0): return c.post('/api/admin/economy/publish',headers=HEAD,json={'config':cfg or config(),'expected_revision':revision})
def pick(c,i,stake=10): return c.post('/api/orbit/pick',headers={'x-uno-client':'spin-ui'},json={'request_id':f'economy-round-request-{i}','stake':stake})
def hand(faces,colors=('blue',)*3): return [dict(face=str(f),color=c) for f,c in zip(faces,colors)]


def test_auth_no_config_leak_and_origin(client):
    assert client.get('/api/admin/economy').status_code==403
    assert client.post('/api/admin/economy/publish',json={'config':config(),'expected_revision':0}).status_code==403
    assert client.get('/api/admin/economy',headers=HEAD|{'origin':'https://evil.example'}).status_code==403
    before=client.get('/api/admin/economy',headers=HEAD).json()
    assert before['revision']==0 and before['active'] is None
    assert before['legacy_rtp_percent']==pytest.approx(sum(t['multiplier']*t['weight']/orbit.WEIGHT_SCALE*.8 for t in orbit.CELEBRATIONS.values())*100)
    assert publish(client).status_code==200
    public=client.get('/api/orbit/state').json()
    assert public['rules']['stake_options']==[10,20,25,50,100,250]
    assert public['rules']['virtual_rp_per_coin']==40
    assert 'percentages' not in json.dumps(public)
    assert 'economy_json' not in json.dumps(public)
    assert publish(client).status_code==409


@pytest.mark.parametrize('change',[
    {'stake_options':[9,25]}, {'stake_options':[10,10]}, {'stake_options':[10,20.5]},
    {'sum_cap':0}, {'product_cap':17}, {'multipliers':[200,80,30,10,2]},
    {'percentages':{**config()['percentages'],'NO_MATCH':'100'}},
    {'percentages':{**config()['percentages'],'PAIR_SUM':'NaN'}},
    {'percentages':{**config()['percentages'],'PAIR_SUM':'5.00001','NO_MATCH':'93.35899'}},
    {'percentages':{**config()['percentages'],'PAIR_PRODUCT':'0.5','NO_MATCH':'93.859'}},
])
def test_invalid_config_blocked(change):
    with pytest.raises(ValidationError): economy.Config.model_validate(config()|change)


def test_exact_math_independent_enumeration():
    cfg=economy.PRESET
    numbers=[h for h in itertools.product(range(10),repeat=3) if h[0]==h[1] or h[1]==h[2] or h[0]==h[2]]
    assert len(numbers)==280
    expected=.05*sum(min(sum(h),10) for h in numbers)/280+.01*sum(min(h[0]*h[1]*h[2],20) for h in numbers)/280
    expected += .005*25+.001*40+.0003*80+.0001*150+.00001*300
    result=economy.simulate(economy.Simulation(config=cfg))
    assert result['rtp_percent']==pytest.approx(expected*100)
    assert result['rtp_percent']==pytest.approx(79.025)
    assert sum(x['percent'] for x in result['distribution'])==pytest.approx(100)
    assert result['payout_probability_percent']<6.641 # zero product outcomes are not wins
    assert result['expected_net']==pytest.approx((expected-1)*10)
    assert result==economy.simulate(economy.Simulation(config=cfg))
    empty=economy.simulate(economy.Simulation(config=cfg,balance=9))
    assert empty['stopped_percent']==100 and empty['average_rounds']==0 and empty['trace']==[9]


@pytest.mark.parametrize('faces,colors,combo,multiplier',[
    ((2,2,1),('red','blue','green'),'PAIR_SUM',5),
    ((3,3,2),('blue',)*3,'PAIR_PRODUCT',18),
    ((9,9,9),('blue',)*3,'PAIR_PRODUCT',20),
    ((0,0,0),('blue',)*3,'PAIR_PRODUCT',0),
    ((2,3,4),('blue',)*3,'COLOR_MATCH',40),
    ((2,5,9),('blue',)*3,'COLOR_MATCH',25),
])
def test_settlement_snapshot_replay_and_ledger(client,monkeypatch,faces,colors,combo,multiplier):
    assert publish(client).status_code==200
    monkeypatch.setattr(economy,'draw',lambda cfg:hand(faces,colors))
    first=pick(client,1).json()
    assert first['round']['bonus'] is None and first['round']['payout'] is None
    assert first['account']['balance']==990
    changed=config();changed['multipliers']=[600,300,150,80,50];changed['product_cap']=30
    changed['stake_options']=[10,25,50]
    assert publish(client,changed,1).status_code==200
    assert pick(client,2).status_code==200
    result=pick(client,3).json()
    assert result['round']['combo']==combo and result['round']['payout']==multiplier*10
    assert result['account']['balance']==990+multiplier*10
    if combo.startswith('PAIR_'): assert result['round']['tier'] is None
    else: assert result['round']['tier']['multiplier']==multiplier
    replay=pick(client,3).json()
    assert replay['replayed'] and replay['account']==result['account']
    db=orbit.open_db()
    assert db.execute('SELECT SUM(delta) FROM ledger').fetchone()[0]==result['account']['balance']
    assert db.execute("SELECT COUNT(*) FROM ledger WHERE reason='orbit_payout'").fetchone()[0]==1
    db.close()


def test_removed_stake_can_finish_and_replay(client,monkeypatch):
    publish(client);monkeypatch.setattr(economy,'draw',lambda cfg:hand((2,2,1),('red','blue','green')))
    assert pick(client,1,20).status_code==200
    changed=config();changed['stake_options']=[10,25]
    publish(client,changed,1)
    assert pick(client,1,20).json()['replayed']
    assert pick(client,2,20).status_code==200
    assert pick(client,3,20).json()['round']['payout']==100
    assert pick(client,4,20).status_code==422


def test_legacy_paid_round_survives_publish(client,monkeypatch):
    monkeypatch.setattr(orbit,'choose_cards',lambda:hand((3,3,2)))
    pick(client,1,25);publish(client);pick(client,2,25)
    result=pick(client,3,25).json()
    assert result['round']['combo']=='COLOR_MATCH' and result['round']['payout']==50
    assert result['round']['tier']['multiplier']==2


def test_generator_boundaries_match_categories(monkeypatch):
    cfg=economy.PRESET;roll=0
    original=orbit.cards_for_tier
    # Exercise exact interval boundaries rather than a noisy statistical test.
    for key in economy.KEYS:
        size=int(cfg.percentages[key]*10000)
        for value in (roll,roll+size-1):
            # Patch only selection randbelow; tier-4 also uses it for a face start.
            calls=iter([value])
            monkeypatch.setattr(economy.secrets,'randbelow',lambda n:next(calls) if n==economy.SCALE else 0)
            cards=economy.draw(cfg);combo,_,rank=economy.classify(cards,cfg)
            assert ('RANK_'+str(rank) if rank else combo)==key
        roll+=size
    assert roll==economy.SCALE


def test_balance_cap_and_corrupted_snapshot(client,monkeypatch):
    publish(client);monkeypatch.setattr(economy,'draw',lambda cfg:hand((3,3,2)))
    pick(client,1)
    db=orbit.open_db();db.execute('UPDATE accounts SET balance=?',(spin.COIN_CAP-3,));db.close()
    pick(client,2);result=pick(client,3).json()
    assert result['round']['payout']==3 and result['account']['balance']==spin.COIN_CAP


def test_simulation_endpoint_is_read_only(client):
    before=client.get('/api/orbit/state').json()['account']
    payload={'config':config(),'stake':10,'balance':1000,'rounds':100,'seed':42}
    assert client.post('/api/admin/economy/simulate',json=payload).status_code==403
    assert client.post('/api/admin/economy/simulate',headers=HEAD,json=payload).status_code==200
    assert client.get('/api/orbit/state').json()['account']==before
    assert client.get('/api/admin/economy',headers=HEAD).json()['revision']==0


def test_corrupt_snapshot_cannot_credit(client,monkeypatch):
    publish(client);monkeypatch.setattr(economy,'draw',lambda cfg:hand((3,3,2)))
    pick(client,1);pick(client,2)
    db=orbit.open_db();row=db.execute('SELECT id,economy_json FROM orbit_rounds').fetchone()
    snap=json.loads(row['economy_json']);snap['multiplier']=999
    db.execute('UPDATE orbit_rounds SET economy_json=? WHERE id=?',(json.dumps(snap),row['id']));db.close()
    with pytest.raises(RuntimeError,match='settlement blocked'): pick(client,3)
    state=client.get('/api/orbit/state').json()
    assert state['account']['balance']==990 and state['round']['picked']==2
    db=orbit.open_db();assert db.execute("SELECT COUNT(*) FROM ledger WHERE reason='orbit_payout'").fetchone()[0]==0;db.close()


def test_operator_projection_and_target_are_read_only(client):
    before=client.get('/api/orbit/state').json()['account']['balance']
    result=client.post('/api/admin/economy/simulate',headers=HEAD,json={
        'config':config(),'turnover_rp':1000000,'costs_rp':50000}).json()
    assert result['operator_margin_percent']==pytest.approx(20.975)
    assert result['projection']['expected_payout_rp']==pytest.approx(790250)
    assert result['projection']['gross_result_rp']==pytest.approx(209750)
    assert result['projection']['net_result_rp']==pytest.approx(159750)
    response=client.post('/api/admin/economy/target',headers=HEAD,json={'config':config(),'margin_percent':20})
    assert response.status_code==200
    result=response.json();proposed=result['config']
    assert abs(result['actual_margin_percent']-20)<.05
    from decimal import Decimal
    assert sum(Decimal(v) for v in proposed['percentages'].values())==100
    for field in ('multipliers','sum_cap','product_cap','stake_options'):assert proposed[field]==config()[field]
    calc=client.post('/api/admin/economy/simulate',headers=HEAD,json={'config':proposed}).json()
    assert result['actual_margin_percent']==pytest.approx(calc['operator_margin_percent'])
    assert client.get('/api/admin/economy',headers=HEAD).json()['revision']==0
    assert client.get('/api/orbit/state').json()['account']['balance']==before
    assert client.post('/api/admin/economy/target',json={'config':config(),'margin_percent':20}).status_code==403
    assert client.post('/api/admin/economy/target',headers=HEAD|{'origin':'https://evil.example'},json={'config':config(),'margin_percent':20}).status_code==403


@pytest.mark.parametrize('margin',[-1,100,'NaN','Infinity'])
def test_invalid_target_blocked(client,margin):
    assert client.post('/api/admin/economy/target',headers=HEAD,json={'config':config(),'margin_percent':margin}).status_code==422


def test_target_never_silently_drops_rare_category(client):
    assert client.post('/api/admin/economy/target',headers=HEAD,json={'config':config(),'margin_percent':99}).status_code==422


def test_target_handles_changed_caps_and_payouts(client):
    c=config();c['multipliers']=[23,22,21,20,19];c['sum_cap']=5;c['product_cap']=18
    c['percentages']={**c['percentages'],'NO_MATCH':'20','PAIR_SUM':'79.4','PAIR_PRODUCT':'0.6','RANK_1':'0','RANK_2':'0','RANK_3':'0','RANK_4':'0','RANK_5':'0'}
    # This is feasible: lowering RTP scales down paying probabilities and increases NO MATCH.
    response=client.post('/api/admin/economy/target',headers=HEAD,json={'config':c,'margin_percent':20})
    assert response.status_code==200
    assert response.json()['actual_margin_percent']==pytest.approx(20,abs=.05)
