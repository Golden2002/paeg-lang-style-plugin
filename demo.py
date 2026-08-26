# -*- coding: utf-8 -*-
"""paeg-lang-style 独立运行 demo（Oracle R4：不依赖 PAEG 任何模块）。

用法：
    python demo.py                    # 规则层演示（无 LLM）
    python demo.py --with-llm         # LLM 重写演示（需注入 chat_fn）

演示能力：
1. 病句确定性修正（"我在这里听着你。" → "我就在这里听你说说。"）
2. 语法检查（省略句/无主句/动宾搭配/词法完整/悬空宾语/介词规范/复合句缺主语）
3. AI 味检测（句长变异/过渡词密度/三段式/破折号）
4. 动态违禁词库检测（AI 腔/空洞大词/伪共情/廉价鼓励/网络用语）
5. 系统提示词获取（词法/句法/违禁 分段）
6. （可选）LLM 输出重写（注入 chat_fn 后多轮 Self-Refine）
"""
from __future__ import annotations

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 兼容独立运行（未 pip install）：把 src/ 加入 path
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from paeg_lang_style import (
    fix_known_gaffes, check_ellipsis, detect_ai_taste,
    ForbiddenWords, get_style_prompt, make_refiner,
)


def _demo_rules():
    """规则层演示（无需 LLM）。"""
    print("=" * 60)
    print("paeg-lang-style 独立运行 demo（规则层）")
    print("=" * 60)

    print("\n[1] 病句确定性修正（fix_known_gaffes）")
    cases = [
        "我在这里听着你。",
        "老师在这里听着你，你慢慢说。",
        "你说吧，我听着你。",
        "我在这里听着你说，别急。",  # 合法搭配，保持不变
    ]
    for c in cases:
        print(f"  输入: {c}")
        print(f"  输出: {fix_known_gaffes(c)}")

    print("\n[2] 语法检查（check_ellipsis）")
    cases = [
        "先看一个现象。",
        "不催你，你慢慢来。",
        "这句话本身，已经带着重量。",
        "我想与你探讨。",
        "每天固定时间用。",
        "因为学习了，进步了。",
    ]
    for c in cases:
        issues = check_ellipsis(c)
        print(f"  输入: {c}")
        if issues:
            for i in issues:
                print(f"    ⚠ {i}")
        else:
            print("    ✓ 无语法问题")

    print("\n[3] AI 味检测（detect_ai_taste）")
    cases = [
        "总的来说，让我们一起赋能这个时代，点亮无限可能！",
        "墨水在水里散开，像一朵迟缓的花。",
    ]
    for c in cases:
        s = detect_ai_taste(c)
        print(f"  输入: {c[:30]}…")
        print(f"  → ai_likelihood={s.ai_likelihood} verdict={s.verdict}")

    print("\n[4] 动态违禁词库（ForbiddenWords）")
    fb = ForbiddenWords()
    c = "总的来说，这是一个很好的方案，让我们一起加油，赋能未来！"
    hits = fb.detect(c)
    print(f"  输入: {c}")
    print(f"  命中: {hits}")
    fb.add("自定义禁词")
    print(f"  动态新增后 detect('包含 自定义禁词 的文本') → {fb.detect('包含 自定义禁词 的文本')}")
    fb.remove("自定义禁词")

    print("\n[5] 系统提示词获取（get_style_prompt）")
    for sec in ("weil", "lexicon", "syntax", "forbidden"):
        s = get_style_prompt(sec)
        print(f"  [{sec}] {len(s)} 字符")

    print("\n[6] 语言规范重写工具（make_refiner + refine）")
    print("  （未注入 chat_fn 时不触发——规则层已覆盖病句）")


def _demo_llm():
    """LLM 重写演示（注入 chat_fn）。"""
    print("=" * 60)
    print("LLM 重写演示（注入 chat_fn）")
    print("=" * 60)

    def mock_chat(system, user, max_tokens=800, **kw):
        # 模拟 LLM：将违禁词替换为规范表达（demo 用，真实项目注入真实 LLM）
        out = user
        for w, rep in [("让我们一起", ""), ("赋能", "帮助"), ("点亮", "照亮"),
                       ("无限可能", "许多可能"), ("总的来说", "")]:
            out = out.replace(w, rep)
        return out.strip()

    refiner = make_refiner(chat_fn=mock_chat)
    text = "总的来说，让我们一起赋能这个时代，点亮无限可能！"
    print(f"  输入: {text}")
    print(f"  输出: {refiner.refine(text, max_rounds=1)}")


if __name__ == "__main__":
    _demo_rules()
    if "--with-llm" in sys.argv:
        _demo_llm()
