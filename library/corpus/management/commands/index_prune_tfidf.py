from django.core.management.base import BaseCommand
from django.db import connection
from corpus.models import Posting

class Command(BaseCommand):
    help = "Supprimer les entrées mineures selon le TF-IDF"

    def add_arguments(self, parser):
        parser.add_argument("--topk", type=int, default=2000)

    def handle(self, *args, **opts):

        k = opts["topk"]
        self.stdout.write(f"TF-IDF prune: keeping top {k} postings per book...")

        sql = f"""
            DELETE FROM postings
            WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (PARTITION BY book_id ORDER BY tfidf DESC) AS rn
                    FROM postings
                ) WHERE rn <= {k}
            );
        """

        with connection.cursor() as cursor:
            cursor.execute(sql)

        self.stdout.write("TF-IDF prune finished.")
