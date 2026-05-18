from django.db import models

# 1. Informations de base sur les livres
class Book(models.Model):
    text_id = models.IntegerField(primary_key=True)
    title = models.TextField(blank=True, default="")
    authors = models.TextField(blank=True, default="")
    local_path = models.TextField(blank=True, default="")
    doc_len_tokens = models.IntegerField(default=0)
    # Optional HTTPS cover (e.g. Open Library); filled via sync_curated_cover_urls or manually.
    cover_image_url = models.TextField(blank=True, default="")

    class Meta:
        db_table = "books"


# 2. Table des termes (unique)
class Term(models.Model):
    term = models.TextField(unique=True)
    df = models.IntegerField(default=0)

    class Meta:
        db_table = "terms"
        indexes = [models.Index(fields=["term"])]


# 3. Postings (index inversé)
class Posting(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    tf = models.IntegerField(default=0)
    tfidf = models.FloatField(default=0.0)

    class Meta:
        db_table = "postings"
        unique_together = (("term", "book"),)


# 4. Statistiques globales (N_docs, avg_len, etc.)
class IndexStat(models.Model):
    key = models.TextField(primary_key=True)
    value = models.TextField()

    class Meta:
        db_table = "index_stats"

#crous 6 step3: G_d
class DocumentGraph(models.Model):
    doc1 = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="edges_from")
    doc2 = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="edges_to")
    similarity = models.FloatField(default=0.0)

    class Meta:
        db_table = "document_graph"
        unique_together = (("doc1", "doc2"),)

#4 algo score
class DocumentScore(models.Model):
    book = models.OneToOneField(Book, on_delete=models.CASCADE)
    popularity = models.FloatField(default=0.0)   # degree centrality
    closeness = models.FloatField(default=0.0)
    betweenness = models.FloatField(default=0.0)
    pagerank = models.FloatField(default=0.0)
    total = models.FloatField(default=0.0)

    class Meta:
        db_table = "document_scores"


