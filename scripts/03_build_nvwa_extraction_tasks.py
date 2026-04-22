#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX_PATH = ROOT / "references" / "nvwa" / "transcript_index.jsonl"
DEFAULT_PROMPT_PATH = ROOT / "references" / "nvwa" / "prompts" / "transcript_extract_prompt.md"
DEFAULT_OUTPUT_DIR = ROOT / "references" / "nvwa" / "tasks"
REVIEW_QUEUE_FILENAME = "review_queue.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_input_text(record: dict, prompt_text: str) -> str:
    source_path = Path(record["source_path"])
    source_text = source_path.read_text(encoding="utf-8")
    return (
        f"{prompt_text}\n\n"
        f"## Transcript Metadata\n\n"
        f"- seq: {record['seq']}\n"
        f"- title: {record['title']}\n"
        f"- aweme_id: {record['aweme_id']}\n"
        f"- create_time: {record['create_time']}\n"
        f"- source_path: {record['source_path']}\n"
        f"- content_type_hint: {record['content_type']}\n"
        f"- primary_targets_hint: {', '.join(record['primary_targets'])}\n"
        f"- value_level_hint: {record['value_level']}\n\n"
        f"## Transcript Content\n\n"
        f"{source_text.strip()}\n"
    )


def make_task_record(record: dict, prompt_text: str) -> dict:
    seq = int(record["seq"])
    source_path = Path(record["source_path"])
    cleaned_md_text = source_path.read_text(encoding="utf-8")
    return {
        "task_id": f"transcript-extract-{seq:04d}",
        "schema_version": "1",
        "task_type": "cleaned_md_extraction_v2",
        "cleaned_md_text": cleaned_md_text,
        "input": build_input_text(record, prompt_text),
        "metadata": {
            "seq": seq,
            "title": record["title"],
            "aweme_id": record["aweme_id"],
            "create_time": record["create_time"],
            "source_path": record["source_path"],
            "content_type": record["content_type"],
            "primary_targets": record["primary_targets"],
            "value_level": record["value_level"],
        },
    }


def build_tasks(index_path: Path, prompt_path: Path, output_dir: Path, sample_size: int = 30) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_text = prompt_path.read_text(encoding="utf-8")
    records = load_jsonl(index_path)
    review_records = [record for record in records if record.get("needs_review")]
    eligible_records = [record for record in records if not record.get("needs_review")]
    tasks = [make_task_record(record, prompt_text) for record in eligible_records]

    full_path = output_dir / "transcript_extract_tasks.jsonl"
    full_path.write_text(
        "\n".join(json.dumps(task, ensure_ascii=False) for task in tasks) + ("\n" if tasks else ""),
        encoding="utf-8",
    )

    sample_path = output_dir / "transcript_extract_tasks_sample_30.jsonl"
    sample_tasks = tasks[:sample_size]
    sample_path.write_text(
        "\n".join(json.dumps(task, ensure_ascii=False) for task in sample_tasks) + ("\n" if sample_tasks else ""),
        encoding="utf-8",
    )

    review_path = output_dir / REVIEW_QUEUE_FILENAME
    review_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in review_records)
        + ("\n" if review_records else ""),
        encoding="utf-8",
    )

    return {
        "count": len(tasks),
        "sample_count": len(sample_tasks),
        "review_count": len(review_records),
        "full_path": str(full_path),
        "sample_path": str(sample_path),
        "review_path": str(review_path),
    }


def main() -> None:
    result = build_tasks(
        index_path=DEFAULT_INDEX_PATH,
        prompt_path=DEFAULT_PROMPT_PATH,
        output_dir=DEFAULT_OUTPUT_DIR,
    )
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
