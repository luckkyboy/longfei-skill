# Nvwa Distillation Bootstrap

这批产物是把 `references/sources/transcripts/cleaned-md/` 变成 `nuwa-skill` 可继续加工的中间层，而不是最终 Skill 内容。

## 目录说明

- `transcript_index.jsonl`
  - 全量 transcript 路由清单
  - 每条记录包含元数据、轻量分类、目标研究文件建议、预览文本
- `samples/transcript_extract_sample_30.jsonl`
  - 首批 30 条样本
  - 用于校验 schema、prompt 和分类 heuristics
- `schema/cleaned_md_extraction.schema.json`
  - 当前 AI 全量抽取时要输出的正式字段定义
- `prompts/cleaned_md_extraction_developer_prompt.md`
  - NVIDIA NIM 请求中的 developer prompt
- `prompts/cleaned_md_extraction_user_prompt.md`
  - NVIDIA NIM 请求中的 user prompt 模板
- `schema/transcript_extract.schema.json` 与 `prompts/transcript_extract_prompt.md`
  - 旧版抽取字段定义与提示词，保留作历史参考
- `tasks/transcript_extract_tasks.jsonl`
  - 全量 AI 任务文件
- `tasks/transcript_extract_tasks_sample_30.jsonl`
  - 30 条样本任务文件

## 使用顺序

1. 运行 `python3 scripts/02_build_nvwa_transcript_index.py`
2. 人工查看 `samples/transcript_extract_sample_30.jsonl`
3. 修正分类 heuristics、schema 和 prompt
4. 对全量 `cleaned-md` 进行 AI 抽取，产出 `transcript_extract.jsonl`
5. 运行严格校验：
   - `python3 scripts/05_strict_validate_nvwa_extract.py`
6. 基于新版 `transcript_extract.jsonl` 继续做人审、聚合或 skill 素材整理

## 使用 NVIDIA NIM 运行抽取

环境变量：

```bash
export NVIDIA_NIM_API_KEY=你的_key
```

全量运行：

```bash
python3 scripts/03_build_nvwa_extraction_tasks.py
python3 scripts/04_run_nvwa_extraction_with_nim.py
```

说明：
- 当前脚本默认对 `z-ai/glm4.7` 显式传入 `chat_template_kwargs.enable_thinking=false`
- 目的是关闭 thinking，减少额外思维块，提升结构化 JSON 输出稳定性
- 当前脚本使用 `developer + user` 双消息，并传入 `response_format.json_schema`
- 默认输出会写入并续跑 `output/transcript_extract.jsonl`
- 已完成的 `task_id` 会自动跳过
- `429/500/502/503/504` 会按退避策略自动重试

只跑样本前 30 条：

```bash
python3 scripts/04_run_nvwa_extraction_with_nim.py \
  --tasks-path references/nvwa/tasks/transcript_extract_tasks_sample_30.jsonl
```

只跑 1 条验证：

```bash
python3 scripts/04_run_nvwa_extraction_with_nim.py \
  --tasks-path references/nvwa/tasks/transcript_extract_tasks_sample_30.jsonl \
  --limit 1
```

## 当前抽取产物状态

- `output/transcript_extract.jsonl`
  - 当前为新版 `cleaned_md_extraction` schema
  - 共 500 条
  - `transcript-extract-0346` 因 NVIDIA NIM 多次返回 `HTTP 500` / read timeout，已按同一 schema 手工补录
  - 手工补录记录带有 `raw_response.manual=true`，便于后续追踪

## 设计原则

- `cleaned-md` 继续作为源语料，不被覆盖
- `transcript_index.jsonl` 只做路由和初筛，不生成高阶结论
- 心智模型、决策启发式、表达 DNA 由 AI 二次汇总阶段生成
