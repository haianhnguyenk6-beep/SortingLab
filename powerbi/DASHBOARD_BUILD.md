# Power BI Desktop dashboard – Sorting Lab

**Data origin:** Kaggle Store Item Demand Forecasting Challenge (`train.csv`, numeric `sales`). Competition rules may require Kaggle sign-in/acceptance. Never present synthetic CSV as Kaggle data.

1. Download `train.csv` from https://www.kaggle.com/competitions/demand-forecasting-kernels-only/data or run `python -m pip install kaggle` and `python -m scripts.kaggle_pipeline --download` after configuring your own Kaggle credentials.
2. Run `python -m scripts.kaggle_pipeline --csv data/kaggle/store_item_demand/train.csv --column sales --limit 1000 --repeats 3`.
3. In Power BI Desktop: **Get data > Text/CSV** and choose `results/powerbi/kaggle_benchmark.csv`. Name table **SortingBenchmark**. Confirm numeric data types. Alternatively use `PowerQuery_SortingBenchmark.m` and change the file path.
4. Add DAX measures from `DAX_Measures.txt` (Modeling > New measure).
5. Create 4 KPI cards: Successful Runs, Median Runtime (ms), Average Peak Memory (KB), Success Rate.
6. Clustered bar: Y-axis `algorithm`, X-axis `median_ms`, filter `status = ok`, ascending runtime. Clustered column: X-axis `algorithm`, Y-axis `peak_kb`.
7. Scatter: X `median_ms`, Y `peak_kb`, Details `algorithm`, Size `n`. Add slicers for `dataset`, `column`, `n`, `run_id`.
8. Table: `algorithm`, `n`, `repeats`, `min_ms`, `median_ms`, `max_ms`, `peak_kb`, `status`, `reason`. Refresh after new CSV runs.

**Limitations:** `.pbix` must be saved from Power BI Desktop on Windows; this repository provides a complete data pipeline, DAX, Power Query and an offline interactive dashboard, not a prebuilt `.pbix`. Benchmark time depends on machine, input and number of repeats; memory numbers reflect Python measurement method.
