#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "references" / "nvwa" / "output" / "transcript_extract.jsonl"
DEFAULT_REPORT = ROOT / "references" / "nvwa" / "output" / "transcript_extract.validation_report.md"
DEFAULT_SUMMARY = ROOT / "references" / "nvwa" / "output" / "transcript_extract.validation_summary.json"

ALLOWED_CONFIDENCE = {"low", "medium", "high"}
HOST_REFRAME_ENABLED_CONTENT_TYPES = {"fan_call_case", "opinion_monologue"}

TASK_ID_RE = re.compile(r"^transcript-extract-\d{4}$")

OUTPUT_REQUIRED_FIELDS = [
    "episode_id",
    "title",
    "create_time",
    "source_path",
    "hook_text",
    "case_summary",
    "case_constraints",
    "core_question",
    "host_reframe",
    "decision_rules",
    "action_rules",
    "catchphrases",
    "style_tags",
    "evidence_quotes",
    "timestamp_refs",
    "confidence",
]

OUTPUT_ARRAY_FIELDS = [
    "case_constraints",
    "decision_rules",
    "action_rules",
    "catchphrases",
    "style_tags",
    "evidence_quotes",
    "timestamp_refs",
]

OUTPUT_STRING_FIELDS = [
    "episode_id",
    "title",
    "create_time",
    "source_path",
    "hook_text",
    "case_summary",
    "core_question",
    "host_reframe",
    "confidence",
]


@dataclass
class Issue:
    line: int
    kind: str
    detail: str


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[Issue]]:
    records: list[dict[str, Any]] = []
    issues: list[Issue] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            issues.append(Issue(line_no, "blank_line", "Blank line in JSONL"))
            continue
        try:
            records.append(json.loads(line))
        except Exception as exc:  # noqa: BLE001
            issues.append(Issue(line_no, "invalid_json", str(exc)))
    return records, issues


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _check_required_keys(container: dict[str, Any], required: list[str], prefix: str, line: int) -> list[Issue]:
    out: list[Issue] = []
    for key in required:
        if key not in container:
            out.append(Issue(line, f"{prefix}.missing_key", key))
    return out


def validate_record(record: dict[str, Any], line: int) -> list[Issue]:
    issues: list[Issue] = []

    issues.extend(_check_required_keys(record, ["task_id", "model", "metadata", "output"], "top", line))
    task_id = record.get("task_id")
    if not isinstance(task_id, str):
        issues.append(Issue(line, "top.task_id_type", f"type={type(task_id).__name__}"))
    elif not TASK_ID_RE.match(task_id):
        issues.append(Issue(line, "top.task_id_format", task_id))

    metadata = record.get("metadata")
    output = record.get("output")
    if not isinstance(metadata, dict):
        issues.append(Issue(line, "top.metadata_type", f"type={type(metadata).__name__}"))
        return issues
    if not isinstance(output, dict):
        issues.append(Issue(line, "top.output_type", f"type={type(output).__name__}"))
        return issues

    issues.extend(_check_required_keys(output, OUTPUT_REQUIRED_FIELDS, "output", line))

    extra_output_keys = sorted(set(output) - set(OUTPUT_REQUIRED_FIELDS))
    if extra_output_keys:
        issues.append(Issue(line, "output.extra_keys", f"value={extra_output_keys!r}"))

    confidence = output.get("confidence")
    if confidence not in ALLOWED_CONFIDENCE:
        issues.append(Issue(line, "output.confidence_enum", f"value={confidence!r}"))

    for field in OUTPUT_ARRAY_FIELDS:
        value = output.get(field)
        if not _is_str_list(value):
            issues.append(Issue(line, f"output.{field}_type", f"type={type(value).__name__}"))

    for field in OUTPUT_STRING_FIELDS:
        value = output.get(field)
        if not isinstance(value, str):
            issues.append(Issue(line, f"output.{field}_type", f"type={type(value).__name__}"))

    if len(output.get("evidence_quotes", [])) > 8:
        issues.append(Issue(line, "output.evidence_quotes_count", f"value={len(output.get('evidence_quotes', []))}"))

    content_type = metadata.get("content_type")
    if content_type not in HOST_REFRAME_ENABLED_CONTENT_TYPES and output.get("host_reframe") != "":
        issues.append(
            Issue(
                line,
                "output.host_reframe_for_non_analysis_content",
                f"content_type={content_type!r}, host_reframe={output.get('host_reframe')!r}",
            )
        )

    return issues


def build_report(
    source_path: Path,
    records: list[dict[str, Any]],
    issues: list[Issue],
    report_path: Path,
    summary_path: Path,
) -> None:
    issue_counter = Counter(item.kind for item in issues)
    by_kind_lines: dict[str, list[Issue]] = defaultdict(list)
    for item in issues:
        by_kind_lines[item.kind].append(item)

    task_ids = [record.get("task_id") for record in records if isinstance(record.get("task_id"), str)]
    dup_task_ids = [task_id for task_id, count in Counter(task_ids).items() if count > 1]

    confidence_counter = Counter()
    model_counter = Counter()
    manual_records = []
    for record in records:
        model_counter.update([record.get("model")])
        if isinstance(record.get("raw_response"), dict) and record["raw_response"].get("manual"):
            manual_records.append(record.get("task_id"))
        output = record.get("output", {})
        if not isinstance(output, dict):
            continue
        confidence_counter.update([output.get("confidence")])

    strict_pass = len(issues) == 0 and not dup_task_ids

    lines: list[str] = []
    lines.append("# transcript_extract 严格校验报告")
    lines.append("")
    lines.append(f"- Source: `{source_path}`")
    lines.append(f"- Total Records: `{len(records)}`")
    lines.append(f"- Strict Result: `{'PASS' if strict_pass else 'FAIL'}`")
    lines.append(f"- Total Issues: `{len(issues)}`")
    lines.append(f"- Duplicate task_id: `{len(dup_task_ids)}`")
    lines.append(f"- Manual Records: `{len(manual_records)}`")
    lines.append("")
    lines.append("## 规则统计")
    lines.append("")
    if issue_counter:
        for kind, count in issue_counter.most_common():
            lines.append(f"- `{kind}`: `{count}`")
    else:
        lines.append("- 无")
    lines.append("")
    lines.append("## 样本问题（每类最多 5 条）")
    lines.append("")
    if issue_counter:
        for kind, _ in issue_counter.most_common():
            lines.append(f"### {kind}")
            for item in by_kind_lines[kind][:5]:
                lines.append(f"- line `{item.line}`: {item.detail}")
            lines.append("")
    else:
        lines.append("- 无")
        lines.append("")
    lines.append("## 分布概览")
    lines.append("")
    lines.append(f"- confidence: `{dict(confidence_counter)}`")
    lines.append(f"- model: `{dict(model_counter)}`")
    lines.append(f"- manual_records: `{manual_records}`")
    lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "source": str(source_path),
        "total_records": len(records),
        "strict_result": "PASS" if strict_pass else "FAIL",
        "total_issues": len(issues),
        "issue_count_by_rule": dict(issue_counter),
        "duplicate_task_id_count": len(dup_task_ids),
        "duplicate_seq_count": 0,
        "duplicate_task_ids": dup_task_ids,
        "duplicate_seqs": [],
        "manual_records": manual_records,
        "distribution": {
            "confidence": dict(confidence_counter),
            "model": dict(model_counter),
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strict validator for transcript_extract.jsonl")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input JSONL path")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="Markdown report output path")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY), help="JSON summary output path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    report_path = Path(args.report)
    summary_path = Path(args.summary)

    records, issues = load_jsonl(input_path)
    all_issues = list(issues)
    for line_no, record in enumerate(records, 1):
        all_issues.extend(validate_record(record, line_no))

    build_report(
        source_path=input_path,
        records=records,
        issues=all_issues,
        report_path=report_path,
        summary_path=summary_path,
    )

    result = {
        "ok": True,
        "input": str(input_path),
        "records": len(records),
        "issues": len(all_issues),
        "report": str(report_path),
        "summary": str(summary_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
