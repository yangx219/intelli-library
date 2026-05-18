from django.core.management.base import BaseCommand
from corpus.models import DocumentScore, Book
import csv
from pathlib import Path


class Command(BaseCommand):
    help = "Export document centrality scores to a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default="centrality.csv",
            help="Output CSV file path (default: centrality.csv)",
        )

    def handle(self, *args, **opts):

        out_path = Path(opts["out"])
        self.stdout.write(f"Exporting centrality scores to {out_path} ...")

        qs = DocumentScore.objects.select_related("book")
        total = qs.count()

        if total == 0:
            self.stdout.write("Warning: DocumentScore table is empty, nothing to export.")
            return

        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "book_id",
                "title",
                "popularity",
                "closeness",
                "betweenness",
                "pagerank",
                "total",
            ])

            for ds in qs:
                book: Book = ds.book
                writer.writerow([
                    book.text_id,
                    (book.title or "").strip(),
                    ds.popularity,
                    ds.closeness,
                    ds.betweenness,
                    ds.pagerank,
                    ds.total,
                ])

        self.stdout.write(f"Done. Exported {total} rows to {out_path}.")
