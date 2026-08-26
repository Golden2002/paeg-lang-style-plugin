# -*- coding: utf-8 -*-
"""paeg_lang_style.refiner — LLM 输出重写工具（注入式 chat_fn）。

从 PAEG 教育智能体 language_refiner.py 提取（v0.12-v0.71）。
用户需求 ⭐：重写大模型输出的工具。

**关键解耦改造（P1 ⭐）**：
- 原 PAEG 版 `LanguageRefiner.__init__` 中 `self._chat_fn = chat_fn or self._default_chat`，
  `_default_chat` 硬引 `subagents._safe_chat`——插件独立运行时不可用。
- 本插件版：**强制外部注入 chat_fn**，`chat_fn=None` 时抛 `TypeError`（fail-fast）。
  其他项目只需传自己的 LLM 调用包装即可完全独立使用。

用法：
    def my_chat(system, user, max_tokens=800, **kw) -> str:
        return call_my_llm(system, user, max_tokens=max_tokens)
    refiner = LanguageRefiner(llm=None, chat_fn=my_chat)
    refined = refiner.refine(text)  # 重写 LLM 输出
"""

from __future__ import annotations

import json
import os
from typing import Callable, List, Optional

from .ai_taste import detect_ai_taste
from .forbidden import ForbiddenWords
from .rules import check_ellipsis, fix_known_gaffes

# chat_fn 类型：LLM 调用包装 (system, user, max_tokens=800, **kw) -> str
ChatFn = Callable[..., str]


class LanguageRefiner:
    """语言优化 Agent：矫正文本，去除 AI 痕迹（注入式 chat_fn）。"""

    def __init__(self, llm=None, corpus_path: Optional[str] = None, chat_fn: Optional[ChatFn] = None):
        # P1 ⭐ 强制外部注入 chat_fn（插件独立可用，不依赖任何宿主项目）
        if chat_fn is None:
            raise TypeError(
                "LanguageRefiner 需要注入 chat_fn（LLM 调用包装）。"
                "示例：LanguageRefiner(chat_fn=lambda sys, usr, **kw: my_llm(sys, usr, **kw))"
            )
        self.llm = llm
        self._chat_fn = chat_fn
        self.corpus = self._load_corpus(corpus_path)
        self.forbidden = ForbiddenWords()
        self.forbidden.load_json()  # 合并 data/forbidden_words.json（外部动态词库）

    def _load_corpus(self, corpus_path: Optional[str] = None) -> list:
        """加载语料（薇依语料 few-shot；可替换为中性语料）。"""
        path = corpus_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data", "weil_corpus.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    # ── 检测 ──
    def detect_ai_tells(self, text: str) -> List[str]:
        """检测文本中的 AI 痕迹（违禁词命中）。返回命中列表。"""
        return self.forbidden.detect(text)

    def detect_ai_taste_signals(self, text: str):
        """检测 AI 味信号（句长变异/过渡词密度/三段式/破折号）。"""
        return detect_ai_taste(text)

    def check_grammar(self, text: str) -> List[str]:
        """检测语法问题（词法/句法/动宾/介词/复合句）。返回问题列表。"""
        return check_ellipsis(text)

    # ── 重写 ──
    def refine(self, text: str, context: str = "", max_rounds: int = 2) -> str:
        """用语料矫正文本（v0.13：Self-Refine 多轮）。

        流程（基于 Self-Refine 论文 NeurIPS 2023 + AI 味检测）：
        1. 病句确定性修正（规则兜底，无 LLM）
        2. 检测 AI 味信号（句长变异/过渡词/三段清单/破折号）
        3. 若有 AI 味 → LLM 改写
        4. 复检信号，未达标且有轮次 → 再改写（最多 max_rounds 轮）
        5. 最终病句规则再跑一遍（改写可能重新引入悬空'听着你'）
        """
        if not text or not text.strip():
            return text

        # L0-0：病句确定性修正（规则兜底）
        text = fix_known_gaffes(text)

        # 检测 AI 味信号
        try:
            signals = detect_ai_taste(text)
            ai_prob = signals.ai_likelihood
        except Exception:
            ai_prob = 1.0 if self.detect_ai_tells(text) else 0.2

        # 省略句/语法问题触发改写
        has_ellipsis = len(self.check_grammar(text)) > 0

        # 高频词重复（affection 语言刻板）
        rep_issues = self._check_word_repetition(text)
        has_repetition = bool(rep_issues)

        # 无 AI 味、无省略句、无重复、且不算太长 → 直接返回
        if ai_prob < 0.4 and not has_ellipsis and not has_repetition and len(text) < 400 \
                and not self.detect_ai_tells(text):
            return text

        system = self._build_system()
        current = text
        for round_i in range(max_rounds):
            feedback = self._get_feedback(current, context)
            try:
                refined = self._chat_fn(system,
                                        self._build_user(current, context, feedback),
                                        max_tokens=800)
            except Exception:
                break
            if not refined or not refined.strip():
                break
            current = refined.strip()
            # 复检
            try:
                signals = detect_ai_taste(current)
                if signals.ai_likelihood < 0.4:
                    break
            except Exception:
                break

        # 最终收口：病句规则再跑一遍（改写可能重新引入悬空'听着你'）
        return fix_known_gaffes(current)

    def _get_feedback(self, text: str, context: str = "") -> str:
        """生成 AI 味反馈（用检测器信号 + 语法问题 + 违禁词）。"""
        feedback_parts = []
        try:
            s = detect_ai_taste(text)
            if s.burstiness_cv < 0.35:
                feedback_parts.append("句子长度太均匀，需要长短交替（短句制造节奏）")
            if s.marker_density > 1.5:
                feedback_parts.append("过渡词/套话过多，需要删除")
            if s.three_list_count > 0:
                feedback_parts.append("避免'三点/三步'式列举（薇依用二、四、七）")
            if s.em_dash_count > 3:
                feedback_parts.append("破折号过多，每段最多一个")
            if not feedback_parts and s.ai_likelihood >= 0.35:
                feedback_parts.append("整体偏'AI腔'，请用更朴素、具体的语言重写")
        except Exception:
            pass
        # 语法完整性检查（省略句/无主句）
        omit_issues = self.check_grammar(text)
        if omit_issues:
            feedback_parts.append("存在省略句/无主句，需补全主谓宾：" + "；".join(omit_issues[:3]))
        # 违禁词命中
        hits = self.detect_ai_tells(text)
        if hits:
            feedback_parts.append(f"检测到这些套话：{', '.join(hits[:5])}")
        # 词汇重复（affection 模式高频词轮换）
        rep_issues = self._check_word_repetition(text)
        if rep_issues:
            feedback_parts.append(
                "【词汇重复】在 200 字内同一名词/形容词复用过多，"
                "请用同义词轮换：" + "；".join(rep_issues[:4])
            )
        return "；".join(feedback_parts) if feedback_parts else "请保持原意，用更自然、朴素的语言表达。"

    # v0.50 ⭐ 高频词重复检测（affection 语言刻板）："重量/重要/真实/看见/听见"等在
    # 200 字内 ≥3 次即触发反馈，提示用同义词轮换。
    _REPETITION_TRIGGER_WORDS = (
        "重量", "重要", "真实", "看见", "听见", "感受", "感受到",
        "空间", "声音", "陪伴", "力量", "勇气", "温暖", "沉重",
    )
    _REPETITION_WINDOW = 200
    _REPETITION_THRESHOLD = 3

    def _check_word_repetition(self, text: str, threshold: int = 3) -> list:
        """检测 LLM 高频词重复。"""
        if not text:
            return []
        window = text[:self._REPETITION_WINDOW]
        issues = []
        for w in self._REPETITION_TRIGGER_WORDS:
            count = window.count(w)
            if count >= threshold:
                if w in ("重量", "沉重"):
                    hint = "建议换用：分量/担子/沉甸甸的那一块"
                elif w in ("听见",):
                    hint = "建议换用：在/在这儿/听着你说"
                elif w in ("看见",):
                    hint = "建议换用：注意到/你说的事"
                elif w in ("感受", "感受到"):
                    hint = "建议换用：体察到/我心里"
                elif w in ("空间",):
                    hint = "建议换用：余地/位置/口子"
                elif w in ("声音",):
                    hint = "建议换用：语气/话/那句话"
                elif w in ("陪伴",):
                    hint = "建议换用：在/在这儿陪着"
                elif w in ("力量",):
                    hint = "建议换用：靠得住的东西/撑得住的那一点"
                elif w in ("勇气",):
                    hint = "建议换用：敢/迈出这一步"
                elif w in ("温暖",):
                    hint = "建议换用：不冷/实在/具体"
                elif w in ("重要",):
                    hint = "建议换用：要紧/不能省/关键"
                elif w in ("真实",):
                    hint = "建议换用：实打实的/不算虚/这回事"
                else:
                    hint = "建议换用同义词"
                issues.append(f"'{w}' 在前 {self._REPETITION_WINDOW} 字内出现 {count} 次——{hint}")
        return issues

    def _build_user(self, text: str, context: str = "", feedback: str = "") -> str:
        fb = f"\n【改写方向】{feedback}" if feedback else ""
        return f"""请改写下面的文本为薇依式的语言：{fb}
{('（上下文：' + context + '）\n') if context else ''}
【待改写文本】
{text[:1500]}"""

    def _build_system(self) -> str:
        """构建语言优化的 system prompt（含语料 few-shot）。"""
        corpus_examples = "\n\n".join(
            f"【语料原句 {i+1}】\n{c[:300]}" for i, c in enumerate(self.corpus[:6])
        )
        return f"""你是一位语言校正者，任务是让 AI 生成的文字像一位真实的人写的——朴素、准确、有力量。

## 语料参考（来自真实文本）
{corpus_examples if corpus_examples else "（无语料，请遵循下方核心特征）"}

## 语言核心特征
- 朴素：说具体的话，不用空泛的大词。"墨水在水里散开"胜过"生命的奥秘"。
- 准确：用词精确，不模糊。描述动作用自然的动词（观察/比较/拆开），不硬造"拉一拉"类怪动词短语。
- 有力量：每句话立得住——要么是事实，要么是观点，要么是问题。
- 温柔：不哄不捧，认真对待。不用"你真棒""加油"这类廉价鼓励。
- 不煽情：不用"让我们踏上""知识的海洋""点亮智慧"等套话；不堆语气词（嗯/啊/呢/吧/呀）。
- **语法完整**：每一句都是完整句子（有主谓宾），不写省略句、无主句。
  ❌"一句话记住：…"→✅"我们可以用一句话来记住：…"
  ❌"先看一个现象"→✅"我们先来看一个现象。"
- **无主语短语禁止单独成句**：
  ❌"不催你。"→✅"老师不催你，你慢慢来。"
  ❌"先不急。"→✅"我们先不着急。"
- **动宾搭配必须通顺**：
  ❌"带着重量"→✅"有很重的分量"/"本身就很重"
  ❌"进行一个分析"→✅"分析"
- **词法完整——使用完整词语**：
  ❌"觉得倦了" → ✅"觉得疲倦了"
  ❌"道出真相" → ✅"说出真相"
  ❌"探知本质" → ✅"探索并了解本质"
- **句法完整——句子成分完整 + 动宾搭配合理 + 充足修饰**：
  ❌"我想与你探讨。"→✅"我想与你探讨这个问题。"
  ❌"关于学习方面。"（悬空）→✅"在学习方面，要重视方法。"
  ❌"我在这里听着你。"（病句）→✅"我就在这里听你说说。"
- **介词规范**：介词必须带宾语，不得悬空、误用、缺失。

## 你的任务
把下面的 AI 生成文本改写为规范、朴素、有力量的语言。要求：
1. **最小改动**：保留原意、事实、和已通顺的句子；只改有问题的部分，不重写整个风格
2. 删掉 AI 痕迹（套话、廉价鼓励、空洞形容词、语气词堆砌）
3. 句子变短，用词变具体
4. **补全省略句**：所有省略主语/谓语的句子改成完整句式（纯祈使指令如"请做这道题"可保留）
5. **修正动宾搭配**：动宾不通的（"带着重量""进行一个分析"）改为自然搭配
6. **补全省略词**：压缩/省略的词形改为完整词形（『倦』→『疲倦』『道出』→『说出来』）
7. **补足悬空宾语 + 句子成分完整**：动词缺宾语的句子补足宾语；确保每句有完整的主谓宾/主系表结构
8. **补充修饰成分与连接词**：用连接词（因为/所以/但是/同时/然后）标明逻辑关系
9. 消除重复：重复说明同一观点的句子合并或删去冗余
10. **不改变语气和人格**：保留原文本的温度和亲切感，只修正语法问题——不要改成生硬的书面语
11. 直接输出改写后的文本，不要解释，不要加"改写如下"之类的话
12. **保留 markdown 结构**：文本可能含 `### 标题`、`- 列表项`、`> 引用`、`**加粗**` 等结构。这些结构是刻意设计的内容骨架，**必须原样保留**——只修正措辞/语法，绝不删除任何 `###`/`-`/`>` 开头的段落或列表项。"""


def make_refiner(*, chat_fn: ChatFn, llm=None, corpus_path: Optional[str] = None) -> LanguageRefiner:
    """工厂方法（Oracle R12）：注入 chat_fn 创建 LanguageRefiner。"""
    return LanguageRefiner(llm=llm, corpus_path=corpus_path, chat_fn=chat_fn)
