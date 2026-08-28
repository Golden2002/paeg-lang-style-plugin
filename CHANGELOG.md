# CHANGELOG — paeg-lang-style-plugin（PAEG 工具生态 14.1 语言规范）

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
