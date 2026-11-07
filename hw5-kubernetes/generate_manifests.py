import json
from pathlib import Path

OUT = Path('manifests')
OUT.mkdir(exist_ok=True)
NS = 'vk-hw5'
IMAGE = 'vk-pairs:hw5'


def save(name, obj):
    (OUT / (name + '.json')).write_text(json.dumps(obj, indent=2) + '\n')


def pod(name, cpu='100m', memory='128Mi', args=None, priority=None, hold=False):
    container = dict(name='pairs', image=IMAGE, imagePullPolicy='Never', args=args or ['--local'],
                     resources=dict(requests=dict(cpu=cpu, memory='16Mi'), limits=dict(cpu=cpu, memory=memory)))
    if hold:
        container['command'] = ['sh', '-c', 'python pairs.py --local; sleep 300']
        container.pop('args')
    spec = dict(restartPolicy='Never', terminationGracePeriodSeconds=2, containers=[container])
    if priority:
        spec['priorityClassName'] = priority
    return dict(apiVersion='v1', kind='Pod', metadata=dict(name=name, namespace=NS), spec=spec)


def job(name, args, memory='128Mi', s3=False, indexed=False):
    p = pod(name, memory=memory, args=args)
    if s3:
        p['spec']['containers'][0]['envFrom'] = [dict(secretRef=dict(name='s3-credentials'))]
        p['spec']['containers'][0]['env'] = [dict(name='S3_ENDPOINT', value='http://rustfs:9000')]
    spec = dict(backoffLimit=0, template=dict(metadata=dict(labels=dict(app=name)), spec=p['spec']))
    if indexed:
        spec.update(completionMode='Indexed', completions=4, parallelism=4)
    return dict(apiVersion='batch/v1', kind='Job', metadata=p['metadata'], spec=spec)


save('00-namespace', dict(apiVersion='v1',kind='Namespace',metadata=dict(name=NS)))
save('10-baseline', job('pairs-baseline', ['--local'], '256Mi'))
save('20-storage',dict(apiVersion='v1',kind='List',items=[
 dict(apiVersion='v1',kind='PersistentVolume',metadata=dict(name='vk-hw5-rustfs'),
      spec=dict(capacity=dict(storage='1Gi'), accessModes=['ReadWriteOnce'], persistentVolumeReclaimPolicy='Retain',
                storageClassName='vk-local', hostPath=dict(path='/var/local/vk-hw5-rustfs',type='DirectoryOrCreate'))),
 dict(apiVersion='v1',kind='PersistentVolumeClaim',metadata=dict(name='rustfs-data',namespace=NS),
      spec=dict(accessModes=['ReadWriteOnce'], storageClassName='vk-local', volumeName='vk-hw5-rustfs',resources=dict(requests=dict(storage='1Gi')))),
 dict(apiVersion='v1',kind='Service',metadata=dict(name='rustfs',namespace=NS),
      spec=dict(selector=dict(app='rustfs'),ports=[dict(port=9000,targetPort=9000)])),
 dict(apiVersion='apps/v1',kind='Deployment',metadata=dict(name='rustfs',namespace=NS),
      spec=dict(replicas=1,selector=dict(matchLabels=dict(app='rustfs')),template=dict(
       metadata=dict(labels=dict(app='rustfs')),spec=dict(
        initContainers=[dict(name='permissions',image='busybox:1.37',command=['sh','-c','chown -R 10001:10001 /data /logs'],
                             volumeMounts=[dict(name='data',mountPath='/data'),dict(name='logs',mountPath='/logs')])],
        containers=[dict(name='rustfs',image='rustfs/rustfs:latest',imagePullPolicy='IfNotPresent',ports=[dict(containerPort=9000)],
          env=[dict(name='RUSTFS_VOLUMES',value='/data'),dict(name='RUSTFS_OBS_LOG_DIRECTORY',value='/logs'),
               dict(name='RUSTFS_ACCESS_KEY',valueFrom=dict(secretKeyRef=dict(name='s3-credentials',key='S3_ACCESS_KEY'))),
               dict(name='RUSTFS_SECRET_KEY',valueFrom=dict(secretKeyRef=dict(name='s3-credentials',key='S3_SECRET_KEY')))],
          resources=dict(requests=dict(cpu='100m',memory='128Mi'),limits=dict(cpu='1',memory='1Gi')),
          readinessProbe=dict(httpGet=dict(path='/health',port=9000),periodSeconds=2),
          volumeMounts=[dict(name='data',mountPath='/data'),dict(name='logs',mountPath='/logs')])],
        volumes=[dict(name='data',persistentVolumeClaim=dict(claimName='rustfs-data')),dict(name='logs',emptyDir={})]))))]))
save('21-upload',job('s3-upload',['--upload'],s3=True))
save('22-parallel',job('pairs-parallel',['--key','parts/{index}.jsonl','--prefix','results/parts'],memory='32Mi',s3=True,indexed=True))
save('23-reduce',job('pairs-reduce',['--parts','4'],memory='32Mi',s3=True))
for name,value in [('low',1000),('high',2000)]:
 save('30-priority-'+name,dict(apiVersion='scheduling.k8s.io/v1',kind='PriorityClass',metadata=dict(name='vk-hw5-'+name),value=value,globalDefault=False,preemptionPolicy='PreemptLowerPriority'))
save('31-blocker',pod('cpu-blocker',cpu='2',hold=True))
save('32-pending',pod('cpu-waiting',cpu='2',hold=True))
save('33-low',pod('priority-low',cpu='2',priority='vk-hw5-low',hold=True))
save('34-high',pod('priority-high',cpu='2',priority='vk-hw5-high',hold=True))
quota_ns='vk-hw5-quota'
save('40-quota',dict(apiVersion='v1',kind='List',items=[
 dict(apiVersion='v1',kind='Namespace',metadata=dict(name=quota_ns)),
 dict(apiVersion='v1',kind='ResourceQuota',metadata=dict(name='compute-budget',namespace=quota_ns),spec=dict(hard={'requests.cpu':'500m','requests.memory':'128Mi','limits.cpu':'1','limits.memory':'256Mi','pods':'2'}))]))
p=pod('quota-rejected',cpu='600m');p['metadata']['namespace']=quota_ns
save('41-quota-rejected',p)
