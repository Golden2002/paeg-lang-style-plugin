# paeg-lang-style — PAEG 语言规范插件

> 可拆卸、可独立、可接入教育智能体的**中文语言规范模块**。
> 从 PAEG 教育智能体（v0.12-v0.71 迭代）提取，改造为**零宿主依赖**的独立插件。

语言规范模块包含三大能力（用户需求 ⭐）：

| 能力 | 实现 | 说明 |
|---|---|---|
| **1. 系统提示词约束** | `paeg_lang_style/prompts/language_style.py` | 从**词法、句法规则**约束 LLM 输出 |
| **2. 动态违禁词库** | `paeg_lang_style/forbidden.py` | 动态维护的违禁词库（运行时增删 + 外部 JSON 热加载） |
| **3. 重写大模型输出的工具** | `paeg_lang_style/refiner.py` | LLM 输出后处理（病句修正 + AI 味检测 + 多轮 Self-Refine） |

---

## 快速开始

```bash
# 独立运行（无需安装）
cd paeg-lang-style-plugin
python demo.py                    # 规则层演示
python demo.py --with-llm         # LLM 重写演示（注入 chat_fn）

# 安装为 Python 包
pip install -e .

# 测试
python -m pytest tests/ -q
```

```python
from paeg_lang_style import (
    gate_content,          # 生成内容语言规范守门（L0+L2）
    gate_short,            # 短文本语言守门（仅 L0）
    make_refiner,          # 重写工具工厂（注入 chat_fn）
    get_style_prompt,      # 系统提示词（weil/lexicon/syntax/forbidden 分段）
    fix_known_gaffes,      # 病句确定性修正
    check_ellipsis,        # 语法检查
    detect_ai_taste,       # AI 味检测
    ForbiddenWords,        # 动态违禁词库
)

# 1. 系统提示词约束（词法/句法规则约束 LLM）
system = get_style_prompt("all")                    # 全量
system = get_style_prompt("syntax")                 # 仅句法段
system = get_style_prompt(["weil", "lexicon"])      # 多段拼接

# 2. 动态违禁词库
fb = ForbiddenWords()
fb.add("新禁词")          # 运行时新增（动态维护）
fb.load_json("path.json") # 外部 JSON 热加载
hits = fb.detect(text)    # 检测命中

# 3. 重写 LLM 输出（注入自己的 LLM 调用包装）
def my_chat(system, user, max_tokens=800, **kw):
    return call_my_llm(system, user, max_tokens=max_tokens)

refiner = make_refiner(chat_fn=my_chat)   # ⭐ 强制注入，插件独立可用
refined = refiner.refine(llm_output)

# 4. 守门入口（生成链路统一收口）
out = gate_content(text)                                  # 纯规则（L0 快路径）
out = gate_content(text, refiner=refiner)                 # L0 + L2 深度矫正
```

---

## 架构

```
paeg-lang-style-plugin/
├── pyproject.toml              # 独立包（MIT）
├── demo.py                     # 独立运行 demo（不依赖 PAEG）
├── README.md                   # 本文件：架构 + 每条语法规则
├── SKILL.md                    # Agent Skills 标准（渐进披露 3 层）
├── src/paeg_lang_style/
│   ├── __init__.py             # 对外 API（gate_content / make_refiner / ...）
│   ├── rules.py                # 列举式规则（确定性兜底：倦→疲倦、听着你→听你说说）
│   ├── rules_enhanced.py       # 通则化检测（指挥 LLM 泛化：词法/句法完整通则）
│   ├── rule_registry.py        # ⭐ 可扩充规则集（Rule 模型 + JSON 热加载 + profile 拼装）
│   ├── ai_taste.py             # AI 味检测（句长变异/过渡词/三段式/破折号）
│   ├── forbidden.py            # 动态违禁词库（运行时增删 + JSON 热加载）
│   ├── refiner.py              # 改写脚本（注入式 chat_fn，规则 ID 反馈闭环）
│   ├── gate.py                 # 守门入口（L0+L2 三层，注入式解耦）
│   └── prompts/
│       ├── builder.py          # ⭐ profile 动态拼装系统提示词（general/teaching/confessional）
│       └── language_style.py   # 语言风格提示词（weil/lexicon/syntax/forbidden 四段）
├── data/
│   ├── rules.json              # ⭐ 可扩充语法规则集（用户追加即热加载）
│   ├── forbidden_words.json    # 外部违禁词库（动态维护）
│   └── weil_corpus.json        # 语料 few-shot（可替换为中性语料）
├── docs/
│   ├── architecture.md         # 架构图 + 数据流
│   ├── integration_paeg.md     # 接入 PAEG 指南
│   └── samples_20.md           # 20 段 LLM 直生成 vs 处理后对比
└── tests/                      # 67 项测试（含规则集/通则/一致性）
```

### 三层架构（用户要求 ⭐：语法规则约束 + 违禁词兜底 + 改写脚本）

| 层 | 模块 | 定位 | 可扩充性 |
|---|---|---|---|
| **语法规则约束**（最重要） | `rule_registry.py` + `prompts/builder.py` | **系统提示词核心，谁用都拼**——通则层指挥 LLM 泛化（用完整词/完整句法），列举层确定性兜底 | ⭐ 规则集外置 `data/rules.json`，追加即热加载 |
| **违禁词兜底** | `forbidden.py` | 防 LLM 不听话时的底线（AI 腔/空洞大词/伪共情/廉价鼓励/网络用语） | ⭐ 运行时增删 + JSON 热加载 |
| **改写脚本** | `refiner.py` | LLM 输出后处理（检测命中规则 → 反馈带规则 ID → 多轮 Self-Refine） | 规则集扩充自动接入检测/反馈 |

### 可扩充规则集（RuleRegistry ⭐ 核心设计）

**Rule 数据模型**（外置 JSON，可扩充）：
```json
{
  "id": "rule-lx-general-001",
  "type": "general",              // general=通则（指挥 LLM）/ explicit=列举（确定性兜底）
  "category": "lexical",          // lexical / syntactic / punctuation / register
  "pattern": "正则（检测用）",
  "replacement": "替换文本（列举层确定性）",
  "message": "修正建议（反馈 LLM）",
  "prompt_block": "通则提示词段落（拼进系统提示词）",
  "severity": "high",
  "enabled": true,
  "source": "builtin",           // builtin / user
  "profile_tags": ["general", "teaching", "confessional"]
}
```

**可扩充方式**（用户要求 ⭐）：
```python
from paeg_lang_style import RuleRegistry
reg = RuleRegistry()                 # 内置规则
reg.load("data/rules.json")          # 合并用户扩展规则（追加即生效）
reg.add_rule({...})                  # 运行时新增
reg.watch("data/rules.json")         # mtime 热重载
reg.check_reload()                   # 每次调用前检查

# 谁用都拼（语法规则作为系统提示词核心）
prompt = reg.build_prompt("teaching")       # 教学档
prompt = reg.build_prompt("confessional")   # 倾诉档
prompt = reg.build_prompt("general")        # 通用档
```

**设计哲学**（用户关切 ⭐ 避免狭隘性）：
- **通则层指挥 LLM 泛化**：`prompt_block` 写"凡表达状态/感受的单字形容词一律扩展为完整双字词形（倦/乏/沉/累/苦/慌/虚/弱/低/烦/闷/困/急/乱）"——LLM 自行泛化到未列举词，而非只修"倦→疲倦"
- **列举层确定性兜底**：LLM 不听话时的最后防线（"我在这里听着你"→"我就在这里听你说说"）
- **规则 ID 反馈闭环**：改写反馈带规则编号（"违反 #rule-lx-007…"），形成规则↔生成↔反馈闭环

### 三大架构模式（librarian 调研应用）

| 模式 | 来源范式 | 插件实现 |
|---|---|---|
| 规则声明式 + 模式匹配引擎 | LanguageTool（grammar.xml 规则） | `rule_registry.py`（Rule 数据模型 + pattern 检测） |
| 算法式度量 | textstat（语言特定公式） | `ai_taste.py`（burstiness/marker_density 等） |
| 中文特化预处理 | jieba + LTP（分词驱动） | `rules.py` 正则分句检测（零依赖版） |
| 渐进披露 3 层 | Agent Skills 标准 | `SKILL.md`（L1 入口）+ `docs/`（L2 规则页）+ `data/`（L3 数据） |
| 标点规范 | GB/T 15834-2011 | `rule-pn-*` 标点规则（句末点号/顿号vs逗号/说后逗号） |

### 数据流

```
LLM 生成文本
   │
   ▼
gate_content() ── L0-0: fix_known_gaffes（病句确定性修正，纯规则）
   │
   ├── L0: polish（AI 味检测 → 触发改写；注入式 polish_fn）
   │
   ├── L2: refiner.refine（注入式 chat_fn → 多轮 Self-Refine）
   │        └─ detect_ai_taste → 复检 < 0.4 停止
   │
   └── 收口: fix_known_gaffes（改写后病句再跑一遍）
   │
   ▼
规范输出
```

---

## 语法规则约束（8 条 · README 详记 ⭐）

每条规则含：**规则定义 / 触发模式（正则）/ 修正方向 / 正反例**。

### 规则 1：词法完整（禁止单字压缩双字词）

> **定义**：动词、名词、形容词一律使用完整词形，不得省略、压缩。双字词/多字词不得压缩为单字。

**触发模式**（`rules.py` `ELLIPSIS_WORDS`）：
```python
(r"觉得倦了|感到倦|已倦", "『倦』是『疲倦』的省略，应改为完整词形『疲倦』")
(r"的乏($|[，。；])", "『乏』是『疲乏』的省略，应改为完整词形『疲乏』")
(r"道出", "『道出』是压缩写法，应改为『说出来』或『说出』")
(r"探知", "『探知』是压缩写法，应改为『探索并了解』")
(r"开始算|先算|来算|算算|算一下|算个", "『算』是『计算』的省略，应改为完整词形『计算』")
(r"开始看|先看|来看|看看", "『看』若指『观察/查看』应用完整形式『观察』『查看』")
(r"开始想|想想|想一想|来想", "『想』若指『思考』应用完整形式『思考』")
(r"(每天|每周|每日|每晚|每早|平时|空闲|晚上|早上|下午|中午|睡前|早起)[^，。；]{0,8}(时间|时候)?[用学看听读]($|[，。；])",
 "缺介词+动词不规范——『每天固定时间用』应改为『在每天固定的时间使用』")
```
**修正方向**：`倦`→`疲倦`、`乏`→`疲乏`、`沉`→`沉重`、`道出`→`说出来`、`探知`→`探索并了解`、`算`→`计算`、`看`→`观察/查看`、`想`→`思考`。
**正例**："觉得疲倦了" / "身体上的疲乏" / "心里有点沉重" / "我们开始计算"。
**反例**："觉得倦了" / "身体上的乏" / "心里有点沉" / "开始算"。
**例外**：真正的祈使指令（"请做这道题""看这里"）可保留简洁动词。

### 规则 2：动宾搭配（动词须自然接宾语）

> **定义**：动词与其宾语语义搭配自然，禁止强行组合、抽象装饰动词。

**触发模式**（`BAD_COLLOCATIONS`）：
```python
(r"带着(重量|分量)", "『带着重量/分量』动宾不通——『带』是随身携带，重量不能随身带")
(r"带着(意义|温度|感情)", "『带着意义/温度/感情』是拟人化装饰，应改为更具体的表达")
(r"做着(思考|努力|准备)", "『做着思考/努力』是凑词式动宾，应改为『正在思考』『正在努力』")
(r"进行(一个)?(分析|讨论|思考)", "『进行分析/讨论』是翻译腔冗余动词，应直接说『分析/讨论』")
```
**修正方向**：`带着重量`→`这句话的分量很重` / `这句话本身已经很重`；`进行一个分析`→`分析`；`做着思考`→`正在思考`。
**正例**："这句话本身，已经有很重的分量。"
**反例**："这句话本身，已经带着重量。"

### 规则 3：悬空宾语（动词缺宾语补足）

> **定义**：动词必须带恰当的宾语，不得悬空。修饰成分残缺须补中心名词。

**触发模式**（`DANGLING_VERBS`）：
```python
(r"与你探讨$|和你探讨$|与你分享$|和你分享$|与您探讨$|与您分享$",
 "『与你探讨/分享』动词悬空缺宾语，应补足为『与你探讨这个问题』『与你分享我的想法』")
(r"与你交流$|和你交流$", "『与你交流』动词悬空缺宾语，应补足为『与你交流我的看法』")
(r"作为(主力|主打|核心|重点|首选|备选)($|[，。；])",
 "『作为主力』修饰成分残缺——『主力』是修饰语，须接中心名词")
```
**修正方向**：`我想与你探讨。`→`我想与你探讨这个问题。`；`作为主力`→`作为主力工具/主要方法`。
**正例**："我想与你探讨这个问题。"
**反例**："我想与你探讨。"

### 规则 4：无主语短语禁止单独成句

> **定义**：老师对学生说话时必须补主语。无主语短语（副词+动词）不得单独成句。

**触发模式**（`NO_SUBJECT_PHRASES`）：
```python
r"^不催你", r"^先不急", r"^先别急", r"^别催",
r"^(不|先|再|别|不必|不要|无需|不需要|不用)(用)?(着急|急着|急|催|担心|怕|慌|赶|抢)",
r"^(别|不要|不必|无需|不用|先别|先不要)(贪|急|慌|怕|赶|抢|省|凑|堆|贪多|一口吃)",
```
**修正方向**：`不催你。`→`老师不催你，你慢慢来。`；`先不急。`→`我们先不着急。`；`别贪多。`→`你不要贪多。`
**正例**："老师不催你，你慢慢来。"
**反例**："不催你。"
**合法省略边界**（三种可省略）：祈使指令 / 上下文同一主语 / 简短应答。

### 规则 5：复合句分句缺主语（因果/转折）

> **定义**：因果/转折复合句的每个分句都应有主语。

**触发模式**（`COMPOUND_PATTERNS`）：
```python
(r"^(因为|由于|既然|如果|虽然|尽管|即使)[^，。；]{1,15}，(所以|因此|但|但是|然而|就|便)(?!.*(我们|我|你|学生|它|他|她))[^，。；]{1,15}$",
 "复合句分句缺主语——『因为…所以…』每个分句都应有主语")
(r"^(虽然|尽管)[^，。；]{1,15}，(但|但是|可是)(?!.*(我们|我|你|学生|它|他|她))[^，。；]{1,15}$",
 "复合句转折分句缺主语——『虽然…但…』分句应有主语")
```
**修正方向**：`因为学习了，进步了。`→`因为学习了，所以我进步了。`；`虽然困难，但要坚持。`→`虽然困难，但我们要坚持。`
**正例**："因为学习了，所以我进步了。"
**反例**："因为学习了，进步了。"

### 规则 6：介词规范（不得悬空/误用/缺失）

> **定义**：介词必须带宾语，不得悬空、误用、缺失。时间/地点/方式状语前须有介词。

**触发模式**（`BAD_PREPOSITIONS`）：
```python
(r"(关于|对于)[^，。；]{1,12}[，。；](?!.*(我们|我|你|学生|它|他|她))",
 "『关于/对于』引出的内容后直接接无主句——介词短语须引出完整主句")
(r"通过[^，。；]{1,12}[，。；](?!.*(我们|我|你|学生|它|他|她))",
 "『通过』须引出对象且后接完整主句——不得悬空")
(r"根据[^，。；]{1,12}[，。；](?!.*(我们|我|你|学生|它|他|她|结论|结果|判断))",
 "『根据』须引出依据且后接完整主句")
(r"把他(帮助|教导|培养|改变)了", "『把』字句误用——『把』须引出受事且动词结构完整")
(r"被[^，。；]{0,6}$", "『被』字句悬空——『被』须引出施事")
```
**修正方向**：`关于学习方面。`→`在学习方面，要重视方法。`；`通过这次讲解，让学生明白了。`→`通过这次讲解，学生明白了导数的意义。`；`把他帮助了。`→`他帮助了那个学生。`；`每天固定时间用`→`在每天固定的时间使用`。
**正例**："通过这次讲解，学生明白了导数的意义。"
**反例**："通过这次讲解，让学生明白了。"

### 规则 7：谓宾补足（"听着你"病句修正）

> **定义**："听"类动词必须带补语（听你说/听你讲讲），禁止"听着你"悬空（缺"听什么"）。

**触发模式**（`_GAFFE_FIX_RULES`，`fix_known_gaffes` 确定性修正）：
```python
_GAFFE_END = r'(?=[。！？!?，,；;：:…]|$)'
(re.compile(r'我在这里听着你' + _GAFFE_END), '我就在这里听你说说'),
(re.compile(r'在这里听着你' + _GAFFE_END), '在这里听你说说'),
(re.compile(r'我听着你' + _GAFFE_END), '我听你说说'),
(re.compile(r'听着你' + _GAFFE_END), '听你说说'),
```
**修正方向**：`我在这里听着你。`→`我就在这里听你说说。`；`你说吧，我听着你。`→`你说吧，我听你说说。`
**正例**："我就在这里听你说说。" / "我在这里听着你说。"（带补语合法）
**反例**："我在这里听着你。"
**关键**：只修**悬空的"听着你"**（后接句末/停顿标点）；"听着你说/听着你讲/听着你的话"等已带补语的合法搭配保持原样。

### 规则 8：语义残缺（形容词+的+缺失中心名词）

> **定义**：抽象名词做宾语时须有中心名词，不悬空；形容词+的 须搭配正确的中心名词。

**触发模式**（`SEMANTIC_ISSUES`）：
```python
(r"最直觉的(地方|角度|层面|方法)", "『最直觉的…』语义不当——『直觉』是名词，应说『最直观的…』")
(r"最基础的(东西|内容)(?=[，。；])", "『最基础的东西/内容』过于笼统，应具体化（『最基础的概念』『最基础的方法』）")
```
**修正方向**：`最直觉的地方`→`最直观的地方`；`最基础的东西`→`最基础的概念/方法`。
**正例**："从最直观的角度看……"
**反例**："从最直觉的地方看……"

### 违禁表达（forbidden · 系统提示词层）

系统提示词 `get_style_prompt("forbidden")` 约束 LLM 禁止：
- **AI 腔套话**：总的来说/综上所述/值得注意的是/让我们一起…
- **空洞大词**：赋能/点亮/激活/重塑/升级/全方位/一站式…
- **伪共情动词**：接住（情绪）/托住/兜住/我懂你/心疼你…（表演关怀非真实陪伴）
- **廉价鼓励**：加油/你真棒/你一定可以…
- **低劣网络用语**：yyds/绝绝子/栓Q/破防/内卷/躺平/宝子/家人们…
- **空洞赞美形容词**：深刻/全面/系统/本质…

---

## 插件化接入（PAEG 主项目）

主项目（教育智能体）通过**唯一适配层** `infra/lang_plugin_bridge.py` 接入：

```python
# PAEG 内改造（示例）
from infra.lang_plugin_bridge import gate_content, gate_short, get_style_prompt, make_refiner

# 原 from services.lang_gate import lang_gate_content → gate_content
# 原 from prompts import LANGUAGE_STYLE → get_style_prompt
# 原 LanguageRefiner(llm) → make_refiner(chat_fn=_safe_chat, llm=llm)
```

**插件化铁律（R20）**：
1. 插件未挂载（import 失败）→ 桥**静默回退** PAEG 原实现
2. PAEG 旧文件（services/lang_gate.py / language_refiner.py / prompts.LANGUAGE_STYLE）**永不删除**
3. 桥是**叠加层**，不是替换层——接入失败零破坏

详见 [docs/integration_paeg.md](docs/integration_paeg.md)。

---

## 测试

```bash
python -m pytest tests/ -q
# 31 项插件测试 + 4 项行为一致性（vs PAEG 原实现 20 段样本字符串相等）
```

## License

MIT（与 PAEG 主项目一致）
