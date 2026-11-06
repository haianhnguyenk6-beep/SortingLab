"""V23 acceptance evidence: real files only; no simulated PASS results."""
import csv, hashlib, json, math, platform, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DATASETS = {
    'Superstore': ('data/kaggle/superstore', ['SampleSuperstore.csv', 'Superstore.csv'], 'Sales'),
    'Olist': ('data/kaggle/olist', ['olist_order_items_dataset.csv'], 'price'),
    'Credit Card': ('data/kaggle/creditcard', ['creditcard.csv'], 'Amount'),
}
EXPORTS = {
    'Batch benchmark': 'results/powerbi/all_datasets_benchmark.csv',
    'History': 'results/powerbi/history.csv',
    'Final benchmark': 'results/powerbi/final_benchmark.csv',
}
def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()
def csv_stats(path, column=None):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader=csv.DictReader(f)
        fields=reader.fieldnames or []
        if not fields: return {'status':'FAIL','reason':'CSV header missing'}
        if column and column not in fields: return {'status':'FAIL','reason':f'Missing numeric column: {column}'}
        rows=valid=0
        for row in reader:
            rows+=1
            if column:
                try:
                    value=float((row.get(column) or '').replace(',',''))
                    if math.isfinite(value):valid+=1
                except (ValueError,TypeError):pass
        if not rows:return {'status':'FAIL','reason':'CSV has no data rows','rows':0}
        if column and not valid:return {'status':'FAIL','reason':'No finite numeric values','rows':rows,'valid_numeric':0}
        return {'status':'PASS','rows':rows,'valid_numeric':valid if column else '', 'columns':','.join(fields)}
def check_dataset(label, spec):
    folder,names,column=spec
    for name in names:
        matches=sorted((ROOT/folder).rglob(name)) if (ROOT/folder).exists() else []
        if matches:
            p=matches[0]; return {'area':'Kaggle','check':label,'path':str(p.relative_to(ROOT)), 'sha256':sha256(p),**csv_stats(p,column)}
    return {'area':'Kaggle','check':label,'status':'BLOCKED','reason':'Original CSV not provided'}
def check_export(label,relative):
    p=ROOT/relative
    if not p.exists():return {'area':'Power BI exports','check':label,'status':'BLOCKED','reason':'Export has not been generated'}
    return {'area':'Power BI exports','check':label,'path':relative,'sha256':sha256(p),**csv_stats(p)}
def collect(run_tests=True):
    rows=[check_dataset(k,v) for k,v in DATASETS.items()]
    rows += [check_export(k,v) for k,v in EXPORTS.items()]
    if run_tests:
        try:
            cmd=[sys.executable,'-m','unittest','discover','-s','tests','-p','test_acceptance_v23.py','-v']
            result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=90)
            (ROOT/'evidence').mkdir(exist_ok=True)
            (ROOT/'evidence'/'v23_unittest.txt').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
            rows.append({'area':'Automated tests','check':'V23 acceptance tests','status':'PASS' if result.returncode==0 else 'FAIL','reason':(result.stdout+result.stderr)[-700:]})
        except (subprocess.TimeoutExpired,OSError) as exc:
            rows.append({'area':'Automated tests','check':'V23 acceptance tests','status':'BLOCKED','reason':str(exc)})
    rows.extend([
        {'area':'Windows','check':'Launcher and browser smoke test','status':'NOT TESTED','reason':'Run MO_SORTINGLAB.bat on Windows and record screenshots'},
        {'area':'Power BI','check':'Native .pbix dashboard','status':'NOT TESTED','reason':'Open CSVs in Power BI Desktop, save and inspect PBIX'},
    ])
    return rows
def main():
    out=ROOT/'evidence';out.mkdir(exist_ok=True)
    rows=collect()
    keys=['area','check','status','path','rows','valid_numeric','sha256','columns','reason']
    with (out/'v23_acceptance.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    (out/'v23_acceptance.json').write_text(json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),'checks':rows},indent=2,ensure_ascii=False),encoding='utf-8')
    for row in rows:print(f"{row['status']:10} {row['area']}: {row['check']}")
    print('Evidence written to evidence/v23_acceptance.csv and .json')
    return 1 if any(r['status']=='FAIL' for r in rows) else 0
if __name__=='__main__':sys.exit(main())
