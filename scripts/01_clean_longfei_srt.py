#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path


CN_TZ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[1]


@dataclass
class SrtEntry:
    index: int
    start: str
    end: str
    text: str


@dataclass
class ExistingTranscriptMeta:
    seq: int
    title: str
    aweme_id: str
    created_display: str
    output_file: str
    source_file: str
    segment_count: int


REPLACEMENTS = [
    ("直播太货", "直播带货"),
    ("太货", "带货"),
    ("龙菲", "龙飞"),
    ("龙飞士", "龙飞律师"),
    ("龙龙飞姐", "龙飞姐"),
    ("龙龙飞姐姐", "龙飞姐姐"),
    ("罗菲姐", "龙飞姐"),
    ("王菲姐", "龙飞姐"),
    ("王菲姐姐", "龙飞姐姐"),
    ("萌菲姐", "龙飞姐"),
    ("老菲姐", "龙飞姐"),
    ("老飞姐", "龙飞姐"),
    ("价装", "嫁妆"),
    ("宠祖家庭", "重组家庭"),
    ("智青智爱", "至亲至爱"),
    ("到囚翻脸", "到时候翻脸"),
    ("筹划说在前面", "丑话说在前面"),
    ("亲兄弟您算帐", "亲兄弟明算账"),
    ("亲兄弟您算账", "亲兄弟明算账"),
    ("平方是", "情况是"),
    ("网败", "网贷"),
    ("复类", "拖累"),
    ("私起", "私企"),
    ("大肺", "大病"),
    ("不生女儿", "不是独女"),
    ("依看你", "一看你"),
    ("人家依看你", "人家一看你"),
    ("没有助理", "没有助力"),
    ("问问摆他", "外面摆摊"),
    ("我跟我舒服之后", "我跟我继父之后"),
    ("一架到了四川", "嫁到了四川"),
    ("手机好奇", "手机号"),
    ("头同身边要同", "头痛身边腰痛"),
    ("淡魔", "淡漠"),
    ("复债", "负债"),
    ("陆续续", "陆陆续续"),
    ("房带", "房贷"),
    ("车带", "车贷"),
    ("课课器器", "客客气气"),
    ("效盡", "孝敬"),
    ("爱折", "癌症"),
    ("艳女", "厌女"),
    ("离官", "离婚"),
    ("伸存", "生存"),
    ("没设", "你给"),
    ("既建", "寄件"),
    ("既个", "寄个"),
    ("隐食", "饮食"),
    ("儀式感", "仪式感"),
    ("白质黑歌", "白纸黑字"),
    ("在圈也可以的是吗", "再签也可以的是吗"),
    ("一带款", "一笔贷款"),
    ("读充一个情况", "补充一个情况"),
    ("复完了", "付完了"),
    ("娘在", "娘家"),
    ("人未婚", "仍未婚"),
    ("西鞋", "心结"),
    ("父父亲", "父亲"),
    ("父父母", "父母"),
    ("生理心里", "生理心理"),
    ("偷顶", "秃顶"),
    ("把门", "部门"),
    ("把门", "把门"),
    ("连系", "联系"),
]

REGEX_REPLACEMENTS = [
    (r"很帅的时候啊", "坦率地说啊"),
    (r"表演出啊", "表演啊"),
    (r"我不跟父母在接触了", "我不跟父母再接触了"),
    (r"我跟父母已经隔有几个月没有再联系了", "我跟父母已经得有几个月没有再联系了"),
    (r"该赦免打扰就赦免打扰", "该设置免打扰就设置免打扰"),
    (r"该设免打扰就设免打扰", "该设置免打扰就设置免打扰"),
    (r"给我到一些进遇", "给我到一些建议"),
    (r"学生生源资源感好", "学生生源资源。好"),
    (r"无条件的去少", "无条件的居少"),
    (r"市值的事业编", "市直的事业编"),
    (r"他提你的时候", "他亲你的时候"),
    (r"得选一个防能力强的", "得选一个防范能力强的"),
    (r"跟他在接触过程当中", "跟他接触过程当中"),
    (r"后面跟他在接触的时候", "后面跟他接触的时候"),
    (r"在我的父母去北京玩一趟", "带我的父母去北京玩一趟"),
    (r"在家里面进行看书", "在家里面静静看书"),
    (r"不去备爱别人的能力", "不具备爱别人的能力"),
    (r"回来关起处好", "回来关系处好"),
    (r"导师比较自由一些", "但是比较自由一些"),
    (r"坏事谈间里", "坏事传千里"),
    (r"刚接一年就离的", "刚结一年就离的"),
    (r"有打庭那个啥就Q续续就打打打那个啥", "有家庭暴力，就持续打那个啥"),
    (r"被厌女长", "被厌女伤害"),
    (r"我是95年的,?现在31岁了我最少是910年的,?35岁", "我是95年的，现在31岁了。我对象是91年的，35岁"),
    (r"做过太减", "做过探店"),
    (r"现在的话就推起了,?下到了5到6000", "现在的话就掉到了五到六千"),
    (r"还尽量犯工作", "还经常换工作"),
    (r"明天差不多有工作12个小时", "每天差不多要工作12个小时"),
    (r"吃大病从那个河北出来之后", "自打我从那个河北出来之后"),
    (r"来四川也有个大小年了", "来四川也有个大概小两年了"),
    (r"最像的父母的话", "对象的父母的话"),
    (r"我跟我继父之后", "我跟我妈嫁到四川之后"),
    (r"有血人关系", "有血缘关系"),
    (r"舒塌", "舒坦"),
    (r"可吃换", "可置换"),
    (r"酒并床前都无效", "久病床前都无孝子"),
    (r"领步的话", "难听的话"),
    (r"经历过的扣移", "经历过的可以理解"),
    (r"文静静", "问清清"),
    (r"劳力几合", "劳逸结合"),
    (r"清腔面", "清汤面"),
    (r"给了我没有别的意思", "这个我没有别的意思"),
    (r"多么借款", "对外借款"),
    (r"夫妻协议", "夫妻财产协议"),
    (r"时间的关系", "之间的关系"),
    (r"这有一比([一二三四五六七八九十0-9两]+)百万的个人债务", r"这有一笔\1百万的个人债务"),
    (r"是需要在五年之内烦心的", "是需要在五年之内还清的"),
    (r"为了利益到时候翻脸的这种至亲至爱", "为了利益到时候翻脸的这种至亲至爱"),
    (r"来尝换这笔婚前的债务", "来偿还这笔婚前的债务"),
    (r"这里昏迁", "这笔婚前"),
    (r"这里前您却为", "这笔钱明确为"),
    (r"出来的环待每个的利息", "出来的还贷每个月的利息"),
    (r"也都是我妈这边在环", "也都是我妈这边在还"),
    (r"那是你妈妈和她时间的关系", "那是你妈妈和她之间的关系"),
    (r"那就牵婚前才产协议", "那就签婚前财产协议"),
    (r"我家已经在我们大头的婚前还想都已经保全了", "我家已经把我们大头的婚前财产都已经保全了"),
    (r"去还这里婚前", "去还这笔婚前"),
    (r"被住手给她个人的借款", "备注是给她个人的借款"),
    (r"我对象像个人像我母亲的借款", "我对象向个人、向我母亲的借款"),
    (r"不被住借款", "不备注借款"),
    (r"对男的这么优秀吗", "这男的这么优秀吗"),
    (r"挡得像明星吗", "长得像明星吗"),
    (r"左上一亿亏老", "做生意亏了"),
    (r"去年还有十六万的负债没缓", "去年还有十六万的负债没还"),
    (r"吃药凝职不了", "吃药都止不了"),
    (r"三个直播带货才能这个18", "三个直播带货才能挣这个"),
    (r"三个直播带货才能挣这个9", "三个直播带货才能挣这个钱"),
    (r"200年前的话有个直到发钱", "之前的话有过直播带货"),
    (r"借钱协议", "夫妻财产协议"),
    (r"第二二十这样能不能停呢", "第二，这样能不能行呢"),
]

TRAILING_CTA_PHRASES = (
    "记得点赞关注哦",
    "你们记得点赞关注哦",
)


def slugify(text: str) -> str:
    text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120].strip()


def derive_title_from_source(source_file: Path) -> str:
    title = re.sub(r"\.(transcribe\.)?srt$", "", source_file.name)
    title = re.sub(r"^\d+_", "", title)
    return title.strip()


def normalize_match_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\.(transcribe\.)?srt$", "", text, flags=re.I)
    text = re.sub(r"^\d+[_-]", "", text)
    text = re.sub(r"#.*", "", text)
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
    text = re.sub(r"\s+", "", text)
    return text


def compact_match_text(text: str) -> str:
    text = normalize_match_text(text)
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", text)


def resolve_title(meta: dict, source_file: Path) -> str:
    source_title = derive_title_from_source(source_file)
    meta_title = (meta.get("item_title") or meta.get("desc") or "").strip()
    has_trusted_meta = bool(
        meta.get("aweme_id") or meta.get("create_time") or meta.get("create_time_display")
    )
    if meta_title and has_trusted_meta:
        return meta_title
    return source_title


def parse_srt(path: Path) -> list[SrtEntry]:
    raw = path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")
    blocks = re.split(r"\n\s*\n", raw.strip())
    entries: list[SrtEntry] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        idx_line = lines[0]
        ts_line = lines[1]
        text_lines = lines[2:]
        if "-->" not in ts_line:
            continue
        try:
            index = int(re.sub(r"\D", "", idx_line) or "0")
        except ValueError:
            index = 0
        start, end = [p.strip() for p in ts_line.split("-->")]
        text = " ".join(text_lines)
        text = re.sub(r"\s+", "", text)
        entries.append(SrtEntry(index=index, start=start, end=end, text=text))
    return entries


def clean_text(text: str) -> str:
    text = text.strip()
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    for pattern, repl in REGEX_REPLACEMENTS:
        text = re.sub(pattern, repl, text)

    text = text.replace("...", "……")
    text = re.sub(r"([，。！？；：、“”])\1+", r"\1", text)
    text = re.sub(r"([。！？；：])(?=[^\n])", r"\1", text)
    return text.strip()


def should_drop_trailing_entry(text: str) -> bool:
    cleaned = clean_text(text).rstrip("。！？；：，、 ")
    return any(phrase in cleaned for phrase in TRAILING_CTA_PHRASES)


def trim_trailing_cta(entries: list[SrtEntry]) -> list[SrtEntry]:
    trimmed = list(entries)
    while trimmed and should_drop_trailing_entry(trimmed[-1].text):
        trimmed.pop()
    return trimmed


def choose_source(files: list[Path]) -> Path:
    transcribed = [p for p in files if p.name.endswith(".transcribe.srt")]
    if transcribed:
        return sorted(transcribed)[0]
    return sorted(files)[0]


def build_posts_map(posts_json: Path) -> dict[str, dict]:
    data = json.loads(posts_json.read_text(encoding="utf-8", errors="ignore"))
    posts = data.get("posts", [])
    mapping: dict[str, dict] = {}
    for post in posts:
        item_title = (post.get("item_title") or post.get("desc") or "").strip()
        normalized = normalize_match_text(item_title)
        if not normalized:
            continue
        item = {
            "aweme_id": post.get("aweme_id", ""),
            "desc": post.get("desc", ""),
            "item_title": item_title,
            "create_time": post.get("create_time"),
        }
        mapping[normalized] = item
        compact = compact_match_text(item_title)
        if compact and compact not in mapping:
            mapping[compact] = item
    return mapping


def parse_existing_transcript(path: Path) -> ExistingTranscriptMeta | None:
    m = re.match(r"^(\d+)-", path.name)
    if not m:
        return None

    text = path.read_text(encoding="utf-8", errors="ignore")
    title_match = re.search(r"^#\s+(.+)$", text, re.M)
    aweme_match = re.search(r"^- aweme_id：(.*)$", text, re.M)
    created_match = re.search(r"^- 发布时间：(.*)$", text, re.M)
    source_match = re.search(r"^- 原始文件：(.*)$", text, re.M)
    segment_count = len(re.findall(r"^- `.*? --> .*?` ", text, re.M))

    return ExistingTranscriptMeta(
        seq=int(m.group(1)),
        title=title_match.group(1).strip() if title_match else path.stem,
        aweme_id=aweme_match.group(1).strip() if aweme_match else "",
        created_display=created_match.group(1).strip() if created_match else "",
        output_file=path.name,
        source_file=source_match.group(1).strip() if source_match else "",
        segment_count=segment_count,
    )


def build_existing_map(existing_dir: Path) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    if not existing_dir.exists():
        return mapping

    for path in sorted(existing_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        meta = parse_existing_transcript(path)
        if not meta:
            continue
        item = {
            "aweme_id": meta.aweme_id,
            "desc": meta.title,
            "item_title": meta.title,
            "create_time_display": meta.created_display,
            "output_file": meta.output_file,
            "source_file": meta.source_file,
            "segment_count": meta.segment_count,
        }
        title_key = normalize_match_text(meta.title)
        if title_key:
            mapping[title_key] = item
        compact_title_key = compact_match_text(meta.title)
        if compact_title_key and compact_title_key not in mapping:
            mapping[compact_title_key] = item

        source_title_key = normalize_match_text(derive_title_from_source(Path(meta.source_file)))
        if source_title_key and source_title_key not in mapping:
            mapping[source_title_key] = item
        compact_source_title_key = compact_match_text(derive_title_from_source(Path(meta.source_file)))
        if compact_source_title_key and compact_source_title_key not in mapping:
            mapping[compact_source_title_key] = item
    return mapping


def build_metadata_map(posts_json: Path | None, existing_dir: Path | None) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    if existing_dir:
        mapping.update(build_existing_map(existing_dir))
    if posts_json and posts_json.exists():
        mapping.update(build_posts_map(posts_json))
    return mapping


def find_best_meta(metadata_map: dict[str, dict], source_title: str) -> dict:
    normalized_source_title = normalize_match_text(source_title)
    compact_source_title = compact_match_text(source_title)

    for key in [normalized_source_title, compact_source_title]:
        if key and key in metadata_map:
            return metadata_map[key]

    best_meta: dict = {}
    best_score = 0
    for candidate_title, candidate_meta in metadata_map.items():
        if not candidate_title:
            continue
        for query in [normalized_source_title, compact_source_title]:
            if not query:
                continue
            shorter = min(len(candidate_title), len(query))
            score = 0
            if shorter >= 8 and (
                candidate_title.startswith(query) or query.startswith(candidate_title)
            ):
                score = shorter
            elif shorter >= 12 and (candidate_title in query or query in candidate_title):
                score = shorter - 2
            if score > best_score:
                best_score = score
                best_meta = candidate_meta
    return best_meta


def render_markdown(
    seq: int,
    meta: dict,
    source_file: Path,
    entries: list[SrtEntry],
) -> str:
    entries = trim_trailing_cta(entries)
    title = resolve_title(meta, source_file)
    created = meta.get("create_time")
    created_str = meta.get("create_time_display", "")
    if created:
        created_str = datetime.fromtimestamp(created, tz=CN_TZ).strftime("%Y-%m-%d %H:%M:%S %z")

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- No：{seq}")
    lines.append(f"- aweme_id：{meta.get('aweme_id', '')}")
    if created:
        lines.append(
            f"- create_time：{datetime.fromtimestamp(created, tz=CN_TZ).strftime('%Y-%m-%d %H:%M:%S')}"
        )
    lines.append(f"- item_title：{meta.get('item_title', title)}")
    try:
        source_path = source_file.relative_to(ROOT)
    except ValueError:
        source_path = source_file
    lines.append(f"- source_path：{source_path}")
    lines.append("")
    lines.append("## Cleaned Transcript")
    lines.append("")

    last_end = None
    paragraph: list[str] = []
    for entry in entries:
        txt = clean_text(entry.text)
        if not txt:
            continue
        if last_end and entry.start != last_end and paragraph:
            lines.append("".join(paragraph))
            lines.append("")
            paragraph = []
        paragraph.append(txt)
        if txt.endswith(("。", "！", "？", "；")):
            lines.append("".join(paragraph))
            lines.append("")
            paragraph = []
        last_end = entry.end
    if paragraph:
        lines.append("".join(paragraph))
        lines.append("")

    lines.append("## Segment References")
    lines.append("")
    for entry in entries:
        txt = clean_text(entry.text)
        if not txt:
            continue
        lines.append(f"- `{entry.start} --> {entry.end}` {txt}")
    lines.append("")
    return "\n".join(lines)


def remove_stale_seq_outputs(output_dir: Path, seq: int, keep_name: str) -> None:
    pattern = f"{seq:03d}-*.md"
    for path in output_dir.glob(pattern):
        if path.name != keep_name:
            path.unlink()


def build_manifest_item(seq: int, path: Path) -> dict | None:
    meta = parse_existing_transcript(path)
    if not meta:
        return None
    return {
        "seq": seq,
        "output_file": path.name,
        "source_file": meta.source_file,
        "aweme_id": meta.aweme_id,
        "title": meta.title,
        "segment_count": meta.segment_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--posts-json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--existing-cleaned-dir")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    posts_json = Path(args.posts_json) if args.posts_json else input_dir / "posts.json"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    existing_cleaned_dir = (
        Path(args.existing_cleaned_dir)
        if args.existing_cleaned_dir
        else output_dir
    )
    existing_map = build_existing_map(existing_cleaned_dir)
    posts_map = build_posts_map(posts_json) if posts_json and posts_json.exists() else {}

    grouped: dict[int, list[Path]] = defaultdict(list)
    for path in sorted(input_dir.glob("*.srt")):
        m = re.match(r"^(\d+)_", path.name)
        if not m:
            continue
        grouped[int(m.group(1))].append(path)

    manifest = []
    for seq in sorted(grouped):
        source = choose_source(grouped[seq])
        entries = parse_srt(source)
        if not entries:
            continue
        source_title = derive_title_from_source(source)
        meta = find_best_meta(posts_map, source_title)
        if not meta:
            meta = find_best_meta(existing_map, source_title)
        title = slugify(source_title)
        out_name = f"{seq:03d}-{title}.md"
        out_path = output_dir / out_name
        remove_stale_seq_outputs(output_dir, seq, out_name)
        out_path.write_text(render_markdown(seq, meta, source, entries), encoding="utf-8")
        manifest_item = build_manifest_item(seq, out_path)
        if manifest_item:
            manifest.append(manifest_item)

    for path in sorted(output_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        m = re.match(r"^(\d+)-", path.name)
        if not m:
            continue
        seq = int(m.group(1))
        if any(item["seq"] == seq for item in manifest):
            continue
        manifest_item = build_manifest_item(seq, path)
        if manifest_item:
            manifest.append(manifest_item)

    manifest.sort(key=lambda item: item["seq"])

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    index_lines = [
        "# Longfei Cleaned Transcript Index",
        "",
        f"- 来源目录：{input_dir}",
        f"- 输出目录：{output_dir}",
        f"- 文件数：{len(manifest)}",
        "",
        "## 文件列表",
        "",
    ]
    for item in manifest:
        index_lines.append(
            f"- `{item['seq']:03d}` [{item['output_file']}](./{item['output_file']}) "
            f"segments={item['segment_count']} aweme_id={item['aweme_id']}"
        )
    index_lines.append("")
    (output_dir / "README.md").write_text("\n".join(index_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
