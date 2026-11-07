import json
import math
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'report/report.pdf'
M=json.loads((ROOT/'results/memory.json').read_text())
R=json.loads((ROOT/'results/parallel.json').read_text())
V=json.loads((ROOT/'results/verification.json').read_text())
P=json.loads((ROOT/'results/pairs.json').read_text())
S=json.loads((ROOT/'results/s3_objects.json').read_text())

def logjson(name):return json.loads((ROOT/'logs'/name).read_text().split('\n',1)[1])
NODE=logjson('nodes.txt')['items'][0]
EP=V['preemption_events'][0]
CP=logjson('cpu-pending.txt')
COND=next(x for x in CP['status']['conditions'] if x.get('reason')=='Unschedulable')
pdfmetrics.registerFont(TTFont('Arial','/System/Library/Fonts/Supplemental/Arial.ttf'))
pdfmetrics.registerFont(TTFont('ArialBold','/System/Library/Fonts/Supplemental/Arial Bold.ttf'))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='ArialBold',italic='Arial',boldItalic='ArialBold')
INK=colors.HexColor('#423342');ROSE=colors.HexColor('#a75d7d');LIGHT=colors.HexColor('#f7eaf0');GRID=colors.HexColor('#e8d8e2')
styles={
 'body':ParagraphStyle('body',fontName='Arial',fontSize=10,leading=14.8,textColor=INK,spaceAfter=9),
 'small':ParagraphStyle('small',fontName='Arial',fontSize=8.3,leading=11.3,textColor=INK,spaceAfter=7,wordWrap='CJK'),
 'h':ParagraphStyle('h',fontName='ArialBold',fontSize=19,leading=25,textColor=ROSE,spaceAfter=16),
 'sub':ParagraphStyle('sub',fontName='ArialBold',fontSize=11,leading=15,textColor=ROSE,spaceBefore=8,spaceAfter=7),
 'title':ParagraphStyle('title',fontName='ArialBold',fontSize=29,leading=37,textColor=INK,spaceAfter=22),
 'cell':ParagraphStyle('cell',fontName='Arial',fontSize=8.6,leading=12,textColor=INK),
}
story=[]
def p(text,style='body'):story.append(Paragraph(text,styles[style]))
def h(text):p(text,'h')
def sub(text):p(text,'sub')
def table(headers,rows,widths=None):
 data=[[Paragraph(escape(str(x)),styles['cell']) for x in row] for row in [headers]+rows]
 t=Table(data,colWidths=widths or [475/len(headers)]*len(headers),repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.4,GRID),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
 story.extend([t,Spacer(1,12)])
def quote(text):
 t=Table([[Paragraph(escape(text).replace('\n','<br/>'),styles['small'])]],colWidths=[475])
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#f6f3f7')),('BOX',(0,0),(-1,-1),0.5,GRID),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
 story.extend([t,Spacer(1,12)])
def page():story.append(PageBreak())
def mib(n):return n/2**20

story.append(Spacer(1,90))
p('ИНЖЕНЕРИЯ ДАННЫХ · ВК','sub')
p('Управление ресурсами\nв Kubernetes'.replace('\n','<br/>'),'title')
p('Расчёт пар навыков, ограничения памяти, планирование, приоритеты и квоты')
story.append(Spacer(1,60))
p('<b>Вита-Виктория Гиалтсо-Мижа</b>')
p('Группа j3313<br/>ИСУ 466703<br/>Вариант 7: вакансии Go/Golang')
story.append(Spacer(1,65))
p('Фактические запуски: 7 ноября 2026 года','small')
p('Программа расчёта написана на Python. Go/Golang здесь обозначает сегмент вакансий индивидуального варианта.','small')
page()
h('1. Среда и контрольный расчёт')
p('На Mac с ARM64 поднята отдельная виртуальная машина Colima: 4 CPU, 4 GiB памяти и диск данных 12 GiB. В ней создан один узел kind. Кластер предназначен для учебных экспериментов, отказоустойчивость нескольких физических машин здесь не проверяется.')
table(['Параметр','Значение'],[
 ['Кластер / namespace','kind-vk-hw5 / vk-hw5'],['Узел',NODE['metadata']['name']],
 ['Kubernetes',NODE['status']['nodeInfo']['kubeletVersion']],['CPU capacity / allocatable',NODE['status']['capacity']['cpu']+' / '+NODE['status']['allocatable']['cpu']],
 ['Память allocatable',NODE['status']['allocatable']['memory']],['Расчётный образ','vk-pairs:hw5; Python 3.12-slim'],['Хранилище','RustFS Deployment + Service + PersistentVolumeClaim']], [165,310])
p('Использован тот же файл vacancies.jsonl из ДЗ №3: 10 000 строк. Фильтр выбирает отдельное слово Go или Golang в названии вакансии. Навыки приводятся к нижнему регистру, пробелы по краям удаляются, повторы внутри вакансии исключаются. Каждая неупорядоченная пара учитывается один раз на вакансию.')
quote('Контроль ДЗ №3\nВакансий варианта: 124\nУникальных пар: 1008\nСумма частот пар: 2382\nПолный словарь частот совпал с hw3_reference.json')
p('Сначала Job читает исходный файл из локального образа. Затем этот же файл загружается в S3 внутри кластера. Четыре indexed-задачи читают разные части, а отдельный reducer суммирует частоты. Полный исходный файл не публикуется в репозитории.','small')
page()
h('2. Память: OOMKilled и рабочий предел')
b=M['baseline'];z=M['sized'];peak=mib(b['cgroup_peak_bytes'])
table(['Запуск','Лимит памяти','Результат'],[['pairs-baseline','256 MiB','Completed; совпадение с ДЗ №3'],['pairs-oom',str(M['oom_limit_mi'])+' MiB','OOMKilled, exit code 137'],['pairs-sized',str(M['chosen_limit_mi'])+' MiB','Completed; совпадение с ДЗ №3']],[155,110,210])
p(f"После подсчёта в исходном запуске memory.peak cgroup равен {peak:.2f} MiB. Пик RSS процесса по getrusage - {mib(b['peak_rss_bytes']):.2f} MiB. Эти показатели не обязаны совпадать: RSS и учёт cgroup по-разному учитывают общие страницы и файловый кеш.")
p(f"Рабочий предел выбран с запасом 50% от измерения cgroup и округлением вверх до 8 MiB: ceil(1.5 × {peak:.2f} / 8) × 8 = {M['chosen_limit_mi']} MiB. При этом он выше и измеренного RSS. Слишком маленький предел {M['oom_limit_mi']} MiB выбран для отрицательного опыта: он не позволяет завершить запуск Python и расчёт.")
quote('kubectl get pods -n vk-hw5 -l job-name=pairs-oom -o json\nreason: '+V['oom']['reason']+'\nexitCode: '+str(V['oom']['exitCode']))
quote('pairs-sized\nrows: '+str(z['rows'])+'\nunique_pairs: '+str(z['unique_pairs'])+'\npeak_rss_bytes: '+str(z['peak_rss_bytes'])+'\ncgroup_peak_bytes: '+str(z['cgroup_peak_bytes'])+'\nmatches_hw3: true')
p('memory limit ограничивает потребление памяти и при нехватке может привести к OOM kill. CPU limit обычно приводит к throttling, а не к OOMKilled. Request нужен планировщику для размещения; это отдельное свойство, не замена limit. Измерение относится к этому небольшому файлу и этому образу, для большего входа предел нужно измерять заново.','small')
p('Доказательства: logs/pairs-oom-pods.txt, logs/pairs-sized-pods.txt, results/memory.json.','small')
page()
h('3. S3 и параллельный расчёт')
p(f"RustFS работает в namespace vk-hw5, адрес для задач - http://rustfs:9000. Бакет hh-lake содержит исходный объект raw/vacancies.jsonl размером {S['raw/vacancies.jsonl']['bytes']} байт. Данные лежат в PVC на локальном томе узла; пересоздание Pod не удаляет их, но удаление самого kind-кластера требует повторной загрузки.")
p('Файл разделён по границам строк на четыре непересекающиеся части по 2500 строк. Job использует completionMode: Indexed, completions: 4 и parallelism: 4. Частота считается внутри каждой части; reducer складывает счётчики. Нормализация навыков и фильтр совпадают с контрольным расчётом.')
table(['Часть','Вакансий варианта','Уникальных пар','Сумма частот'],[[x['output'].split('/')[-1],x['rows'],x['unique_pairs'],x['total_pairs']] for x in sorted(R['parts'],key=lambda x:x['output'])],[90,135,125,125])
p('Итог reducer: 124 вакансии, 1008 уникальных пар, 2382 вхождения. Из S3 повторно скачан результат, и все 1008 частот сравнивались с ДЗ №3. Совпадение только первых строк не использовалось как достаточная проверка. При равных частотах пары упорядочены лексикографически.')
table(['Пара навыков','Частота'],[(' + '.join(x['skills']),x['count']) for x in P['top10']],[375,100])
p('Итоги: results/pairs.json, results/parallel.json, results/s3_objects.json; логи каждого mapper и reducer находятся в logs/. На файле 3 MB накладные расходы Kubernetes и S3 заметны, поэтому по этому опыту не заявляется ускорение в четыре раза.','small')
page()
h('4. Планировщик, приоритеты и квота')
sub('Ожидание CPU')
p('Pod cpu-blocker запросил 2 CPU. После него создан cpu-waiting с таким же request. С учётом системных Pod и RustFS обе заявки не помещались на узле одновременно. Чтобы успеть наблюдать состояние, после подсчёта процесс удерживался sleep 300. Это опыт над резервированием ресурсов, а не тест фактической загрузки процессора.')
quote('cpu-waiting: Pending\nreason: Unschedulable\n'+COND['message'])
p('После удаления cpu-blocker ожидающий Pod стал Ready. Это показывает, что планировщик учитывает requests даже при низком текущем CPU usage.')
sub('Вытеснение')
p('PriorityClass vk-hw5-low имеет значение 1000, vk-hw5-high - 2000. Сначала запущен priority-low с request 2 CPU, затем priority-high с тем же request. Высокоприоритетный Pod стал Ready, а для priority-low записано событие Preempted.')
quote('reason: Preempted\n'+EP['message'])
sub('Квота namespace')
p('В vk-hw5-quota установлена ResourceQuota: requests.cpu = 500m, requests.memory = 128Mi, limits.cpu = 1, limits.memory = 256Mi, pods = 2. Создание Pod с CPU request 600m отклонено на этапе API admission.')
quote('Forbidden: exceeded quota: compute-budget\nrequested: requests.cpu=600m\nused: requests.cpu=0\nlimited: requests.cpu=500m')
p('Отказ квоты отличается от ожидания CPU: при квоте Pod вообще не создан, а при нехватке ресурса узла объект Pod существует и находится в Pending. Проверки: logs/cpu-pending.txt, logs/cpu-after-release.txt, logs/priority-events.txt, logs/quota-rejection.txt.','small')
page()
h('5. YARN, Mesos и Kubernetes')
p('Соответствия ниже описывают близкие роли. Компоненты не являются точными взаимозаменяемыми аналогами.')
table(['Роль','YARN','Mesos','Kubernetes'],[
 ['Ресурсы кластера','ResourceManager','Master / allocator','API server, scheduler и контроллеры'],
 ['Работа на узле','NodeManager','Agent и executor','kubelet и container runtime'],
 ['Координация приложения','ApplicationMaster','Framework scheduler','Job controller; для сложных приложений свой driver/operator'],
 ['Размещение','RM выделяет контейнеры по заявкам AM','Framework принимает или отклоняет resource offer','kube-scheduler назначает Pod узлу'],
 ['Единица ресурса','YARN container','Ресурсы offer и задачи executor','Pod с одним или несколькими контейнерами'],
 ['Политика разделения','Очереди Capacity/Fair','Allocator, роли, квоты','Requests/limits, приоритеты, ResourceQuota'],
 ['Отказоустойчивость управления','HA ResourceManager','Active/standby master, ZooKeeper','HA control plane, etcd и leader election']], [95,120,125,135])
sub('Почему один общий кластер')
p('Выделенные кластеры MapReduce и Spark могут быть загружены неравномерно: один простаивает, пока другой перегружен. Общий менеджер позволяет перераспределять мощности между приложениями. При общем доступе к данным также не приходится держать отдельную копию набора для каждого фреймворка.')
sub('Централизованная и двухуровневая модель')
p('В YARN глобальный ResourceManager принимает заявки ApplicationMaster и выделяет контейнеры. В Mesos первый уровень предлагает ресурсы, а scheduler конкретного фреймворка решает, подходят ли они его задачам. Это удобно для разных фреймворков с собственными требованиями, но требует согласования распределения между ними. В Kubernetes обычное размещение Pod централизовано в scheduler; вычислительную логику приложения он сам не знает.')
p('Важное различие: YARN container означает выделенный набор ресурсов, а не обязательно Docker/OCI-контейнер. ApplicationMaster координирует конкретное приложение; обычный Kubernetes Job controller не реализует всю логику Spark или произвольный DAG.','small')
page()
h('6. Ответы по презентации')
sub('Три сущности YARN и запуск приложения')
p('ResourceManager распределяет ресурсы всего кластера. NodeManager запускает и контролирует контейнеры на своём узле. ApplicationMaster принадлежит одному приложению: получает контейнеры, назначает им задачи и следит за выполнением. Сначала клиент запускает AM через RM, затем AM договаривается о дополнительных контейнерах и работает с NodeManager.')
sub('Как проходит resource offer в Mesos')
p('Master сообщает scheduler фреймворка о доступных ресурсах. Scheduler принимает предложение и указывает задачи либо отклоняет его. При принятии master передаёт запуск agent, а задачи исполняет executor. Отклонённые ресурсы могут быть предложены другим подходящим фреймворкам: они не обязаны простаивать в ожидании нового предложения именно тому же scheduler.')
sub('Отказ master и ZooKeeper')
p('Одновременно работает несколько master: один active и остальные standby. ZooKeeper участвует в выборе лидера и обнаружении активного master клиентами, agent и scheduler. После отказа выбирается новый active. Это не означает автоматического exactly-once выполнения любой пользовательской задачи: обработку повторов и состояние приложения тоже нужно учитывать.')
sub('Большая batch-задача и короткий запрос при FIFO')
p('Если большая задача заняла все ресурсы, короткий запрос при FIFO будет ждать. Fair Scheduler позволяет разделять ресурсы между приложениями, а Capacity Scheduler - выделять гарантированные доли очередям. Если свободных контейнеров нет, одного изменения порядка очереди недостаточно для немедленного запуска: нужна настроенная preemption либо освобождение ресурсов.')
sub('Зачем несколько scheduler для разных фреймворков')
p('У MapReduce, Spark и интерактивных сервисов разные требования к локальности, размеру групп задач и времени ожидания. Двухуровневая модель оставляет эти решения scheduler фреймворка, а общий уровень распределяет пул ресурсов. Это гибкость, но не гарантия лучшего результата на любом наборе задач.')
p('Вопросы и определения сверены со слайдами 10, 12-17, 19-22 и 24-28 лекции К. Хицко «Менеджеры ресурсов YARN и Mesos».','small')
page()
h('7. Воспроизведение и файлы')
p('Код и журналы публикуются в папке hw5-kubernetes репозитория Vitamj/data-engineering-hw3. Для повторения нужен тот же data/vacancies.jsonl из ДЗ №3. Полные данные и credentials исключены из Git; контрольные частоты находятся в results/hw3_reference.json.')
quote('docker build -t vk-pairs:hw5 .\nkind create cluster --name vk-hw5 --kubeconfig runtime/kubeconfig\nkind load docker-image vk-pairs:hw5 --name vk-hw5\npython3.12 run_experiments.py\npython3.12 collect_results.py')
p('Перед запуском Docker должен работать. На этом Mac использовался профиль Colima vk-hw5. Если образы не загружаются напрямую из VM из-за TLS-сбоев, их можно скачать через crane на хосте, импортировать docker load и загрузить kind load docker-image. Имена namespace и кластера выделены только для этой работы.')
table(['Файлы','Назначение'],[['Dockerfile, src/','Образ и программа расчёта'],['manifests/','Job, RustFS, том, приоритеты и квота'],['run_experiments.py','Последовательность экспериментов и запись журналов'],['collect_results.py','Повторное чтение S3 и проверка доказательств'],['logs/','Выводы команд, состояния Pod и события'],['results/','Полные частоты, измерения и сверка с ДЗ №3']],[205,270])
sub('Источники')
for title,url in [
 ('Kubernetes: requests и limits','https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/'),
 ('Kubernetes: приоритеты и preemption','https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/'),
 ('Kubernetes: ResourceQuota','https://kubernetes.io/docs/concepts/policy/resource-quotas/'),
 ('Apache Hadoop: YARN','https://hadoop.apache.org/docs/current/hadoop-yarn/hadoop-yarn-site/YARN'),
 ('Apache Mesos: Scheduler HTTP API','https://mesos.apache.org/documentation/scheduler-http-api/'),
 ('Apache Mesos: High Availability','https://mesos.apache.org/documentation/high-availability/')]:
 p(escape(title)+'<br/><link href="'+url+'">'+escape(url)+'</link>','small')

def decor(canvas,doc):
 canvas.setStrokeColor(GRID);canvas.setLineWidth(0.8);canvas.line(60,39,535,39)
 canvas.setFillColor(ROSE);canvas.setFont('Arial',8);canvas.drawRightString(535,26,str(doc.page))
 canvas.setFillColor(LIGHT);canvas.rect(0,A4[1]-10,A4[0],10,fill=1,stroke=0)

doc=SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=60,rightMargin=60,topMargin=52,bottomMargin=55,title='Управление ресурсами в Kubernetes',author='Вита-Виктория Гиалтсо-Мижа')
doc.build(story,onFirstPage=decor,onLaterPages=decor)
print(OUT)
