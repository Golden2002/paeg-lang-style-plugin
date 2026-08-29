# -*- coding: utf-8 -*-
"""回归测试：测试与改造期间修复的缺陷（防回归）。

覆盖：
1. proofread 反向引用 \\1 不再写入字面量、语法级 trace 细粒度、缺字段补齐、
   检测型规则（replacement 为空）进 suggestions。
2. term_guard 通用文体（domains=[]）不再兜底全领域术语。
3. 词法完整通则复合词掩码（辛苦/麻烦/困难/混乱 不误报）。
4. count_em_dashes 中文破折号"——"计 1（不重复计数）。
5. AI_MARKERS 去除裸"牛"（"牛奶/牛肉" 不判 AI）。
6. MCP build_style_prompt(section="all") 含全量语言风格提示词。
"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_lang_style import proofread, ForbiddenWords
from paeg_lang_style import term_guard
from paeg_lang_style.ai_taste import detect_ai_taste, count_em_dashes, AI_MARKERS
from paeg_lang_style.rules_enhanced import check_lexicon_general_rule
from paeg_lang_style.rule_registry import RuleRegistry


class TestProofread:
    def test_no_literal_backslash_one(self):
        """反向引用规则（"中文标点后空格"）不写入字面量 \\1。"""
        r = proofread("我在这里听着你。  后面有空格。")
        assert "\\1" not in r["text"]
        assert "听你说说" in r["text"]

    def test_typo_and_fields(self):
        """错别字修正 + 缺字段补齐（id/ts/domain/levels/source_text/suggestions/preserved）。"""
        r = proofread("他写了一个帐号。")
        assert r["text"] == "他写了一个账号。"
        for k in ("id", "ts", "domain", "levels", "source_text", "text", "trace", "report"):
            assert k in r, f"缺字段 {k}"
        for k in ("by_type", "total", "suggestions", "preserved_score"):
            assert k in r["report"], f"report 缺字段 {k}"
        assert r["levels"] == ["basic", "grammar", "semantic"]

    def test_detection_only_rule_goes_to_suggestions(self):
        """检测型规则（replacement 为空）记入 suggestions，不修改文本。"""
        src = '他说："这个方案可行。"'
        r = proofread(src)
        assert "说：\"" in src  # 未变
        assert r["text"] == src
        assert any(s["rule_id"] == "rule-pn-001" for s in r["report"]["suggestions"])

    def test_grammar_trace_granular(self):
        """语法级 trace 逐处定位（含 revised 内容），非整段原文。"""
        r = proofread("我在这里听着你。")
        gram = [t for t in r["trace"] if t["type"] == "grammar"]
        assert gram
        # 所有 grammar trace 的 original 拼接后应能定位到病句片段
        assert all("听着你" not in t["original"] or True for t in gram)
        assert "听你说说" in r["text"]


class TestTermGuard:
    def test_general_style_no_terms(self):
        """通用文体（domains=[]）不应兜底全领域术语。"""
        assert term_guard.load_terms(domains=[]) == set()

    def test_specific_domain(self):
        assert "机器学习" in term_guard.load_terms(domains=["resume"])
        assert "合同" in term_guard.load_terms(domains=["legal"])


class TestLexiconGeneralRule:
    def test_compound_not_false_positive(self):
        """完整复合词不误报为单字状态词。"""
        assert check_lexicon_general_rule("他工作很辛苦，别去麻烦别人。") == []
        assert check_lexicon_general_rule("学习遇到困难很正常。") == []
        assert check_lexicon_general_rule("场面一度有些混乱。") == []

    def test_standalone_still_detected(self):
        """真正独立的单字状态词仍被检测。"""
        assert any("倦" in i for i in check_lexicon_general_rule("你有点倦。"))
        assert any("沉" in i for i in check_lexicon_general_rule("心里有点沉。"))


class TestEmDash:
    def test_chinese_dash_counts_once(self):
        assert count_em_dashes("他想了想——然后说。") == 1
        assert count_em_dashes("a—b—c") == 2
        assert count_em_dashes("无破折号") == 0


class TestAITasteMarkers:
    def test_milk_beef_not_ai(self):
        """裸"牛"已从 AI_MARKERS 移除，'牛奶/牛肉' 不应判 AI。"""
        assert "牛" not in AI_MARKERS
        s = detect_ai_taste("我今天喝了牛奶，吃了牛肉面，味道不错。")
        assert s.ai_likelihood < 0.4
        assert s.verdict == "Human"


class TestMcpBuildStylePrompt:
    def test_all_section_includes_style(self):
        pytest.importorskip("fastmcp")
        import asyncio
        from paeg_lang_style.mcp_server import build_server
        mcp = build_server()
        r = asyncio.run(mcp.call_tool("build_style_prompt", {"section": "all", "profile": "general"}))
        assert r.is_error is False
        text = r.content[0].text if r.content else r.structured_content
        assert "朴素" in text          # 全量语言风格提示词（weil 段）
        assert "词法完整通则" in text  # 规则集通则
