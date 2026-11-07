FROM python:3.12-slim
WORKDIR /app
COPY src/ .
COPY data/vacancies.jsonl /input/vacancies.jsonl
COPY results/hw3_reference.json /input/expected.json
USER 10001:10001
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python", "pairs.py"]
