from django.core.management.base import BaseCommand
from django.db import transaction, connection
from pathlib import Path
import csv
import re
import sys
from collections import Counter

from corpus.models import Book, Term, Posting, IndexStat

# Nettoyage du texte
START_RE = re.compile(r'\*{3}\s*START OF .*?PROJECT GUTENBERG EBOOK.*?\*{3}', re.I)
END_RE   = re.compile(r'\*{3}\s*END OF .*?PROJECT GUTENBERG EBOOK.*?\*{3}', re.I)
LICENSE_RE = re.compile(r"START:\s*FULL\s*LICENSE", re.I)

# Extraction des mots : uniquement a-z
WORD_RE = re.compile(r"[A-Za-z]+")

# Liste des mots vides
STOPWORDS = {
    "a","an","and","are","as","at","be","but","by","for","if","in","into","is","it",
    "no","not","of","on","or","such","that","the","their","then","there","these",
    "they","this","to","was","will","with","so","than","too","very","can","from",
    "do","does","did","am","have","has","had",
    "he","him","his","she","her","hers","me","my","mine","you","your","yours",
    "we","our","ours","us","them","those","which","what","who","whom",
    "been","being","shall","should","would","could","may","might","must",
    "i","im","youre","youve","youll","cant","dont","didnt","wont","theres",
    "here","where","when","why","how","any","all","each","every","few",
    "more","most","other","some","only","own","same","too",
}

# Stemming (PorterStemmer)
from nltk.stem import PorterStemmer
stemmer = PorterStemmer()


# Nettoyage du texte : retirer la licence, le début et la fin
def clean_text(raw: str) -> str:
    # Couper d'abord la licence
    m1 = LICENSE_RE.search(raw)
    cut = raw[:m1.start()] if m1 else raw

    # Ensuite supprimer "*** START OF ..."
    m2 = START_RE.search(cut)
    body = cut[m2.end():] if m2 else cut

    # Enfin supprimer "*** END OF ..."
    m3 = END_RE.search(body)
    body = body[:m3.start()] if m3 else body

    return body


# Tokenisation : segmentation + minuscule + stopwords + filtrage longueur + stemming
def tokenize(s: str):
    tokens = []
    for tok in WORD_RE.findall(s):
        tok = tok.lower()

        if tok in STOPWORDS:
            continue
        if len(tok) < 2:
            continue
        # Optionnel : filtrer les tokens très longs, souvent du bruit
        if len(tok) > 25:
            continue

        tok = stemmer.stem(tok)
        tokens.append(tok)

    return tokens


def resolve_book_file(book_dir: Path, tid: int) -> Path | None:
    """Prefer `{id}.txt`, then `.html` / `.htm` mirrors."""
    for name in (f"{tid}.txt", f"{tid}.html", f"{tid}.htm"):
        p = book_dir / name
        if p.is_file():
            return p
    return None


# Commande principale
class Command(BaseCommand):
    help = "Construire l'index inversé (ordre DF correct, TopK + filtrage haute/basse fréquence)"

    def add_arguments(self, parser):
        parser.add_argument("--meta", default="../data/selected_meta.csv")
        parser.add_argument("--dir", default="../books_html_kept")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--topk", type=int, default=3000)      # Nombre maximal de mots TopK par livre
        parser.add_argument("--batch-size", type=int, default=5000)

    def handle(self, *args, **opts):

        meta_csv = Path(opts["meta"]).resolve()
        book_dir = Path(opts["dir"]).resolve()
        rows = list(csv.DictReader(meta_csv.open(encoding="utf8", errors="ignore")))

        if opts["limit"] > 0:
            rows = rows[:opts["limit"]]

        topk  = opts["topk"]
        bsize = opts["batch_size"]

        posting_buf = []
        term_cache = {}   # term_str -> term_id

        total_docs = 0
        total_len = 0

        n_files = sum(
            1
            for p in book_dir.iterdir()
            if p.is_file() and p.suffix.lower() in (".txt", ".html", ".htm")
        )
        self.stdout.write(
            f"Starting index build — CSV rows: {len(rows)}, "
            f"topk terms/book: {topk}, batch_size: {bsize}, corpus files (.txt/.html/.htm): {n_files}"
        )
        self.stdout.write(
            "(If this looks stuck: clearing huge posting tables can take many minutes with no extra lines.)"
        )
        sys.stdout.flush()

        with transaction.atomic():

            # Étape 0 : nettoyer les anciennes données (uniquement dans cette base d'index dédiée)
            self.stdout.write("Step 0/6: deleting existing postings (slow on large DBs)...")
            sys.stdout.flush()
            deleted_p, _ = Posting.objects.all().delete()
            self.stdout.write(f"  postings removed: {deleted_p}")
            sys.stdout.flush()
            self.stdout.write("Step 0/6: deleting existing terms...")
            sys.stdout.flush()
            deleted_t, _ = Term.objects.all().delete()
            self.stdout.write(f"  term rows removed: {deleted_t}")
            sys.stdout.flush()

            # Étape 1 : parcourir les livres (nettoyage, tokenisation, Counter, TopK, création des Postings)
            self.stdout.write("Step 1/6: scanning corpus and bulk-inserting postings...")
            sys.stdout.flush()
            for i, row in enumerate(rows, 1):

                tid_str = (row.get("Text#") or "").strip()
                if not tid_str.isdigit():
                    continue
                tid = int(tid_str)

                p = resolve_book_file(book_dir, tid)
                if not p:
                    continue

                raw = p.read_text(encoding="utf8", errors="ignore")
                toks = tokenize(clean_text(raw))

                if not toks:
                    continue

                book, _ = Book.objects.update_or_create(
                    text_id=tid,
                    defaults=dict(
                        title=row.get("Title", ""),
                        authors=row.get("Authors", ""),
                        local_path=str(p.resolve()),
                        doc_len_tokens=len(toks),
                    )
                )

                total_docs += 1
                total_len += len(toks)

                if total_docs == 1:
                    self.stdout.write(
                        f"  first book indexed: Text#{tid} "
                        f"(very large books can take minutes before the next progress line)"
                    )
                    sys.stdout.flush()

                counter = Counter(toks)

                # Limiter aux mots les plus fréquents (topk <= 0 signifie pas de troncature)
                if topk and topk > 0:
                    items = counter.most_common(topk)
                else:
                    items = counter.items()

                for term_str, tf in items:
                    if term_str not in term_cache:
                        t = Term.objects.create(term=term_str, df=0)
                        term_cache[term_str] = t.id

                    posting_buf.append(Posting(
                        term_id=term_cache[term_str],
                        book=book,
                        tf=tf,
                    ))

                    if len(posting_buf) >= bsize:
                        Posting.objects.bulk_create(posting_buf, batch_size=bsize)
                        posting_buf = []

                if total_docs > 0 and total_docs % 10 == 0:
                    self.stdout.write(f"  ... {total_docs} books indexed (CSV row {i}/{len(rows)})")
                    sys.stdout.flush()

            if posting_buf:
                Posting.objects.bulk_create(posting_buf, batch_size=bsize)

            if total_docs == 0:
                self.stdout.write(self.style.WARNING("No books could be indexed — aborting."))
                return

            # Étape 2 : calculer correctement DF (source unique = Postings)
            term_total = Term.objects.count()
            self.stdout.write(f"Step 2/6: recomputing DF for {term_total} terms (one DB query per term)...")
            sys.stdout.flush()
            for n, term in enumerate(Term.objects.iterator(chunk_size=256), 1):
                df = (
                    Posting.objects.filter(term_id=term.id).values("book_id").distinct().count()
                )
                term.df = df
                term.save(update_fields=["df"])
                if n % 500 == 0:
                    self.stdout.write(f"  ... DF progress {n}/{term_total}")
                    sys.stdout.flush()

            N = total_docs

            # Étape 3 : filtrage DF haute fréquence / basse fréquence
            self.stdout.write("Step 3/6: pruning terms by DF (high / low frequency)...")
            sys.stdout.flush()

            # Haute fréquence : DF >= 95% des documents (the, and, of...)
            high_cut = int(N * 0.95)
            if high_cut > 0:
                Term.objects.filter(df__gte=high_cut).delete()

            # Basse fréquence : DF <= 2 (bruit, fautes, noms propres, etc.)
            Term.objects.filter(df__lte=2).delete()

            # Étape 4 : supprimer les Postings orphelins
            self.stdout.write("Step 4/6: deleting orphan postings...")
            sys.stdout.flush()
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM postings WHERE term_id NOT IN (SELECT id FROM terms);"
                )

            # Étape 5 : recalcul final de DF pour garantir la cohérence
            term_total2 = Term.objects.count()
            self.stdout.write(f"Step 5/6: final DF pass for {term_total2} terms...")
            sys.stdout.flush()
            for n, term in enumerate(Term.objects.iterator(chunk_size=256), 1):
                df = (
                    Posting.objects.filter(term_id=term.id).values("book_id").distinct().count()
                )
                term.df = df
                term.save(update_fields=["df"])
                if n % 500 == 0:
                    self.stdout.write(f"  ... final DF {n}/{term_total2}")
                    sys.stdout.flush()

            # Étape 6 : statistiques
            self.stdout.write("Step 6/6: writing index stats...")
            sys.stdout.flush()
            avg_len = total_len / total_docs
            IndexStat.objects.update_or_create(
                key="N_docs", defaults={"value": str(total_docs)}
            )
            IndexStat.objects.update_or_create(
                key="avg_doc_len", defaults={"value": str(avg_len)}
            )

        self.stdout.write(self.style.SUCCESS("Inverted index build finished."))
        self.stdout.write(f"Documents: {total_docs}, avg length: {avg_len:.2f} tokens")
        self.stdout.write(f"Vocabulary size: {Term.objects.count()} terms")
