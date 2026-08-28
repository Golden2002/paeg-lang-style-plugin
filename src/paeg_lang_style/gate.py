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


def _apply_categories(text: str, categories: tuple) -> str:
    """§3.116 ⭐ G-R3 分级执行：应用指定类别的确定性规则（有 replacement 才替换）。

    §3.116 ⭐ G-R4 术语保护：白名单词（法律/学术/简历/医学术语）先用占位符隔离，
    规则替换后还原——术语不参与替换，误改率 0。
    """
    try:
        from .rule_registry import RuleRegistry
        from .term_guard import load_terms, protect_and_restore
        reg = RuleRegistry()
        terms = load_terms()

        def _replace(t: str) -> str:
            out = t
            for r in reg.explicit_rules():
                if r.get("category") not in categories:
                    continue
                pat = r.get("pattern")
                repl = r.get("replacement")
                if not pat or not repl:
                    continue  # 无 replacement 的检测型规则不自动替换
                cp = reg._compile(r.get("id", ""), pat)
                if cp is not None:
                    out = cp.sub(repl, out)
            return out

        return protect_and_restore(text, terms, _replace)
    except Exception:
        return text


def gate_content(text: str, context: str = "", apply_l2: bool = True,
                 refiner=None, polish_fn=None,
                 levels: Optional[tuple] = None) -> str:
    """生成内容语言规范守门（三级校对 + L0 + L2）。

    §3.116 ⭐ G-R3 三级开关（levels 参数，对齐对标表 P-01「三级可独立开关」）：
    - basic：基础级（错别字/标点/格式）——确定性替换
    - grammar：语法级（病句 fix_known_gaffes + polish_fn）
    - semantic：语义级（语义重复替换；逻辑矛盾/歧义仅检测提示，不改变原意）
    levels=None 时默认全三级（basic+grammar+semantic）。

    - L0 polish：AI 味检测 + 省略句 + 动宾搭配 → 触发 refine
    - L2 refine：AI 味信号强时，用语料多轮 Self-Refine 深度矫正
    任一层异常 → 静默回退原文（不阻塞生成）。
    """
    if not text or not text.strip():
        return text
    levels = tuple(levels) if levels else ("basic", "grammar", "semantic")
    _out = text
    # ── 基础级：错别字/标点/格式（G-R1 确定性替换）──
    if "basic" in levels:
        _out = _apply_categories(_out, ("typo", "punctuation", "format"))
    # ── 语法级：病句确定性修正（规则兜底，不依赖 AI 味检测）──
    if "grammar" in levels:
        _out = fix_known_gaffes(_out)
    # ── 语义级：语义重复替换（矛盾/歧义仅检测，不自动改，保原意）──
    if "semantic" in levels:
        _out = _apply_categories(_out, ("semantic",))
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
    if "grammar" in levels:
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


def proofread(text: str, context: str = "",
              levels: Optional[tuple] = None) -> dict:
    """§3.116 ⭐ G-R5 全流水线校对：返回修订痕迹 + 校对报告（可追溯输出）。

    对标表 P-04「修订痕迹（位置/原文/改文/理由/类型）+ 校对报告（问题类型统计）」。

    Args:
        text: 待校对文本。
        levels: 分级开关（默认 basic+grammar+semantic）。

    Returns:
        {text(修正后), trace([{pos, original, revised, reason, type}]), report({by_type, total})}
        每条修改可定位（pos 为修正前位置）、可解释（reason/type）。
    """
    from .rule_registry import RuleRegistry
    from .term_guard import load_terms, protect_and_restore
    result = {"text": text, "trace": [], "report": {"by_type": {}, "total": 0}}
    if not text or not text.strip():
        return result
    levels = tuple(levels) if levels else ("basic", "grammar", "semantic")
    reg = RuleRegistry()
    terms = load_terms()

    def _apply_and_trace(categories: tuple, target: str) -> str:
        out = target
        for r in reg.explicit_rules():
            if r.get("category") not in categories:
                continue
            pat = r.get("pattern")
            repl = r.get("replacement")
            if not pat or not repl:
                continue
            cp = reg._compile(r.get("id", ""), pat)
            if cp is None:
                continue

            def _sub(m, _repl=repl, _r=r):
                _orig = m.group(0)
                result["trace"].append({
                    "pos": m.start(), "original": _orig, "revised": _repl,
                    "reason": _r.get("message", ""), "type": _r.get("category", ""),
                })
                _t = _r.get("category", "")
                result["report"]["by_type"][_t] = result["report"]["by_type"].get(_t, 0) + 1
                return _repl

            out = cp.sub(_sub, out)
        return out

    _out = text
    # 基础级 + 语义级（RuleRegistry 规则，精确记录 trace）
    if "basic" in levels:
        _out = protect_and_restore(_out, terms,
                                   lambda t: _apply_and_trace(("typo", "punctuation", "format"), t))
    if "semantic" in levels:
        _out = protect_and_restore(_out, terms,
                                   lambda t: _apply_and_trace(("semantic",), t))
    # 语法级（病句 fix_known_gaffes——前后对比记录 trace）
    if "grammar" in levels:
        _before = _out
        _out = fix_known_gaffes(_out)
        if _out != _before:
            result["trace"].append({
                "pos": 0, "original": _before, "revised": _out,
                "reason": "语法级病句修正（fix_known_gaffes）", "type": "grammar",
            })
            _t = "grammar"
            result["report"]["by_type"][_t] = result["report"]["by_type"].get(_t, 0) + 1
    result["text"] = _out
    result["report"]["total"] = len(result["trace"])
    return result
