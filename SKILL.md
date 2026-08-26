---
name: paeg-lang-style
description: 中文语言规范检查与修正（词法/句法规则约束 + 动态违禁词库 + LLM 输出重写）。适用任何中文文本生成场景：AI 腔检测、病句修正（听着你→听你说说）、词法完整（倦→疲倦）、动宾搭配（带着重量→有分量）、悬空宾语补足、介词规范、复合句缺主语检测。需要让生成文本"像人话"、规范、朴素、有力量时使用。
license: MIT
compatibility: paeg, opencode, claude-code, codex
metadata:
  version: "0.1.0"
---

# paeg-lang-style — 中文语言规范插件

## What I do

对中文文本做语言规范检查与修正：
1. **病句确定性修正**（纯规则，无 LLM）："我在这里听着你。" → "我就在这里听你说说。"
2. **词法完整**：双字词不得压缩为单字（倦→疲倦 / 乏→疲乏 / 沉→沉重 / 道出→说出来）
3. **动宾搭配**：动词须自然接宾语（"带着重量"→"有很重的分量"）
4. **悬空宾语补足**："我想与你探讨。" → "我想与你探讨这个问题。"
5. **无主语短语**禁止单独成句（"不催你。"→"老师不催你，你慢慢来。"）
6. **复合句分句缺主语**（"因为学习了，进步了。"→"因为学习了，所以我进步了。"）
7. **介词规范**（不得悬空/误用/缺失）
8. **AI 味检测**：句长变异/过渡词密度/三段式/破折号/段落对称
9. **动态违禁词库**：AI 腔套话/空洞大词/伪共情/廉价鼓励/网络用语
10. **LLM 输出重写**：注入 chat_fn 后多轮 Self-Refine 深度矫正

## When to use me

- 任何中文文本生成后需要"去 AI 味"、规范语法时
- 教学/倾诉/讲稿/PPT/讲义等教育场景的文本质量把关
- 需要把 LLM 输出改写为"像一位真实的人写的"朴素、准确、有力量的语言时

## How to use

```python
from paeg_lang_style import (
    gate_content,          # 守门入口（L0 规则 + L2 深度矫正）
    gate_short,            # 短文本快路径
    make_refiner,          # 重写工具工厂（注入 chat_fn）
    get_style_prompt,      # 系统提示词（weil/lexicon/syntax/forbidden 分段）
    fix_known_gaffes,      # 病句确定性修正（纯规则）
    check_ellipsis,        # 语法检查
    detect_ai_taste,       # AI 味检测
    ForbiddenWords,        # 动态违禁词库
)
```

## References

- 完整 8 条语法规则：`README.md`
- 架构与数据流：`docs/architecture.md`
- 接入 PAEG 指南：`docs/integration_paeg.md`
- 20 段对比样例：`docs/samples_20.md`
