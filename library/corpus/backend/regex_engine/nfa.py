# regex_engine/nfa.py

from typing import Optional, Set, List
from .ast import (
    CharNode, DotNode, ConcatNode, UnionNode, StarNode, RegexNode
)


# Edge

class Edge:
    """
    Directed edge in NFA.

    symbol = None  →  epsilon transition
    symbol = Edge.DOT  → wildcard '.'
    symbol = normal character
    """

    DOT = '\0'   # same as Java: '\u0000'

    def __init__(self, symbol: Optional[str], to: "Node"):
        self.symbol = symbol   # None = epsilon; DOT='\0'; char
        self.to = to

    def is_epsilon(self):
        return self.symbol is None

    def is_dot(self):
        return self.symbol == Edge.DOT

    def __repr__(self):
        if self.symbol is None:
            return f"--ε-->{self.to}"
        if self.symbol == Edge.DOT:
            return f"--.-->{self.to}"
        return f"--{self.symbol}-->{self.to}"


# Node

class Node:
    """NFA state."""
    def __init__(self, id_: int):
        self.id = id_
        self.edges: List[Edge] = []
        self.isAccept: bool = False

    def __repr__(self):
        if self.isAccept:
            return f"Node({self.id}, accept)"
        return f"Node({self.id})"


# Fragment (start + outStates)

class Fragment:
    def __init__(self, start: Node, outStates: Set[Node]):
        self.start = start
        self.outStates = outStates


# Final NFA (start node + set of all nodes)

class Nfa:
    def __init__(self, start: Node, nodes: Set[Node]):
        self.start = start
        self.nodes = nodes


# NFA Builder (Thompson construction)

class NfaBuilder:

    def __init__(self):
        self.nextId = 0
        self.all: Set[Node] = set()

    # new NFA state
    def new_node(self) -> Node:
        n = Node(self.nextId)
        self.nextId += 1
        self.all.add(n)
        return n

    # entry point
    def build(self, root: RegexNode) -> Nfa:
        frag = self.build_frag(root)

        # mark accept states
        for node in frag.outStates:
            node.isAccept = True

        return Nfa(frag.start, self.all)

    # Recursive AST → fragment

    def build_frag(self, n: RegexNode) -> Fragment:
        from .ast import (
            CharNode, DotNode, ConcatNode, UnionNode, StarNode
        )
        if isinstance(n, CharNode):
            return self.literal(n.ch)
        if isinstance(n, DotNode):
            return self.dot()
        if isinstance(n, ConcatNode):
            left = self.build_frag(n.left)
            right = self.build_frag(n.right)
            return self.concat(left, right)
        if isinstance(n, UnionNode):
            a = self.build_frag(n.left)
            b = self.build_frag(n.right)
            return self.union(a, b)
        if isinstance(n, StarNode):
            x = self.build_frag(n.child)
            return self.star(x)

        raise ValueError(f"Unknown AST node type: {type(n)}")

    # Fragment operations

    # literal character
    def literal(self, ch: str) -> Fragment:
        s = self.new_node()
        t = self.new_node()
        s.edges.append(Edge(ch, t))
        return Fragment(s, {t})

    # DOT node
    def dot(self) -> Fragment:
        s = self.new_node()
        t = self.new_node()
        s.edges.append(Edge(Edge.DOT, t))
        return Fragment(s, {t})

    # concat
    def concat(self, X: Fragment, Y: Fragment) -> Fragment:
        for x_end in X.outStates:
            x_end.edges.append(Edge(None, Y.start))  # ε transition
        return Fragment(X.start, Y.outStates)

    # union
    def union(self, X: Fragment, Y: Fragment) -> Fragment:
        s = self.new_node()
        t = self.new_node()

        # branch
        s.edges.append(Edge(None, X.start))
        s.edges.append(Edge(None, Y.start))

        # merge
        for xe in X.outStates:
            xe.edges.append(Edge(None, t))
        for ye in Y.outStates:
            ye.edges.append(Edge(None, t))

        return Fragment(s, {t})

    # star
    def star(self, X: Fragment) -> Fragment:
        s = self.new_node()
        t = self.new_node()

        s.edges.append(Edge(None, t))
        s.edges.append(Edge(None, X.start))

        for xe in X.outStates:
            xe.edges.append(Edge(None, t))
            xe.edges.append(Edge(None, X.start))

        return Fragment(s, {t})
