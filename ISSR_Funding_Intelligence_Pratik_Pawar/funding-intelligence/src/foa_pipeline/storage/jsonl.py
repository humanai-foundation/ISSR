import json
from pathlib import Path
from typing import Iterable, Set


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_existing_ids(jsonl_path: Path) -> Set[str]:
    if not jsonl_path.exists():
        return set()
    ids: Set[str] = set()
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            source_id = payload.get("source_id")
            if source_id:
                ids.add(str(source_id))
    return ids


def write_jsonl(jsonl_path: Path, records: Iterable[dict]) -> int:
    count = 0
    with jsonl_path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
            count += 1
    return count
