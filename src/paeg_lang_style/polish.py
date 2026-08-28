# -*- coding: utf-8 -*-
"""paeg_lang_style.polish — 全局语言质量修正入口（L-08 兼容入口）。

从 PAEG 教育智能体 services/polish.py 迁移（v0.43）。
所有输出端点统一过 refiner：AI 味 / 省略句 / 动宾搭配触发 → refiner.refine；
任一层异常 → 静默回退原文（不阻塞生成链路）。

插件解耦改造（同 gate.py / refiner.py 的注入式）：refiner 由宿主项目注入。
``polish_text(text, context=None, refiner=None)``：
- 文本为空 → 返回原文
- refiner 未注入 → 仅病句确定性修正（规则兜底，不调 LLM）
- AI 味 ≥0.4 或省略句/动宾搭配命中 → refiner.refine；refined 为空仍回退
- 任何异常 → 静默回退原文
"""

from __future__ import annotations

from typing import Optional

from .ai_taste import detect_ai_taste
from .rules import check_ellipsis, fix_known_gaffes


def polish_text(text: str, context: Optional[str] = None, refiner=None) -> str:
    """全局语言质量修正（L-08）：AI 味/省略句/动宾触发 → refiner.refine。

    修正：无主语短语、动宾搭配不当（带着重量）、AI 腔、省略句——
    保持风格的最小改动。纯规则文本（无触发信号）跳过 LLM 改写（成本考虑）。
    任何异常 → 静默回退原文（不阻塞生成链路）。

    Args:
        text: 待修正文本。
        context: 上下文（可选）。
        refiner: 注入的 LanguageRefiner 实例（None 时仅规则兜底，跳过 refine）。
    """
    if not text or not text.strip():
        return text
    original = text
    try:
        # L0-0 病句确定性修正（规则兜底，对已修正文本幂等）
        text = fix_known_gaffes(text)
        if refiner is None:
            return text
        # 触发条件：AI 味 or 省略句/动宾搭配（check_ellipsis 一并覆盖动宾搭配）
        try:
            ai_prob = detect_ai_taste(text).ai_likelihood
        except Exception:
            ai_prob = 0.2
        has_issues = len(check_ellipsis(text)) > 0
        if ai_prob >= 0.4 or has_issues:
            refined = refiner.refine(text, context=context or "")
            if refined:
                return refined
        return text
    except Exception:
        return original
