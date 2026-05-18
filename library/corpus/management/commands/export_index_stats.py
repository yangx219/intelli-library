from django.conf import settings
from django.core.management.base import BaseCommand
from corpus.models import Book, Term, Posting, IndexStat
import csv


class Command(BaseCommand):
    help = "Exporter les données de test TF–IDF et d'index inversé (taille du vocabulaire, nombre de postings, sparsité, etc.)"

    def handle(self, *args, **opts):

        analysis_dir = settings.BASE_DIR.parent / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)

        # Chemins de sortie
        out_global = analysis_dir / "index_global_stats.csv"
        out_books = analysis_dir / "index_book_stats.csv"
        out_vocab = analysis_dir / "vocab_stats.csv"

        self.stdout.write("Export des statistiques TF–IDF et de l'index inversé...")

        # Section 1 : statistiques globales

        try:
            N_docs = int(IndexStat.objects.get(key="N_docs").value)
        except:
            N_docs = Book.objects.count()

        try:
            avg_doc_len = float(IndexStat.objects.get(key="avg_doc_len").value)
        except:
            if N_docs > 0:
                total_len = sum(Book.objects.values_list("doc_len_tokens", flat=True))
                avg_doc_len = total_len / N_docs
            else:
                avg_doc_len = 0

        vocab_size = Term.objects.count()
        posting_total = Posting.objects.count()

        # Écrire index_global_stats.csv
        with out_global.open("w", newline="", encoding="utf8") as f:
            w = csv.writer(f)
            w.writerow(["metric", "value"])
            w.writerow(["N_docs", N_docs])
            w.writerow(["avg_doc_len", avg_doc_len])
            w.writerow(["vocab_size_after_filter", vocab_size])
            w.writerow(["posting_total", posting_total])

        self.stdout.write(f"Statistiques globales de l'index → {out_global}")

        # Section 2 : sparsité TF–IDF et autres métriques par livre
        with out_books.open("w", newline="", encoding="utf8") as f:
            w = csv.writer(f)
            w.writerow([
                "book_id",
                "token_count",
                "tfidf_nonzero",
                "unique_terms",
                "sparsity_percent"
            ])

            for book in Book.objects.all():
                toks = book.doc_len_tokens
                postings = Posting.objects.filter(book=book)

                tfidf_nonzero = postings.count()
                unique_terms = len({p.term_id for p in postings})

                if vocab_size > 0:
                    sparsity = tfidf_nonzero / vocab_size * 100
                else:
                    sparsity = 0

                w.writerow([
                    book.text_id,
                    toks,
                    tfidf_nonzero,
                    unique_terms,
                    f"{sparsity:.3f}"
                ])

        self.stdout.write(f"Statistiques par livre écrites → {out_books}")

        # Section 3 : statistiques du vocabulaire (df par terme)
        with out_vocab.open("w", newline="", encoding="utf8") as f:
            w = csv.writer(f)
            w.writerow(["term_id", "term", "df"])

            for t in Term.objects.all():
                w.writerow([t.id, t.term, t.df])

        self.stdout.write(f"Statistiques du vocabulaire écrites → {out_vocab}")

        self.stdout.write(self.style.SUCCESS("Tous les fichiers CSV ont été générés !"))
