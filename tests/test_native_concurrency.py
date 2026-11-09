"""Concurrent native API clients with a real signed local HTTP wallet transport."""
import hashlib,hmac,json,threading,time,uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from http.cookies import SimpleCookie
from contextlib import contextmanager
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
