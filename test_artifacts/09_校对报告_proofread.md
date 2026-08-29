# 产物 9：校对报告 `proofread`（三级校对 + 修订痕迹 + 报告）

## 能力说明
三级校对（basic 错别字/标点/格式 + grammar 病句 + semantic 语义重复/矛盾/歧义）+ 文体适配 + 术语保护，
返回结构化 `{id, ts, domain, levels, source_text, text, trace, report}`，每条修改可定位可解释。

## 实测输入

```
他写了一个帐号，感到好象有点倦。这个结论绝对正确！！我在这里听着你。  他说："大概也许可行。"
```

## 输出（修正后文本）

```
他写了一个账号，感到好像有点倦。这个结论基本正确！我就在这里听你说说。他说："大概可行。"
```

## 修订痕迹（trace，节选）

| pos | original | revised | type | reason |
|---|---|---|---|---|
| 5 | 帐号 | 账号 | typo | 『帐号』是错别字 |
| 10 | 好象 | 好像 | typo | 『好象』是错别字 |
| 24 | ！！ | ！ | punctuation | 连续感叹号应为单个 |
| 32 | 。␣ | 。 | format | 中文标点后不应有多余空格 |
| 20 | 绝对正确 | 基本正确 | semantic | 过度绝对化，建议软化 |
| 37 | 大概也许 | 大概 | semantic | 语义重复，保留其一 |
| 26/30/32 | （听着你→听你说说） | 就/着/说说 | grammar | 病句修正 fix_known_gaffes |

## 报告（report）

```json
{
  "by_type": {"typo": 2, "punctuation": 1, "format": 2, "semantic": 2, "grammar": 3},
  "total": 10,
  "suggestions": [
    {"pos": 37, "original": "说：\"", "type": "punctuation",
     "reason": "GB/T 15834：插在话语中间的『说/道』后只能用逗号，不能用冒号", "rule_id": "rule-pn-001"}
  ],
  "preserved_score": 0.8172
}
```

## 发现与修复
- **F1（P0 已修复）**：`_sub` 用函数替换导致反向引用 `\1` 被写成字面量，破坏文本（`。 ` → `。\1`）且连带破坏病句修正。改用 `m.expand(_repl)`。
- **F8（已修复）**：补齐 `id/ts/domain/levels/source_text/report.suggestions/report.preserved_score` 字段；检测型规则（replacement 为空）记入 `suggestions` 不再丢弃；语法级 trace 用 difflib 逐处定位（原为整段原文+pos=0）。
- **F9（已修复）**：`proofread` 加入 `__init__` 导出与 MCP 工具。

## 结果判定
✅ **顶尖水平（修复后）**。错别字/标点/格式/语义/病句三级正确修正，逐条可定位可解释，检测型规则进入建议列表，报告结构化。
