"""Produce clearly labeled synthetic retail data and a reproducible Power BI export."""
import csv
import random
from pathlib import Path
from sortinglab.real_data import benchmark_csv


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / 'data' / 'demo' / 'synthetic_retail_orders.csv'
    target = root / 'results' / 'powerbi' / 'sorting_benchmark.csv'
    source.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261013)
    with source.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['OrderID', 'Sales', 'Quantity', 'Category'])
        for i in range(1, 301):
            writer.writerow([f'ORD{i:04d}', round(rng.uniform(10, 5000), 2), rng.randint(1, 15), ['Electronics', 'Office', 'Home'][i % 3]])
    results = benchmark_csv(source, 'Sales', target, limit=300, repeats=3)
    print(f'Synthetic demo input: {source}')
    print(f'Power BI CSV: {target}')
    print(f'Algorithm runs: {len(results)}')


if __name__ == '__main__':
    main()
