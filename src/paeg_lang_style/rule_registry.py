# -*- coding: utf-8 -*-
"""paeg_lang_style.rule_registry — 可扩充规则集（Oracle §3.109 ⭐ 顶尖化核心）。

**核心设计（用户要求 ⭐）**：
1. **语法规则约束是最重要的部分**——将作为系统提示词的一部分，不论谁用都会拼接进去
2. **语法规则可以扩充**——规则集外置为 JSON，运行时热加载
3. **违禁词等也可以扩充**——forbidden_refs 引用违禁词库，复用同一热加载机制
4. **通则层指挥 LLM 泛化**（prompt_block）而非逐词列举——避免"把倦优化成疲倦"的狭隘性

**Rule 数据模型**（Oracle 方案）：
```python
Rule = {
    "id": "rule-lx-007",              # 稳定 ID（反馈时引用，形成闭环）
    "type": "general"|"explicit",     # general=通则（指挥 LLM）/ explicit=列举（确定性兜底）
    "category": "lexical"|"syntactic"|"punctuation"|"register",  # 规则类别
    "pattern": "正则（检测用）",        # explicit 必填；general 可填（辅助检测）
    "replacement": "替换文本（确定性）", # explicit 确定性替换
    "message": "修正建议（反馈 LLM）",
    "prompt_block": "通则提示词段落（拼进系统提示词）",  # general 必填
    "severity": "high"|"medium"|"low",
    "enabled": true,
    "source": "builtin"|"user",       # 内置 / 用户扩展
    "profile_tags": ["general","teaching","confessional"],  # 适用场景
}
```

**使用**：
```python
from paeg_lang_style.rule_registry import RuleRegistry, BUILTIN_RULES
reg = RuleRegistry()                  # 内置规则
reg.load("data/rules.json")           # 合并用户扩展规则（热加载）
reg.watch("data/rules.json")          # mtime 监听热重载
rules = reg.all()                     # 全部规则
hits = reg.detect(text)               # 检测命中规则（显式层）
prompt = reg.build_prompt("teaching") # 按 profile 拼装系统提示词片段
```
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

# ─────────────────────────────────────
# Rule 数据模型（字典即规则；函数式处理，无 dataclass 依赖，方便 JSON 序列化）
# ─────────────────────────────────────

# 内置规则（通则层 general + 列举层 explicit）
BUILTIN_RULES: List[Dict[str, Any]] = [
    # ═══════════════════════════════════════
    # 通则层（general）：指挥 LLM 泛化 —— 系统提示词主力，谁用都拼
    # ═══════════════════════════════════════
    {
        "id": "rule-lx-general-001",
        "type": "general",
        "category": "lexical",
        "severity": "high",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching", "confessional"],
        "prompt_block": """### 词法完整通则（⭐ 使用完整词，而非记忆个别替换）
凡表达"状态/感受"的单字形容词，一律扩展为完整双字词形：
"倦"→"疲倦"、"乏"→"疲乏"、"沉"→"沉重"、"累"→"疲惫"、"苦"→"苦涩"、
"慌"→"慌乱"、"虚/弱"→"虚弱"、"低"→"低落"、"烦"→"烦躁"、"闷"→"烦闷"、
"困"→"困倦"、"急"→"着急"、"乱"→"慌乱"。
这不是"记住某个替换"，而是**应用通则**——遇到任何单字状态词都自动补全为完整词形。
例外：真正的祈使指令（"请做这道题""看这里"）可保留简洁动词；
单字词本身语义完整且无对应双字词（"走""看""吃"）不受限。""",
        "pattern": r"(倦|乏|沉|累|苦|慌|虚|弱|低|烦|闷|困|急|乱)",
        "message": "存在单字状态词——按词法完整通则应扩展为完整双字词形（倦→疲倦/乏→疲乏/沉→沉重…）",
    },
    {
        "id": "rule-sx-general-001",
        "type": "general",
        "category": "syntactic",
        "severity": "high",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching", "confessional"],
        "prompt_block": """### 句法完整通则（⭐ 每个句子成分齐全，而非修补特定句式）
每个句子必须具有完整的主谓宾（陈述句）或主系表（判断/描述句）结构。每句输出前自查：
1. **有主语吗？** 老师对学生说话时禁止无主语短语单独成句（"不催你。"→"老师不催你，你慢慢来。"）
2. **有谓语吗？** 禁止"没头没尾"的祈使碎片（"一句话总结"→"我们可以用一句话来记住这一点"）
3. **有宾语吗？** 动词必须带恰当宾语（"我想与你探讨。"→"我想与你探讨这个问题。"）
4. **动宾搭配自然吗？** 禁止强行组合（"带着重量"→"有很重的分量"）
5. **介词带宾语了吗？** 禁止悬空（"关于学习方面。"→"在学习方面，要重视方法。"）
6. **复合句分句有主语吗？** （"因为学习了，进步了。"→"因为学习了，所以我进步了。"）
7. **"听"类动词带补语了吗？** 禁止"听着你"悬空（→"听你说说"）
8. **修饰成分够吗？** 抽象名词做宾语须有中心名词（"作为主力"→"作为主力工具"）
9. **状语充分了吗？** 见下方"充分状语通则"（时间/地点/方式/条件状语让句意完整可执行）
合法省略主语仅三种：祈使指令 / 上下文同一主语 / 简短应答。
讲解、总结、承诺、描述——必须显式主语。""",
        "pattern": None,
        "message": "句子成分不完整——句法完整通则要求主谓宾齐全（有主语？有谓语？有宾语？介词带宾语？）",
    },
    {
        "id": "rule-sx-general-002",
        "type": "general",
        "category": "syntactic",
        "severity": "high",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching", "confessional"],
        "prompt_block": """### 充分状语通则（⭐ 输出时指挥 LLM 使用充分的状语）
每个动作/判断都要用**充分的状语**交代清楚——时间、地点、方式、条件、对象、目的，
让句意完整、可执行。禁止输出信息不足的孤零零短句。

**状语类型**（每句输出前自查）：
1. **时间状语**：在/当/每天/先…再…（"你可以在每天固定的时间复习。"而非"复习。"）
2. **地点状语**：在…里/在…处（"在草稿纸上先画一遍。"而非"先画。"）
3. **方式状语**：用/通过/按照/逐步（"用三步拆解这道题。"而非"拆解这道题。"）
4. **条件状语**：如果/只要/当…时（"当你把公因式提出来时，式子就简化了。"）
5. **对象状语**：对/向/给/把（"把这道题的思路讲给小明听。"）
6. **目的状语**：为了/以便（"为了让你看清楚，我们一步步来。"）

**反例 → 正例**：
- ❌ "使用这个软件。"（孤零零） → ✅ "你可以在每天固定的时间使用这个软件。"
- ❌ "复习单词。" → ✅ "你可以在每天睡前用十分钟复习单词。"
- ❌ "化简这个式子。" → ✅ "我们先把括号展开，再化简这个式子。"

**本质**：不是修饰堆砌，而是让每个动作/判断的**对象、方式、目的、关系交代完整**——
宁可多用修饰成分，不可让句子悬空、残缺。这需要你（LLM）生成时主动补足状语。""",
        "pattern": None,
        "message": "句子缺状语——充分状语通则要求时间/地点/方式/条件/对象/目的交代完整（如'复习单词'→'你可以在每天睡前用十分钟复习单词'）",
    },
    # ═══════════════════════════════════════
    # 列举层（explicit）：确定性兜底 —— LLM 不听话时的底线
    # ═══════════════════════════════════════
    {
        "id": "rule-lx-001",
        "type": "explicit",
        "category": "lexical",
        "pattern": r"觉得倦了|感到倦|已倦",
        "replacement": "觉得疲倦了",
        "message": "『倦』是『疲倦』的省略，应改为完整词形『疲倦』",
        "severity": "medium",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching", "confessional"],
        "prompt_block": None,
    },
    {
        "id": "rule-lx-002",
        "type": "explicit",
        "category": "lexical",
        "pattern": r"的乏($|[，。；])",
        "replacement": "的疲乏",
        "message": "『乏』是『疲乏』的省略，应改为完整词形『疲乏』（『身体上的疲乏』）",
        "severity": "medium",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching", "confessional"],
        "prompt_block": None,
    },
    {
        "id": "rule-lx-003",
        "type": "explicit",
        "category": "lexical",
        "pattern": r"道出",
        "replacement": "说出来",
        "message": "『道出』是压缩写法，应改为『说出来』或『说出』",
        "severity": "low",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching"],
        "prompt_block": None,
    },
    {
        "id": "rule-lx-004",
        "type": "explicit",
        "category": "lexical",
        "pattern": r"探知",
        "replacement": "探索并了解",
        "message": "『探知』是压缩写法，应改为『探索并了解』",
        "severity": "low",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching"],
        "prompt_block": None,
    },
    {
        "id": "rule-sx-001",
        "type": "explicit",
        "category": "syntactic",
        "pattern": r"我在这里听着你" + r'(?=[。！？!?，,；;：:…]|$)',
        "replacement": "我就在这里听你说说",
        "message": "『我在这里听着你』是病句——『听』缺补语，应改为『我就在这里听你说说』",
        "severity": "high",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching", "confessional"],
        "prompt_block": None,
    },
    {
        "id": "rule-sx-002",
        "type": "explicit",
        "category": "syntactic",
        "pattern": r'在这里听着你' + r'(?=[。！？!?，,；;：:…]|$)',
        "replacement": "在这里听你说说",
        "message": "『在这里听着你』是病句——『听』缺补语，应改为『在这里听你说说』",
        "severity": "high",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching", "confessional"],
        "prompt_block": None,
    },
    {
        "id": "rule-sx-003",
        "type": "explicit",
        "category": "syntactic",
        "pattern": r"我听着你" + r'(?=[。！？!?，,；;：:…]|$)',
        "replacement": "我听你说说",
        "message": "『我听着你』悬空——『听』缺补语，应改为『我听你说说』",
        "severity": "high",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching", "confessional"],
        "prompt_block": None,
    },
    {
        "id": "rule-sx-004",
        "type": "explicit",
        "category": "syntactic",
        "pattern": r"听着你" + r'(?=[。！？!?，,；;：:…]|$)',
        "replacement": "听你说说",
        "message": "『听着你』悬空——『听』缺补语，应改为『听你说说』",
        "severity": "high",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching", "confessional"],
        "prompt_block": None,
    },
    {
        "id": "rule-sx-005",
        "type": "explicit",
        "category": "syntactic",
        "pattern": r"与你探讨$|和你探讨$|与你分享$|和你分享$|与您探讨$|与您分享$",
        "replacement": None,  # 需 LLM 补宾语（无确定性替换）
        "message": "『与你探讨/分享』动词悬空缺宾语，应补足为『与你探讨这个问题』『与你分享我的想法』",
        "severity": "medium",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching"],
        "prompt_block": None,
    },
    {
        "id": "rule-sx-006",
        "type": "explicit",
        "category": "syntactic",
        "pattern": r"带着(重量|分量)",
        "replacement": None,
        "message": "『带着重量/分量』动宾不通——应说『这句话的分量很重』或『这句话本身已经很重』",
        "severity": "medium",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching", "confessional"],
        "prompt_block": None,
    },
    {
        "id": "rule-sx-007",
        "type": "explicit",
        "category": "syntactic",
        "pattern": r"进行(一个)?(分析|讨论|思考)",
        "replacement": None,
        "message": "『进行分析/讨论』是翻译腔冗余动词，应直接说『分析/讨论』",
        "severity": "low",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching"],
        "prompt_block": None,
    },
    {
        "id": "rule-pn-001",
        "type": "explicit",
        "category": "punctuation",
        "pattern": r"说：\"(?!.*说)",
        "replacement": None,
        "message": "GB/T 15834：插在话语中间的『说/道』后只能用逗号，不能用冒号",
        "severity": "low",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching"],
        "prompt_block": None,
    },
    # 通则层补充：标点规范通则（GB/T 15834-2011 融合）
    {
        "id": "rule-pn-general-001",
        "type": "general",
        "category": "punctuation",
        "severity": "medium",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching"],
        "prompt_block": """### 标点规范（GB/T 15834-2011）
- 句末点号（。！？）独占一字格；引号/括号前半个不落行尾、后半个不落行首。
- 并列词语之间用顿号（、），并列短语之间用逗号（，），第三层不再出现。
- 插在话语中间的"说/道/问"类词语后只能用逗号，不能用冒号。""",
        "pattern": None,
        "message": "标点使用不规范（GB/T 15834-2011）",
    },
]

# ═══════════════════════════════════════════════════════════
# §3.116 ⭐ G-R1 基础级规则库（错别字/标点/格式 ≥50 条）
# 对标表 P-01「基础级：错别字/标点/格式 ≥50 条」——确定性规则兜底
# （元能力 L918：LLM 先判断、规则兜底；错别字是确定性可枚举的，用词表拦截）
# ═══════════════════════════════════════════════════════════

# 易错字词对照表（错误写法 → 正确写法）——明确误用，非两可
_TYPO_FIXES = {
    # 帐/账（"账"用于钱财，"帐"用于帐篷）
    "帐号": "账号", "帐单": "账单", "结帐": "结账", "算帐": "算账",
    "赖帐": "赖账", "帐目": "账目", "帐本": "账本", "转帐": "转账",
    # 象/像（"像"用于相似/图像）
    "好象": "好像", "图象": "图像", "录象": "录像", "影象": "影像",
    "照象": "照相", "摄象": "摄像",
    # 常见易错字
    "按排": "安排", "按装": "安装", "脉博": "脉搏", "松驰": "松弛",
    "精萃": "精粹", "凑和": "凑合", "既使": "即使", "重迭": "重叠",
    "渡假": "度假", "了望": "瞭望", "讫今": "迄今", "座标": "坐标",
    "坐谈": "座谈", "暴炸": "爆炸", "布署": "部署",
    # 成语错别字
    "一愁莫展": "一筹莫展", "再接再励": "再接再厉", "穿流不息": "川流不息",
    "甘败下风": "甘拜下风", "自抱自弃": "自暴自弃", "一如继往": "一如既往",
    "食不裹腹": "食不果腹", "迫不急待": "迫不及待", "世外桃园": "世外桃源",
    "出奇不意": "出其不意", "走头无路": "走投无路", "金榜提名": "金榜题名",
    "谈笑风声": "谈笑风生", "名符其实": "名副其实",
}

for _i, (_wrong, _right) in enumerate(_TYPO_FIXES.items(), 1):
    BUILTIN_RULES.append({
        "id": f"rule-typo-{_i:03d}",
        "type": "explicit",
        "category": "typo",
        "pattern": _wrong,
        "replacement": _right,
        "message": f"『{_wrong}』是错别字，应为『{_right}』",
        "severity": "medium",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching", "confessional", "resume", "legal"],
        "prompt_block": None,
    })

# 标点规范（GB/T 15834-2011 确定性兜底）
_PUNCT_FIXES = [
    (r"。{2,}", "。", "连续句号应为单个句号"),
    (r"，{2,}", "，", "连续逗号应为单个逗号"),
    (r"！{2,}", "！", "连续感叹号应为单个感叹号"),
    (r"？{2,}", "？", "连续问号应为单个问号"),
    (r"；{2,}", "；", "连续分号应为单个分号"),
    (r"：{2,}", "：", "连续冒号应为单个冒号"),
    (r"、{2,}", "、", "连续顿号应为单个顿号"),
    (r"([。！？])，", r"\1", "句末点号后不应跟逗号"),
]
for _i, (_pat, _repl, _msg) in enumerate(_PUNCT_FIXES, 1):
    BUILTIN_RULES.append({
        "id": f"rule-pn-basic-{_i:03d}",
        "type": "explicit",
        "category": "punctuation",
        "pattern": _pat,
        "replacement": _repl,
        "message": _msg,
        "severity": "low",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching", "resume", "legal"],
        "prompt_block": None,
    })

# 格式规范（多余空格/空行）
_FORMAT_FIXES = [
    (r"[ \t]{2,}", " ", "连续空格应压缩为单个空格"),
    (r"\n{3,}", "\n\n", "连续空行应压缩为单个空行"),
    (r"([，。；：、！？])[ ]+", r"\1", "中文标点后不应有多余空格"),
    (r"^[ \t]+", "", "段落首行不应有多余空格（用缩进样式而非空格）"),
    (r"[ \t]+$", "", "行尾不应有多余空格"),
]
for _i, (_pat, _repl, _msg) in enumerate(_FORMAT_FIXES, 1):
    BUILTIN_RULES.append({
        "id": f"rule-fmt-basic-{_i:03d}",
        "type": "explicit",
        "category": "format",
        "pattern": _pat,
        "replacement": _repl,
        "message": _msg,
        "severity": "low",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching", "resume", "legal"],
        "prompt_block": None,
    })

# ═══════════════════════════════════════════════════════════
# §3.116 ⭐ G-R2 语义级规则（用词不当/逻辑矛盾/语义重复——确定性检测）
# 对标表 P-01「语义级：逻辑矛盾/概念混淆/歧义/用词不当」的规则通道
# ═══════════════════════════════════════════════════════════
_SEMANTIC_FIXES = [
    # 语义重复（冗余表述）
    (r"大概(?:也许|或许|可能)", "大概", "『大概也许/大概可能』语义重复，保留其一"),
    (r"大约(?:左右|上下)", "大约", "『大约左右』语义重复，保留其一"),
    (r"免费(?:赠送|奉送)", "免费提供", "『免费赠送』语义重复（免费已含赠送义）"),
    (r"亲自(?:自己|亲手)", "亲自", "『亲自自己』语义重复"),
    (r"重新(?:再次|又)", "重新", "『重新再次』语义重复"),
    (r"(?:彻底|完全)地?全部", "彻底", "『彻底全部』语义重复"),
    (r"出乎意料(?:之外|地意外)", "出乎意料", "『出乎意料之外』语义重复"),
    # 绝对化表述（用词不当——过度断言，建议软化）
    (r"绝对(?:地|的)?(?:正确|错误|没问题)", "基本正确", "『绝对正确/绝对错误』过度绝对化，建议软化"),
    (r"永远(?:不会|不可能|不能)", "不会", "『永远不会』过度绝对化，建议软化"),
    (r"百分之百(?:正确|保证|确定)", "基本确定", "『百分之百确定』过度绝对化，建议软化"),
    (r"毫无(?:例外|问题|悬念)", "基本没有", "『毫无例外』过度绝对化，建议软化"),
    # 逻辑矛盾标志（前后冲突表述）
    (r"既是[^，。]*又(?:不是|并非)", None, "『既是…又不是』逻辑矛盾，请核对表述"),
    (r"(?:完全|彻底)相反(?:却|但)?(?:又)?(?:完全)?一致", None, "『完全相反却一致』逻辑矛盾，请核对表述"),
    # 歧义指代（"这/那/它" 指代不明——需上下文，标记提示）
    (r"这(?:样|么)做(?:是|就)", None, "『这样做』指代不明，建议明确所指对象"),
]

for _i, (_pat, _repl, _msg) in enumerate(_SEMANTIC_FIXES, 1):
    BUILTIN_RULES.append({
        "id": f"rule-sm-{_i:03d}",
        "type": "explicit",
        "category": "semantic",
        "pattern": _pat,
        "replacement": _repl,  # None = 仅检测提示，不自动替换（语义级不改变原意）
        "message": _msg,
        "severity": "medium",
        "enabled": True,
        "source": "builtin",
        "profile_tags": ["general", "teaching", "resume", "legal"],
        "prompt_block": None,
    })


# ─────────────────────────────────────
# RuleRegistry：规则集管理（加载/合并/热重载/检测/拼装提示词）
# ─────────────────────────────────────

class RuleRegistry:
    """规则集注册中心：内置规则 + 用户扩展规则（JSON 热加载）。"""

    def __init__(self, rules: Optional[List[Dict[str, Any]]] = None):
        self._rules: List[Dict[str, Any]] = list(rules if rules is not None else BUILTIN_RULES)
        self._compiled: Dict[str, Optional[re.Pattern]] = {}
        self._watch_path: Optional[str] = None
        self._watch_mtime: float = 0.0

    # ── 规则访问 ──
    def all(self) -> List[Dict[str, Any]]:
        return [dict(r) for r in self._rules]

    def by_id(self, rule_id: str) -> Optional[Dict[str, Any]]:
        for r in self._rules:
            if r.get("id") == rule_id:
                return dict(r)
        return None

    def enabled_rules(self) -> List[Dict[str, Any]]:
        return [r for r in self._rules if r.get("enabled", True)]

    def general_rules(self) -> List[Dict[str, Any]]:
        """通则层规则（指挥 LLM 泛化）。"""
        return [r for r in self.enabled_rules() if r.get("type") == "general"]

    def explicit_rules(self) -> List[Dict[str, Any]]:
        """列举层规则（确定性兜底）。"""
        return [r for r in self.enabled_rules() if r.get("type") == "explicit"]

    # ── 扩充（用户要求 ⭐ 可扩充性）──
    def add_rule(self, rule: Dict[str, Any]) -> bool:
        """运行时新增规则（用户扩展）。同 id 覆盖内置。"""
        for i, r in enumerate(self._rules):
            if r.get("id") == rule.get("id"):
                self._rules[i] = rule
                self._compiled.pop(rule.get("id"), None)
                return True
        self._rules.append(rule)
        return True

    def remove_rule(self, rule_id: str) -> bool:
        """运行时移除规则。"""
        for i, r in enumerate(self._rules):
            if r.get("id") == rule_id:
                self._rules.pop(i)
                self._compiled.pop(rule_id, None)
                return True
        return False

    def load(self, path: Optional[str] = None) -> int:
        """合并外部 JSON 规则集（动态扩充 ⭐）。

        JSON 结构：{"rules": [Rule...]} 或 [Rule...]
        返回新增/覆盖规则数；文件缺失/损坏 → 0（保留现有规则，绝不"清空跑"）。
        """
        if path is None:
            path = os.environ.get("PAEG_RULES_PATH") or os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "data", "rules.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return 0
        new_rules = data.get("rules", []) if isinstance(data, dict) else data
        if not isinstance(new_rules, list):
            return 0
        added = 0
        for r in new_rules:
            if isinstance(r, dict) and r.get("id"):
                # 标记来源为 user（除非覆盖内置时保留原 source）
                if self.by_id(r.get("id")) is None:
                    r.setdefault("source", "user")
                if self.add_rule(r):
                    added += 1
        return added

    def watch(self, path: Optional[str] = None) -> None:
        """监听规则文件 mtime 变更，触发热重载（可扩充性 ⭐）。"""
        if path is None:
            path = os.environ.get("PAEG_RULES_PATH") or os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "data", "rules.json")
        self._watch_path = path
        try:
            self._watch_mtime = os.path.getmtime(path)
        except Exception:
            self._watch_mtime = 0.0

    def check_reload(self) -> bool:
        """检查规则文件是否变更；变更则热重载。返回是否重载。"""
        if not self._watch_path:
            return False
        try:
            mtime = os.path.getmtime(self._watch_path)
        except Exception:
            return False
        if mtime != self._watch_mtime:
            self._watch_mtime = mtime
            self.load(self._watch_path)
            return True
        return False

    # ── 编译缓存（pattern 懒编译 + LRU 防膨胀）──
    def _compile(self, rule_id: str, pattern: str) -> Optional[re.Pattern]:
        if rule_id in self._compiled:
            return self._compiled[rule_id]
        try:
            cp = re.compile(pattern)
        except Exception:
            cp = None
        if len(self._compiled) > 200:  # LRU 简单保护
            self._compiled.clear()
        self._compiled[rule_id] = cp
        return cp

    # ── 检测 ──
    def detect(self, text: str, profile: Optional[str] = None) -> List[Dict[str, Any]]:
        """检测文本命中哪些列举层规则（含通则层带 pattern 的）。

        Returns:
            list[Rule]：命中的规则（含触发详情），供反馈 LLM。
        """
        if not text:
            return []
        hits: List[Dict[str, Any]] = []
        for r in self.enabled_rules():
            if profile and r.get("profile_tags") and profile not in r.get("profile_tags", []):
                continue
            pat = r.get("pattern")
            if not pat:
                continue
            cp = self._compile(r.get("id", ""), pat)
            if cp is None:
                continue
            m = cp.search(text)
            if m:
                hit = dict(r)
                hit["matched"] = m.group(0)
                hits.append(hit)
        return hits

    # ── 确定性替换（列举层兜底）──
    def apply_explicit(self, text: str, profile: Optional[str] = None) -> str:
        """应用列举层确定性替换（仅 replacement 非空的规则）。"""
        if not text:
            return text
        out = text
        for r in self.explicit_rules():
            if profile and r.get("profile_tags") and profile not in r.get("profile_tags", []):
                continue
            repl = r.get("replacement")
            pat = r.get("pattern")
            if not repl or not pat:
                continue
            cp = self._compile(r.get("id", ""), pat)
            if cp is None:
                continue
            out = cp.sub(repl, out)
        return out

    # ── 系统提示词拼装（核心 ⭐ 语法规则是最重要部分，谁用都拼）──
    def build_prompt(self, profile: str = "general", token_budget: int = 800) -> str:
        """按 profile 拼装语法规则系统提示词片段。

        通则层（prompt_block）→ 系统提示词主体（指挥 LLM 泛化）。
        列举层（有 prompt_block 的）→ 补充说明。
        token_budget 防提示词膨胀（超出保留 high severity）。

        Args:
            profile: general / teaching / confessional 场景过滤。
            token_budget: 提示词 token 预算（默认 800）。
        """
        sections: List[str] = []
        budget_used = 0
        # 通则层优先（系统提示词主力）
        for r in sorted(self.general_rules(),
                        key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("severity", "medium"), 1)):
            if profile and r.get("profile_tags") and profile not in r.get("profile_tags", []):
                continue
            block = r.get("prompt_block")
            if not block:
                continue
            if budget_used + len(block) // 4 > token_budget:
                if r.get("severity") != "high":
                    continue  # 预算超限，跳过非 high
            sections.append(block)
            budget_used += len(block) // 4
        # 列举层（含通则性说明的 prompt_block，如标点通则）
        for r in self.explicit_rules():
            block = r.get("prompt_block")
            if not block:
                continue
            if profile and r.get("profile_tags") and profile not in r.get("profile_tags", []):
                continue
            if budget_used + len(block) // 4 > token_budget:
                continue
            sections.append(block)
            budget_used += len(block) // 4
        return "\n\n".join(sections)
