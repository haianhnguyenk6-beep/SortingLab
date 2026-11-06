"""Command-line interface for demos, experiments and chart reproduction."""
import argparse
import json
from pathlib import Path

from .algorithms import ALGORITHMS
from .benchmark import isolated, run_matrix, summarize, write_csv
from .data_generator import DISTRIBUTIONS, MAX_N, generate


def size(value: str) -> int:
    """Argparse bounded nonnegative size."""
    n = int(value)
    if not 0 <= n <= MAX_N:
        raise argparse.ArgumentTypeError(f"n must be in [0, {MAX_N}]")
    return n


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return an exit status."""
    parser = argparse.ArgumentParser(description="SortingLab: sorting experiments")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Sort and compare identical input")
    demo.add_argument("--algorithm", choices=[*ALGORITHMS, "all"], default="all")
    demo.add_argument("--distribution", choices=DISTRIBUTIONS, default="random")
    demo.add_argument("--n", type=size, default=1000)
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--csv", type=Path)
    bench = sub.add_parser("run", help="Reproduce E1-E4 and charts")
    bench.add_argument("--profile", choices=["smoke", "pilot", "full"], default="full")
    bench.add_argument("--out", type=Path, default=Path("results/reproduced"))
    bench.add_argument("--repeats", type=int, default=7)
    bench.add_argument("--seed", type=int, default=42)
    plot = sub.add_parser("plots", help="Regenerate figures from existing CSV")
    plot.add_argument("--results", type=Path, default=Path("results/final"))
    args = parser.parse_args(argv)
    if args.command == "demo":
        names = list(ALGORITHMS) if args.algorithm == "all" else [args.algorithm]
        rows = []
        for name in names:
            rows.extend(isolated((name, args.distribution, args.n,
                                  args.seed, 5, "demo", True)))
        ranked = sorted(summarize(rows), key=lambda r: r.get("median_ms", float("inf")))
        print(f"Input: n={args.n}, distribution={args.distribution}, seed={args.seed}")
        print("algorithm       median_ms  comparisons        moves    peak_KiB status")
        for r in ranked:
            print(f"{r['algorithm']:14} {r.get('median_ms', 0):10.5f} "
                  f"{str(r.get('comparisons', '-')):>12} "
                  f"{str(r.get('moves', 'N/A')):>12} "
                  f"{r.get('peak_kb', 0):11.2f} {r['status']} {r.get('reason', '')}")
        data = generate(args.n, args.distribution, args.seed)
        ok_names = [r['algorithm'] for r in ranked if r['status'] == 'ok']
        if ok_names:
            # Show real selected-algorithm output, outside all measurements.
            output = ALGORITHMS[ok_names[0]](data)
            print("Sorted sample:", output[:10], "...", output[-10:])
        if args.csv:
            write_csv(args.csv, rows)
        return 0 if ok_names else 1
    if args.command == "run":
        if args.repeats < 2:
            parser.error("--repeats must be >= 2")
        sizes = {"smoke": [32, 64], "pilot": [1000, 2000, 4000],
                 "full": [1000, 2000, 4000, 8000, 16000, 32000]}[args.profile]
        run_matrix(args.out, sizes, args.repeats, args.seed,
                   small=args.profile != "smoke")
        results = args.out
    else:
        results = args.results
    from .plots import make_plots
    make_plots(results)
    print(json.dumps({"results": str(results), "status": "complete"}))
    return 0
