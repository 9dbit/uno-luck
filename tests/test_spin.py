"""Virtual Spin API validation, idempotent accounting, and rate/permission checks."""
import itertools
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import spin
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("UNO_SPIN_DB_PATH", str(tmp_path / "wallet.sqlite3"))
    spin.INITIALIZED.clear()
    with TestClient(app) as c:
        yield c


def setup(client):
    resp = client.get('/api/spin/state')
    assert resp.status_code == 200, resp.text
    assert 'ul_spin_guest' in client.cookies
    return resp.json()


def place(client, key, stake=25):
    return client.post('/api/spin/place', json={'stake': stake, 'request_id': key}, headers={'x-uno-client':'spin-ui'})


def bonus(client, endpoint):
    return client.post('/api/spin/' + endpoint, json={}, headers={'x-uno-client':'spin-ui'})


def test_spin_replaces_home_but_classic_remains(client):
    a = client.get('/')
    b = client.get('/classic')
    assert a.status_code == b.status_code == 200
    assert 'orbit-ring' in a.text and 'DRAGON SPIN' in a.text
    assert 'PRIVATE ROOM' in b.text
    assert client.get('/health').json()['main_mode'] == 'spin'


def test_starting_wallet_and_rules(client):
    s = setup(client)
    assert s['account']['balance'] == 1000
    assert s['account']['spins'] == 0
    assert s['rules']['probability_color_match'] == 1/16
    assert s['account']['daily_available']


def test_color_match_two_x_and_idempotent(client, monkeypatch):
    setup(client)
    monkeypatch.setattr(spin, 'fresh_cards', lambda: [dict(color='blue',face=str(i)) for i in (6, 3, 8)])
    a = place(client, 'spin_test_winning_key')
    assert a.status_code == 200, a.text
    a=a.json()
    assert a['combo'] == 'COLOR_MATCH' and a['payout'] == 50 and a['delta'] == 25
    assert a['balance'] == 1025
    duplicate = place(client, 'spin_test_winning_key').json()
    assert duplicate['replayed'] is True
    assert duplicate['id'] == a['id'] and duplicate['balance'] == 1025
    s = client.get('/api/spin/state').json()
    assert s['account']['spins'] == 1 and s['account']['wins'] == 1
    assert len(client.get('/api/spin/history').json()['items']) == 1


def test_no_match_debits_exactly_once(client, monkeypatch):
    setup(client)
    monkeypatch.setattr(spin, 'fresh_cards', lambda: [dict(color=c,face='7') for c in ('blue','red','blue')])
    r = place(client, 'spin_test_losing_key').json()
    assert r['payout'] == 0 and r['delta'] == -25 and r['balance'] == 975
    assert client.get('/api/spin/state').json()['account']['balance'] == 975


def test_color_match_probability_exhaustive():
    count=0
    for colors in itertools.product(spin.COLORS,repeat=3):
        cards=[dict(color=c,face='1') for c in colors]
        matched,payout=spin.classify(cards,25)
        if matched=='COLOR_MATCH':
            count+=1
            assert payout==50
        else:
            assert payout==0
    assert count == 4  # 4 / 64 combinations = 6.25%


def test_cost_validation_and_mutation_guard(client):
    setup(client)
    invalid=place(client, 'spin_test_invalid_stake', stake=24)
    assert invalid.status_code==422
    reject=client.post('/api/spin/place',json={'stake':25,'request_id':'spin_test_guard'})
    assert reject.status_code==403
    assert client.get('/api/spin/state').json()['account']['balance']==1000


def test_daily_once_per_jakarta_day_and_free_refill_once(client):
    setup(client)
    a=bonus(client,'daily')
    assert a.status_code==200 and a.json()['account']['balance']==1250
    assert bonus(client,'daily').status_code==409
    b=bonus(client,'refill')
    assert b.status_code==200 and b.json()['account']['balance']==2250
    assert bonus(client,'refill').status_code==409
    assert client.get('/api/spin/state').json()['account']['balance']==2250


def test_profile_validation_does_not_allow_html(client):
    setup(client)
    r=client.patch('/api/spin/profile',json={'name':'<Player> Name'},headers={'x-uno-client':'spin-ui'})
    assert r.status_code==200
    assert '<' not in r.json()['account']['name']


def test_session_is_private_between_clients(tmp_path,monkeypatch):
    monkeypatch.setenv('UNO_SPIN_DB_PATH',str(tmp_path/'sessions.db'))
    spin.INITIALIZED.clear()
    a=TestClient(app); b=TestClient(app)
    sa=setup(a); sb=setup(b)
    assert sa['account']['balance']==sb['account']['balance']==1000
    assert a.cookies['ul_spin_guest']!=b.cookies['ul_spin_guest']
    assert bonus(a,'daily').status_code==200
    assert b.get('/api/spin/state').json()['account']['balance']==1000


def test_wallet_ledger_consistency(client,monkeypatch):
    setup(client)
    monkeypatch.setattr(spin, 'fresh_cards',lambda:[dict(color=c,face='7') for c in ('red','blue','green')])
    place(client,'ledger_spin1')
    bonus(client,'daily')
    b=client.get('/api/spin/state').json()['account']['balance']
    db=spin.connection()
    try:
        totals=db.execute('SELECT sum(delta) FROM ledger').fetchone()[0]
        assert totals==b
        assert b==1000-25+250
    finally:
        db.close()


def test_spin_id_validation(client):
    setup(client)
    assert place(client,'short').status_code==422
    assert place(client,'bad value w spaces').status_code==422


def test_no_actual_money_routes(client):
    setup(client)
    for route in ('/api/spin/withdraw','/api/spin/topup','/api/spin/deposit'):
        assert client.post(route).status_code in (404,405)
