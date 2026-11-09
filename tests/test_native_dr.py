"""Disposable complete volume loss with the real UNO native API and SQLite state."""
import hashlib, io, json, os, shutil, time, uuid
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app import agency, orbit
from app.provider_main import app
from app.deployment_identity import requested_identity
from scripts.native_backup import backup_once, restore_from_remote, restore_verify

class Storage:
    def __init__(self): self.objects={}
    def put_object(self, Bucket, Key, Body, Metadata): self.objects[Key]=Body
    def get_object(self, Bucket, Key): return {'Body':io.BytesIO(self.objects[Key])}

def test_full_native_volume_loss_key_rotation_and_recovery(tmp_path,monkeypatch):
    volume=tmp_path/'disposable-volume';volume.mkdir();path=volume/'native.sqlite'
    old,new=os.urandom(32).hex(),os.urandom(32).hex()
    values={'AGENCY_WALLET_MODE':'sandbox','AGENCY_ENVIRONMENT':'preproduction','AGENCY_DEPLOYMENT_ID':'uno-dr-deployment','AGENCY_CORE_DEPLOYMENT_ID':'core-dr-deployment','UNO_AGENCY_DB_PATH':str(path),'AGENCY_WALLET_ORIGIN':'https://core.example','AGENCY_WALLET_KEY_ID':'test-engine','AGENCY_WALLET_SECRET':'q'*40,'ENGINE_BACKUP_KEYS_JSON':json.dumps({'old':old}),'ENGINE_BACKUP_ACTIVE_KEY_ID':'old','ENGINE_BACKUP_S3_ENDPOINT':'https://storage.example','ENGINE_BACKUP_S3_ACCESS_KEY_ID':'test','ENGINE_BACKUP_S3_SECRET_ACCESS_KEY':'test','ENGINE_BACKUP_S3_BUCKET':'backups'}
    for k,v in values.items():monkeypatch.setenv(k,v)
    storage=Storage();rounds={};balance=100000000;lost=False;generated=0
    original=orbit.choose_cards
    def choose():
        nonlocal generated
        generated+=1;return original()
    monkeypatch.setattr(orbit,'choose_cards',choose)
    class Wallet:
        def request(self,action,p):
            nonlocal balance,lost
            if action=='redeem':return {'provider':'soft-tech','tenant_id':'tenant','player_id':'player','session_id':'session','game':'uno-luck','coin_scale':2,'currency':'VCOIN','environment':'preproduction','deployment_id':'core-dr-deployment'}
            if action=='status':return {'balance':str(balance),'reserved':'0'}
            if action=='reserve':
                rid=p['round_ref']
                if rid not in rounds:rounds[rid]={'id':rid,**p};balance-=int(p['stake'])
                if lost:lost=False;raise HTTPException(503,'simulated lost reserve response')
                return rounds[rid]
            if action=='settle':
                r=rounds[p['round_id']]
                if not r.get('settled'):r['settled']=True;balance+=int(p['payout'])
                return {'ok':True}
            raise AssertionError(action)
    monkeypatch.setattr(agency,'wallet',lambda:Wallet())
    headers={'X-UNO-Client':'spin-ui'}
    with patch('boto3.client',return_value=storage):
        with TestClient(app) as c:
            assert c.post('/api/agency/launch',headers=headers,json={'token':'t'*48}).status_code==200
            cookie=c.cookies.get(agency.COOKIE);rid=None
            for phase in range(1,4):
                request={'request_id':str(uuid.uuid4()),'stake':25,'expected_phase':phase,'round_id':rid if phase>1 else None}
                response=c.post('/api/agency/pick',headers=headers,json=request);assert response.status_code==200,response.text
                rid=response.json()['round']['id']
            first_id=rid;first_outcome=response.json()['round'];lost=True
            pending={'request_id':str(uuid.uuid4()),'stake':25,'expected_phase':1,'round_id':None}
            assert c.post('/api/agency/pick',headers=headers,json=pending).status_code==503
            db=agency.db_open();pending_before=dict(db.execute("SELECT * FROM agency_rounds WHERE state='intent'").fetchone());db.close()
            backup=backup_once(str(path),'uno','backups','native')
            assert backup['manifest']['key_id']=='old'
        # Neither a native SQLite file nor its WAL/SHM survives this deletion.
        lost_at=time.monotonic();shutil.rmtree(volume);assert not volume.exists();volume.mkdir()
        monkeypatch.setenv('ENGINE_BACKUP_KEYS_JSON',json.dumps({'old':old,'rotated':new}));monkeypatch.setenv('ENGINE_BACKUP_ACTIVE_KEY_ID','rotated')
        monkeypatch.setenv('ENGINE_RESTORE_OBJECT_KEY',backup['object']);monkeypatch.setenv('ENGINE_RESTORE_CIPHERTEXT_SHA256',backup['ciphertext_sha256']);monkeypatch.setenv('ENGINE_RESTORE_CONFIRM_DEPLOYMENT_ID','uno-dr-deployment')
        with TestClient(app) as c:
            c.cookies.set(agency.COOKIE,cookie)
            assert c.get('/health').json()['deployment_identity']['environment']=='preproduction'
            r=c.post('/api/agency/pick',headers=headers,json=pending);assert r.status_code==200,r.text
            restored_rid=r.json()['round']['id'];assert restored_rid==pending_before['id']
            for phase in (2,3):
                request={'request_id':str(uuid.uuid4()),'stake':25,'expected_phase':phase,'round_id':restored_rid}
                r=c.post('/api/agency/pick',headers=headers,json=request);assert r.status_code==200,r.text
            assert c.post('/api/agency/pick',headers=headers,json=request).json()['round']==r.json()['round']
            assert generated==2 and len(rounds)==2 and all(r['settled'] for r in rounds.values())
            db=agency.db_open();after=dict(db.execute('SELECT * FROM agency_rounds WHERE id=?',(restored_rid,)).fetchone());first=dict(db.execute('SELECT * FROM agency_rounds WHERE id=?',(first_id,)).fetchone());db.close()
            assert after['cards_json']==pending_before['cards_json'] and after['payout']==pending_before['payout']
            assert first['payout']==first_outcome['payout'] and first['state']=='settled'
            expected=100000000-5000+(first['payout']+after['payout'])*100
            assert balance==expected
            rotated=backup_once(str(path),'uno','backups','native');assert rotated['manifest']['key_id']=='rotated'
            assert restore_verify(storage.objects[backup['object']])['key_id']=='old'
            assert restore_verify(storage.objects[rotated['object']])['key_id']=='rotated'
            assert backup['object']!=rotated['object']
        rto=time.monotonic()-lost_at
        # An unchanged restore marker makes later restarts idempotent.
        assert restore_from_remote(str(path),'uno',requested_identity('uno-luck',str(path))) is None
        monkeypatch.setenv('ENGINE_BACKUP_KEYS_JSON',json.dumps({'rotated':new}))
        with pytest.raises(ValueError,match='unavailable'):restore_verify(storage.objects[backup['object']])
        report={'game':'uno','scenario':'disposable-native-volume-deleted-and-replaced','transport':'in-memory S3 double; real native HTTP + SQLite + AES-GCM','settled_rounds_preserved':1,'pending_rounds_recovered':1,'rounds_generated':generated,'duplicate_debits':0,'duplicate_credits':0,'rpo_lost_committed_rounds':0,'snapshot_age_seconds':max(0,time.time()-backup['manifest']['created_at']),'rto_seconds':rto,'old_and_new_keys_restore':True,'production_certified':False}
        output=os.getenv('NATIVE_DR_EVIDENCE_PATH')
        if output:Path(output).write_text(json.dumps(report,indent=2)+'\n')
