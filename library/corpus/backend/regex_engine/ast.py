# regex_engine/ast.py

class RegexNode:
    """Base interface (empty just like Java)."""
    pass


class CharNode(RegexNode):
    """Single literal character."""
    def __init__(self, ch: str):
        self.ch = ch  # a single character

    def __repr__(self):
        return f"'{self.ch}'"


class ConcatNode(RegexNode):
    """Concatenation: left · right"""
    def __init__(self, left: RegexNode, right: RegexNode):
        self.left = left
        self.right = right

    def __repr__(self):
        return f"({self.left}·{self.right})"


class DotNode(RegexNode):
    """Wildcard '.' matches any character."""
    def __repr__(self):
        return "."


class StarNode(RegexNode):
    """Kleene star: (child)*"""
    def __init__(self, child: RegexNode):
        self.child = child

    def __repr__(self):
        return f"({self.child})*"


class UnionNode(RegexNode):
    """Union (OR): left | right"""
    def __init__(self, left: RegexNode, right: RegexNode):
        self.left = left
        self.right = right

    def __repr__(self):
        return f"({self.left}|{self.right})"
