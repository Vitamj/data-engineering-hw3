import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0,str(ROOT/'src'))
for line in (ROOT/'runtime/s3.env').read_text().splitlines():
    key,value=line.split('=',1)
    os.environ[key]=value
os.environ['S3_ENDPOINT']='http://127.0.0.1:19005'
import s3

k=['/opt/homebrew/bin/kubectl','--kubeconfig',str(ROOT/'runtime/kubeconfig')]
with (ROOT/'logs/s3-port-forward.txt').open('w') as log:
    process=subprocess.Popen(k+['-n','vk-hw5','port-forward','service/rustfs','19005:9000'],stdout=log,stderr=log)
    try:
        for _ in range(40):
            try:
                head=s3.head('hh-lake','raw/vacancies.jsonl');break
            except Exception:
                time.sleep(0.25)
        else:raise RuntimeError('S3 not reachable')
        with s3.get('hh-lake','results/parallel.json') as response:
            result=json.load(response)
        expected=json.loads((ROOT/'results/hw3_reference.json').read_text())
        assert result['counts']==expected
        assert result['rows']==124 and result['matches_hw3']
        (ROOT/'results/pairs.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        objects={key:s3.head('hh-lake',key) for key in ['raw/vacancies.jsonl']+[f'parts/{i}.jsonl' for i in range(4)]+[f'results/parts/{i}.json' for i in range(4)]+['results/parallel.json']}
        (ROOT/'results/s3_objects.json').write_text(json.dumps(objects,indent=2))
    finally:
        process.terminate();process.wait(timeout=10)

def logged(name):
    return json.loads((ROOT/'logs'/name).read_text().split('\n',1)[1])
events=logged('priority-events.txt')['items']
victims=[x for x in events if x.get('reason')=='Preempted' and x.get('regarding',x.get('involvedObject',{})).get('name')=='priority-low']
assert victims,'No priority-low Preempted event'
pending=logged('cpu-pending.txt')
assert any(c.get('reason')=='Unschedulable' and 'Insufficient cpu' in c.get('message','') for c in pending['status']['conditions'])
assert 'exceeded quota' in (ROOT/'logs/quota-rejection.txt').read_text()
oom=logged('pairs-oom-pods.txt')['items'][0]['status']['containerStatuses'][0]['state']['terminated']
assert oom['reason']=='OOMKilled' and oom['exitCode']==137
(ROOT/'results/verification.json').write_text(json.dumps(dict(full_counts_match_hw3=True,unique_pairs=len(expected),total_pairs=sum(x['count'] for x in expected),oom=oom,preemption_events=victims,pending_cpu=True,quota_rejected=True),ensure_ascii=False,indent=2))
print('VERIFIED: all 1008 counts match HW3; OOMKilled/137, pending CPU, Preempted victim and quota rejection confirmed')
