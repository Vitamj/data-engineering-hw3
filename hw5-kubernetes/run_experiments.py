import json
import math
import os
import secrets
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
K = ['/opt/homebrew/bin/kubectl', '--kubeconfig', str(ROOT/'runtime/kubeconfig')]
NS = 'vk-hw5'
LOG = ROOT/'logs'
LOG.mkdir(exist_ok=True)


def cmd(args, name, stdin=None, check=True):
    result = subprocess.run(K+args, input=stdin, text=True, capture_output=True, timeout=240)
    (LOG/(name+'.txt')).write_text('$ kubectl '+' '.join(args)+'\n'+result.stdout+result.stderr)
    if check and result.returncode:
        raise RuntimeError(name+': '+result.stderr)
    return result


def apply(file):
    return cmd(['apply','-f',str(file)],Path(file).stem+'-apply')


def pods(job):
    return json.loads(cmd(['get','pods','-n',NS,'-l','job-name='+job,'-o','json'],job+'-pods').stdout)['items']


def finish(job):
    cmd(['wait','-n',NS,'--for=condition=complete','job/'+job,'--timeout=180s'],job+'-wait')
    data=pods(job)
    texts=[]
    for pod in data:
        name=pod['metadata']['name']
        text=cmd(['logs','-n',NS,name],job+'-'+name+'-log').stdout
        texts.extend(text.strip().splitlines())
    return [json.loads(t) for t in texts if t.startswith('{')]


def wait_pod(name, condition):
    cmd(['wait','pod/'+name,'-n',NS,'--for=condition='+condition,'--timeout=120s'],name+'-wait')


def events(name, namespace=NS):
    cmd(['get','events','-n',namespace,'--sort-by=.metadata.creationTimestamp','-o','json'],name+'-events')


apply('manifests/00-namespace.json')
cmd(['version','-o','json'],'versions')
cmd(['get','nodes','-o','json'],'nodes')
apply('manifests/10-baseline.json')
baseline=finish('pairs-baseline')[0]
peak=baseline['cgroup_peak_bytes'] or baseline['peak_rss_bytes']
safe=math.ceil(1.5*peak/(8*2**20))*8
small=max(4,math.floor(0.5*peak/2**20))
for name,limit in [('pairs-oom',small),('pairs-sized',safe)]:
    job=json.loads(Path('manifests/10-baseline.json').read_text())
    job['metadata']['name']=name
    c=job['spec']['template']['spec']['containers'][0]
    c['resources']['requests']['memory']='1Mi'
    c['resources']['limits']['memory']=str(limit)+'Mi'
    p=Path('manifests')/(name+'.json');p.write_text(json.dumps(job,indent=2))
    apply(p)
    if name=='pairs-oom':
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            data=pods(name)
            terms=[s.get('state',{}).get('terminated',{}) for p in data for s in p.get('status',{}).get('containerStatuses',[])]
            if any(t.get('reason')=='OOMKilled' for t in terms):break
            if any(t.get('reason')=='Completed' for t in terms):raise RuntimeError('OOM experiment completed without OOM')
            time.sleep(2)
        else:raise RuntimeError('No OOMKilled observed')
        events('oom')
    else:
        sized=finish(name)[0]
Path('results/memory.json').write_text(json.dumps(dict(baseline=baseline,chosen_limit_mi=safe,oom_limit_mi=small,sized=sized),ensure_ascii=False,indent=2))
print('MEMORY DONE',safe,small,flush=True)
for file in ['22-parallel','23-reduce']:
    path=Path('manifests')/(file+'.json')
    obj=json.loads(path.read_text())
    obj['spec']['template']['spec']['containers'][0]['resources']['limits']['memory']=str(safe)+'Mi'
    path.write_text(json.dumps(obj,indent=2))
credentials=ROOT/'runtime/s3.env'
if not credentials.exists():credentials.write_text('S3_ACCESS_KEY=hw5'+secrets.token_hex(6)+'\nS3_SECRET_KEY='+secrets.token_hex(20)+'\n')
cmd(['create','secret','generic','s3-credentials','-n',NS,'--from-env-file='+str(credentials)],'credentials-create',check=False)
apply('manifests/20-storage.json')
cmd(['rollout','status','deployment/rustfs','-n',NS,'--timeout=180s'],'rustfs-ready')
apply('manifests/21-upload.json');finish('s3-upload')
apply('manifests/22-parallel.json');parts=finish('pairs-parallel')
apply('manifests/23-reduce.json');reduced=finish('pairs-reduce')[0]
assert reduced['matches_hw3'] and reduced['top10']==baseline['top10']
Path('results/parallel.json').write_text(json.dumps(dict(parts=parts,reduced=reduced),ensure_ascii=False,indent=2))
print('PARALLEL DONE',flush=True)
for file in ['30-priority-low','30-priority-high','31-blocker']:
    apply('manifests/'+file+'.json')
wait_pod('cpu-blocker','Ready')
apply('manifests/32-pending.json')
for _ in range(30):
    p=json.loads(cmd(['get','pod/cpu-waiting','-n',NS,'-o','json'],'cpu-pending').stdout)
    conditions=p.get('status',{}).get('conditions',[])
    if any(x.get('reason')=='Unschedulable' and 'Insufficient cpu' in x.get('message','') for x in conditions):break
    time.sleep(2)
else:raise RuntimeError('Expected Insufficient cpu was not observed')
events('pending')
cmd(['delete','pod/cpu-blocker','-n',NS,'--wait=true'],'release-cpu')
wait_pod('cpu-waiting','Ready')
cmd(['get','pod/cpu-waiting','-n',NS,'-o','json'],'cpu-after-release')
cmd(['delete','pod/cpu-waiting','-n',NS,'--wait=true'],'pending-cleanup')
apply('manifests/33-low.json');wait_pod('priority-low','Ready')
apply('manifests/34-high.json');wait_pod('priority-high','Ready')
cmd(['get','pods','-n',NS,'-o','json'],'priority-pods')
events('priority')
cmd(['delete','pod/priority-high','-n',NS,'--wait=true'],'priority-cleanup')
apply('manifests/40-quota.json')
r=cmd(['create','-f','manifests/41-quota-rejected.json'],'quota-rejection',check=False)
assert r.returncode and 'exceeded quota' in r.stderr
cmd(['get','resourcequota','-n','vk-hw5-quota','-o','json'],'quota-status')
events('quota','vk-hw5-quota')
cmd(['get','pods','-n',NS,'-o','json'],'final-pods')
Path('results/experiments_complete.json').write_text(json.dumps(dict(memory=True,parallel=True,pending=True,preemption=True,quota=True)))
print('ALL EXPERIMENTS DONE',flush=True)
