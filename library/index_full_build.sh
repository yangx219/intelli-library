#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "Suppression de l'ancienne base d'index..."
rm -f db_index.sqlite3

echo "[1/4] Migration de la nouvelle structure de base de données..."
python manage.py migrate --settings=library.settings_index --noinput

echo "Correction/ajout de la colonne postings.tfidf (si absente)..."
sqlite3 db_index.sqlite3 "ALTER TABLE postings ADD COLUMN tfidf REAL DEFAULT 0.0;" 2>/dev/null || true

echo "[2/4] Construction de l'index inversé (TopK=7000 TF + racines) ..."
python manage.py index_build_fast \
  --settings=library.settings_index \
  --meta ../data/selected_meta.csv \
  --dir ../books_html_kept \
  --topk 7000

echo "Vérification à nouveau de l'existence de la colonne postings.tfidf..."
sqlite3 db_index.sqlite3 "ALTER TABLE postings ADD COLUMN tfidf REAL DEFAULT 0.0;" 2>/dev/null || true

echo "[3/4] Calcul du TF-IDF..."
python manage.py index_compute_tfidf --settings=library.settings_index

echo "[4/4] Élagage selon le TF-IDF (TopK=2500)..."
python manage.py index_prune_tfidf \
  --settings=library.settings_index \
  --topk 2500

#echo "Terminé ! La base d'index a été générée : db_index.sqlite3"
echo "5/7 Construction des vecteurs de documents (build_doc_vectors)"
python manage.py build_doc_vectors \
  --settings=library.settings_index

echo "6/7 Construction du graphe de documents (build_doc_graph)"
python manage.py build_doc_graph \
  --settings=library.settings_index

echo "7/7 Calcul des centralités (compute_centrality)"
python manage.py compute_centrality \
  --settings=library.settings_index

echo "Terminé ! La base d'index a été générée : db_index.sqlite3"