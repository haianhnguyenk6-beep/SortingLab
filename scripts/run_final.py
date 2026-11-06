"""One-command CSV benchmark + offline dashboard; no Kaggle account required for local files."""
import argparse
from pathlib import Path
from sortinglab.real_data_plus import run_csv,numeric_columns
from scripts.build_dashboard import build

def main():
    p=argparse.ArgumentParser();p.add_argument("--csv",required=True,type=Path);p.add_argument("--column",default="sales");p.add_argument("--limit",type=int,default=1000);p.add_argument("--repeats",type=int,default=3);a=p.parse_args()
    if not a.csv.is_file():p.error("CSV does not exist")
    if a.column not in numeric_columns(a.csv):p.error("Numeric column not found. Available: "+str(numeric_columns(a.csv)))
    root=Path(__file__).resolve().parents[1];out=root/"results"/"powerbi"/"final_benchmark.csv"
    rows=run_csv(a.csv,a.column,out,limit=a.limit,repeats=a.repeats)
    page=build(out,out.with_name("FINAL_DASHBOARD.html"))
    print("Benchmark:",out,"\nDashboard:",page,"\nResults:",[(r["algorithm"],r["status"]) for r in rows])
if __name__=="__main__":main()
