# 产物 10：文体预设 `style_presets` + 术语保护 `term_guard`

## 能力说明
5 文体（学术/公文/简历/法律/通用），每文体关联术语领域，决定校对时保护哪些术语白名单（黑名单是"禁止出现"，白名单是"禁止误改"）。

## 文体预设列表（list_styles）

| id | label | term_domains | note |
|---|---|---|---|
| academic | 学术论文 | academic, resume | 保留专业术语准确性 |
| official | 公文 | legal | 公文用语庄重简洁 |
| resume | 简历 | resume | STAR 量化表达 |
| legal | 法律文书 | legal | 法条引用规范 |
| general | 通用 | [] | 通用校对（无术语保护） |

## 术语保护实测

| 调用 | 结果 |
|---|---|
| `load_terms(domains=None)` | 75 词（全领域） |
| `load_terms(domains=["legal"])` | 28 词 |
| `load_terms(domains=["resume"])` 含"机器学习" | True |
| `load_terms(domains=[])` | **0 词（修复后）** |
| `protect("我们签订了合同，约定了违约责任。", legal 术语)` → restore | 占位符隔离 → 原样还原 ✅ |

## 发现与修复
- **F6（已修复）**：`load_terms(domains=[])` 因兜底条件 `not domains` 误触发，返回全领域 47 词，与"通用=无术语保护"相反。修复为：仅 `domains is None`（全领域）或指定领域存在内置词时兜底，`domains=[]` 保持空集。

## 结果判定
✅ **顶尖水平（修复后）**。5 文体、分领域术语、占位符保护/还原正确，通用文体不再误保护。
