# CHANGELOG — paeg-lang-style-plugin（PAEG 工具生态 14.1 语言规范）

## v0.1.1 (2026-08-31) — 全面测试修复 9 项 + 校对报告补齐

**更新路径**：src/paeg_lang_style/{gate, ai_taste, rules_enhanced, rule_registry, term_guard, mcp_server, __init__}.py + demo.py + tests/test_fixes.py（新增）

- P0：proofread 反向引用 `\1` 被写成字面量破坏文本 → `m.expand()` 修复
- 词法通则误报「辛苦/麻烦/困难/混乱」→ 复合词掩码 + pattern 置 None
- AI 味「牛」误判「牛奶/牛肉」→ 移除裸「牛」；破折号「——」计 3 → 计 1
- term_guard 通用文体误加载全领域词 → 兜底条件修复
- MCP build_style_prompt(section=all) 漏语言风格提示词 → 补齐
- proofread 补齐 id/ts/domain/levels/source_text/suggestions/preserved_score + 检测型规则漏报 + 语法 trace 定位 + MCP 工具导出
- 测试 +11（test_fixes.py）；全量 101 passed

## v0.1.0 (2026-08) — 发布

**更新路径**：src/paeg_lang_style/{rules, rules_enhanced, rule_registry, forbidden, gate, refiner, ai_taste, mcp_server}.py + data/{rules, forbidden_words, weil_corpus}.json

- 病句确定性修正（纯规则）、词法完整、动宾搭配、悬空宾语补足、无主语短语、复合句缺主语、介词规范
- AI 味检测（句长变异/过渡词密度/三段式/破折号/段落对称）
- 动态违禁词库 + LLM 输出重写（Self-Refine）
- MCP 插件 + SKILL.md
- 测试 83 全绿

## 2026-08-28 — 作为依赖接入简历工具（14.5 v1.7.0）

- pip install -e 指向真实位置（14.1）——独立更新即时同步
- 简历 core.py compose 接入 fix_known_gaffes 语言规范
- 待办（顶尖标准对标后）：三级校对体系补齐（基础级标点格式/语义级深度/领域适配/可追溯输出）
