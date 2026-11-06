# SortingLab — Power BI report setup

## Source and reproducibility
- Run `MO_DEMO_POWERBI.bat` on Windows, or `python -m scripts.prepare_powerbi_demo` in the project folder.
- This creates **synthetic demonstration data**, not Kaggle data. The output is `results/powerbi/sorting_benchmark.csv`.
- For actual Kaggle datasets, download a CSV subject to its license and run `python -m sortinglab.real_data --csv "data/kaggle/YOUR_FILE.csv" --column Sales --out results/powerbi/kaggle_benchmark.csv`.

## Power BI Desktop steps
1. Get Data > Text/CSV > select `results/powerbi/sorting_benchmark.csv` > Load.
2. In Power Query set `algorithm`, `dataset`, `column`, `status` to Text, `n` to Whole Number, `median_ms` and `peak_kb` to Decimal Number.
3. Add page title **SortingLab | Sorting Algorithm Benchmark**.
4. Add clustered bar chart: Y-axis `algorithm`, X-axis `median_ms`; filter `status = ok`.
5. Add another clustered bar chart: Y-axis `algorithm`, X-axis `peak_kb`; filter `status = ok`.
6. Add cards: distinct count of `algorithm`; max of `n`.
7. Add slicers for `dataset`, `column`, and `status`. If combining several CSV runs, append the files in Power Query rather than joining by algorithm alone.
8. Save as `SortingLab_Dashboard.pbix` from Power BI Desktop.

## Interpretation
- `median_ms` is median wall-clock runtime on the machine running the benchmark.
- `peak_kb` is peak Python allocation observed by the measurement utility; it is not whole-process RSS.
- Benchmarks depend on machine, software, sample size and dataset. Compare only like-for-like runs.
- A `.pbix` file requires Power BI Desktop and is not included in this package.
