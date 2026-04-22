#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "references" / "nvwa" / "output" / "transcript_extract.jsonl"
DEFAULT_OUT_DIR = ROOT / "references" / "nvwa" / "aggregate"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def output(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("output")
    return value if isinstance(value, dict) else {}


def metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata")
    return value if isinstance(value, dict) else {}


def should_exclude_from_core(row: dict[str, Any]) -> bool:
    curation = row.get("curation")
    return isinstance(curation, dict) and curation.get("exclude_from_core_aggregation") is True


def clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    return "" if text == "无" else text


def clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = clean_text(item)
        if text:
            items.append(text)
    return items


def top_counter(values: list[str], top_n: int = 40) -> list[tuple[str, int]]:
    return Counter(values).most_common(top_n)


def content_type_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(clean_text(metadata(row).get("content_type")) or "unknown" for row in rows)
    return dict(sorted(counts.items()))


def render_header(title: str, source: Path, rows: list[dict[str, Any]], total_rows: int) -> list[str]:
    return [
        f"# {title}",
        "",
        f"- Source: `{source}`",
        f"- Total Records: `{total_rows}`",
        f"- Included Here: `{len(rows)}`",
        f"- Content Types: `{json.dumps(content_type_counts(rows), ensure_ascii=False)}`",
        "",
    ]


def append_counter_section(lines: list[str], title: str, values: list[str], top_n: int = 40) -> None:
    lines.append(f"## {title}")
    lines.append("")
    pairs = top_counter(values, top_n=top_n)
    if not pairs:
        lines.append("- 空")
    for text, count in pairs:
        lines.append(f"- {text}: `{count}`")
    lines.append("")


def append_numbered_section(lines: list[str], title: str, values: list[str], limit: int = 80) -> None:
    lines.append(f"## {title}")
    lines.append("")
    items = [item for item in values if item][:limit]
    if not items:
        lines.append("1. 空")
    for idx, text in enumerate(items, 1):
        lines.append(f"{idx}. {text}")
    lines.append("")


def row_label(row: dict[str, Any]) -> str:
    out = output(row)
    task_id = clean_text(row.get("task_id"))
    title = clean_text(out.get("title"))
    content_type = clean_text(metadata(row).get("content_type")) or "unknown"
    if title:
        return f"{task_id} [{content_type}] {title}"
    return f"{task_id} [{content_type}]"


def build_core_ideas(rows: list[dict[str, Any]], total_rows: int, source: Path, out_path: Path) -> None:
    reframes: list[str] = []
    decision_rules: list[str] = []
    action_rules: list[str] = []
    quotes: list[str] = []
    source_rows: list[str] = []

    for row in rows:
        out = output(row)
        reframe = clean_text(out.get("host_reframe"))
        if reframe:
            reframes.append(reframe)
            source_rows.append(row_label(row))
        decision_rules.extend(clean_list(out.get("decision_rules")))
        action_rules.extend(clean_list(out.get("action_rules")))
        quotes.extend(clean_list(out.get("evidence_quotes")))

    lines = render_header("核心观点聚合", source, rows, total_rows)
    lines.append("说明：本文件默认排除 `curation.exclude_from_core_aggregation=true` 的记录。")
    lines.append("")
    append_numbered_section(lines, "问题重构 Host Reframe", reframes, limit=120)
    append_counter_section(lines, "高频判断规则 Decision Rules", decision_rules)
    append_counter_section(lines, "高频行动建议 Action Rules", action_rules)
    append_numbered_section(lines, "关键证据原话 Evidence Quotes", quotes, limit=120)
    append_numbered_section(lines, "Reframe 来源记录", source_rows, limit=120)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_case_scenarios(rows: list[dict[str, Any]], total_rows: int, source: Path, out_path: Path) -> None:
    case_rows = [row for row in rows if clean_text(metadata(row).get("content_type")) == "fan_call_case"]
    summaries: list[str] = []
    constraints: list[str] = []
    questions: list[str] = []
    titles: list[str] = []

    for row in case_rows:
        out = output(row)
        summary = clean_text(out.get("case_summary"))
        question = clean_text(out.get("core_question"))
        title = clean_text(out.get("title"))
        if summary:
            summaries.append(f"{row_label(row)}：{summary}")
        if question:
            questions.append(question)
        if title:
            titles.append(title)
        constraints.extend(clean_list(out.get("case_constraints")))

    lines = render_header("案例场景聚合", source, case_rows, total_rows)
    append_counter_section(lines, "高频客观限制 Case Constraints", constraints)
    append_counter_section(lines, "高频标题问题", titles)
    append_numbered_section(lines, "核心问题 Core Questions", questions, limit=160)
    append_numbered_section(lines, "案例摘要 Case Summaries", summaries, limit=160)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_expression_dna(rows: list[dict[str, Any]], total_rows: int, source: Path, out_path: Path) -> None:
    style_tags: list[str] = []
    catchphrases: list[str] = []
    hooks: list[str] = []

    for row in rows:
        out = output(row)
        style_tags.extend(clean_list(out.get("style_tags")))
        catchphrases.extend(clean_list(out.get("catchphrases")))
        hook = clean_text(out.get("hook_text"))
        if hook:
            hooks.append(f"{row_label(row)}：{hook}")

    lines = render_header("表达 DNA 聚合", source, rows, total_rows)
    append_counter_section(lines, "高频风格标签 Style Tags", style_tags)
    append_counter_section(lines, "高频口头禅 Catchphrases", catchphrases)
    append_numbered_section(lines, "开场钩子 Hook Text", hooks, limit=120)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_catchphrases(rows: list[dict[str, Any]], total_rows: int, source: Path, out_path: Path) -> None:
    entries: list[str] = []
    flat: list[str] = []
    for row in rows:
        phrases = clean_list(output(row).get("catchphrases"))
        if not phrases:
            continue
        flat.extend(phrases)
        entries.append(f"{row_label(row)}：{'；'.join(phrases)}")

    lines = render_header("口头禅与句式库", source, rows, total_rows)
    append_counter_section(lines, "高频短语", flat, top_n=80)
    append_numbered_section(lines, "按记录展开", entries, limit=180)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_low_priority_archive(rows: list[dict[str, Any]], total_rows: int, source: Path, out_path: Path) -> None:
    lines = render_header("低优先级归档", source, rows, total_rows)
    lines.append("说明：这些记录不进入核心观点聚合，可作为直播通知、日常、人设和运营表达素材。")
    lines.append("")
    for row in rows:
        out = output(row)
        curation = row.get("curation") if isinstance(row.get("curation"), dict) else {}
        lines.append(f"- {row_label(row)}")
        reason = clean_text(curation.get("reason"))
        hook = clean_text(out.get("hook_text"))
        if reason:
            lines.append(f"  - reason: `{reason}`")
        if hook:
            lines.append(f"  - hook: {hook}")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_summary(
    rows: list[dict[str, Any]],
    included: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    files: list[Path],
    out_path: Path,
) -> None:
    summary = {
        "ok": True,
        "total_records": len(rows),
        "included_core_records": len(included),
        "excluded_low_priority_records": len(excluded),
        "content_type_all": content_type_counts(rows),
        "content_type_included": content_type_counts(included),
        "content_type_excluded": content_type_counts(excluded),
        "files": [str(path) for path in files],
    }
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate cleaned-md extraction JSONL into reviewable markdown files")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input transcript_extract.jsonl path")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory")
    parser.add_argument(
        "--include-low-priority-in-core",
        action="store_true",
        help="Do not filter curation.exclude_from_core_aggregation records from core aggregate outputs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(input_path)
    excluded = [row for row in rows if should_exclude_from_core(row)]
    included = rows if args.include_low_priority_in_core else [row for row in rows if not should_exclude_from_core(row)]

    files = [
        out_dir / "core_ideas.md",
        out_dir / "case_scenarios.md",
        out_dir / "expression_dna.md",
        out_dir / "catchphrases.md",
        out_dir / "low_priority_archive.md",
        out_dir / "aggregate_summary.json",
    ]

    build_core_ideas(included, len(rows), input_path, files[0])
    build_case_scenarios(included, len(rows), input_path, files[1])
    build_expression_dna(included, len(rows), input_path, files[2])
    build_catchphrases(included, len(rows), input_path, files[3])
    build_low_priority_archive(excluded, len(rows), input_path, files[4])
    build_summary(rows, included, excluded, files[:-1], files[5])

    result = {
        "ok": True,
        "input": str(input_path),
        "out_dir": str(out_dir),
        "total_records": len(rows),
        "included_core_records": len(included),
        "excluded_low_priority_records": len(excluded),
        "files": [str(path) for path in files],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
