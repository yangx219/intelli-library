# regex_engine/lexer.py

from enum import Enum, auto


class TokenType(Enum):
    LPAREN = auto()   # (
    RPAREN = auto()   # )
    STAR = auto()     # *
    DOT = auto()      # .
    UNION = auto()    # |
    CHAR = auto()     # literal character
    PLUS = auto()     # +
    END = auto()      # end of pattern


class Token:
    def __init__(self, token_type: TokenType, ch: str, index: int):
        self.type = token_type
        self.ch = ch  # only used for CHAR
        self.index = index

    def __repr__(self):
        if self.type == TokenType.CHAR:
            return f"CHAR('{self.ch}')@{self.index}"
        return f"{self.type.name}@{self.index}"


class Lexer:
    def lex(self, pattern: str):
        if pattern is None:
            raise ValueError("pattern == None")

        out = []
        n = len(pattern)

        for i, c in enumerate(pattern):
            if c == '(':
                out.append(Token(TokenType.LPAREN, '\0', i))
            elif c == ')':
                out.append(Token(TokenType.RPAREN, '\0', i))
            elif c == '*':
                out.append(Token(TokenType.STAR, '\0', i))
            elif c == '.':
                out.append(Token(TokenType.DOT, '\0', i))
            elif c == '+':
                out.append(Token(TokenType.PLUS, '\0', i))
            elif c == '|':
                out.append(Token(TokenType.UNION, '\0', i))
            else:
                # CHar (must be printable ASCII 0x20 ~ 0x7E except tab)
                if '\x20' <= c <= '\x7E' and c != '\t':
                    out.append(Token(TokenType.CHAR, c, i))
                else:
                    raise ValueError(f"Unsupported char at {i}: {repr(c)}")

        # END token
        out.append(Token(TokenType.END, '\0', n))
        return out
