# regex_engine/parser.py

from .lexer import Lexer, TokenType
from .ast import (
    RegexNode, CharNode, DotNode, StarNode,
    ConcatNode, UnionNode
)


class RegexSyntaxException(Exception):
    def __init__(self, message, index):
        super().__init__(f"{message} at index {index}")
        self.index = index


class RegexParser:

    def __init__(self):
        self.tokens = []
        self.pos = 0

    # Public methods
    def parse(self, pattern: str) -> RegexNode:
        self.tokens = Lexer().lex(pattern)
        self.pos = 0
        node = self.parse_regex()   # regex := union
        self.expect(TokenType.END)
        return node

    # Grammar
    # regex := union
    def parse_regex(self):
        return self.parse_union()

    # union := concat { '|' concat }
    def parse_union(self):
        left = self.parse_concat()
        while self.match(TokenType.UNION):
            right = self.parse_concat()
            left = UnionNode(left, right)
        return left

    # concat := repeat { repeat }
    def parse_concat(self):
        left = self.parse_repeat()
        while self.can_start_atom(self.peek().type):
            right = self.parse_repeat()
            left = ConcatNode(left, right)
        return left

    # repeat := atom ( '*' | '+' )?
    def parse_repeat(self):
        base = self.parse_atom()
        if self.match(TokenType.STAR):
            return StarNode(base)
        if self.match(TokenType.PLUS):
            # B+ => B · (B)*
            return ConcatNode(base, StarNode(base))
        return base

    # atom := CHAR | '.' | '(' regex ')'
    def parse_atom(self):
        t = self.peek()
        if t.type == TokenType.CHAR:
            self.next()
            return CharNode(t.ch)
        elif t.type == TokenType.DOT:
            self.next()
            return DotNode()
        elif t.type == TokenType.LPAREN:
            self.next()  # consume '('
            inside = self.parse_regex()
            self.expect(TokenType.RPAREN)
            return inside
        else:
            raise self.error("Expected CHAR, '.' or '('", t.index)

    # Helpers

    def peek(self):
        return self.tokens[self.pos]

    def next(self):
        t = self.tokens[self.pos]
        self.pos = min(self.pos + 1, len(self.tokens))
        return t

    def match(self, token_type: TokenType):
        if self.peek().type == token_type:
            self.next()
            return True
        return False

    def expect(self, token_type: TokenType):
        t = self.peek()
        if t.type != token_type:
            raise self.error(f"Expected {token_type} but found {t.type}", t.index)
        return self.next()

    @staticmethod
    def can_start_atom(ttype: TokenType):
        return ttype in (TokenType.CHAR, TokenType.DOT, TokenType.LPAREN)

    def error(self, msg, index):
        return RegexSyntaxException(msg, index)
