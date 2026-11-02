"""Explicit live staged-only CP15 acceptance; no private admin credentials."""
import urllib.request, urllib.error, http.cookiejar, json, time, uuid, pathlib
from datetime import datetime, timezone
BASE='https://uno-game-data-pilot-staging.up.railway.app'
ADMIN='https://playground-admin-production.up.railway.app'
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs): return None
jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPCookieProcessor(jar))
report={'scope':'new_isolated_UNO_staging_pilot','adminAccountUsed':False,'productionGameplayChanged':False,'startedAt':datetime.now(timezone.utc).isoformat(),'checks':[]}
def call(path,body=None,base=BASE):
 assert base in (BASE,ADMIN)
 if body is not None: assert base==BASE and path=='/api/orbit/pick'
 data=None if body is None else json.dumps(body).encode()
 headers={'Accept':'application/json','Cache-Control':'no-cache','User-Agent':'CP15-staging-acceptance'}
 if data is not None: headers.update({'Content-Type':'application/json','X-Uno-Client':'spin-ui','Origin':BASE})
 try:
  with opener.open(urllib.request.Request(base+path,data=data,headers=headers),timeout=15) as res:
   raw=res.read(100000);status=res.status
 except urllib.error.HTTPError as e:
  raw=e.read(100000);status=e.code
 return status,json.loads(raw)
try:
 status,health=call('/health',base=ADMIN)
 assert status==200 and health.get('version')=='0.15.0' and health.get('db')=='connected',(status,health)
 status,blocked=call('/api/admin/data/summary?environment=staging',base=ADMIN)
 assert status==401,(status,blocked)
 report['checks'].append({'check':'receiver_version_and_anonymous_admin_block','status':'PASS','version':health['version'],'unauthorized':status})
 for ready in range(24):
  try:
   status,game_health=call('/health')
   if status==200 and game_health.get('ok') is True: break
  except (ValueError,OSError): pass
  time.sleep(5)
 else: raise AssertionError('New isolated pilot is not healthy')
 assert game_health.get('money_enabled') is False
 status,before=call('/api/gameops/status');assert status==200 and before['enabled'] and before['environment']=='staging'
 assert isinstance(before['source_count'],int)
 initial=before['source_count']
 status,state=call('/api/orbit/state');assert status==200
 completed=[]
 for n in range(3):
  for pick in range(3):
   status,body=call('/api/orbit/pick',{'stake':25,'request_id':'cp15-live-'+uuid.uuid4().hex})
   assert status==200,(status,body)
   assert body['round']['picked']==pick+1
   if pick<2: assert body['round']['complete'] is False
  assert body['round']['complete'] is True
  r=body['round'];completed.append({'id':r['id'],'stake':r['stake'],'payout':r['payout'],'delta':r['delta']})
 report['checks'].append({'check':'three_server_determined_rounds','status':'PASS','rounds':completed,'noForcedOutcomes':True})
 final=None
 for attempt in range(36):
  status,s=call('/api/gameops/status');assert status==200
  final=s
  if s['source_count']>=initial+3 and s['acknowledged']==s['source_count'] and s['pending']==0 and s['reconciliation']=='matched' and int(s['reconciled_through'])==s['source_count']: break
  time.sleep(5)
 else: raise AssertionError({'delivery_not_verified':final})
 report['checks'].append({'check':'durable_source_signed_receipt_and_manifest','status':'PASS','beforeCount':initial,'source':final})
 report['result']='PASS'
except Exception as e:
 report['result']='FAIL';report['error']=str(e);raise
finally:
 report['finishedAt']=datetime.now(timezone.utc).isoformat()
 pathlib.Path('cp15-live-pilot').mkdir(exist_ok=True)
 pathlib.Path('cp15-live-pilot/acceptance.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(report))
