# regex_engine/dfa.py

from typing import Dict, Set, List, Optional
from collections import deque

from .nfa import Nfa, Node, Edge


# DfaState

class DfaState:
    def __init__(self, id_: int, accept: bool):
        self.id = id_
        self.accept = accept
        self.trans: Dict[str, "DfaState"] = {}  # char -> state

    def add_transition(self, c: str, to: "DfaState"):
        self.trans[c] = to

    def next(self, c: str) -> Optional["DfaState"]:
        return self.trans.get(c)

    def transitions(self):
        return self.trans

    def __repr__(self):
        return f"D{self.id}{'(accept)' if self.accept else ''}"


# DFA container

class Dfa:
    def __init__(self, start: DfaState, states: Set[DfaState]):
        self.start = start
        self.states = states

    def getStart(self):
        return self.start

    def getStates(self):
        return self.states

    def __repr__(self):
        return f"DFA(states={len(self.states)}, start={self.start})"


# DfaBuilder — NFA → DFA (subset construction)

class DfaBuilder:

    def __init__(self, dotAll: bool = False):
        self.dotAll = dotAll

    def build(self, nfa: Nfa) -> Dfa:
        # 1) extract alphabet
        alphabet: Set[str] = set()
        hasDot = False

        for nd in nfa.nodes:
            for e in nd.edges:
                if e.is_epsilon():
                    continue
                if e.is_dot():
                    hasDot = True
                elif e.symbol is not None:
                    alphabet.add(e.symbol)

        # DOT means: match all chars
        if hasDot:
            alphabet = {chr(i) for i in range(256)}

        # 2) start set = epsilon closure(start node)
        startSet = self.epsilon_closure({nfa.start})

        # subset → DfaState
        subset_to_state: Dict[frozenset, DfaState] = {}
        work = deque()

        id_gen = 0
        start_state = DfaState(id_gen, self.contains_accept(startSet))
        id_gen += 1

        subset_to_state[frozenset(startSet)] = start_state
        work.append(startSet)

        # 3) BFS over subsets
        while work:
            T = work.popleft()
            from_state = subset_to_state[frozenset(T)]

            for c in alphabet:
                U = self.epsilon_closure(self.move(T, c))
                if not U:
                    continue

                key = frozenset(U)
                if key not in subset_to_state:
                    new_state = DfaState(id_gen, self.contains_accept(U))
                    id_gen += 1
                    subset_to_state[key] = new_state
                    work.append(U)

                to_state = subset_to_state[key]
                from_state.add_transition(c, to_state)

        return Dfa(start_state, set(subset_to_state.values()))

    # Helper functions

    def epsilon_closure(self, seeds: Set[Node]) -> Set[Node]:
        result = set(seeds)
        stack = list(seeds)

        while stack:
            s = stack.pop()
            for e in s.edges:
                if e.is_epsilon():
                    if e.to not in result:
                        result.add(e.to)
                        stack.append(e.to)
        return result

    def move(self, T: Set[Node], c: str) -> Set[Node]:
        res = set()
        for s in T:
            for e in s.edges:
                if not e.is_epsilon() and self.edge_matches(e, c):
                    res.add(e.to)
        return res

    def edge_matches(self, e: Edge, c: str) -> bool:
        # dot matches everything except newline (unless dotAll=True)
        if e.is_dot():
            return self.dotAll or c != '\n'
        return e.symbol == c

    def contains_accept(self, nodes: Set[Node]) -> bool:
        return any(n.isAccept for n in nodes)


# DfaMatcher — run DFA on input

class DfaMatcher:
    @staticmethod
    def matches(dfa: Dfa, s: str) -> bool:
        cur = dfa.getStart()
        for ch in s:
            cur = cur.next(ch)
            if cur is None:
                return False
        return cur.accept

    @staticmethod
    def matchPrefix(dfa: Dfa, s: str, start: int) -> int:
        cur = dfa.getStart()
        best_len = 0
        length = 0

        for i in range(start, len(s)):
            ch = s[i]
            cur = cur.next(ch)
            if cur is None:
                break
            length += 1
            if cur.accept:
                best_len = length

        return best_len

    @staticmethod
    def findAll(dfa: Dfa, s: str) -> List[List[int]]:
        spans = []
        i = 0
        while i < len(s):
            length = DfaMatcher.matchPrefix(dfa, s, i)
            if length > 0:
                spans.append([i, i + length])
                i += length     # non-overlapping
            else:
                i += 1
        return spans
