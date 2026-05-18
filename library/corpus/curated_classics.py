"""
Curated Project Gutenberg titles shown on the homepage classics shelf.

Single source of truth for API + optional corpus ingestion (`ingest_curated_classics`).
Keep IDs aligned with `frontend/src/classicBooksFallback.ts` for offline SPA fallback.
"""

from __future__ import annotations

# Each row: (gutenberg_text_id, display_title, list of author names for UI / OL hints).
CURATED_CLASSICS: list[tuple[int, str, list[str]]] = [
    (1342, "Pride and Prejudice", ["Jane Austen"]),
    (1260, "Jane Eyre", ["Charlotte Brontë"]),
    (98, "A Tale of Two Cities", ["Charles Dickens"]),
    (1400, "Great Expectations", ["Charles Dickens"]),
    (766, "David Copperfield", ["Charles Dickens"]),
    (2701, "Moby Dick", ["Herman Melville"]),
    (1661, "The Adventures of Sherlock Holmes", ["Arthur Conan Doyle"]),
    (84, "Frankenstein", ["Mary Wollstonecraft Shelley"]),
    (345, "Dracula", ["Bram Stoker"]),
    (768, "Wuthering Heights", ["Emily Brontë"]),
    (158, "Emma", ["Jane Austen"]),
    (161, "Sense and Sensibility", ["Jane Austen"]),
    (174, "The Picture of Dorian Gray", ["Oscar Wilde"]),
    (120, "Treasure Island", ["Robert Louis Stevenson"]),
    (11, "Alice's Adventures in Wonderland", ["Lewis Carroll"]),
    (74, "The Adventures of Tom Sawyer", ["Mark Twain"]),
    (33, "The Scarlet Letter", ["Nathaniel Hawthorne"]),
    (2600, "War and Peace", ["Leo Tolstoy"]),
    (1399, "Anna Karenina", ["Leo Tolstoy"]),
    (996, "Don Quixote", ["Miguel de Cervantes"]),
    (1184, "The Count of Monte Cristo", ["Alexandre Dumas"]),
    (1513, "Romeo and Juliet", ["William Shakespeare"]),
    (2591, "Grimms' Fairy Tales", ["Jacob Grimm", "Wilhelm Grimm"]),
    (730, "Oliver Twist", ["Charles Dickens"]),
]

SAMPLE_FALLBACK = CURATED_CLASSICS[:10]
