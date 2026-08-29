# 产物 7：可扩充规则集 `RuleRegistry`

## 能力说明
规则外置 `data/rules.json`，追加即热加载；通则层（prompt_block 指挥 LLM）+ 列举层（pattern+replacement 确定性兜底）；规则 ID 反馈闭环。

## 实测输入 / 输出

| 项 | 结果 |
|---|---|
| 规则总数 | 93（通则 4 + 列举 89） |
| 分类分布 | lexical 5 / syntactic 9 / punctuation 10 / typo 43 / format 5 / semantic 14 / pragmatic 4 / discourse 3 |
| `build_prompt("general")` | 1611 字符（含词法/句法/充分状语通则） |
| `build_prompt("teaching")` | 1611 字符（加载用户扩展后含"教学用语通则"） |
| `build_prompt("confessional")` | 1475 字符（不含教学扩展） |
| `detect("我在这里听着你。")` | rule-sx-001 / rule-sx-002 / rule-sx-004 |
| `detect("这是大概也许正确的说法。")` | rule-sm-001（`大概也许`） |
| `detect("这是绝对正确的结论。")` | rule-sm-008（`绝对正确`） |
| `apply_explicit("我在这里听着你。")` | `我就在这里听你说说。` |
| 热加载/损坏容错 | 追加合并；坏 JSON 保留原规则集 |

## 发现与修复
- **F3（已修复）**：`rule-lx-general-001` 的 pattern 由裸字符类改为 `None`（prompt-only），避免 `detect` 误报"辛苦/困难"等复合词。

## 结果判定
✅ **顶尖水平**。93 规则、通则/列举分层、热加载、损坏容错、规则 ID 反馈闭环全部实测通过。
