"""Generate report figures and empirical growth tables from measured CSV."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .algorithms import ALGORITHMS  # noqa: E402
from .benchmark import write_csv  # noqa: E402
from .data_generator import DISTRIBUTIONS, generate  # noqa: E402

COLORS = dict(zip(ALGORITHMS, ["#d1495b", "#00798c", "#e0a100", "#30638e", "#794c9e", "#238543"]))


def make_plots(results: Path) -> None:
    """Create 20+ figures plus growth/distribution tables, preserving skips."""
    rows = list(csv.DictReader((results / "summary.csv").open(encoding="utf-8")))
    good = [r for r in rows if r["status"] == "ok"]
    main = [r for r in good if r["experiment"] == "E1E2"]
    folder = results / "figures"
    folder.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.dpi": 140})

    def save(name: str) -> None:
        plt.tight_layout()
        plt.savefig(folder / f"{name}.png", dpi=180)
        plt.savefig(folder / f"{name}.svg")
        plt.close()

    for dist in DISTRIBUTIONS:
        for log in (False, True):
            plt.figure(figsize=(7.4, 4.2))
            for name in ALGORITHMS:
                rr = sorted([r for r in main if r["distribution"] == dist
                             and r["algorithm"] == name], key=lambda r: int(r["n"]))
                plt.plot([int(r["n"]) for r in rr], [float(r["median_ms"]) for r in rr],
                         "o-", label=name, color=COLORS[name], markersize=3)
            if log:
                plt.xscale("log", base=2)
                plt.yscale("log")
            plt.xlabel("Input size n")
            plt.ylabel("Median runtime (ms / call)")
            plt.title(f"E1 / E2: {dist}" + (" (log-log)" if log else ""))
            plt.legend(fontsize=8, ncol=2)
            plt.grid(alpha=0.2)
            save(f"time_{dist}_{'log' if log else 'linear'}")
    common_n = min(4000, max(int(r["n"]) for r in main))
    matrix = np.full((len(ALGORITHMS), len(DISTRIBUTIONS)), np.nan)
    for i, name in enumerate(ALGORITHMS):
        for j, dist in enumerate(DISTRIBUTIONS):
            rr = [r for r in main if r["algorithm"] == name and r["distribution"] == dist
                  and int(r["n"]) == common_n]
            if rr:
                matrix[i, j] = float(rr[0]["median_ms"])
    plt.figure(figsize=(8, 4.6))
    plt.imshow(np.log10(matrix), aspect="auto", cmap="YlOrRd")
    plt.xticks(range(5), DISTRIBUTIONS)
    plt.yticks(range(6), ALGORITHMS)
    for (i, j), value in np.ndenumerate(matrix):
        plt.text(j, i, f"{value:.3f}", ha="center", va="center", fontsize=9)
    plt.colorbar(label="log10 runtime (ms)")
    plt.title(f"E2: runtime by distribution, n = {common_n} (labels in ms)")
    save("distribution_heatmap")
    for metric, title, unit in [("comparisons", "E3 comparisons", "Key comparisons"),
                                ("moves", "E3 array writes", "Array writes"),
                                ("peak_kb", "E4 peak allocation", "Peak traced memory (KiB)")]:
        plt.figure(figsize=(7.4, 4.2))
        for name in ALGORITHMS:
            rr = sorted([r for r in main if r["algorithm"] == name
                         and r["distribution"] == "random" and r.get(metric)],
                        key=lambda r: int(r["n"]))
            if rr:
                plt.loglog([int(r["n"]) for r in rr], [float(r[metric]) for r in rr],
                           "o-", label=name, color=COLORS[name], markersize=3)
        plt.xlabel("Input size n")
        plt.ylabel(unit)
        plt.title(title + " on random input")
        plt.legend(fontsize=8, ncol=2)
        plt.grid(alpha=0.2)
        save(metric)
    plt.figure(figsize=(7.4, 4.2))
    rr = sorted([r for r in main if r["algorithm"] == "insertion"
                 and r["distribution"] == "reversed"], key=lambda r: int(r["n"]))
    ns = [int(r["n"]) for r in rr]
    plt.plot(ns, [n * (n - 1) // 2 for n in ns], label="n(n-1)/2", linewidth=3)
    plt.scatter(ns, [float(r["comparisons"]) for r in rr], label="measured", color="#d1495b")
    plt.title("E3: reversed insertion sort, exact comparison count")
    plt.xlabel("Input size n")
    plt.ylabel("Key comparisons")
    plt.legend()
    save("theory_counts")
    plt.figure(figsize=(7.4, 4.2))
    for name in ALGORITHMS:
        rr = sorted([r for r in good if r["experiment"] == "small" and r["algorithm"] == name],
                    key=lambda r: int(r["n"]))
        if rr:
            plt.plot([int(r["n"]) for r in rr], [1000 * float(r["median_ms"]) for r in rr],
                     "o-", label=name, color=COLORS[name], markersize=3)
    plt.title("Small-n crossover on fixed-seed random input")
    plt.xlabel("Input size n")
    plt.ylabel("Median runtime (microseconds / call)")
    plt.legend(fontsize=8, ncol=2)
    save("small_crossover")
    growth = []
    for name in ALGORITHMS:
        rr = sorted([r for r in main if r["algorithm"] == name and r["distribution"] == "random"],
                    key=lambda r: int(r["n"]))
        if len(rr) < 2:
            continue
        x = np.log([int(r["n"]) for r in rr])
        y = np.log([float(r["median_ms"]) for r in rr])
        slope = float(np.polyfit(x, y, 1)[0])
        for first, second in zip(rr, rr[1:]):
            growth.append(dict(algorithm=name, n1=first["n"], n2=second["n"],
                               doubling_ratio=(float(second["median_ms"]) /
                                               float(first["median_ms"])),
                               loglog_slope=slope))
    if growth:
        write_csv(results / "growth.csv", growth, list(growth[0]))
    analysis = []
    for i, name in enumerate(ALGORITHMS):
        values = matrix[i]
        if np.isfinite(values).all():
            analysis.append(dict(algorithm=name, n=common_n,
                                 fastest=DISTRIBUTIONS[int(np.argmin(values))],
                                 slowest=DISTRIBUTIONS[int(np.argmax(values))],
                                 max_min_ratio=float(np.max(values) / np.min(values))))
    if analysis:
        write_csv(results / "distribution.csv", analysis, list(analysis[0]))
    for dist in DISTRIBUTIONS:
        data = generate(200, dist, 42)
        plt.figure(figsize=(7.4, 3))
        plt.scatter(range(200), data, s=9, color="#30638e")
        plt.title(f"Generator sample: {dist}, n=200, seed=42")
        plt.xlabel("Index")
        plt.ylabel("Value")
        save(f"sample_{dist}")
    plt.figure(figsize=(7.4, 3.5))
    cv = [float(r["cv_pct"]) for r in good]
    plt.hist(cv, bins=25, color="#30638e")
    plt.axvline(10, color="#d1495b", linestyle="--", label="Plan threshold 10%")
    plt.xlabel("Coefficient of variation (%)")
    plt.ylabel("Configuration count")
    plt.title("Timing variability across batch observations")
    plt.legend()
    save("cv_distribution")
