"""Concurrent native API clients with a real signed local HTTP wallet transport."""
import hashlib,hmac,json,sqlite3,threading,time,uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from http.cookies import SimpleCookie
from contextlib import closing, contextmanager
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from app.provider_main import app
from app import agency

@contextmanager
def wallet_server(game):
    lock=threading.Lock();entered=threading.Event();release=threading.Event();rounds={};balances={'slow':100000,'fast':100000};nonces=set()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            raw=self.rfile.read(int(self.headers['Content-Length']));p=json.loads(raw);action=self.path.rsplit('/',1)[-1]
            canonical='\n'.join(('agency.v2','preproduction','core-concurrency-test','POST',self.path,self.headers.get('X-Agency-Timestamp',''),self.headers.get('X-Agency-Nonce',''),hashlib.sha256(raw).hexdigest()))
            expected=hmac.new(('q'*40).encode(),canonical.encode(),'sha256').hexdigest()
            if self.headers.get('X-Agency-Version')!='2' or self.headers.get('X-Agency-Audience')!='core-concurrency-test' or not hmac.compare_digest(self.headers.get('X-Agency-Signature',''),expected):self.send_error(403);return
            with lock:
                nonce=self.headers.get('X-Agency-Nonce')
                if nonce in nonces:self.send_error(409);return
                nonces.add(nonce)
            delay=False
            with lock:
                if action=='redeem':
                    player='slow' if p['token'].startswith('s') else 'fast';result={'provider':'soft-tech','game':game,'environment':'preproduction','deployment_id':'core-concurrency-test','tenant_id':'tenant','player_id':player,'session_id':player,'coin_scale':0,'currency':'VCOIN'}
                elif action=='status':result={'balance':str(balances[p['session_id']]),'reserved':'0'}
                elif action=='reserve':
                    ref=p['round_ref'];player=p['session_id']
                    if ref not in rounds:rounds[ref]={'id':ref,'player':player,'debits':1,'credits':0,**p};balances[player]-=int(p['stake'])
                    result=rounds[ref];delay=player=='slow' and not release.is_set()
                elif action=='settle':
                    row=rounds[p['round_id']]
                    if not row['credits']:row['credits']=1;balances[row['player']]+=int(p['payout']);row['payout']=p['payout']
                    result={'ok':True}
                else:self.send_error(404);return
            if delay:entered.set();release.wait(10)
            payload=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True;thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}',entered,release,rounds
    finally:release.set();server.shutdown();server.server_close();thread.join()

def test_delayed_player_does_not_block_another_and_duplicate_is_exactly_once(tmp_path,monkeypatch):
    with wallet_server('uno-luck') as (origin,entered,release,rounds):
        values={'AGENCY_WALLET_MODE':'sandbox','AGENCY_ENVIRONMENT':'preproduction','AGENCY_DEPLOYMENT_ID':'uno-concurrency-test','AGENCY_CORE_DEPLOYMENT_ID':'core-concurrency-test','UNO_AGENCY_DB_PATH':str(tmp_path/'native.sqlite'),'AGENCY_WALLET_ORIGIN':origin,'AGENCY_WALLET_KEY_ID':'test-engine','AGENCY_WALLET_SECRET':'q'*40,'AGENCY_WALLET_LOCAL_QA':'1','AGENCY_STUDIO_SYNC':'0','ENGINE_BACKUP_ENABLED':'false'}
        for k,v in values.items():monkeypatch.setenv(k,v)
        for key in ('ENGINE_RESTORE_OBJECT_KEY','ENGINE_RESTORE_OBJECT','ENGINE_RESTORE_CIPHERTEXT_SHA256'):monkeypatch.delenv(key,raising=False)
        with TestClient(app) as c:
            cookies={}
            for player in ('slow','fast'):
                response=c.post('/api/agency/launch',headers={'X-UNO-Client':'spin-ui'},json={'token':player[0]*48});assert response.status_code==200,response.text
                parsed=SimpleCookie();parsed.load(response.headers['set-cookie']);cookies[player]=agency.COOKIE+'='+parsed[agency.COOKIE].value
            def headers(player):return {**{'X-UNO-Client':'spin-ui'},'Cookie':cookies[player]}
            payloads={p:{'request_id':str(uuid.uuid4()),'stake':25,'expected_phase':1,'round_id':None} for p in ('slow','fast')}
            def request(player,payload):
                result=c.post('/api/agency/pick',headers=headers(player),json=payload);assert result.status_code==200,result.text;return result.json()
            def fast_round():
                r=request('fast',payloads['fast'])
                for phase in (2,3):r=request('fast',{'request_id':str(uuid.uuid4()),'stake':25,'expected_phase':phase,'round_id':r['round']['id']})
                return r
            with ThreadPoolExecutor(max_workers=3) as pool:
                slow=pool.submit(request,'slow',payloads['slow'])
                try:
                    assert entered.wait(3),'slow signed wallet request did not arrive'
                    duplicate=pool.submit(request,'slow',payloads['slow']);fast=pool.submit(fast_round)
                    fast_result=fast.result(timeout=3)
                    assert not slow.done() and not duplicate.done(),'same-player queue must wait for the delayed reserve'
                finally:release.set()
                a,b=slow.result(timeout=3),duplicate.result(timeout=3)
                assert a['round']==b['round'] and sorted([a['replayed'],b['replayed']])==[False,True]
            for phase in (2,3):a=request('slow',{'request_id':str(uuid.uuid4()),'stake':25,'expected_phase':phase,'round_id':a['round']['id']})
            assert len(rounds)==2 and all(r['debits']==1 and r['credits']==1 for r in rounds.values())

            assert c.get('/health').json()['pending_operation_locks']==0


def native_dump(path):
    with closing(sqlite3.connect(path)) as db:
        return tuple(db.iterdump())


@pytest.fixture
def completed_replay(tmp_path, monkeypatch):
    """One real signed-wallet round with all original phase responses retained."""
    with wallet_server('uno-luck') as (origin, entered, release, rounds):
        path = tmp_path / 'native.sqlite'
        values = {'AGENCY_WALLET_MODE': 'sandbox', 'AGENCY_ENVIRONMENT': 'preproduction',
                  'AGENCY_DEPLOYMENT_ID': 'uno-replay-test',
                  'AGENCY_CORE_DEPLOYMENT_ID': 'core-concurrency-test',
                  'UNO_AGENCY_DB_PATH': str(path), 'AGENCY_WALLET_ORIGIN': origin,
                  'AGENCY_WALLET_KEY_ID': 'test-engine', 'AGENCY_WALLET_SECRET': 'q' * 40,
                  'AGENCY_WALLET_LOCAL_QA': '1', 'AGENCY_STUDIO_SYNC': '0',
                  'ENGINE_BACKUP_ENABLED': 'false'}
        for key, value in values.items():
            monkeypatch.setenv(key, value)
        for key in ('ENGINE_RESTORE_OBJECT_KEY', 'ENGINE_RESTORE_OBJECT',
                    'ENGINE_RESTORE_CIPHERTEXT_SHA256'):
            monkeypatch.delenv(key, raising=False)
        headers = {'X-UNO-Client': 'spin-ui'}
        with TestClient(app) as client:
            launched = client.post('/api/agency/launch', headers=headers,
                                   json={'token': 'f' * 48})
            assert launched.status_code == 200, launched.text
            phases, rid = [], None
            for phase in (1, 2, 3):
                payload = {'request_id': str(uuid.uuid4()), 'stake': 25,
                           'expected_phase': phase, 'round_id': rid}
                response = client.post('/api/agency/pick', headers=headers, json=payload)
                assert response.status_code == 200, response.text
                rid = response.json()['round']['id']
                phases.append((payload, response.json()))

            statements, actions = [], []
            original_open, original_remote = agency.db_open, agency.remote
            def observed_open(**kwargs):
                db = original_open(**kwargs)
                db.set_trace_callback(statements.append)
                return db
            def observed_remote(action, payload):
                actions.append(action)
                return original_remote(action, payload)
            monkeypatch.setattr(agency, 'db_open', observed_open)
            monkeypatch.setattr(agency, 'remote', observed_remote)
            from app import orbit
            def forbid_new_outcome():
                pytest.fail('A completed replay must not generate another outcome')
            monkeypatch.setattr(orbit, 'choose_cards', forbid_new_outcome)
            yield SimpleNamespace(client=client, headers=headers, rounds=rounds,
                                  path=path, phases=phases, statements=statements,
                                  actions=actions, before=native_dump(path))


def assert_read_only_replay(probe):
    assert native_dump(probe.path) == probe.before
    assert len(probe.rounds) == 1
    assert all(row['debits'] == row['credits'] == 1 for row in probe.rounds.values())
    writes = ('BEGIN', 'COMMIT', 'END', 'ROLLBACK', 'INSERT', 'UPDATE', 'DELETE',
              'REPLACE', 'CREATE', 'DROP', 'ALTER', 'SAVEPOINT', 'RELEASE')
    assert not any(sql.lstrip().upper().startswith(writes) for sql in probe.statements)
    assert probe.client.get('/health').json()['pending_operation_locks'] == 0


def test_completed_replay_finishes_while_unrelated_sqlite_writer_is_held(completed_replay):
    probe = completed_replay
    payload, original = probe.phases[-1]
    blocker = sqlite3.connect(probe.path, isolation_level=None)
    try:
        blocker.execute('BEGIN IMMEDIATE')
        with ThreadPoolExecutor(max_workers=1) as pool:
            replay = pool.submit(probe.client.post, '/api/agency/pick',
                                 headers=probe.headers, json=payload)
            try:
                response = replay.result(timeout=5)
                assert blocker.in_transaction, 'The unrelated writer was released too early'
                assert response.status_code == 200, response.text
                assert response.json()['round'] == original['round']
                assert response.json()['replayed']
            finally:
                blocker.rollback()
    finally:
        blocker.close()
    assert probe.actions == ['status']
    assert_read_only_replay(probe)


def test_completed_replays_keep_original_card_phase_and_current_wallet_snapshot(completed_replay, monkeypatch):
    probe = completed_replay
    original_remote = agency.remote
    def current_status(action, payload):
        result = original_remote(action, payload)
        # Different authoritative values expose accidental cached-account use.
        return dict(result, balance='876543', reserved='321') if action == 'status' else result
    monkeypatch.setattr(agency, 'remote', current_status)
    for payload, original in probe.phases:
        response = probe.client.post('/api/agency/pick', headers=probe.headers, json=payload)
        assert response.status_code == 200, response.text
        replay = response.json()
        assert replay['replayed'] and replay['round'] == original['round']
        assert replay['account']['balance'] == 876543 and replay['account']['reserved'] == 321
        assert response.headers['cache-control'] == 'no-store'
        phase = payload['expected_phase']
        assert len(replay['round']['cards']) == phase and replay['round']['picked'] == phase
        if phase < 3:
            assert not replay['round']['complete']
            assert all(replay['round'][key] is None for key in ('combo', 'tier', 'pattern', 'payout', 'delta'))
    assert probe.actions == ['status', 'status', 'status']
    assert_read_only_replay(probe)


@pytest.mark.parametrize('changed', [{'stake': 50}, {'expected_phase': 2}, {'round_id': 'another-round'}])
def test_completed_replay_payload_conflicts_do_not_write_or_call_wallet(completed_replay, changed):
    probe = completed_replay
    payload, _ = probe.phases[-1]
    response = probe.client.post('/api/agency/pick', headers=probe.headers,
                                 json=dict(payload, **changed))
    assert response.status_code == 409, response.text
    assert probe.actions == []
    assert_read_only_replay(probe)


def test_settled_row_without_all_picks_keeps_original_transaction_path(completed_replay):
    probe = completed_replay
    payload, original = probe.phases[-1]
    # This inconsistent terminal row must not qualify for the read-only path.
    with closing(sqlite3.connect(probe.path)) as db:
        db.execute('UPDATE agency_rounds SET picked=2 WHERE id=?', (original['round']['id'],))
        db.commit()
    before = native_dump(probe.path)
    response = probe.client.post('/api/agency/pick', headers=probe.headers, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()['replayed'] and response.json()['round']['picked'] == 2
    statements = [sql.strip().upper() for sql in probe.statements]
    assert statements.count('BEGIN IMMEDIATE') == statements.count('COMMIT') == 1
    assert native_dump(probe.path) == before
    assert probe.actions == ['status']
    assert all(row['debits'] == row['credits'] == 1 for row in probe.rounds.values())
