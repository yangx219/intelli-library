import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CSV_SIM = BASE_DIR / "similarity.csv"

OUT_DIR = BASE_DIR / "graph"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Chargement des données

print("Loading similarity data...")
sim_df = pd.read_csv(CSV_SIM)

if "similarity" not in sim_df.columns:
    raise ValueError("CSV file must contain a 'similarity' column.")

print(f"Loaded {len(sim_df)} similarity entries.")

# Tracé : distribution de la similarité cosinus

plt.figure(figsize=(8, 5))
plt.hist(sim_df["similarity"], bins=50, edgecolor='black')
plt.title("Distribution of Cosine Similarity Between Documents")
plt.xlabel("Cosine Similarity")
plt.ylabel("Frequency")
plt.grid(alpha=0.3)

out_path = OUT_DIR / "similarity_hist.png"
plt.savefig(out_path, dpi=300)
plt.close()

print(f"Similarity histogram saved to: {out_path}")
print("Done.")
