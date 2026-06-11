import argparse
import json
import random
import matplotlib.pyplot as plt


def load(path):
    with open(path) as f:
        return json.load(f)


def all_pairings(graph):
    """Return list of (source, target) that have at least one timestep."""
    pairs = []
    for src, targets in graph.items():
        for tgt, series in targets.items():
            if series:
                pairs.append((src, tgt))
    return pairs


def plot_pairing(graph, src, tgt):
    """series is a list of {label: score} dicts, one per timestep."""
    series = graph[src][tgt]

    # Collect every label that appears (POSITIVE/NEGATIVE/NEUTRAL or whatever your model emits)
    labels = sorted({label for entry in series for label in entry})
    timesteps = list(range(len(series)))

    plt.figure(figsize=(11, 5))
    for label in labels:
        # score is 0 if that label is absent at a given timestep
        ys = [entry.get(label, 0.0) for entry in series]
        plt.plot(timesteps, ys, marker="o", markersize=3, label=label)

    plt.title(f"Opinion of {src} -> {tgt} over time")
    plt.xlabel("Interaction timestep")
    plt.ylabel("Sentiment score")
    plt.ylim(-0.05, 1.05)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    out = f"opinion_{src}_to_{tgt}.png"
    plt.savefig(out, dpi=130)
    print(f"saved {out}  ({len(series)} timesteps, labels: {labels})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="opinion_graph.json")
    parser.add_argument(
        "--pairing",
        help='Choose a pairing as "source,target" instead of picking one at random.',
    )
    args = parser.parse_args()

    graph = load(args.path)

    pairs = all_pairings(graph)
    if not pairs:
        sys.exit("no pairings with data found")

    if args.pairing:
        src, tgt = args.pairing.split(",", 1)
    else:
        src, tgt = random.choice(pairs)
        print(f"random pairing: {src} -> {tgt}")

    plot_pairing(graph, src, tgt)