# -*- coding: utf-8 -*-
"""paeg_lang_style.term_guard —— 术语白名单保护（§3.116 ⭐ G-R4）。

对标表 P-03「术语保护：术语白名单不误改专业词汇，术语误改率 0」。
方向与 forbidden.py（禁词黑名单）相反：黑名单是"禁止出现"，白名单是"禁止误改"。

机制：校对替换前把白名单词用占位符（__TERM_{i}__）隔离，规则替换后还原——
白名单词不参与任何基础级/语法级替换，术语误改率 0。

术语表：data/term_whitelist.json（领域分类，可扩展）+ 内置兜底。
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Set

# 内置术语兜底（JSON 缺失时；领域 → 术语）
_BUILTIN_TERMS: Dict[str, List[str]] = {
    "legal": [
        "民法典", "司法解释", "合同", "要约", "承诺", "违约责任", "管辖权",
        "诉讼时效", "举证责任", "侵权责任", "债权", "物权", "抵押权", "质权",
        "不可抗力", "情势变更", "违约责任", "定金", "违约金",
    ],
    "academic": [
        "现象学", "本体论", "认识论", "范式", "实证", "阐释", "解构",
        "符号学", "阐释学", "认识", "存在主义", "先验", "超验",
    ],
    "resume": [
        "机器学习", "深度学习", "自然语言处理", "数据挖掘", "敏捷开发",
        "Scrum", "KPI", "OKR", "MVP", "A/B测试",
    ],
    "medical": [
        "安慰剂", "双盲", "循证医学", "随机对照", "队列研究", "荟萃分析",
    ],
}


def _default_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "term_whitelist.json")


def load_terms(path: str = None) -> Set[str]:
    """加载术语白名单（JSON 优先，缺失时内置兜底）。"""
    terms: Set[str] = set()
    p = path or _default_path()
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for lst in data.values():
                if isinstance(lst, list):
                    terms.update(str(t).strip() for t in lst if str(t).strip())
    except Exception:
        pass
    if not terms:
        for lst in _BUILTIN_TERMS.values():
            terms.update(t for t in lst)
    return {t for t in terms if len(t) >= 2}


def protect(text: str, terms: Set[str]) -> tuple:
    """用占位符隔离白名单词，返回 (保护后文本, 还原映射)。

    placeholders: {placeholder: original_term}
    """
    placeholders: Dict[str, str] = {}
    if not terms or not text:
        return text, placeholders

    # 按长度降序排序（长术语优先替换，避免"合同"截断"违约责任"内的词）
    sorted_terms = sorted(terms, key=len, reverse=True)

    def _sub(m):
        term = m.group(0)
        key = f"__TERM_{len(placeholders)}__"
        placeholders[key] = term
        return key

    out = text
    for term in sorted_terms:
        if term in out:
            # re.sub 支持函数替换（每个匹配生成唯一占位符）
            out = re.sub(re.escape(term), _sub, out)
    return out, placeholders


def restore(text: str, placeholders: Dict[str, str]) -> str:
    """还原占位符为原始术语。"""
    out = text
    for key, term in placeholders.items():
        out = out.replace(key, term)
    return out


def protect_and_restore(text: str, terms: Set[str], apply_fn) -> str:
    """术语保护执行：保护 → apply_fn 替换 → 还原。

    apply_fn: 接受保护后文本，返回替换后文本（基础级/语法级规则替换）。
    """
    if not text or not terms:
        return apply_fn(text)
    protected, placeholders = protect(text, terms)
    replaced = apply_fn(protected)
    return restore(replaced, placeholders)
