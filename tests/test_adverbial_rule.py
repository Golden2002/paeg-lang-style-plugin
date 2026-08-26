# -*- coding: utf-8 -*-
"""充分状语通则测试（§3.109 用户新增 ⭐）：指挥 LLM 使用充分的状语。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_lang_style.rules_enhanced import (
    check_adverbial_general_rule,
    build_adverbial_rule_prompt,
)
from paeg_lang_style.rule_registry import RuleRegistry


# ─────────────────────────────────────
# 1. 充分状语通则检测
# ─────────────────────────────────────
class TestAdverbialGeneralRule:
    def test_verb_short_sentence(self):
        """动词开头短句（'复习单词。'）缺状语被检测。"""
        issues = check_adverbial_general_rule("复习单词。")
        assert any("状语" in i for i in issues)

    def test_single_verb(self):
        """孤零零单动词（'化简。'）信息不足被检测。"""
        issues = check_adverbial_general_rule("化简。")
        assert len(issues) > 0

    def test_adverbial_complete_not_detected(self):
        """已有充分状语（'你可以在每天睡前用十分钟复习单词。'）不误报。"""
        issues = check_adverbial_general_rule("你可以在每天睡前用十分钟复习单词。")
        assert issues == []

    def test_clean_text(self):
        issues = check_adverbial_general_rule("墨水在水里散开，像一朵迟缓的花。")
        assert issues == []

    def test_prompt_is_general(self):
        prompt = build_adverbial_rule_prompt()
        assert "充分状语通则" in prompt
        assert "时间状语" in prompt
        assert "方式状语" in prompt
        assert "宁可多用修饰成分" in prompt


# ─────────────────────────────────────
# 2. 规则集集成（RuleRegistry 通则层）
# ─────────────────────────────────────
class TestAdverbialInRegistry:
    def test_rule_exists_in_builtin(self):
        """充分状语通则已加入内置规则集（rule-sx-general-002）。"""
        reg = RuleRegistry()
        rule = reg.by_id("rule-sx-general-002")
        assert rule is not None
        assert rule["type"] == "general"
        assert rule["category"] == "syntactic"
        assert "充分状语通则" in rule["prompt_block"]

    def test_prompt_build_includes_adverbial(self):
        """build_prompt 拼接含充分状语通则。"""
        reg = RuleRegistry()
        p = reg.build_prompt("general")
        assert "充分状语通则" in p

    def test_teaching_profile_includes_adverbial(self):
        reg = RuleRegistry()
        p = reg.build_prompt("teaching")
        assert "充分状语通则" in p
