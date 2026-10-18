"""Three-click orbit is server authoritative with 80% scheduled win odds."""
from __future__ import annotations

import collections
import itertools
import random

import pytest
from fastapi.testclient import TestClient

from app import orbit, spin
from app.main import app


@pytest.fixture
def c(tmp_path,monkeypatch):
    monkeypatch.setenv('UNO_SPIN_DB_PATH', str(tmp_path / 'orbit.sqlite3'))
    spin.INITIALIZED.clear()
    orbit._initialized.clear()
    with TestClient(app) as client:
        assert client.get('/api/orbit/state').status_code==200
        yield client


def pick(client,key,stake=25):
    return client.post('/api/orbit/pick',headers={'x-uno-client':'spin-ui'},json={'request_id':key,'stake':stake})


def winning_cards():
    return [{'color':'blue','face':f} for f in ('6','3','8')]


def test_route_and_rules(c):
    page=c.get('/')
    assert page.status_code==200
    assert 'orbit-ring' in page.text
    assert 'COLOR MATCH' in page.text
    assert 'SPIN' in page.text
    assert c.get('/spin-legacy').status_code==200
    rules=c.get('/api/orbit/state').json()['rules']
    assert rules['win_probability_percent']==80
    assert rules['virtual_only'] is True
    assert rules['payout_multiplier']==2


def test_three_picks_charge_once_then_settle(c,monkeypatch):
    monkeypatch.setattr(orbit,'choose_cards',winning_cards)
    r1=pick(c,'first_card_phase_test').json()
    assert r1['round']['picked']==1 and len(r1['round']['cards'])==1
    assert r1['round']['cards'][0]['face']=='6'
    assert r1['round']['combo'] is None and r1['round']['payout'] is None
    assert r1['account']['balance']==975
    r2=pick(c,'second_card_phase_test').json()
    assert r2['round']['picked']==2 and len(r2['round']['cards'])==2
    assert r2['account']['balance']==975
    r3=pick(c,'third_card_phase_test').json()
    assert r3['round']['picked']==3 and r3['round']['complete']
    assert [x['face'] for x in r3['round']['cards']]==['6','3','8']
    assert r3['round']['combo']=='COLOR_MATCH'
    assert r3['round']['payout']==50
    assert r3['round']['delta']==25
    assert r3['account']['balance']==1025
    assert r3['account']['spins']==1 and r3['account']['wins']==1
    assert c.get('/api/orbit/state').json()['round'] is None
    hist=c.get('/api/spin/history').json()['items']
    assert len(hist)==1 and hist[0]['delta']==25
    db=spin.connection();total=db.execute('SELECT SUM(delta) FROM ledger').fetchone()[0];db.close()
    assert total==1025


def test_idempotence_at_all_three_phases(c,monkeypatch):
    monkeypatch.setattr(orbit,'choose_cards',winning_cards)
    for phase in range(1,4):
        key=f'orbit_replay_phase_{phase}_key'
        result=pick(c,key).json()
        repeated=pick(c,key).json()
        assert repeated['replayed'] is True
        assert repeated['round']['picked']==phase
        assert repeated['round']['cards']==result['round']['cards']
        assert repeated['account']['balance']==result['account']['balance']
    assert c.get('/api/orbit/state').json()['account']['spins']==1
    assert c.get('/api/spin/history').json()['items'][0]['payout']==50


def test_failure_only_consumes_one_stake(c,monkeypatch):
    monkeypatch.setattr(orbit,'choose_cards',lambda:[{'color':c,'face':'7'} for c in ('red','blue','yellow')])
    a=pick(c,'orbit_loss_phase_1').json()
    b=pick(c,'orbit_loss_phase_2').json()
    last=pick(c,'orbit_loss_phase_3').json()
    assert a['account']['balance']==b['account']['balance']==975
    assert last['round']['combo']=='NO_MATCH'
    assert last['round']['payout']==0 and last['round']['delta']==-25
    assert last['account']['balance']==975


def test_changed_stake_during_round_rejected(c):
    assert pick(c,'orbit_stake_initial',25).status_code==200
    mismatch=pick(c,'orbit_mismatch_second',50)
    assert mismatch.status_code==409
    assert c.get('/api/orbit/state').json()['round']['picked']==1
    assert c.get('/api/orbit/state').json()['account']['balance']==975


def test_mutation_header_and_request_validation(c):
    response=c.post('/api/orbit/pick',json={'request_id':'invalid-no-client','stake':25})
    assert response.status_code==403
    assert pick(c,'invalid spaces ',25).status_code==422
    assert pick(c,'valid-but-bad-stake',42).status_code==422
    assert c.get('/api/orbit/state').json()['account']['balance']==1000


def test_probabilistic_gate_exhaustive_on_forced_rng(monkeypatch):
    # Verify the advertised 80% branch explicitly, not by flaky randomness.
    import secrets
    choices=itertools.cycle(range(100))
    monkeypatch.setattr(orbit.secrets,'randbelow',lambda n:next(choices))
    winners=0
    for i in range(100):
        cards=orbit.choose_cards()
        assert len(cards)==3
        if len({card['color'] for card in cards})==1:winners+=1
    assert winners==80


def test_reload_restores_unfinished_round(c,monkeypatch):
    monkeypatch.setattr(orbit,'choose_cards',winning_cards)
    first=pick(c,'orbit_reload_first').json()
    active=c.get('/api/orbit/state').json()['round']
    assert active['id']==first['round']['id']
    assert len(active['cards'])==1
    assert 'face' in active['cards'][0]
    assert pick(c,'orbit_reload_second').json()['round']['picked']==2
    assert pick(c,'orbit_reload_third').json()['round']['picked']==3
    assert c.get('/api/orbit/state').json()['round'] is None


def test_no_money_routes(c):
    for url in ('/api/orbit/topup','/api/orbit/withdraw','/api/orbit/deposit'):
        assert c.post(url).status_code in (404,405)
