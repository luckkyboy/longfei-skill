你在为一个人物型 skill 做中间层蒸馏。输入是一条 cleaned transcript。

任务不是写评论，不是发挥，不是总结成心智模型，而是抽取“这条内容明确体现出来的信息”。

## 核心约束（必须遵守）

1. 只输出一个 JSON 对象，不要输出 markdown，不要输出解释文字。
2. 不要脑补不存在的信息。
3. 如果某字段不适用，用 `null`、`[]` 或 `false`。
4. `representative_quotes` 必须来自原文，不得改写原意。
5. `decision_rules` 只能写该条 transcript 明确出现的规则，不要上升成通用理论。
6. `promotion` 和 `daily_life` 通常 `decision_rules` 为空数组。

## 强约束模式（字段锁定，不可改写）

下面 8 个字段必须完全等于输入 metadata/hint，不允许改写、推断、纠正、格式转换：

- `seq` = 输入 `seq`
- `title` = 输入 `title`
- `aweme_id` = 输入 `aweme_id`（保留为字符串，不要转成数字）
- `create_time` = 输入 `create_time`
- `source_path` = 输入 `source_path`
- `content_type` = 输入 `content_type_hint`
- `primary_targets` = 输入 `primary_targets_hint`
- `value_level` = 输入 `value_level_hint`

即使你认为 hint 可能不准确，也不允许覆盖。

## 严格类型约束

- `aweme_id` 必须是 `string`
- `primary_targets` 必须是 `string[]`，不能是单个字符串
- `topics` 必须是 `string[]`
- `decision_rules` 必须是 `string[]`
- `expression_signals` 必须是 `string[]`
- `representative_quotes` 必须是 `string[]`
- `risk_signals` 必须是 `string[]`
- `anti_patterns` 必须是 `string[]`
- `timeline_signals` 必须是 `string[]`
- `judgment_present` 必须是 `boolean`
- `core_question` / `scenario` / `judgment_summary` 只允许 `string | null`

## 枚举约束

- `content_type` 只能是：`promotion` / `daily_life` / `opinion_monologue` / `fan_call_case`
- `primary_targets` 元素只能是：`02-conversations` / `03-expression-dna` / `05-decisions` / `06-timeline`
- `value_level` 只能是：`low` / `medium` / `high`
- `confidence` 只能是：`low` / `medium` / `high`

## 输出字段（完整返回）

- `seq`
- `title`
- `aweme_id`
- `create_time`
- `source_path`
- `content_type`
- `primary_targets`
- `value_level`
- `topics`
- `summary`
- `core_question`
- `scenario`
- `judgment_present`
- `judgment_summary`
- `decision_rules`
- `expression_signals`
- `representative_quotes`
- `risk_signals`
- `anti_patterns`
- `timeline_signals`
- `confidence`

## 输入 transcript

将单条 `cleaned-md` 的标题、元数据和 `## Cleaned Transcript` 内容作为输入。
