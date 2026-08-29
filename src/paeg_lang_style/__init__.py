# -*- coding: utf-8 -*-
"""paeg_lang_style — PAEG 语言规范插件（可拆卸、可独立、可接入教育智能体）。

用户需求 ⭐：语言规范模块应当包含——
1. **系统提示词约束**：从词法、句法的规则对 LLM 进行约束（prompts.language_style）
2. **动态违禁词库**：动态维护的违禁词库（forbidden.ForbiddenWords）
3. **重写大模型输出的工具**（refiner.LanguageRefiner）

三大架构模式（librarian 调研）：
- 规则声明式引擎（LanguageTool 范式）→ rules.py（词法/句法规则 + 正则模式）
- 公式度量（textstat 范式）→ ai_taste.py（可读性/变异度指标）
- 中文特化预处理 → rules.py 的正则分句检测

对外 API（Oracle R10-R13）：
    gate_content(text, context="", apply_l2=True, refiner=None, polish_fn=None) -> str
    gate_short(text, context="", refiner=None, polish_fn=None) -> str
    polish_text(text, context=None, refiner=None) -> str
    make_refiner(*, chat_fn, llm=None, corpus_path=None) -> LanguageRefiner
    get_style_prompt(section="all") -> str
    fix_known_gaffes(text) -> str
    check_ellipsis(text) -> list
    detect_ai_taste(text) -> AITasteSignals
    ForbiddenWords() -> 动态违禁词库

零宿主依赖：本包不 import PAEG 任何模块（services/infra/subagents/prompts），
任意项目 `pip install` 或 `sys.path` 加入即可独立使用。
"""

from __future__ import annotations

from .rules import (
    check_ellipsis,
    fix_known_gaffes,
    ELLIPSIS_WORDS,
    NO_SUBJECT_PHRASES,
    COMPOUND_PATTERNS,
    BAD_COLLOCATIONS,
    SEMANTIC_ISSUES,
    DANGLING_VERBS,
    BAD_PREPOSITIONS,
    VERB_OPENERS,
)
from .ai_taste import (
    detect_ai_taste,
    AITasteSignals,
    measure_burstiness,
    measure_marker_density,
    count_three_lists,
    count_em_dashes,
    measure_paragraph_symmetry,
)
from .forbidden import ForbiddenWords, _BUILTIN_FORBIDDEN
from .refiner import LanguageRefiner, make_refiner
from .gate import gate_content, gate_short, proofread
from .polish import polish_text
from .prompts.language_style import LANGUAGE_STYLE, get_style_prompt
from .rules_enhanced import (
    check_lexicon_general_rule,
    check_syntax_general_rule,
    check_adverbial_general_rule,
    build_lexicon_rule_prompt,
    build_syntax_rule_prompt,
    build_adverbial_rule_prompt,
    SINGLE_CHAR_STATE_WORDS,
)
from .rule_registry import RuleRegistry, BUILTIN_RULES

__version__ = "0.1.0"

__all__ = [
    # 核心 API
    "gate_content", "gate_short", "polish_text", "proofread",
    "make_refiner", "LanguageRefiner",
    "get_style_prompt", "LANGUAGE_STYLE",
    # 规则
    "check_ellipsis", "fix_known_gaffes",
    "ELLIPSIS_WORDS", "NO_SUBJECT_PHRASES", "COMPOUND_PATTERNS",
    "BAD_COLLOCATIONS", "SEMANTIC_ISSUES", "DANGLING_VERBS",
    "BAD_PREPOSITIONS", "VERB_OPENERS",
    # AI 味检测
    "detect_ai_taste", "AITasteSignals",
    "measure_burstiness", "measure_marker_density",
    "count_three_lists", "count_em_dashes", "measure_paragraph_symmetry",
    # 违禁词库
    "ForbiddenWords", "_BUILTIN_FORBIDDEN",
    # 通则化增强（§3.109 ⭐ 指挥 LLM 使用完整词，而非逐词修补）
    "check_lexicon_general_rule", "check_syntax_general_rule",
    "check_adverbial_general_rule",
    "build_lexicon_rule_prompt", "build_syntax_rule_prompt",
    "build_adverbial_rule_prompt",
    "SINGLE_CHAR_STATE_WORDS",
    # 可扩充规则集（Oracle §3.109 ⭐ 语法规则可扩充，作为系统提示词核心）
    "RuleRegistry", "BUILTIN_RULES",
    # 元信息
    "__version__",
]
