# -*- coding: utf-8 -*-
"""paeg-lang-style 全产物实测脚本（可复现）。

用法：
    cd <插件根目录>
    python test_artifacts/run_tests.py            # 全部（含真实 LLM 重写）
    python test_artifacts/run_tests.py --no-llm   # 仅确定性产物（离线）

LLM 注入：从 ~/.local/share/opencode/auth.json 读取 deepseek key，
构造 chat_fn 调用 DeepSeek（OpenAI 兼容接口）——零宿主依赖，仅测试脚本用。

输出：UTF-8 打印到 stdout；重定向到文件可保留中文：
    python test_artifacts/run_tests.py > test_artifacts/_run_out.txt
"""
import io, os, sys, json, difflib

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from paeg_lang_style import (
    fix_known_gaffes, check_ellipsis, detect_ai_taste, ForbiddenWords,
    get_style_prompt, make_refiner, gate_content, gate_short, polish_text,
    proofread, RuleRegistry,
)
from paeg_lang_style.rules_enhanced import (
    check_lexicon_general_rule, check_syntax_general_rule, check_adverbial_general_rule,
)
from paeg_lang_style import style_presets, term_guard

USE_LLM = "--no-llm" not in sys.argv


def _load_key():
    p = os.path.join(os.path.expanduser("~"), ".local", "share", "opencode", "auth.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)["deepseek"]["key"]


import urllib.request


def deepseek_chat(system, user, max_tokens=800, **kw):
    key = _load_key()
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": max_tokens, "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]


def sec(t):
    print("\n" + "=" * 66)
    print(t)
    print("=" * 66)


def main():
    sec("1. 病句确定性修正 fix_known_gaffes")
    for t in ["我在这里听着你。", "老师在这里听着你，你慢慢说。", "我在这里听着你说，别急。"]:
        print(f"   {t}  ->  {fix_known_gaffes(t)}")

    sec("2. 语法检查 check_ellipsis")
    for t in ["他道出了真相。", "这句话带着重量。", "我想与你探讨。", "不催你，你慢慢来。",
              "因为学习了，进步了。", "这是最直觉的地方。"]:
        print(f"   {t}")
        for i in check_ellipsis(t):
            print(f"       ⚠ {i}")

    sec("3. 通则检测")
    for t in ["你有点倦。", "他工作很辛苦，别去麻烦别人。", "别贪多，一口吃不成胖子。", "复习单词。"]:
        print(f"   词法: {t!r} -> {check_lexicon_general_rule(t)}")
        print(f"   句法: {t!r} -> {check_syntax_general_rule(t)}")
        print(f"   状语: {t!r} -> {check_adverbial_general_rule(t)}")

    sec("4. AI 味检测 detect_ai_taste")
    for t in ["总的来说，让我们一起赋能这个时代，点亮无限可能！",
              "墨水在水里散开，像一朵迟缓的花。",
              "我今天喝了牛奶，吃了牛肉面，味道不错。"]:
        s = detect_ai_taste(t)
        print(f"   {t[:24]!r} -> ai_likelihood={s.ai_likelihood} verdict={s.verdict} "
              f"(marker={s.marker_density}, em_dash={s.em_dash_count})")

    sec("5. 动态违禁词库 ForbiddenWords")
    fb = ForbiddenWords()
    print(f"   detect('总的来说，让我们一起加油，赋能未来！') -> {fb.detect('总的来说，让我们一起加油，赋能未来！')}")
    print(f"   内置词数 {len(fb.words)}；load_json() 新增 {ForbiddenWords().load_json()}")

    sec("6. 系统提示词 get_style_prompt")
    for s in ("all", "weil", "lexicon", "syntax", "forbidden"):
        print(f"   [{s}] {len(get_style_prompt(s))} 字符")

    sec("7. 可扩充规则集 RuleRegistry")
    reg = RuleRegistry()
    from collections import Counter
    print(f"   规则总数 {len(reg.all())}，分类 {dict(Counter(r['category'] for r in reg.all()))}")
    print(f"   apply_explicit('我在这里听着你。') -> {reg.apply_explicit('我在这里听着你。')!r}")

    sec("8. 守门入口 gate_content / gate_short / polish_text")
    print(f"   gate_content('我在这里听着你。') -> {gate_content('我在这里听着你。')!r}")
    print(f"   gate_short('老师在这里听着你。') -> {gate_short('老师在这里听着你。')!r}")

    sec("9. 校对报告 proofread")
    txt = "他写了一个帐号，感到好象有点倦。这个结论绝对正确！！我在这里听着你。  他说：\"大概也许可行。\""
    pr = proofread(txt, style="general")
    print(json.dumps(pr, ensure_ascii=False, indent=2))

    sec("10. 文体预设 + 术语保护")
    print("   styles:", json.dumps(style_presets.list_styles(), ensure_ascii=False))
    print(f"   load_terms(domains=[]) = {len(term_guard.load_terms(domains=[]))}（通用文体无术语保护）")
    print(f"   load_terms(domains=['legal']) = {len(term_guard.load_terms(domains=['legal']))}")

    sec("11. LLM 输出重写 LanguageRefiner.refine（真实 DeepSeek）")
    if USE_LLM:
        ref = make_refiner(chat_fn=deepseek_chat)
        raw = "总的来说，让我们一起赋能这个时代，点亮无限可能！"
        out = ref.refine(raw, max_rounds=1)
        print(f"   输入: {raw}")
        print(f"   输出: {out}")
        print(f"   字符相似度: {difflib.SequenceMatcher(None, raw, out).ratio():.3f}")
    else:
        print("   （--no-llm 跳过）")

    sec("12. MCP 服务")
    import asyncio
    from paeg_lang_style.mcp_server import build_server
    mcp = build_server()
    tools = asyncio.run(mcp.list_tools())
    print("   tools:", sorted(t.name for t in tools))
    print("   resources:", sorted(r.uri for r in asyncio.run(mcp.list_resources())))
    print("   prompts:", sorted(p.name for p in asyncio.run(mcp.list_prompts())))


if __name__ == "__main__":
    main()
