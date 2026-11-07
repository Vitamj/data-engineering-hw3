import argparse
import json
import os
import re
import resource
from pathlib import Path
import time
from collections import Counter
from itertools import combinations

import s3

GO = re.compile(r'(?<!\w)(?:go|golang)(?!\w)', re.I)


def calculate(stream):
    result = Counter()
    rows = 0
    for line in stream:
        row = json.loads(line)
        if not GO.search(row.get('name', '')):
            continue
        rows += 1
        skills = sorted({str(s).strip().lower() for s in row['skills'] if str(s).strip()})
        result.update(combinations(skills, 2))
    return result, rows


def encode(counts):
    return [{'skills': list(p), 'count': n} for p, n in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', default='raw/vacancies.jsonl')
    parser.add_argument('--prefix', default='results/single')
    parser.add_argument('--parts', type=int, default=0)
    parser.add_argument('--local', action='store_true')
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    index = int(os.getenv('JOB_COMPLETION_INDEX', '0'))
    bucket = 'hh-lake'
    start = time.monotonic()
    if args.upload:
        try:
            s3.create_bucket(bucket)
        except Exception as error:
            if getattr(error, 'code', None) != 409:
                raise
        payload = Path('/input/vacancies.jsonl').read_bytes()
        s3.put(bucket, 'raw/vacancies.jsonl', payload)
        lines = payload.splitlines(keepends=True)
        for i in range(4):
            part = b''.join(lines[len(lines)*i//4:len(lines)*(i+1)//4])
            s3.put(bucket, f'parts/{i}.jsonl', part)
        print(json.dumps(dict(uploaded_rows=len(lines), parts=4)), flush=True)
        return
    if args.local:
        with open('/input/vacancies.jsonl', 'rb') as stream:
            counts, rows = calculate(stream)
        output_key = None
    elif args.parts:
        counts = Counter()
        rows = 0
        for i in range(args.parts):
            with s3.get(bucket, f'results/parts/{i}.json') as response:
                part = json.load(response)
            for item in part['counts']:
                counts[tuple(item['skills'])] += item['count']
            rows += part['rows']
        output_key = 'results/parallel.json'
    else:
        key = args.key.format(index=index)
        with s3.get(bucket, key) as stream:
            counts, rows = calculate(stream)
        output_key = f'{args.prefix}/{index}.json'
    result = dict(rows=rows, counts=encode(counts), elapsed_seconds=time.monotonic()-start,
                  peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    result['top10'] = result['counts'][:10]
    peak = Path('/sys/fs/cgroup/memory.peak')
    result['cgroup_peak_bytes'] = int(peak.read_text()) if peak.exists() else None
    if args.local or args.parts:
        expected = {tuple(x['skills']): x['count'] for x in json.loads(Path('/input/expected.json').read_text())}
        assert dict(counts) == expected, 'Result differs from HW3'
        result['matches_hw3'] = True
    if output_key:
        s3.put(bucket, output_key, json.dumps(result, ensure_ascii=False).encode())
    print(json.dumps(dict(output=output_key, rows=rows, unique_pairs=len(counts),
                         total_pairs=sum(counts.values()), peak_rss_bytes=result['peak_rss_bytes'],
                         elapsed_seconds=result['elapsed_seconds'], cgroup_peak_bytes=result['cgroup_peak_bytes'],
                         matches_hw3=result.get('matches_hw3'), top10=result['top10']), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
