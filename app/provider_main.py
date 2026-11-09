"""Isolated Soft Tech entrypoint; live game math/assets remain byte-identical."""
from contextlib import asynccontextmanager
import hashlib, os, threading, sys, json
from datetime import datetime,timezone
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from . import agency
ROOT=Path(__file__).resolve().parent
@asynccontextmanager
async def lifespan(app):
    agency.validate_config()
    if os.getenv('ENGINE_BACKUP_ENABLED')=='true':
        print('[ENGINE BACKUP] launching UNO provider worker thread',flush=True)
        def backup_loop():
            try:
                print('[ENGINE BACKUP] UNO worker thread entered',flush=True)
                print('[ENGINE BACKUP] UNO importing backup module',flush=True)
                from scripts.native_backup_loop import run
                print('[ENGINE BACKUP] UNO module loaded',flush=True)
                run(['--database',os.environ['UNO_AGENCY_DB_PATH'],'--game','uno'])
            except BaseException as exc:
                print(f'[ENGINE BACKUP] UNO worker terminated: {type(exc).__name__}: {str(exc)[:160]}',flush=True)
        threading.Thread(target=backup_loop,name='native-backup',daemon=True).start()
    stop=threading.Event();threading.Thread(target=agency.worker,args=(stop,),daemon=True).start()
    yield
    stop.set()
app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
app.include_router(agency.router)
app.mount('/assets',StaticFiles(directory=ROOT/'static'),name='assets')
@app.middleware('http')
async def headers(req,next):
    r=await next(req);r.headers.update({'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY'});return r
@app.get('/')
async def home():
    html=(ROOT/'static/orbit-index.html').read_text()
    anchor='<script src="/assets/orbit.js'
    if anchor not in html: raise RuntimeError('Locked UNO script anchor missing')
    html=html.replace(anchor,'<script src="/assets/provider-client.js?v=1" defer></script>\n'+anchor,1)
    return HTMLResponse(html.replace('__UNO_RELEASE__','softtech-provider-v1'))
@app.get('/health')
async def health():
    db=agency.db_open();db.execute('SELECT 1');db.close()
    return {**agency.runtime_health(),'ok':True,'provider':'soft-tech','game':'UNO LUCK','version':'provider-v1','environment':os.getenv('AGENCY_ENVIRONMENT','sandbox'),'deployment_identity':agency.public_identity('uno-luck',os.environ['UNO_AGENCY_DB_PATH']),'database':'connected','source_commit':os.getenv('RAILWAY_GIT_COMMIT_SHA',''),'math_sha256':hashlib.sha256((ROOT/'orbit.py').read_bytes()).hexdigest()}
@app.get('/health/backup')
async def backup_health():
    from scripts.native_backup_status import backup_health as read_backup_health
    proof=read_backup_health('/data/uno-backup-status.json',os.getenv('RAILWAY_GIT_COMMIT_SHA',''),enabled=os.getenv('ENGINE_BACKUP_ENABLED')=='true')
    return JSONResponse(proof,status_code=200 if proof['ok'] else 503)
@app.get('/api/ui-version')
async def version(): return {'release':'softtech-provider-v1'}
@app.get('/api/agency/context')
def context(request:Request):
    db=agency.db_open()
    try:
        s,_=agency.session(db,request)
        return {'navigation':s.get('navigation'), 'expires_at':s.get('expires_at')}
    finally: db.close()
@app.api_route('/api/spin/{rest:path}',methods=['GET','POST','PATCH'])
async def blocked(rest:str): return JSONResponse({'detail':'Managed by Soft Tech provider; no local balance mutation.'},status_code=403)
