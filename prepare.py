from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def prepare(source: Path, destination: Path) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    rows = 0
    with zipfile.ZipFile(source) as archive, destination.open("w", encoding="utf-8", newline="\n") as out:
        for member in sorted(archive.namelist()):
            if not member.endswith(".json"):
                continue
            raw = json.loads(archive.read(member))
            salary = raw.get("salary") or {}
            row = {
                "vacancy_id": str(raw.get("vacancy_id") or Path(member).stem),
                "name": raw.get("name") or "",
                "region": (raw.get("area") or {}).get("name") or "",
                "skills": raw.get("key_skills") or [],
                "salary_from": float(salary["from"]) if salary.get("from") else None,
                "salary_to": float(salary["to"]) if salary.get("to") else None,
                "currency": salary.get("currency"),
                "gross": salary.get("gross"),
            }
            out.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            rows += 1
    return {"source": str(source), "source_sha256": sha, "rows": rows,
            "jsonl_bytes": destination.stat().st_size}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("zip", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/vacancies.jsonl"))
    args = parser.parse_args()
    print(json.dumps(prepare(args.zip, args.output), ensure_ascii=False, indent=2))
