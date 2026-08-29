# 产物 8：守门入口 `gate_content` / `gate_short` / `polish_text`

## 能力说明
`gate_content`（L0 病句+基础+语义 + L2 深度矫正 + 收口）、`gate_short`（短文本快路径）、`polish_text`（L-08 兼容入口）。异常静默回退原文。

## 实测输入 / 输出

| 调用 | 输出 |
|---|---|
| `gate_content("我在这里听着你。")` | `我就在这里听你说说。` |
| `gate_content("他写了一个帐号，感到好象有点倦。这个结论绝对正确！！  后面有空格  。")` | `他写了一个账号，感到好像有点倦。这个结论基本正确！后面有空格 。`（无字面 `\1`） |
| `gate_short("老师在这里听着你。")` | `老师在这里听你说说。` |
| `gate_content("")` | `""`（空输入安全） |
| `polish_text("我在这里听着你。")`（无 refiner） | `我就在这里听你说说。`（规则兜底） |
| `gate_content(raw, refiner=refiner)`（L2，真实 LLM） | 回退原文（preserve_check 拒绝相似度 0.145 的重写，见风险 1） |

## 结果判定
✅ **顶尖水平**（规则层）。L0/L2 编排、三级开关（levels）、原意保持校验、异常静默回退均正确。

## 发现与修复
- 规则层 `_apply_categories` 用字符串 replacement（`cp.sub(repl, out)`），反向引用 `\1` 正确解析，无缺陷。
- **风险 1（未改动）**：L2 的 `preserve_check`（≥95%）与"去 AI 味重写"语义冲突，导致 L2 基本不采用 LLM 重写（详见 `README.md` §四）。
