# 产物 12：MCP 服务 `mcp_server`（tools / resources / prompts）

## 能力说明
独立 MCP server（stdio），`pip install` 后零代码桥接入。三原语完整：Tools + Resources + Prompts。

## 实测清单

### Tools（修复后 8 个）
| 工具 | 实测结果 |
|---|---|
| `normalize_text` | ✅ `我在这里听着你。` → `我就在这里听你说说。` |
| `language_policy_check` | ✅ `{ai_likelihood:0.6, verdict:AI, forbidden_hits:[总的来说,让我们,…]}` |
| `check_grammar` | ✅ 返回省略主语/省略词形问题列表 |
| `check_ai_taste` | ✅ 返回 5 维信号 + verdict |
| `build_style_prompt(section=all)` | ✅ 6274 字符、含"朴素"（修复后） |
| `list_rules` | ✅ 93 条 |
| `forbidden_words(list/add/remove/check)` | ✅ 正常 |
| `proofread` | ✅ 返回完整校对报告（修复后新增） |

### Resources（3 个）
`rules://stats` · `style-presets://list` · `term-whitelist://list`

### Prompts（2 个）
`proofread_workflow` · `report`

## 发现与修复
- **F7（已修复）**：`build_style_prompt(section="all")` 原逻辑 `if section != "all"` 导致"all"漏掉语言风格提示词（只返回规则集、不含"朴素"）。改为始终调用 `get_style_prompt(section)`。
- **F9（已修复）**：新增 `proofread` 工具（对齐 docs/05 §4 声明），`__init__` 同步导出。

## 结果判定
✅ **顶尖水平（修复后）**。8 工具 + 3 资源 + 2 提示词，三原语完整，`strict_input_validation` 开启。
