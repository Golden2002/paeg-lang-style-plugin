# -*- coding: utf-8 -*-
"""行为一致性测试（Oracle R-SK3 ⭐）：插件输出 vs PAEG 原实现字符串相等。

输入 20+ 段真实样本（含 PAEG eval 常见病句），断言：
- fix_known_gaffes：插件 == PAEG language_refiner.fix_known_gaffes
- check_ellipsis 命中数：插件 == PAEG LanguageRefiner._check_ellipsis（规则层对等）
- detect_ai_taste verdict：插件 == PAEG ai_taste_detector.detect_ai_taste

运行前提：PAEG 项目在 D:/wbo-workspace/paeg_project/05_实现原型（仅本测试读取，不改写）。
"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_lang_style import fix_known_gaffes, check_ellipsis, detect_ai_taste as plugin_detect

# PAEG 原实现路径（测试只读）
_PAEG_DIR = r"D:/wbo-workspace/paeg_project/05_实现原型"
_HAS_PAEG = os.path.isdir(_PAEG_DIR)


# 20 段真实样本（PAEG 教学/倾诉/讲稿场景常见病句）
SAMPLES = [
    "我在这里听着你。",
    "老师在这里听着你，你慢慢说。",
    "你说吧，我听着你。",
    "我在这里听着你说，别急。",
    "先看一个现象。",
    "不催你，你慢慢来。",
    "这句话本身，已经带着重量。",
    "我想与你探讨。",
    "每天固定时间用。",
    "因为学习了，进步了。",
    "总的来说，让我们一起赋能这个时代，点亮无限可能！",
    "墨水在水里散开，像一朵迟缓的花。",
    "记住这一句：极限环并不稀奇。",
    "关键在理解，不在记忆。",
    "关于学习方面。",
    "通过这次讲解，让学生明白了。",
    "你有点倦，想和你探讨。",
    "作为主力，这个软件很好用。",
    "别贪多，一口吃不成胖子。",
    "感觉心里有点沉。",
]


@pytest.mark.skipif(not _HAS_PAEG, reason="PAEG 项目不可用（跳过一致性对比）")
def test_gaffes_parity_with_paeg():
    """fix_known_gaffes：插件输出与 PAEG 原实现逐样本字符串相等。"""
    paeg_sys_path = sys.path.copy()
    sys.path.insert(0, _PAEG_DIR)
    try:
        from language_refiner import fix_known_gaffes as paeg_gaffes
    finally:
        sys.path[:] = paeg_sys_path

    mismatches = []
    for s in SAMPLES:
        plug_out = fix_known_gaffes(s)
        paeg_out = paeg_gaffes(s)
        if plug_out != paeg_out:
            mismatches.append((s, plug_out, paeg_out))
    assert not mismatches, f"行为不一致 {len(mismatches)} 例: {mismatches[:3]}"


@pytest.mark.skipif(not _HAS_PAEG, reason="PAEG 项目不可用（跳过一致性对比）")
def test_ellipsis_parity_with_paeg():
    """check_ellipsis：插件命中数 vs PAEG _check_ellipsis 命中数一致。"""
    paeg_sys_path = sys.path.copy()
    sys.path.insert(0, _PAEG_DIR)
    try:
        from language_refiner import LanguageRefiner as PaegRefiner
        paeg_r = PaegRefiner(llm=None, chat_fn=lambda *a, **k: "")
    finally:
        sys.path[:] = paeg_sys_path

    mismatches = []
    for s in SAMPLES:
        plug_n = len(check_ellipsis(s))
        paeg_n = len(paeg_r._check_ellipsis(s))
        if plug_n != paeg_n:
            mismatches.append((s, plug_n, paeg_n))
    assert not mismatches, f"命中数不一致 {len(mismatches)} 例: {mismatches[:3]}"


@pytest.mark.skipif(not _HAS_PAEG, reason="PAEG 项目不可用（跳过一致性对比）")
def test_ai_taste_parity_with_paeg():
    """detect_ai_taste verdict：插件 vs PAEG ai_taste_detector 一致。"""
    paeg_sys_path = sys.path.copy()
    sys.path.insert(0, _PAEG_DIR)
    try:
        from ai_taste_detector import detect_ai_taste as paeg_detect
    finally:
        sys.path[:] = paeg_sys_path

    mismatches = []
    for s in SAMPLES:
        plug_v = plugin_detect(s).verdict
        paeg_v = paeg_detect(s).verdict
        if plug_v != paeg_v:
            mismatches.append((s, plug_v, paeg_v))
    assert not mismatches, f"verdict 不一致 {len(mismatches)} 例: {mismatches[:3]}"


def test_samples_cover_8_rules():
    """20 段样本必须触发 8 类语法规则中的至少 6 类（规则覆盖验证）。"""
    # 各规则触发样本
    rule_samples = {
        "病句修正(听着你)": "我在这里听着你。",
        "词法完整(倦)": "你有点倦，想和你探讨。",
        "动宾搭配(带着重量)": "这句话本身，已经带着重量。",
        "悬空宾语(与你探讨)": "我想与你探讨。",
        "无主语(不催你)": "不催你，你慢慢来。",
        "介词(关于/对于)": "关于学习方面。",
        "复合句(因为)": "因为学习了，进步了。",
        "语义(最直觉的)": "这是最直觉的地方。",
    }
    triggered = 0
    for name, sample in rule_samples.items():
        if check_ellipsis(sample) or (sample != fix_known_gaffes(sample)):
            triggered += 1
    assert triggered >= 6, f"8 类规则仅触发 {triggered} 类"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
