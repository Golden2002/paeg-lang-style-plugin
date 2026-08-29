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

import difflib
from typing import Optional

from .rules import fix_known_gaffes
from .ai_taste import detect_ai_taste


def preserve_check(original: str, revised: str, threshold: float = 0.95) -> dict:
    """§3.116 ⭐ G-R7 原意保持校验：改写前后相似度 ≥ threshold 才算达标。

    对标表 P-05「语义级改写约束 + 原意保持校验（相似度阈值 ≥95%），
    不达标降级为"仅建议不自动替换"」。

    相似度 = 字符级 SequenceMatcher 相似度（中文按字符，英文按字符序列）。
    """
    import difflib
    if original == revised:
        return {"ok": True, "similarity": 1.0}
    if not original or not revised:
        return {"ok": False, "similarity": 0.0}
    sim = difflib.SequenceMatcher(None, original, revised).ratio()
    return {"ok": sim >= threshold, "similarity": round(sim, 4)}


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
                    # §3.116 ⭐ G-R7 原意保持：LLM 改写后相似度 ≥95% 才采用，
                    # 否则回退原文（仅建议不自动替换——不改变原文核心意思）
                    _pc = preserve_check(_out, _refined)
                    if _pc["ok"]:
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


def _term_spans(text: str, terms) -> list:
    """计算术语白名单词在原文中的字符区间（长词优先，避免子串截断）。"""
    import re as _re
    spans = []
    for term in sorted(terms, key=len, reverse=True):
        for m in _re.finditer(_re.escape(term), text):
            spans.append((m.start(), m.end()))
    return spans


def _overlaps(start: int, end: int, spans: list) -> bool:
    return any(s < end and e > start for s, e in spans)


def proofread(text: str, context: str = "",
              levels: Optional[tuple] = None, style: str = "general") -> dict:
    """§3.116 ⭐ G-R5 全流水线校对：返回修订痕迹 + 校对报告（可追溯输出）。

    对标表 P-04「修订痕迹（位置/原文/改文/理由/类型）+ 校对报告（问题类型统计）」。
    数据模型对齐 docs/05_技术架构设计 §5 ProofreadResult：
    {id, ts, domain, levels, source_text, text, trace, report{by_type, total, suggestions, preserved_score}}。

    Args:
        text: 待校对文本。
        levels: 分级开关（默认 basic+grammar+semantic）。
        style: 文体预设（academic/official/resume/legal/general）——G-R6 分领域适配。

    Returns:
        dict：修正后文本 + 逐条修订痕迹 + 结构化校对报告。
        检测型规则（replacement 为空的语义/语用/篇章规则）记入 report.suggestions，
        不自动替换（语义级不改变原意）。
    """
    import time
    import uuid
    from .rule_registry import RuleRegistry
    from .term_guard import load_terms
    from .style_presets import style_term_domains

    _levels = list(levels) if levels else ["basic", "grammar", "semantic"]
    result = {
        "id": uuid.uuid4().hex[:12],
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "domain": style,
        "style": style,
        "levels": _levels,
        "source_text": text,
        "text": text,
        "trace": [],
        "report": {"by_type": {}, "total": 0, "suggestions": [], "preserved_score": 1.0},
    }
    if not text or not text.strip():
        return result
    levels = tuple(_levels)
    reg = RuleRegistry()
    terms = load_terms(domains=style_term_domains(style))
    spans = _term_spans(text, terms)  # 术语白名单区间（G-R4：术语不参与替换）

    suggestions = []

    def _apply_and_trace(categories: tuple, target: str) -> str:
        """应用指定类别的确定性规则并记录 trace；返回新文本。

        - 有 replacement 的规则：替换 + 记 trace（用 m.expand 正确展开 \\1 反向引用）。
        - 无 replacement 的检测型规则：命中记入 suggestions，不修改文本。
        """
        out = target
        for r in reg.explicit_rules():
            if r.get("category") not in categories:
                continue
            pat = r.get("pattern")
            repl = r.get("replacement")
            if not pat:
                continue
            cp = reg._compile(r.get("id", ""), pat)
            if cp is None:
                continue
            if repl is None or repl == "":
                for m in cp.finditer(out):
                    if _overlaps(m.start(), m.end(), spans):
                        continue
                    suggestions.append({
                        "pos": m.start(), "original": m.group(0),
                        "reason": r.get("message", ""), "type": r.get("category", ""),
                        "rule_id": r.get("id"),
                    })
                continue

            def _sub(m, _repl=repl, _r=r):
                if _overlaps(m.start(), m.end(), spans):
                    return m.group(0)  # 术语保护：命中落在白名单内，不改
                revised = m.expand(_repl)  # 处理 \\1 等反向引用，避免写入字面量
                result["trace"].append({
                    "pos": m.start(), "original": m.group(0), "revised": revised,
                    "reason": _r.get("message", ""), "type": _r.get("category", ""),
                    "rule_id": _r.get("id"),
                })
                _t = _r.get("category", "")
                result["report"]["by_type"][_t] = result["report"]["by_type"].get(_t, 0) + 1
                return revised

            out = cp.sub(_sub, out)
        return out

    _out = text
    if "basic" in levels:
        _out = _apply_and_trace(("typo", "punctuation", "format"), _out)
    if "semantic" in levels:
        # 语义级含检测型规则（replacement 为空 → 仅建议）；语用/篇章层一并检测提示
        _out = _apply_and_trace(("semantic", "pragmatic", "discourse"), _out)
    if "grammar" in levels:
        _before = _out
        _out = fix_known_gaffes(_out)
        if _out != _before:
            # 用 difflib 生成细粒度病句修订痕迹（逐处定位）；合并相邻的非 equal 操作块
            _merged = []
            for _op in difflib.SequenceMatcher(None, _before, _out).get_opcodes():
                if _op[0] == "equal":
                    continue
                if _merged and _merged[-1]["i2"] == _op[1]:
                    _merged[-1]["i2"] = _op[2]
                    _merged[-1]["j2"] = _op[4]
                else:
                    _merged.append({"i1": _op[1], "i2": _op[2], "j1": _op[3], "j2": _op[4]})
            for _m in _merged:
                result["trace"].append({
                    "pos": _m["i1"], "original": _before[_m["i1"]:_m["i2"]],
                    "revised": _out[_m["j1"]:_m["j2"]],
                    "reason": "语法级病句修正（fix_known_gaffes）", "type": "grammar",
                })
                _t = "grammar"
                result["report"]["by_type"][_t] = result["report"]["by_type"].get(_t, 0) + 1
    result["text"] = _out
    result["report"]["total"] = len(result["trace"])
    result["report"]["suggestions"] = suggestions
    # 原意保持：确定性替换基本不改动语义，按字符相似度给出可参考分数
    if text and _out:
        result["report"]["preserved_score"] = round(
            difflib.SequenceMatcher(None, text, _out).ratio(), 4)
    return result
