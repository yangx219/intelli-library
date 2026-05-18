from django.core.management.base import BaseCommand
from corpus.models import Posting, Book

class Command(BaseCommand):
    help = "Build TF-IDF vectors for all documents (in memory only)."

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Building TF-IDF vectors..."))

        # Étape 1 : récupérer tous les livres
        all_books = Book.objects.all()
        self.stdout.write(f"Total books = {all_books.count()}")

        # Étape 2 : parcourir chaque livre
        for book in all_books:
            # Récupérer tous les couples (term_id, tfidf)
            postings = Posting.objects.filter(book=book, tfidf__gt=0)

            # Étape 3 : construire le vecteur clairsemé (term_id → tfidf)
            vector = {p.term_id: p.tfidf for p in postings}

            # Afficher un exemple
            self.stdout.write(
                f"Book {book.text_id}: vector size = {len(vector)}"
            )

        self.stdout.write(self.style.SUCCESS("TF-IDF vectors built successfully!"))
