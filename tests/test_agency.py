import json
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app import agency, orbit
from app.agency_wallet import AgencyWalletError
from app.main import app

HEADERS = {'X-UNO-Client': 'spin-ui'}
TOKEN = 'A' * 43

class Wallet:
    def __init__(self):
        self.balance = 1000
        self.reserved = 0
        self.rounds = {}
        self.actions = []
        self.fail_after = None
        self.reject = None
        self.launches = {}

    def request(self, action, p):
        self.actions.append(action)
        if self.reject == action:
            raise AgencyWalletError(409, 'REJECTED')
        if action == 'redeem':
            t = p['token']
            if t not in self.launches:
                self.launches[t] = {'session_id': t[:8], 'tenant_id': 'tenant-1', 'player_id': 'player-1', 'game': 'uno-luck', 'currency': 'IDR', 'coin_scale': 0, 'balance': str(self.balance)}
            result = self.launches[t]
        elif action == 'reserve':
            ref = p['round_ref']
            if ref not in self.rounds:
                self.rounds[ref] = {'id': ref, **p, 'state': 'reserved'}
                self.balance -= int(p['stake'])
                self.reserved += int(p['stake'])
            result = self.rounds[ref]
        elif action == 'settle':
            r = self.rounds[p['round_id']]
            if r['state'] != 'settled':
                self.balance += int(p['payout'])
                self.reserved -= int(r['stake'])
                r['state'] = 'settled'
                r['payout'] = p['payout']
            assert r['payout'] == p['payout']
            result = r
        elif action == 'status':
            result = {'balance': str(self.balance), 'reserved': str(self.reserved)}
        else:
            raise AssertionError(action)
        if self.fail_after == action:
            self.fail_after = None
            raise TimeoutError('response lost AFTER central commit')
        return result

@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('AGENCY_WALLET_MODE', 'sandbox')
    monkeypatch.setenv('UNO_AGENCY_DB_PATH', str(tmp_path / 'agency.sqlite3'))
    monkeypatch.setenv('AGENCY_WALLET_SECRET', 'secret-' * 8)
    w = Wallet()
    monkeypatch.setattr(agency, 'wallet', lambda: w)
    monkeypatch.setattr(orbit, 'choose_cards', lambda: [{'color':'red','face':'1'}]*3)
    monkeypatch.setattr(orbit, 'choose_tier', lambda: 5)
    with TestClient(app) as c:
        yield c, w

def launch(c, token=TOKEN):
    return c.post('/api/agency/launch', json={'token':token}, headers=HEADERS)

def pick(c, phase=1, rid=None, key=None, stake=25):
    return c.post('/api/agency/pick', headers=HEADERS, json={'request_id':key or 'request-phase-' + str(phase), 'expected_phase':phase, 'round_id':rid,'stake':stake})

def test_three_picks_and_duplicate_payload(setup):
    c,w = setup
    assert launch(c).status_code == 200
    first = pick(c).json()
    rid = first['round']['id']
    assert first['account']['balance'] == 975
    assert len(first['round']['cards']) == 1
    assert first['round']['payout'] is None
    assert pick(c).json()['round'] == first['round']
    assert pick(c, stake=50).status_code == 409
    assert pick(c, 2, rid, stake=50).status_code == 409
    assert pick(c, 2, rid).json()['account']['balance'] == 975
    last = pick(c, 3, rid).json()
    assert last['account']['balance'] == 1025
    assert last['round']['payout'] == 50
    assert pick(c, 3, rid).json()['account']['balance'] == 1025
    assert len(w.rounds) == 1 and w.reserved == 0
    db=agency.db_open()
    assert db.execute('SELECT count(*) FROM agency_rounds').fetchone()[0]==1
    db.close()

def test_guest_and_cross_origin_blocked(setup):
    c,w = setup
    for path in ('/api/orbit/state', '/api/spin/profile', '/api/spin/daily', '/api/spin/refill', '/classic', '/spin-legacy'):
        assert c.get(path).status_code == 403
    assert c.get('/api/agency/state').status_code == 401
    assert c.post('/api/agency/launch',json={'token':TOKEN}).status_code == 403
    assert c.post('/api/agency/launch',headers={**HEADERS,'Sec-Fetch-Site':'cross-site'},json={'token':TOKEN}).status_code == 403
    assert launch(c).status_code == 200
    assert c.post('/api/agency/pick',headers=HEADERS,json={'request_id':'request-111111','expected_phase':1,'stake':'25'}).status_code == 422
    assert not c.get('/api/agency/state').json()['account']['refill_available']

@pytest.mark.parametrize('action', ['redeem','reserve','settle'])
def test_lost_response_recovers_without_reroll(setup, monkeypatch, action):
    c,w=setup
    if action=='redeem':
        w.fail_after=action
        assert launch(c).status_code == 503
        assert launch(c).status_code == 200
    else:
        assert launch(c).status_code == 200
        if action=='reserve':
            w.fail_after=action
            assert pick(c).status_code == 503
            assert w.balance==975
            monkeypatch.setattr(orbit,'choose_cards',lambda: (_ for _ in ()).throw(AssertionError('MUST NOT REROLL')))
        rid=pick(c).json()['round']['id']
        assert pick(c,2,rid).status_code==200
        if action=='settle':
            w.fail_after=action
            assert pick(c,3,rid).status_code==503
            assert w.balance==1025
        assert pick(c,3,rid).status_code==200
        assert w.balance==1025 and len(w.rounds)==1

def test_new_launch_and_restart_resume_canonical_player(setup):
    c,w=setup
    launch(c)
    rid=pick(c).json()['round']['id']
    agency._initialized.clear()  # simulate process losing all in-memory schema cache
    launch(c, 'B'*43)
    assert c.get('/api/agency/state').json()['round']['id']==rid
    assert pick(c,2,rid).status_code==200
    assert pick(c,3,rid).json()['account']['balance']==1025

def test_concurrent_identical_clicks_reserve_once(setup):
    c,w=setup
    launch(c)
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses=list(executor.map(lambda _:pick(c),range(4)))
    assert all(r.status_code==200 for r in responses)
    assert len({r.json()['round']['id'] for r in responses})==1
    assert len(w.rounds)==1 and w.balance==975

def test_no_abandonment_selective_refund(setup):
    c,w=setup
    launch(c)
    rid=pick(c).json()['round']['id']
    db=agency.db_open();db.execute('UPDATE agency_rounds SET created_at=?',(time.time()-1000,));db.close()
    agency.recover_due();agency.recover_due()
    assert w.balance==1025 and w.reserved==0
    view=c.get('/api/agency/state').json()
    assert view['round'] is None and view['recent'][0]['id']==rid
    assert 'void' not in w.actions

def test_rejection_does_not_reveal_outcome_or_change_balance(setup):
    c,w=setup;launch(c);w.reject='reserve'
    assert pick(c).status_code==409 and w.balance==1000
    assert 'round' not in pick(c).json()
    w.reject=None
    assert pick(c,key='new-request-after-rejection').status_code==200
    assert w.balance==975

def test_scale_mismatch_and_tenant_isolation(setup):
    c,w=setup
    w.launches[TOKEN]={'session_id':'s','tenant_id':'A','player_id':'p','game':'uno-luck','coin_scale':2}
    assert launch(c).status_code==409
    w.launches[TOKEN]['coin_scale']=0
    assert launch(c).status_code==200
    rid=pick(c).json()['round']['id']
    other='C'*43
    w.launches[other]={'session_id':'s2','tenant_id':'B','player_id':'p','game':'uno-luck','coin_scale':0}
    assert launch(c,other).status_code==200
    assert c.get('/api/agency/state').json()['round'] is None
    assert pick(c,2,rid).status_code==409

def test_live_mode_rejected(monkeypatch):
    monkeypatch.setenv('AGENCY_WALLET_MODE','live')
    with pytest.raises(RuntimeError,match='Only sandbox'):
        agency.validate_config()
