"""Server-authoritative UNO-like Classic rules for UNO LUCK staging.

108-card Classic deck, no +2/+4 stacking. Each new round deals seven cards,
uses a number as opening discard, supports challenge +4 and official-style UNO calls.
"""
from __future__ import annotations
from dataclasses import dataclass
import random
from typing import Any

COLORS = ("red", "yellow", "green", "blue")
SPECIAL = ("skip", "reverse", "+2")
WILDS = ("wild", "+4")
VALID_KINDS = tuple(map(str, range(10))) + SPECIAL + WILDS


@dataclass(frozen=True)
class Card:
    id: int
    color: str
    kind: str

    def view(self) -> dict[str, Any]:
        return {"id": self.id, "color": self.color, "kind": self.kind}


def classic_deck() -> list[Card]:
    cards: list[Card] = []
    for color in COLORS:
        cards.append(Card(len(cards), color, "0"))
        for kind in list(map(str, range(1, 10))) + list(SPECIAL):
            for _ in range(2):
                cards.append(Card(len(cards), color, kind))
    for kind in WILDS:
        for _ in range(4):
            cards.append(Card(len(cards), "wild", kind))
    assert len(cards) == 108
    assert len({c.id for c in cards}) == 108
    return cards


class RuleError(ValueError):
    """Illegal action which must not mutate game state."""


class UnoGame:
    def __init__(self, players: list[dict[str, Any]], *, seed: int | None = None,
                 previous_scores: dict[str, int] | None = None) -> None:
        if not 2 <= len(players) <= 4:
            raise ValueError("UNO LUCK supports 2 to 4 seats")
        ids = [p["id"] for p in players]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate player id")
        self.rng = random.Random(seed)
        self.players = [dict(p) for p in players]
        self.deck = classic_deck()
        self.rng.shuffle(self.deck)
        self.hands: dict[str, list[Card]] = {pid: [] for pid in ids}
        for _ in range(7):
            for pid in ids:
                self.hands[pid].append(self.deck.pop())
        # Start every demonstration round on a neutral number. Action-card
        # starters are a Classic optional extension to address in the next ruleset.
        for i in range(len(self.deck) - 1, -1, -1):
            if self.deck[i].kind.isdigit():
                opening = self.deck.pop(i)
                break
        else:
            raise RuntimeError("No initial card")
        self.discard: list[Card] = [opening]
        self.active_color = opening.color
        self.direction = 1
        self.turn_index = 0
        self.phase = "turn"  # turn | after_draw | challenge | round_over
        self.drawn_id: int | None = None
        self.pending_plus4: dict[str, Any] | None = None
        self.uno_armed: str | None = None
        self.uno_candidate: str | None = None
        self.winner: str | None = None
        self.last_award = 0
        self.scores: dict[str, int] = {pid: (previous_scores or {}).get(pid, 0) for pid in ids}
        self.log: list[str] = ["The cards are dealt. Good luck!"]

    @property
    def current_id(self) -> str:
        return self.players[self.turn_index]["id"]

    def _next_index(self, offset: int = 1) -> int:
        return (self.turn_index + self.direction * offset) % len(self.players)

    def _next_turn(self, offset: int = 1) -> None:
        self.turn_index = self._next_index(offset)
        self.phase = "turn"
        self.drawn_id = None
        # UNO declarations are valid for the present play only. They must not
        # survive a draw/keep and accidentally immunize a later turn.
        self.uno_armed = None

    def _label(self, player: str) -> str:
        return next((p["name"] for p in self.players if p["id"] == player), "Player")

    def _event(self, value: str) -> None:
        self.log.append(value)
        self.log = self.log[-40:]

    def _ensure_turn(self, player: str, *, phases: tuple[str, ...] = ("turn",)) -> None:
        if self.phase not in phases:
            raise RuleError("That action isn't available right now")
        if player != self.current_id:
            raise RuleError("Wait for your turn")

    def legal_card(self, card: Card) -> bool:
        if card.color == "wild":
            return True
        top = self.discard[-1]
        return card.color == self.active_color or card.kind == top.kind

    def options(self, player: str) -> list[int]:
        if player != self.current_id or self.phase not in ("turn", "after_draw"):
            return []
        return [c.id for c in self.hands[player] if self.legal_card(c)
                and (self.phase != "after_draw" or c.id == self.drawn_id)]

    def _draw(self, pid: str, amount: int) -> list[Card]:
        drawn: list[Card] = []
        for _ in range(amount):
            if not self.deck:
                if len(self.discard) < 2:
                    break  # All cards are in hands; extremely rare.
                top = self.discard.pop()
                self.deck = self.discard
                self.discard = [top]
                self.rng.shuffle(self.deck)
            card = self.deck.pop()
            self.hands[pid].append(card)
            drawn.append(card)
        return drawn

    def _clear_catch_window(self, actor: str) -> None:
        # Window remains open until the next player's first actual game action.
        if self.uno_candidate is not None and self.uno_candidate != actor:
            self.uno_candidate = None

    def call_uno(self, player: str) -> None:
        if self.phase in ("turn", "after_draw") and player == self.current_id:
            if len(self.hands[player]) != 2:
                raise RuleError("Press UNO when you have exactly two cards")
            self.uno_armed = player
            self._event(f"{self._label(player)} called UNO!")
            return
        # A player who forgot may still declare before being caught.
        if self.uno_candidate == player and len(self.hands[player]) == 1:
            self.uno_candidate = None
            self._event(f"{self._label(player)} called UNO just in time!")
            return
        raise RuleError("UNO is not available now")

    def catch_uno(self, player: str) -> None:
        victim = self.uno_candidate
        if self.phase == "round_over" or not victim or victim == player:
            raise RuleError("There is no uncalled UNO to catch")
        if player not in self.hands:
            raise RuleError("You are not a player")
        if len(self.hands[victim]) != 1:
            self.uno_candidate = None
            raise RuleError("UNO window has expired")
        self.uno_candidate = None
        self._draw(victim, 2)
        self._event(f"{self._label(player)} caught {self._label(victim)}: +2 penalty")

    def play(self, player: str, card_id: int, choice: str | None = None) -> None:
        self._ensure_turn(player, phases=("turn", "after_draw"))
        if not isinstance(card_id, int) or isinstance(card_id, bool):
            raise RuleError("Invalid card")
        card = next((c for c in self.hands[player] if c.id == card_id), None)
        if card is None:
            raise RuleError("This card is not in your hand")
        if self.phase == "after_draw" and self.drawn_id != card_id:
            raise RuleError("You may only play the card you just drew")
        if not self.legal_card(card):
            raise RuleError("Card must match color, value or action")
        if card.color == "wild" and choice not in COLORS:
            raise RuleError("Choose a valid color")
        if card.color != "wild" and choice is not None:
            raise RuleError("Only Wild cards choose a color")
        previous_color = self.active_color
        plus4_is_legal = not any(c.color == previous_color for c in self.hands[player] if c.id != card_id)
        self._clear_catch_window(player)
        had_two = len(self.hands[player]) == 2
        self.hands[player].remove(card)
        self.discard.append(card)
        self.active_color = choice if card.color == "wild" else card.color
        self.drawn_id = None
        self._event(f"{self._label(player)} played {self._color_kind(card)}")
        if had_two and self.uno_armed != player:
            self.uno_candidate = player
        elif self.uno_candidate == player:
            self.uno_candidate = None
        self.uno_armed = None

        if card.kind == "+4":
            offender = player
            target_index = self._next_index()
            target = self.players[target_index]["id"]
            self.pending_plus4 = {"offender": offender, "target": target,
                                  "legal": plus4_is_legal, "color_before": previous_color}
            self.turn_index = target_index
            self.phase = "challenge"
            self._event(f"{self._label(target)}: accept +4 or challenge")
            return
        if card.kind == "+2":
            target = self.players[self._next_index()]["id"]
            self._draw(target, 2)
            self._event(f"{self._label(target)} drew two and was skipped")
            if not self._settle_if_empty(player):
                self._next_turn(2)
            return
        if card.kind == "skip":
            if not self._settle_if_empty(player):
                self._next_turn(2)
            return
        if card.kind == "reverse":
            if len(self.players) == 2:
                if not self._settle_if_empty(player):
                    self._next_turn(2)  # Reverse is a Skip in two-player mode.
            else:
                self.direction *= -1
                if not self._settle_if_empty(player):
                    self._next_turn()
            return
        if not self._settle_if_empty(player):
            self._next_turn()

    @staticmethod
    def _color_kind(card: Card) -> str:
        return card.kind if card.color == "wild" else f"{card.color} {card.kind}"

    def _settle_if_empty(self, player: str) -> bool:
        if self.hands[player]:
            return False
        self.winner = player
        self.phase = "round_over"
        self.pending_plus4 = None
        self.uno_candidate = None
        self.last_award = sum(self.card_points(c)
                              for pid, hand in self.hands.items() if pid != player for c in hand)
        self.scores[player] += self.last_award
        self._event(f"{self._label(player)} wins the round (+{self.last_award} points)!")
        return True

    @staticmethod
    def card_points(card: Card) -> int:
        if card.kind.isdigit():
            return int(card.kind)
        return 50 if card.kind in WILDS else 20

    def draw(self, player: str) -> None:
        self._ensure_turn(player)
        self._clear_catch_window(player)
        picked = self._draw(player, 1)
        if not picked:
            self._event("Draw deck exhausted")
            self._next_turn()
            return
        card = picked[0]
        self._event(f"{self._label(player)} drew one card")
        if self.legal_card(card):
            self.phase = "after_draw"
            self.drawn_id = card.id
        else:
            self._next_turn()

    def keep(self, player: str) -> None:
        self._ensure_turn(player, phases=("after_draw",))
        self._clear_catch_window(player)
        self._event(f"{self._label(player)} kept the drawn card")
        self._next_turn()

    def plus4_decision(self, player: str, challenge: bool) -> None:
        self._ensure_turn(player, phases=("challenge",))
        pending = self.pending_plus4
        if not pending or pending["target"] != player:
            raise RuleError("No challenge is pending for you")
        offender = pending["offender"]
        self.pending_plus4 = None
        self.uno_candidate = None
        if not challenge:
            self._draw(player, 4)
            self._event(f"{self._label(player)} accepted +4 and lost their turn")
            if not self._settle_if_empty(offender):
                self._next_turn()
            return
        if pending["legal"]:
            self._draw(player, 6)
            self._event(f"Challenge failed: {self._label(player)} drew 6 and was skipped")
            if not self._settle_if_empty(offender):
                self._next_turn()
        else:
            self._draw(offender, 4)
            self._event(f"Challenge won: {self._label(offender)} illegally played +4 and drew 4")
            self.phase = "turn"  # The challenger gets their regular turn.
            self.drawn_id = None

    def bot_step(self) -> bool:
        if self.phase == "round_over":
            return False
        actor = next((p for p in self.players if p["id"] == self.current_id), None)
        if not actor or not actor.get("bot"):
            return False
        pid = actor["id"]
        if self.uno_candidate and self.uno_candidate != pid:
            # This is a nonstrategic demo opponent, not hidden-information cheating.
            self.catch_uno(pid)
        if self.phase == "challenge":
            self.plus4_decision(pid, challenge=self.rng.random() < 0.25)
            return True
        if len(self.hands[pid]) == 2:
            self.call_uno(pid)
        legal_ids = set(self.options(pid))
        valid = [c for c in self.hands[pid] if c.id in legal_ids]
        if valid:
            # Prefer a non-Wild card and use special cards tactically.
            def rank(card: Card) -> tuple[int, int, float]:
                own_color_count = sum(c.color == card.color for c in self.hands[pid])
                return (int(card.color != "wild"), int(card.kind in ("skip", "reverse", "+2")),
                        own_color_count + self.rng.random() / 10)
            c = max(valid, key=rank)
            color = self._bot_color(pid, exclude=c.id) if c.color == "wild" else None
            self.play(pid, c.id, color)
            return True
        if self.phase == "after_draw":
            self.keep(pid)
            return True
        self.draw(pid)
        return True

    def _bot_color(self, pid: str, *, exclude: int) -> str:
        counts = {color: sum(c.color == color for c in self.hands[pid] if c.id != exclude)
                  for color in COLORS}
        return max(COLORS, key=lambda color: (counts[color], self.rng.random()))

    def run_bots(self, limit: int = 300) -> int:
        steps = 0
        while steps < limit and self.bot_step():
            steps += 1
        if steps == limit:
            self._event("Bot action limit reached; administrator review required")
        return steps

    def view(self, pid: str) -> dict[str, Any]:
        if pid not in self.hands:
            raise RuleError("Unknown player")
        return {
            "players": [{"id": p["id"], "name": p["name"], "bot": bool(p.get("bot")),
                         "count": len(self.hands[p["id"]]), "score": self.scores[p["id"]],
                         "uno_warning": self.uno_candidate == p["id"]}
                        for p in self.players],
            "me": pid,
            "hand": [c.view() for c in self.hands[pid]],
            "top": self.discard[-1].view(), "active_color": self.active_color,
            "turn": self.current_id, "direction": self.direction, "phase": self.phase,
            "legal_ids": self.options(pid), "drawn_id": self.drawn_id if self.current_id == pid else None,
            "uno_armed": self.uno_armed == pid, "uno_candidate": self.uno_candidate,
            "challenge": ({"target": self.pending_plus4["target"],
                           "offender": self.pending_plus4["offender"]}
                          if self.pending_plus4 else None),
            "winner": self.winner, "award": self.last_award,
            "logs": self.log[-12:],
        }
