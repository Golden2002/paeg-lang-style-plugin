# -*- coding: utf-8 -*-
"""paeg_lang_style.style_presets —— 文体预设（§3.116 ⭐ G-R6）。

对标表 P-02「分领域适配：学术论文/公文/简历/法律文书/通用 ≥5 文体，每文体专属规则包」。

设计：文体 = 术语领域 + 校对侧重说明。术语领域决定 term_guard 加载哪些白名单
（学术→学术术语、法律→法律术语、简历→简历术语），实现"不误改专业词汇"的分文体差异化。
"""
from __future__ import annotations

from typing import Dict, List

# 文体预设：id → {label, term_domains, note}
STYLE_PRESETS: Dict[str, Dict] = {
    "academic": {
        "label": "学术论文",
        "term_domains": ["academic", "resume"],   # 学术术语 + 技术术语
        "note": "保留专业术语准确性，格式规范（引文/参考文献）",
    },
    "official": {
        "label": "公文",
        "term_domains": ["legal"],
        "note": "公文用语庄重简洁，格式规范（标题/落款/编号）",
    },
    "resume": {
        "label": "简历",
        "term_domains": ["resume"],
        "note": "STAR 量化表达，动作动词，术语精确",
    },
    "legal": {
        "label": "法律文书",
        "term_domains": ["legal"],
        "note": "法条引用规范，术语精确，效力层级清晰",
    },
    "general": {
        "label": "通用",
        "term_domains": [],
        "note": "通用校对（无领域术语保护）",
    },
}


def list_styles() -> List[Dict]:
    """文体预设列表（MCP resources 用）。"""
    return [{"id": k, "label": v["label"], "note": v["note"]} for k, v in STYLE_PRESETS.items()]


def style_term_domains(style: str) -> List[str]:
    """文体 → 术语领域列表（供 term_guard 按领域加载白名单）。"""
    return list(STYLE_PRESETS.get(style, STYLE_PRESETS["general"]).get("term_domains", []))


def is_valid_style(style: str) -> bool:
    return style in STYLE_PRESETS
