from __future__ import annotations

import json
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations

import s3

GO = re.compile(r"(?<!\w)(?:go|golang)(?!\w)", re.I)


def normalized(skills: list[str]) -> list[str]:
    return sorted({str(x).strip().lower() for x in skills if str(x).strip()})


def map_chunk(lines: list[bytes]):
    counters = [Counter(), Counter(), Counter()]
    vacancies = salary = with_skills = 0
    for line in lines:
        row = json.loads(line)
        if not GO.search(row["name"]):
            continue
        vacancies += 1
        if row.get("currency") == "RUR" and (row.get("salary_from") is not None or row.get("salary_to") is not None):
            salary += 1
        skills = normalized(row["skills"])
        with_skills += bool(skills)
        for size, counter in enumerate(counters, start=1):
            counter.update(combinations(skills, size))
    return counters, {"vacancies": vacancies, "with_skills": with_skills, "rub_salary": salary}


def chunks(stream, size=1 << 20):
    carry = b""
    while block := stream.read(size):
        pieces = (carry + block).split(b"\n")
        carry = pieces.pop()
        if pieces:
            yield pieces
    if carry:
        yield [carry]


def mapreduce(bucket="hh-lake", key="raw/vacancies.jsonl", workers=2):
    totals = [Counter(), Counter(), Counter()]
    meta = Counter()
    with s3.get(bucket, key) as stream, ProcessPoolExecutor(max_workers=workers) as pool:
        for partial, info in pool.map(map_chunk, chunks(stream), chunksize=1):
            for total, counter in zip(totals, partial):
                total.update(counter)
            meta.update(info)
    return totals, dict(meta)


def encode_counts(counter):
    return json.dumps([{"skills": list(key), "count": count}
                       for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))],
                      ensure_ascii=False, indent=2).encode()


def duckdb_counts(conn):
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE go_vacancies AS
        SELECT vacancy_id, name, region,
               list_sort(list_distinct(list_transform(skills, x -> lower(trim(x))))) AS skills,
               salary_from, salary_to, currency, gross
        FROM read_json_auto('s3://hh-lake/raw/vacancies.jsonl', format='newline_delimited')
        WHERE regexp_matches(lower(name), '(^|[^[:alnum:]_])(go|golang)([^[:alnum:]_]|$)')
    """)
    outputs = []
    for size in (1, 2, 3):
        joins = "\n".join(f"CROSS JOIN unnest(v.skills) AS s{i}(skill)" for i in range(1, size + 1))
        conditions = " AND ".join(f"s{i}.skill < s{i+1}.skill" for i in range(1, size))
        selected = ", ".join(f"s{i}.skill AS skill{i}" for i in range(1, size + 1))
        grouped = ", ".join(str(i) for i in range(1, size + 1))
        sql = f"SELECT {selected}, count(*) AS n FROM go_vacancies v {joins} "
        if conditions:
            sql += f"WHERE {conditions} "
        sql += f"GROUP BY {grouped}"
        rows = conn.execute(sql).fetchall()
        outputs.append(Counter({tuple(row[:size]): row[-1] for row in rows}))
    return outputs
