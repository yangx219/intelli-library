"""
Append curated classics into the existing inverted index WITHOUT running index_build_fast.

Use when your corpus is already indexed and you only need ~24 extra PG ids searchable.

Still required afterwards:
  python manage.py index_compute_tfidf

(IDF depends on global N_docs — every posting row must be refreshed.)

Optional (slow; updates recommendations / centrality ranks):
  python manage.py build_doc_graph && python manage.py compute_centrality
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from corpus.curated_classics import CURATED_CLASSICS
from corpus.management.commands.index_build_fast import clean_text, resolve_book_file, tokenize
from corpus.models import Book, IndexStat, Posting, Term


class Command(BaseCommand):
    help = (
        "Incrementally index curated classics into postings/terms (no full wipe). "
        "Run ingest_curated_classics first if .txt files are missing."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default="../books_html_kept",
            help="Corpus directory (same filenames as index_build_fast).",
        )
        parser.add_argument("--topk", type=int, default=3000, help="Max stored term types per book.")
        parser.add_argument("--batch-size", type=int, default=5000)
        parser.add_argument(
            "--force",
            action="store_true",
            help="Drop existing postings for these ids and re-ingest (fixes stale rows).",
        )

    def handle(self, *args, **opts):
        book_dir = Path(opts["dir"]).resolve()
        topk: int = opts["topk"]
        bsize: int = opts["batch_size"]
        force: bool = opts["force"]

        curated_meta = {bid: (title, authors) for bid, title, authors in CURATED_CLASSICS}
        ids_ordered = [bid for bid, _, _ in CURATED_CLASSICS]

        to_process: list[tuple[int, Path]] = []
        for bid in ids_ordered:
            path = resolve_book_file(book_dir, bid)
            if not path:
                self.stdout.write(
                    self.style.WARNING(f"PG#{bid}: no corpus file — run ingest_curated_classics first")
                )
                continue

            exists = Posting.objects.filter(book_id=bid).exists()
            if exists and not force:
                self.stdout.write(f"PG#{bid}: already indexed — skip")
                continue

            if exists and force:
                old_term_ids = list(
                    Posting.objects.filter(book_id=bid).values_list("term_id", flat=True).distinct()
                )
                deleted, _ = Posting.objects.filter(book_id=bid).delete()
                self.stdout.write(f"PG#{bid}: removed {deleted} postings (--force)")
                for tid in old_term_ids:
                    df = Posting.objects.filter(term_id=tid).values("book_id").distinct().count()
                    Term.objects.filter(pk=tid).update(df=df)

            to_process.append((bid, path))

        if not to_process:
            self.stdout.write(self.style.WARNING("Nothing to index."))
            return

        self.stdout.write(f"Vocabulary cache warm-up ({Term.objects.count()} existing terms)...")
        term_cache: dict[str, int] = dict(Term.objects.values_list("term", "id"))

        new_postings: list[Posting] = []
        indexed_ids: list[int] = []

        with transaction.atomic():
            for bid, path in to_process:
                title, authors_list = curated_meta[bid]
                authors_cell = "; ".join(authors_list)

                raw = path.read_text(encoding="utf-8", errors="ignore")
                toks = tokenize(clean_text(raw))
                if not toks:
                    self.stdout.write(self.style.WARNING(f"PG#{bid}: no tokens — skip"))
                    continue

                Book.objects.update_or_create(
                    text_id=bid,
                    defaults=dict(
                        title=title,
                        authors=authors_cell,
                        local_path=str(path.resolve()),
                        doc_len_tokens=len(toks),
                    ),
                )

                counter = Counter(toks)
                items = counter.most_common(topk) if topk and topk > 0 else list(counter.items())

                for term_str, tf in items:
                    tid = term_cache.get(term_str)
                    if tid is None:
                        t = Term.objects.create(term=term_str, df=0)
                        term_cache[term_str] = t.id
                        tid = t.id
                    new_postings.append(Posting(term_id=tid, book_id=bid, tf=tf))

                    if len(new_postings) >= bsize:
                        Posting.objects.bulk_create(new_postings, batch_size=bsize)
                        new_postings = []

                indexed_ids.append(bid)

            if new_postings:
                Posting.objects.bulk_create(new_postings, batch_size=bsize)

            self.stdout.write(f"Refreshing DF for terms touched by books {indexed_ids}...")
            touched_term_ids = (
                Posting.objects.filter(book_id__in=indexed_ids)
                .values_list("term_id", flat=True)
                .distinct()
            )
            for tid in touched_term_ids.iterator(chunk_size=512):
                df = Posting.objects.filter(term_id=tid).values("book_id").distinct().count()
                Term.objects.filter(pk=tid).update(df=df)

            n_docs = Book.objects.count()
            total_tokens = Book.objects.aggregate(s=Sum("doc_len_tokens"))["s"] or 0
            avg_len = float(total_tokens) / float(n_docs) if n_docs else 0.0
            IndexStat.objects.update_or_create(key="N_docs", defaults={"value": str(n_docs)})
            IndexStat.objects.update_or_create(key="avg_doc_len", defaults={"value": str(avg_len)})

        self.stdout.write(self.style.SUCCESS(f"Indexed {len(indexed_ids)} curated book(s)."))
        self.stdout.write(self.style.WARNING("Required next: python manage.py index_compute_tfidf"))
        self.stdout.write(
            "Optional (slow): python manage.py build_doc_graph && python manage.py compute_centrality"
        )
