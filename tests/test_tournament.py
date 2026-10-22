import concurrent.futures
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import orbit, spin, tournament

HEADERS={'X-UNO-Client':'spin-ui'}

@pytest.fixture
def c(tmp_path,monkeypatch):
    monkeypatch.setenv('UNO_SPIN_DB_PATH',str(tmp_path/'game.sqlite3'))
    with TestClient(app) as client:
        client.get('/api/orbit/state')
        yield client

def play(c,key,stake=25):
    for phase in range(3):
        r=c.post('/api/orbit/pick',headers=HEADERS,json={'request_id':f'test_tournament_{key}_{phase}', 'stake':stake})
        assert r.status_code==200
    return r.json()

def test_join_auth_idempotence_and_no_balance_mutation(c):
    before=c.get('/api/orbit/state').json()['account']
    assert c.get('/api/tournament/state').json()['you'] is None
    assert c.post('/api/tournament/join').status_code==403
    a=c.post('/api/tournament/join',headers=HEADERS)
    b=c.post('/api/tournament/join',headers=HEADERS)
    assert a.status_code==b.status_code==200
    assert b.json()['event']['participants']==1
    assert b.json()['you']['points']==0
    assert a.headers['cache-control']=='no-store'
    assert c.get('/api/orbit/state').json()['account']==before
    db=tournament.open_db()
    assert db.execute('SELECT COUNT(*) FROM tournament_entries').fetchone()[0]==1
    assert db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0]==1
    db.close()
    with TestClient(app) as anon:
        assert anon.get('/api/tournament/state').status_code==401
        assert anon.post('/api/tournament/join',headers=HEADERS).status_code==401

def test_only_new_complete_first_ten_rounds_and_replays(c,monkeypatch):
    monkeypatch.setattr(orbit,'choose_cards',lambda:[{'color':'red','face':str(n)} for n in [2,5,9]])
    play(c,'before')
    # A paid round already in progress does not enter the event.
    c.post('/api/orbit/pick',headers=HEADERS,json={'request_id':'before_join_partial','stake':25})
    c.post('/api/tournament/join',headers=HEADERS)
    for n in range(2):
        c.post('/api/orbit/pick',headers=HEADERS,json={'request_id':f'before_join_end_{n}','stake':25})
    assert c.get('/api/tournament/state').json()['you']['rounds']==0
    for n in range(11): play(c,str(n),10 if n%2 else 25)
    result=c.get('/api/tournament/state').json()
    assert result['you']['rounds']==10
    assert result['you']['points']==20
    c.post('/api/orbit/pick',headers=HEADERS,json={'request_id':'test_tournament_10_2','stake':25})
    assert c.get('/api/tournament/state').json()['you']==result['you']
    assert not any(k in str(result) for k in ['token_hash','cards_json','account_id','balance'])

def test_wib_rollover_and_late_finish(c,monkeypatch):
    clock=[datetime(2026,10,22,23,59,tzinfo=spin.TZ).timestamp()]
    monkeypatch.setattr(tournament.time,'time',lambda:clock[0])
    monkeypatch.setattr(orbit,'choose_cards',lambda:[{'color':'wild','face':'+4'}]*3)
    first=c.post('/api/tournament/join',headers=HEADERS).json()
    assert first['event']['id']=='2026-10-22'
    c.post('/api/orbit/pick',headers=HEADERS,json={'request_id':'late_round_start','stake':25})
    clock[0]+=120
    for n in range(2):c.post('/api/orbit/pick',headers=HEADERS,json={'request_id':f'late_round_end_{n}','stake':25})
    new=c.get('/api/tournament/state').json()
    assert new['event']['id']=='2026-10-23' and new['you'] is None
    db=tournament.open_db();aid=db.execute('SELECT id FROM accounts').fetchone()[0]
    old=tournament.snapshot(db,aid,clock[0]-120)
    assert old['you']['rounds']==0
    db.close()
    c.post('/api/tournament/join',headers=HEADERS)
    play(c,'nextday')
    assert c.get('/api/tournament/state').json()['you']['points']==200

def test_ties_and_current_player_outside_top_twenty(c):
    c.post('/api/tournament/join',headers=HEADERS)
    for _ in range(21):
        with TestClient(app) as other:
            other.get('/api/orbit/state')
            other.post('/api/tournament/join',headers=HEADERS)
    db=tournament.open_db()
    aid=db.execute('SELECT id FROM accounts ORDER BY created_at DESC LIMIT 1').fetchone()[0]
    data=tournament.snapshot(db,aid,tournament.time.time());db.close()
    assert data['event']['participants']==22
    assert len(data['leaderboard'])==20
    assert data['you']['position']==1 and data['you']['rounds']==0
    assert all(r['position']==1 for r in data['leaderboard'])
