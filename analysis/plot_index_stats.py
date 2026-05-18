import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CSV_BOOK = BASE_DIR / "index_book_stats.csv"
CSV_VOCAB = BASE_DIR / "vocab_stats.csv"

OUT_DIR = BASE_DIR / "graph"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Chargement des données
book_df = pd.read_csv(CSV_BOOK)
vocab_df = pd.read_csv(CSV_VOCAB)


# Figure 1 : histogramme de la longueur des documents (token_count)
plt.figure(figsize=(8, 5))
plt.hist(book_df["token_count"], bins=50, edgecolor='black')
plt.title("Distribution des longueurs de documents (token_count)")
plt.xlabel("Nombre de tokens")
plt.ylabel("Fréquence")
plt.grid(alpha=0.3)

out1 = OUT_DIR / "token_count_hist.png"
plt.savefig(out1, dpi=300)
plt.close()
print(f"Figure 1 générée : {out1}")


# Figure 2 : histogramme de la distribution DF

plt.figure(figsize=(8, 5))
plt.hist(vocab_df["df"], bins=50, edgecolor='black')
plt.title("Distribution de DF (Document Frequency)")
plt.xlabel("DF (nombre de documents contenant le terme)")
plt.ylabel("Fréquence")
plt.grid(alpha=0.3)

out2 = OUT_DIR / "df_hist.png"
plt.savefig(out2, dpi=300)
plt.close()
print(f"Figure 2 générée : {out2}")


# Figure 3 : histogramme de la sparsité TF-IDF (sparsity_percent)

plt.figure(figsize=(8, 5))
plt.hist(book_df["sparsity_percent"], bins=50, edgecolor='black')
plt.title("Distribution de la sparsité TF–IDF (%)")
plt.xlabel("Sparsité (%)")
plt.ylabel("Fréquence")
plt.grid(alpha=0.3)

out3 = OUT_DIR / "sparsity_hist.png"
plt.savefig(out3, dpi=300)
plt.close()
print(f"Figure 3 générée : {out3}")


print("\nTous les graphiques ont été générés !")
