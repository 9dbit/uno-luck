"""Pinned, read-only capture for a NEW QA service. No source writes or credentials."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path

ORIGINS = {'https://uno-luck-pr23-qa.onrender.com',
           'https://uno-luck-render-staging.onrender.com'}
CUES = {'soft-tech-splash-screen','loading-scene','background-music','push-button',
        'spinning-sound','chosen-card','result-sound',*(f'jackpot-{i}' for i in range(1,6))}
FIELDS = ('source','start','stop','fadeIn','fadeOut','fileDuration','repeat','mirror',
          'mirrorCrossfadeMs','fileName','revision')
LIMIT = 16 * 1024 * 1024


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def normalized(data):
    if data.get('ready') is not True or not isinstance(data.get('cues'),dict):
        raise ValueError('Source published sound manifest is not ready')
    cues = {key:{field:value[field] for field in FIELDS if field in value}
            for key,value in data['cues'].items() if key in CUES and isinstance(value,dict)}
    for key in ('soft-tech-splash-screen','background-music'):
        if cues.get(key,{}).get('source') != 'custom':
            raise ValueError('Source lacks required published cue '+key)
    return dict(revision=str(data['revision']),cues=cues,mixer=data.get('mixer'))


def get(origin,path,limit):
    request=urllib.request.Request(origin+path,headers={'User-Agent':'UNO-DEV02-ReadonlySnapshot/1.0'},method='GET')
    with urllib.request.urlopen(request,timeout=20) as response:
        if response.geturl().split('/api/')[0] != origin:
            raise ValueError('Unexpected redirect from approved sound origin')
        blob=response.read(limit+1)
        mime=response.headers.get_content_type()
    if len(blob)>limit:raise ValueError('Oversize source audio')
    return blob,mime


def extension(blob,mime):
    if blob.startswith(b'RIFF') and blob[8:12]==b'WAVE':return '.wav'
    if blob.startswith(b'ID3') or (len(blob)>1 and blob[0]==255 and blob[1]&224==224):
        return '.aac' if mime=='audio/aac' else '.mp3'
    if len(blob)>12 and blob[4:8]==b'ftyp':return '.m4a'
    if blob.startswith(b'OggS'):return '.ogg'
    if blob.startswith(bytes.fromhex('1a45dfa3')):return '.webm'
    raise ValueError('Source bytes are not supported audio')


def capture(origin,root,expected=None,fetch=get):
    if origin not in ORIGINS:raise ValueError('Unapproved sound origin')
    root=Path(root)
    raw,_=fetch(origin,'/api/sounds/manifest',256*1024)
    source=normalized(json.loads(raw))
    source_hash=digest(source)
    if expected and source_hash!=expected:
        raise ValueError('Published audio differs from pinned DEV02 snapshot')
    root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.capture-',dir=root) as temp:
        stage=Path(temp);(stage/'audio').mkdir()
        local=json.loads(json.dumps(source));hashes={}
        for key,info in local['cues'].items():
            if info.get('source')!='custom':continue
            payload,mime=fetch(origin,'/api/sounds/files/'+key,LIMIT)
            checksum=hashlib.sha256(payload).hexdigest()
            filename=key+'-'+checksum[:24]+extension(payload,mime)
            (stage/'audio'/filename).write_bytes(payload)
            info['storageName']=filename
            hashes[key]=checksum
        after,_=fetch(origin,'/api/sounds/manifest',256*1024)
        if digest(normalized(json.loads(after)))!=source_hash:
            raise ValueError('Source manifest changed during capture')
        (root/'audio').mkdir(exist_ok=True)
        for file in (stage/'audio').iterdir():
            os.replace(file,root/'audio'/file.name)
        (stage/'manifest.json').write_text(json.dumps(local,ensure_ascii=False),encoding='utf-8')
        os.replace(stage/'manifest.json',root/'manifest.json')
        evidence={'source':origin,'revision':source['revision'],'manifest_sha256':source_hash,
                  'cue_sha256':hashes,'cues':len(local['cues']),'mixer':source.get('mixer')}
        (root/'snapshot-evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    return evidence



# DEV-07 QA-only Sound Cloud readiness: verify a local copy of the *same*
# previously approved manifest and each custom audio file before a green health.
def validate_pinned_local(root, expected):
    import re
    root = Path(root)
    if not expected or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError('Pinned Sound Cloud SHA-256 is required')
    if not (root.is_absolute() and str(root) == '/tmp/uno-dev02/sound'):
        raise ValueError('Refusing non-isolated QA sound destination')
    try:
        evidence = json.loads((root/'snapshot-evidence.json').read_text(encoding='utf-8'))
        snapshot = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError('Pinned QA Sound Cloud snapshot missing') from error
    if evidence.get('manifest_sha256') != expected or evidence.get('source') not in ORIGINS:
        raise ValueError('QA Sound Cloud source/hash does not match the approved snapshot')
    local = {'ready': True, 'revision': snapshot.get('revision'),
             'cues': snapshot.get('cues'), 'mixer': snapshot.get('mixer')}
    if digest(normalized(local)) != expected:
        raise ValueError('QA Sound Cloud manifest content differs from pinned original')
    for cue, cfg in snapshot['cues'].items():
        if cfg.get('source') != 'custom':
            continue
        filename = cfg.get('storageName', '')
        if (cue not in CUES or not isinstance(filename, str)
                or not re.fullmatch(re.escape(cue)+r'-[a-f0-9]{24}\.(mp3|wav|m4a|aac|ogg|webm)', filename)):
            raise ValueError('Pinned QA sound file name is invalid')
        target = root/'audio'/filename
        if not target.is_file():
            raise ValueError('Pinned QA sound file missing: '+cue)
        checksum = hashlib.sha256(target.read_bytes()).hexdigest()
        if checksum != evidence.get('cue_sha256', {}).get(cue):
            raise ValueError('Pinned QA sound file SHA-256 mismatch: '+cue)
    return {'ready': True, 'revision': snapshot['revision'],
            'cues': len(snapshot['cues']), 'source': evidence['source'],
            'manifest_sha256': expected}


def ensure_pinned_qa_snapshot():
    """Read-only approved-source GET; writes only isolated QA /tmp storage."""
    expected = os.getenv('UNO_DEV02_SOUND_SHA256', '').strip()
    if not expected:
        return None   # never execute on any unpinned service
    root = os.getenv('UNO_SOUND_STORAGE_DIR', '')
    if root != '/tmp/uno-dev02/sound':
        raise RuntimeError('Refusing to capture Sound Cloud outside isolated QA /tmp')
    try:
        return validate_pinned_local(root, expected)
    except ValueError:
        pass
    preferred = os.getenv('UNO_DEV02_SOUND_SOURCE', '').strip().rstrip('/')
    candidates = [preferred, 'https://uno-luck-render-staging.onrender.com',
                  'https://uno-luck-pr23-qa.onrender.com']
    errors = []
    for origin in dict.fromkeys(candidates):
        if origin not in ORIGINS:
            continue
        try:
            capture(origin, root, expected=expected)
            return validate_pinned_local(root, expected)
        except (ValueError, OSError, TimeoutError, UnicodeError, urllib.error.URLError) as error:
            errors.append(origin+': '+type(error).__name__)
    raise RuntimeError('Pinned QA Sound Cloud unavailable; aborting startup, '+', '.join(errors))


if __name__=='__main__':
    origin=os.environ.get('UNO_DEV02_SOUND_SOURCE','')
    target=os.environ.get('UNO_SOUND_STORAGE_DIR','')
    expected=os.environ.get('UNO_DEV02_SOUND_SHA256','')
    capture_mode=os.environ.get('UNO_DEV02_CAPTURE_ONLY')=='1'
    if not expected and not capture_mode:raise SystemExit('DEV02 requires a reviewed pinned audio hash')
    if not target.startswith('/tmp/uno-dev02/') and not (capture_mode and target.startswith('artifacts/')):
        raise SystemExit('Refusing any existing-service or unscoped audio destination')
    evidence=capture(origin,target,expected or None)
    print(json.dumps(evidence,sort_keys=True),flush=True)
