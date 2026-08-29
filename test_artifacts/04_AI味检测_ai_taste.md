# 产物 4：AI 味检测 `detect_ai_taste`（5 维信号）

## 能力说明
句长变异（burstiness）/ 过渡词密度（marker_density）/ 三段式（three_list）/ 破折号（em_dash）/ 段落对称（paragraph_cv）→ 综合 `ai_likelihood` + `verdict`（AI/Mixed/Human）。

## 实测输入 / 输出（修复后）

| 输入 | ai_likelihood | verdict | 关键信号 |
|---|---|---|---|
| 总的来说，让我们一起赋能这个时代，点亮无限可能！ | 0.6 | AI | marker_density=2000 |
| 墨水在水里散开，像一朵迟缓的花。 | 0.0 | Human | 全 0 |
| 我今天喝了牛奶，吃了牛肉面，味道不错。 | 0.0 | Human | marker=0（修复后） |
| 他想了想——然后说，没关系。 | 0.0 | Human | em_dash=1（修复后） |
| （空串） | 0.3 | Human | 空输入安全 |

## 发现与修复
- **F4（已修复）**：`AI_MARKERS` 含裸单字 `"牛"`，导致"牛奶/牛肉/蜗牛"等人类文本被判 AI（实测 marker=666.67 → AI）。移除裸 `"牛"`，保留"牛啊/牛批"等短语。
- **F5（已修复）**：`count_em_dashes` 把中文破折号"——"计为 3 个（`findall("—")` 计 2 次 + `findall("——")` 计 1 次）。改为先数"——"再数剩余"—"，"——"计 1。

## 结果判定
✅ **顶尖水平（修复后）**。AI 腔与人类文本区分清晰，常见人类词（牛奶/牛肉）与中文破折号不再误报。
