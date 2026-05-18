# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.db import transaction
from corpus.models import Book, Term, Posting, IndexStat
from pathlib import Path
import csv, re, time
from collections import defaultdict

START_RE   = re.compile(r'\*{3}\s*START OF .*?PROJECT GUTENBERG EBOOK.*?\*{3}', re.I)
END_RE     = re.compile(r'\*{3}\s*END OF .*?PROJECT GUTENBERG EBOOK.*?\*{3}', re.I)
LICENSE_RE = re.compile(r'START:\s*FULL\s*LICENSE', re.I)
WORD_RE    = re.compile(r"[A-Za-z0-9']+")

def split_front_body(text: str):
    """Renvoie le corps nettoyé (licence retirée et marqueurs END supprimés)."""
    lic = LICENSE_RE.search(text)
    cut = text[:lic.start()] if lic else text
    sm = START_RE.search(cut)
    if sm:
        body_all = cut[sm.end():]
    else:
        body_all = cut
    em = END_RE.search(body_all)
    body = body_all[:em.start()] if em else body_all
    return body.strip()

def tokenize(s: str):
    """Tokenisation anglaise avec léger filtrage (stopwords, mots trop courts, etc.)"""
    STOPWORDS = {
        'a','an','and','are','as','at','be','but','by','for','if','in','into','is','it',
        'no','not','of','on','or','such','that','the','their','then','there','these',
        'they','this','to','was','will','with','so','than','too','very','can','from'
    }

    toks = [t.lower() for t in WORD_RE.findall(s)]
    out = []
    for t in toks:
        if len(t) < 2:   # Ignorer les tokens d'un seul caractère
            continue
        if t in STOPWORDS:
            continue
        if t.isdigit(): 
            continue
        out.append(t)
    return out

        
class Command(BaseCommand):
    help = "Nettoyer les livres et construire l'index inversé (sans conserver les fichiers front/body)"

    def add_arguments(self, parser):
        parser.add_argument("--meta", default="../data/selected_meta.csv",
                            help="Chemin du fichier CSV des métadonnées")
        parser.add_argument("--dir", default="../books_html_kept",
                            help="Répertoire des textes bruts des livres")
        parser.add_argument("--limit", type=int, default=0,
                            help="Importer uniquement les N premiers livres pour test (0 = totalité)")

    def handle(self, *args, **opts):
        meta_csv = Path(opts["meta"]).resolve()
        book_dir = Path(opts["dir"]).resolve()
        assert meta_csv.exists(), f"CSV introuvable : {meta_csv}"
        assert book_dir.exists(), f"Répertoire introuvable : {book_dir}"

        with meta_csv.open(newline="", encoding="utf-8", errors="ignore") as f:
            rows = list(csv.DictReader(f))
        if opts["limit"] > 0:
            rows = rows[:opts["limit"]]

        term_cache = {}
        term_doc_seen = defaultdict(set)
        total_docs, total_len = 0, 0

        with transaction.atomic():
            for i, row in enumerate(rows, 1):
                tid = (row.get("Text#") or "").strip()
                if not tid.isdigit():
                    continue
                doc_id = int(tid)
                p = book_dir / f"{doc_id}.txt"
                if not p.exists():
                    continue

                raw = p.read_text(encoding="utf-8", errors="ignore")
                body = split_front_body(raw)
                toks = tokenize(body)
                if not toks:
                    continue

                Book.objects.update_or_create(
                    text_id=doc_id,
                    defaults=dict(
                        title=row.get("Title",""),
                        authors=row.get("Authors",""),
                        local_path=str(p),
                        doc_len_tokens=len(toks),
                    ),
                )

                total_docs += 1
                total_len += len(toks)

                # Calculer les tf
                tf = defaultdict(int)
                for t in toks:
                    tf[t] += 1

                # Écrire terms/postings
                for t, tfv in tf.items():
                    if t not in term_cache:
                        obj, _ = Term.objects.get_or_create(term=t, defaults={"df": 0})
                        term_cache[t] = obj.id
                    term_doc_seen[t].add(doc_id)
                    Posting.objects.update_or_create(
                        term_id=term_cache[t],
                        book_id=doc_id,
                        defaults={"tf": tfv},
                    )

                if i % 100 == 0:
                    self.stdout.write(self.style.SUCCESS(f"Indexed {i} rows..."))

            # Mettre à jour df
            for t, docs in term_doc_seen.items():
                Term.objects.filter(term=t).update(df=len(docs))

            # Statistiques globales
            avg_len = total_len / total_docs if total_docs else 0
            IndexStat.objects.update_or_create(key="N_docs",
                                               defaults={"value": str(total_docs)})
            IndexStat.objects.update_or_create(key="avg_doc_len",
                                               defaults={"value": f"{avg_len:.6f}"})
            IndexStat.objects.update_or_create(key="built_at",
                                               defaults={"value": time.strftime('%Y-%m-%d %H:%M:%S')})
            IndexStat.objects.update_or_create(key="tokenizer_version",
                                               defaults={"value": "plain-lower-words-v1"})

        self.stdout.write(self.style.SUCCESS(
            f"Import terminé : N_docs={total_docs}, avg_doc_len={avg_len:.2f}"
        ))
