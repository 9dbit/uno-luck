import pytest
from fastapi.testclient import TestClient
from app.main import app, ROOMS, Room, make_room, join_room, resume_room, start_game, handle_action, valid_name, RuleError


@pytest.fixture(autouse=True)
def clean_rooms():
    ROOMS.clear()
    yield
    ROOMS.clear()


def test_health_and_static():
    c=TestClient(app)
    assert c.get('/health').json()['money_enabled'] is False
    assert c.get('/').status_code==200
    assert 'UNO LUCK' in c.get('/').text
    assert c.get('/assets/app.js').status_code==200


def test_sanitized_name():
    assert valid_name('  Ayu <danger>  ')=='Ayu danger'
    with pytest.raises(RuleError):valid_name('')
    with pytest.raises(RuleError):valid_name('x'*21)


def test_host_and_guest_room_token_are_secret():
    room,host=make_room('Host')
    r,guest=join_room(room.code,'Guest')
    assert r is room and room.host_id==host.id
    assert resume_room(room.code,guest.token)==(room,guest)
    with pytest.raises(RuleError):resume_room(room.code,'guessed-token')
    with pytest.raises(RuleError):join_room('XXXXXX','Evil')


def test_game_cannot_start_by_guest():
    room,host=make_room('Host')
    _,guest=join_room(room.code,'Guest')
    with pytest.raises(RuleError):start_game(room,guest.id)
    assert room.game is None
    start_game(room,host.id)
    assert len(room.game.players)==4
    assert sum(p['bot'] for p in room.game.players)==2
    with pytest.raises(RuleError):join_room(room.code,'Late')


def test_private_view_no_other_hands_and_server_rejects_bad_actor():
    room,host=make_room('Host')
    _,guest=join_room(room.code,'Guest')
    start_game(room,host.id)
    h=room.lobby_view(host.id)['game']
    g=room.lobby_view(guest.id)['game']
    assert h['me']==host.id and g['me']==guest.id
    assert h['hand'] != g['hand']
    assert 'deck' not in repr(h)
    with pytest.raises(RuleError):handle_action(room,'fake',{ 'action':'draw' })


def test_websocket_create_join_start_and_reconnect():
    client=TestClient(app)
    with client.websocket_connect('/ws') as host_ws:
        host_ws.send_json({'type':'create','name':'Ayu'})
        welcome=host_ws.receive_json();assert welcome['type']=='welcome'
        state=host_ws.receive_json();assert state['game_running'] is False
        code=welcome['room']
        with client.websocket_connect('/ws') as guest_ws:
            guest_ws.send_json({'type':'join','room':code,'name':'Budi'})
            joined=guest_ws.receive_json();assert joined['type']=='welcome'
            assert joined['room']==code
            host_update=host_ws.receive_json()
            assert host_update['member_count']==2
            guest_update=guest_ws.receive_json()
            assert guest_update['member_count']==2
            guest_ws.send_json({'action':'start'})
            denied=guest_ws.receive_json()
            assert denied['type']=='error' and 'Only the room host' in denied['message']
            host_ws.send_json({'action':'start'})
            game_host=host_ws.receive_json()
            game_guest=guest_ws.receive_json()
            assert game_host['game_running'] and game_guest['game_running']
            assert len(game_host['game']['players'])==4
            assert len(game_guest['game']['hand'])==7
        disconnected=host_ws.receive_json()
        assert disconnected['members'][1]['online'] is False
    # Session still present, and has same private hand on reconnect.
    with client.websocket_connect('/ws') as ws:
        ws.send_json({'type':'resume','room':code,'token':joined['token']})
        v=ws.receive_json();assert v['player_id']==joined['player_id']
        board=ws.receive_json();assert board['game']['me']==joined['player_id']
        assert board['game']['hand']==game_guest['game']['hand']


def test_socket_rejects_invalid_requests():
    c=TestClient(app)
    with c.websocket_connect('/ws') as ws:
        ws.send_json({'type':'join','room':'BAD','name':'Budi'})
        assert ws.receive_json()['type']=='error'


def test_room_full():
    room,_=make_room('One')
    for i in range(3):join_room(room.code,f'Player{i}')
    with pytest.raises(RuleError):join_room(room.code,'Fifth')


def test_round_repeat_requires_completed_round():
    room,host=make_room('Host')
    start_game(room,host.id)
    with pytest.raises(RuleError):start_game(room,host.id,new_round=True)
