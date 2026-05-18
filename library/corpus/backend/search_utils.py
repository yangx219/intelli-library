
import re
from typing import List, Dict
from nltk.stem import PorterStemmer

from corpus.models import Term, Posting

from typing import List
from corpus.backend.regex_engine.engine import RegexEngine
from corpus.models import Term


# 1. Prétraitement de la requête : minuscule + tokenisation + stemming
def preprocess_query(query: str):
    """
    Préparer la requête du SearchService : minuscule → découpe → stemming
    """
    if not query:
        return []

    q_norm = query.strip().lower()
    if not q_norm:
        return []

    # Découper en tokens
    tokens = [t for t in re.split(r"\W+", q_norm) if t]

    # Stemming (cohérent avec search)
    stemmer = PorterStemmer()
    tokens = [stemmer.stem(t) for t in tokens]



    return tokens


# 2. Correspondance des termes
# -----------------------------
def get_term_ids(tokens: List[str]) -> List[int]:
    """
    Rechercher dans la table des termes les identifiants correspondants
    """
    if not tokens:
        return []
    qs = Term.objects.filter(term__in=tokens)
    return list(qs.values_list("id", flat=True))


# -----------------------------
# 3. Correspondance des postings + calcul du TF-IDF par livre
# -----------------------------
def compute_tfidf_for_books(term_ids: List[int]):
    """
    Interroger la table posting à partir des term_ids
    - TF-IDF total pour chaque livre
    - Ensemble des termes trouvés par livre
    """
    if not term_ids:
        return {}, {}

    postings = Posting.objects.filter(term_id__in=term_ids).select_related("book", "term")

    tfidf_by_book = {}
    matched_terms = {}

    for p in postings:
        bid = p.book_id
        tfidf_by_book[bid] = tfidf_by_book.get(bid, 0.0) + p.tfidf
        matched_terms.setdefault(bid, set()).add(p.term.term)

    return tfidf_by_book, matched_terms


def regex_search(pattern):
    engine = RegexEngine(pattern, wrap=False)

    matches = []
    for t in Term.objects.all().values_list("term", flat=True):
        if engine.matches(t):
            matches.append(t)

    return matches



def get_regex_term_ids(tokens: List[str]) -> List[int]:
    """
    Faire correspondre chaque token avec RegexEngine, relation OR entre tokens (un seul match suffit)
    """

    if not tokens:
        return []

    matched_term_set = set()   # Sert à accumuler les chaînes de termes trouvées

    # Effectuer une recherche regex pour chaque token
    for tok in tokens:
        engine = RegexEngine(tok)

        for t in Term.objects.all():
            if engine.matches(t.term):     # Ajouter en cas de correspondance
                matched_term_set.add(t.term)

    # Récupérer les term_ids
    if not matched_term_set:
        return []

    qs = Term.objects.filter(term__in=matched_term_set)
    return list(qs.values_list("id", flat=True))
