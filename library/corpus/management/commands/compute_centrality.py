from django.core.management.base import BaseCommand
from corpus.models import DocumentGraph, DocumentScore
import networkx as nx


class Command(BaseCommand):
    help = "Compute centrality (popularity, closeness, betweenness, pagerank) and total score."

    def handle(self, *args, **kwargs):

        self.stdout.write(self.style.SUCCESS("Loading G_d graph..."))

        G = nx.Graph()

        #  loading graphe
        for edge in DocumentGraph.objects.all():
            G.add_edge(edge.doc1_id, edge.doc2_id, weight=edge.similarity)

        self.stdout.write(
            self.style.SUCCESS(
                f"Graph loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
            )
        )

        #  centrality 4 algo
        self.stdout.write(self.style.SUCCESS("Calculating centrality..."))

        popularity = nx.degree_centrality(G)
        self.stdout.write("degree done!")
        closeness = nx.closeness_centrality(G)
        self.stdout.write("closeness done!")
        betweenness = nx.betweenness_centrality(G, normalized=True, weight="weight")
        self.stdout.write("betweenness done!")
        pagerank = nx.pagerank(G, weight="weight")
        self.stdout.write("pagerank done!")

        # normalization 0 a 1
        def normalize(values_dict):
            vals = list(values_dict.values())
            mn, mx = min(vals), max(vals)
            if mx == mn:
                return {k: 0 for k in values_dict}
            return {k: (v - mn) / (mx - mn) for k, v in values_dict.items()}

        pop_n = normalize(popularity)
        clo_n = normalize(closeness)
        bet_n = normalize(betweenness)
        pr_n  = normalize(pagerank)

        # 4. total（0,1popularity+0.2closense+0.2betweenness+0.5pagerank)
        total = {
            k: 0.1 * pop_n[k] +
               0.2 * clo_n[k] +
               0.2 * bet_n[k] +
               0.5 * pr_n[k]
            for k in pr_n.keys()
        }

        # DB — bulk insert (much faster than per-row create on large graphs)
        self.stdout.write(self.style.SUCCESS("Saving DocumentScore..."))
        DocumentScore.objects.all().delete()

        batch_size = 500
        buf: list[DocumentScore] = []
        for doc_id in G.nodes():
            buf.append(
                DocumentScore(
                    book_id=doc_id,
                    popularity=popularity.get(doc_id, 0.0),
                    closeness=closeness.get(doc_id, 0.0),
                    betweenness=betweenness.get(doc_id, 0.0),
                    pagerank=pagerank.get(doc_id, 0.0),
                    total=total.get(doc_id, 0.0),
                )
            )
            if len(buf) >= batch_size:
                DocumentScore.objects.bulk_create(buf, batch_size=batch_size)
                buf = []
        if buf:
            DocumentScore.objects.bulk_create(buf, batch_size=batch_size)

        self.stdout.write(self.style.SUCCESS("Centrality + Total computed!"))
