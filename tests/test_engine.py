import pytest
from app.engine import Card, COLORS, RuleError, UnoGame, classic_deck


def game(n=4):
    return UnoGame([{'id':str(i),'name':f'Player {i}','bot':False} for i in range(n)], seed=3)


def setturn(g, *, hand, top, color='red', turn=0):
    g.hands[str(turn)]=hand
    g.turn_index=turn
    g.phase='turn'
    g.discard=[top]
    g.active_color=color
    g.direction=1
    g.uno_armed=None
    g.uno_candidate=None
    g.pending_plus4=None
    g.drawn_id=None


def test_classic_deck_unique_and_distribution():
    cards=classic_deck()
    assert len(cards)==108 and len({c.id for c in cards})==108
    for color in COLORS:
        assert sum(c.color==color for c in cards)==25
        assert sum(c.color==color and c.kind=='0' for c in cards)==1
        assert sum(c.color==color and c.kind=='+2' for c in cards)==2
    for kind in ('wild','+4'):
        assert sum(c.kind==kind for c in cards)==4


def test_deal_start_and_visibility():
    g=game()
    assert all(len(h)==7 for h in g.hands.values())
    assert g.discard[-1].kind.isdigit()
    assert len(g.deck)==79
    v=g.view('0')
    assert len(v['hand'])==7
    assert set(v['players'][1])=={'id','name','bot','count','score','uno_warning'}
    assert not any('hand' in p for p in v['players'])
    assert 'deck' not in v and 'pending_plus4' not in v


def test_illegal_action_does_not_mutate():
    g=game()
    hand=list(g.hands['0'])
    top=g.discard[-1]
    with pytest.raises(RuleError):g.play('1', hand[0].id)
    with pytest.raises(RuleError):g.play('0', -900)
    assert g.hands['0']==hand and g.discard[-1]==top


def test_play_same_color_or_number_or_wild():
    g=game()
    setturn(g,hand=[Card(900,'green','4'),Card(901,'red','7'),Card(902,'wild','wild'), Card(903,'red','3')],top=Card(899,'red','4'))
    assert set(g.options('0'))=={901,902,903,900}
    with pytest.raises(RuleError):g.play('0',902)
    g.play('0',902,'blue')
    assert g.active_color=='blue' and g.turn_index==1


def test_nonmatching_rejected_and_input_checked():
    g=game()
    setturn(g,hand=[Card(901,'blue','8'),Card(902,'red','4')],top=Card(900,'red','2'))
    with pytest.raises(RuleError):g.play('0',901)
    with pytest.raises(RuleError):g.play('0',902,'red')
    assert g.turn_index==0 and len(g.hands['0'])==2


def test_skip_jumps_and_reverse_changes_direction():
    g=game()
    setturn(g,hand=[Card(901,'red','skip'),Card(902,'blue','9')],top=Card(900,'red','4'))
    g.play('0',901)
    assert g.turn_index==2
    g2=game()
    setturn(g2,hand=[Card(901,'red','reverse'),Card(902,'blue','9')],top=Card(900,'red','4'))
    g2.play('0',901)
    assert g2.turn_index==3 and g2.direction==-1


def test_two_player_reverse_acts_like_skip():
    g=game(2)
    setturn(g,hand=[Card(901,'red','reverse'),Card(902,'blue','9')],top=Card(900,'red','4'))
    g.play('0',901)
    assert g.turn_index==0 and g.direction==1


def test_draw2_targets_next_and_skips():
    g=game()
    setturn(g,hand=[Card(901,'red','+2'),Card(902,'blue','3')],top=Card(900,'red','4'))
    count=len(g.hands['1'])
    g.play('0',901)
    assert len(g.hands['1'])==count+2
    assert g.turn_index==2


def test_legal_plus4_challenge_fails_draw_six_and_skip():
    g=game()
    setturn(g,hand=[Card(901,'wild','+4'),Card(902,'blue','3')],top=Card(900,'red','4'))
    c1=len(g.hands['1']); g.play('0',901,'green')
    assert g.phase=='challenge' and g.turn_index==1
    assert 'legal' not in g.view('1')['challenge']
    g.plus4_decision('1',True)
    assert len(g.hands['1'])==c1+6 and g.turn_index==2


def test_illegal_plus4_challenge_succeeds_and_target_turn():
    g=game()
    setturn(g,hand=[Card(901,'wild','+4'),Card(902,'red','3')],top=Card(900,'red','4'))
    g.play('0',901,'green')
    g.plus4_decision('1',True)
    assert len(g.hands['0'])==5 and g.turn_index==1 and g.phase=='turn'
    assert 'Challenge won' in g.log[-1]


def test_accepted_plus4_deducts_four_and_skips():
    g=game()
    setturn(g,hand=[Card(901,'wild','+4'),Card(902,'blue','3')],top=Card(900,'red','4'))
    before=len(g.hands['1']);g.play('0',901,'yellow');g.plus4_decision('1',False)
    assert len(g.hands['1'])==before+4 and g.turn_index==2 and g.active_color=='yellow'


def test_last_plus4_waits_for_challenge_then_scores():
    g=game()
    setturn(g,hand=[Card(901,'wild','+4')],top=Card(900,'red','4'))
    g.play('0',901,'yellow')
    assert g.winner is None
    g.plus4_decision('1',False)
    assert g.winner=='0' and g.phase=='round_over' and g.last_award>0


def test_last_illegal_plus4_if_challenged_cannot_win():
    g=game()
    setturn(g,hand=[Card(901,'wild','+4'),Card(902,'red','9')],top=Card(900,'red','4'))
    g.play('0',901,'yellow')
    g.plus4_decision('1',True)
    assert g.winner is None and len(g.hands['0'])==5


def test_call_uno_and_catch_penalty():
    g=game()
    setturn(g,hand=[Card(901,'red','3'),Card(902,'red','8')],top=Card(900,'red','4'))
    before=len(g.hands['0']); g.play('0',901)
    assert before==2 and g.uno_candidate=='0' and len(g.hands['0'])==1
    g.catch_uno('1')
    assert len(g.hands['0'])==3 and g.uno_candidate is None


def test_call_uno_in_time_prevents_penalty():
    g=game()
    setturn(g,hand=[Card(901,'red','3'),Card(902,'red','8')],top=Card(900,'red','4'))
    g.call_uno('0');g.play('0',901)
    assert g.uno_candidate is None
    with pytest.raises(RuleError):g.catch_uno('1')


def test_late_self_call_before_caught_prevents_penalty():
    g=game()
    setturn(g,hand=[Card(901,'red','3'),Card(902,'red','8')],top=Card(900,'red','4'))
    g.play('0',901)
    g.call_uno('0')
    assert g.uno_candidate is None


def test_catch_window_closes_on_next_player_draw():
    g=game()
    setturn(g,hand=[Card(901,'red','3'),Card(902,'red','8')],top=Card(900,'red','4'))
    g.play('0',901)
    g.draw('1')
    assert g.uno_candidate is None


def test_after_draw_only_new_card_can_be_played():
    g=game()
    setturn(g,hand=[Card(901,'blue','8'),Card(902,'yellow','2')],top=Card(900,'red','4'))
    g.deck.append(Card(903,'red','7'))
    g.draw('0');assert g.phase=='after_draw' and g.drawn_id==903
    with pytest.raises(RuleError):g.play('0',902)
    g.play('0',903)
    assert g.turn_index==1


def test_keep_drawn_card_passes():
    g=game()
    setturn(g,hand=[Card(901,'blue','8'),Card(902,'yellow','2')],top=Card(900,'red','4'))
    g.deck.append(Card(903,'red','7'))
    g.draw('0');g.keep('0')
    assert g.turn_index==1 and g.phase=='turn' and 903 in [c.id for c in g.hands['0']]


def test_recycle_draw_discards_except_top():
    g=game()
    setturn(g,hand=[Card(901,'blue','8')],top=Card(900,'red','4'))
    g.deck=[]
    g.discard=[Card(800,'red','9'),Card(801,'blue','8'),Card(900,'red','4')]
    g.draw('0')
    assert g.discard[-1].id==900 and len(g.hands['0'])==2


def test_round_scoring_20_for_action_50_for_wild():
    g=game(2)
    setturn(g,hand=[Card(901,'red','7')],top=Card(900,'red','4'))
    g.hands['1']=[Card(903,'green','9'),Card(904,'blue','reverse'),Card(905,'wild','wild')]
    g.play('0',901)
    assert g.winner=='0' and g.last_award==9+20+50 and g.scores['0']==79


def test_bots_finish_or_stop_before_human():
    players=[{'id':'human','name':'You','bot':False}]+[{'id':f'bot{i}','name':f'Bot {i}','bot':True} for i in range(3)]
    g=UnoGame(players,seed=16)
    assert g.run_bots()<300
    if g.phase!='round_over':
        assert g.current_id=='human'


def test_uno_call_cleared_when_player_draws_and_turn_moves():
    game = UnoGame([{"id":"p1","name":"P1"},{"id":"p2","name":"P2"}], seed=21)
    current=game.current_id
    game.hands[current]=game.hands[current][:2]
    game.call_uno(current)
    assert game.uno_armed == current
    # Simulate the end of a turn after a draw or keep: stale UNO never survives.
    game._next_turn()
    assert game.uno_armed is None
