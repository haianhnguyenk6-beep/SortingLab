"""Offline acceptance preflight; never marks unexecuted external checks as passed."""
import csv, importlib.util, json, platform, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DATASETS = {
 'Superstore': ('data/kaggle/superstore', ['SampleSuperstore.csv','Superstore.csv'], ['Sales']),
 'Olist': ('data/kaggle/olist', ['olist_order_items_dataset.csv'], ['price']),
 'Credit Card': ('data/kaggle/creditcard', ['creditcard.csv'], ['Amount']),
}
def locate(folder, names):
 p=ROOT/folder
 if not p.exists(): return None
 for name in names:
  matches=list(p.rglob(name))
  if matches: return matches[0]
 return None
def check_csv(path, columns):
 with path.open(encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f)
  header=reader.fieldnames or []
  matches=[c for c in columns if c in header]
  if not matches: return {'status':'FAIL','reason':f'Missing columns {columns}; found {header[:20]}'}
  col=matches[0]; total=valid=0
  for row in reader:
   total+=1
   try:
    val=float((row.get(col) or '').replace(',',''))
    import math
    valid+=math.isfinite(val)
   except (ValueError,TypeError): pass
 return {'status':'PASS' if valid else 'FAIL','rows':total,'valid_numeric':valid,'column':col}
def main():
 rows=[]
 for label,(folder,names,cols) in DATASETS.items():
  p=locate(folder,names)
  result=check_csv(p,cols) if p else {'status':'BLOCKED','reason':'Original Kaggle CSV not found'}
  rows.append({'area':'Kaggle','check':label,'path':str(p.relative_to(ROOT)) if p else '',**result})
 for dep in ['pytest','hypothesis']:
  rows.append({'area':'Environment','check':dep,'status':'PASS' if importlib.util.find_spec(dep) else 'BLOCKED','reason':'' if importlib.util.find_spec(dep) else 'Dependency not installed'})
 cmd=[sys.executable,'-m','pytest','-q','tests']
 if importlib.util.find_spec('pytest') and importlib.util.find_spec('hypothesis'):
  try:
   run=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=180)
   (ROOT/'evidence'/'v22_pytest.txt').write_text(run.stdout+'\n'+run.stderr,encoding='utf-8')
   rows.append({'area':'Automated tests','check':'pytest full suite','status':'PASS' if run.returncode==0 else 'FAIL','reason':run.stdout[-400:]})
  except subprocess.TimeoutExpired: rows.append({'area':'Automated tests','check':'pytest full suite','status':'BLOCKED','reason':'Exceeded 180-second timeout'})
 else: rows.append({'area':'Automated tests','check':'pytest full suite','status':'BLOCKED','reason':'Install pytest and hypothesis'})
 rows += [
  {'area':'Windows','check':'GUI and launcher on Windows','status':'NOT TESTED','reason':'Requires actual Windows execution'},
  {'area':'Power BI','check':'Native PBIX report','status':'NOT TESTED','reason':'Requires Power BI Desktop and native PBIX save'},
 ]
 out=ROOT/'evidence';out.mkdir(exist_ok=True)
 with (out/'v22_acceptance.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['area','check','status','path','rows','valid_numeric','column','reason'],extrasaction='ignore');w.writeheader();w.writerows(rows)
 (out/'v22_acceptance.json').write_text(json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),'checks':rows},indent=2,ensure_ascii=False),encoding='utf-8')
 for row in rows: print(f"{row['status']:10} {row['area']}: {row['check']}")
 print('Evidence: evidence/v22_acceptance.csv and .json')
if __name__=='__main__':main()
