# -*- coding: utf-8 -*-
"""通则化增强测试（§3.109 ⭐）：词法完整通则 + 句法完整通则——指挥 LLM 泛化，非逐词修补。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_lang_style.rules_enhanced import (
    check_lexicon_general_rule,
    check_syntax_general_rule,
    build_lexicon_rule_prompt,
    build_syntax_rule_prompt,
)
from paeg_lang_style.refiner import make_refiner


# ─────────────────────────────────────
# 1. 词法完整通则（通则推理，非列举）
# ─────────────────────────────────────
class TestLexiconGeneralRule:
    def test_single_char_state_word_detected(self):
        """单字状态词（倦）被通则检测，提示扩展为完整词形。"""
        issues = check_lexicon_general_rule("你有点倦，想和你探讨。")
        assert any("倦" in i and "疲倦" in i for i in issues)

    def test_already_full_form_skipped(self):
        """已是完整词形（疲倦）时不误报。"""
        issues = check_lexicon_general_rule("你有点疲倦了，想和你探讨。")
        assert not any("倦" in i for i in issues)

    def test_multiple_state_words(self):
        """多个单字状态词同时检测（沉/乏）。"""
        issues = check_lexicon_general_rule("心里有点沉，身体上的乏还没缓过来。")
        assert any("沉" in i for i in issues)
        assert any("乏" in i for i in issues)

    def test_clean_text_no_issues(self):
        issues = check_lexicon_general_rule("墨水在水里散开，像一朵迟缓的花。")
        assert issues == []

    def test_prompt_is_general_rule_not_list(self):
        """通则提示词强调'应用通则'而非'记住替换'——本质是指挥 LLM 泛化。"""
        prompt = build_lexicon_rule_prompt()
        assert "通则" in prompt
        assert "扩展为完整双字词形" in prompt
        assert "不是修补特定词" in prompt  # 明确反对列举式


# ─────────────────────────────────────
# 2. 句法完整通则（句子成分齐全）
# ─────────────────────────────────────
class TestSyntaxGeneralRule:
    def test_no_subject_general(self):
        """无主语短语单独成句被通则检测（非列举）。"""
        issues = check_syntax_general_rule("别贪多，一口吃不成胖子。")
        assert any("无主语" in i or "缺主语" in i for i in issues)

    def test_dangling_general(self):
        issues = check_syntax_general_rule("我想与你探讨。")
        assert any("悬空" in i or "宾语" in i for i in issues)

    def test_compound_general(self):
        issues = check_syntax_general_rule("因为学习了，进步了。")
        assert any("复合句" in i or "缺主语" in i for i in issues)

    def test_preposition_general(self):
        """介词悬空（'关于…方面。' 单独成句缺主句）被通则检测。"""
        issues = check_syntax_general_rule("关于学习方面。")
        assert any("介词" in i or "无主句" in i or "主句" in i for i in issues)

    def test_preposition_through_complete(self):
        """'通过这次讲解，学生明白了'（有完整主语）不误报。"""
        issues = check_syntax_general_rule("通过这次讲解，学生明白了导数的意义。")
        # 可能有 base 检测命中，但不该有"介词悬空"误报
        assert not any("介词短语后接无主句" in i for i in issues)

    def test_clean_text_no_issues(self):
        issues = check_syntax_general_rule("墨水在水里散开，像一朵迟缓的花。")
        assert issues == []

    def test_prompt_is_general(self):
        prompt = build_syntax_rule_prompt()
        assert "通则" in prompt
        assert "主谓宾" in prompt
        assert "自查" in prompt


# ─────────────────────────────────────
# 3. 通则与列举式的关系（refiner 集成）
# ─────────────────────────────────────
class TestGeneralRuleIntegration:
    def test_refiner_system_includes_general_rules(self):
        """refiner 的 system prompt 包含通则提示词（指挥 LLM 应用通则）。"""
        def mock_chat(system, user, max_tokens=800, **kw):
            return user

        r = make_refiner(chat_fn=mock_chat)
        system = r._build_system()
        assert "词法完整通则" in system
        assert "句法完整通则" in system
        assert "应用通则" in system  # 明确指挥 LLM 泛化

    def test_refiner_feedback_includes_general(self):
        """refiner 反馈包含通则检测结果。"""
        def mock_chat(system, user, max_tokens=800, **kw):
            return "你有点疲倦了，想和你探讨这个问题。"

        r = make_refiner(chat_fn=mock_chat)
        feedback = r._get_feedback("你有点倦，想和你探讨。")
        assert "词法完整通则" in feedback or "倦" in feedback
