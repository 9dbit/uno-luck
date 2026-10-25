"""No external requests: test snapshot pinning with in-memory source fixtures."""
import json
import pytest
from app.dev02_sound_snapshot import capture,digest,normalized


def source():
    cue={'source':'custom','revision':'abc','start':0,'stop':2,'fileDuration':2,'repeat':True}
    return {'ready':True,'revision':'original-mixer','mixer':{'master':.9,'music':.22,'sfx':.85},
            'cues':{'soft-tech-splash-screen':cue.copy(),'background-music':cue.copy()}}


def test_snapshot_preserves_settings_and_uses_only_get_paths(tmp_path):
    data=source();calls=[]
    def fetch(origin,path,limit):
        calls.append(path)
        return (json.dumps(data).encode(),'application/json') if path.endswith('manifest') else (b'RIFF0000WAVEdata','audio/wav')
    result=capture('https://uno-luck-pr23-qa.onrender.com',tmp_path,digest(normalized(data)),fetch)
    saved=json.loads((tmp_path/'manifest.json').read_text())
    assert result['revision']=='original-mixer'
    assert saved['mixer']==data['mixer']
    assert all(p.startswith('/api/sounds/') for p in calls)
    for key,info in saved['cues'].items():
        assert (tmp_path/'audio'/info['storageName']).read_bytes()==b'RIFF0000WAVEdata'
        assert {k:v for k,v in info.items() if k!='storageName'}==data['cues'][key]


def test_wrong_hash_does_not_download_audio(tmp_path):
    calls=[]
    def fetch(origin,path,limit):calls.append(path);return json.dumps(source()).encode(),'application/json'
    with pytest.raises(ValueError,match='pinned'):
        capture('https://uno-luck-pr23-qa.onrender.com',tmp_path,'bad-hash',fetch)
    assert calls==['/api/sounds/manifest']
    assert not (tmp_path/'manifest.json').exists()


def test_capture_rejects_manifest_changed_midflight(tmp_path):
    data=source();count=0
    def fetch(origin,path,limit):
        nonlocal count
        if path.endswith('manifest'):
            count+=1
            if count>1:data['revision']='changed'
            return json.dumps(data).encode(),'application/json'
        return b'RIFF0000WAVEdata','audio/wav'
    with pytest.raises(ValueError,match='changed'):
        capture('https://uno-luck-pr23-qa.onrender.com',tmp_path,None,fetch)
    assert not (tmp_path/'manifest.json').exists()


def test_unapproved_origin_rejected(tmp_path):
    with pytest.raises(ValueError,match='Unapproved'):
        capture('https://example.invalid',tmp_path)
