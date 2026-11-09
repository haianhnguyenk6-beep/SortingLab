"""Kaggle datasets to SortingLab benchmarks (CLI)."""
import argparse, json, subprocess, sys, zipfile, shutil
from pathlib import Path
from sortinglab.real_data_plus import run_csv, numeric_columns
from sortinglab.csv_input import is_lfs_pointer
DATASETS={
 'superstore':('xubao666/superstore','SampleSuperstore.csv','Sales'),
 'olist':('olistbr/brazilian-ecommerce','olist_order_items_dataset.csv','price'),
 'creditcard':('mlg-ulb/creditcardfraud','creditcard.csv','Amount'),
}
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--dataset',choices=DATASETS,default='superstore')
 p.add_argument('--csv',type=Path)
 p.add_argument('--download',action='store_true')
 p.add_argument('--column')
 p.add_argument('--limit',type=int,default=1000)
 p.add_argument('--repeats',type=int,default=3)
 a=p.parse_args()
 root=Path(__file__).resolve().parents[1]
 slug,filename,default_column=DATASETS[a.dataset]
 folder=root/'data'/'kaggle'/a.dataset
 source=a.csv or folder/filename
 if a.download:
  folder.mkdir(parents=True,exist_ok=True)
  subprocess.run([sys.executable,'-m','kaggle','datasets','download','-d',slug,'-p',str(folder)],check=True)
  if not source.exists() or is_lfs_pointer(source):
   for archive in folder.glob('*.zip'):
    with zipfile.ZipFile(archive) as z:
     match=next((x for x in z.infolist() if Path(x.filename).name.lower()==filename.lower()),None)
     if match:
      with z.open(match) as f,source.open('wb') as out:shutil.copyfileobj(f,out)
      break
 if not source.exists():p.error('Missing CSV: '+str(source))
 column=a.column or default_column
 if column not in numeric_columns(source):p.error('Not numeric column: '+column)
 out=root/'results'/'powerbi'/f'{a.dataset}_benchmark.csv'
 rows=run_csv(source,column,out,limit=a.limit,repeats=a.repeats)
 print('Saved',out,'Rows',len(rows))
if __name__=='__main__':main()
