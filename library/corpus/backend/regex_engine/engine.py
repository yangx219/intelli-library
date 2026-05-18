from .parser import RegexParser
from .nfa import NfaBuilder
from .dfa import DfaBuilder, DfaMatcher
from .ast import DotNode, StarNode, ConcatNode
class RegexEngine:
    def __init__(self, pattern, ignore_case=False):
        self.pattern = pattern.lower() if ignore_case else pattern
        self.ignore_case = ignore_case

        ast = RegexParser().parse(self.pattern)
        nfa = NfaBuilder().build(ast)
        self.dfa = DfaBuilder().build(nfa)

    def matches(self, word: str) -> bool:
        w = word.lower() if self.ignore_case else word
        return DfaMatcher.matches(self.dfa, w)

    def find_all(self, text: str):
        t = text.lower() if self.ignore_case else text
        return DfaMatcher.findAll(self.dfa, t)


# class RegexEngine:
#
#     def __init__(self, pattern: str, ignore_case=False, wrap=True):
#         """
#         pattern: expression régulière
#         ignore_case: indique s'il faut ignorer la casse
#         wrap: activer la correspondance de sous-chaînes (c.-à-d. .*(pattern).*)
#         """
#         self.pattern = pattern.lower() if ignore_case else pattern
#         self.ignore_case = ignore_case
#
#         # --- parse ---
#         parser = RegexParser()
#         ast = parser.parse(self.pattern)
#
#         # --- wrap for substring match like egrep ---
#         if wrap:
#             ast = self.wrap_for_grep(ast)
#
#         # --- NFA + DFA ---
#         nfa = NfaBuilder().build(ast)
#         self.dfa = DfaBuilder().build(nfa)
#
#     # Faire correspondre le mot entier (term)
#     def matches(self, text: str) -> bool:
#         """
#         Return True if the regex matches anywhere inside text.
#         Puisque nous enveloppons le motif, matches = correspondance de sous-chaîne.
#         """
#         t = text.lower() if self.ignore_case else text
#         return DfaMatcher.matches(self.dfa, t)
#
#     # Trouver tous les segments correspondants (pour la mise en évidence du snippet)
#     def find_all(self, text: str):
#         t = text.lower() if self.ignore_case else text
#         return DfaMatcher.findAll(self.dfa, t)
#
#     # Envelopper : .* (pattern) .*
#     @staticmethod
#     def wrap_for_grep(inner_ast):
#         """
#         Convert pattern into:   '.*(pattern).*'
#         """
#         any_star = StarNode(DotNode())
#         return ConcatNode(any_star, ConcatNode(inner_ast, StarNode(DotNode())))