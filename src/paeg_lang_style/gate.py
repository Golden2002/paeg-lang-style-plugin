# -*- coding: utf-8 -*-
"""paeg_lang_style.gate — 语言规范守门（L0 + L1 + L2 三层接入生成链路）。

从 PAEG 教育智能体 services/lang_gate.py 迁移（v0.66 ⭐ L0+L1+L2 三层）。

- L0：病句确定性修正（fix_known_gaffes 规则）+ polish_text（AI 味/省略句/动宾搭配修正）
- L1：提示词层语言规范约束（LANGUAGE_STYLE 注入，由生成函数自行拼入）
- L2：refiner.refine 深度矫正（语料多轮 Self-Refine）

**P2 守门解耦改造 ⭐**：原 PAEG 版 lang_gate 通过 `infra.runtime.get_paeg()` 拉起
整套 PAEG 运行时（LLM/KB/Library）——插件独立运行时不可用。
本插件版改为**注入式**：`refiner: Optional[RefinerProtocol] = None` 参数，
None 时跳过 L2 路径（纯规则守门），由宿主项目注入 refiner 实例即启用 L2。

用法：
    from paeg_lang_style.gate import gate_content, gate_short
    out = gate_content(text, context="")                 # 纯规则（L0 快路径）
    out = gate_content(text, context="", refiner=my_refiner)  # L0 + L2 全量
"""

from __future__ import annotations

from typing import Optional

from .rules import fix_known_gaffes
from .ai_taste import detect_ai_taste


def gate_content(text: str, context: str = "", apply_l2: bool = True,
                 refiner=None, polish_fn=None) -> str:
    """生成内容语言规范守门（L0 + L2）。

    - L0 polish：AI 味检测 + 省略句 + 动宾搭配 → 触发 refine
    - L2 refine：AI 味信号强时，用语料多轮 Self-Refine 深度矫正
    任一层异常 → 静默回退原文（不阻塞生成）。

    Args:
        text: 待守门文本。
        context: 上下文（可选）。
        apply_l2: 是否启用 L2 深度矫正（默认 True）。
        refiner: 注入的 LanguageRefiner 实例（None 时跳过 L2）。
        polish_fn: 注入的基础语言修正函数（默认用 refiner.refine 兜底；
                   不传则跳过 polish 层）。
    """
    if not text or not text.strip():
        return text
    _out = text
    # ── L0-0：病句确定性修正（规则兜底，不依赖 AI 味检测）──
    _out = fix_known_gaffes(_out)
    # ── L0：基础语言修正（注入式 polish_fn；缺省跳过，靠 L2 深度矫正）──
    if polish_fn is not None:
        try:
            _out = polish_fn(_out, context=context)
        except Exception:
            pass
    # ── L2：AI 味深度矫正（仅当注入 refiner 且仍有明显信号）──
    if apply_l2 and refiner is not None:
        try:
            _sig = detect_ai_taste(_out)
            if getattr(_sig, 'ai_likelihood', 0) >= 0.45:
                _refined = refiner.refine(_out, context=context, max_rounds=1)
                if _refined:
                    _out = _refined
        except Exception:
            pass
    # ── 最终收口：病句规则再跑一遍（refine 改写可能重新引入悬空'听着你'）──
    _out = fix_known_gaffes(_out)
    return _out


def gate_short(text: str, context: str = "", refiner=None, polish_fn=None) -> str:
    """短文本语言守门（讲稿单段/要点）：仅 L0，快路径。"""
    if not text or not text.strip():
        return text
    _out = fix_known_gaffes(text)
    if polish_fn is not None:
        try:
            _out = polish_fn(_out, context=context)
        except Exception:
            return _out
    return fix_known_gaffes(_out)
