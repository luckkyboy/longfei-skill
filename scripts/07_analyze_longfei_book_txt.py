#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "references" / "sources" / "books" / "txt" / "Ba Ri Zi Guo Ming Bai - Long Fei Lu Shi.txt"
DEFAULT_OUTPUT = ROOT / "skills" / "longfei-lawyer-perspective" / "references" / "research" / "01a-book-txt-analysis.md"

CHAPTER_RE = re.compile(r"^(0[1-7])\s+(.+)$")
KEYWORDS = [
    "先谋生", "谋爱", "财产", "彩礼", "婚前财产", "婚前财产协议", "护城河",
    "共同债务", "证据", "出轨", "忠诚协议", "怀孕", "生育权", "终止妊娠",
    "独立", "界限感", "原生家庭", "身体", "情绪稳定", "安全措施", "及时止损",
    "底气", "面包", "风险", "协议", "房产", "加名字", "全职太太",
]
THEMES = {
    "生存与选择权": ["先谋生", "谋爱", "底气", "面包", "养活自己", "选择的权利"],
    "婚前识人与筛选": ["原生家庭", "价值观", "金钱观", "情绪稳定", "共同生活", "远嫁"],
    "财产护城河": ["财产", "婚前财产", "婚前财产协议", "护城河", "房产", "加名字", "租金"],
    "彩礼风险": ["彩礼", "彩礼陷阱", "实物彩礼", "现金彩礼", "债务彩礼"],
    "身体与生育自主": ["身体", "怀孕", "生育权", "终止妊娠", "安全措施", "亲密关系"],
    "证据与协议": ["证据", "录音", "聊天记录", "视频", "协议", "夫妻财产约定书"],
    "婚姻危机处置": ["出轨", "第三者", "背叛", "忠诚协议", "离婚", "赶紧逃"],
    "独立个体与边界": ["独立的个体", "界限感", "娘家", "丈夫", "孩子", "自己的人生"],
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def content_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    start = 0
    for idx, line in enumerate(lines):
        if line.startswith("婚前篇"):
            start = idx
            break
    return lines[start:]


def split_chapters(lines: list[str]) -> list[tuple[str, str, list[str]]]:
    chapters: list[tuple[str, str, list[str]]] = []
    current_no = ""
    current_title = ""
    current_lines: list[str] = []
    for line in lines:
        match = CHAPTER_RE.match(line)
        if match:
            no, title = match.groups()
            if no in {"01", "02", "03", "04", "05", "06", "07"}:
                if current_no:
                    chapters.append((current_no, current_title, current_lines))
                current_no = no
                current_title = title.strip()
                current_lines = []
                continue
        if current_no:
            current_lines.append(line)
    if current_no:
        chapters.append((current_no, current_title, current_lines))
    # The txt contains a front table of contents and then real chapters. Keep the second set.
    if len(chapters) > 7:
        chapters = chapters[-7:]
    return chapters


def keyword_counts(text: str) -> dict[str, int]:
    return {keyword: text.count(keyword) for keyword in KEYWORDS if text.count(keyword)}


def theme_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for theme, words in THEMES.items():
        counts[theme] = sum(text.count(word) for word in words)
    return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))


def representative_sentences(text: str, keyword: str, limit: int = 3) -> list[str]:
    normalized = re.sub(r"\s+", " ", text)
    chunks = re.split(r"(?<=[。！？])", normalized)
    hits: list[str] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if keyword in chunk and 20 <= len(chunk) <= 180:
            hits.append(chunk)
            if len(hits) >= limit:
                break
    return hits


def top_terms(text: str) -> list[tuple[str, int]]:
    words = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
    stop = {"我们", "自己", "什么", "如果", "因为", "所以", "一个", "这个", "那个", "可以", "没有", "时候", "进行", "就是", "不是", "但是", "需要", "对方", "丈夫", "婚姻", "女性"}
    return Counter(w for w in words if w not in stop).most_common(40)


def render(input_path: Path, output_path: Path) -> dict[str, object]:
    text = read_text(input_path)
    lines = content_lines(text)
    chapters = split_chapters(lines)
    body = "\n".join(lines)
    lines_out: list[str] = []
    lines_out.extend([
        "# 01a-book-txt-analysis · 《把日子过明白》全文结构化分析",
        "",
        f"- Source: `{input_path}`",
        f"- Characters: `{len(text)}`",
        f"- Content Lines: `{len(lines)}`",
        f"- Chapters Detected: `{len(chapters)}`",
        "- Source Type: 私有本地 txt；输出不包含原文摘句",
        "- Copyright Policy: 因版权原因不提供书籍原文，不提供长段摘录。",
        "",
        "## 全书结构",
        "",
    ])
    for no, title, chapter_lines in chapters:
        chapter_text = "\n".join(chapter_lines)
        lines_out.append(f"- {no} {title}: `{len(chapter_text)}` chars")
    lines_out.append("")

    lines_out.append("## 主题强度")
    lines_out.append("")
    for theme, count in theme_counts(body).items():
        lines_out.append(f"- {theme}: `{count}`")
    lines_out.append("")

    lines_out.append("## 关键词计数")
    lines_out.append("")
    for keyword, count in sorted(keyword_counts(body).items(), key=lambda item: item[1], reverse=True):
        lines_out.append(f"- {keyword}: `{count}`")
    lines_out.append("")

    lines_out.append("## 逐章提炼")
    lines_out.append("")
    for no, title, chapter_lines in chapters:
        chapter_text = "\n".join(chapter_lines)
        lines_out.append(f"### {no} {title}")
        lines_out.append("")
        top = sorted(keyword_counts(chapter_text).items(), key=lambda item: item[1], reverse=True)[:10]
        if top:
            lines_out.append("**高频信号**：" + "；".join(f"{k}({v})" for k, v in top))
            lines_out.append("")
        chapter_themes = sorted(theme_counts(chapter_text).items(), key=lambda item: item[1], reverse=True)[:4]
        lines_out.append("**核心主题**：" + "；".join(f"{k}({v})" for k, v in chapter_themes if v))
        lines_out.append("")
        lines_out.append("**版权处理**：本节只保留关键词计数和抽象主题，不输出原文摘句。")
        lines_out.append("")
    lines_out.append("## 适合并入 Skill 的增量结论")
    lines_out.append("")
    lines_out.extend([
        "- 《把日子过明白》把龙飞的直播判断系统化为 7 个模块：爱情观、彩礼、婚前财产、人身安全、情感问题、财产问题、婚姻危机。",
        "- 书中最强的系统性母题不是单纯‘搞钱’，而是‘女性要先拥有谋生能力，才能拥有选择权’。",
        "- 法律工具在书里承担的是‘护城河’功能：婚前财产协议、夫妻财产约定书、证据、转账、房产登记、共同债务识别。",
        "- 书籍表达比直播更温和，更强调善意、自我教育、情绪稳定、独立个体；skill 不应只保留直播切片的犀利。",
        "- 婚姻危机部分将‘背叛’处理为证据、财产、第三者转账、离婚标准和安全退出问题，和 transcript 聚合中的现实主义判断互相印证。",
        "",
        "## 高频中文词组",
        "",
    ])
    for term, count in top_terms(body):
        lines_out.append(f"- {term}: `{count}`")
    lines_out.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines_out), encoding="utf-8")
    return {
        "ok": True,
        "input": str(input_path),
        "output": str(output_path),
        "characters": len(text),
        "content_lines": len(lines),
        "chapters": len(chapters),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Long Fei's book txt for nvwa skill research")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = render(Path(args.input), Path(args.output))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
