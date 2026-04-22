#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLEANED_DIR = ROOT / "references" / "sources" / "transcripts" / "cleaned-md"
DEFAULT_OUTPUT_DIR = ROOT / "references" / "nvwa"
SAMPLE_FILENAME = "transcript_extract_sample_30.jsonl"

PROMOTION_KEYWORDS = (
    "下单",
    "购买",
    "链接",
    "课程",
    "签名",
    "福利",
    "发售",
    "礼物",
    "青春水乳",
    "好物",
    "优惠",
)
DAILY_LIFE_KEYWORDS = (
    "vlog",
    "出差",
    "请一天假",
    "宝宝",
    "生活",
    "日常",
    "回归直播",
)
QUESTION_KEYWORDS = (
    "怎么办",
    "该不该",
    "要不要",
    "还能",
    "怎么做",
    "适合",
    "如何",
    "有没有必要",
    "继续吗",
)
OPINION_KEYWORDS = (
    "建议",
    "记住",
    "一定要",
    "逻辑",
    "规律",
    "判断",
    "提醒",
    "我想告诉",
)
TITLE_INTENT_KEYWORDS = (
    "怎么办",
    "该不该",
    "要不要",
    "适合",
    "建议",
    "分享",
    "回归",
    "高考",
    "旗开得胜",
    "祝",
)
TRANSCRIPT_SIGNAL_KEYWORDS = (
    "我",
    "你",
    "他",
    "她",
    "我们",
    "你们",
    "他们",
    "老公",
    "老婆",
    "男友",
    "女友",
    "孩子",
    "结婚",
    "离婚",
    "工作",
    "生活",
    "关系",
    "因为",
    "所以",
    "就是",
    "如果",
)

CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
ASCII_ALPHA_RE = re.compile(r"[A-Za-z]")


def parse_cleaned_md(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    title_match = re.search(r"^#\s+(.+)$", text, re.M)
    seq_match = re.search(r"^- No：(\d+)\s*$", text, re.M)
    aweme_match = re.search(r"^- aweme_id：(.*)$", text, re.M)
    create_time_match = re.search(r"^- create_time：(.*)$", text, re.M)
    item_title_match = re.search(r"^- item_title：(.*)$", text, re.M)
    source_path_match = re.search(r"^- source_path：(.*)$", text, re.M)
    transcript_match = re.search(
        r"## Cleaned Transcript\s*(.*?)\s*## Segment References",
        text,
        re.S,
    )
    cleaned_transcript = transcript_match.group(1).strip() if transcript_match else ""
    return {
        "seq": int(seq_match.group(1)) if seq_match else 0,
        "title": title_match.group(1).strip() if title_match else path.stem,
        "aweme_id": aweme_match.group(1).strip() if aweme_match else "",
        "create_time": create_time_match.group(1).strip() if create_time_match else "",
        "item_title": item_title_match.group(1).strip() if item_title_match else "",
        "source_path": source_path_match.group(1).strip() if source_path_match else "",
        "cleaned_transcript": cleaned_transcript,
    }


def pick_topic_hints(title: str, transcript: str) -> list[str]:
    raw = re.split(r"[，。！？；、\s#]+", f"{title} {transcript[:120]}")
    hints: list[str] = []
    for token in raw:
        token = token.strip()
        if len(token) < 2:
            continue
        if token in {"龙飞", "姐妹们", "大家", "这个", "那个"}:
            continue
        if token not in hints:
            hints.append(token)
        if len(hints) == 5:
            break
    return hints


def detect_anomaly_flags(title: str, transcript: str) -> list[str]:
    flags: list[str] = []
    stripped = transcript.strip()
    if not stripped:
        flags.append("empty_transcript")
        return flags

    chinese_count = len(CHINESE_CHAR_RE.findall(stripped))
    ascii_count = len(ASCII_ALPHA_RE.findall(stripped))
    unique_chars = len(set(stripped))
    length = len(stripped)
    signal_hits = sum(1 for keyword in TRANSCRIPT_SIGNAL_KEYWORDS if keyword in stripped)
    title_intent = any(keyword in title for keyword in TITLE_INTENT_KEYWORDS)
    paragraph_count = len([part for part in stripped.split("\n\n") if part.strip()])

    if ascii_count > chinese_count * 2 and ascii_count > 40:
        flags.append("non_chinese_lyrics")
    if chinese_count < 20 and length < 120:
        flags.append("low_semantic_density")
    if unique_chars < 30 and length > 80:
        flags.append("high_repetition")
    if title_intent and signal_hits <= 1 and length < 180:
        flags.append("title_body_mismatch")
    if signal_hits == 0 and chinese_count > 20 and length < 160:
        flags.append("lyric_like_content")
    if paragraph_count >= 4 and length < 160 and signal_hits <= 2:
        flags.append("lyric_like_content")
    if any(keyword in title for keyword in QUESTION_KEYWORDS) and not any(
        keyword in stripped for keyword in QUESTION_KEYWORDS
    ):
        flags.append("title_body_mismatch")
    return sorted(set(flags))


def classify_content(title: str, transcript: str) -> str:
    haystack = f"{title}\n{transcript}"
    if any(keyword in haystack for keyword in PROMOTION_KEYWORDS):
        return "promotion"
    if any(keyword in haystack for keyword in QUESTION_KEYWORDS):
        return "fan_call_case"
    if any(keyword in haystack for keyword in OPINION_KEYWORDS):
        return "opinion_monologue"
    if any(keyword.lower() in haystack.lower() for keyword in DAILY_LIFE_KEYWORDS):
        return "daily_life"
    return "opinion_monologue"


def primary_targets_for(content_type: str) -> list[str]:
    if content_type == "fan_call_case":
        return ["02-conversations", "03-expression-dna", "05-decisions"]
    if content_type == "opinion_monologue":
        return ["02-conversations", "03-expression-dna", "05-decisions"]
    if content_type == "daily_life":
        return ["03-expression-dna", "06-timeline"]
    return ["03-expression-dna"]


def value_level_for(content_type: str) -> str:
    if content_type in {"fan_call_case", "opinion_monologue"}:
        return "high"
    if content_type == "daily_life":
        return "medium"
    return "low"


def score_record(record: dict) -> tuple[int, int]:
    weight = {"high": 0, "medium": 1, "low": 2}[record["value_level"]]
    return (weight, record["seq"])


def build_index(cleaned_dir: Path, output_dir: Path, sample_size: int = 30) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    samples_dir = output_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    for path in sorted(cleaned_dir.glob("*.md")):
        if path.name in {"README.md", "manifest.json"}:
            continue
        parsed = parse_cleaned_md(path)
        content_type = classify_content(parsed["title"], parsed["cleaned_transcript"])
        try:
            source_path = str(path.relative_to(ROOT))
        except ValueError:
            source_path = str(path)
        record = {
            "seq": parsed["seq"],
            "title": parsed["title"],
            "aweme_id": parsed["aweme_id"],
            "create_time": parsed["create_time"],
            "source_path": source_path,
            "upstream_source_path": parsed["source_path"],
            "content_type": content_type,
            "primary_targets": primary_targets_for(content_type),
            "value_level": value_level_for(content_type),
            "topic_hints": pick_topic_hints(parsed["title"], parsed["cleaned_transcript"]),
            "anomaly_flags": detect_anomaly_flags(parsed["title"], parsed["cleaned_transcript"]),
            "question_like": content_type == "fan_call_case",
            "transcript_char_count": len(parsed["cleaned_transcript"]),
            "transcript_preview": parsed["cleaned_transcript"][:180],
        }
        record["needs_review"] = bool(record["anomaly_flags"])
        records.append(record)

    index_path = output_dir / "transcript_index.jsonl"
    index_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + ("\n" if records else ""),
        encoding="utf-8",
    )

    samples = sorted(records, key=score_record)[:sample_size]
    sample_path = samples_dir / SAMPLE_FILENAME
    sample_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in samples) + ("\n" if samples else ""),
        encoding="utf-8",
    )

    counts = Counter(record["content_type"] for record in records)
    try:
        index_path_value = str(index_path.relative_to(ROOT))
    except ValueError:
        index_path_value = str(index_path)
    try:
        sample_path_value = str(sample_path.relative_to(ROOT))
    except ValueError:
        sample_path_value = str(sample_path)
    return {
        "count": len(records),
        "sample_count": len(samples),
        "index_path": index_path_value,
        "sample_path": sample_path_value,
        "content_type_counts": dict(counts),
    }


def main() -> None:
    result = build_index(DEFAULT_CLEANED_DIR, DEFAULT_OUTPUT_DIR)
    print(
        json.dumps(
            {
                "ok": True,
                "count": result["count"],
                "sample_count": result["sample_count"],
                "index_path": result["index_path"],
                "sample_path": result["sample_path"],
                "content_type_counts": result["content_type_counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
