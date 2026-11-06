"""Re-run a deterministic random sample and report differences honestly."""
import argparse
import csv
import random
from pathlib import Path

from sortinglab.benchmark import isolated, summarize, write_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path("results/final"))
    args = parser.parse_args()
    rows = list(csv.DictReader((args.results / "summary.csv").open()))
    eligible = [r for r in rows if r["status"] == "ok" and r["experiment"] == "E1E2"]
    sample = random.Random(2026).sample(eligible, min(6, len(eligible)))
    output = []
    for r in sample:
        new = summarize(isolated((r["algorithm"], r["distribution"], int(r["n"]),
                                  int(r["seed"]), 9, "recheck", False)))[0]
        old_ms = float(r["median_ms"])
        new_ms = new.get("median_ms")
        delta = 100 * abs(new_ms - old_ms) / old_ms if new_ms else None
        output.append(dict(algorithm=r["algorithm"], distribution=r["distribution"],
                           n=r["n"], seed=r["seed"], original_ms=old_ms, new_ms=new_ms,
                           difference_pct=delta,
                           status="pass" if delta is not None and delta < 10 else "fail"))
    write_csv(args.results / "reproducibility.csv", output, list(output[0]))
    print(output)


if __name__ == "__main__":
    main()
