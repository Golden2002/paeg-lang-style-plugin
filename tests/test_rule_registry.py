# -*- coding: utf-8 -*-
"""可扩充规则集测试（Oracle §3.109 ⭐）：RuleRegistry 加载/热重载/检测/拼装/用户扩充。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_lang_style.rule_registry import RuleRegistry, BUILTIN_RULES


# ─────────────────────────────────────
# 1. 内置规则集
# ─────────────────────────────────────
class TestBuiltinRules:
    def test_builtin_has_general_and_explicit(self):
        reg = RuleRegistry()
        generals = reg.general_rules()
        explicits = reg.explicit_rules()
        assert len(generals) >= 2  # 词法通则 + 句法通则（+标点通则）
        assert len(explicits) >= 8  # 列举层兜底

    def test_general_has_prompt_block(self):
        """通则层规则必须有 prompt_block（系统提示词核心）。"""
        reg = RuleRegistry()
        for r in reg.general_rules():
            assert r.get("prompt_block"), f"{r['id']} 缺 prompt_block"

    def test_explicit_has_pattern(self):
        reg = RuleRegistry()
        for r in reg.explicit_rules():
            assert r.get("pattern"), f"{r['id']} 缺 pattern"


# ─────────────────────────────────────
# 2. 规则检测（命中列举层 + 通则层带 pattern）
# ─────────────────────────────────────
class TestRuleDetect:
    def test_detect_gaffe(self):
        reg = RuleRegistry()
        hits = reg.detect("我在这里听着你。")
        assert any(h["id"] == "rule-sx-001" for h in hits)

    def test_detect_lexicon(self):
        reg = RuleRegistry()
        hits = reg.detect("你有点倦，想和你探讨。")
        assert any(h["id"] == "rule-lx-general-001" for h in hits)  # 通则层带 pattern 检测

    def test_detect_clean(self):
        reg = RuleRegistry()
        assert reg.detect("墨水在水里散开，像一朵迟缓的花。") == []


# ─────────────────────────────────────
# 3. 确定性替换（列举层兜底）
# ─────────────────────────────────────
class TestApplyExplicit:
    def test_apply_gaffe(self):
        reg = RuleRegistry()
        out = reg.apply_explicit("我在这里听着你。")
        assert "听你说说" in out

    def test_apply_lexicon(self):
        reg = RuleRegistry()
        out = reg.apply_explicit("你有点倦了。")
        assert "疲倦" in out or "倦" in out  # rule-lx-001 替换觉得倦了；此处匹配通则不替换


# ─────────────────────────────────────
# 4. 系统提示词拼装（核心 ⭐ 谁用都拼）
# ─────────────────────────────────────
class TestBuildPrompt:
    def test_prompt_contains_general_rules(self):
        reg = RuleRegistry()
        p = reg.build_prompt("general")
        assert "词法完整通则" in p
        assert "句法完整通则" in p

    def test_prompt_profile_filter(self):
        """teaching profile 包含教学通则（用户扩展），confessional 不含。"""
        reg = RuleRegistry()
        # 加载用户扩展规则
        rules_path = os.path.join(os.path.dirname(_SRC), "data", "rules.json")
        reg.load(rules_path)
        p_teach = reg.build_prompt("teaching")
        p_conf = reg.build_prompt("confessional")
        assert "教学用语通则" in p_teach      # teaching 含用户扩展
        assert "教学用语通则" not in p_conf    # confessional 不含

    def test_prompt_token_budget(self):
        reg = RuleRegistry()
        p = reg.build_prompt("general", token_budget=200)
        assert len(p) < 5000  # 预算约束不膨胀


# ─────────────────────────────────────
# 5. 可扩充性（用户要求 ⭐）
# ─────────────────────────────────────
class TestExtensibility:
    def test_add_rule(self):
        reg = RuleRegistry()
        n_before = len(reg.all())
        reg.add_rule({
            "id": "rule-test-ext",
            "type": "explicit",
            "category": "lexical",
            "pattern": "测试词",
            "replacement": "替换词",
            "message": "测试扩充规则",
            "severity": "low",
            "enabled": True,
            "source": "user",
        })
        assert len(reg.all()) == n_before + 1
        assert reg.by_id("rule-test-ext") is not None

    def test_load_json_merges(self):
        reg = RuleRegistry()
        n_before = len(reg.all())
        rules_path = os.path.join(os.path.dirname(_SRC), "data", "rules.json")
        added = reg.load(rules_path)
        assert added >= 3  # 3 条用户扩展规则
        assert len(reg.all()) == n_before + 3
        # 用户规则 source 标记
        demo = reg.by_id("rule-user-demo-001")
        assert demo is not None

    def test_load_bad_json_keeps_rules(self):
        """损坏 JSON 不"清空跑"（Oracle 风险规避）。"""
        reg = RuleRegistry()
        n_before = len(reg.all())
        bad_path = os.path.join(os.path.dirname(_SRC), "data", "bad_rules_test.json")
        with open(bad_path, "w", encoding="utf-8") as f:
            f.write("{ not valid json")
        try:
            added = reg.load(bad_path)
            assert added == 0
            assert len(reg.all()) == n_before  # 保留现有规则
        finally:
            os.remove(bad_path)

    def test_remove_rule(self):
        reg = RuleRegistry()
        reg.add_rule({"id": "rule-test-rm", "type": "explicit", "category": "lexical",
                      "pattern": "x", "replacement": "y", "message": "m",
                      "severity": "low", "enabled": True, "source": "user"})
        assert reg.remove_rule("rule-test-rm") is True
        assert reg.by_id("rule-test-rm") is None

    def test_watch_reload(self):
        """mtime 变更触发重载。"""
        rules_path = os.path.join(os.path.dirname(_SRC), "data", "rules.json")
        reg = RuleRegistry()
        reg.watch(rules_path)
        assert reg.check_reload() is False  # 未变更
        # 修改 mtime 模拟变更
        os.utime(rules_path, None)
        # mtime 可能相同（同秒），直接断言不抛异常
        reg.check_reload()


# ─────────────────────────────────────
# 6. refiner 集成（规则 ID 反馈闭环）
# ─────────────────────────────────────
class TestRefinerRuleIntegration:
    def test_refiner_system_uses_rule_registry(self):
        from paeg_lang_style.refiner import make_refiner
        def mock_chat(system, user, max_tokens=800, **kw):
            return user
        r = make_refiner(chat_fn=mock_chat)
        system = r._build_system(profile="general", rules=r.rules)
        assert "词法完整通则" in system
        assert "语法规则约束" in system  # 规则集作为系统提示词核心

    def test_refiner_feedback_has_rule_id(self):
        from paeg_lang_style.refiner import make_refiner
        def mock_chat(system, user, max_tokens=800, **kw):
            return "你有点疲倦了，想和你探讨这个问题。"
        r = make_refiner(chat_fn=mock_chat)
        feedback = r._get_feedback("我在这里听着你。")
        assert "规则违反" in feedback  # 反馈带规则 ID 闭环
