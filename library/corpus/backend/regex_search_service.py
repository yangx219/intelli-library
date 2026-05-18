import re
from collections import defaultdict
from corpus.backend.regex_engine.engine import RegexEngine
from corpus.models import Term, Posting, Book, DocumentScore
from corpus.backend.search_utils import compute_tfidf_for_books


def regex_match_token(token: str):
    eng = RegexEngine(token)
    matched_terms = [
        t.term
        for t in Term.objects.all()
        if eng.matches(t.term)
    ]
    if not matched_terms:
        return []

    qs = Term.objects.filter(term__in=matched_terms)
    return list(qs.values_list("id", flat=True))


class RegexSearchService:

    @staticmethod
    def search(pattern: str, centrality="total", limit=30):

        if not pattern:
            return []

        # --- 1. tokens ---
        tokens = pattern.split()
        if not tokens:
            return []

        # --- 2. TF-IDF for each token ---
        token_scores = []
        token_matches = []

        for tok in tokens:
            term_ids = regex_match_token(tok)
            if not term_ids:
                continue

            tfidf_i, matches_i = compute_tfidf_for_books(term_ids)

            if tfidf_i:
                # normalization per token
                vals = list(tfidf_i.values())
                mi, ma = min(vals), max(vals)

                def norm(v):
                    if ma == mi:
                        return 0.0
                    return (v - mi) / (ma - mi)

                norm_map = {bid: norm(v) for bid, v in tfidf_i.items()}
                token_scores.append(norm_map)
                token_matches.append(matches_i)

        if not token_scores:
            return []

        # --- 3. Merge token scores (sum of normalized scores) ---
        total_score = defaultdict(float)
        total_terms = defaultdict(set)

        for score_map, match_map in zip(token_scores, token_matches):
            for bid, v in score_map.items():
                total_score[bid] += v
                total_terms[bid].update(match_map.get(bid, set()))

        # --- 4.  ---
        book_ids = list(total_score.keys())

        books = Book.objects.filter(text_id__in=book_ids)
        book_map = {b.text_id: b for b in books}

        scores = DocumentScore.objects.filter(book_id__in=book_ids)

        if centrality == "pagerank":
            cent_map = {s.book_id: s.pagerank for s in scores}
        elif centrality == "closeness":
            cent_map = {s.book_id: s.closeness for s in scores}
        elif centrality == "betweenness":
            cent_map = {s.book_id: s.betweenness for s in scores}
        elif centrality == "degree":
            cent_map = {s.book_id: s.popularity for s in scores}
        else:
            cent_map = {s.book_id: s.total for s in scores}

        # build items
        items = []
        for bid in book_ids:
            items.append((bid, book_map[bid], total_score[bid], cent_map.get(bid, 0), total_terms[bid]))

        # normalize centrality only
        cents = [x[3] for x in items]
        min_c, max_c = min(cents), max(cents)

        def norm_c(v):
            if v == min_c == max_c:
                return 0.0
            return (v - min_c) / (max_c - min_c)

        a = 0.7
        b = 0.3

        results = []
        for bid, book, score_tf, cent_val, terms in items:
            cent_norm = norm_c(cent_val)
            final_score = a * score_tf + b * cent_norm

            authors = (book.authors or "").split(",")
            authors = [x.strip() for x in authors if x.strip()]

            results.append({
                "book_id": bid,
                "title": book.title,
                "authors": authors,
                "match_terms": sorted(terms),
                "score": final_score,
                "rank_features": {
                    "tfidf": score_tf,
                    "centrality": cent_val,
                    "score": final_score
                }
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
