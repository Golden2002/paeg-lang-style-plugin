# 产物 6：系统提示词 `get_style_prompt` / `LANGUAGE_STYLE`

## 能力说明
词法/句法规则作为系统提示词约束 LLM（谁用都拼）。4 段：weil（薇依式风格）/ lexicon（词法）/ syntax（句法）/ forbidden（违禁表达）。

## 实测输入 / 输出

| section | 字符数 | 关键内容 |
|---|---|---|
| all | 4661 | 朴素 / 主谓宾 / 伪共情 / 循循善诱 |
| weil | 919 | 循循善诱 |
| lexicon | 786 | 词法完整 |
| syntax | 1969 | 主谓宾 |
| forbidden | 981 | 伪共情 |
| `get_style_prompt(["weil","syntax"])` | — | 两段拼接 |

## 结果判定
✅ **顶尖水平**。四段结构清晰、内容与 README/SKILL 一致，列表拼接正确。
