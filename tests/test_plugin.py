# -*- coding: utf-8 -*-
"""paeg-lang-style 插件测试：规则 / AI 味 / 违禁词 / 风格提示词 / refiner / gate。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_lang_style import (
    fix_known_gaffes, check_ellipsis, detect_ai_taste,
    ForbiddenWords, get_style_prompt, LANGUAGE_STYLE,
    make_refiner, LanguageRefiner, gate_content, gate_short,
)


# ─────────────────────────────────────
# 1. 病句确定性修正（fix_known_gaffes）
# ─────────────────────────────────────
class TestFixKnownGaffes:
    def test_hanging_tingzhe_ni(self):
        """悬空'听着你'缺补语 → 修正为'听你说说'。"""
        assert fix_known_gaffes("我在这里听着你。") == "我就在这里听你说说。"

    def test_other_subject(self):
        assert fix_known_gaffes("老师在这里听着你，你慢慢说。") == "老师在这里听你说说，你慢慢说。"

    def test_bare_wo_tingzhe_ni(self):
        assert fix_known_gaffes("你说吧，我听着你。") == "你说吧，我听你说说。"

    def test_legal_complement_unchanged(self):
        """已带补语的合法搭配必须保持原样（'听着你说'）。"""
        assert fix_known_gaffes("我在这里听着你说，别急。") == "我在这里听着你说，别急。"

    def test_empty_input(self):
        assert fix_known_gaffes("") == ""
        assert fix_known_gaffes("  ") == "  "

    def test_idempotent(self):
        """对已修正文本幂等（不二次破坏）。"""
        once = fix_known_gaffes("我在这里听着你。")
        twice = fix_known_gaffes(once)
        assert once == twice


# ─────────────────────────────────────
# 2. 语法检查（check_ellipsis）
# ─────────────────────────────────────
class TestCheckEllipsis:
    def test_verb_opener(self):
        issues = check_ellipsis("先看一个现象。")
        assert any("省略主语" in i for i in issues)

    def test_no_subject_phrase(self):
        issues = check_ellipsis("不催你，你慢慢来。")
        assert any("缺主语" in i for i in issues)

    def test_bad_collocation(self):
        issues = check_ellipsis("这句话本身，已经带着重量。")
        assert any("动宾搭配" in i for i in issues)

    def test_dangling_verb(self):
        issues = check_ellipsis("我想与你探讨。")
        assert any("悬空宾语" in i for i in issues)

    def test_ellipsis_word(self):
        issues = check_ellipsis("每天固定时间用。")
        assert any("省略词形" in i for i in issues)

    def test_compound_no_subject(self):
        issues = check_ellipsis("因为学习了，进步了。")
        assert any("复合句缺主语" in i for i in issues)

    def test_clean_text_no_issues(self):
        assert check_ellipsis("这道题的思路很清楚，我们一起算一遍。") == []


# ─────────────────────────────────────
# 3. AI 味检测（detect_ai_taste）
# ─────────────────────────────────────
class TestDetectAITaste:
    def test_ai_slang_text(self):
        s = detect_ai_taste("总的来说，让我们一起赋能这个时代，点亮无限可能！")
        assert s.ai_likelihood >= 0.5
        assert s.verdict in ("AI", "Mixed")

    def test_human_text(self):
        s = detect_ai_taste("墨水在水里散开，像一朵迟缓的花。")
        assert s.ai_likelihood < 0.4
        assert s.verdict == "Human"

    def test_empty_text(self):
        s = detect_ai_taste("")
        assert s.verdict == "Human"


# ─────────────────────────────────────
# 4. 动态违禁词库（ForbiddenWords）
# ─────────────────────────────────────
class TestForbiddenWords:
    def test_detect_hits(self):
        fb = ForbiddenWords()
        hits = fb.detect("总的来说，让我们一起加油，赋能未来！")
        assert "总的来说" in hits and "加油" in hits and "赋能" in hits

    def test_dynamic_add_remove(self):
        fb = ForbiddenWords()
        assert fb.add("测试禁词") is True
        assert "测试禁词" in fb.detect("包含 测试禁词 的文本")
        assert fb.remove("测试禁词") is True
        assert "测试禁词" not in fb.detect("包含 测试禁词 的文本")

    def test_load_json(self):
        fb = ForbiddenWords()
        path = os.path.join(os.path.dirname(_SRC), "data", "forbidden_words.json")
        added = fb.load_json(path)
        assert added >= 0  # 不抛异常，合并外部词库

    def test_detect_empty(self):
        fb = ForbiddenWords()
        assert fb.detect("") == []
        assert fb.detect(None if False else "") == []


# ─────────────────────────────────────
# 5. 风格提示词（get_style_prompt）
# ─────────────────────────────────────
class TestStylePrompt:
    def test_all(self):
        s = get_style_prompt("all")
        assert len(s) > 3000
        assert "朴素" in s

    def test_sections(self):
        assert "词法" in get_style_prompt("lexicon")
        assert "主谓宾" in get_style_prompt("syntax")
        assert "伪共情" in get_style_prompt("forbidden")
        assert "循循善诱" in get_style_prompt("weil")

    def test_list_join(self):
        s = get_style_prompt(["weil", "syntax"])
        assert "循循善诱" in s and "主谓宾" in s


# ─────────────────────────────────────
# 6. refiner（P1 ⭐ chat_fn 注入 fail-fast）
# ─────────────────────────────────────
class TestRefiner:
    def test_chat_fn_required(self):
        """P1：chat_fn=None 必须抛 TypeError（插件独立，不依赖宿主项目）。"""
        with pytest.raises(TypeError):
            LanguageRefiner()

    def test_make_refiner_injects(self):
        def mock_chat(system, user, max_tokens=800, **kw):
            return user.replace("让我们一起", "").replace("赋能", "帮助")

        r = make_refiner(chat_fn=mock_chat)
        assert r is not None
        assert r._chat_fn is mock_chat

    def test_refine_rules_without_llm_call(self):
        """无 AI 味的干净文本：不调用 chat_fn，直接返回原文。"""
        calls = []

        def mock_chat(system, user, max_tokens=800, **kw):
            calls.append(1)
            return user

        r = make_refiner(chat_fn=mock_chat)
        out = r.refine("墨水在水里散开，像一朵迟缓的花。")
        assert calls == []  # 规则层已判定无需 LLM
        assert out == "墨水在水里散开，像一朵迟缓的花。"

    def test_refine_ai_text_triggers_chat(self):
        """AI 味文本：调用 chat_fn 改写 + 病句收口。"""
        def mock_chat(system, user, max_tokens=800, **kw):
            return "我就在这里听你说说。"

        r = make_refiner(chat_fn=mock_chat)
        out = r.refine("总的来说，我在这里听着你。让我们一起加油！", max_rounds=1)
        assert "听你说说" in out


# ─────────────────────────────────────
# 7. gate（P2 ⭐ 守门解耦）
# ─────────────────────────────────────
class TestGate:
    def test_gate_content_rule_only(self):
        """gate_content 无 refiner → 纯规则守门（L0 快路径）。"""
        out = gate_content("我在这里听着你。")
        assert out == "我就在这里听你说说。"

    def test_gate_content_with_refiner(self):
        """注入 refiner → L2 深度矫正路径。"""
        def mock_chat(system, user, max_tokens=800, **kw):
            return "我就在这里听你说说。"

        r = make_refiner(chat_fn=mock_chat)
        out = gate_content("总的来说，我在这里听着你。让我们一起加油！", refiner=r)
        assert "听你说说" in out

    def test_gate_short(self):
        out = gate_short("老师在这里听着你。")
        assert "听你说说" in out

    def test_gate_empty(self):
        assert gate_content("") == ""
        assert gate_short("") == ""
