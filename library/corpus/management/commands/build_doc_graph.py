from django.core.management.base import BaseCommand
from corpus.models import Book, Posting, DocumentGraph
from math import sqrt

class Command(BaseCommand):
    help = "Build document similarity graph (G_d) using cosine similarity."

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print each edge (very noisy for large catalogues)",
        )

    # ----------------------------
    # Calculer le cosinus de deux vecteurs TF-IDF
    # ----------------------------
    def cosine(self, vecA, vecB):
        # Seuls les termes communs contribuent au produit scalaire
        common_terms = set(vecA.keys()) & set(vecB.keys())

        if not common_terms:
            return 0.0

        dot = sum(vecA[t] * vecB[t] for t in common_terms)

        normA = sqrt(sum(v*v for v in vecA.values()))
        normB = sqrt(sum(v*v for v in vecB.values()))

        if normA == 0 or normB == 0:
            return 0.0

        return dot / (normA * normB)

    # ----------------------------
    # Logique principale : construire G_d
    # ----------------------------
    def handle(self, *args, **options):
        verbose = options["verbose"]
        self.stdout.write(self.style.SUCCESS("Building document similarity graph (G_d)..."))

        DocumentGraph.objects.all().delete()
        self.stdout.write("Cleared old document_graph table.")

        books = list(Book.objects.all())
        total = len(books)

        vectors = {}
        for book in books:
            postings = Posting.objects.filter(book=book, tfidf__gt=0)
            vectors[book.text_id] = {p.term_id: p.tfidf for p in postings}

        threshold = 0.05

        pairs_total = total * (total - 1) // 2 if total > 1 else 0
        processed = 0
        report_every = max(1, min(5000, pairs_total // 25)) if pairs_total else 1
        edges_buf: list[DocumentGraph] = []
        batch = 8000

        for i in range(total):
            for j in range(i + 1, total):
                processed += 1
                id_a = books[i].text_id
                id_b = books[j].text_id

                sim = self.cosine(vectors[id_a], vectors[id_b])

                if sim >= threshold:
                    edges_buf.append(
                        DocumentGraph(
                            doc1_id=id_a,
                            doc2_id=id_b,
                            similarity=sim,
                        )
                    )
                    if verbose:
                        self.stdout.write(f"Edge: {id_a} <-> {id_b}, sim={sim:.4f}")

                if len(edges_buf) >= batch:
                    DocumentGraph.objects.bulk_create(edges_buf, batch_size=batch)
                    edges_buf.clear()

                if not verbose and pairs_total and processed % report_every == 0:
                    pct = 100.0 * processed / pairs_total
                    self.stdout.write(f"... pairs {processed}/{pairs_total} ({pct:.0f}%)")

        if edges_buf:
            DocumentGraph.objects.bulk_create(edges_buf, batch_size=batch)

        edge_count = DocumentGraph.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"Document graph G_d built: {edge_count} edges (threshold={threshold})."),
        )
