# paeg-lang-style 全产物测试与修复报告

> 测试时间：2026-08-30 · 测试对象：`D:\wbo-workspace\paeg-lang-style-plugin`（symlink → 桌面 14.1）
> 测试方式：真实中文文本逐产物实测；LLM 路径经 `~/.local/share/opencode/auth.json` 注入 DeepSeek（`deepseek-chat`）
> 测试基线：`python -m pytest tests/ -q` = **90 passed** → 修复后 = **101 passed**

---

## 一、测了什么（产物/能力清单）

| # | 产物/能力 | 入口 | 状态 |
|---|---|---|---|
| 1 | 病句确定性修正（纯规则） | `fix_known_gaffes` | ✅ 可用 |
| 2 | 语法检查（8 类规则） | `check_ellipsis` | ✅ 可用 |
| 3 | 通则检测（词法/句法/充分状语） | `check_*_general_rule` | ✅ 可用（修复误报后） |
| 4 | AI 味检测（5 维信号） | `detect_ai_taste` | ✅ 可用（修复误报后） |
| 5 | 动态违禁词库 | `ForbiddenWords` | ✅ 可用 |
| 6 | 系统提示词拼装 | `get_style_prompt` / `LANGUAGE_STYLE` | ✅ 可用 |
| 7 | 可扩充规则集 | `RuleRegistry` | ✅ 可用 |
| 8 | 守门入口 | `gate_content` / `gate_short` / `polish_text` | ✅ 可用 |
| 9 | 校对报告（修订痕迹+报告） | `proofread` | ⚠️ 修复后可用（原会写入字面量 `\1` 破坏文本） |
| 10 | 文体预设 + 术语保护 | `style_presets` / `term_guard` | ✅ 可用（修复通用文体误保护后） |
| 11 | LLM 输出重写（Self-Refine） | `LanguageRefiner.refine` | ✅ 可用（真实 LLM 实测） |
| 12 | MCP 服务（tools/resources/prompts） | `mcp_server` | ✅ 可用（补 `proofread` 工具后 8 工具） |

**文档宣称但未实现（见「仍存在的风险」）**：Web 网页端/Flask API（`web/` 目录、`basic_rules.py`/`syntax_rules.py`/`semantic_checker.py`/`proofread_service.py`/`trace_builder.py`/`report_builder.py` 均不存在）；语义级 LLM 双通道（当前语义级仅规则通道，无 LLM 语义改写）。

---

## 二、每个产物的结果（结论摘要）

| # | 产物 | 结果判定 | 一句话结论 |
|---|---|---|---|
| 1 | 病句修正 | ✅ 顶尖 | "听着你"悬空病句 4 类模式全部正确修正，合法搭配零误伤，幂等 |
| 2 | 语法检查 | ✅ 良好 | 8 类规则 7 类实测命中；「介词」独立短语在 check_ellipsis 漏检（enhanced 通则层可补） |
| 3 | 通则检测 | ✅ 顶尖（修复后） | 修复前把"辛苦/麻烦/困难/混乱"误判为单字状态词；修复后 0 误报且真单字仍命中 |
| 4 | AI 味检测 | ✅ 顶尖（修复后） | 修复裸"牛"误报（牛奶/牛肉判 AI）与"——"破折号重复计数 |
| 5 | 违禁词库 | ✅ 顶尖 | 552 内置词 + 外部 JSON 三类合并；动态增删正确 |
| 6 | 系统提示词 | ✅ 顶尖 | 四段 4661 字符，分段/列表拼接正确 |
| 7 | 规则集 | ✅ 顶尖 | 93 规则（4 通则+89 列举），热加载/损坏容错/规则 ID 反馈闭环 |
| 8 | 守门入口 | ✅ 顶尖 | L0/L2 编排正确，异常静默回退，原意保持校验生效 |
| 9 | 校对报告 | ⚠️→✅ 修复 | 修复前输出含字面量 `\1` 破坏文本；修复后逐条可定位可解释 |
| 10 | 文体+术语 | ✅ 顶尖（修复后） | 5 文体；修复前"通用"文体误加载全领域术语（47 词），修复后为 0 |
| 11 | LLM 重写 | ✅ 可用 | 真实 DeepSeek 重写去除赋能/点亮等 AI 腔，薇依式朴素文风 |
| 12 | MCP 服务 | ✅ 顶尖（修复后） | 修复前 7 工具 + `build_style_prompt(all)` 漏掉风格提示词；修复后 8 工具 |

---

## 三、发现并修复的问题（共 9 项）

### 🔴 P0 破坏性缺陷（1 项）

**F1. `proofread` 把反向引用 `\1` 写成字面量，破坏输出文本。**
`gate.proofread` 的 `_apply_and_trace` 用函数 `_sub` 作为 `re.sub` 的替换，函数返回值被**原样**写入（不解析 `\1`），导致
`rule-fmt-basic-003`（"中文标点后不应有多余空格"）和 `rule-pn-basic-008` 把 `。 ` 替换成字面量 `。\1`。
实测输入 `"我在这里听着你。  这段话…"` → 输出 `"我在这里听着你\1这段话…"`，且 `\1` 隔断"听着你"后，病句修正也失效。
**修复**：`_sub` 改用 `m.expand(_repl)` 正确展开反向引用。

### 🟡 质量/正确性缺陷（6 项）

**F2. 词法完整通则误报常见复合词。**
`check_lexicon_general_rule` 用 `if single in text` 裸子串匹配，把"辛苦→苦""麻烦→烦""困难→困""混乱→乱"误判为单字状态词。
**修复**：改为复合词掩码法——先剔除完整词形与常见复合词（`_SAFE_COMPOUNDS`），再判断单字是否独立出现。

**F3. `rule-lx-general-001` 的 pattern 用裸字符类 `(倦|乏|沉|…)` 同样误报。**
`RuleRegistry.detect()` 因此对"辛苦/困难"也返回命中，触发 refiner 误改写。
**修复**：pattern 置 `None`（prompt-only，与其它通则 `rule-sx-general-00x` 一致）；单字状态词检测交由修复后的 `check_lexicon_general_rule` 负责。

**F4. AI 味检测把"牛奶/牛肉"判为 AI（裸"牛"误报）。**
`AI_MARKERS` 含裸单字 `"牛"`，任何含"牛奶/牛肉/蜗牛"的人类文本都被计入 marker_density（实测 666.67 → verdict=AI）。
**修复**：移除裸 `"牛"`（保留"牛啊/牛批"等短语）；"牛奶牛肉面"实测回归 Human。

**F5. 破折号重复计数：`——` 被计为 3 个。**
`count_em_dashes` = `findall("—") + findall("——")`，中文破折号"——"被计 3 次。
**修复**：先数"——"再数剩余"—"；"——"计 1。

**F6. 通用文体误加载全领域术语（term_guard）。**
`load_terms(domains=[])` 因兜底条件 `not domains` 误触发，返回全领域 47 词；与"通用=无术语保护"的文档语义相反。
**修复**：兜底仅当 `domains is None`（全领域）或指定领域存在内置词时生效，`domains=[]` 保持空集。

**F7. MCP `build_style_prompt(section="all")` 漏掉语言风格提示词。**
原逻辑 `if section != "all"` 导致"all"只返回规则集提示词（1580 字符、不含"朴素"），丢失 weil/lexicon/syntax/forbidden 四段。
**修复**：始终调用 `get_style_prompt(section)`；"all" 现返回 6274 字符、含"朴素"。

### 🟢 文档-实现差距 / 缺字段（2 项）

**F8. `proofread` 缺字段 + 检测型规则漏报 + 语法 trace 粗粒度。**
原实现只返回 `{text, trace, report{by_type,total}, style}`，缺少文档数据模型要求的
`id/ts/domain/levels/source_text/report.suggestions/report.preserved_score`；
replacement 为空的检测型规则（如 `rule-pn-001` "说后冒号"）被静默丢弃；
语法级 trace 只有一条"整段原文/改文 + pos=0"。
**修复**：补齐全部字段；检测型规则命中记入 `report.suggestions`（不改文本）；语法级改用 difflib 逐处定位 trace。

**F9. `proofread` 未导出、MCP 无 `proofread` 工具；`demo.py` 有重复代码块。**
文档（05_技术架构设计 §4）声明 MCP 提供 `proofread` 工具，但代码无；`demo.py` 把 `_demo_rule_registry` 函数体重复内联了一遍（运行打印两次）。
**修复**：`proofread` 加入 `__init__` 导出 + 新增 MCP `proofread` 工具；删除 demo.py 重复代码块。

---

## 四、仍存在的风险 / 建议（未改动）

1. **【设计张力】`gate_content` L2 的 `preserve_check`（95% 相似度门槛）与"去 AI 味重写"冲突。**
   去 AI 味重写本质上是大幅改写（README 示例 `"总的来说，让我们一起赋能这个时代！"` → `"我们把这个时代里的每一个孩子…"`），
   字符相似度远低于 95%，因此 L2 几乎总是**拒绝采用** LLM 改写、回退原文（实测相似度 0.145 → 回退）。
   `refiner.refine()` 直调则正常产出重写。二者语义不同：`preserve_check` 应约束"语义级改写"，而非"去 AI 味重写"。建议后续明确拆分两条 LLM 通道。
2. **`check_ellipsis` 的「介词」独立短语漏检。** 如 `"关于学习方面。"` 在 `check_ellipsis` 中无命中（分句切分去掉了句末标点，`BAD_PREPOSITIONS` 又要求字面标点）；`check_syntax_general_rule`（通则层）可补。为保持与 PAEG 基线 parity 未改动。
3. **`check_ellipsis` 未覆盖"听着你"病句与"有点倦"词法**（分别在 `fix_known_gaffes` 与通则层检测），属分工而非缺陷。
4. **语义级 LLM 双通道未实现**：语义级当前仅规则通道（rule-sm-*），无 LLM 逻辑矛盾/歧义改写（`semantic_checker.py` 不存在）。
5. **`rule-pn-001` 正则 `说：\"(?!.*说)` 的负向前瞻写法可疑**，但为检测型规则（不自动替换），影响有限。
6. **错别字库仍可扩充**：如"签定→签订"未收录（实测 `proofread("我们签定了合同…")` 不命中）。

---

## 五、test_artifacts 文件清单

| 文件 | 内容 |
|---|---|
| `README.md` | 本报告（测了什么/结果/发现与修复/风险） |
| `run_tests.py` | 可复现全产物实测脚本（`--no-llm` 可离线跑确定性部分） |
| `01_病句修正_fix_known_gaffes.md` | 病句确定性修正 |
| `02_语法检查_check_ellipsis.md` | 8 类语法检查 |
| `03_通则检测_general_rules.md` | 词法/句法/充分状语通则 |
| `04_AI味检测_ai_taste.md` | 5 维 AI 味信号 |
| `05_违禁词库_forbidden_words.md` | 动态违禁词库 |
| `06_系统提示词_style_prompt.md` | 语言风格系统提示词 |
| `07_规则集_rule_registry.md` | 可扩充规则集 |
| `08_守门入口_gate.md` | gate_content/gate_short/polish_text |
| `09_校对报告_proofread.md` | 三级校对 + 修订痕迹 + 报告 |
| `10_文体预设与术语保护_style_presets.md` | 5 文体 + 术语白名单 |
| `11_LLM重写_refine.md` | LLM Self-Refine 重写（真实 DeepSeek） |
| `12_MCP服务_mcp_server.md` | MCP 8 工具 + 3 资源 + 2 提示词 |
| `13_测试样本_samples.md` | 测试样本集与预期 |
| `14_生态联通_L0校对验证.md` | Round-2：三下游工具（14.2/14.3/14.5）注册并使用本插件 `gate_short`+`fix_known_gaffes` 的确定性证据（含优雅降级） |
| `verify_l0_ecosystem.py` | Round-3：`14_生态联通_L0校对验证.md` 的**可复现生成脚本**（确定性，无网络；子进程屏蔽假包验证优雅降级） |
| `scan_frontend_emoji.py` | Round-3：验收项③扫描脚本（三下游 web 前端装饰性 emoji=0，图标均为内联 SVG） |
| `_run_out.txt` | `run_tests.py` 的一次完整运行输出快照 |
