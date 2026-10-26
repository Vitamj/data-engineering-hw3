from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path

import duckdb
import psutil

import counts
import s3

ROOT = Path(__file__).resolve().parent


def connection():
    extension_dir = ROOT / "runtime" / "duckdb_extensions"
    extension_dir.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(config={"extension_directory": str(extension_dir), "memory_limit": "512MB"})
    conn.execute("LOAD httpfs")
    conn.execute("SET s3_endpoint='127.0.0.1:9000'")
    conn.execute("SET s3_use_ssl=false")
    conn.execute("SET s3_url_style='path'")
    conn.execute(f"SET s3_access_key_id='{s3.ACCESS_KEY}'")
    conn.execute(f"SET s3_secret_access_key='{s3.SECRET_KEY}'")
    conn.execute(f"SET s3_region='{s3.REGION}'")
    return conn


def measure(fn):
    proc = psutil.Process()
    before = proc.memory_info().rss
    peak = [before]
    stop = threading.Event()
    def sample():
        while not stop.is_set():
            processes = [proc, *proc.children(recursive=True)]
            rss = 0
            for process in processes:
                try:
                    rss += process.memory_info().rss
                except psutil.Error:
                    pass
            peak[0] = max(peak[0], rss)
            stop.wait(0.005)
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    start = time.perf_counter()
    try:
        value = fn()
    finally:
        stop.set()
        sampler.join()
    seconds = time.perf_counter() - start
    return value, {"seconds": round(seconds, 4), "rss_before_mb": round(before / 1e6, 2),
                   "rss_after_mb": round(proc.memory_info().rss / 1e6, 2),
                   "peak_rss_mb": round(peak[0] / 1e6, 2)}


def pair_triple_salary(conn):
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE salary_vacancies AS
        SELECT vacancy_id, region, skills,
               coalesce((salary_from + salary_to) / 2, salary_from, salary_to) AS salary
        FROM go_vacancies
        WHERE currency='RUR' AND (salary_from IS NOT NULL OR salary_to IS NOT NULL)
    """)
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE salary_single AS
        SELECT s.skill, count(*) AS n, median(v.salary) AS median_salary
        FROM salary_vacancies v CROSS JOIN unnest(v.skills) AS s(skill)
        GROUP BY 1
    """)
    rows = {}
    for size in (2, 3):
        joins = " ".join(f"CROSS JOIN unnest(v.skills) AS s{i}(skill)" for i in range(1, size + 1))
        where = " AND ".join(f"s{i}.skill < s{i+1}.skill" for i in range(1, size))
        keys = ", ".join(f"s{i}.skill" for i in range(1, size + 1))
        group = ", ".join(str(i) for i in range(1, size + 1))
        sql = f"SELECT {keys}, count(*) AS n, median(v.salary) AS median_salary FROM salary_vacancies v {joins} WHERE {where} GROUP BY {group}"
        combos = conn.execute(sql).fetchall()
        scored = []
        singles = {skill: (n, med) for skill, n, med in conn.execute("SELECT skill,n,median_salary FROM salary_single").fetchall()}
        for row in combos:
            skills, n, med = list(row[:size]), row[size], row[size+1]
            anchor = sorted(skills, key=lambda skill: (-singles[skill][0], skill))[0]
            base_n, base_med = singles[anchor]
            scored.append({"skills": skills, "n": n, "median_rub": med,
                           "anchor": anchor, "anchor_n": base_n,
                           "anchor_median_rub": base_med, "delta_rub": med - base_med})
        rows[str(size)] = sorted(scored, key=lambda r: (-r["n"], r["skills"]))
    return rows


def regions(conn):
    chosen = [r[0] for r in conn.execute("SELECT region FROM go_vacancies GROUP BY 1 ORDER BY count(*) DESC, region LIMIT 3").fetchall()]
    basic = conn.execute("""
        SELECT region, count(*) AS vacancies,
               count(*) FILTER (WHERE currency='RUR' AND (salary_from IS NOT NULL OR salary_to IS NOT NULL)) AS salaries,
               median(coalesce((salary_from + salary_to)/2,salary_from,salary_to))
                 FILTER (WHERE currency='RUR') AS median_rub
        FROM go_vacancies WHERE region IN (SELECT unnest(?::VARCHAR[]))
        GROUP BY 1 ORDER BY vacancies DESC
    """, [chosen]).fetchall()
    top_skills = conn.execute("""
        WITH skill_counts AS (
          SELECT v.region,s.skill,count(*) AS n,
                 row_number() OVER (PARTITION BY v.region ORDER BY count(*) DESC,s.skill) AS rank
          FROM go_vacancies v CROSS JOIN unnest(v.skills) AS s(skill)
          WHERE v.region IN (SELECT unnest(?::VARCHAR[]))
          GROUP BY 1,2
        ) SELECT region,skill,n FROM skill_counts WHERE rank<=5 ORDER BY region,rank
    """, [chosen]).fetchall()
    top_combinations = {}
    for size in (2, 3):
        joins = " ".join(f"CROSS JOIN unnest(v.skills) AS s{i}(skill)" for i in range(1, size + 1))
        condition = " AND ".join(f"s{i}.skill < s{i+1}.skill" for i in range(1, size))
        keys = ", ".join(f"s{i}.skill" for i in range(1, size + 1))
        grouped = ", ".join(str(i) for i in range(1, size + 2))
        sql = (f"SELECT v.region, {keys}, count(*) AS n FROM go_vacancies v {joins} "
               f"WHERE v.region IN (SELECT unnest(?::VARCHAR[])) AND {condition} "
               f"GROUP BY {grouped} ORDER BY v.region, n DESC, {keys}")
        by_region = {region: [] for region in chosen}
        for row in conn.execute(sql, [chosen]).fetchall():
            region, combo, n = row[0], row[1:-1], row[-1]
            if len(by_region[region]) < 3:
                by_region[region].append({"skills": list(combo), "n": n})
        top_combinations[str(size)] = by_region
    return {"regions": chosen, "basic": [{"region": r, "vacancies": n, "salary_rows": sn, "median_rub": med}
                                            for r,n,sn,med in basic],
            "top_skills": [{"region": r, "skill": s, "n": n} for r,s,n in top_skills],
            "top_combinations": top_combinations}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,default=ROOT / "data" / "vacancies.jsonl")
    parser.add_argument("--repeats",type=int,default=3)
    args=parser.parse_args()
    results=ROOT / "results"
    results.mkdir(exist_ok=True)
    try:
        s3.create_bucket("hh-lake")
    except Exception:
        pass  # Existing bucket is acceptable; the PUT/HEAD checks below are not.
    upload=s3.put("hh-lake","raw/vacancies.jsonl",args.input.read_bytes())
    evidence={"input": {"local_bytes": args.input.stat().st_size, "upload": upload,
                         "head": s3.head("hh-lake","raw/vacancies.jsonl")}}
    mr_profiles=[]; sql_profiles=[]
    for _ in range(args.repeats):
        (mr,meta), profile=measure(counts.mapreduce)
        mr_profiles.append(profile)
    for _ in range(args.repeats):
        conn=connection()
        sql,profile=measure(lambda: counts.duckdb_counts(conn))
        sql_profiles.append(profile)
        conn.close()
    differences=[]
    for size,(a,b) in enumerate(zip(mr,sql),start=1):
        if a!=b:
            differences.append({"size":size,"only_mr":list((a-b).items())[:5],"only_sql":list((b-a).items())[:5]})
    if differences:
        raise AssertionError(differences)
    outputs={}
    for size,counter in enumerate(mr,start=1):
        payload=counts.encode_counts(counter)
        key=f"results/go/skills_{size}.json"
        outputs[str(size)]={"unique_combinations":len(counter),"total_occurrences":sum(counter.values()),
                            "top10": [{"skills":list(k),"n":v} for k,v in counter.most_common(10)],
                            "s3": s3.put("hh-lake",key,payload), "s3_head":s3.head("hh-lake",key)}
        (results/f"skills_{size}.json").write_bytes(payload)
    conn=connection(); counts.duckdb_counts(conn)
    salary=pair_triple_salary(conn); regional=regions(conn); conn.close()
    evidence.update({"variant":7,"filter":"Go/Golang as a separate word in vacancy title",
                     "mapreduce_meta":meta,"counts":outputs,"exact_match":True,
                     "profiles":{"mapreduce":mr_profiles,"duckdb":sql_profiles},
                     "salary":salary,"regional":regional})
    (results/"evidence.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:evidence[k] for k in ("input","mapreduce_meta","counts","exact_match","profiles","regional")},ensure_ascii=False,indent=2))


if __name__=="__main__": main()
