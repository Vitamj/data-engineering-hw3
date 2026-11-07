# ДЗ 5. Kubernetes

Работа по инженерии данных (ВК). Вариант 7 из ДЗ №3: вакансии Go/Golang. Расчёт написан на Python.

[Отчёт PDF](report/report.pdf)

Здесь лежат Dockerfile, программа расчёта, манифесты, журналы и результаты. Все 1008 частот пар после параллельного расчёта совпали с ДЗ №3.

## Что получилось

- При лимите 8 MiB: OOMKilled, код 137.
- Измеренный пик cgroup: 17.39 MiB. Рабочий предел с запасом: 32 MiB.
- RustFS работает внутри кластера, исходный объект находится в `hh-lake`.
- Четыре indexed-задачи обработали разные части файла; reducer получил те же топ-10 и полный словарь частот.
- Зафиксированы Pending с `Insufficient cpu`, событие `Preempted` и отказ квоты при запросе 600m вместо разрешённых 500m.

## Повторный запуск на Mac

Нужны Colima (или другой работающий Docker), Docker CLI, kind, kubectl и Python 3.12. Для расчёта Python-пакеты устанавливать не требуется.

Положить исходный `vacancies.jsonl` из ДЗ №3 в `data/`. Это тот же файл после `prepare.py`; новые данные брать не нужно.

```bash
mkdir -p runtime
colima -p vk-hw5 start --cpu 4 --memory 4 --disk 12
export DOCKER_HOST="unix://$HOME/.colima/vk-hw5/docker.sock"
docker build -t vk-pairs:hw5 .
kind create cluster --name vk-hw5 --kubeconfig runtime/kubeconfig
kind load docker-image vk-pairs:hw5 --name vk-hw5
python3.12 run_experiments.py
python3.12 collect_results.py
```

Запускать в новом кластере с указанным именем. Скрипт создаёт два своих namespace: `vk-hw5` и `vk-hw5-quota`. Локальные ключи S3 генерируются в `runtime/s3.env` и передаются через Secret; в Git они не входят.

Если в старой конфигурации Docker осталась ссылка на отсутствующий credential-helper, можно использовать отдельный `DOCKER_CONFIG` с пустым `auths`. При сетевых TLS-сбоях загрузки образов из VM в этом запуске использовался `crane pull` на macOS, затем `docker load` и `kind load docker-image`. Манифест RustFS использует `IfNotPresent`.

`generate_manifests.py` создаёт исходные манифесты. `run_experiments.py` подбирает предел по пику и записывает его в манифесты расчёта. Для CPU/priority-опытов Pod после расчёта удерживается `sleep 300`: проверяется планирование по requests, а не загрузочное тестирование CPU.

Полный итог находится в `results/pairs.json`, контроль ДЗ №3 - в `results/hw3_reference.json`. Файлы в `logs/` содержат фактические выводы команд. `collect_results.py` повторно читает S3 и проверяет результат, OOM, событие preemption и отказ квоты.

Для повторной сборки PDF нужен `reportlab` и шрифты Arial из macOS; генератор - `build_report.py`. Готовый PDF уже приложен.

После проверки можно остановить VM: `colima -p vk-hw5 stop`. Данные сохранятся; для продолжения нужно снова запустить этот профиль.

В опубликованных журналах локальные пути заменены на `<WORKDIR>` и `<HOME>`. Команды, состояния Pod, события и численные результаты сохранены.
