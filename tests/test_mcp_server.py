# -*- coding: utf-8 -*-
"""MCP server 测试（§3.109 可及性 ⭐）：build/list_tools/call_tool。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

pytest.importorskip("fastmcp")

from paeg_lang_style.mcp_server import build_server, SERVER_NAME


@pytest.fixture(scope="module")
def mcp():
    return build_server()


class TestMcpServer:
    def test_server_name(self, mcp):
        assert SERVER_NAME == "paeg-lang-style"

    def test_tools_registered(self, mcp):
        """7 个 MCP 工具全部注册。"""
        import asyncio
        tools = asyncio.run(mcp.list_tools())
        names = {t.name for t in tools}
        assert "normalize_text" in names
        assert "language_policy_check" in names
        assert "forbidden_words" in names
        assert "check_grammar" in names
        assert "check_ai_taste" in names
        assert "build_style_prompt" in names
        assert "list_rules" in names
        assert len(names) >= 7

    def test_normalize_text(self, mcp):
        """normalize_text 修正病句。"""
        import asyncio
        r = asyncio.run(mcp.call_tool("normalize_text", {"text": "我在这里听着你。"}))
        assert r.is_error is False
        text = r.content[0].text
        assert "听你说说" in text

    def test_language_policy_check(self, mcp):
        """language_policy_check 检测 AI 味 + 违禁词。"""
        import asyncio
        r = asyncio.run(mcp.call_tool("language_policy_check", {"text": "总的来说，让我们一起加油！"}))
        assert r.is_error is False
        sc = r.structured_content
        assert sc["verdict"] in ("AI", "Mixed")
        assert "总的来说" in sc["forbidden_hits"]

    def test_check_grammar(self, mcp):
        """check_grammar 语法检查。"""
        import asyncio
        r = asyncio.run(mcp.call_tool("check_grammar", {"text": "先看一个现象。"}))
        assert r.is_error is False
        assert len(r.structured_content["result"]) >= 1

    def test_build_style_prompt(self, mcp):
        """build_style_prompt 拼装提示词（谁用都拼）。"""
        import asyncio
        r = asyncio.run(mcp.call_tool("build_style_prompt", {"section": "syntax", "profile": "teaching"}))
        assert r.is_error is False
        text = r.content[0].text
        assert "主谓宾" in text or "句法" in text

    def test_list_rules(self, mcp):
        """list_rules 规则集清单。"""
        import asyncio
        r = asyncio.run(mcp.call_tool("list_rules", {}))
        assert r.is_error is False
        rules = r.structured_content["result"]
        assert isinstance(rules, list)
        assert len(rules) >= 10

    def test_forbidden_words(self, mcp):
        """forbidden_words 增删查。"""
        import asyncio
        r = asyncio.run(mcp.call_tool("forbidden_words", {"action": "add", "word": "测试禁词mcp"}))
        assert r.is_error is False
        r2 = asyncio.run(mcp.call_tool("forbidden_words", {"action": "check", "word": "测试禁词mcp"}))
        assert "在词库中" in r2.content[0].text
        asyncio.run(mcp.call_tool("forbidden_words", {"action": "remove", "word": "测试禁词mcp"}))
