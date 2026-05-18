from django.core.management.base import BaseCommand
from corpus.models import DocumentGraph
import csv
from pathlib import Path


class Command(BaseCommand):
    help = "Export document similarity (DocumentGraph) into a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default="similarity.csv",
            help="Output CSV file path (default: similarity.csv)"
        )

    def handle(self, *args, **opts):

        out_path = Path(opts["out"])
        self.stdout.write(f"Exporting DocumentGraph to {out_path} ...")

        edges = DocumentGraph.objects.all()
        total = edges.count()

        if total == 0:
            self.stdout.write("Warning: DocumentGraph table is empty. Nothing to export.")
            return

        with out_path.open("w", newline="", encoding="utf8") as f:
            writer = csv.writer(f)
            writer.writerow(["doc1", "doc2", "similarity"])

            for edge in edges:
                writer.writerow([edge.doc1_id, edge.doc2_id, edge.similarity])

        self.stdout.write(f"Done. Exported {total} similarity records to {out_path}.")
