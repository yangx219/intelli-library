import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "centrality.csv"

OUT_DIR = BASE_DIR / "graph"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Load CSV

print("Loading centrality.csv ...")
df = pd.read_csv(CSV_FILE)

required_cols = [
    "popularity", "closeness", "betweenness", "pagerank", "total"
]

for col in required_cols:
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found in CSV.")

print(f"Loaded {len(df)} rows.")

# Helper: Plot histogram

def plot_hist(column, title, filename, bins=50):
    plt.figure(figsize=(7, 5))
    plt.hist(df[column], bins=bins, edgecolor='black')
    plt.title(title)
    plt.xlabel(column)
    plt.ylabel("Frequency")
    plt.grid(alpha=0.3)

    out_path = OUT_DIR / filename
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved: {out_path}")


# Plot each centrality measure

plot_hist("popularity",
          "Distribution of Degree Centrality (Popularity)",
          "popularity_hist.png")

plot_hist("closeness",
          "Distribution of Closeness Centrality",
          "closeness_hist.png")

plot_hist("betweenness",
          "Distribution of Betweenness Centrality",
          "betweenness_hist.png")

plot_hist("pagerank",
          "Distribution of PageRank",
          "pagerank_hist.png")

plot_hist("total",
          "Distribution of Total Centrality Score",
          "total_hist.png")

print("All centrality histograms generated.")
