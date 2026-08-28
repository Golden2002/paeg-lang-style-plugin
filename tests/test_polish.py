# -*- coding: utf-8 -*-
"""L-08 全局守门兼容入口（polish_text）测试。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from paeg_lang_style import polish_text, make_refiner


class TestPolishText:
    def test_polish_text_triggers_refine(self):
        """AI 味 + 病句 → 触发 refine，输出不含"听着你"。"""
        calls = []

        def mock_chat(system, user, max_tokens=800, **kw):
            calls.append(1)
            return "我就在这里听你说说。"

        r = make_refiner(chat_fn=mock_chat)
        out = polish_text("总的来说，我在这里听着你。让我们一起加油！", refiner=r)
        assert calls != []          # refine 被触发
        assert "听着你" not in out  # 病句已修正

    def test_polish_text_silent_fallback(self):
        """refine 抛异常 → 静默回退原文（不变）。"""

        class BoomRefiner:
            def refine(self, text, context="", max_rounds=2):
                raise RuntimeError("boom")

        original = "总的来说，我在这里听着你。让我们一起加油！"
        assert polish_text(original, refiner=BoomRefiner()) == original
